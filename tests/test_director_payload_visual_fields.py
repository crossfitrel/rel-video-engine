#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L28 — כל מדד שהפרומפט של הבמאי מזכיר בשמו חייב לעבור את המסננת אליו.

השורש (17.8.26): director.plan_v1.4 מקדיש סעיף שלם ("התמונה, לא רק הקול")
לארבעת מדדי התמונה ומורה לבמאי לקבוע לפיהם את אורך הפאוזה — אבל
`_slim_candidate` לא כלל אותם ב-keep, ולכן הבמאי קיבל None בכל אחד מהם.
candidates.py חישב אותם נאמנה; המסננת זרקה אותם בשקט.

בדיקת יחידה על הדגלים לא הייתה תופסת את זה — הדגלים כלל לא היו קיימים
בצד המקבל. לכן הבדיקה כאן היא **חוזה בין הפרומפט למסננת**: היא קוראת את
קובץ הפרומפט בפועל ומוודאת שכל שם-שדה שמוזכר בו שורד את _slim_candidate.
"""
import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))

import edit_director as ED  # noqa: E402
from relvid import provider as PV  # noqa: E402

# המדדים החזותיים שהפרומפט מורה לשפוט לפיהם.
VISUAL_FIELDS = ("motion_around_norm", "pose_delta_at_024",
                 "pose_range_in_gap", "face_low_before", "face_low_after")


def _slim_features(**features):
    c = {"candidate_id": "gap_0001", "kind": "inter_word_gap",
         "t_start": 1.0, "t_end": 2.0, "features": dict(features)}
    return ED._slim_candidate(c)["features"]


class TestDirectorPayloadVisualFields(unittest.TestCase):

    def test_visual_fields_survive_the_slimmer(self):
        """הכשל שהיה: המספרים חושבו, ולא הגיעו למודל."""
        vals = {"motion_around_norm": 0.57, "pose_delta_at_024": 0.315,
                "pose_range_in_gap": 0.3705,
                "face_low_before": False, "face_low_after": True}
        out = _slim_features(gap_sec=2.59, **vals)
        for k, v in vals.items():
            self.assertIn(k, out, f"{k} נזרק ב-_slim_candidate — הבמאי עיוור אליו")
            self.assertEqual(out[k], v, f"{k} הגיע מעוות")

    def test_prompt_named_features_are_all_whitelisted(self):
        """חוזה: שדה שהפרומפט מזכיר בשמו — חייב לעבור את המסננת.

        זה מה שמונע רגרסיה עתידית: פרומפט v1.5 שיוסיף מדד חדש ולא יעדכן את
        keep ייכשל כאן, ולא אצל הראל על המסך.
        """
        prompt = PV.prompt_text("director")
        named = [f for f in VISUAL_FIELDS if f in prompt]
        self.assertTrue(named, "הפרומפט לא מזכיר אף מדד חזותי — האם שם השדה השתנה?")
        out = _slim_features(gap_sec=1.0, **{f: 0.5 for f in named})
        missing = [f for f in named if f not in out]
        self.assertFalse(
            missing,
            "הפרומפט מורה לשפוט לפי מדדים שלא עוברים ל-payload: %s" % missing)

    def test_unknown_features_are_still_dropped(self):
        """המסננת עדיין מסננת — הרחבנו אותה, לא ביטלנו אותה."""
        out = _slim_features(gap_sec=1.0, some_internal_debug_field=123)
        self.assertNotIn("some_internal_debug_field", out)


if __name__ == "__main__":
    unittest.main()
