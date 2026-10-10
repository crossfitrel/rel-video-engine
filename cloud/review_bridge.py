#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""review_bridge — גשר בין עמוד הרוויו בטלפון (Artifact + db) למנוע הרוויו הקיים (review-app/server.py).

העיקרון: לא כותבים מחדש את הלוגיקה. כל פעולה של הראל בטלפון עוברת לאותם endpoints שהאפליקציה
המקומית (5112) קראה — דרך Flask test_client בתוך התהליך, בלי שרת ובלי פורט. ככה revisions, tasks,
artifact_id נעול, corrections.jsonl ו-derive_state ממשיכים לעבוד בדיוק כמו במק.

קריאה וכתיבה ל-db של העמוד נעשות ע"י Claude בסשן (כלי ArtifactData) — הסקריפט רק מתרגם קבצי JSON:
  1. Claude: ArtifactData list comments/actions --out_dir IN        (מה הראל עשה)
  2. python3 cloud/review_bridge.py apply --in IN --out OUT           (מחיל על פרויקטי העבודה)
  3. Claude: ArtifactData batch עם OUT/db_writes.json                  (מסמן consumed, מעדכן סטטוסים)
  4. python3 cloud/review_bridge.py export --out OUT                   (מצב כל הפרויקטים → מסמכי projects)
     + OUT/uploads_needed.json — פרוקסי רוויו/קאבר שצריך להעלות כ-asset (Artifact publish asset:true)
  5. python3 cloud/review_bridge.py record-asset --project NAME --kind video|cover --sha SHA --url URL

מזהי מסמכים ב-db חייבים ASCII ⇒ project doc_id = "p-<monday_item_id>" (או p-<sha1 של שם התיקייה>).
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYS = HERE.parent
sys.path.insert(0, str(SYS / "tools")); sys.path.insert(0, str(SYS / "review-app"))
from relvid.paths import work_root                      # noqa: E402

STATE_MAP = {  # derive_state → מצב בעמוד
    "not_started": "draft", "running": "finishing", "failed": "blocked", "in_review": "review",
    "approved": "approved", "final": "review", "awaiting_schedule_approval": "cover_review",
    "ready_to_schedule": "ready_to_schedule", "scheduled": "scheduled", "published": "published",
}
PROXY_MAX = 14 * 1024 * 1024          # מגבלת asset בינארי בכלי (15MB) פחות מרווח
ASSETS_FILE = "cloud_assets.json"    # בתוך תיקיית הפרויקט: sha → url שכבר הועלה
MAP_FILE = "cloud_comment_map.json"  # db comment id ↔ comment_id מקומי


def _client():
    import server  # review-app/server.py — WORK נקבע מ-REL_WORK_ROOT
    server.app.testing = True
    return server.app.test_client()


