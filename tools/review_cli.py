#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review_cli.py — Claude Bridge (v7): ממשק יציב לקלאוד מעל הפרויקטים, המשימות
והגרסאות. כל הפלטים JSON עם --json (ברירת מחדל: טקסט קריא).

פקודות:
  projects [--json]                         רשימת כל הפרויקטים (registry חי)
  tasks [--status queued_for_claude] [--project X] [--json]
  task TASK_ID [--json]                     הקשר מלא למשימה
  claim TASK_ID [--actor claude] [--force]
  resolve TASK_ID --revision REV --summary "..."
  fail TASK_ID --reason "..."
  project IDENT --context [--json]          תמונת פרויקט מלאה
  revisions IDENT [--json]
  compare IDENT REV_A REV_B [--json]
  restore IDENT REV [--actor claude]
  undo IDENT / redo IDENT
  new-revision IDENT --summary "..." [--actor claude]   (אחרי עריכת קבצים ידנית)
  sync IDENT [--dry-run] [--summary "..."]  מיישר את ציר האפליקציה למה שנחתך בפועל
  sync-status IDENT [--json]                מצב הסנכרון ציר ↔ FINAL
  sync-all [--dry-run] [--json]             סריקת דריפט בכל הפרויקטים (+תיקון)
  qa IDENT [--json]
  rebuild-index [--probe]
  comment IDENT --text "..." [--time T] [--category edit] [--priority high] [--queue]
  verify-fixes IDENT [--artifact ID] [--reel]      (v9.18) מדידות+גיליונות לכל תיקון
  fix-verdict IDENT ITEM_ID STATE [--artifact ID] [--evidence "..."] [--note "..."]
      STATE: verified | not_fixed | needs_eye — הפסיקה אחרי קריאת הגיליונות.
      not_fixed על cmt_* מחזיר את ההערה לתור אוטומטית.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from relvid import read_json, WORK                       # noqa: E402
from relvid import registry as reg                       # noqa: E402
from relvid import revisions as rev_mod                  # noqa: E402
from relvid import tasks as tasks_mod                    # noqa: E402
from relvid import runner as runner_mod                  # noqa: E402
from relvid import sync as sync_mod                      # noqa: E402


def out(data, as_json):
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=1))  # קריא ממילא


def need_project(ident):
    d = reg.find_project(ident)
    if not d:
        print(json.dumps({"error": f"פרויקט לא נמצא: {ident}"}, ensure_ascii=False))
        sys.exit(2)
    return d


