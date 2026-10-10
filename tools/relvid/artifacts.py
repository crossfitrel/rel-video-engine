#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
artifacts — Artifact Store: כל תוצר וידאו מוצלח נשמר לצמיתות ולא נדרס (v9.4).
==============================================================================
שורש הבעיה (נמדד 31.7.26 על ~/rel-video-work): 71 ריצות גימור מוצלחות,
71 output_hash שונים — ורק 51 קובצי וידאו קיימים בפועל. בפרויקט אחד
("יום-בחיים-של-הראל") היו 16 ריצות מוצלחות ונשארו 3 קבצים. הסיבה:

  * ה"זהות" של גרסה הייתה **שם הקובץ** `FINAL.mp4`, וכל ריצה דרסה אותו;
  * הגיבוי `FINAL_prev_<ts>.mp4` נגזם ל-2 אחרונים ע"י `cleanup_work.py`;
  * `run_finish.py` חתם `output_hash` על `FINAL.mp4` **גם בריצה שנכשלה** —
    כלומר רשומת ריצה כושלת נשאה את החתימה של FINAL ישן ותקין (21 מקרים).

הפתרון: מזהה תוצר קבוע (`artifact_id`) שאינו תלוי בשם קובץ, תיקייה משלו
שלעולם לא נדרסת ולא נמחקת בניקוי, ו-checksum sha256 **מלא** לאימות.

מבנה בדיסק (בתוך תיקיית הפרויקט):

    artifacts/
      pointers.json               ← latest_candidate / approved_final / published_final
      index.json                  ← cache בלבד; ניתן לבנייה מחדש מהתיקיות
      art_<hex>/
        FINAL.mp4                 ← hardlink לתוכן (או עותק) — 0444, לא נדרס
        artifact.json             ← זהות, checksum, קישורים, מצב
        provenance.json           ← עותק FINAL_PROVENANCE.json של אותה ריצה
        qa_report.json
        broll_plan.json

עקרונות:
  * **התיקיות הן מקור האמת.** `index.json` הוא cache; `reindex()` בונה אותו
    מחדש מהדיסק. גם `pointers.json` ניתן לשחזור — כל artifact נושא בעצמו
    `approved_at` / `published_at`.
  * **יצירה אטומית.** נבנה ב-`.staging_<id>/`, ורק כשהכל שלם `os.rename`
    לשם הסופי. קריסה באמצע משאירה `.staging_*` — שלא נספר כגרסה, ומנוקה
    ע"י `sweep_staging()`.
  * **ריצה כושלת לא יוצרת artifact** ולעולם לא מקבלת חתימה של FINAL ישן.
  * **hardlink כברירת מחדל** — אפס עלות דיסק. הקובץ ב-artifact מקבל 0444,
    כך ש-`open(...,"w")` / `O_TRUNC` על אותו inode נכשל. rename (וזה כל מה
    שהצנרת עושה ל-FINAL.mp4: `PENDING.replace(FINAL)`) ממשיך לעבוד, כי rename
    דורש הרשאת כתיבה על התיקייה ולא על הקובץ.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import (atomic_write_json, new_id, now_ts, read_json, sha256_file,
               sha256_json)

ART_DIRNAME = "artifacts"
POINTERS = "pointers.json"
INDEX = "index.json"
FINAL_NAME = "FINAL.mp4"
POINTER_KINDS = ("latest_candidate", "approved_final", "published_final")

# קבצי לוואי שנשמרים לצד כל תוצר (מקור בתיקיית הפרויקט → שם בתוך ה-artifact)
SIDECARS = {
    "FINAL_PROVENANCE.json": "provenance.json",
    "qa_report.json": "qa_report.json",
    "broll_plan.json": "broll_plan.json",
}

# v9.23 (11.9.26) — Visual Hook: קבצי לוואי שנקפאים **רק** כשרשומת המקור של
# ה-FINAL הזה מצביעה עליהם עם hash תואם. בלי זה, קובץ plan שנשאר מריצה קודמת
# היה נקפא עם גרסה שלא נבנתה ממנו. פרויקט ישן בלי השדה — תקף כמו קודם.
HOOK_SIDECARS = ("visual_hook_plan.json", "visual_hook_render.json",
                 "visual_hook_report.json", "visual_hook_qa.json")


