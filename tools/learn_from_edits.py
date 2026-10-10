#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
learn_from_edits.py — Learning Engine v2 (v7): לולאת למידה בטוחה עם shadow mode.
===============================================================================
מה השתנה מ-v1 (ראה AUDIT-v7 §2):
  * reason_code יציב לכל אירוע — לא רק טקסט עברי; ה-classifier מכיר את *כל*
    סוגי האירועים שנרשמים בפועל (cut_disable, cut_widen, activate_cut, ...).
  * offsets לפי project_id (מהמניפסט) — רינון תיקייה לא שובר ולא סופר כפול.
  * הפרדה ל-cohorts: (content_type, brand).
  * שום שינוי ישיר ב-edl-policy.json: ‏--propose יוצר הצעה ב-shadow mode;
    ‏--evaluate מריץ אותה על ה-Golden Set; ‏--approve מחיל רק אחרי regression
    PASS ואישור הראל; ‏--rollback מחזיר בפקודה אחת.
  * כל גרסת policy נשמרת ב-tools/policy-history/.

שימוש:
  python3 learn_from_edits.py                 # סריקה ודוח בלבד
  python3 learn_from_edits.py --propose       # יצירת הצעת כיול (shadow)
  python3 learn_from_edits.py --evaluate tools/policy-proposals/proposal_X.json
  python3 learn_from_edits.py --approve  tools/policy-proposals/proposal_X.json
  python3 learn_from_edits.py --rollback      # חזרה לגרסת policy הקודמת
  (--apply הישן = alias ל---propose, לא מחיל יותר כלום ישירות)
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from relvid.paths import work_root as _work_root   # v8.6 (P0-11)
WORK = _work_root()
POLICY = HERE / "edl-policy.json"
STATE = HERE / "learn-state.json"
LESSONS = HERE / "edit-lessons.md"
PROPOSALS = HERE / "policy-proposals"
HISTORY = HERE / "policy-history"

from relvid import read_json, atomic_write_json, now_ts   # noqa: E402

MIN_EVIDENCE = 6          # v2: הועלה מ-3 (AUDIT: 3 היה רגיש מדי)
MIN_PROJECTS = 3          # ראיות מלפחות 3 פרויקטים שונים — בדיקה סטטיסטית פשוטה
BURST_GAP_SEC = 90        # v2.1: אירועים מאותו קוד/פרויקט בפער קטן מזה = ניסוי-ניסוי
                          # אחד (גרירה/קליק חוזר על אותו cut), נספרים כאירוע בודד —
                          # מונע ניפוח מלאכותי מטסטים/QA שרצו ישירות על תיקיית עבודה
                          # אמיתית במקום _work/.e2e/ (ראה CHANGELOG 23.7 — 393 אירועי
                          # adjust_cut תוך 90 שניות בפרויקט אחד התבררו כרעש טסט)


def _ts_epoch(ts):
    """'YYYY-MM-DD HH:MM:SS' → epoch שניות; None אם אין/לא תקין."""
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").timestamp()
    except Exception:
        return None

# (מפתח policy, צעד, תקרה) — כיוון תמיד ריכוך (המכונה חתכה יותר מדי)
CAL = {
    "RC_SILENCE_RESTORE": [("silence_in_sentence_keep", 0.03, 0.35),
                           ("silence_between_sentences_keep", 0.03, 0.30)],
    "RC_TAKE_RESTORE":    [("take_similarity", 0.03, 0.85)],
    "RC_FILLER_RESTORE":  [("filler_isolated_gap", 0.03, 0.30)],
}

REPORT_ONLY = {"RC_MANUAL_ADD", "RC_BOUNDARY_ADJUST", "RC_HOOK", "RC_TRANSCRIPT", "RC_VISUAL_HOOK",
               "RC_GATE_OVERRIDE", "RC_MUSIC", "RC_VIDEO_PATCH", "RC_MERGE",
               "RC_ACTIVATE", "RC_OTHER_RESTORE"}


