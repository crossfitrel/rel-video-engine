#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
registry — Project Registry v7: מזהה יציב לכל פרויקט + אינדקס SQLite נבנה-מחדש.
==============================================================================
עקרונות:
  * מקור האמת = project_manifest.json בתוך כל תיקיית פרויקט (+ הקבצים עצמם).
  * SQLite (_work/.index/registry.db) הוא אינדקס בלבד — מחיקתו אינה מאבדת מידע,
    `rebuild()` בונה אותו מחדש מהדיסק.
  * שם תיקייה אינו המזהה: project_id (UUID) נשמר במניפסט ושורד רינון.
"""
import json
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path

from . import (INDEX_DIR, WORK, atomic_write_json, now_ts, read_json,
               sha256_file, policy_version)

DB_PATH = INDEX_DIR / "registry.db"
MANIFEST = "project_manifest.json"


def ffprobe_media(path):
    """מדדי מדיה בסיסיים (media health בסיסי): רזולוציה, fps, משך, אודיו, צבע."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(p)],
            capture_output=True, text=True, timeout=60)
        j = json.loads(r.stdout)
    except Exception:
        return None
    out = {"duration": None, "width": None, "height": None, "fps": None,
           "has_audio": False, "color_transfer": None, "rotation": 0,
           "size_bytes": p.stat().st_size}
    try:
        out["duration"] = round(float(j["format"]["duration"]), 2)
    except Exception:
        pass
    for s in j.get("streams", []):
        if s.get("codec_type") == "video" and out["width"] is None:
            out["width"], out["height"] = s.get("width"), s.get("height")
            fr = s.get("avg_frame_rate") or "0/1"
            try:
                num, den = fr.split("/")
                out["fps"] = round(int(num) / int(den), 2) if int(den) else None
            except Exception:
                pass
            out["color_transfer"] = s.get("color_transfer")
            sd = (s.get("side_data_list") or [{}])[0]
            out["rotation"] = sd.get("rotation", 0)
        if s.get("codec_type") == "audio":
            out["has_audio"] = True
    return out


def ensure_manifest(workdir, probe=False):
    """טוען/יוצר project_manifest.json. probe=True מרענן מדדי ffprobe+checksums."""
    w = Path(workdir)
    mpath = w / MANIFEST
    m = read_json(mpath, {}) or {}
    changed = False
    if not m.get("project_id"):
        m["project_id"] = "prj_" + uuid.uuid4().hex[:12]
        m["created_at"] = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(w.stat().st_mtime))
        changed = True
    if m.get("name") != w.name:
        m["name"] = w.name
        changed = True
    m.setdefault("monday_item_id", None)
    m.setdefault("dept", None)
    m.setdefault("month", None)
    # brand/content_type — מ-APPROVAL.json אם קיים
    appr = read_json(w / "APPROVAL.json")
    if appr:
        for k in ("content_type", "brand"):
            if appr.get(k) and m.get(k) != appr[k]:
                m[k] = appr[k]
                changed = True
    m.setdefault("content_type", None)
    m.setdefault("brand", None)
    if probe or "media" not in m:
        media = {}
        for key, fname in (("input", "INPUT.mp4"), ("final", "FINAL.mp4"),
                           ("export", "EXPORT.mp4"), ("preview", "PREVIEW.mp4")):
            f = w / fname
            if f.exists():
                media[key] = {"file": fname, "probe": ffprobe_media(f),
                              "checksum": sha256_file(f)}
        m["media"] = media
        changed = True
    if changed:
        m["updated_at"] = now_ts()
        atomic_write_json(mpath, m)
    return m


