#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v9.33 (23.9.26) — מצב `scheduled` אמיתי: "תוזמן" ≠ "פורסם".
=====================================================================
הראל 24.7.26: "הושלם באפליקציה זה לא פורסם בפועל אלא תוזמן". עד v9.32 הסקיל
סימן `state_override:"published"` מיד אחרי תזמון, כי לא היה מצב אחר שמוציא
פרויקט מתור "מוכן לתזמון" (לקח 23.8.26: 12 פרויקטים שכבר תוזמנו נשארו
ב-ready_to_schedule ⇒ "תרוץ על כל מה שמוכן" היה מתזמן אותם שוב).

שלוש הוכחות (L97):
  א. set_meta מקבל scheduled, והוא ממוקם אחרי ready_to_schedule ולפני published.
  ב. פרויקט scheduled לא נאסף לתור התזמון — לא ב-derive_state, לא ב-/api/next
     ולא ב-/api/claude-brief (הבריף שהראל מדביק לקלאוד).
  ג. הזרקת כשל: בדיקת ה-API כאן נכשלת אם מחזירים את הסינון הישן ב-_next_action
     (`== "published"` בלבד) — נמדד ידנית ב-23.9.26, הפלט ב-CHANGELOG v9.33.
stdlib + flask (הבדיקות של ה-API מדולגות אם flask לא מותקן בפייתון הזה).
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
APP = HERE.parent / "review-app"
sys.path.insert(0, str(TOOLS))

from relvid import atomic_write_json                              # noqa: E402
from relvid import artifacts as art                               # noqa: E402
from relvid import registry as reg                                # noqa: E402
from relvid import tasks as tasks_mod                             # noqa: E402

NAME = "פרויקט-תוזמן"


def make_ready_to_schedule(root, name=NAME):
    """פרויקט במצב ready_to_schedule אמיתי: FINAL → artifact → אישור קאבר+קפשן."""
    d = Path(root) / name
    d.mkdir(parents=True, exist_ok=True)
    atomic_write_json(d / "edl.json", {
        "total_dur": 60.0, "kept_dur": 55.0,
        "keep_segments": [{"start": 0.0, "end": 55.0}],
        "review": {"cuts": [], "hook_move": None, "speed": 1.0}})
    atomic_write_json(d / "project_manifest.json",
                      {"project_id": "prj_sched", "name": name, "brand": "rel"})
    (d / "INPUT.mp4").write_bytes(b"IN" * 5000)
    (d / "FINAL.mp4").write_bytes(b"READY" * 5000)
    art.create_artifact(d)
    reg.set_schedule_approval(d, "approve", cover_path="thumbnail.png",
                              caption_text="קפשן מאושר")
    return d


class TestScheduledState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = make_ready_to_schedule(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_set_meta_accepts_scheduled(self):
        self.assertEqual(reg.derive_state(self.d), "ready_to_schedule")
        m = reg.set_meta(self.d, state_override="scheduled")
        self.assertEqual(m["state_override"], "scheduled")
        self.assertEqual(reg.derive_state(self.d), "scheduled")

    def test_a_order_ready_scheduled_published(self):
        s = reg.STATE_OVERRIDES
        self.assertLess(s.index("ready_to_schedule"), s.index("scheduled"))
        self.assertLess(s.index("scheduled"), s.index("published"))
        self.assertEqual(set(reg.SCHEDULE_CLOSED_STATES), {"scheduled", "published"})

    def test_a_unknown_state_still_rejected(self):
        with self.assertRaises(ValueError):
            reg.set_meta(self.d, state_override="scheduled_maybe")

    def test_b_scheduled_leaves_ready_to_schedule(self):
        """ה-override גובר גם על אישור תזמון תקף — אחרת תזמון כפול."""
        reg.set_meta(self.d, state_override="scheduled")
        self.assertNotEqual(reg.derive_state(self.d), "ready_to_schedule")
        self.assertEqual(reg.project_row(self.d)["state"], "scheduled")
        # ניקוי ה-override מחזיר לאוטומטי (האישור עדיין תקף)
        reg.set_meta(self.d, state_override=None)
        self.assertEqual(reg.derive_state(self.d), "ready_to_schedule")


@unittest.skipUnless(importlib.util.find_spec("flask"), "flask לא מותקן בפייתון הזה")
class TestScheduledStateAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["REL_WORK_ROOT"] = self.tmp
        self.d = make_ready_to_schedule(self.tmp)
        sys.path.insert(0, str(APP))
        sys.modules.pop("server", None)
        import server
        importlib.reload(server)
        self.server = server
        self.c = server.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("REL_WORK_ROOT", None)

    def _next_rows(self):
        r = self.c.get("/api/next")
        self.assertEqual(r.status_code, 200)
        return [x for x in r.get_json() if x.get("project") == NAME]

    def _brief(self):
        r = self.c.get("/api/claude-brief")
        self.assertEqual(r.status_code, 200)
        return r.get_json()["brief"]

    def test_control_ready_to_schedule_is_in_queue(self):
        """ביקורת חיובית: בלי סימון — הפרויקט כן בתור התזמון (אחרת הבדיקות ריקות)."""
        rows = self._next_rows()
        self.assertEqual([r["action"] for r in rows], ["לתזמן ב-Metricool"])
        self.assertIn(NAME, self._brief())

    def test_b_scheduled_not_collected_via_meta_api(self):
        r = self.c.post(f"/api/meta/{NAME}", json={"state_override": "scheduled"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["state"], "scheduled")
        self.assertEqual(self._next_rows(), [])
        self.assertNotIn(NAME, self._brief())

    def test_b_scheduled_with_queued_comment_stays_closed(self):
        """כמו published: הערה בתור על פוסט מתוזמן לא מחזירה אותו לתור/לבריף.
        (זו הבדיקה שנכשלת כשמסירים את scheduled מהסינון ב-_next_action.)"""
        reg.set_meta(self.d, state_override="scheduled")
        tasks_mod.add_comment(self.d, "עוד תיקון", queue=True)
        self.assertEqual(reg.derive_state(self.d), "scheduled")
        self.assertEqual(self._next_rows(), [])
        self.assertNotIn(NAME, self._brief())

    def test_b_published_parity(self):
        reg.set_meta(self.d, state_override="published")
        tasks_mod.add_comment(self.d, "עוד תיקון", queue=True)
        self.assertEqual(self._next_rows(), [])
        self.assertNotIn(NAME, self._brief())


if __name__ == "__main__":
    unittest.main()