def classify(act):
    """אירוע → reason_code יציב. מקבל reason_code מפורש אם קיים."""
    if act.get("reason_code"):
        return str(act["reason_code"])
    t = act.get("type", "")
    if t == "visual_hook":
        # v9.23 — פתיחה חזותית (תמונה בלבד). **לא** RC_HOOK: זה חיתוך/הזזה של
        # ההוק המדובר ב-EDL. שני הדברים חיים באותו יומן ואסור שיתערבבו.
        return "RC_VISUAL_HOOK"
    reason = (act.get("cut") or {}).get("reason", "") or act.get("reason", "") or ""
    def by_reason():
        if "שקט" in reason or "דד-אייר" in reason:
            return "RC_SILENCE_RESTORE"
        if "טייק" in reason or "כפילות" in reason:
            return "RC_TAKE_RESTORE"
        if "מילוי" in reason:
            return "RC_FILLER_RESTORE"
        return "RC_OTHER_RESTORE"
    # v8.6: הוספו שמות אירועים אמיתיים שנרשמו בפועל ונזרקו. שורש: "silence_restore"
    # (3 אירועים) קיים היה אך ורק ב-legacy_map של המיגרציה, לא ב-classifier — וזה
    # בדיוק סוג האירוע שמזין את RC_SILENCE_RESTORE, הקוד היחיד מבין שלושת הכיולים
    # שיש לו נתונים. נמדד: 484 מתוך 1,608 אירועים (30%) נזרקו לגמרי.
    if t in ("restore_cut", "cut_disable", "silence_restore", "toggle_cut",
             "cut_edit", "cut_correction", "manual_edl_edit",
             "qa_fix_edge_silence", "tail_trim", "delete_cut"):
        return by_reason()
    if t in ("add_cut",):
        return "RC_MANUAL_ADD"
    if t in ("adjust_cut", "cut_widen", "cut_shift"):
        return "RC_BOUNDARY_ADJUST"
    if t in ("cuts_merge",):
        return "RC_MERGE"
    if t in ("activate_cut",):
        return "RC_ACTIVATE"
    if t in ("hook_move", "hook_clear"):
        return "RC_HOOK"
    if t in ("transcript_fix",):
        return "RC_TRANSCRIPT"
    if t in ("gate_override",):
        return "RC_GATE_OVERRIDE"
    if t.startswith("music"):
        return "RC_MUSIC"
    if t.startswith("video_patch"):
        return "RC_VIDEO_PATCH"
    if t in ("delete_cut",):
        return "RC_MANUAL_ADD"        # מחיקת cut ידני = שינוי ידני, דיווח בלבד
    return None                        # note_sent / round_correct / comment_* / approve...


# ═══ v9.23 — אירועי פתיחה חזותית: למידה בצל בלבד ═══
HOOK_EVENTS = ("hook_suggested", "hook_selected", "hook_approved", "hook_disabled",
               "hook_replaced", "hook_strength_changed", "hook_rejected", "hook_render_failed")


def hook_event_id(ev):
    from relvid import sha256_json
    return sha256_json({k: ev.get(k) for k in ("project_id", "event", "plan_digest", "actor",
                                               "artifact_id", "run_id", "edit_token",
                                               "comparison_seen")})[7:31]


def summarize_hook_events(events):
    """דדופ לפי event_id (ניסיון חוזר נספר פעם אחת). "אשר הכל" בלי השוואה = ראיה
    חלשה, לא ניצחון. כשל רינדור אינו העדפה. בלי ML, בלי סף-מדגם מומצא."""
    seen, out = set(), {}
    for ev in events:
        if ev.get("type") != "visual_hook" or ev.get("event") not in HOOK_EVENTS:
            continue
        eid = ev.get("event_id") or hook_event_id(ev)
        if eid in seen:
            continue
        seen.add(eid)
        coh = f"{ev.get('content_type') or 'unknown'}/{ev.get('brand') or 'rel'}"
        c = out.setdefault(coh, {"suggested": 0, "explicit_positive": 0, "weak_positive": 0,
                                 "negative": 0, "render_failures": 0, "events": 0, "projects": set()})
        c["events"] += 1
        c["projects"].add(ev.get("project_id"))
        e = ev["event"]
        if e == "hook_suggested":
            c["suggested"] += 1
        elif e == "hook_selected" or (e == "hook_approved" and ev.get("comparison_seen")):
            c["explicit_positive"] += 1
        elif e == "hook_approved":
            c["weak_positive"] += 1
        elif e in ("hook_disabled", "hook_rejected", "hook_replaced"):
            c["negative"] += 1
        elif e == "hook_render_failed":
            c["render_failures"] += 1
    for c in out.values():
        c["projects"] = len(c["projects"])
        denom = c["explicit_positive"] + c["negative"]
        c["explicit_preference_ratio"] = round(c["explicit_positive"] / denom, 3) if denom else None
    return out


def collect_hook_events(work=None):
    root = Path(work) if work else WORK
    evs = []
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        cj = d / "corrections.jsonl"
        if not d.is_dir() or not cj.exists():
            continue
        for ln in cj.read_text(encoding="utf-8").splitlines():
            try:
                a = json.loads(ln)
            except Exception:
                continue
            if a.get("type") == "visual_hook":
                evs.append(a)
    return evs


