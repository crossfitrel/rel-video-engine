#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ops_dashboard.py — מדדי תפעול המערכת (v7, P3). איכות תפעולית — לא ציון ויראליות.
==============================================================================
לכל פרויקט + סיכום רוחבי: תיקונים לסרטון, restore rate, manual cut rate,
transcript corrections, QA failures, ריצות חוזרות, זמן מהרוויו הראשון לאישור,
הצלחה לפי גרסת policy/pipeline.

  python3 tools/ops_dashboard.py [--json]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from relvid.paths import work_root as _work_root   # v8.6 (P0-11)
WORK = _work_root()

from relvid import read_json                       # noqa: E402
from learn_from_edits import classify              # noqa: E402


def project_metrics(d):
    events = []
    cj = d / "corrections.jsonl"
    if cj.exists():
        for ln in cj.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(ln))
            except Exception:
                pass
    codes = Counter(c for c in (classify(e) for e in events) if c)
    runs = []
    if (d / "runs").exists():
        runs = [read_json(p) for p in sorted((d / "runs").glob("run_*.json"))]
    qa = read_json(d / "qa_report.json")
    appr = read_json(d / "APPROVAL.json", {}) or {}
    first_note = next((e.get("ts") for e in events
                       if e.get("type") in ("note_sent", "comment_added")), None)
    approved_at = appr.get("approved_at")
    n_cuts_restored = codes.get("RC_SILENCE_RESTORE", 0) + codes.get("RC_TAKE_RESTORE", 0) \
        + codes.get("RC_FILLER_RESTORE", 0) + codes.get("RC_OTHER_RESTORE", 0)
    return {
        "name": d.name,
        "corrections_total": len(events),
        "restored_cuts": n_cuts_restored,
        "manual_cuts": codes.get("RC_MANUAL_ADD", 0),
        "boundary_adjusts": codes.get("RC_BOUNDARY_ADJUST", 0),
        "transcript_fixes": codes.get("RC_TRANSCRIPT", 0),
        "gate_overrides": codes.get("RC_GATE_OVERRIDE", 0),
        "runs": len(runs),
        "failed_runs": sum(1 for r in runs if r and r.get("status") == "failed"),
        "qa": ("PASS" if qa.get("pass") else "FAIL") if qa else None,
        "first_note_at": first_note,
        "approved_at": approved_at,
        "pipeline_versions": sorted({r.get("pipeline_version") for r in runs if r}),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = []
    for d in sorted(WORK.iterdir()):
        if d.is_dir() and (d / "edl.json").exists():
            rows.append(project_metrics(d))
    agg = {
        "projects": len(rows),
        "avg_corrections": round(sum(r["corrections_total"] for r in rows) / max(1, len(rows)), 1),
        "total_restored_cuts": sum(r["restored_cuts"] for r in rows),
        "total_manual_cuts": sum(r["manual_cuts"] for r in rows),
        "total_transcript_fixes": sum(r["transcript_fixes"] for r in rows),
        "qa_fail": sum(1 for r in rows if r["qa"] == "FAIL"),
        "qa_pass": sum(1 for r in rows if r["qa"] == "PASS"),
        "rerun_projects": sum(1 for r in rows if r["runs"] > 1),
        "failed_runs": sum(r["failed_runs"] for r in rows),
    }
    out = {"summary": agg, "projects": rows}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        s = agg
        print(f"📊 {s['projects']} פרויקטים · ממוצע {s['avg_corrections']} תיקונים/סרטון")
        print(f"   ↩ {s['total_restored_cuts']} חיתוכים שוחזרו · ✂ {s['total_manual_cuts']} ידניים · "
              f"📝 {s['total_transcript_fixes']} תיקוני תמליל")
        print(f"   QA: {s['qa_pass']} PASS / {s['qa_fail']} FAIL · "
              f"{s['rerun_projects']} פרויקטים עם ריצות חוזרות · {s['failed_runs']} ריצות כושלות")
        worst = sorted(rows, key=lambda r: -r["corrections_total"])[:5]
        for r in worst:
            print(f"   · {r['name'][:30]}: {r['corrections_total']} תיקונים, QA={r['qa']}")


if __name__ == "__main__":
    main()
