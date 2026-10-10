#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""בדיקות Learning v2 + Golden compare (stdlib)."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

from learn_from_edits import classify, CAL, MIN_EVIDENCE, MIN_PROJECTS  # noqa: E402
import golden                                                            # noqa: E402


class TestClassifyV2(unittest.TestCase):
    def test_all_real_event_types_recognized(self):
        """כל סוגי האירועים שנרשמים בפועל (AUDIT §2) חייבים להיות מוכרים."""
        cases = {
            "restore_cut": "RC_SILENCE_RESTORE",   # עם reason שקט
            "cut_disable": "RC_SILENCE_RESTORE",
            "add_cut": "RC_MANUAL_ADD",
            "adjust_cut": "RC_BOUNDARY_ADJUST",
            "cut_widen": "RC_BOUNDARY_ADJUST",
            "cut_shift": "RC_BOUNDARY_ADJUST",
            "cuts_merge": "RC_MERGE",
            "activate_cut": "RC_ACTIVATE",
            "hook_move": "RC_HOOK",
            "transcript_fix": "RC_TRANSCRIPT",
            "gate_override": "RC_GATE_OVERRIDE",
            "music_redo": "RC_MUSIC",
            "video_patch_freeze_lookdown": "RC_VIDEO_PATCH",
        }
        for t, expected in cases.items():
            act = {"type": t, "cut": {"reason": "שקט פתיחה"}}
            self.assertEqual(classify(act), expected, f"type={t}")

    def test_reason_from_top_level(self):
        # v1 קרא רק את cut.reason — v2 חייב לקרוא גם reason עליון
        act = {"type": "restore_cut", "reason": "טייק כפול"}
        self.assertEqual(classify(act), "RC_TAKE_RESTORE")

    def test_explicit_reason_code_wins(self):
        act = {"type": "whatever", "reason_code": "RC_FILLER_RESTORE"}
        self.assertEqual(classify(act), "RC_FILLER_RESTORE")

    def test_noise_events_ignored(self):
        for t in ("note_sent", "round_correct", "comment_added", "approve",
                  "undo", "redo"):
            self.assertIsNone(classify({"type": t}), f"type={t}")

    def test_thresholds_raised(self):
        self.assertGreaterEqual(MIN_EVIDENCE, 6)
        self.assertGreaterEqual(MIN_PROJECTS, 3)

    def test_calibration_map_uses_codes(self):
        for k in CAL:
            self.assertTrue(k.startswith("RC_"))


class TestGoldenCompare(unittest.TestCase):
    def _edl(self, cuts, kept):
        return {"auto_cuts": [{"start": s, "end": e} for s, e in cuts],
                "kept_dur": kept}

    def test_identical_pass(self):
        e = self._edl([(1.0, 2.0), (5.0, 6.0)], 50.0)
        r = golden.compare(e, self._edl([(1.02, 2.01), (5.0, 6.0)], 50.1))
        self.assertTrue(r["pass"])

    def test_false_cut_fails(self):
        e = self._edl([(1.0, 2.0)], 50.0)
        r = golden.compare(e, self._edl([(1.0, 2.0), (30.0, 31.0)], 49.0))
        self.assertFalse(r["pass"])
        self.assertEqual(len(r["false_cuts"]), 1)

    def test_missed_cut_fails(self):
        e = self._edl([(1.0, 2.0), (5.0, 6.0)], 50.0)
        r = golden.compare(e, self._edl([(1.0, 2.0)], 51.0))
        self.assertFalse(r["pass"])
        self.assertEqual(len(r["missed_cuts"]), 1)

    def test_duration_drift_fails(self):
        e = self._edl([(1.0, 2.0)], 50.0)
        r = golden.compare(e, self._edl([(1.0, 2.0)], 55.0))
        self.assertFalse(r["pass"])


if __name__ == "__main__":
    unittest.main()
