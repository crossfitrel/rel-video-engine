#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — אפליקציית הרוויו של R.E.L (v7 — Editorial Operating System מקומי)
=============================================================================
הראל רואה את ה-INPUT עם כל חיתוכי ה-EDL מסומנים על הציר, מתקן בקליק
(ביטול/הוספה/כוונון/העברת Hook), מתקן טקסט תמליל, מאשר — והגימור המקומי
רץ אוטומטית תחת נעילה (relvid.runner → run_finish.py). אפס העלאות.

v7:
  * כל שמירה יוצרת revision לא-הרסני (relvid.revisions) + undo/redo/restore.
  * הערות מובנות בטיימקוד (relvid.tasks) + תור "ממתין לקלאוד".
  * אישור idempotent — לחיצה כפולה לא מריצה גימור פעמיים.
  * כל תיקון נרשם ל-corrections.jsonl → לולאת הלמידה (learn_from_edits.py).
"""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path
from flask import Flask, request, jsonify, send_file, Response

APP_DIR = Path(__file__).resolve().parent
SYS_DIR = APP_DIR.parent
TOOLS   = SYS_DIR / "tools"
MUSIC_DIR = SYS_DIR / "brand-assets" / "music"
PORT    = 5112

sys.path.insert(0, str(TOOLS))
from relvid.paths import work_root as _work_root               # noqa: E402  (v8.6, P0-11)
WORK    = _work_root(create=True)
TRASH   = WORK / "_trash"
from relvid import read_json, sha256_json                      # noqa: E402
from relvid import revisions as rev_mod                        # noqa: E402
from relvid import tasks as tasks_mod                          # noqa: E402
from relvid import runner as runner_mod                        # noqa: E402
from relvid import registry as reg                             # noqa: E402
from relvid import sync as sync_mod                            # noqa: E402
from relvid import artifacts as art_mod                        # noqa: E402  (v9.4)
from relvid import changelog as cl_mod                         # noqa: E402  (v9.15)
from relvid import visual_hook as vh_mod                       # noqa: E402  (v9.23)
from relvid.edl_utils import derive_keep                       # noqa: E402

app = Flask(__name__)

def safe(name):
    if not re.fullmatch(r"[\w֐-׿ .\-()+]+", name) or ".." in name:
        raise ValueError("שם פרויקט לא חוקי")
    return name

def wdir(name):
    d = WORK / safe(name)
    if not d.is_dir():
        raise FileNotFoundError(name)
    return d

def atomic_write(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)

def log_correction(d, action):
    action = dict(action); action["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(d / "corrections.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(action, ensure_ascii=False) + "\n")

class Busy(Exception):
    """v8.6 (P0-8) — הפרויקט בגימור, אסור לגעת בציר/בתמליל."""
    def __init__(self, lock): self.lock = lock or {}

def guard_lock(d):
    """שורש: מתוך 22 endpoints שכותבים, רק sync ו-delete בדקו את .finish.lock.
    save / transcript / undo / redo / restore / recut כתבו את edl.json ו-edited.txt
    בלי כל בדיקה — בזמן שהצנרת קוראת בדיוק את הקבצים האלה תוך כדי ריצה. כלומר
    שמירה באמצע גימור שינתה את מקור האמת שממנו נבנה ה-FINAL, בשקט.
    התשובה היא 409 עם פרטי הריצה, כדי שהאפליקציה תוכל להסביר להראל למה."""
    lk = runner_mod.current_lock(d)
    if lk:
        raise Busy(lk)
    return None

def edl_token(d):
    """חתימת מצב הציר — לזיהוי lost-update ב-/api/save (P0-9).
    מורכבת מ-review (מה שהמשתמש עורך) + head ה-revision, ולא מהקובץ כולו,
    כדי שכתיבות לא-מהותיות (kept_dur מחושב מחדש) לא יפסלו שמירה תקינה."""
    edl = read_json(d / "edl.json", {}) or {}
    try:
        head = (read_json(d / "revisions" / "index.json", {}) or {}).get("head")
    except Exception:
        head = None
    return sha256_json({"review": edl.get("review"), "head": head})[:16]

@app.errorhandler(Busy)
def _busy(e):
    return jsonify(error="הפרויקט בגימור כרגע — אין לערוך את הציר עד שהריצה תסתיים "
                         "(או בטל אותה בלשונית ריצות)",
                   code="BUSY_FINISHING", lock=e.lock), 409

@app.errorhandler(FileNotFoundError)
def _nf(e):
    return jsonify(error=f"פרויקט לא נמצא: {e}", code="NOT_FOUND"), 404

@app.errorhandler(ValueError)
def _bad(e):
    return jsonify(error=str(e), code="BAD_REQUEST"), 400

TRASH_RE = re.compile(r"^\d{8}-\d{6}__(.+?)(?:__\d+)?$")

def log_trash(entry):
    TRASH.mkdir(parents=True, exist_ok=True)
    entry = dict(entry); entry["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(TRASH / "trash_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# ---------- סבבי בדיקה (legacy v6 — נשמר לתאימות; המערכת החדשה: comments) ----------
def load_rounds(d):
    p = d / "review_rounds.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    notes_p = d / "notes.txt"
    if notes_p.exists():
        txt = notes_p.read_text(encoding="utf-8").strip()
        if txt:
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(notes_p.stat().st_mtime))
            return [{"round": 1, "note": txt, "note_at": mtime, "corrected_at": None, "summary": None}]
    return []

def save_rounds(d, rounds):
    atomic_write(d / "review_rounds.json", json.dumps(rounds, ensure_ascii=False, indent=1))

def compute_round_status(rounds):
    if not rounds:
        return None
    last = rounds[-1]; n = len(rounds)
    if last.get("corrected_at") is None:
        return {"text": f"📝 הערה #{n} ממתינה לתיקון", "kind": "pending_fix"}
    return {"text": f"✅ תוקן (סבב {n}) — ממתין למעבר נוסף שלך", "kind": "pending_review"}

@app.before_request
def _auth():
    # בוטל לבקשת הראל 19.7 — שרת מקומי 127.0.0.1 בלבד
    return

@app.get("/")
def index():
    return send_file(str(APP_DIR / "index.html"))

@app.get("/health")
def health():
    return jsonify(ok=True, version="v7")

PLANNED_DATES_FILE = APP_DIR / "planned_dates.json"

def load_planned_dates():
    """v9.27 (20.9.26, בקשת הראל): {שם-פרויקט: 'YYYY-MM-DD'} — תאריך הפרסום
    המתוכנן מבורד הסושיאל/EDITPLAN, כדי שהרשימה תיסדר לפי דחיפות אמיתית
    ולא לפי מתי נגעו בקובץ לאחרונה. חסר/ריק = לא ידוע, לא חוסם כלום."""
    return read_json(PLANNED_DATES_FILE, {}) or {}

CAROUSELS_FILE = APP_DIR / "carousels_queue.json"
# v9.28: תוזמן!/פורסם/פוצץ = מאנדיי כבר סגר את הפריט — לא שורת פעולה יותר.
CAROUSEL_CLOSED_STATUSES = {"תוזמן!", "פורסם", "פוצץ"}

def load_carousels_queue():
    """v9.28 (21.9.26, בקשת הראל): קרוסלות בשלב עריכה/תכנון (ממאנדיי) — כדי
    ש\"מה עכשיו\" יראה אותן לצד הסרטונים, במקום שיישארו רק בצ'אט/מאנדיי.
    לא נוגע ב-_work/EDL/derive_state — קובץ נפרד, שורות \"וירטואליות\" בלבד.
    כל שורה: name, action, owner, detail, planned_date, monday_url, monday_status, checked_at.
    קובץ חסר/ריק = אין קרוסלות פתוחות, לא חוסם כלום.

    v9.34 (24.9.26, בקשת הראל): הראל דיווח ששורות קרוסלה נשארות "לעריכה"
    באפליקציה גם אחרי שהוא כבר תזמן אותן במאנדיי בפועל — כי הקובץ הזה
    נכתב ידנית ע"י קלאוד פעם אחת ואף אחד לא רענן אותו. תיקון-שורש חלקי:
    כל שורה נושאת עכשיו monday_status (הסטטוס שנצפה במאנדיי בזמן הכתיבה)
    ו-checked_at (מתי נבדק). שורה שה-monday_status שלה כבר סגור
    (CAROUSEL_CLOSED_STATUSES) לא מוצגת — הגנה אוטומטית למקרה שהקובץ
    יתעדכן בלי שהסטטוס יתעדכן איתו. אבל זה עדיין לא סנכרון חי: אין ל-
    review-app גישת API למאנדיי (שרת מקומי 127.0.0.1 בלבד, בלי טוקן
    שמור) — כל צ'אט קלאוד שנוגע בפרויקט הזה חייב לאמת כל שורה מול
    monday_com MCP ולעדכן/למחוק לפני שסומך על מה שמוצג (ראו PIPELINE.md)."""
    rows = read_json(CAROUSELS_FILE, []) or []
    out = []
    for r in rows:
        if (r.get("monday_status") or "") in CAROUSEL_CLOSED_STATUSES:
            continue
        out.append({"project": r.get("name") or "קרוסלה",
                     "action": r.get("action") or "בעריכה",
                     "owner": r.get("owner") or "harel",
                     "detail": r.get("detail") or "",
                     "planned_date": r.get("planned_date"),
                     "preflight": None,
                     "type": "carousel",
                     "dept": r.get("dept"),   # v9.34 — כדי שסינון מחלקה יעבוד גם על קרוסלות
                     "monday_url": r.get("monday_url"),
                     "monday_status": r.get("monday_status"),
                     "checked_at": r.get("checked_at")})
    return out

@app.get("/api/projects")
def projects():
    out = []
    planned = load_planned_dates()
    for d in sorted(WORK.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir() or not (d / "edl.json").exists() or not (d / "INPUT.mp4").exists():
            continue
        try:
            edl = json.loads((d / "edl.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        corr_p = d / "corrections.jsonl"
        n_corr = sum(1 for _ in open(corr_p, encoding="utf-8")) if corr_p.exists() else 0
        rounds = load_rounds(d)
        round_status = compute_round_status(rounds)
        last_note = next((r["note"] for r in reversed(rounds) if r.get("note")), "")
        approved = (d / "APPROVAL.json").exists()
        has_final = (d / "FINAL.mp4").exists()
        state = reg.derive_state(d)
        comments = tasks_mod.list_comments(d)
        open_comments = [c for c in comments if c["status"] in ("open", "queued_for_claude", "in_progress")]
        queued = [c for c in comments if c["status"] == "queued_for_claude"]
        resolved_waiting = [c for c in comments if c["status"] == "resolved"]
        # v7.1: פילוח "מצב סקירה" — מה עדיין אצלך מול מה כבר עבר אליך/לקלאוד
        truly_open = [c for c in comments if c["status"] == "open"]           # כתבת, עוד לא שלחת
        in_progress = [c for c in comments if c["status"] == "in_progress"]  # קלאוד עובד עליו עכשיו
        qa = read_json(d / "qa_report.json")
        qa_state = None
        if qa is not None:
            qa_state = "PASS" if qa.get("pass") else "FAIL"
        m = read_json(d / "project_manifest.json", {}) or {}
        out.append({"name": d.name, "total": edl.get("total_dur"),
                    "kept": edl.get("kept_dur"),
                    "approved": approved,
                    "has_final": has_final,
                    "has_notes": bool(last_note),
                    "notes_preview": last_note[:90],
                    "corrections": n_corr,
                    "rounds_count": len(rounds),
                    "round_status": round_status,
                    "state": state,
                    "updated_at": d.stat().st_mtime,
                    "planned_date": planned.get(d.name),   # v9.27
                    # v7:
                    "project_id": m.get("project_id"),
                    "dept": m.get("dept"),
                    "state_override": m.get("state_override"),
                    "brand": m.get("brand"),
                    "content_type": m.get("content_type"),
                    "open_comments": len(open_comments),
                    "queued_for_claude": len(queued),
                    "resolved_waiting": len(resolved_waiting),
                    "truly_open": len(truly_open),
                    "in_progress": len(in_progress),
                    "qa_state": qa_state,
                    "blocker": reg.blocker_of(d),
                    "active_revision": rev_mod.head(d),
                    "sync_state": sync_mod.sync_badge(d),   # v7.7
                    "artifacts": art_mod.summary_row(d),    # v9.4
                    "schedule_approval": m.get("schedule_approval")})
    return jsonify(out)

@app.get("/api/project/<name>")
def project(name):
    d = wdir(name)
    # v7.7 (הראל 25.7): ריפוי-עצמי בפתיחת פרויקט — אם נערך מחוץ לאפליקציה (בצ'אט)
    # ו-review.cuts נשאר מאחור, מיישרים את הציר למה שנחתך בפועל *לפני* שמציגים,
    # כדי שהראל לא יערוך ידנית מעל גרסה ישנה. לא נוגעים בזמן שגימור רץ.
    healed = None
    if not runner_mod.current_lock(d):
        r = sync_mod.reconcile_edl(d, actor="system",
                                   summary="סנכרון אוטומטי בפתיחת הפרויקט באפליקציה")
        if r.get("changed"):
            healed = r
            log_correction(d, {"type": "sync_review_from_keeps", "auto": True,
                               "delta": r["drift"]["delta"],
                               "revision_id": r.get("revision_id")})
    edl = json.loads((d / "edl.json").read_text(encoding="utf-8"))
    words = json.loads((d / "whisper_raw.json").read_text(encoding="utf-8")) \
        if (d / "whisper_raw.json").exists() else []
    review = edl.get("review")
    if not review:
        cuts = [dict(c, active=True, source="auto") for c in edl.get("auto_cuts", [])] + \
               [dict(c, active=False, source="suggested") for c in edl.get("manual_review_cuts", [])]
        review = {"cuts": cuts, "hook_move": None, "speed": 1.0}
    review.setdefault("speed", 1.0)
    txt = ""
    for cand in ("edited.txt", "correct_transcript.txt"):
        if (d / cand).exists():
            txt = (d / cand).read_text(encoding="utf-8"); break
    if not txt and words:
        txt = " ".join(w["word"] for w in words)
    intent = (d / "intent_card.md").read_text(encoding="utf-8") if (d / "intent_card.md").exists() else ""
    status = read_json(d / "finish_status.json", {}) or {}
    notes = (d / "notes.txt").read_text(encoding="utf-8") if (d / "notes.txt").exists() else ""
    rounds = load_rounds(d)
    revs = rev_mod.list_revisions(d)
    mani = read_json(d / "project_manifest.json", {}) or {}
    try:                                   # v9.25 — מדיניות אורך לפי סוג תוכן
        import length_policy as _LP
        _lpt = _LP.policy_table()
    except Exception:
        _lpt = None
    return jsonify({"name": name, "total": edl.get("total_dur"), "review": review,
                    "dept": mani.get("dept"),
                    "content_type": mani.get("content_type"),
                    "length_reason": mani.get("length_reason"),
                    "length_policy": _lpt,
                    "state_override": mani.get("state_override"),
                    "state": reg.derive_state(d),
                    "words": words, "transcript": txt, "intent": intent, "notes": notes,
                    "approved": (d / "APPROVAL.json").exists(),
                    "has_preview": (d / "PREVIEW.mp4").exists(),
                    "has_final": (d / "FINAL.mp4").exists(),
                    "finish_status": status,
                    "rounds": rounds,
                    "round_status": compute_round_status(rounds),
                    # v7:
                    "comments": [dict(c, artifact_ref=tasks_mod.comment_artifact(d, c))
                                 for c in tasks_mod.list_comments(d)],
                    "revisions": revs,
                    # v9.4 — גרסאות הווידאו: מה מוצג עכשיו, ומה ממתין
                    "artifacts": art_mod.summary_row(d),
                    "qa_report": read_json(d / "qa_report.json"),
                    "gate_fail": read_json(d / "gate_fail.json"),
                    "cut_qa": read_json(d / "cut_qa_report.json"),
                    "canon": read_json(d / "canon_report.json"),
                    # v9.9 — דקדוק הרצף וחוב הצילום. שער שאומר רק "לא" לא סיים
                    # את העבודה: כאן הראל רואה גם **מה המערכת מציעה במקום**.
                    "broll_sequence": read_json(d / "broll_sequence_report.json"),
                    "broll_seam": read_json(d / "broll_seam_report.json"),
                    "shot_debt": read_json(d / "shot_debt.json"),
                    "last_run": runner_mod.last_run(d),
                    "running": bool(runner_mod.current_lock(d)),
                    # v7.2: אישור קאבר+קפשן לפני תזמון
                    "schedule_approval": mani.get("schedule_approval"),
                    # v7.4: שליטה ידנית בגימור (מוזיקה/בירולים) + זמינות גימור מהיר
                    "finish_prefs": mani.get("finish_prefs") or {},
                    "has_tight": (d / "EXPORT_TIGHT.mp4").exists(),
                    # v7.7: מצב סנכרון בין הציר שמוצג לבין ה-FINAL שעל הדיסק
                    "sync": sync_mod.sync_status(d),
                    # v9.19: פתיח קבוע מלא מזיז את ציר ה-FINAL מול ציר העריכה.
                    # בלי זה, הערה על 00:12 ב-FINAL מצביעה על 00:02 ב-EDL.
                    "intro_offset_sec": float(
                        (read_json(d / "FINAL_PROVENANCE.json", {}) or {})
                        .get("intro_offset_sec") or 0.0),
                    "auto_synced": healed,
                    # v8.6 (P0-9): חתימת מצב הציר — הקליינט מחזיר אותה ב-/api/save
                    "edl_token": edl_token(d)})

# ---------- הערות legacy (נשמר) ----------
@app.post("/api/notes/<name>")
def notes(name):
    d = wdir(name)
    txt = (request.get_json(force=True) or {}).get("text", "").strip()
    if not txt:
        return jsonify(error="ההודעה ריקה"), 400
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    rounds = load_rounds(d)
    rounds.append({"round": len(rounds) + 1, "note": txt, "note_at": now,
                   "corrected_at": None, "summary": None})
    save_rounds(d, rounds)
    with open(d / "notes.txt", "a", encoding="utf-8") as f:
        f.write(f"[{now}] {txt}\n\n")
    log_correction(d, {"type": "note_sent", "chars": len(txt)})
    # v7: הערה חופשית נכנסת גם כהערה מובנית בתור של קלאוד
    tasks_mod.add_comment(d, txt, category="general", actor="harel", queue=True)
    return jsonify(ok=True, rounds=len(rounds), round_status=compute_round_status(rounds))

@app.post("/api/round/<name>/correct")
def round_correct(name):
    d = wdir(name)
    body = request.get_json(force=True) or {}
    summary = (body.get("summary") or "").strip()
    rounds = load_rounds(d)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    if rounds and rounds[-1].get("corrected_at") is None:
        rounds[-1]["corrected_at"] = now; rounds[-1]["summary"] = summary
    else:
        rounds.append({"round": len(rounds) + 1, "note": None, "note_at": None,
                       "corrected_at": now, "summary": summary})
    save_rounds(d, rounds)
    log_correction(d, {"type": "round_correct", "summary": summary})
    return jsonify(ok=True, rounds=len(rounds), round_status=compute_round_status(rounds))

# ---------- v7: הערות מובנות ----------
@app.post("/api/comments/<name>")
def add_comment(name):
    d = wdir(name)
    b = request.get_json(force=True) or {}
    if not (b.get("text") or "").strip():
        return jsonify(error="הערה ריקה"), 400
    c = tasks_mod.add_comment(
        d, b["text"].strip(),
        time_start=b.get("time_start"), time_end=b.get("time_end"),
        category=b.get("category", "general"), priority=b.get("priority", "normal"),
        actor=b.get("actor", "harel"), frame=b.get("frame"),
        queue=bool(b.get("queue")), on_final=bool(b.get("on_final")),
        artifact_id=b.get("artifact_id"))     # v9.4 — ההערה נקשרת לגרסה מסוימת
    return jsonify(ok=True, comment=dict(c, artifact_ref=tasks_mod.comment_artifact(d, c)))

@app.post("/api/comment/<name>/<cid>")
def update_comment(name, cid):
    d = wdir(name)
    b = request.get_json(force=True) or {}
    c = tasks_mod.update_comment(d, cid, **b)
    if not c:
        return jsonify(error="הערה לא נמצאה"), 404
    return jsonify(ok=True, comment=c)

@app.get("/api/claude-queue")
def claude_queue():
    rows = []
    for d in reg.iter_workdirs():
        for c in tasks_mod.list_comments(d):
            if c["status"] in ("queued_for_claude", "in_progress"):
                rows.append({"project": d.name, **{k: c.get(k) for k in
                             ("comment_id", "text", "category", "priority",
                              "status", "time_start", "created_at")}})
    return jsonify(rows)

# ---------- v9.13: "מה עכשיו" — הצעד הבא לכל פרויקט, במקום אחד ----------
# הראל 16.8.26: "לחשוב איך לקצר את הצעדים לכל תהליך." במקום שהראל יפתח
# פרויקט-פרויקט או ינסח לקלאוד מה תלוי — שורה אחת לכל פרויקט: מה הצעד הבא
# ושל מי הוא (הראל/קלאוד), וכפתור שמעתיק בריף מוכן להדבקה בקלאוד.
def _next_action(d):
    """(action, owner, detail) — של מי המהלך הבא בפרויקט הזה."""
    m = read_json(d / "project_manifest.json", {}) or {}
    # v9.33: תוזמן (scheduled) או פורסם (published) = התזמון סגור. בלי זה פרויקט
    # שתוזמן חוזר ל"לתזמן ב-Metricool" ולבריף — תזמון כפול (לקח 23.8.26, L97).
    if (m.get("state_override") or "") in reg.SCHEDULE_CLOSED_STATES:
        return None
    state = reg.derive_state(d)
    comments = tasks_mod.list_comments(d)
    n_q = sum(1 for c in comments if c["status"] in ("queued_for_claude", "in_progress"))
    n_open = sum(1 for c in comments if c["status"] == "open")
    n_wait = sum(1 for c in comments if c["status"] == "resolved")
    pf = read_json(d / "PREFLIGHT.json", {}) or {}
    pf_v = (pf.get("verdict") or {})
    if state == "ready_to_schedule":
        return ("לתזמן ב-Metricool", "claude", "הקאבר והקפשן מאושרים ונעולים")
    if state == "awaiting_schedule_approval":
        return ("לאשר קאבר+קפשן", "harel", "פאנל 🖼 בלשונית ריצות")
    if n_q:
        return ("לטפל בהערות בתור", "claude", f"{n_q} הערות ממתינות לקלאוד")
    if n_open:
        return ("לשלוח הערות לקלאוד", "harel", f"{n_open} הערות שנכתבו ולא נשלחו")
    if n_wait:
        return ("לבדוק תיקונים", "harel",
                f"{n_wait} תיקונים ממתינים — לשונית 🔍 מה תוקן: סבב בדיקה על "
                f"הנקודות שהשתנו בלבד, בלי לעבור על הסרטון המלא")
    if not (d / "APPROVAL.json").exists():
        det = "ממתין לרוויו ואישור"
        if pf_v and not pf_v.get("ready_for_harel", True):
            det += f" · 🔴 מבקר-קדם: {pf_v.get('summary', '')[:80]}"
        return ("רוויו ואישור", "harel", det)
    if not (d / "FINAL.mp4").exists():
        blk = reg.blocker_of(d)
        return ("גימור", "claude", f"אושר אבל אין FINAL{' · ' + str(blk) if blk else ''}")
    sa = m.get("schedule_approval") or {}
    if not sa:
        return ("טיוטת קאבר+קפשן", "claude", "FINAL קיים — חסר set_draft")
    return None

@app.get("/api/next")
def next_actions():
    rows = []
    planned = load_planned_dates()
    for d in sorted(WORK.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir() or not (d / "edl.json").exists():
            continue
        na = _next_action(d)
        if not na:
            continue
        pf = read_json(d / "PREFLIGHT.json", {}) or {}
        mani = read_json(d / "project_manifest.json", {}) or {}
        rows.append({"project": d.name, "action": na[0], "owner": na[1],
                     "detail": na[2],
                     "planned_date": planned.get(d.name),   # v9.27
                     "dept": mani.get("dept"),   # v9.34 — כדי שסינון מחלקה יעבוד גם ב"מה עכשיו"
                     "preflight": (pf.get("verdict") or {}).get("summary")})
    rows.extend(load_carousels_queue())  # v9.28 — קרוסלות בעריכה, לצד הסרטונים
    # v9.27 (20.9.26, בקשת הראל): "מה עכשיו" מסודר לפי דחיפות פרסום אמיתית —
    # מי שיש לו תאריך מתוכנן, הקרוב קודם; מי שאין לו נשאר בסדר הישן (mtime).
    rows.sort(key=lambda r: (0, r["planned_date"]) if r["planned_date"] else (1, ""))
    return jsonify(rows)

@app.get("/api/preflight/<name>")
def preflight(name):
    doc = read_json(wdir(name) / "PREFLIGHT.json")
    if doc is None:
        return jsonify({"error": "אין PREFLIGHT.json — הגימור טרם רץ"}), 404
    return jsonify(doc)

@app.get("/api/claude-brief")
def claude_brief():
    """בריף מוכן להדבקה בקלאוד — כל מה שממתין לצד של קלאוד, בהודעה אחת.
    מקצר את 'הרוב עדיין נעשה מול קלאוד': קליק אחד במקום ניסוח ידני."""
    lines = ["תרוץ על מערכת העריכה — זה מה שממתין לך:"]
    n = 0
    for d in sorted(WORK.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir() or not (d / "edl.json").exists():
            continue
        na = _next_action(d)
        if not na or na[1] != "claude":
            continue
        n += 1
        lines.append(f"{n}. {d.name} — {na[0]} ({na[2]})")
        for c in tasks_mod.list_comments(d):
            if c["status"] in ("queued_for_claude", "in_progress"):
                lines.append(f"   - הערה [{c.get('category', '?')}] "
                             f"{c.get('time_start', '')}: {c.get('text', '')[:120]}")
    if n == 0:
        lines = ["אין כרגע משימות בצד של קלאוד — הכל אצל הראל או מתוזמן."]
    return jsonify({"n": n, "brief": "\n".join(lines)})

# ---------- v7.7: סנכרון ציר ↔ FINAL ----------
@app.get("/api/sync/<name>")
def sync_get(name):
    return jsonify(sync_mod.sync_status(wdir(name)))

@app.post("/api/sync/<name>")
def sync_post(name):
    """סנכרון ידני מהאפליקציה ('סנכרן ציר'): מיישר את review.cuts למה שנחתך בפועל."""
    d = wdir(name)
    if runner_mod.current_lock(d):
        return jsonify(error="גימור רץ כרגע — נסה שוב כשיסתיים"), 409
    r = sync_mod.reconcile_edl(d, actor="harel", summary="סנכרון ציר ידני מהאפליקציה")
    if r.get("changed"):
        log_correction(d, {"type": "sync_review_from_keeps", "auto": False,
                           "delta": r["drift"]["delta"], "revision_id": r.get("revision_id")})
    return jsonify(dict(r, sync=sync_mod.sync_status(d)))

# ---------- v7: revisions ----------
@app.get("/api/revisions/<name>")
def revisions(name):
    return jsonify(rev_mod.list_revisions(wdir(name)))

@app.post("/api/undo/<name>")
def undo(name):
    d = wdir(name); guard_lock(d)
    r = rev_mod.undo(d)
    log_correction(d, {"type": "undo", "result": r.get("head")})
    return jsonify(r)

@app.post("/api/redo/<name>")
def redo(name):
    d = wdir(name); guard_lock(d)
    r = rev_mod.redo(d)
    log_correction(d, {"type": "redo", "result": r.get("head")})
    return jsonify(r)

@app.post("/api/restore/<name>")
def restore(name):
    d = wdir(name); guard_lock(d)
    rid = (request.get_json(force=True) or {}).get("revision_id")
    if not rid or not isinstance(rid, str):
        raise ValueError("restore דורש revision_id")   # היה 500 מ-AttributeError
    r = rev_mod.restore(d, rid, actor="harel")
    log_correction(d, {"type": "restore_revision", "revision_id": rid})
    return jsonify(r)

@app.get("/api/compare/<name>")
def compare(name):
    d = wdir(name)
    ra, rb = request.args.get("a"), request.args.get("b")
    if not ra or not rb:
        raise ValueError("compare דורש שני מזהי revision (a,b)")   # היה 500
    return jsonify(rev_mod.compare(d, ra, rb))

# ---------- שמירה / recut / תמליל ----------
def snap_cuts_to_words(d, cuts):
    """v7.5 (הראל 24.7: 'חיתוכים ידניים לא מדויקים בגרסה הסופית — קפיצות וקטיעות'):
    גבול חיתוך ידני שנופל *בתוך* מילה נצמד לגבול המילה הקרוב (עד 0.3ש), עם ריפוד
    30ms — כך שמילה תמיד נחתכת בשלמותה או נשמרת בשלמותה, במקום הברה קטועה שנשמעת
    כקפיצה. אותה נוסחה לשני הגבולות: הצמדה ל-word.start-pad מכניסה את המילה לחיתוך,
    ל-word.end+pad משאירה אותה בחוץ. רק על חיתוכים של הראל (source=harel)."""
    wp = d / "whisper_raw.json"
    if not wp.exists():
        return cuts, 0
    try:
        words = json.loads(wp.read_text(encoding="utf-8"))
    except Exception:
        return cuts, 0
    SNAP, PAD = 0.3, 0.03
    moved = 0

    def snap(t):
        nonlocal moved
        for w in words:
            s, e = float(w["start"]), float(w["end"])
            if s >= t:
                break
            if s < t < e:
                nt = (s - PAD) if (t - s) <= (e - t) else (e + PAD)
                if abs(nt - t) <= SNAP:
                    moved += 1
                    return round(max(0.0, nt), 3)
                return t
        return t

    out = []
    for c in cuts:
        c = dict(c)
        try:
            if c.get("source") == "harel":
                s2, e2 = snap(float(c["start"])), snap(float(c["end"]))
                if e2 - s2 >= 0.08:
                    c["start"], c["end"] = s2, e2
        except (TypeError, ValueError, KeyError):
            pass
        out.append(c)
    return out, moved

@app.post("/api/save/<name>")
def save(name):
    d = wdir(name); guard_lock(d)
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        raise ValueError("גוף הבקשה חייב להיות אובייקט JSON")
    # v8.6 (P0-9) — הגנת lost-update. שורש: /api/save קיבל את מערך ה-cuts בשלמותו
    # וכתב את edl.json בלי base_revision/ETag. שני טאבים על אותו פרויקט = הכתיבה
    # האחרונה מנצחת בשקט, וה-revision שנוצר מתעד את התוצאה ולא את הקונפליקט.
    # base_token אופציונלי (תאימות לאחור לקליינטים ישנים); כשהוא נשלח ולא תואם —
    # 409 עם ה-token הנוכחי, והאפליקציה טוענת מחדש במקום לדרוס.
    cur_token = edl_token(d)
    base_token = data.get("base_token")
    if base_token and base_token != cur_token:
        return jsonify(error="הציר השתנה מאז שנטען במסך הזה (טאב אחר? תיקון של קלאוד?) — "
                             "טען מחדש כדי לא לדרוס שינוי",
                       code="STALE_EDL", current_token=cur_token,
                       your_token=base_token), 409
    edl_path = d / "edl.json"
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    if not (d / "edl.machine.json").exists():          # שימור גרסת המכונה ללמידה
        (d / "edl.machine.json").write_text(edl_path.read_text(encoding="utf-8"), encoding="utf-8")
    rev_mod.ensure_baseline(d)                          # v7: revision-בסיס לפני השינוי הראשון
    try:
        speed = round(float(data.get("speed", 1.0) or 1.0), 3)
    except (TypeError, ValueError):
        speed = 1.0
    speed = min(2.0, max(0.5, speed))
    snapped_cuts, n_snapped = snap_cuts_to_words(d, data.get("cuts", []))
    review = {"cuts": snapped_cuts, "hook_move": data.get("hook_move"), "speed": speed}
    edl["review"] = review
    edl["keep_segments"] = derive_keep(float(edl["total_dur"]), review["cuts"], review["hook_move"])
    edl["kept_dur"] = round(sum(k["end"] - k["start"] for k in edl["keep_segments"]), 2)
    edl["kept_dur_at_speed"] = round(edl["kept_dur"] / speed, 2)
    atomic_write(edl_path, json.dumps(edl, ensure_ascii=False, indent=1))
    for act in data.get("actions", []):
        log_correction(d, act)
    # v7: revision על כל שמירה
    acts = data.get("actions", [])
    summary = data.get("summary") or (
        f"{len(acts)} פעולות עריכה" if acts else "שמירת עריכה")
    rid = rev_mod.create_revision(d, actor=data.get("actor", "harel"),
                                  summary=summary, actions=acts)
    if n_snapped:
        log_correction(d, {"type": "snap_cuts_to_words", "moved": n_snapped})
    return jsonify(ok=True, kept=edl["kept_dur"], kept_at_speed=edl["kept_dur_at_speed"],
                   speed=speed, segments=len(edl["keep_segments"]), revision_id=rid,
                   snapped=n_snapped, edl_token=edl_token(d))

@app.post("/api/recut/<name>")
def recut(name):
    d = wdir(name); guard_lock(d)
    r = subprocess.run(["python3", str(TOOLS / "edl_cut.py"), "--video", str(d / "INPUT.mp4"),
                        "--edl", str(d / "edl.json"), "--out", str(d / "PREVIEW.mp4"),
                        "--crf", "23", "--preset", "veryfast"],
                       capture_output=True, text=True, timeout=1200)
    if r.returncode != 0:
        return jsonify(error=(r.stdout + r.stderr)[-400:]), 500
    return jsonify(ok=True, url=f"/media/{name}/PREVIEW.mp4")

@app.post("/api/transcript/<name>")
def transcript(name):
    d = wdir(name); guard_lock(d)
    txt = (request.get_json(force=True) or {}).get("text", "").strip()
    if not txt:
        return jsonify(error="טקסט ריק"), 400
    rev_mod.ensure_baseline(d)
    atomic_write(d / "edited.txt", txt)
    log_correction(d, {"type": "transcript_fix", "chars": len(txt)})
    rid = rev_mod.create_revision(d, actor="harel", summary="תיקון תמליל")
    return jsonify(ok=True, revision_id=rid)

# ---------- אישור וגימור (v7: תחת נעילה, idempotent) ----------
@app.post("/api/approve/<name>")
def approve(name):
    d = wdir(name)
    body = request.get_json(force=True) or {}
    n_corr = 0
    if (d / "corrections.jsonl").exists():
        n_corr = sum(1 for _ in open(d / "corrections.jsonl", encoding="utf-8"))
    rev_mod.ensure_baseline(d)
    approved_rev = rev_mod.mark_approved(d)
    # v9.23 — האישור קושר רק את הפתיחה החזותית **שנצפתה** (digest + תצוגה טרייה).
    # אישור בלי תצוגה טרייה ⇒ אין טיפול בגימור הזה (ולא כשל).
    vh_bind = _vh_bind_on_approve(d, body)
    # v9.25 — נימוק אורך מהמודאל נשמר במניפסט (הגימור וה-QA קוראים משם)
    _lr = (body.get("length_reason") or "").strip()
    if _lr:
        _m = read_json(d / "project_manifest.json", {}) or {}
        _m["length_reason"] = _lr
        atomic_write(d / "project_manifest.json", json.dumps(_m, ensure_ascii=False, indent=1))
    atomic_write(d / "APPROVAL.json", json.dumps({
        "tag": "[APPROVE-PUBLISH]", "approved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "via": "review-app", "corrections": n_corr, "note": body.get("note", ""),
        "content_type": body.get("content_type", "value"),
        "length_reason": _lr or None,
        "brand": body.get("brand", "rel"),
        "speed": body.get("speed", 1.0),
        "revision_id": approved_rev,
        **({"visual_hook": vh_bind} if vh_bind else {})}, ensure_ascii=False, indent=1))
    venv_py = Path.home() / ".rel-whisper" / "bin" / "python"
    pybin = str(venv_py) if venv_py.exists() else "python3"
    r = runner_mod.start_detached(d, body, pybin)
    log_correction(d, {"type": "approve", "run_id": r.get("run_id"),
                       "already_running": r.get("already_running", False),
                       "revision_id": approved_rev})
    return jsonify(ok=True, started=not r.get("already_running"),
                   already_running=r.get("already_running", False),
                   run_id=r.get("run_id"), resume=r.get("resume"))

# ---------- v9.23: Visual Hook — שורה מקופלת אחת, השוואה, כיבוי, קשירת אישור ----------
# אין מסך אישור חדש ואין endpoint תזמון חדש. "אשר והמשך לגימור" הקיים קושר את
# ה-digest שנצפה; הצעה שלא נצפתה לעולם לא מוחלת.
VH_EVENTS = ("hook_suggested", "hook_selected", "hook_approved", "hook_disabled",
             "hook_replaced", "hook_strength_changed", "hook_rejected", "hook_render_failed")


def _vh_pref(d):
    m = read_json(d / "project_manifest.json", {}) or {}
    return (m.get("finish_prefs") or {}).get("visual_hook") or {}


def _vh_pref_version(pref):
    return sha256_json(pref or {})[7:23]


def _vh_current(d):
    return read_json(d / "visual_hook" / "review" / "current.json")


def _vh_fresh(d, cur):
    return bool(cur and cur.get("edit_token") == vh_mod.edit_token(d))


def _vh_preview_ok(d, cur):
    pv = (cur or {}).get("preview") or {}
    if not pv.get("treatment"):
        return False
    for k in ("treatment", "side_by_side"):
        fp = d / str(pv.get(k) or "")
        if not fp.is_file() or vh_mod.file_sha256(fp) != (pv.get("sha256") or {}).get(k):
            return False
    return True


def _vh_event(d, event, **kw):
    if event not in VH_EVENTS:
        raise ValueError(f"אירוע פתיחה חזותית לא מוכר: {event}")
    m = read_json(d / "project_manifest.json", {}) or {}
    ev = {"type": "visual_hook", "schema_version": 1, "event": event,
          "project_id": m.get("project_id"), "actor": kw.pop("actor", "harel"),
          "content_type": m.get("content_type"), "brand": m.get("brand"),
          "speaker_id": None, "performance": None}
    ev.update(kw)
    ev["event_id"] = sha256_json({k: ev.get(k) for k in (
        "project_id", "event", "plan_digest", "actor", "artifact_id", "run_id",
        "edit_token", "comparison_seen")})[7:31]
    cj = d / "corrections.jsonl"
    if cj.exists() and f'"event_id": "{ev["event_id"]}"' in cj.read_text(encoding="utf-8"):
        return ev["event_id"]                         # ניסיון חוזר = אותו אירוע, לא קול נוסף
    log_correction(d, ev)
    return ev["event_id"]


def _vh_bind_on_approve(d, body):
    want = body.get("visual_hook_plan_digest")
    pref = _vh_pref(d)
    cur = _vh_current(d)
    plan = (cur or {}).get("plan") or {}
    ok = (bool(want) and pref.get("enabled") is not False and _vh_fresh(d, cur)
          and _vh_preview_ok(d, cur) and plan.get("plan_digest") == want
          and plan.get("recipe") not in (None, "NO_OP"))
    if ok:
        ok = not vh_mod.validate_plan_shape(plan) and vh_mod.digest_plan(plan) == want
    if not ok:
        if pref.get("approved_plan_digest"):
            reg.set_finish_prefs(d, {"visual_hook": {"approved_plan_digest": None}})
        if want or pref:
            return {"bound": False, "requested": want,
                    "reason": "no_fresh_preview" if want else "not_requested"}
        return None
    vh_mod.atomic_write_json(vh_mod.approved_plan_path(d, want), plan)
    seen = bool(body.get("visual_hook_comparison_seen") or pref.get("comparison_seen"))
    reg.set_finish_prefs(d, {"visual_hook": {"approved_plan_digest": want, "enabled": True,
                                             "comparison_seen": seen}})
    _vh_event(d, "hook_approved", plan_digest=want, comparison_seen=seen,
              edit_token=cur.get("edit_token"), suggested_recipe=plan.get("recipe"),
              selected_recipe=plan.get("recipe"), strength_after="subtle",
              evidence_grade=(plan.get("evidence") or {}).get("grade"))
    return {"bound": True, "plan_digest": want, "comparison_seen": seen, "recipe": plan.get("recipe")}


@app.get("/api/visual-hook/<name>")
def visual_hook_get(name):
    d = wdir(name)
    pref = _vh_pref(d)
    cur = _vh_current(d)
    fresh = _vh_fresh(d, cur)
    plan = (cur or {}).get("plan") or {}
    rep = (cur or {}).get("report") or {}
    treat = (fresh and plan.get("recipe") not in (None, "NO_OP")
             and pref.get("enabled") is not False and _vh_preview_ok(d, cur))
    pv = (cur or {}).get("preview") or {}
    return jsonify(
        mode=pref.get("mode") or "off", enabled=pref.get("enabled") is not False,
        pref=pref, pref_version=_vh_pref_version(pref), hook_token=vh_mod.edit_token(d),
        fresh=fresh, treatment_available=bool(treat),
        label_he=vh_mod.LABEL_HE["SMART_PUNCH_IN" if treat else "NO_OP"],
        plan_digest=plan.get("plan_digest") if treat else None,
        candidate_id=plan.get("candidate_id") if treat else None,
        why=rep.get("why") or [], has_alternative=bool(rep.get("has_alternative")),
        preview=({"treatment": f"/media/{name}/{pv['treatment']}",
                  "side_by_side": f"/media/{name}/{pv['side_by_side']}"} if treat else None),
        approved_plan_digest=pref.get("approved_plan_digest"),
        status=read_json(d / "visual_hook" / "review" / "status.json"),
        running_lock=runner_mod.current_lock(d),
        last_finish=read_json(d / "visual_hook_report.json"))


@app.post("/api/visual-hook/<name>")
def visual_hook_set(name):
    d = wdir(name); guard_lock(d)
    b = request.get_json(force=True) or {}
    pref = _vh_pref(d)
    if b.get("pref_version") != _vh_pref_version(pref):
        return jsonify(error="העדפות הפתיחה החזותית השתנו במסך אחר — טען מחדש כדי לא לדרוס",
                       code="STALE_PREFS", pref_version=_vh_pref_version(pref)), 409
    action = b.get("action")
    ev, extra = None, {}
    cur = _vh_current(d)
    plan = (cur or {}).get("plan") or {}
    if action == "disable":
        new = {"enabled": False, "approved_plan_digest": None, "selected_candidate_id": None,
               "plan_digest": None}
        ev = "hook_disabled"
        extra = {"plan_digest": plan.get("plan_digest"), "suggested_recipe": plan.get("recipe"),
                 "selected_recipe": "NO_OP", "reason_codes": [str(x) for x in (b.get("reasons") or [])][:5]}
    elif action == "enable":
        new = {"enabled": True}
    elif action == "compare_viewed":
        new = {"comparison_seen": True}
    elif action == "select":
        if not (_vh_fresh(d, cur) and _vh_preview_ok(d, cur)) or \
                b.get("expected_plan_digest") != plan.get("plan_digest"):
            return jsonify(error="התצוגה המקדימה אינה תואמת לעריכה הנוכחית — הכן תצוגה מחדש",
                           code="HOOK_REVIEW_STALE"), 409
        new = {"enabled": True, "selected_candidate_id": plan.get("candidate_id"),
               "plan_digest": plan.get("plan_digest")}
        ev = "hook_selected"
        extra = {"plan_digest": plan.get("plan_digest"), "selected_recipe": plan.get("recipe"),
                 "edit_token": cur.get("edit_token")}
    elif action == "mode":
        new = {"mode": b.get("mode")}
    else:
        raise ValueError("action לא מוכר (disable/enable/select/compare_viewed/mode)")
    m = reg.set_finish_prefs(d, {"visual_hook": new})
    if ev:
        _vh_event(d, ev, **extra)
    p2 = (m.get("finish_prefs") or {}).get("visual_hook") or {}
    return jsonify(ok=True, pref=p2, pref_version=_vh_pref_version(p2))


@app.post("/api/visual-hook/<name>/preview")
def visual_hook_preview(name):
    d = wdir(name); guard_lock(d)
    if (_vh_pref(d).get("mode") or "off") == "off":
        # פעולה מפורשת של הראל על הפרויקט הזה בלבד — shadow, לא auto
        reg.set_finish_prefs(d, {"visual_hook": {"mode": "shadow"}})
    mani = read_json(d / "project_manifest.json", {}) or {}
    venv_py = Path.home() / ".rel-whisper" / "bin" / "python"
    pybin = str(venv_py) if venv_py.exists() else "python3"
    r = runner_mod.start_detached(d, {"content_type": mani.get("content_type") or "value",
                                      "brand": mani.get("brand") or "rel"}, pybin,
                                  job_kind="hook_preview")
    return jsonify(ok=True, run_id=r.get("run_id"), already_running=r.get("already_running", False))


@app.post("/api/cancel/<name>")
def cancel(name):
    return jsonify(runner_mod.cancel(wdir(name)))

# ---------- v7.3: מחיקת סרטון — soft-delete לפח (אף פעם לא rm -rf ישיר) ----------
# שורש: "מחיקה בלתי הפיכה" מחייבת עצירה ואישור (הנחיות R.E.L). לכן מחיקה מהאפליקציה
# תמיד מעבירה לפח (_work/_trash) עם timestamp — אפשר לשחזר. מחיקה תמידית (purge)
# היא פעולה נפרדת ומפורשת מתוך מסך הפח, עם אישור-שם נוסף.
@app.post("/api/delete/<name>")
def delete_project(name):
    d = wdir(name)
    if runner_mod.current_lock(d):
        return jsonify(error="גימור רץ ברקע כרגע — בטל את הריצה (⏹) ואז אפשר למחוק"), 409
    b = request.get_json(force=True) or {}
    if (b.get("confirm_name") or "").strip() != name:
        return jsonify(error="אישור שם לא תואם — הקלד את שם הסרטון המדויק"), 400
    TRASH.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = TRASH / f"{ts}__{name}"
    n = 1
    while dest.exists():
        n += 1
        dest = TRASH / f"{ts}__{name}__{n}"
    shutil.move(str(d), str(dest))
    log_trash({"action": "delete", "name": name, "trash_dir": dest.name})
    return jsonify(ok=True, trashed_as=dest.name)

@app.get("/api/trash")
def trash_list():
    TRASH.mkdir(parents=True, exist_ok=True)
    out = []
    for d in sorted(TRASH.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        m = TRASH_RE.match(d.name)
        out.append({"trash_name": d.name, "original_name": m.group(1) if m else d.name,
                    "trashed_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(d.stat().st_mtime))})
    return jsonify(out)

@app.post("/api/trash/restore/<trash_name>")
def trash_restore(trash_name):
    src = TRASH / safe(trash_name)
    if not src.is_dir():
        return jsonify(error="לא נמצא בפח"), 404
    m = TRASH_RE.match(trash_name)
    original = m.group(1) if m else trash_name
    dest = WORK / original
    if dest.exists():
        dest = WORK / f"{original}__שוחזר__{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.move(str(src), str(dest))
    log_trash({"action": "restore", "name": dest.name, "trash_dir": trash_name})
    return jsonify(ok=True, restored_as=dest.name)

@app.post("/api/trash/purge/<trash_name>")
def trash_purge(trash_name):
    d = TRASH / safe(trash_name)
    if not d.is_dir():
        return jsonify(error="לא נמצא בפח"), 404
    m = TRASH_RE.match(trash_name)
    original = m.group(1) if m else trash_name
    b = request.get_json(force=True) or {}
    if (b.get("confirm_name") or "").strip() != original:
        return jsonify(error="אישור שם לא תואם — מחיקה לצמיתות דורשת הקלדת שם הסרטון המדויק"), 400
    shutil.rmtree(d)
    log_trash({"action": "purge", "name": trash_name})
    return jsonify(ok=True)

# ---------- v7.1: עדכון ידני של מצב/מחלקה ----------
@app.post("/api/meta/<name>")
def set_meta(name):
    d = wdir(name)
    b = request.get_json(force=True) or {}
    kwargs = {}
    if "state_override" in b:
        kwargs["state_override"] = b["state_override"] or None
    if "dept" in b:
        kwargs["dept"] = b["dept"]
    try:
        m = reg.set_meta(d, **kwargs)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    log_correction(d, {"type": "manual_meta", "fields": {k: b.get(k) for k in
                       ("state_override", "dept") if k in b}})
    return jsonify(ok=True, state=reg.derive_state(d), dept=m.get("dept"),
                   state_override=m.get("state_override"))


# ---------- v7.2: אישור קאבר+קפשן — שער בין FINAL לתזמון ב-Metricool ----------
# שורש (בקשת הראל 23.7): לפני שמתזמנים, הראל צריך לראות את הקאבר ואת הקפשן
# בעצמו, לאשר/לתקן, ורק אז זה "מוכן לתזמון". ה-checksum שנועל ב-approve הוא
# מה שקלאוד חייב להשוות מול הקובץ בפועל רגע לפני קריאה ל-Metricool — לא לתזמן
# בלי התאמה מדויקת (ראה set_schedule_approval + derive_state ב-registry.py).
@app.get("/api/schedule-review/<name>")
def schedule_review(name):
    d = wdir(name)
    m = read_json(d / "project_manifest.json", {}) or {}
    return jsonify(schedule_approval=m.get("schedule_approval"),
                   has_final=(d / "FINAL.mp4").exists(),
                   state=reg.derive_state(d))

@app.post("/api/schedule-review/<name>")
def schedule_review_action(name):
    d = wdir(name)
    b = request.get_json(force=True) or {}
    action = b.get("action")
    if action not in ("set_draft", "approve", "request_changes"):
        return jsonify(error="פעולה לא מוכרת"), 400
    if action == "request_changes":
        note = (b.get("note") or "").strip()
        if not note:
            return jsonify(error="צריך הערה — מה לשנות בקאבר/בקפשן"), 400
        tasks_mod.add_comment(d, note, category=b.get("category", "cover"),
                              priority=b.get("priority", "normal"),
                              actor="harel", queue=True)
    try:
        m = reg.set_schedule_approval(
            d, action, cover_path=b.get("cover_path"),
            caption_draft=b.get("caption_draft"), caption_text=b.get("caption_text"),
            note=b.get("note"),
            # v9.48 — שער הקפשן: סוג תוכן, מותג ומהלך ההוספה של הטיוטה
            caption_type=b.get("caption_type"), brand=b.get("brand"),
            caption_meta=b.get("caption_meta"),
            # v9.4 — האישור ננעל לגרסה מסוימת. ברירת מחדל: מה שמוצג באפליקציה.
            artifact_id=b.get("artifact_id") or art_mod.display_target(d).get("artifact_id"))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    log_correction(d, {"type": f"schedule_review_{action}"})
    return jsonify(ok=True, schedule_approval=m.get("schedule_approval"),
                   state=reg.derive_state(d))

# ---------- v7.4: שליטה ידנית בגימור — מוזיקה / בירולים / גימור מהיר ----------
# שורש (בקשת הראל 24.7): "הרבה תיקונים קטנים מצריכים כל פעם קלאוד וזה מקשה לסגור
# סרטונים". הפתרון: העדפות גימור נשמרות במניפסט (finish_prefs) והראל מפעיל בעצמו
# "גימור מהיר" (--refinish) — reconcile+בירול+מוזיקה+כתוביות+QA על הציר המהודק
# הקיים, בלי recut/whisper/tighten. דקות במקום המתנה לקלאוד.

@app.get("/api/music")
def music_tracks():
    catalog = (read_json(TOOLS / "music-catalog.json", {}) or {}).get("tracks", {})
    rotation = read_json(TOOLS / "music-rotation.json", {}) or {}
    history = rotation.get("history", {})
    out = []
    for p in sorted(MUSIC_DIR.glob("*.mp3")):
        meta = catalog.get(p.name, {})
        out.append({"file": p.name, "genre": meta.get("genre"),
                    "energy": meta.get("energy"), "duration": meta.get("duration"),
                    "last_used": history.get(p.name)})
    return jsonify(out)

@app.get("/music/<path:fname>")
def music_media(fname):
    if "/" in fname or ".." in fname or not fname.endswith(".mp3"):
        return "forbidden", 403
    p = MUSIC_DIR / fname
    if not p.is_file():
        return "not found", 404
    return send_file(str(p), conditional=True)

def _broll_catalog():
    cfg = read_json(TOOLS / "broll-catalog-config.json", {}) or {}
    cat_path = Path(cfg.get("catalog_path", ""))
    if not cat_path.is_file():                      # fallback: נתיב יחסי לתיקיית המערכת
        cat_path = SYS_DIR / "בירולים" / "catalog.json"
    cat = read_json(cat_path, {}) or {}
    return cat.get("items", [])

@app.get("/api/broll")
def broll_list():
    keys = ("id", "file", "desc", "tags", "audience", "category", "dur", "vertical", "path")
    return jsonify([{k: it.get(k) for k in keys} for it in _broll_catalog()])

@app.get("/broll-media/<bid>")
def broll_media(bid):
    it = next((x for x in _broll_catalog() if x.get("id") == bid), None)
    if not it:
        return "not found", 404
    p = Path(it.get("path", ""))
    if not p.is_file():
        return "not found", 404
    return send_file(str(p), conditional=True)

@app.post("/api/finish-prefs/<name>")
def finish_prefs(name):
    d = wdir(name)
    b = request.get_json(force=True) or {}
    prefs = {k: b[k] for k in ("music", "broll") if k in b}
    if not prefs:
        return jsonify(error="אין העדפות לשמירה (music / broll)"), 400
    m = reg.set_finish_prefs(d, prefs)
    log_correction(d, {"type": "finish_prefs", "prefs": prefs})
    return jsonify(ok=True, finish_prefs=m.get("finish_prefs"))

@app.post("/api/refinish/<name>")
def refinish(name):
    d = wdir(name)
    if not (d / "EXPORT_TIGHT.mp4").exists() or not (d / "whisper_export_tight.json").exists():
        return jsonify(error="גימור מהיר אפשרי רק אחרי ריצת גימור מלאה אחת "
                             "(חסר הציר המהודק) — הרץ קודם 'אשר והמשך לגימור'"), 400
    b = request.get_json(force=True) or {}
    appr = read_json(d / "APPROVAL.json", {}) or {}
    mani = read_json(d / "project_manifest.json", {}) or {}
    # v7.5 — מותג לפי המחלקה, לא ברירת מחדל עיוורת (באג 24.7: תיקון כתוביות לסרטון
    # של "הראל חיון" צרב מתאר אדום של המועדון במקום הכחול האישי — כי לא היה
    # APPROVAL.json והמותג נפל ל-rel). מחלקת "הראל חיון" ⇒ תמיד personal.
    dept = (mani.get("dept") or "").strip()
    brand = mani.get("brand") or appr.get("brand") or "rel"
    if dept == "הראל חיון":
        brand = "personal"
    content_type = mani.get("content_type") or appr.get("content_type") or "value"
    body = {"content_type": content_type, "brand": brand, "refinish": True}
    venv_py = Path.home() / ".rel-whisper" / "bin" / "python"
    pybin = str(venv_py) if venv_py.exists() else "python3"
    r = runner_mod.start_detached(d, body, pybin)
    log_correction(d, {"type": "refinish", "scope": b.get("scope", "all"),
                       "run_id": r.get("run_id"),
                       "already_running": r.get("already_running", False)})
    return jsonify(ok=True, started=not r.get("already_running"),
                   already_running=r.get("already_running", False),
                   run_id=r.get("run_id"))

def _eta_secs(d, refinish=False):
    """v7.8 — הערכת זמן נותר מריצות קודמות מוצלחות (חציון), כדי שהראל יראה
    'עוד ~40 שניות' במקום ספינר עיוור. מסתמך על total_secs שנרשם ברשומות הריצה
    מ-v7.8 והלאה; אין היסטוריה ⇒ None (האפליקציה לא מציגה ETA)."""
    tot = []
    rd = d / "runs"
    if rd.exists():
        for f in sorted(rd.glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:12]:
            r = read_json(f, {}) or {}
            if r.get("status") == "done" and r.get("total_secs"):
                is_refin = "--refinish" in (r.get("command") or [])
                if is_refin == refinish:
                    tot.append(float(r["total_secs"]))
    if not tot:
        return None
    tot.sort()
    return round(tot[len(tot) // 2])


@app.get("/api/status/<name>")
def status(name):
    d = wdir(name)
    p = d / "finish_status.json"
    base = read_json(p, {"state": "none"}) or {"state": "none"}
    base["running_lock"] = runner_mod.current_lock(d)
    base["last_run"] = runner_mod.last_run(d)
    # v7.8: ETA + מה תוקן אוטומטית מההערות (notefix)
    lock = base["running_lock"] or {}
    base["eta_secs"] = _eta_secs(d, refinish=bool(lock.get("refinish")))
    base["note_corrections"] = read_json(d / "note_corrections.json")
    return jsonify(base)

@app.get("/api/qa/<name>")
def qa(name):
    d = wdir(name)
    return jsonify({"qa_report": read_json(d / "qa_report.json"),
                    "cut_qa": read_json(d / "cut_qa_report.json"),
                    "gate_fail": read_json(d / "gate_fail.json"),
                    "canon": read_json(d / "canon_report.json")})

_FF_CACHE = {}

def _ffmpeg_bin():
    """נתיב מוחלט ל-ffmpeg. PATH של השרת אינו בהכרח PATH של shell התחברות."""
    if "ff" in _FF_CACHE:
        return _FF_CACHE["ff"]
    cand = [os.environ.get("RELVID_FFMPEG"), shutil.which("ffmpeg"),
            "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]
    ff = next((c for c in cand if c and os.path.isfile(c) and os.access(c, os.X_OK)), None)
    _FF_CACHE["ff"] = ff
    return ff


@app.get("/api/frame/<name>")
def frame(name):
    """חילוץ פריים בודד (JPEG) — להצגת שני צדי גבול-חיתוך באפליקציה."""
    d = wdir(name)
    try:
        t = max(0.0, float(request.args.get("t", 0)))
    except ValueError:
        return "bad t", 400
    src = request.args.get("src", "INPUT.mp4")
    if not re.fullmatch(r"[\w.\-+]+\.mp4", src) or not (d / src).exists():
        return "not found", 404
    # v9.21 — הבינארי נפתר בנתיב מוחלט. השרת מופעל לעיתים בלי סביבת login,
    # ואז /opt/homebrew/bin חסר מה-PATH: subprocess זורק FileNotFoundError,
    # המטפל הגלובלי מחזיר 404 "פרויקט לא נמצא", והתמונות נשברות בשקט.
    ff = _ffmpeg_bin()
    if not ff:
        return jsonify({"code": "FFMPEG_MISSING",
                        "error": "ffmpeg לא נמצא ב-PATH של השרת"}), 503
    r = subprocess.run([ff, "-nostdin", "-ss", f"{t:.3f}", "-i", str(d / src),
                        "-frames:v", "1", "-vf", "scale=360:-2", "-f", "image2",
                        "-c:v", "mjpeg", "-q:v", "5", "pipe:1"],
                       capture_output=True, timeout=30)
    if r.returncode != 0 or not r.stdout:
        return jsonify({"code": "FRAME_ERROR",
                        "error": (r.stderr or b"").decode("utf-8", "replace")[-400:]}), 500
    return Response(r.stdout, mimetype="image/jpeg")

# ---------- v9.4: מרכז גרסאות ותוצרים (Artifact Store) ----------
# שורש: "גרסה" הייתה שם קובץ (FINAL.mp4) שכל ריצה דרסה, ולכן היסטוריית הווידאו
# נאבדה. מכאן: כל תוצר מוצלח הוא artifact עם מזהה קבוע, והאפליקציה מציגה תמיד
# **מה בדיוק מוצג עכשיו** ואם יש גרסה חדשה יותר שממתינה.

@app.get("/api/artifacts/<name>")
def artifacts_list(name):
    d = wdir(name)
    art_mod.sweep_staging(d)
    deep = request.args.get("verify") == "1"
    arts = art_mod.list_artifacts(d, verify_integrity=True)
    p = art_mod.pointers(d)
    rows = []
    for a in arts:
        integ = a.get("integrity") or {"ok": a.get("exists"), "state": "ok"}
        rows.append({
            "artifact_id": a["artifact_id"], "version": a.get("version"),
            "created_at": a.get("created_at"), "duration": a.get("duration"),
            "size_bytes": a.get("size_bytes"), "checksum": a.get("checksum"),
            "run_id": a.get("run_id"), "revision_id": a.get("revision_id"),
            "qa": a.get("qa"), "music": a.get("music"),
            "broll_items": a.get("broll_items"), "summary": a.get("summary"),
            "approved_at": a.get("approved_at"), "published_at": a.get("published_at"),
            "migrated": a.get("migrated", False), "matched": a.get("matched"),
            "status": art_mod.status_of(d, a["artifact_id"], p),
            "integrity": integ,
            "media_url": f"/artifact-media/{name}/{a['artifact_id']}",
        })
    return jsonify({
        "artifacts": rows,
        "pointers": {k: p.get(k) for k in art_mod.POINTER_KINDS},
        "display": art_mod.display_target(d),
        "live_final_artifact": art_mod.artifact_of_live_final(d) if deep else None,
        "unmatched": (read_json(art_mod.adir(d) / "unmatched.json", {}) or {}).get(
            "unmatched_runs", []),
    })


@app.post("/api/artifacts/<name>/<aid>/<action>")
def artifact_action(name, aid, action):
    d = wdir(name)
    if not art_mod.get_artifact(d, aid):
        return jsonify(error=f"גרסה לא נמצאה: {aid}"), 404
    v = art_mod.verify(d, aid)
    if action in ("approve", "publish", "activate") and not v["ok"]:
        return jsonify(error=f"הגרסה פגומה ({v['detail']}) — אי אפשר {action}",
                       integrity=v), 409
    if action == "approve":
        art_mod.approve(d, aid, actor="harel")
    elif action == "publish":
        art_mod.publish(d, aid, actor="harel")
    elif action == "activate":
        if runner_mod.current_lock(d):
            return jsonify(error="גימור רץ כרגע — אי אפשר להחליף גרסה פעילה"), 409
        r = art_mod.activate(d, aid, actor="harel")
        if not r.get("ok"):
            return jsonify(error=r.get("error")), 409
    elif action == "verify":
        return jsonify(ok=v["ok"], integrity=v)
    else:
        return jsonify(error=f"פעולה לא מוכרת: {action}"), 400
    log_correction(d, {"type": f"artifact_{action}", "artifact_id": aid})
    return jsonify(ok=True, display=art_mod.display_target(d),
                   pointers=art_mod.pointers(d), state=reg.derive_state(d))


# ---------- v9.15: "מה תוקן בגרסה הזו" — בדיקת תיקונים במקום צפייה מלאה ----------
# הראל 17.8.26: "שאוכל לבדוק בדיוק את ההערות שתוקנו במקום לעבור על הסרטון
# המלא כל פעם שיש תיקונים." כל גרסה מקבלת יומן שינויים עם טיימקוד **בציר
# שלה** (ממופה מהגרסה שעליה נכתבה ההערה), וסבב בדיקה שמנגן רק את הנקודות.

@app.get("/api/changelog/<name>")
def changelog(name):
    d = wdir(name)
    doc = cl_mod.build(d, artifact_id=request.args.get("artifact"))
    for v in doc["versions"]:
        v["review_plan"] = cl_mod.review_plan(v)
        # v9.18 — הסבב הממוקד: רק מה שקלאוד לא אימת והראל טרם סימן
        v["review_plan_focus"] = cl_mod.review_plan(v, focus=True)
    # v9.18 — ראיות האימות של קלאוד (גיליונות + reel), אם קיימות
    fv = read_json(d / "FIX_VERIFY.json") or {}
    if fv.get("artifact_id"):
        doc["fix_verify"] = {"artifact_id": fv["artifact_id"],
                             "generated_at": fv.get("generated_at"),
                             "summary": fv.get("summary"),
                             "reel": fv.get("reel"),
                             "items": {x["item_id"]: {"status": x["machine"]["status"],
                                                      "detail": x["machine"]["detail"],
                                                      "sheet": x.get("sheet")}
                                       for x in fv.get("items", [])}}
    return jsonify(doc)


@app.get("/fixverify-media/<name>/<aid>/<fname>")
def fixverify_media(name, aid, fname):
    """גיליונות-המגע וה-CHECK_REEL של אימות התיקונים (v9.18)."""
    d = wdir(name)
    if not re.fullmatch(r"[\w.\-+]+\.(jpg|mp4)", fname) \
            or not re.fullmatch(r"[\w\-]+", aid):
        return "forbidden", 403
    p = d / "fix_verify" / aid / fname
    if not p.exists():
        return "not found", 404
    return send_file(str(p), conditional=True)


@app.post("/api/changelog/<name>/<aid>/check")
def changelog_check(name, aid):
    """סימון פריט: נבדק ותקין / עדיין לא תוקן.

    הסימון הוא **פעולה אחת** על שני מקומות: מצב הבדיקה של הגרסה, וסטטוס
    ההערה עצמה. "עדיין לא תוקן" מחזיר את ההערה לתור של קלאוד עם הנימוק —
    כדי שלא ייווצר מצב שהראל סימן ✖ במסך אחד והתור במסך אחר עוד חושב
    שהכל נסגר."""
    d = wdir(name)
    b = request.get_json(force=True) or {}
    item_id = (b.get("item_id") or "").strip()
    state = (b.get("state") or "").strip()
    note = (b.get("note") or "").strip() or None
    if not item_id:
        return jsonify(error="חסר item_id"), 400
    rec = cl_mod.set_check(d, aid, item_id, state, note=note)
    ver = (art_mod.get_artifact(d, aid) or {}).get("version")
    comment = None
    if item_id.startswith("cmt_"):
        cid = item_id[4:]
        if state == "not_fixed":
            comment = tasks_mod.update_comment(
                d, cid, status="queued_for_claude",
                resolution=f"הראל בדק בגרסה {ver} — עדיין לא תוקן"
                           + (f": {note}" if note else ""))
        elif state == "ok":
            comment = tasks_mod.update_comment(
                d, cid, status="rejected",
                resolution=f"אושר ע\"י הראל בבדיקת גרסה {ver}"
                           + (f" — {note}" if note else ""))
    log_correction(d, {"type": "changelog_check", "artifact_id": aid,
                       "item_id": item_id, "state": state, "has_note": bool(note)})
    return jsonify(ok=True, check=rec, comment=comment)


@app.get("/api/artifacts/<name>/compare")
def artifacts_compare(name):
    """השוואה בין שתי גרסאות וידאו — מה באמת שונה ביניהן."""
    d = wdir(name)
    a = art_mod.get_artifact(d, request.args.get("a") or "")
    b = art_mod.get_artifact(d, request.args.get("b") or "")
    if not a or not b:
        raise ValueError("compare דורש שני מזהי גרסה קיימים (a,b)")
    def n(x, k):
        return x.get(k)
    return jsonify(ok=True, a=a["artifact_id"], b=b["artifact_id"], diff={
        "version": [n(a, "version"), n(b, "version")],
        "duration": [n(a, "duration"), n(b, "duration")],
        "duration_delta": (round((b.get("duration") or 0) - (a.get("duration") or 0), 2)
                           if a.get("duration") and b.get("duration") else None),
        "size_bytes": [n(a, "size_bytes"), n(b, "size_bytes")],
        "revision_id": [n(a, "revision_id"), n(b, "revision_id")],
        "same_revision": a.get("revision_id") == b.get("revision_id"),
        "edl_hash_same": a.get("edl_hash") == b.get("edl_hash"),
        "music": [n(a, "music"), n(b, "music")],
        "broll_items": [n(a, "broll_items"), n(b, "broll_items")],
        "qa_pass": [(a.get("qa") or {}).get("pass"), (b.get("qa") or {}).get("pass")],
        "identical_content": a.get("checksum") == b.get("checksum"),
    })


@app.get("/artifact-media/<name>/<aid>")
def artifact_media(name, aid):
    d = wdir(name)
    rec = art_mod.get_artifact(d, aid)
    if not rec or not Path(rec["path"]).is_file():
        return "not found", 404
    dl = request.args.get("download") == "1"
    return send_file(str(rec["path"]), conditional=True, as_attachment=dl,
                     download_name=f"{name}_v{rec.get('version')}.mp4")


@app.get("/media/<name>/<path:fname>")
def media(name, fname):
    d = wdir(name)
    if not re.fullmatch(r"[\w.\-+]+\.(mp4|png|jpg)", fname):
        return "forbidden", 403
    p = d / fname
    if not p.exists():
        return "not found", 404
    return send_file(str(p), conditional=True)

if __name__ == "__main__":
    print(f"\n🎬 אפליקציית הרוויו של R.E.L v7 — http://127.0.0.1:{PORT}\n")
    app.run(host="127.0.0.1", port=PORT, threaded=True)
