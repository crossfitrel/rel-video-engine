#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
בדיקות ליבה v7 — רצות עם python3 -m unittest discover -s tests (stdlib בלבד).
כל בדיקה עובדת על תיקיות זמניות; לא נוגעת ב-_work האמיתי ולא במדיה.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

from relvid import sha256_json, read_json, atomic_write_json          # noqa: E402
from relvid.edl_utils import derive_keep, cuts_diff, edl_change_summary  # noqa: E402
from relvid import revisions as rev_mod                               # noqa: E402
from relvid import tasks as tasks_mod                                 # noqa: E402
from relvid import runner as runner_mod                               # noqa: E402


def make_workdir(tmp, name="פרויקט-בדיקה"):
    d = Path(tmp) / name
    d.mkdir(parents=True, exist_ok=True)
    edl = {
        "total_dur": 60.0, "kept_dur": 50.0,
        "keep_segments": [{"start": 0.0, "end": 10.0}, {"start": 20.0, "end": 60.0}],
        "auto_cuts": [{"start": 10.0, "end": 20.0, "reason": "שקט", "confidence": "high"}],
        "manual_review_cuts": [],
        "review": {"cuts": [{"start": 10.0, "end": 20.0, "reason": "שקט",
                             "confidence": "high", "source": "auto", "active": True}],
                   "hook_move": None},
    }
    atomic_write_json(d / "edl.json", edl)
    (d / "edited.txt").write_text("שלום לכולם זה סרטון בדיקה", encoding="utf-8")
    return d


class TestDeriveKeep(unittest.TestCase):
    def test_basic_cut(self):
        keep = derive_keep(60.0, [{"start": 10.0, "end": 20.0, "active": True}], None)
        self.assertEqual(keep, [{"start": 0.0, "end": 10.0}, {"start": 20.0, "end": 60.0}])

    def test_inactive_cut_ignored(self):
        keep = derive_keep(60.0, [{"start": 10.0, "end": 20.0, "active": False}], None)
        self.assertEqual(keep, [{"start": 0.0, "end": 60.0}])

    def test_overlapping_cuts_merge(self):
        keep = derive_keep(60.0, [{"start": 10.0, "end": 20.0, "active": True},
                                  {"start": 19.0, "end": 25.0, "active": True}], None)
        self.assertEqual(keep, [{"start": 0.0, "end": 10.0}, {"start": 25.0, "end": 60.0}])

    def test_hook_move_to_front(self):
        keep = derive_keep(60.0, [], {"start": 30.0, "end": 35.0})
        self.assertEqual(keep[0], {"start": 30.0, "end": 35.0})
        # שאר הזמן נשמר (לא נחתך) — סכום הזמן נשאר 60
        total = sum(k["end"] - k["start"] for k in keep)
        self.assertAlmostEqual(total, 60.0, places=2)

    def test_cut_at_edges(self):
        keep = derive_keep(60.0, [{"start": 0.0, "end": 5.0, "active": True},
                                  {"start": 55.0, "end": 60.0, "active": True}], None)
        self.assertEqual(keep, [{"start": 5.0, "end": 55.0}])


class TestCutsDiff(unittest.TestCase):
    def test_added_removed(self):
        a = [{"start": 1.0, "end": 2.0, "active": True}]
        b = [{"start": 5.0, "end": 6.0, "active": True}]
        d = cuts_diff(a, b)
        self.assertEqual(len(d["added"]), 1)
        self.assertEqual(len(d["removed"]), 1)

    def test_changed_boundary(self):
        a = [{"start": 1.0, "end": 2.0, "active": True}]
        b = [{"start": 1.0, "end": 2.5, "active": True}]
        d = cuts_diff(a, b)
        self.assertEqual(len(d["changed"]), 1)
        self.assertEqual(d["added"], [])


