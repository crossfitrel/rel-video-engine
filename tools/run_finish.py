#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_finish.py — עוטף הריצה של הגימור (v7): נעילה, run record, resume, FINAL בטוח.
================================================================================
זה מה שאפליקציית הרוויו מריצה בפועל ב"אשר והמשך לגימור" (דרך relvid.runner).
מריץ את local_finish_pipeline.py כתת-תהליך תחת נעילה; מעדכן runs/run_<id>.json
לפי finish_status.json; משחרר את הנעילה תמיד.

שימוש ידני:
  ~/.rel-whisper/bin/python tools/run_finish.py --workdir "_work/{שם}" \
      [--run-id run_x] [--content-type value] [--brand rel] [כל דגלי הפייפליין]
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from relvid import (new_id, now_ts, read_json, sha256_file, sha256_json)  # noqa: E402
from relvid import runner as runner_mod                                    # noqa: E402
from relvid import revisions as rev_mod                                    # noqa: E402
from relvid import artifacts as art_mod                                    # noqa: E402  (v9.4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--run-id", default=None)
    a, passthrough = ap.parse_known_args()

    W = Path(a.workdir).resolve()
    run_id = a.run_id or new_id("run")
    rec_path = runner_mod.run_record_path(W, run_id)
    rec = read_json(rec_path, {}) or {
        "run_id": run_id, "project": W.name, "status": "starting",
        "started_at": now_ts(), "revision_id": rev_mod.head(W),
        "pipeline_version": runner_mod.PIPELINE_VERSION_TAG,
        "edl_hash": sha256_json(read_json(W / "edl.json", {}) or {}),
        "input_hash": sha256_file(W / "INPUT.mp4"),
        "log": f"runs/{run_id}.log",
    }

    try:
        runner_mod.acquire_lock(W, run_id)
    except runner_mod.Locked as e:
        rec["status"] = "skipped_already_running"
        rec["detail"] = f"נעול ע\"י {e.meta}"
        rec["finished_at"] = now_ts()
        runner_mod.save_run(W, rec)
        print(f"⛔ ריצה פעילה כבר קיימת ({e.meta.get('run_id')}) — לא מפעיל שוב")
        sys.exit(0)

    exit_code = 1
    try:
        rec["status"] = "running"
        runner_mod.save_run(W, rec)
        pipeline = [sys.executable, str(HERE / "local_finish_pipeline.py"),
                    "--workdir", str(W)] + passthrough
        rec["command"] = pipeline
        runner_mod.save_run(W, rec)
        env = dict(os.environ, REL_RUN_ID=run_id)   # v7.7: לרשומת מקור ה-FINAL
        proc = subprocess.Popen(pipeline, cwd=str(HERE.parent), env=env)
        # מעקב שלב חי מ-finish_status.json
        while proc.poll() is None:
            time.sleep(2)
            fs = read_json(W / "finish_status.json", {}) or {}
            if fs.get("step") and fs.get("step") != rec.get("stage"):
                rec["stage"] = fs.get("step")
                runner_mod.save_run(W, rec)
        exit_code = proc.returncode
        fs = read_json(W / "finish_status.json", {}) or {}
        rec["stage"] = None
        rec["exit_code"] = exit_code
        rec["status"] = "done" if exit_code == 0 and fs.get("state") == "done" else "failed"
        rec["detail"] = fs.get("detail")
        # v7.8: זמני שלבים נשמרים ברשומת הריצה — כך ש-ops_dashboard יכול להראות
        # מגמה אמיתית ("איפה הזמן נשרף") ולא רק משך כולל.
        rec["stage_timings"] = fs.get("timings") or {}
        rec["total_secs"] = fs.get("total_secs")
        # v9.4 — שני תיקונים באותה נקודה:
        # (1) חתימת פלט **רק** בריצה מוצלחת. עד כה השורה רצה תמיד, ולכן ריצה
        #     שנכשלה קיבלה את ה-checksum של FINAL.mp4 *הישן* שנשאר על הדיסק
        #     (נמדד: 21 רשומות ריצה כושלות שנשאו חתימת FINAL תקין). זה גרם
        #     לרשומה כושלת להיראות כאילו הפיקה וידאו.
        # (2) ריצה מוצלחת יוצרת **artifact קבוע** — עותק/hardlink שאינו נדרס
        #     ע"י הריצה הבאה ואינו נמחק בניקוי. זו הזהות של הגרסה מכאן והלאה;
        #     FINAL.mp4 נשאר רק לתאימות עם קוד ישן.
        rec["output_hash"] = None
        rec["artifact_id"] = None
        if "--prepare-visual-hook-review" in passthrough:
            # v9.23 — הכנת תצוגת פתיחה אינה גימור: אסור לחתום output_hash או ליצור
            # artifact מ-FINAL ישן שנשאר בתיקייה (אותו באג של v9.4, מסלול חדש).
            rec["job_kind"] = "hook_preview"
        elif rec["status"] == "done":
            rec["output_hash"] = sha256_file(W / "FINAL.mp4")
            try:
                art = art_mod.create_artifact(
                    W, run_id=run_id, revision_id=rev_mod.head(W),
                    edl_hash=rec.get("edl_hash"), input_hash=rec.get("input_hash"),
                    pipeline_version=rec.get("pipeline_version"),
                    summary=f"ריצת גימור {run_id}", actor="pipeline")
                rec["artifact_id"] = art["artifact_id"]
                rec["artifact_version"] = art.get("version")
                rec["artifact_checksum"] = art.get("checksum")
                print(f"📦 גרסה {art.get('version')} נשמרה לצמיתות: {art['artifact_id']}")
            except Exception as e:
                # יצירת ה-artifact לא מפילה ריצה מוצלחת, אבל **כן** מסומנת
                # במפורש כדי שלא ייווצר הרושם שהגרסה נשמרה.
                rec["artifact_error"] = str(e)
                print(f"⚠️ שמירת הגרסה הקבועה נכשלה: {e}")
        art_mod.sweep_staging(W)
        rec["finished_at"] = now_ts()
        runner_mod.save_run(W, rec)
    except Exception as e:
        rec["status"] = "failed"
        rec["detail"] = f"run_finish exception: {e}"
        rec["finished_at"] = now_ts()
        runner_mod.save_run(W, rec)
        raise
    finally:
        runner_mod.release_lock(W)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