def _j(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _w(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def sha256(path, n=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(n), b""):
            h.update(b)
    return h.hexdigest()


def doc_id(W: Path) -> str:
    m = _j(W / "project_manifest.json", {}) or {}
    item = m.get("monday_item_id")
    return f"p-{item}" if item else "p-" + hashlib.sha1(W.name.encode()).hexdigest()[:12]


def by_doc_id():
    out = {}
    for d in work_root().iterdir():
        if d.is_dir() and (d / "edl.json").exists():
            out[doc_id(d)] = d
    return out


def make_proxy(src: Path, out: Path) -> Path:
    """פרוקסי רוויו 720×1280 שנכנס במגבלת asset. רק לצפייה — לא נוגע ב-FINAL ולא נשלח לפרסום."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                               capture_output=True, text=True).stdout.strip() or 60)
    kbps = max(500, int((PROXY_MAX * 8 / 1000) / max(dur, 1) * 0.92) - 96)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src), "-vf", "scale=720:-2",
                    "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps*1.3)}k",
                    "-bufsize", f"{kbps*2}k", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out)], check=True)
    if out.stat().st_size > PROXY_MAX:
        raise RuntimeError(f"proxy {out.stat().st_size} > {PROXY_MAX}")
    return out


def export(out: Path):
    c = _client()
    rows = c.get("/api/projects").get_json() or []
    docs, uploads = [], []
    for r in rows:
        W = work_root() / r["name"]
        m = _j(W / "project_manifest.json", {}) or {}
        assets = _j(W / ASSETS_FILE, {}) or {}
        disp = ((r.get("artifacts") or {}).get("display") or {})
        aid = disp.get("artifact_id")
        src = None
        if aid:
            a = _j(W / "artifacts" / aid / "artifact.json", {}) or {}
            p = W / "artifacts" / aid / a.get("file", "FINAL.mp4")
            src = p if p.exists() else None
        if not src and (W / "FINAL.mp4").exists():
            src = W / "FINAL.mp4"
        video_url = None
        if src:
            s = sha256(src)
            video_url = (assets.get(s) or {}).get("url")
            if not video_url:
                uploads.append({"project": r["name"], "doc_id": doc_id(W), "kind": "video", "src": str(src), "sha": s,
                                "proxy": str(W / "REVIEW_PROXY.mp4")})
        sched = m.get("schedule_approval") or {}
        cover_url = None
        cp = sched.get("cover_path")
        if cp:
            cpp = (W / cp) if not os.path.isabs(cp) else Path(cp)
            if cpp.exists():
                cs = sha256(cpp)
                cover_url = (assets.get(cs) or {}).get("url")
                if not cover_url:
                    uploads.append({"project": r["name"], "doc_id": doc_id(W), "kind": "cover", "src": str(cpp), "sha": cs})
        pf = _j(W / "PREFLIGHT.json", {}) or {}
        findings = pf.get("findings") or []
        lines = [f.get("message") or f.get("msg") or f.get("id") for f in findings if isinstance(f, dict)][:6]
        fixed = []
        try:
            cl = c.get(f"/api/changelog/{r['name']}").get_json() or {}
            for f in (cl.get("fixes") or cl.get("items") or [])[:12]:
                fixed.append({"text": f.get("text") or f.get("summary") or "", "verdict": f.get("verdict") or f.get("status")})
        except Exception:
            pass
        state = STATE_MAP.get(r.get("state"), r.get("state") or "draft")
        if state == "review" and not pf.get("ready_for_harel", pf.get("ready")):
            state = "fixing"   # אין תוצר להראל בלי מבקר-קדם תקין (חוזה 1)
        docs.append({"doc_id": doc_id(W), "data": {
            "title": m.get("title") or r["name"].replace("-", " "), "workdir": r["name"], "dept": r.get("dept"),
            "monday_item_id": m.get("monday_item_id"), "state": state, "raw_state": r.get("state"),
            "version": disp.get("version"), "artifact_id": aid, "duration": disp.get("duration") or r.get("kept"),
            "video_url": video_url,
            "preflight": {"ready": bool(pf.get("ready_for_harel", pf.get("ready"))),
                          "verdict": pf.get("verdict") or pf.get("summary"), "lines": [l for l in lines if l]},
            "fixed": fixed, "cover_url": cover_url,
            "caption": sched.get("caption_text") or sched.get("caption_draft"),
            "publish_date": r.get("planned_date"), "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }})
    _w(out / "projects.json", docs)
    _w(out / "uploads_needed.json", uploads)
    print(f"[bridge] export: {len(docs)} פרויקטים · {len(uploads)} העלאות נדרשות → {out}")


def _read_dir(d: Path):
    if not d.exists():
        return []
    rows = []
    for f in sorted(d.glob("*.json")):
        j = _j(f, {}) or {}
        doc = j.get("data") if isinstance(j.get("data"), dict) else j
        rows.append({"id": j.get("id") or f.stem, "version": j.get("version"), **doc})
    return rows


def apply(inp: Path, out: Path):
    """inp/comments/*.json + inp/actions/*.json (פלט ArtifactData out_dir) → פעולות על הפרויקטים + db_writes.json."""
    c = _client(); idx = by_doc_id(); writes = []; log = []
    comments = _read_dir(inp / "comments"); actions = _read_dir(inp / "actions")
    for cm in comments:
        W = idx.get(cm.get("project"))
        if not W:
            continue
        cmap = _j(W / MAP_FILE, {}) or {}
        if cm["id"] not in cmap and cm.get("status") == "sent":
            r = c.post(f"/api/comments/{W.name}", json={"text": cm.get("text", ""), "time_start": cm.get("t"),
                       "category": cm.get("category", "general"), "queue": True, "on_final": True, "actor": "harel"}).get_json() or {}
            if r.get("ok"):
                cmap[cm["id"]] = r["comment"]["comment_id"]; _w(W / MAP_FILE, cmap)
                log.append(f"{W.name}: הערה {cm['id']} → {cmap[cm['id']]}")
        # סטטוס מקומי → db
        lid = cmap.get(cm["id"])
        if lid:
            from relvid import tasks as tasks_mod
            local = next((x for x in tasks_mod.list_comments(W) if x.get("comment_id") == lid), None)
            if local:
                fv = (local.get("fix_verdict") or {}).get("verdict") if isinstance(local.get("fix_verdict"), dict) else local.get("fix_verdict")
                new = {"queued_for_claude": "sent", "in_progress": "sent", "resolved": "fixed", "open": "sent"}.get(local["status"], local["status"])
                if fv == "verified": new = "verified"
                if fv == "not_fixed": new = "not_fixed"
                upd = {"status": new}
                if local.get("resolution"): upd["reply"] = local["resolution"][:300]
                if any(cm.get(k) != v for k, v in upd.items()):
                    writes.append({"op": "update", "collection": "comments", "doc_id": cm["id"], "data": upd, "if_version": cm.get("version")})
    for a in actions:
        if a.get("consumed"):
            continue
        W = idx.get(a.get("project"))
        res = {"ok": False, "error": "פרויקט לא נמצא"}
        if W:
            t = a.get("type")
            if t == "approve_publish":
                res = c.post(f"/api/approve/{W.name}", json={"actor": "harel", "source": "cloud-review"}).get_json() or {}
            elif t == "approve_cover_caption":
                res = c.post(f"/api/schedule-review/{W.name}", json={"action": "approve", "caption_text": a.get("caption")}).get_json() or {}
            elif t == "request_cover_change":
                res = c.post(f"/api/schedule-review/{W.name}", json={"action": "request_changes", "note": a.get("note"),
                             "caption_draft": a.get("caption")}).get_json() or {}
            elif t == "send_notes":
                res = {"ok": True, "note": "ההערות עצמן מוחלות בלולאת ההערות"}
        log.append(f"{a.get('project')}: {a.get('type')} → {'✓' if res.get('ok') else '✗ ' + str(res.get('error'))}")
        writes.append({"op": "update", "collection": "actions", "doc_id": a["id"], "if_version": a.get("version"),
                       "data": {"consumed": True, "result": "ok" if res.get("ok") else str(res.get("error"))[:200],
                                "consumed_at": time.strftime("%Y-%m-%dT%H:%M:%S")}})
    _w(out / "db_writes.json", writes)
    print("\n".join(log) or "[bridge] apply: אין פעולות חדשות")
    print(f"[bridge] {len(writes)} עדכוני db → {out/'db_writes.json'}")


def record_asset(project: str, kind: str, sha: str, url: str):
    W = work_root() / project
    a = _j(W / ASSETS_FILE, {}) or {}
    a[sha] = {"kind": kind, "url": url, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _w(W / ASSETS_FILE, a)
    print(f"[bridge] asset {kind} נרשם ל-{project}")


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("--out", required=True)
    a = sub.add_parser("apply"); a.add_argument("--in", dest="inp", required=True); a.add_argument("--out", required=True)
    p = sub.add_parser("proxy"); p.add_argument("--src", required=True); p.add_argument("--out", required=True)
    r = sub.add_parser("record-asset"); r.add_argument("--project", required=True); r.add_argument("--kind", required=True)
    r.add_argument("--sha", required=True); r.add_argument("--url", required=True)
    x = ap.parse_args()
    if x.cmd == "export": export(Path(x.out))
    elif x.cmd == "apply": apply(Path(x.inp), Path(x.out))
    elif x.cmd == "proxy": print(make_proxy(Path(x.src), Path(x.out)))
    elif x.cmd == "record-asset": record_asset(x.project, x.kind, x.sha, x.url)


if __name__ == "__main__":
    main()