def _hook_sidecars_for(w: Path) -> dict:
    prov = read_json(w / "FINAL_PROVENANCE.json", {}) or {}
    vh = prov.get("visual_hook") or {}
    want = vh.get("sidecars") or {}
    out = {}
    for name, digest_ in want.items():
        if name not in HOOK_SIDECARS:
            continue
        p = w / name
        if not p.exists():
            continue
        import hashlib
        h = "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
        if h == digest_:
            out[name] = h
    return {"meta": {k: vh.get(k) for k in ("mode", "applied", "recipe", "plan_digest",
                                            "input_digest", "approved_digest")},
            "sidecars": out} if vh else {}


# ---------------------------------------------------------------- נתיבים
def adir(workdir, create=False) -> Path:
    d = Path(workdir) / ART_DIRNAME
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def artifact_dir(workdir, artifact_id) -> Path:
    return adir(workdir) / str(artifact_id)


def artifact_final(workdir, artifact_id) -> Path:
    return artifact_dir(workdir, artifact_id) / FINAL_NAME


def is_inside_artifacts(path) -> bool:
    """שומר סף לכלי ניקוי: כל נתיב שיושב תחת artifacts/ הוא מחוץ לתחום."""
    return ART_DIRNAME in Path(path).parts


# ---------------------------------------------------------------- עזר
def probe_duration(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(p)],
            capture_output=True, text=True, timeout=60)
        return round(float(r.stdout.strip()), 2)
    except Exception:
        return None


def _link_or_copy(src: Path, dst: Path, link=True):
    """hardlink אם אפשר (אותו filesystem), אחרת עותק. מחזיר "link"/"copy"."""
    if link:
        try:
            os.link(src, dst)
            return "link"
        except OSError:
            pass
    shutil.copy2(src, dst)
    return "copy"


def _freeze(path: Path):
    try:
        os.chmod(path, 0o444)
    except OSError:
        pass


# ---------------------------------------------------------------- pointers
def pointers(workdir) -> dict:
    p = read_json(adir(workdir) / POINTERS, None)
    if p is None:
        p = {k: None for k in POINTER_KINDS}
        p["log"] = []
    for k in POINTER_KINDS:
        p.setdefault(k, None)
    p.setdefault("log", [])
    return p


def _save_pointers(workdir, p):
    atomic_write_json(adir(workdir, create=True) / POINTERS, p)


def set_pointer(workdir, kind, artifact_id, actor="system", note=None):
    """מזיז מצביע. יצירת מועמד חדש **לעולם** לא נוגעת ב-approved/published."""
    if kind not in POINTER_KINDS:
        raise ValueError(f"מצביע לא מוכר: {kind}")
    if artifact_id and not (artifact_dir(workdir, artifact_id) / "artifact.json").exists():
        raise ValueError(f"artifact לא קיים: {artifact_id}")
    p = pointers(workdir)
    prev = p.get(kind)
    p[kind] = artifact_id
    p["log"].append({"ts": now_ts(), "kind": kind, "from": prev,
                     "to": artifact_id, "actor": actor, "note": note})
    _save_pointers(workdir, p)
    return p


def _stamp(workdir, artifact_id, field, actor):
    """חותם approved_at/published_at *בתוך* ה-artifact — כדי ש-pointers.json
    יהיה ניתן לשחזור גם אם ייעלם, וכדי שהניקוי יידע מה אסור לגעת בו."""
    ap = artifact_dir(workdir, artifact_id) / "artifact.json"
    a = read_json(ap)
    if not a:
        return None
    a[field] = now_ts()
    a.setdefault("retain", True)
    a.setdefault("history", []).append({"ts": now_ts(), "event": field, "actor": actor})
    atomic_write_json(ap, a)
    return a


def approve(workdir, artifact_id, actor="harel"):
    """מסמן גרסה כמאושרת. הגרסה המאושרת הקודמת נשארת קיימת ונגישה."""
    _stamp(workdir, artifact_id, "approved_at", actor)
    return set_pointer(workdir, "approved_final", artifact_id, actor=actor)