def build_hook_proposal(summary, out_dir=None):
    """הצעה שקופה בצל: ספירות לקוהורט + יחס העדפה מפורשת. `suggested_change` תמיד
    None — שינוי מדיניות/קוהורט auto הוא החלטה של הראל, והמדיניות הקפואה בתוכניות
    שכבר אושרו אינה משתנה לעולם."""
    d = Path(out_dir) if out_dir else PROPOSALS
    d.mkdir(parents=True, exist_ok=True)
    pid = f"visual_hook_shadow_{time.strftime('%Y%m%d-%H%M%S')}"
    doc = {"proposal_id": pid, "created_at": now_ts(), "status": "shadow",
           "scope": "visual_hook_policy (future plans only)", "cohorts": summary,
           "suggested_change": None, "applies_to_frozen_plans": False}
    path = d / f"{pid}.json"
    atomic_write_json(path, doc)
    return path


def cohort_of(workdir):
    appr = read_json(Path(workdir) / "APPROVAL.json", {}) or {}
    m = read_json(Path(workdir) / "project_manifest.json", {}) or {}
    ct = appr.get("content_type") or m.get("content_type") or "unknown"
    br = appr.get("brand") or m.get("brand") or "rel"
    return f"{ct}/{br}"


def project_id_of(workdir):
    m = read_json(Path(workdir) / "project_manifest.json", {}) or {}
    return m.get("project_id") or f"name:{Path(workdir).name}"


def load_state():
    st = read_json(STATE, None)
    if st is None:
        return {"version": 2, "projects": {}, "counts": {}}
    if st.get("version") == 2:
        return st
    # --- מיגרציה מ-v1: offsets לפי שם תיקייה → project_id ---
    # תיקייה ששוננה (offset יתום) לא ניתנת לשיוך ודאי — כדי *למנוע ספירה כפולה*
    # כל פרויקט שלא נמצא ב-offsets הישנים מתחיל מ-offset=סוף הקובץ הנוכחי
    # (ההיסטוריה כבר נספרה או אבדה; לא סופרים אותה שוב). counts נשמרים.
    v2 = {"version": 2, "projects": {}, "counts": {},
          "migrated_from_v1": now_ts()}
    old_off = st.get("offsets", {})
    old_counts = st.get("counts", {})
    legacy_map = {"silence_restore": "RC_SILENCE_RESTORE",
                  "take_restore": "RC_TAKE_RESTORE",
                  "filler_restore": "RC_FILLER_RESTORE",
                  "manual_add": "RC_MANUAL_ADD",
                  "boundary_adjust": "RC_BOUNDARY_ADJUST",
                  "hook_move": "RC_HOOK", "transcript_fix": "RC_TRANSCRIPT",
                  "other_restore": "RC_OTHER_RESTORE"}
    lc = {}
    for k, v in old_counts.items():
        lc[legacy_map.get(k, k)] = v
    v2["counts"]["_legacy_v1"] = lc
    for d in WORK.iterdir():
        cj = d / "corrections.jsonl"
        if not d.is_dir() or not cj.exists():
            continue
        pid = project_id_of(d)
        n_lines = len(cj.read_text(encoding="utf-8").splitlines())
        off = old_off.get(d.name)
        v2["projects"][pid] = {"name": d.name,
                               "offset": off if off is not None else n_lines}
    return v2


def scan(state):
    """קורא אירועים חדשים מכל הפרויקטים; מעדכן offsets; מחזיר אירועים לפי cohort.
    v2.1: bursts (אותו קוד+פרויקט בפער <BURST_GAP_SEC) נספרים כאירוע יחיד —
    ראה BURST_GAP_SEC למעלה."""
    new_events = []
    last_ts = state.setdefault("last_event_ts", {})   # pid -> code -> epoch אחרון שנספר
    for d in sorted(WORK.iterdir()):
        cj = d / "corrections.jsonl"
        if not d.is_dir() or not cj.exists():
            continue
        pid = project_id_of(d)
        rec = state["projects"].get(pid, {"name": d.name, "offset": 0})
        rec["name"] = d.name
        lines = cj.read_text(encoding="utf-8").splitlines()
        coh = cohort_of(d)
        pid_last = last_ts.setdefault(pid, {})
        burst_absorbed = 0
        for ln in lines[rec["offset"]:]:
            try:
                act = json.loads(ln)
            except Exception:
                continue
            code = classify(act)
            if not code:
                continue
            epoch = _ts_epoch(act.get("ts"))
            prev = pid_last.get(code)
            if epoch is not None and prev is not None and (epoch - prev) < BURST_GAP_SEC:
                burst_absorbed += 1
                pid_last[code] = epoch   # שרשרת הבועה ממשיכה להתקדם
                continue                  # לא נספר כאירוע עצמאי — חלק מאותה בועה
            if epoch is not None:
                pid_last[code] = epoch
            new_events.append({"project_id": pid, "project": d.name,
                               "cohort": coh, "code": code,
                               "type": act.get("type"), "ts": act.get("ts")})
            cc = state["counts"].setdefault(coh, {})
            cc[code] = cc.get(code, 0) + 1
        if burst_absorbed:
            new_events.append({"project_id": pid, "project": d.name, "cohort": coh,
                               "code": "_burst_absorbed", "type": None, "ts": None,
                               "count": burst_absorbed})
        rec["offset"] = len(lines)
        state["projects"][pid] = rec
    return new_events