def derive_state(workdir):
    """מצב תפעולי מקומי (נגזר מקבצים — לא מערכת סטטוסים מתחרה ל-Monday).
    v7.1 (הראל 23.7): (1) state_override במניפסט גובר על הכל — שליטה ידנית;
    (2) הערות פתוחות/בתור-קלאוד מורידות פרויקט מ-final/approved חזרה ל-in_review —
    FINAL עם הערות חדשות הוא כנראה לא באמת final.
    v7.2 (הראל 23.7 ערב): שלב אישור קאבר+קפשן בין final לתזמון — ולא לסמוך על
    "אושר" בעבר בלבד: אם FINAL.mp4 בפועל השתנה מאז האישור, האישור בטל אוטומטית
    וחוזרים ל-awaiting_schedule_approval (שורש: למנוע תזמון גרסה ישנה/שגויה אם
    FINAL נבנה מחדש אחרי אישור הקאבר+קפשן).
    **קריטי:** ההשוואה היא מול `os.stat` חי על FINAL.mp4 בפועל (mtime+size) —
    לא מול checksum שנשמר במניפסט, כי אין ערובה שהוא רוענן מאז שהקובץ השתנה
    (ensure_manifest(probe=True) לא רץ אוטומטית על כל שינוי קובץ). checksum
    ב-schedule_approval משמש רק לתיעוד/לדיווח האימות (קריאה חוזרת ב-getScheduledPosts),
    לא לגזירת state.
    v9.33 (23.9.26): `scheduled` ("📅 תוזמן — ממתין לפרסום") ו-`published` ("🚀 פורסם
    בפועל") מגיעים **רק** מ-state_override (סימון אחרי תזמון מאומת / אחרי שהפוסט חי) —
    שניהם בתוך SCHEDULE_CLOSED_STATES ולכן יוצאים מתור "מוכן לתזמון" (לקח L97)."""
    from . import tasks as tasks_mod   # import מקומי — מניעת מעגליות
    w = Path(workdir)
    m = read_json(w / MANIFEST, {}) or {}
    if m.get("state_override"):
        return m["state_override"]
    fs = read_json(w / "finish_status.json", {}) or {}
    corr = w / "corrections.jsonl"
    n_corr = sum(1 for _ in open(corr, encoding="utf-8")) if corr.exists() else 0
    lock = (w / ".finish.lock").exists()
    if lock or fs.get("state") == "running":
        return "running"
    if fs.get("state") == "failed":
        return "failed"
    open_comments = [c for c in tasks_mod.list_comments(w)
                     if c.get("status") in ("open", "queued_for_claude", "in_progress")]
    if open_comments:
        return "in_review"
    final_path = w / "FINAL.mp4"
    # v9.4 — קיום גרסה נמדד קודם כל ב-Artifact Store ורק אחר כך בקובץ FINAL.mp4.
    has_artifact = False
    try:
        from . import artifacts as art_mod
        has_artifact = bool(art_mod.list_artifacts(w))
    except Exception:
        art_mod = None
    if final_path.exists() or has_artifact:
        sched = m.get("schedule_approval") or {}
        if sched:
            if sched.get("status") == "approved":
                aid = sched.get("artifact_id")
                if aid and art_mod:
                    # הנעילה היא על **הגרסה** — לא על הנתיב. ריצה חדשה יוצרת
                    # מועמד ואינה מבטלת את האישור; רק פגיעה בגרסה עצמה מבטלת.
                    v = art_mod.verify(w, aid)
                    return "ready_to_schedule" if v["ok"] else "awaiting_schedule_approval"
                if final_path.exists():
                    st = final_path.stat()          # מסלול ישן (אין artifact)
                    if sched.get("approved_final_live_sig") == [round(st.st_mtime, 3), st.st_size]:
                        return "ready_to_schedule"
            return "awaiting_schedule_approval"
        return "final"
    if (w / "APPROVAL.json").exists():
        return "approved"
    if n_corr > 0 or (w / "review_rounds.json").exists():
        return "in_review"
    return "not_started"


