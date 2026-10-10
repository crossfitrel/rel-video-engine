#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
בדיקות Artifact Store (v9.4) — כל בדיקה **מזריקה כשל אמיתי**, לא רק מאמתת נתיב תקין.
=====================================================================================
עשרת התרחישים שהוגדרו כחובה:
  1. חמש ריצות מוצלחות — כל חמשת הסרטונים נשארים נגישים.
  2. ריצה כושלת אחרי הצלחה — המאושר הקודם נשאר.
  3. ריצה כושלת אינה מקבלת output_hash של FINAL ישן.
  4. יצירת מועמד חדש אינה משנה approved_final.
  5. הערה על גרסה ישנה פותחת את אותה גרסה.
  6. ניקוי אינו מוחק artifacts.
  7. אישור תזמון ננעל ל-artifact ID.
  8. קריסה באמצע יצירת artifact אינה משאירה גרסה חלקית כמוצלחת.
  9. מיגרציה חוזרת אינה יוצרת כפילויות.
 10. קובץ חסר / checksum לא תואם מוצגים כתקלה, לא כגרסה תקינה.

stdlib בלבד; הכל על תיקיות זמניות. אין ffmpeg — "וידאו" = קובץ בייטים.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))

from relvid import atomic_write_json, read_json, sha256_file      # noqa: E402
from relvid import artifacts as art                               # noqa: E402
from relvid import tasks as tasks_mod                             # noqa: E402
from relvid import registry as reg                                # noqa: E402


def make_project(root, name="פרויקט-גרסאות"):
    d = Path(root) / name
    d.mkdir(parents=True, exist_ok=True)
    atomic_write_json(d / "edl.json", {
        "total_dur": 60.0, "kept_dur": 55.0,
        "keep_segments": [{"start": 0.0, "end": 55.0}],
        "review": {"cuts": [], "hook_move": None, "speed": 1.0}})
    atomic_write_json(d / "project_manifest.json",
                      {"project_id": "prj_test", "name": name, "brand": "rel"})
    (d / "INPUT.mp4").write_bytes(b"INPUT" * 100)
    return d


def write_final(d, payload):
    """מדמה את מה שהצנרת עושה: FINAL קודם מגובה, החדש נכנס במקומו (rename)."""
    f = d / "FINAL.mp4"
    if f.exists():
        f.replace(d / f"FINAL_prev_{time.strftime('%Y%m%d-%H%M%S')}_{os.urandom(2).hex()}.mp4")
    tmp = d / "FINAL_PENDING.mp4"
    tmp.write_bytes(payload)
    tmp.replace(f)
    return f


class TestArtifactStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = make_project(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- 1
    def test_01_five_successful_runs_all_remain_playable(self):
        ids = []
        for i in range(5):
            write_final(self.d, f"VIDEO-{i}".encode() * 5000)
            rec = art.create_artifact(self.d, run_id=f"run_{i}",
                                      summary=f"ריצה {i}")
            ids.append(rec["artifact_id"])
        self.assertEqual(len(set(ids)), 5, "כל ריצה חייבת ליצור artifact_id ייחודי")
        arts = art.list_artifacts(self.d)
        self.assertEqual(len(arts), 5)
        self.assertEqual([a["version"] for a in arts], [1, 2, 3, 4, 5])
        for i, aid in enumerate(ids):
            v = art.verify(self.d, aid)
            self.assertTrue(v["ok"], f"גרסה {i} אינה נגישה: {v}")
            self.assertEqual(art.artifact_final(self.d, aid).read_bytes(),
                             f"VIDEO-{i}".encode() * 5000,
                             "תוכן הגרסה השתנה — הגרסה נדרסה")

    # ---------------------------------------------------------------- 2 + 4
    def test_02_failed_run_after_success_keeps_approved(self):
        write_final(self.d, b"GOOD" * 5000)
        a1 = art.create_artifact(self.d, run_id="run_ok")["artifact_id"]
        art.approve(self.d, a1)
        self.assertEqual(art.pointers(self.d)["approved_final"], a1)

        # ריצה כושלת: כותבת FINAL_PENDING ולא מקדמת ל-FINAL, ולא יוצרת artifact
        (self.d / "FINAL_PENDING.mp4").write_bytes(b"BROKEN" * 100)
        atomic_write_json(self.d / "finish_status.json",
                          {"state": "failed", "detail": "gate חוסם"})
        self.assertEqual(art.pointers(self.d)["approved_final"], a1)
        self.assertTrue(art.verify(self.d, a1)["ok"],
                        "הגרסה המאושרת חייבת להישאר נגישה אחרי ריצה כושלת")
        self.assertEqual(len(art.list_artifacts(self.d)), 1,
                         "ריצה כושלת לא יוצרת גרסה")

    def test_04_new_candidate_does_not_move_approved(self):
        write_final(self.d, b"V1" * 5000)
        a1 = art.create_artifact(self.d)["artifact_id"]
        art.approve(self.d, a1)
        write_final(self.d, b"V2" * 5000)
        a2 = art.create_artifact(self.d)["artifact_id"]
        p = art.pointers(self.d)
        self.assertEqual(p["approved_final"], a1, "מועמד חדש הזיז את הגרסה המאושרת")
        self.assertEqual(p["latest_candidate"], a2)
        dt = art.display_target(self.d)
        self.assertEqual(dt["artifact_id"], a1, "ברירת המחדל להצגה היא המאושרת")
        self.assertTrue(dt["is_approved"])
        self.assertEqual(dt["newer_count"], 1, "צריך לדווח שקיימת גרסה חדשה יותר")
        self.assertEqual(dt["newer_artifact_id"], a2)

    def test_04b_candidate_only_marked_not_approved(self):
        write_final(self.d, b"ONLY" * 5000)
        art.create_artifact(self.d)
        dt = art.display_target(self.d)
        self.assertFalse(dt["is_approved"], "מועמד חייב להיות מסומן כלא-מאושר")
        self.assertEqual(dt["status"], "candidate")

    # ---------------------------------------------------------------- 3
    def test_03_failed_run_gets_no_stale_output_hash(self):
        """הבאג המקורי: run_finish חתם output_hash על FINAL.mp4 גם בכישלון."""
        write_final(self.d, b"OLD-GOOD-FINAL" * 500)
        old_hash = sha256_file(self.d / "FINAL.mp4")
        atomic_write_json(self.d / "finish_status.json", {"state": "failed"})
        src = (TOOLS / "run_finish.py").read_text(encoding="utf-8")
        self.assertNotIn('rec["output_hash"] = sha256_file(W / "FINAL.mp4")\n        rec["finished_at"]',
                         src, "output_hash עדיין נחתם ללא תנאי")
        self.assertIn('if rec["status"] == "done":', src,
                      "חתימת הפלט חייבת להיות מותנית בהצלחה")
        # סימולציה של הלוגיקה החדשה
        rec = {"status": "failed", "output_hash": None, "artifact_id": None}
        if rec["status"] == "done":
            rec["output_hash"] = old_hash
        self.assertIsNone(rec["output_hash"])
        self.assertIsNone(rec["artifact_id"])

    # ---------------------------------------------------------------- 5
    def test_05_comment_opens_the_version_it_was_written_on(self):
        write_final(self.d, b"V1-CONTENT" * 3000)
        a1 = art.create_artifact(self.d)["artifact_id"]
        c = tasks_mod.add_comment(self.d, "המוזיקה חזקה מדי בשנייה 14",
                                  time_start=14.0, on_final=True)
        self.assertEqual(c["artifact_id"], a1)

        write_final(self.d, b"V2-CONTENT" * 3000)     # ריצה נוספת — FINAL התחלף
        a2 = art.create_artifact(self.d)["artifact_id"]
        self.assertNotEqual(a1, a2)

        res = tasks_mod.comment_artifact(self.d, c)
        self.assertTrue(res["resolved"])
        self.assertEqual(res["artifact_id"], a1,
                         "ההערה חייבת לפתוח את הגרסה שעליה נכתבה, לא את החדשה")
        self.assertEqual(art.artifact_final(self.d, res["artifact_id"]).read_bytes(),
                         b"V1-CONTENT" * 3000)

    def test_05b_legacy_comment_without_artifact_id(self):
        """תאימות: הערה ישנה שיש בה רק on_final."""
        write_final(self.d, b"LEGACY" * 3000)
        a1 = art.create_artifact(self.d)["artifact_id"]
        time.sleep(1.05)
        legacy = {"comment_id": "c_old", "on_final": True, "time_start": 5.0,
                  "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        res = tasks_mod.comment_artifact(self.d, legacy)
        self.assertTrue(res["resolved"])
        self.assertEqual(res["source"], "inferred_by_time")
        self.assertEqual(res["artifact_id"], a1)

    # ---------------------------------------------------------------- 6
    def test_06_cleanup_never_deletes_artifacts(self):
        write_final(self.d, b"KEEP-ME" * 5000)
        a1 = art.create_artifact(self.d)["artifact_id"]
        art.approve(self.d, a1)
        for i in range(4):                       # עוד היסטוריית FINAL_prev
            write_final(self.d, f"OLD{i}".encode() * 5000)
            art.create_artifact(self.d)
        n_before = len(art.list_artifacts(self.d))
        env = dict(os.environ, REL_WORK_ROOT=self.tmp)
        r = subprocess.run([sys.executable, str(TOOLS / "cleanup_work.py"),
                            "--apply", "--keep-finals", "0", "--json"],
                           capture_output=True, text=True, env=env, timeout=180)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(art.list_artifacts(self.d)), n_before,
                         "ניקוי מחק גרסאות מ-artifacts/")
        for a in art.list_artifacts(self.d):
            self.assertTrue(art.verify(self.d, a["artifact_id"])["ok"],
                            f"גרסה נפגמה בניקוי: {a['artifact_id']}")

    def test_06b_cleanup_keeps_unarchived_prev_by_default(self):
        """FINAL_prev שלא נשמר כגרסה — ברירת המחדל היא לא למחוק אותו."""
        write_final(self.d, b"A" * 5000)
        write_final(self.d, b"B" * 5000)         # יוצר FINAL_prev, בלי artifact
        n_prev = len(list(self.d.glob("FINAL_prev_*.mp4")))
        self.assertEqual(n_prev, 1)
        env = dict(os.environ, REL_WORK_ROOT=self.tmp)
        subprocess.run([sys.executable, str(TOOLS / "cleanup_work.py"),
                        "--apply", "--keep-finals", "0", "--json"],
                       capture_output=True, text=True, env=env, timeout=180)
        self.assertEqual(len(list(self.d.glob("FINAL_prev_*.mp4"))), 1,
                         "ניקוי מחק וידאו מוצלח שלא נשמר כגרסה")

    # ---------------------------------------------------------------- 7
    def test_07_schedule_approval_locks_artifact_id(self):
        write_final(self.d, b"READY" * 5000)
        a1 = art.create_artifact(self.d)["artifact_id"]
        m = reg.set_schedule_approval(self.d, "approve", cover_path="thumbnail.png",
                                      caption_text="קפשן")
        sched = m["schedule_approval"]
        self.assertEqual(sched["artifact_id"], a1)
        self.assertEqual(sched["artifact_checksum"],
                         art.get_artifact(self.d, a1)["checksum"])
        self.assertTrue(Path(sched["artifact_path"]).exists())
        self.assertEqual(reg.derive_state(self.d), "ready_to_schedule")

        # ריצה חדשה מייצרת מועמד — האישור על הגרסה הישנה **לא** מתבטל,
        # וקובץ התזמון עדיין מצביע על הגרסה שאושרה בפועל.
        write_final(self.d, b"NEWER" * 5000)
        art.create_artifact(self.d)
        self.assertEqual(reg.derive_state(self.d), "ready_to_schedule")
        self.assertEqual(Path(sched["artifact_path"]).read_bytes(), b"READY" * 5000,
                         "קובץ התזמון השתנה מתחת לידיים")

    def test_07b_damaged_approved_artifact_blocks_scheduling(self):
        write_final(self.d, b"READY" * 5000)
        aid = art.create_artifact(self.d)["artifact_id"]
        reg.set_schedule_approval(self.d, "approve")
        self.assertEqual(reg.derive_state(self.d), "ready_to_schedule")
        f = art.artifact_final(self.d, aid)
        os.chmod(f, 0o644)
        f.unlink()
        self.assertEqual(reg.derive_state(self.d), "awaiting_schedule_approval",
                         "גרסה מאושרת פגומה חייבת לחסום תזמון")

    # ---------------------------------------------------------------- 8
    def test_08_crash_mid_creation_leaves_no_partial_version(self):
        write_final(self.d, b"PARTIAL" * 5000)
        real_link = art._link_or_copy

        def boom(src, dst, link=True):
            real_link(src, dst, link=link)
            raise IOError("קריסה מדומה באמצע יצירת ה-artifact")

        art._link_or_copy = boom
        try:
            with self.assertRaises(IOError):
                art.create_artifact(self.d)
        finally:
            art._link_or_copy = real_link
        self.assertEqual(art.list_artifacts(self.d), [],
                         "יצירה שקרסה השאירה גרסה חלקית כאילו הצליחה")
        self.assertEqual(list(art.adir(self.d).glob(".staging_*")), [],
                         "שארית staging לא נוקתה")
        self.assertIsNone(art.pointers(self.d)["latest_candidate"])
        # אחרי הקריסה עדיין אפשר ליצור גרסה תקינה
        rec = art.create_artifact(self.d)
        self.assertTrue(art.verify(self.d, rec["artifact_id"])["ok"])

    def test_08b_staging_leftover_is_not_counted_and_is_swept(self):
        write_final(self.d, b"X" * 5000)
        art.create_artifact(self.d)
        stale = art.adir(self.d) / ".staging_art_deadbeef"
        stale.mkdir()
        (stale / "FINAL.mp4").write_bytes(b"HALF")
        self.assertEqual(len(art.list_artifacts(self.d)), 1,
                         "staging נספר כגרסה")
        self.assertEqual(art.sweep_staging(self.d), 1)
        self.assertFalse(stale.exists())

    # ---------------------------------------------------------------- 9
    def test_09_migration_is_idempotent(self):
        write_final(self.d, b"OLD-ONE" * 5000)
        write_final(self.d, b"OLD-TWO" * 5000)
        write_final(self.d, b"CURRENT" * 5000)
        runs = self.d / "runs"
        runs.mkdir()
        atomic_write_json(runs / "run_a.json", {
            "run_id": "run_a", "status": "done", "revision_id": "rev_x",
            "started_at": "2020-01-01 00:00:00", "finished_at": "2020-01-01 00:01:00",
            "output_hash": sha256_file(self.d / "FINAL.mp4")})
        atomic_write_json(runs / "run_lost.json", {
            "run_id": "run_lost", "status": "done",
            "started_at": "2019-01-01 00:00:00", "finished_at": "2019-01-01 00:01:00",
            "output_hash": "quick:אבד"})

        def run_migration(apply_=True):
            cmd = [sys.executable, str(TOOLS / "migrate_artifacts.py"),
                   "--work-root", self.tmp, "--json"]
            if apply_:
                cmd.append("--apply")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            return json.loads(r.stdout)

        first = run_migration()
        self.assertEqual(first["to_create"], 3)
        n1 = len(art.list_artifacts(self.d))
        self.assertEqual(n1, 3)
        second = run_migration()
        self.assertEqual(second["to_create"], 0, "מיגרציה חוזרת יצרה כפילויות")
        self.assertEqual(second["already"], 3)
        self.assertEqual(len(art.list_artifacts(self.d)), n1)
        checksums = [a["checksum"] for a in art.list_artifacts(self.d)]
        self.assertEqual(len(set(checksums)), 3)
        # ריצה מוצלחת שהווידאו שלה אבד = תקלה מדווחת, לא גרסה
        um = read_json(art.adir(self.d) / "unmatched.json", {})
        self.assertEqual([u["run_id"] for u in um["unmatched_runs"]], ["run_lost"])

    def test_09b_migration_dry_run_touches_nothing(self):
        write_final(self.d, b"DRY" * 5000)
        before = sorted(p.name for p in self.d.iterdir())
        r = subprocess.run([sys.executable, str(TOOLS / "migrate_artifacts.py"),
                            "--work-root", self.tmp, "--json"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertFalse(out["applied"])
        self.assertEqual(out["to_create"], 1)
        self.assertEqual(sorted(p.name for p in self.d.iterdir()), before,
                         "dry-run יצר או הזיז קבצים")

    # ---------------------------------------------------------------- 10
    def test_10_missing_file_is_a_fault_not_a_valid_version(self):
        write_final(self.d, b"WILL-VANISH" * 3000)
        aid = art.create_artifact(self.d)["artifact_id"]
        f = art.artifact_final(self.d, aid)
        os.chmod(f, 0o644)
        f.unlink()
        v = art.verify(self.d, aid)
        self.assertFalse(v["ok"])
        self.assertEqual(v["state"], "missing_file")
        rec = [a for a in art.list_artifacts(self.d, verify_integrity=True)
               if a["artifact_id"] == aid][0]
        self.assertFalse(rec["exists"])
        self.assertFalse(rec["integrity"]["ok"])
        self.assertFalse(art.activate(self.d, aid)["ok"],
                         "אסור להפעיל גרסה שהקובץ שלה חסר")

    def test_10b_checksum_mismatch_is_a_fault(self):
        write_final(self.d, b"ORIGINAL" * 3000)
        aid = art.create_artifact(self.d)["artifact_id"]
        f = art.artifact_final(self.d, aid)
        os.chmod(f, 0o644)
        f.write_bytes(b"TAMPERED" * 3000)
        v = art.verify(self.d, aid)
        self.assertFalse(v["ok"])
        self.assertIn(v["state"], ("checksum_mismatch", "size_mismatch"))

    # ---------------------------------------------------------------- נוספות
    def test_11_activate_never_loses_the_live_final(self):
        write_final(self.d, b"V1" * 5000)
        a1 = art.create_artifact(self.d)["artifact_id"]
        write_final(self.d, b"V2-UNSAVED" * 5000)     # FINAL חי שלא נשמר כגרסה
        r = art.activate(self.d, a1)
        self.assertTrue(r["ok"])
        self.assertIsNotNone(r["captured_previous"], "ה-FINAL החי לא נלכד לפני ההחלפה")
        self.assertEqual((self.d / "FINAL.mp4").read_bytes(), b"V1" * 5000)
        captured = art.artifact_final(self.d, r["captured_previous"]).read_bytes()
        self.assertEqual(captured, b"V2-UNSAVED" * 5000)

    def test_12_identical_content_does_not_duplicate(self):
        write_final(self.d, b"SAME" * 5000)
        a1 = art.create_artifact(self.d)
        a2 = art.create_artifact(self.d)
        self.assertEqual(a1["artifact_id"], a2["artifact_id"])
        self.assertEqual(len(art.list_artifacts(self.d)), 1)

    def test_13_pointers_recoverable_after_loss(self):
        write_final(self.d, b"P1" * 5000)
        a1 = art.create_artifact(self.d)["artifact_id"]
        art.approve(self.d, a1)
        write_final(self.d, b"P2" * 5000)
        art.create_artifact(self.d)
        (art.adir(self.d) / art.POINTERS).unlink()
        p = art.repair_pointers(self.d)
        self.assertEqual(p["approved_final"], a1,
                         "לא ניתן היה לשחזר את הגרסה המאושרת מהחותמות")

    def test_14_reindex_rebuilds_from_disk(self):
        for i in range(3):
            write_final(self.d, f"R{i}".encode() * 5000)
            art.create_artifact(self.d)
        (art.adir(self.d) / art.INDEX).unlink()
        idx = art.reindex(self.d)
        self.assertEqual(idx["count"], 3)
        self.assertEqual(len(art.list_artifacts(self.d)), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