def publish(workdir, artifact_id, actor="harel", note=None):
    _stamp(workdir, artifact_id, "published_at", actor)
    return set_pointer(workdir, "published_final", artifact_id, actor=actor, note=note)


def protected_ids(workdir) -> set:
    """מזהים שאסור למחוק לעולם: מאושר, פורסם, ומועמד אחרון."""
    p = pointers(workdir)
    ids = {p.get(k) for k in POINTER_KINDS if p.get(k)}
    for a in list_artifacts(workdir):
        if a.get("approved_at") or a.get("published_at") or a.get("retain"):
            ids.add(a["artifact_id"])
    return ids


# ---------------------------------------------------------------- יצירה
def create_artifact(workdir, source_final=None, *, run_id=None, revision_id=None,
                    edl_hash=None, input_hash=None, pipeline_version=None,
                    summary=None, extra=None, link=True, actor="pipeline",
                    make_candidate=True):
    """יוצר תוצר קבוע מתוך קובץ וידאו מוגמר. אטומי: staging → rename.

    מחזיר את רשומת ה-artifact. **לא** מזיז את approved_final/published_final.
    אם התוכן זהה (checksum) ל-artifact קיים — מחזיר אותו ולא יוצר כפילות
    (idempotency: מיגרציה חוזרת / refinish שהפיק בייט-זהה)."""
    w = Path(workdir)
    src = Path(source_final) if source_final else (w / FINAL_NAME)
    if not src.exists():
        raise FileNotFoundError(f"אין קובץ וידאו ליצירת artifact: {src}")
    if src.stat().st_size == 0:
        raise ValueError(f"קובץ ריק — לא נוצר artifact: {src}")

    checksum = sha256_file(src, quick=False)
    existing = find_by_checksum(w, checksum)
    if existing:
        if make_candidate and pointers(w).get("latest_candidate") != existing["artifact_id"]:
            set_pointer(w, "latest_candidate", existing["artifact_id"], actor=actor,
                        note="תוכן זהה לתוצר קיים")
        return existing

    root = adir(w, create=True)
    aid = new_id("art")
    staging = root / f".staging_{aid}"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    try:
        mode = _link_or_copy(src, staging / FINAL_NAME, link=link)
        # אימות אחרי ההעתקה — לא סומכים על הצלחת copy/link בלי לבדוק
        after = sha256_file(staging / FINAL_NAME, quick=False)
        if after != checksum:
            raise IOError("checksum לא תואם אחרי העתקה — התוצר לא נשמר")
        for src_name, dst_name in SIDECARS.items():
            sp = w / src_name
            if sp.exists():
                shutil.copy2(sp, staging / dst_name)
        vh_freeze = _hook_sidecars_for(w)
        for name in (vh_freeze.get("sidecars") or {}):
            shutil.copy2(w / name, staging / name)
            _freeze(staging / name)

        prov = read_json(w / "FINAL_PROVENANCE.json", {}) or {}
        qa = read_json(w / "qa_report.json", {}) or {}
        mani = read_json(w / "project_manifest.json", {}) or {}
        edl = read_json(w / "edl.json", {}) or {}
        plan = read_json(w / "broll_plan.json", {}) or {}
        prefs = mani.get("finish_prefs") or {}

        rec = {
            "artifact_id": aid,
            "schema": 1,
            "version": _next_version(w),
            "created_at": now_ts(),
            "actor": actor,
            "project": w.name,
            "project_id": mani.get("project_id"),
            "file": FINAL_NAME,
            "storage": mode,
            "size_bytes": src.stat().st_size,
            "checksum": checksum,
            "duration": probe_duration(src),
            "run_id": run_id or prov.get("run_id"),
            "revision_id": revision_id or prov.get("revision_id"),
            "edl_hash": edl_hash or prov.get("edl_hash") or (sha256_json(edl) if edl else None),
            "input_hash": input_hash or prov.get("input_hash"),
            "pipeline_version": pipeline_version,
            "kept_dur": prov.get("kept_dur") or edl.get("kept_dur"),
            "speed": prov.get("speed"),
            "qa": {"pass": qa.get("pass"),
                   "gates": [g.get("gate") or g.get("name")
                             for g in (qa.get("gates") or []) if isinstance(g, dict)],
                   "warnings": sum(1 for g in (qa.get("gates") or [])
                                   if isinstance(g, dict) and g.get("warn"))} if qa else None,
            "music": (prefs.get("music") or {}).get("track"),
            "broll_items": len(plan.get("plan") or []) if plan else 0,
            "brand": mani.get("brand"),
            "content_type": mani.get("content_type"),
            "dept": mani.get("dept"),
            "summary": summary,
            "source_path": str(src),
            "approved_at": None,
            "published_at": None,
            "retain": False,
            "history": [{"ts": now_ts(), "event": "created", "actor": actor}],
        }
        # v9.15 — "מה תוקן בגרסה הזו" נחתם **ברגע היצירה**, כשחותמות הזמן עוד
        # אומרות את האמת. שורש: אחרי המיגרציה של v9.4 כל 71 הגרסאות נושאות
        # created_at זהה, ולכן שיוך בדיעבד של תיקון לגרסה הוא ניחוש. מכאן
        # והלאה זו רשומה. כישלון כאן לעולם לא מפיל יצירת גרסה — הוא רק מחזיר
        # את הגרסה הזו למסלול ההסקה, וה-changelog מסמן אותה ככזו.
        try:
            from . import changelog as cl_mod
            _prev = list_artifacts(w)
            rec["fixes"] = cl_mod.stamp_fixes(
                w, since_ts=(_prev[-1].get("created_at") if _prev else None))
        except Exception as _e:                                # pragma: no cover
            rec["fixes_error"] = str(_e)
        if vh_freeze:
            rec["visual_hook"] = dict(vh_freeze["meta"], sidecars=vh_freeze["sidecars"])
        if extra:
            rec.update(extra)
        atomic_write_json(staging / "artifact.json", rec)
        final_dir = root / aid
        os.rename(staging, final_dir)          # ← נקודת האטומיות
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    _freeze(final_dir / FINAL_NAME)
    if make_candidate:
        set_pointer(w, "latest_candidate", aid, actor=actor, note=summary)
    reindex(w)
    return rec