# v9.33 (23.9.26) — הראל 24.7.26: "הושלם באפליקציה זה לא פורסם בפועל אלא תוזמן".
# scheduled = תוזמן ב-Metricool ואומת בקריאה חוזרת, עוד לא חי; published = חי בפועל
# (ידני, או getScheduledPosts מראה providers[].status=PUBLISHED). סדר המצבים:
# … ready_to_schedule → scheduled → published. שני האחרונים סוגרים את התזמון —
# כל תור "מוכן לתזמון" חייב להוציא את שניהם (לקח 23.8.26: 12 פרויקטים שתוזמנו
# נשארו ב-ready_to_schedule ⇒ סכנת תזמון כפול).
SCHEDULE_CLOSED_STATES = ("scheduled", "published")
STATE_OVERRIDES = (None, "not_started", "in_review", "approved", "running",
                   "failed", "final", "awaiting_schedule_approval",
                   "ready_to_schedule", "scheduled", "published")


def set_meta(workdir, state_override=..., dept=...):
    """עדכון ידני של מצב/מחלקה במניפסט. העברת None מנקה; אי-העברה לא נוגעת."""
    w = Path(workdir)
    m = ensure_manifest(w)
    if state_override is not ...:
        allowed = STATE_OVERRIDES
        if state_override not in allowed:
            raise ValueError(f"מצב לא חוקי: {state_override}")
        m["state_override"] = state_override
    if dept is not ...:
        m["dept"] = dept or None
    m["updated_at"] = now_ts()
    atomic_write_json(w / MANIFEST, m)
    return m


VISUAL_HOOK_PREF_KEYS = {"mode", "enabled", "selected_candidate_id", "strength",
                         "plan_digest", "approved_plan_digest", "comparison_seen"}


def validate_visual_hook_prefs(vh):
    """דחייה מפורשת של מפתח/ערך לא מוכר — העדפה שאינה נקראת היא העדפה שנעלמת."""
    import re as _re
    if not isinstance(vh, dict):
        raise ValueError("visual_hook חייב להיות אובייקט")
    extra = set(vh) - VISUAL_HOOK_PREF_KEYS
    if extra:
        raise ValueError(f"visual_hook: מפתחות לא מוכרים {sorted(extra)}")
    out = {}
    if "mode" in vh:
        if vh["mode"] not in (None, "off", "shadow", "auto"):
            raise ValueError("visual_hook.mode: off/shadow/auto")
        out["mode"] = vh["mode"]
    if "enabled" in vh:
        if vh["enabled"] not in (None, True, False):
            raise ValueError("visual_hook.enabled: true/false")
        out["enabled"] = vh["enabled"]
    if "strength" in vh:
        if vh["strength"] not in (None, "subtle"):
            raise ValueError("visual_hook.strength: רק subtle עד שמעטפת רגילה תאושר")
        out["strength"] = vh["strength"]
    if "comparison_seen" in vh:
        if vh["comparison_seen"] not in (None, True, False):
            raise ValueError("visual_hook.comparison_seen: true/false")
        out["comparison_seen"] = vh["comparison_seen"]
    if "selected_candidate_id" in vh:
        v = vh["selected_candidate_id"]
        if v is not None and not (isinstance(v, str) and _re.fullmatch(r"cand_[0-9a-f]{12}", v)):
            raise ValueError("visual_hook.selected_candidate_id לא חוקי")
        out["selected_candidate_id"] = v
    for k in ("plan_digest", "approved_plan_digest"):
        if k in vh:
            v = vh[k]
            if v is not None and not (isinstance(v, str) and _re.fullmatch(r"sha256:[0-9a-f]{64}", v)):
                raise ValueError(f"visual_hook.{k} לא חוקי")
            out[k] = v
    return out


