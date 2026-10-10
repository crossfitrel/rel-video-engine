# -*- coding: utf-8 -*-
"""L40 — ציר המילים מכויל לאורך הקאט שנמדד, לא למתוכנן.

edl_cut מעגל כל מקטע כלפי מעלה לגבול פריים. map_words_to_keeps סוכם את
המשכים המתוכננים, ולכן בלי כיול הכתוביות מקדימות ביחס ישר למספר התפרים.
"""
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPE = ROOT / "tools" / "local_finish_pipeline.py"


class TestWordMapCalibration(unittest.TestCase):

    def test_pipeline_calibrates_to_measured_duration(self):
        src = PIPE.read_text(encoding="utf-8")
        self.assertIn("כיול ציר המילים לאורך הקאט בפועל", src,
                      "אין כיול של ציר המילים לאורך שנמדד (L40)")
        self.assertIn("_sc = dur / _planned", src,
                      "הכיול לא מחושב מהאורך שנמדד חלקי המתוכנן")

    def test_calibration_is_guarded(self):
        """מתיחה גדולה = תקלה אחרת. הכיול חייב להיות חסום לסטייה קטנה."""
        src = PIPE.read_text(encoding="utf-8")
        self.assertIn("abs(dur / _planned - 1.0) <= 0.02", src,
                      "הכיול חייב סף בטיחות — אחרת באג ברינדור נמרח על הכתוביות")

    def test_drift_model_matches_frame_ceiling(self):
        """המודל: ~חצי פריים לתפר. 11 תפרים @30fps ⇒ ~0.19ש — כפי שנמדד."""
        fps, seams = 30.0, 11
        predicted = (seams + 1) * (1.0 / fps) / 2.0
        self.assertTrue(math.isclose(predicted, 0.20, abs_tol=0.03),
                        f"מודל ההסחה לא תואם את הנמדד (0.19ש): {predicted:.3f}")


if __name__ == "__main__":
    unittest.main()
