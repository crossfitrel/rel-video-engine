#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tasks — הערות מובנות בטיימקוד + תור המשימות לקלאוד (Claude Bridge backend).
==========================================================================
הערה (comment) היא הרשומה היחידה; "משימה לקלאוד" = הערה שסטטוסה
queued_for_claude. הכל נשמר ב-comments.json פר-פרויקט, append-only ברוחו:
הערות לא נדרסות — רק שדות סטטוס/resolution מתעדכנים, וכל שינוי נרשם
ל-corrections.jsonl (ללמידה).

סטטוסים: open → queued_for_claude → in_progress → resolved / rejected
stale: אם ה-EDL השתנה מאז יצירת ההערה — ההערה מסומנת stale ולא מוחלת
אוטומטית (Claude חייב לאשר ידנית שהיא עדיין רלוונטית).
"""
from pathlib import Path

from . import (append_jsonl, atomic_write_json, new_id, now_ts, read_json,
               sha256_json)
from . import revisions as rev_mod

CATEGORIES = ("edit", "transcript", "hook", "pacing", "audio", "captions",
              "broll", "cover", "qa", "general")
PRIORITIES = ("low", "normal", "high", "blocking")
STATUSES = ("open", "queued_for_claude", "in_progress", "resolved", "rejected")


def _path(workdir):
    return Path(workdir) / "comments.json"


def list_comments(workdir):
    return read_json(_path(workdir), []) or []


def _save(workdir, comments):
    atomic_write_json(_path(workdir), comments)


def _log(workdir, event):
    append_jsonl(Path(workdir) / "corrections.jsonl", dict(event, ts=now_ts()))


def add_comment(workdir, text, time_start=None, time_end=None, category="general",
                priority="normal", actor="harel", frame=None, queue=False,
                on_final=False, artifact_id=None):
    """on_final=True — ההערה נכתבה תוך כדי צפייה בגרסת וידאו מוגמרת (טיימקוד
    בציר הגימור, לא בציר ה-INPUT).

    v9.4 — הערה על וידאו נקשרת ל**גרסה מסוימת** ולא ל"FINAL.mp4" הכללי:
    נשמרים `artifact_id` + `artifact_hash` + `artifact_version`. שורש: FINAL.mp4
    מתחלף בכל ריצה, ולכן הערה ישנה שנכתבה על 00:14 הצביעה, אחרי ריצה נוספת,
    לנקודה אחרת לגמרי בסרטון אחר. עכשיו לחיצה על ההערה פותחת בדיוק את הווידאו
    שעליו היא נכתבה. הערות ישנות (רק `on_final`) נשארות תקפות — ראה
    `comment_artifact` שמטפל בהן בנפרד."""
    if category not in CATEGORIES:
        category = "general"
    if priority not in PRIORITIES:
        priority = "normal"
    w = Path(workdir)
    edl = read_json(w / "edl.json", {}) or {}
    art = None
    if on_final or artifact_id:
        try:
            from . import artifacts as art_mod
            aid = artifact_id or (art_mod.display_target(w) or {}).get("artifact_id") \
                or art_mod.artifact_of_live_final(w)
            art = art_mod.get_artifact(w, aid) if aid else None
        except Exception:
            art = None
    c = {
        "comment_id": new_id("c"),
        "revision_id": rev_mod.head(w),
        "edl_hash": sha256_json(edl) if edl else None,
        "time_start": time_start, "time_end": time_end, "frame": frame,
        "category": category, "priority": priority,
        "text": text, "actor": actor, "created_at": now_ts(),
        "status": "queued_for_claude" if queue else "open",
        "resolution": None, "resolved_revision_id": None, "stale": False,
        "on_final": bool(on_final or artifact_id),
        "artifact_id": (art or {}).get("artifact_id"),
        "artifact_hash": (art or {}).get("checksum"),
        "artifact_version": (art or {}).get("version"),
    }
    comments = list_comments(w)
    comments.append(c)
    _save(w, comments)
    _log(w, {"type": "comment_added", "comment_id": c["comment_id"],
             "category": category, "priority": priority,
             "time_start": time_start, "chars": len(text)})
    return c


def get_comment(workdir, cid):
    for c in list_comments(workdir):
        if c["comment_id"] == cid:
            return c
    return None


def update_comment(workdir, cid, **fields):
    comments = list_comments(workdir)
    for c in comments:
        if c["comment_id"] == cid:
            allowed = {"status", "priority", "category", "resolution",
                       "resolved_revision_id", "claimed_by", "claimed_at",
                       "stale", "text", "time_start", "time_end"}
            for k, v in fields.items():
                if k in allowed:
                    c[k] = v
            c["updated_at"] = now_ts()
            _save(workdir, comments)
            _log(workdir, {"type": "comment_updated", "comment_id": cid,
                           "fields": {k: v for k, v in fields.items()
                                      if k in allowed and k != "text"}})
            return c
    return None


def comment_artifact(workdir, comment):
    """איזו גרסת וידאו צריך לפתוח כשלוחצים על ההערה הזו.

    שלוש דרגות, מהוודאי לפחות ודאי:
      1. `artifact_id` שנשמר בהערה (v9.4 והלאה) — הגרסה המדויקת. אם הקובץ
         חסר/לא תואם checksum, זו **תקלה** ולא נפילה שקטה ל-FINAL הנוכחי.
      2. הערה ישנה עם `on_final` בלבד: מנסים לזהות לפי הגרסה שהייתה קיימת
         בזמן כתיבת ההערה (created_at) — הגרסה האחרונה שנוצרה לפניה.
      3. אין מידע ⇒ None, והאפליקציה מציגה "ציר לא ידוע" במקום לנחש.
    """
    w = Path(workdir)
    try:
        from . import artifacts as art_mod
    except Exception:
        return None
    if comment.get("artifact_id"):
        rec = art_mod.get_artifact(w, comment["artifact_id"])
        if not rec:
            return {"artifact_id": comment["artifact_id"], "resolved": False,
                    "fault": "missing_record",
                    "detail": "הגרסה שעליה נכתבה ההערה אינה רשומה יותר"}
        v = art_mod.verify(w, comment["artifact_id"])
        if comment.get("artifact_hash") and comment["artifact_hash"] != rec.get("checksum"):
            v = {"ok": False, "state": "checksum_mismatch",
                 "detail": "תוכן הגרסה השתנה מאז שנכתבה ההערה"}
        return {"artifact_id": rec["artifact_id"], "version": rec.get("version"),
                "resolved": v["ok"], "source": "exact",
                "fault": None if v["ok"] else v["state"], "detail": v["detail"]}
    if not comment.get("on_final"):
        return None
    arts = [a for a in art_mod.list_artifacts(w)
            if (a.get("created_at") or "") <= (comment.get("created_at") or "")]
    if arts:
        a = arts[-1]
        return {"artifact_id": a["artifact_id"], "version": a.get("version"),
                "resolved": True, "source": "inferred_by_time",
                "fault": None,
                "detail": "הערה ישנה — הגרסה זוהתה לפי זמן הכתיבה"}
    return {"artifact_id": None, "resolved": False, "source": "legacy",
            "fault": "unknown_axis",
            "detail": "הערה ישנה על FINAL שלא נשמר כגרסה — הציר אינו ידוע"}


def check_stale(workdir, comment):
    """ההערה נכתבה על גרסה מסוימת; אם ה-EDL השתנה מאז — היא stale."""
    edl = read_json(Path(workdir) / "edl.json", {}) or {}
    cur = sha256_json(edl) if edl else None
    return bool(comment.get("edl_hash")) and comment["edl_hash"] != cur


def task_context(workdir, comment):
    """הקשר מלא למשימת Claude: snippet תמליל סביב הטיימקוד + קבצים + מצב."""
    w = Path(workdir)
    words = read_json(w / "whisper_raw.json", []) or []
    snippet = ""
    ts = comment.get("time_start")
    if ts is not None and words:
        lo, hi = float(ts) - 6.0, float(comment.get("time_end") or ts) + 6.0
        snippet = " ".join(x["word"] for x in words
                           if lo <= float(x.get("start", 0)) <= hi)
    edl = read_json(w / "edl.json", {}) or {}
    relevant = [f for f in ("edl.json", "edited.txt", "correct_transcript.txt",
                            "whisper_raw.json", "gate_fail.json", "qa_report.json",
                            "finish_status.json", "INPUT.mp4", "PREVIEW.mp4",
                            "EXPORT_TIGHT.mp4", "FINAL.mp4") if (w / f).exists()]
    expected = {
        "edit": "עדכון cuts ב-edl.json דרך האפליקציה/CLI + revision חדש + recut preview",
        "transcript": "תיקון edited.txt + revision חדש",
        "hook": "hook_move ב-edl.review + revision חדש",
        "audio": "בדיקת מיקס/loudness, תיקון והרצת גימור מחדש",
        "captions": "תיקון טקסט/תזמון כתוביות + צריבה מחדש",
        "broll": "עדכון broll plan והרצת overlay מחדש",
        "cover": "יצירת קאבר מחדש (thumbnail tools)",
        "qa": "אבחון כשל QA לפי qa_report.json ותיקון",
        "pacing": "בחינת צפיפות חיתוכים/קצב ותיקון EDL",
        "general": "לפי נוסח ההערה",
    }.get(comment.get("category", "general"))
    return {
        "task_id": comment["comment_id"],
        "project": w.name,
        "project_path": str(w),
        "current_revision": rev_mod.head(w),
        "task_revision": comment.get("revision_id"),
        "current_edl_hash": sha256_json(edl) if edl else None,
        "task_edl_hash": comment.get("edl_hash"),
        "stale": check_stale(w, comment),
        "time_range": [comment.get("time_start"), comment.get("time_end")],
        "on_final": bool(comment.get("on_final")),
        "artifact": comment_artifact(w, comment),   # v9.4 — על איזו גרסה נכתבה
        "transcript_snippet": snippet,
        "instruction": comment.get("text"),
        "category": comment.get("category"),
        "priority": comment.get("priority"),
        "status": comment.get("status"),
        "created_at": comment.get("created_at"),
        "resolution": comment.get("resolution"),
        "relevant_files": relevant,
        "expected_action": expected,
        "kept_dur": edl.get("kept_dur"),
    }


def claim(workdir, cid, actor="claude", force=False):
    c = get_comment(workdir, cid)
    if not c:
        return {"ok": False, "error": f"משימה לא נמצאה: {cid}"}
    if c["status"] not in ("open", "queued_for_claude"):
        return {"ok": False, "error": f"סטטוס לא ניתן ל-claim: {c['status']}"}
    if check_stale(workdir, c) and not force:
        update_comment(workdir, cid, stale=True)
        return {"ok": False, "stale": True,
                "error": "stale task — ה-EDL השתנה מאז יצירת ההערה. "
                         "בדוק רלוונטיות והפעל שוב עם --force"}
    update_comment(workdir, cid, status="in_progress", claimed_by=actor,
                   claimed_at=now_ts())
    return {"ok": True, "task": task_context(workdir, get_comment(workdir, cid))}


def resolve(workdir, cid, revision_id, summary, actor="claude"):
    c = get_comment(workdir, cid)
    if not c:
        return {"ok": False, "error": f"משימה לא נמצאה: {cid}"}
    if not revision_id or not rev_mod.get_revision(workdir, revision_id):
        return {"ok": False,
                "error": "resolve מחייב revision קיים שנוצר עם התיקון "
                         "(אין סימון resolved לפני שהשינוי נכתב)"}
    update_comment(workdir, cid, status="resolved", resolution=summary,
                   resolved_revision_id=revision_id)
    _log(workdir, {"type": "task_resolved", "comment_id": cid,
                   "revision_id": revision_id, "summary": summary, "actor": actor})
    return {"ok": True, "comment_id": cid, "revision_id": revision_id}


def fail(workdir, cid, reason, actor="claude"):
    c = get_comment(workdir, cid)
    if not c:
        return {"ok": False, "error": f"משימה לא נמצאה: {cid}"}
    update_comment(workdir, cid, status="queued_for_claude", claimed_by=None)
    _log(workdir, {"type": "task_failed", "comment_id": cid, "reason": reason,
                   "actor": actor})
    return {"ok": True, "comment_id": cid, "requeued": True, "reason": reason}