def set_finish_prefs(workdir, prefs):
    """v7.4 — העדפות גימור ידניות מהאפליקציה (בקשת הראל 24.7: שליטה ידנית במוזיקה,
    בכתוביות ובבירולים בלי תלות בקלאוד). merge לפי מפתח עליון (music / broll);
    ערכי None בתוך קבוצה מוחקים את המפתח (track=None ⇒ חזרה לבחירה אוטומטית).
    ההעדפות נקראות ע"י local_finish_pipeline.py וגוברות על דגלי ה-CLI."""
    w = Path(workdir)
    m = ensure_manifest(w)
    fp = dict(m.get("finish_prefs") or {})
    if "visual_hook" in prefs:
        # v9.23 — קבוצה מאומתת. בלי ההרחבה הזאת בחירה באפליקציה הייתה נעלמת בשקט
        # (ה-whitelist היה music/broll בלבד). חסר = off לפרויקטים ישנים.
        vh = prefs["visual_hook"]
        if vh is None:
            fp.pop("visual_hook", None)
        else:
            cur = dict(fp.get("visual_hook") or {})
            cur.update(validate_visual_hook_prefs(vh))
            fp["visual_hook"] = {kk: vv for kk, vv in cur.items() if vv is not None}
    for k in ("music", "broll"):
        if k not in prefs:
            continue
        if prefs[k] is None:
            fp.pop(k, None)
            continue
        cur = dict(fp.get(k) or {})
        cur.update(prefs[k])
        fp[k] = {kk: vv for kk, vv in cur.items() if vv is not None}
    m["finish_prefs"] = fp
    m["updated_at"] = now_ts()
    atomic_write_json(w / MANIFEST, m)
    return m


def _caption_gate(w, caption, caption_type=None, brand=None):
    """v9.48 — מריץ את tools/caption_gate.py על טיוטת קפשן מול מה שנשמע בסרטון.
    מחזיר None אם הכלי לא נטען (גלאי שנעלם מדווח ב-lesson_registry, לא כאן)."""
    try:
        import importlib.util
        p = Path(__file__).resolve().parent.parent / "caption_gate.py"
        spec = importlib.util.spec_from_file_location("caption_gate", p)
        cg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cg)
    except Exception:
        return None
    m = ensure_manifest(w)
    ct_map = {"value": "ערך", "conversion": "המרה", "connection": "קהילה",
              "community": "קהילה", "testimonial": "עדות"}
    ctype = caption_type or ct_map.get(m.get("content_type"), m.get("content_type")) or "ערך"
    if ctype not in ("ערך", "המרה", "קהילה", "עדות"):
        ctype = "ערך"
    br = brand or ("harel" if (m.get("brand") == "personal" or "הראל" in str(m.get("dept") or ""))
                   else "club")
    return cg.gate(caption, ctype, br, cg.heard_text(str(w)))