def _next_version(workdir):
    return max([a.get("version") or 0 for a in list_artifacts(workdir)] + [0]) + 1


def sweep_staging(workdir):
    """מנקה שאריות staging של יצירות שקרסו באמצע. אף פעם לא נוגע ב-art_*."""
    root = adir(workdir)
    n = 0
    if not root.is_dir():
        return 0
    for d in root.glob(".staging_*"):
        shutil.rmtree(d, ignore_errors=True)
        n += 1
    return n


# ---------------------------------------------------------------- קריאה
def list_artifacts(workdir, verify_integrity=False):
    """כל התוצרים של הפרויקט, מהישן לחדש. נקרא מהתיקיות — לא מהאינדקס."""
    root = adir(workdir)
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        rec = read_json(d / "artifact.json")
        if not rec:
            continue
        rec = dict(rec)
        rec["dir"] = str(d)
        rec["path"] = str(d / rec.get("file", FINAL_NAME))
        rec["exists"] = (d / rec.get("file", FINAL_NAME)).exists()
        if verify_integrity:
            rec["integrity"] = verify(workdir, rec["artifact_id"])
        out.append(rec)
    out.sort(key=lambda r: (r.get("version") or 0, r.get("created_at") or ""))
    return out


def get_artifact(workdir, artifact_id):
    rec = read_json(artifact_dir(workdir, artifact_id) / "artifact.json")
    if not rec:
        return None
    d = artifact_dir(workdir, artifact_id)
    rec = dict(rec)
    rec["dir"] = str(d)
    rec["path"] = str(d / rec.get("file", FINAL_NAME))
    rec["exists"] = (d / rec.get("file", FINAL_NAME)).exists()
    return rec


