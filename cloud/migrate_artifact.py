#!/usr/bin/env python3
"""migrate_artifact — העברה חד-פעמית של ה-db של עמוד ה-Artifact (B799jvngoLRUMYzoz1XqZn) ל-Supabase (v11, 29.10.26).
קלט: תיקייה עם projects/ comments/ actions/ (ArtifactData list --out_dir) + תיקיית נכסים (/_blob/<id>.<ext>).
  VIDEO_ADMIN_KEY=… python3 cloud/migrate_artifact.py --db DIR --assets DIR [--dry]
אידמפוטנטי: מזהי הערות/פעולות נשמרים; נכס שהועלה נבדק ב-sha256 אחרי הורדה חוזרת.
"""
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import video_api as V

STATE_KEEP = {"draft", "review", "fixing", "approved", "finishing", "cover_review", "ready_to_schedule", "scheduled", "published", "blocked"}


def load(d):
    out = {}
    for f in sorted(glob.glob(os.path.join(d, "*.json"))):
        j = json.load(open(f, encoding="utf-8"))
        out[os.path.basename(f)[:-5]] = j.get("data", j)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); ap.add_argument("--assets", required=True); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    projects, comments, actions = (load(os.path.join(a.db, k)) for k in ("projects", "comments", "actions"))
    assets = {os.path.basename(p).split(".")[0]: p for p in glob.glob(os.path.join(a.assets, "*"))}
    report = {"projects": 0, "assets": 0, "comments": 0, "actions": 0, "missing_assets": []}
    for pid, p in projects.items():
        row = {k: p.get(k) for k in ("title", "dept", "workdir", "raw_state", "version", "duration", "publish_date", "caption", "preflight", "fixed", "monday_item_id")}
        row.update(id=pid, state=p.get("state") if p.get("state") in STATE_KEEP else "draft", hidden=bool(p.get("hidden")),
                   test=pid == "p-e2etest" or bool(p.get("test")), source="artifact-migration",
                   extra={k: v for k, v in p.items() if k not in row and k not in ("video_url", "cover_url")} | {"artifact_updated_at": p.get("updated_at")})
        for key, col, ctype, ext in (("video_url", "video_path", "video/mp4", "mp4"), ("cover_url", "cover_path", "image/png", "png")):
            v = p.get(key) or ""
            if v.startswith("/_blob/"):
                aid = v[7:]
                if aid not in assets:
                    report["missing_assets"].append(f"{pid}:{key}"); continue
                path = f"{pid}/v{p.get('version') or 1}-{ 'proxy' if ext == 'mp4' else 'cover'}-{aid[:8]}.{ext}"
                if not a.dry:
                    V.upload(assets[aid], path, ctype)
                row[col] = path; report["assets"] += 1
        if not a.dry:
            r = V.call("project_upsert", project=row)
            if not r.get("ok"): raise SystemExit(f"{pid}: {r}")
        report["projects"] += 1
    for cid, c in comments.items():
        if c.get("project") not in projects: continue
        if not a.dry:
            V.call("comment_import", comment={"id": cid, "project_id": c["project"], "version": c.get("version"), "t": c.get("t"), "text": c.get("text") or "",
                   "category": c.get("category"), "status": c.get("status"), "reply": c.get("reply"), "at": c.get("at"), "extra": {"by": c.get("by")}})
        report["comments"] += 1
    for aid, x in actions.items():
        if x.get("project") not in projects: continue
        payload = {k: v for k, v in x.items() if k not in ("project", "type", "version", "consumed", "consumed_at", "handled_as", "at")}
        if not a.dry:
            V.call("action_import", action={"id": aid, "project_id": x["project"], "type": x.get("type"), "version": x.get("version"), "payload": payload,
                   "consumed": bool(x.get("consumed")), "consumed_at": x.get("consumed_at"), "handled_as": x.get("handled_as"), "at": x.get("at")})
        report["actions"] += 1
    print(json.dumps(report, ensure_ascii=False))
    return 1 if report["missing_assets"] else 0


if __name__ == "__main__":
    sys.exit(main())