def set_schedule_approval(workdir, action, cover_path=None, caption_draft=None,
                          caption_text=None, note=None, artifact_id=None,
                          caption_type=None, brand=None, caption_meta=None):
    """v7.2 — שלב אישור קאבר+קפשן בין 'final' לתזמון (בקשת הראל 23.7, שורש:
    למנוע תזמון בטעות של גרסה לא-סופית/ישנה).
    action:
      set_draft        — קלאוד כותב טיוטת קפשן + קאבר לבדיקת הראל (סטטוס→pending).
      approve          — הראל מאשר: נועל את FINAL.mp4 הנוכחי כ"מה שמותר לתזמן" —
                         גם live_sig (mtime+size, מה ש-derive_state בודק בזמן אמת
                         בכל קריאה) וגם checksum sha256 מלא (לתיעוד/לדיווח האימות —
                         קריאה חוזרת ב-getScheduledPosts).
      request_changes  — הראל מבקש שינוי (יוצר גם comment בתור קלאוד, בשרת).
    """
    w = Path(workdir)
    m = ensure_manifest(w)
    sched = m.get("schedule_approval") or {}
    if action == "set_draft":
        if cover_path is not None:
            sched["cover_path"] = cover_path
        if caption_draft is not None:
            # v9.48 — שער הקפשן (הראל 10.10.26: "הקפשן תמיד חוזר על מה שנאמר בתסריט").
            # טיוטה של קלאוד שנכשלת בקאנון או משכפלת את הסרטון לא נכנסת לאפליקציה.
            # האישור/עריכה של הראל עצמו (approve) לא עובר בשער — הוא המילה האחרונה.
            gate_res = _caption_gate(w, caption_draft, caption_type, brand)
            if gate_res and gate_res.get("status") == "FAIL":
                raise ValueError("CAPTION-GATE FAIL — " + " | ".join(gate_res["issues"]))
            sched["caption_draft"] = caption_draft
            if gate_res:
                sched["caption_gate"] = {k: gate_res[k] for k in ("status", "warns")}
                sched["caption_gate"]["echo"] = gate_res["novelty"]["echo_total"]
            if caption_meta:
                sched["caption_meta"] = caption_meta   # מהלך ההוספה + אלמנט StoryBrand — לרוטציה ולרטרו
        if sched.get("status") in (None, "changes_requested"):
            sched["status"] = "pending"
    elif action == "approve":
        final_path = w / "FINAL.mp4"
        if not final_path.exists():
            raise ValueError("אין FINAL.mp4 — אי אפשר לאשר קאבר/קפשן לפני שהגימור הושלם")
        st = final_path.stat()
        # v9.4 — האישור ננעל ל-**artifact_id** ולא לנתיב `FINAL.mp4`. שורש:
        # הנתיב מתחלף בכל ריצה, ולכן "אישרתי את הקובץ הזה" לא היה טענה יציבה.
        # מכאן: התזמון חייב לקחת את הקובץ מתוך ה-artifact הנעול (נתיב קבוע),
        # ולא מהנתיב הכללי. גם approve על גרסה = סימון approved_final.
        try:
            from . import artifacts as art_mod
            aid = (artifact_id or art_mod.artifact_of_live_final(w)
                   or (art_mod.create_artifact(
                       w, final_path, actor="schedule_approval",
                       summary="נלכד באישור קאבר+קפשן") or {}).get("artifact_id"))
            if aid:
                art_mod.approve(w, aid, actor="harel")
                rec = art_mod.get_artifact(w, aid) or {}
                sched["artifact_id"] = aid
                sched["artifact_version"] = rec.get("version")
                sched["artifact_checksum"] = rec.get("checksum")
                sched["artifact_path"] = rec.get("path")
        except Exception as e:
            sched["artifact_error"] = str(e)
        sched["status"] = "approved"
        sched["cover_path"] = cover_path or sched.get("cover_path") or "thumbnail.png"
        sched["caption_approved"] = (caption_text or sched.get("caption_draft") or "").strip()
        # live_sig הוא מה ש-derive_state משווה אליו בכל קריאה (זול: stat בלבד,
        # לא תלוי ברענון ידני של המניפסט) — checksum sha256 מלא לתיעוד/לדיווח
        # האימות (קריאה חוזרת ב-getScheduledPosts).
        sched["approved_final_live_sig"] = [round(st.st_mtime, 3), st.st_size]
        sched["approved_final_checksum"] = sha256_file(final_path)
        sched["approved_final_path"] = str(final_path.resolve())
        sched["approved_at"] = now_ts()
    elif action == "request_changes":
        sched["status"] = "changes_requested"
        sched["note"] = note
    else:
        raise ValueError(f"פעולה לא מוכרת: {action}")
    m["schedule_approval"] = sched
    m["updated_at"] = now_ts()
    atomic_write_json(w / MANIFEST, m)
    return m


def blocker_of(workdir):
    w = Path(workdir)
    fs = read_json(w / "finish_status.json", {}) or {}
    if fs.get("state") == "failed":
        if (w / "gate_fail.json").exists():
            return "gate שקט נכשל — תיקון באפליקציית הרוויו"
        return fs.get("detail") or "הגימור נכשל"
    return None