def iter_all_comments():
    for d in reg.iter_workdirs():
        for c in tasks_mod.list_comments(d):
            yield d, c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--status", default=None)
    ap.add_argument("--project", default=None)
    ap.add_argument("--actor", default="claude")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--revision", default=None)
    ap.add_argument("--summary", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--context", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--text", default="")
    ap.add_argument("--time", type=float, default=None)
    ap.add_argument("--time-end", type=float, default=None)
    ap.add_argument("--category", default="general")
    ap.add_argument("--priority", default="normal")
    ap.add_argument("--queue", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--artifact", default=None)
    ap.add_argument("--reel", action="store_true")
    ap.add_argument("--evidence", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    cmd, args = a.cmd, a.args

    if cmd == "projects":
        out(reg.list_projects(live=True), a.json)

    elif cmd == "tasks":
        want = a.status or "queued_for_claude"
        rows = []
        for d, c in iter_all_comments():
            if a.project and d.name != a.project:
                continue
            if want != "all" and c["status"] != want:
                continue
            rows.append({"task_id": c["comment_id"], "project": d.name,
                         "status": c["status"], "category": c["category"],
                         "priority": c["priority"], "time_start": c["time_start"],
                         "text": c["text"], "created_at": c["created_at"],
                         "stale": tasks_mod.check_stale(d, c)})
        prio = {"blocking": 0, "high": 1, "normal": 2, "low": 3}
        rows.sort(key=lambda r: (prio.get(r["priority"], 9), r["created_at"]))
        out(rows, a.json)

    elif cmd == "task":
        tid = args[0]
        for d, c in iter_all_comments():
            if c["comment_id"] == tid:
                out(tasks_mod.task_context(d, c), a.json)
                return
        out({"error": f"משימה לא נמצאה: {tid}"}, a.json)
        sys.exit(2)

    elif cmd == "claim":
        tid = args[0]
        for d, c in iter_all_comments():
            if c["comment_id"] == tid:
                r = tasks_mod.claim(d, tid, actor=a.actor, force=a.force)
                out(r, a.json)
                sys.exit(0 if r.get("ok") else (4 if r.get("stale") else 1))
        out({"error": f"משימה לא נמצאה: {tid}"}, a.json)
        sys.exit(2)

    elif cmd == "resolve":
        tid = args[0]
        if not a.revision:
            out({"error": "resolve מחייב --revision (ה-revision שנוצר עם התיקון)"}, a.json)
            sys.exit(2)
        for d, c in iter_all_comments():
            if c["comment_id"] == tid:
                r = tasks_mod.resolve(d, tid, a.revision, a.summary, actor=a.actor)
                out(r, a.json)
                sys.exit(0 if r.get("ok") else 1)
        out({"error": f"משימה לא נמצאה: {tid}"}, a.json)
        sys.exit(2)

    elif cmd == "fail":
        tid = args[0]
        for d, c in iter_all_comments():
            if c["comment_id"] == tid:
                out(tasks_mod.fail(d, tid, a.reason, actor=a.actor), a.json)
                return
        out({"error": f"משימה לא נמצאה: {tid}"}, a.json)
        sys.exit(2)

    elif cmd == "project":
        d = need_project(args[0])
        row = reg.project_row(d)
        if a.context:
            row["revisions"] = rev_mod.list_revisions(d)
            row["comments"] = tasks_mod.list_comments(d)
            row["last_run"] = runner_mod.last_run(d)
            row["finish_status"] = read_json(d / "finish_status.json")
            row["gate_fail"] = read_json(d / "gate_fail.json")
        out(row, a.json)

    elif cmd == "revisions":
        d = need_project(args[0])
        out(rev_mod.list_revisions(d), a.json)

    elif cmd == "compare":
        d = need_project(args[0])
        out(rev_mod.compare(d, args[1], args[2]), a.json)

    elif cmd == "restore":
        d = need_project(args[0])
        out(rev_mod.restore(d, args[1], actor=a.actor), a.json)

    elif cmd == "undo":
        d = need_project(args[0])
        out(rev_mod.undo(d), a.json)

    elif cmd == "redo":
        d = need_project(args[0])
        out(rev_mod.redo(d), a.json)

    elif cmd == "new-revision":
        # v7.7: כל revision מעריכה מחוץ לאפליקציה מיישר קודם את הציר שהאפליקציה
        # מציגה (review.cuts) למה שבאמת נחתך (keep_segments) — אחרת הראל יפתח
        # את האפליקציה ויראה את הגרסה הקודמת.
        d = need_project(args[0])
        rev_mod.ensure_baseline(d)
        s = sync_mod.reconcile_edl(d, actor=a.actor, summary=a.summary or None)
        if s.get("changed"):
            out({"ok": True, "revision_id": s["revision_id"], "synced": True,
                 "drift": s["drift"], "sync": sync_mod.sync_status(d)}, a.json)
        else:
            rid = rev_mod.create_revision(d, actor=a.actor, summary=a.summary)
            out({"ok": True, "revision_id": rid, "synced": False,
                 "sync_note": s.get("reason"), "sync": sync_mod.sync_status(d)}, a.json)

    elif cmd == "sync":
        d = need_project(args[0])
        r = sync_mod.reconcile_edl(d, actor=a.actor, summary=a.summary or None,
                                   dry_run=a.dry_run)
        out(dict(r, sync=sync_mod.sync_status(d)), a.json)
        sys.exit(0 if r.get("ok") else 1)

    elif cmd == "sync-status":
        d = need_project(args[0])
        out(sync_mod.sync_status(d), a.json)

    elif cmd == "sync-all":
        rows = []
        for d in reg.iter_workdirs():
            st = sync_mod.sync_status(d)
            row = {"project": d.name, "state": st["state"],
                   "kept_dur": st.get("kept_dur"),
                   "final_expected_dur": st.get("final_expected_dur"),
                   "drift_delta": (st.get("drift") or {}).get("delta")}
            if st["state"] == "drift" and not a.dry_run:
                r = sync_mod.reconcile_edl(d, actor=a.actor,
                                           summary="סנכרון ציר (sync-all)")
                row["fixed"] = bool(r.get("changed"))
                row["revision_id"] = r.get("revision_id")
                row["detail"] = r.get("reason")
            rows.append(row)
        out(rows, a.json)

    elif cmd == "qa":
        d = need_project(args[0])
        out({"qa_report": read_json(d / "qa_report.json"),
             "cut_qa": read_json(d / "cut_qa_report.json"),
             "gate_fail": read_json(d / "gate_fail.json"),
             "canon": read_json(d / "canon_report.json")}, a.json)

    elif cmd == "rebuild-index":
        n = reg.rebuild(probe=a.probe)
        out({"ok": True, "indexed": n, "db": str(reg.DB_PATH)}, a.json)

    elif cmd == "verify-fixes":
        # v9.18 — "קלאוד בודק לפני הראל": מדידות + גיליונות-מגע לכל תיקון
        # בגרסה. אחרי הריצה: Read על כל sheet_*.jpg ואז fix-verdict פר-פריט.
        d = need_project(args[0])
        import fix_verify as fv
        out(fv.run(d, artifact_id=a.artifact, reel=a.reel), a.json)

    elif cmd == "fix-verdict":
        # פסיקת קלאוד על תיקון בודד. not_fixed מחזיר את ההערה לתור באותה
        # פעולה — כדי שלא יהיה פער בין "מה קלאוד יודע" ל"מה בתור".
        d = need_project(args[0])
        item_id, state = args[1], args[2]
        from relvid import artifacts as art_cli_mod
        from relvid import changelog as cl_cli_mod
        aid = a.artifact
        if not aid:
            arts = art_cli_mod.list_artifacts(d)
            if not arts:
                out({"error": "אין גרסאות וידאו בפרויקט"}, a.json)
                sys.exit(2)
            aid = arts[-1]["artifact_id"]
        rec = cl_cli_mod.set_claude_verdict(d, aid, item_id, state,
                                            evidence=a.evidence or None,
                                            note=a.note or None)
        requeued = None
        if state == "not_fixed" and item_id.startswith("cmt_"):
            ver = (art_cli_mod.get_artifact(d, aid) or {}).get("version")
            requeued = tasks_mod.update_comment(
                d, item_id[4:], status="queued_for_claude",
                resolution=f"קלאוד אימת בגרסה {ver} — התיקון לא נכנס"
                           + (f": {a.note}" if a.note else ""))
        out({"ok": True, "artifact_id": aid, "item_id": item_id,
             "claude": rec, "requeued": bool(requeued)}, a.json)

    elif cmd == "comment":
        d = need_project(args[0])
        c = tasks_mod.add_comment(d, a.text, time_start=a.time, time_end=a.time_end,
                                  category=a.category, priority=a.priority,
                                  actor=a.actor, queue=a.queue)
        out(c, a.json)

    else:
        out({"error": f"פקודה לא מוכרת: {cmd}"}, a.json)
        sys.exit(2)


if __name__ == "__main__":
    main()