def total_counts(state, code):
    n, projects = 0, set()
    for coh, cc in state["counts"].items():
        if coh == "_legacy_v1":
            continue
        n += cc.get(code, 0)
    return n


def distinct_projects(events, code):
    return len({e["project_id"] for e in events if e["code"] == code})


def build_proposal(state, new_events):
    """הצעת כיול shadow — לא נוגעת ב-policy."""
    pol = read_json(POLICY, {})
    changes = []
    for code, rules in CAL.items():
        n_total = total_counts(state, code)
        n_new = sum(1 for e in new_events if e["code"] == code)
        n_proj = distinct_projects(new_events, code)
        if n_new == 0 or n_total < MIN_EVIDENCE or n_proj < MIN_PROJECTS:
            continue
        for pkey, step, limit in rules:
            old = pol.get(pkey)
            if old is None:
                continue
            new = round(min(limit, old + step), 3)
            if new != old:
                changes.append({"key": pkey, "from": old, "to": new,
                                "evidence": {"code": code, "total": n_total,
                                             "new": n_new, "projects": n_proj}})
    if not changes:
        return None
    PROPOSALS.mkdir(exist_ok=True)
    pid = f"proposal_{time.strftime('%Y%m%d-%H%M%S')}"
    prop = {"proposal_id": pid, "created_at": now_ts(),
            "policy_version_base": str(pol.get("version", "?")),
            "changes": changes, "status": "shadow",
            "evaluation": None, "approved_by": None}
    path = PROPOSALS / f"{pid}.json"
    atomic_write_json(path, prop)
    return path


def evaluate_proposal(path):
    """מריץ את ההצעה על ה-Golden Set (golden.py run --policy candidate)."""
    prop = read_json(path)
    pol = read_json(POLICY, {})
    cand = dict(pol)
    for ch in prop["changes"]:
        cand[ch["key"]] = ch["to"]
    cand_path = Path(path).with_suffix(".candidate-policy.json")
    atomic_write_json(cand_path, cand)
    # v8.6 (P0-7): --allow-missed 0 מפורש. שורש: ברירת המחדל ב-golden.py היא 3,
    # ו-evaluate_proposal לא דרס אותה — כלומר candidate מרכך היה יכול להעלים עד 3
    # cuts בכל case (עד 15 מתוך 38 = 39% מהחיתוכים) ולהרחיב את סבילות המשך
    # ל-1.5+3×1.0=4.5ש, ועדיין לקבל PASS שמאשר החלה על הפוליסי. שער אישור הלמידה
    # חייב להיות הדוק יותר מהרצה ידנית של הבדיקה, לא רחב פי שלוש.
    r = subprocess.run([sys.executable, str(HERE / "golden.py"), "run",
                        "--policy", str(cand_path), "--allow-missed", "0", "--json"],
                       capture_output=True, text=True, timeout=1800)
    try:
        result = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        result = {"ok": False, "error": r.stdout[-300:] + r.stderr[-300:]}
    prop["evaluation"] = {"at": now_ts(), "regression": "PASS" if result.get("ok") else "FAIL",
                          "detail": result}
    prop["status"] = "evaluated"
    atomic_write_json(path, prop)
    return prop