def project_row(workdir):
    """שורת רישום מלאה לפרויקט — למסך הסרטונים ול-CLI."""
    from . import tasks as tasks_mod   # מניעת import מעגלי
    from . import revisions as rev_mod
    w = Path(workdir)
    m = ensure_manifest(w)
    edl = read_json(w / "edl.json", {}) or {}
    fs = read_json(w / "finish_status.json", {}) or {}
    qa = read_json(w / "qa_report.json")
    qa_state = None
    if qa is not None:
        if qa.get("pass"):
            warns = any(g.get("warn") for g in qa.get("gates", []) if isinstance(g, dict))
            qa_state = "PASS_WITH_WARNINGS" if warns else "PASS"
        else:
            qa_state = "FAIL"
    comments = tasks_mod.list_comments(w)
    open_comments = [c for c in comments if c["status"] in ("open", "queued_for_claude", "in_progress")]
    queued = [c for c in comments if c["status"] == "queued_for_claude"]
    return {
        "project_id": m["project_id"],
        "name": w.name,
        "path": str(w),
        "monday_item_id": m.get("monday_item_id"),
        "dept": m.get("dept"),
        "brand": m.get("brand"),
        "content_type": m.get("content_type"),
        "month": m.get("month"),
        "created_at": m.get("created_at"),
        # ‏23.8.26 — היה `.get("probe", {})`: ברירת המחדל חלה רק כשהמפתח **חסר**.
        # מניפסט עם `probe: null` מפורש (ההבנה-האנטומית-סוגי-קרעים) החזיר None
        # והפיל את `projects` כולו ב-AttributeError. `or {}` מטפל גם בערך null.
        "input_dur": (((m.get("media") or {}).get("input") or {}).get("probe") or {}).get("duration") if (m.get("media") or {}).get("input") else None,
        "total_dur": edl.get("total_dur"),
        "kept_dur": edl.get("kept_dur"),
        "final_exists": (w / "FINAL.mp4").exists(),
        "state": derive_state(w),
        "pipeline_step": fs.get("step") or (fs.get("steps_done") or [{}])[-1].get("step") if fs else None,
        "open_comments": len(open_comments),
        "queued_for_claude": len(queued),
        "qa_state": qa_state,
        "active_revision": rev_mod.head(w),
        "policy_version": policy_version(),
        "blocker": blocker_of(w),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(w.stat().st_mtime)),
        "checksums": {k: (v or {}).get("checksum") for k, v in (m.get("media") or {}).items()},
        "schedule_approval": m.get("schedule_approval"),
        "artifacts": _artifacts_summary(w),         # v9.4
    }


def _artifacts_summary(w):
    try:
        from . import artifacts as art_mod
        return art_mod.summary_row(w)
    except Exception as e:
        return {"count": 0, "display": None, "error": str(e)}


def iter_workdirs():
    if not WORK.exists():
        return
    for d in sorted(WORK.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and (d / "edl.json").exists():
            yield d


def _db():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY, name TEXT, state TEXT, brand TEXT,
        content_type TEXT, qa_state TEXT, open_comments INT, queued INT,
        updated_at TEXT, row_json TEXT)""")
    return con


def rebuild(probe=False):
    """בנייה מחדש מלאה של האינדקס מהדיסק. בטוח להריץ תמיד."""
    con = _db()
    con.execute("DELETE FROM projects")
    n = 0
    for d in iter_workdirs():
        try:
            if probe:
                ensure_manifest(d, probe=True)
            row = project_row(d)
        except Exception as e:
            row = {"project_id": f"err_{d.name}", "name": d.name, "state": "error",
                   "error": str(e)}
        con.execute("INSERT OR REPLACE INTO projects VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (row.get("project_id"), row.get("name"), row.get("state"),
                     row.get("brand"), row.get("content_type"), row.get("qa_state"),
                     row.get("open_comments", 0), row.get("queued_for_claude", 0),
                     row.get("updated_at"), json.dumps(row, ensure_ascii=False)))
        n += 1
    con.commit()
    con.close()
    return n


def list_projects(live=True):
    """live=True קורא ישירות מהדיסק (תמיד עדכני); live=False מהאינדקס."""
    if live:
        return [project_row(d) for d in iter_workdirs()]
    con = _db()
    rows = [json.loads(r[0]) for r in con.execute(
        "SELECT row_json FROM projects ORDER BY updated_at DESC")]
    con.close()
    return rows


def find_project(ident):
    """מאתר פרויקט לפי project_id או שם תיקייה."""
    for d in iter_workdirs():
        m = read_json(d / MANIFEST, {}) or {}
        if m.get("project_id") == ident or d.name == ident:
            return d
    return None