def find_by_checksum(workdir, checksum):
    if not checksum:
        return None
    for a in list_artifacts(workdir):
        if a.get("checksum") == checksum:
            return a
    return None


def verify(workdir, artifact_id, deep=True):
    """אימות אמיתי: הקובץ קיים ו-checksum תואם. קובץ חסר/לא תואם = תקלה."""
    rec = read_json(artifact_dir(workdir, artifact_id) / "artifact.json")
    if not rec:
        return {"ok": False, "state": "missing_record",
                "detail": "אין artifact.json — התוצר לא רשום"}
    f = artifact_dir(workdir, artifact_id) / rec.get("file", FINAL_NAME)
    if not f.exists():
        return {"ok": False, "state": "missing_file",
                "detail": "קובץ הווידאו חסר — הגרסה אינה ניתנת לצפייה"}
    if f.stat().st_size != rec.get("size_bytes"):
        return {"ok": False, "state": "size_mismatch",
                "detail": f"גודל שונה מהרשום ({f.stat().st_size} מול {rec.get('size_bytes')})"}
    if deep:
        cur = sha256_file(f, quick=False)
        if cur != rec.get("checksum"):
            return {"ok": False, "state": "checksum_mismatch",
                    "detail": "התוכן השתנה מאז היצירה — אין להסתמך על הגרסה הזו"}
    # v9.23 — ראיית ה-Visual Hook קפואה יחד עם התוצר. שינוי בה = אותה חומרה.
    import hashlib
    for name, digest_ in ((rec.get("visual_hook") or {}).get("sidecars") or {}).items():
        sp = artifact_dir(workdir, artifact_id) / name
        if not sp.exists():
            return {"ok": False, "state": "hook_sidecar_missing",
                    "detail": f"קובץ ראיית הפתיחה החזותית חסר: {name}"}
        if "sha256:" + hashlib.sha256(sp.read_bytes()).hexdigest() != digest_:
            return {"ok": False, "state": "hook_sidecar_mismatch",
                    "detail": f"ראיית הפתיחה החזותית שונתה אחרי ההקפאה: {name}"}
    return {"ok": True, "state": "ok", "detail": None}


def status_of(workdir, artifact_id, ptrs=None):
    p = ptrs or pointers(workdir)
    if p.get("published_final") == artifact_id:
        return "published"
    if p.get("approved_final") == artifact_id:
        return "approved"
    rec = read_json(artifact_dir(workdir, artifact_id) / "artifact.json") or {}
    if rec.get("published_at"):
        return "was_published"
    if rec.get("approved_at"):
        return "was_approved"
    return "candidate"


def display_target(workdir):
    """מה האפליקציה צריכה להציג כברירת מחדל, ומה להגיד עליו.

    כלל: מציגים את **המאושרת**. אין מאושרת ⇒ מציגים את המועמד האחרון, אבל
    מסמנים במפורש שהוא אינו מאושר. אם קיימת גרסה חדשה מזו שמוצגת — אומרים.
    """
    arts = list_artifacts(workdir)
    p = pointers(workdir)
    by_id = {a["artifact_id"]: a for a in arts}
    approved = by_id.get(p.get("approved_final"))
    latest = by_id.get(p.get("latest_candidate")) or (arts[-1] if arts else None)
    published = by_id.get(p.get("published_final"))
    show = approved or latest
    newer = []
    if show:
        newer = [a for a in arts if (a.get("version") or 0) > (show.get("version") or 0)]
    return {
        "artifact_id": show["artifact_id"] if show else None,
        "version": show.get("version") if show else None,
        "is_approved": bool(approved and show and
                            show["artifact_id"] == approved["artifact_id"]),
        "is_published": bool(published and show and
                             show["artifact_id"] == published["artifact_id"]),
        "status": status_of(workdir, show["artifact_id"], p) if show else None,
        "newer_count": len(newer),
        "newer_version": (newer[-1].get("version") if newer else None),
        "newer_artifact_id": (newer[-1]["artifact_id"] if newer else None),
        "total": len(arts),
        "pointers": {k: p.get(k) for k in POINTER_KINDS},
        "duration": show.get("duration") if show else None,
        "created_at": show.get("created_at") if show else None,
    }