def approve_proposal(path):
    prop = read_json(path)
    ev = prop.get("evaluation") or {}
    if ev.get("regression") != "PASS":
        return {"ok": False, "error": "אין regression PASS — הרץ --evaluate קודם "
                                      "(policy לא מוחל בלי shadow evaluation)"}
    pol = read_json(POLICY, {})
    HISTORY.mkdir(exist_ok=True)
    ver = str(pol.get("version", "0"))
    backup = HISTORY / f"edl-policy_v{ver}_{time.strftime('%Y%m%d-%H%M%S')}.json"
    shutil.copy2(POLICY, backup)
    for ch in prop["changes"]:
        pol[ch["key"]] = ch["to"]
    try:
        major, minor = ver.split(".")
        pol["version"] = f"{major}.{int(minor) + 1}"
    except Exception:
        pol["version"] = ver + "+1"
    pol["_last_calibration"] = {"proposal": prop["proposal_id"], "at": now_ts()}
    atomic_write_json(POLICY, pol)
    prop["status"] = "applied"
    prop["applied_at"] = now_ts()
    prop["policy_backup"] = str(backup)
    atomic_write_json(path, prop)
    return {"ok": True, "new_version": pol["version"], "backup": str(backup),
            "changes": prop["changes"]}


def rollback():
    snaps = sorted(HISTORY.glob("edl-policy_*.json")) if HISTORY.exists() else []
    if not snaps:
        return {"ok": False, "error": "אין גרסת policy קודמת ב-policy-history"}
    last = snaps[-1]
    cur = read_json(POLICY, {})
    HISTORY.mkdir(exist_ok=True)
    undo = HISTORY / f"pre-rollback_{time.strftime('%Y%m%d-%H%M%S')}.json"
    atomic_write_json(undo, cur)
    shutil.copy2(last, POLICY)
    return {"ok": True, "restored": str(last), "undone_saved_to": str(undo)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--propose", action="store_true")
    ap.add_argument("--apply", action="store_true",
                    help="alias ל---propose (v2: אין החלה ישירה)")
    ap.add_argument("--evaluate")
    ap.add_argument("--approve")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--hook-report", action="store_true",
                    help="v9.23: סיכום אירועי פתיחה חזותית (קריאה בלבד; עם --propose — הצעה בצל)")
    a = ap.parse_args()

    if a.hook_report:
        summ = summarize_hook_events(collect_hook_events())
        print(json.dumps(summ, ensure_ascii=False, indent=1))
        if a.propose:
            print(f"הצעה בצל: {build_hook_proposal(summ)}")
        return

    if a.rollback:
        print(json.dumps(rollback(), ensure_ascii=False))
        return
    if a.evaluate:
        prop = evaluate_proposal(a.evaluate)
        print(json.dumps({"proposal": prop["proposal_id"],
                          "regression": prop["evaluation"]["regression"]},
                         ensure_ascii=False))
        return
    if a.approve:
        print(json.dumps(approve_proposal(a.approve), ensure_ascii=False))
        return

    state = load_state()
    new_events = scan(state)
    atomic_write_json(STATE, state)

    real_events = [e for e in new_events if e["code"] != "_burst_absorbed"]
    burst_events = [e for e in new_events if e["code"] == "_burst_absorbed"]

    lines = [f"## ריצת למידה v2 — {time.strftime('%d.%m.%Y %H:%M')}",
             f"- אירועים חדשים: {len(real_events)}"]
    by_code = {}
    for e in real_events:
        by_code.setdefault(e["code"], []).append(e)
    for code, evs in sorted(by_code.items()):
        lines.append(f"  - {code}: {len(evs)} חדשים "
                     f"({len({e['project_id'] for e in evs})} פרויקטים) · "
                     f"מצטבר {total_counts(state, code)}")
    if burst_events:
        n_absorbed = sum(e["count"] for e in burst_events)
        lines.append(f"- 🧹 {n_absorbed} אירועים נבלעו כ-bursts (קליקים/גרירות "
                     f"חוזרות תוך <{BURST_GAP_SEC}ש על אותו קוד+פרויקט) — "
                     f"נספרו כאירוע יחיד ולא ניפחו את הראיות")
    new_events = real_events

    prop_path = None
    if (a.propose or a.apply) and new_events:
        prop_path = build_proposal(state, new_events)
        if prop_path:
            lines.append(f"- **הצעת כיול נוצרה (shadow):** {prop_path.name}")
            lines.append("  → הרץ --evaluate ואז --approve (באישור הראל בלבד)")
        else:
            lines.append("- אין הצעת כיול (מתחת לסף הראיות: "
                         f"{MIN_EVIDENCE} אירועים מ-{MIN_PROJECTS}+ פרויקטים)")
    report = "\n".join(lines)
    with open(LESSONS, "a", encoding="utf-8") as f:
        f.write("\n" + report + "\n")
    print(report)
    print(json.dumps({"new_events": len(new_events),
                      "proposal": str(prop_path) if prop_path else None},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