class TestRevisions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = make_workdir(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _edit_edl(self, kept):
        edl = read_json(self.d / "edl.json")
        edl["kept_dur"] = kept
        atomic_write_json(self.d / "edl.json", edl)

    def test_create_and_list(self):
        r1 = rev_mod.ensure_baseline(self.d)
        self.assertIsNotNone(r1)
        self._edit_edl(45.0)
        r2 = rev_mod.create_revision(self.d, "harel", "קיצור")
        lst = rev_mod.list_revisions(self.d)
        self.assertEqual(lst["head"], r2)
        self.assertEqual(len(lst["revisions"]), 2)
        self.assertEqual(lst["revisions"][1]["parent_revision_id"], r1)

    def test_undo_redo(self):
        rev_mod.ensure_baseline(self.d)
        self._edit_edl(45.0)
        r2 = rev_mod.create_revision(self.d, "harel", "קיצור")
        u = rev_mod.undo(self.d)
        self.assertTrue(u["ok"])
        self.assertEqual(read_json(self.d / "edl.json")["kept_dur"], 50.0)
        rd = rev_mod.redo(self.d)
        self.assertTrue(rd["ok"])
        self.assertEqual(rd["head"], r2)
        self.assertEqual(read_json(self.d / "edl.json")["kept_dur"], 45.0)

    def test_restore_nondestructive(self):
        r1 = rev_mod.ensure_baseline(self.d)
        self._edit_edl(45.0)
        rev_mod.create_revision(self.d, "harel", "קיצור")
        res = rev_mod.restore(self.d, r1)
        self.assertTrue(res["ok"])
        self.assertEqual(read_json(self.d / "edl.json")["kept_dur"], 50.0)
        # שחזור יוצר revision חדש — לא מוחק היסטוריה
        self.assertEqual(len(rev_mod.list_revisions(self.d)["revisions"]), 3)

    def test_approved_marked(self):
        rev_mod.ensure_baseline(self.d)
        rid = rev_mod.mark_approved(self.d)
        rev = rev_mod.get_revision(self.d, rid)
        self.assertTrue(rev["approved"])

    def test_compare(self):
        r1 = rev_mod.ensure_baseline(self.d)
        edl = read_json(self.d / "edl.json")
        edl["review"]["cuts"].append({"start": 30.0, "end": 32.0, "active": True,
                                      "reason": "ידני", "source": "harel"})
        edl["kept_dur"] = 48.0
        atomic_write_json(self.d / "edl.json", edl)
        r2 = rev_mod.create_revision(self.d, "harel", "הוספת חיתוך")
        c = rev_mod.compare(self.d, r1, r2)
        self.assertTrue(c["ok"])
        self.assertEqual(c["summary"]["cuts_added"], 1)
        self.assertAlmostEqual(c["summary"]["kept_dur_delta"], -2.0, places=1)


class TestTasks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = make_workdir(self.tmp)
        rev_mod.ensure_baseline(self.d)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_and_queue(self):
        c = tasks_mod.add_comment(self.d, "תחתוך את הפתיחה", time_start=3.2,
                                  category="edit", priority="high", queue=True)
        self.assertEqual(c["status"], "queued_for_claude")
        self.assertEqual(c["category"], "edit")
        self.assertIsNotNone(c["edl_hash"])

    def test_claim_resolve_flow(self):
        c = tasks_mod.add_comment(self.d, "תקן תמליל", category="transcript", queue=True)
        r = tasks_mod.claim(self.d, c["comment_id"])
        self.assertTrue(r["ok"])
        self.assertEqual(r["task"]["status"], "in_progress")
        # resolve בלי revision — נדחה
        bad = tasks_mod.resolve(self.d, c["comment_id"], None, "תוקן")
        self.assertFalse(bad["ok"])
        # עם revision אמיתי — עובר
        rid = rev_mod.create_revision(self.d, "claude", "תיקון לפי הערה")
        good = tasks_mod.resolve(self.d, c["comment_id"], rid, "תוקן")
        self.assertTrue(good["ok"])
        self.assertEqual(tasks_mod.get_comment(self.d, c["comment_id"])["status"], "resolved")

    def test_stale_task_blocked(self):
        c = tasks_mod.add_comment(self.d, "הערה על גרסה ישנה", queue=True)
        # משנים את ה-EDL אחרי יצירת ההערה
        edl = read_json(self.d / "edl.json")
        edl["kept_dur"] = 40.0
        atomic_write_json(self.d / "edl.json", edl)
        r = tasks_mod.claim(self.d, c["comment_id"])
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("stale"))
        # עם force — עובר
        r2 = tasks_mod.claim(self.d, c["comment_id"], force=True)
        self.assertTrue(r2["ok"])

    def test_fail_requeues(self):
        c = tasks_mod.add_comment(self.d, "משימה", queue=True)
        tasks_mod.claim(self.d, c["comment_id"])
        r = tasks_mod.fail(self.d, c["comment_id"], "חסר קובץ")
        self.assertTrue(r["ok"])
        self.assertEqual(tasks_mod.get_comment(self.d, c["comment_id"])["status"],
                         "queued_for_claude")