def artifact_of_live_final(workdir):
    """איזה artifact מתאים ל-FINAL.mp4 שעל הדיסק כרגע (או None)."""
    f = Path(workdir) / FINAL_NAME
    if not f.exists():
        return None
    st = f.stat()
    for a in list_artifacts(workdir):
        if a.get("size_bytes") == st.st_size:
            if sha256_file(f, quick=False) == a.get("checksum"):
                return a["artifact_id"]
    return None


def activate(workdir, artifact_id, actor="harel"):
    """הופך גרסה קיימת ל-FINAL.mp4 הפעיל — בלי לאבד את הגרסה שהייתה שם.

    לפני ההחלפה, ה-FINAL הנוכחי מובטח כ-artifact (אם עוד לא היה כזה), כך
    שהפעולה הזו לעולם לא מוחקת וידאו."""
    w = Path(workdir)
    rec = get_artifact(w, artifact_id)
    if not rec:
        return {"ok": False, "error": f"artifact לא נמצא: {artifact_id}"}
    v = verify(w, artifact_id)
    if not v["ok"]:
        return {"ok": False, "error": f"אי אפשר להפעיל גרסה פגומה: {v['detail']}"}
    live = w / FINAL_NAME
    captured = None
    if live.exists() and artifact_of_live_final(w) is None:
        captured = create_artifact(w, live, actor=actor,
                                   summary="נלכד אוטומטית לפני החלפת הגרסה הפעילה",
                                   make_candidate=False)
    tmp = w / f".FINAL.activate.{os.getpid()}.mp4"
    if tmp.exists():
        tmp.unlink()
    _link_or_copy(Path(rec["path"]), tmp, link=True)
    try:
        os.chmod(tmp, 0o644)
    except OSError:
        pass
    os.replace(tmp, live)
    return {"ok": True, "artifact_id": artifact_id, "version": rec.get("version"),
            "captured_previous": captured["artifact_id"] if captured else None}


# ---------------------------------------------------------------- אינדקס
def reindex(workdir):
    """בונה מחדש את index.json מהתיקיות (cache בלבד — בטוח להריץ תמיד)."""
    w = Path(workdir)
    arts = list_artifacts(w)
    p = pointers(w)
    idx = {
        "updated_at": now_ts(),
        "count": len(arts),
        "pointers": {k: p.get(k) for k in POINTER_KINDS},
        "artifacts": [{k: a.get(k) for k in
                       ("artifact_id", "version", "created_at", "checksum",
                        "duration", "size_bytes", "run_id", "revision_id",
                        "approved_at", "published_at")} for a in arts],
    }
    if arts or adir(w).is_dir():
        atomic_write_json(adir(w, create=True) / INDEX, idx)
    return idx


def repair_pointers(workdir):
    """משחזר pointers.json מהחותמות שבתוך ה-artifacts (אם הקובץ אבד/נפגם)."""
    w = Path(workdir)
    arts = list_artifacts(w)
    if not arts:
        return pointers(w)
    p = pointers(w)
    by_id = {a["artifact_id"] for a in arts}
    changed = False
    if p.get("latest_candidate") not in by_id:
        p["latest_candidate"] = arts[-1]["artifact_id"]
        changed = True
    for kind, field in (("approved_final", "approved_at"),
                        ("published_final", "published_at")):
        if p.get(kind) in by_id:
            continue
        stamped = [a for a in arts if a.get(field)]
        if stamped:
            stamped.sort(key=lambda a: a[field])
            p[kind] = stamped[-1]["artifact_id"]
            changed = True
    if changed:
        p.setdefault("log", []).append({"ts": now_ts(), "kind": "repair",
                                        "actor": "system"})
        _save_pointers(w, p)
    return p


def summary_row(workdir):
    """שורה קומפקטית לרשימת הפרויקטים באפליקציה."""
    arts = list_artifacts(workdir)
    if not arts:
        return {"count": 0, "display": None}
    dt = display_target(workdir)
    return {"count": len(arts), "display": dt}