class TestLocks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = make_workdir(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_double_acquire_blocked(self):
        runner_mod.acquire_lock(self.d, "run_a")
        with self.assertRaises(runner_mod.Locked):
            runner_mod.acquire_lock(self.d, "run_b")
        runner_mod.release_lock(self.d)

    def test_stale_lock_recovered(self):
        # נעילה עם pid מת → acquire הבא מנקה ותופס
        ld = self.d / ".finish.lock"
        ld.mkdir()
        atomic_write_json(ld / "meta.json", {"pid": 99999999, "run_id": "run_dead"})
        runner_mod.acquire_lock(self.d, "run_new")   # לא אמור לזרוק
        meta = read_json(ld / "meta.json")
        self.assertEqual(meta["run_id"], "run_new")
        runner_mod.release_lock(self.d)

    def test_current_lock_live_and_release(self):
        runner_mod.acquire_lock(self.d, "run_x")
        live = runner_mod.current_lock(self.d)
        self.assertEqual(live["run_id"], "run_x")
        runner_mod.release_lock(self.d)
        self.assertIsNone(runner_mod.current_lock(self.d))

    def test_resume_flags(self):
        # ריצה כושלת קודמת + steps_done → דגלי resume
        edl = read_json(self.d / "edl.json")
        (self.d / "runs").mkdir()
        atomic_write_json(self.d / "runs" / "run_prev.json",
                          {"run_id": "run_prev", "status": "failed",
                           "edl_hash": sha256_json(edl)})
        atomic_write_json(self.d / "finish_status.json",
                          {"state": "failed",
                           "steps_done": [{"step": "recut"}, {"step": "whisper"}]})
        (self.d / "EXPORT.mp4").write_bytes(b"x")
        (self.d / "whisper_export.json").write_text("[]")
        flags, note = runner_mod.resume_flags(self.d)
        self.assertIn("--no-recut", flags)
        self.assertIn("--skip-whisper", flags)
        # אם ה-EDL השתנה — אין resume
        edl["kept_dur"] = 1.0
        atomic_write_json(self.d / "edl.json", edl)
        flags2, _ = runner_mod.resume_flags(self.d)
        self.assertEqual(flags2, [])


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        import relvid.registry as reg
        self.reg = reg
        self.old = (reg.WORK, reg.INDEX_DIR, reg.DB_PATH)
        reg.WORK = Path(self.tmp)
        reg.INDEX_DIR = Path(self.tmp) / ".index"
        reg.DB_PATH = reg.INDEX_DIR / "registry.db"
        self.d = make_workdir(self.tmp, "סרטון-אחד")
        make_workdir(self.tmp, "סרטון-שני")

    def tearDown(self):
        self.reg.WORK, self.reg.INDEX_DIR, self.reg.DB_PATH = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_manifest_stable_uuid(self):
        m1 = self.reg.ensure_manifest(self.d)
        m2 = self.reg.ensure_manifest(self.d)
        self.assertEqual(m1["project_id"], m2["project_id"])
        self.assertTrue(m1["project_id"].startswith("prj_"))

    def test_rebuild_after_db_delete(self):
        n = self.reg.rebuild()
        self.assertEqual(n, 2)
        os.remove(self.reg.DB_PATH)
        n2 = self.reg.rebuild()          # אינדקס נבנה מחדש מהדיסק
        self.assertEqual(n2, 2)
        rows = self.reg.list_projects(live=False)
        self.assertEqual(len(rows), 2)

    def test_find_by_id_and_name(self):
        m = self.reg.ensure_manifest(self.d)
        self.assertEqual(self.reg.find_project(m["project_id"]), self.d)
        self.assertEqual(self.reg.find_project("סרטון-אחד"), self.d)

    def test_state_derivation(self):
        self.assertEqual(self.reg.derive_state(self.d), "not_started")
        atomic_write_json(self.d / "APPROVAL.json", {"tag": "[APPROVE-PUBLISH]"})
        self.assertEqual(self.reg.derive_state(self.d), "approved")
        atomic_write_json(self.d / "finish_status.json", {"state": "failed", "detail": "x"})
        self.assertEqual(self.reg.derive_state(self.d), "failed")
        atomic_write_json(self.d / "finish_status.json", {"state": "done"})
        (self.d / "FINAL.mp4").write_bytes(b"x")
        self.assertEqual(self.reg.derive_state(self.d), "final")

    def test_open_comment_demotes_final(self):
        """v7.1: הערה חדשה על סרטון מוכן מחזירה אותו ל-in_review (הראל 23.7)."""
        atomic_write_json(self.d / "finish_status.json", {"state": "done"})
        (self.d / "FINAL.mp4").write_bytes(b"x")
        self.assertEqual(self.reg.derive_state(self.d), "final")
        c = tasks_mod.add_comment(self.d, "עוד תיקון בבקשה", queue=True)
        self.assertEqual(self.reg.derive_state(self.d), "in_review")
        # נסגרה ההערה → חוזר ל-final
        rid = rev_mod.create_revision(self.d, "claude", "תוקן")
        tasks_mod.resolve(self.d, c["comment_id"], rid, "תוקן")
        # resolved עדיין ממתין לבדיקת הראל — אבל לא בתור; ההגדרה: רק open/queued/in_progress מדמיטות
        self.assertEqual(self.reg.derive_state(self.d), "final")

    def test_manual_state_override(self):
        """v7.1: שליטה ידנית — override גובר, ניקוי מחזיר לאוטומטי."""
        self.reg.set_meta(self.d, state_override="in_review", dept="שיקום בתנועה")
        self.assertEqual(self.reg.derive_state(self.d), "in_review")
        m = self.reg.ensure_manifest(self.d)
        self.assertEqual(m["dept"], "שיקום בתנועה")
        self.reg.set_meta(self.d, state_override=None)
        self.assertEqual(self.reg.derive_state(self.d), "not_started")
        with self.assertRaises(ValueError):
            self.reg.set_meta(self.d, state_override="לא-קיים")


if __name__ == "__main__":
    unittest.main()
