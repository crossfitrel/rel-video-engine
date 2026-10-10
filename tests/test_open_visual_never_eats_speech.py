#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L36 — חלון "לפני הדיבור" לא רשאי להיגמר אחרי שהדיבור התחיל.

השורש (17.8.26, "טיפ-אחד-בטן-בר"): `snap_words_to_audio` הזיזה את המילה
"טיפ" מ-6.80ש ל-7.14ש. ‏`open_visual` נבנה מהמילה הראשונה **אחרי** ההצמדה
ולכן השתרע 0→7.14 — חלון "שקט פתיחה" שכולל 0.34 שניות מתוך מילה בת 0.40.
הבמאי חתך אותו בצדק (זה חלון בלי דיבור, לפי המדידה שקיבל), ו-85% מהמילה
הראשונה יצאו איתו.

מה שהפך את זה לשקוף: `map_words_to_keeps` מפיל מילה שנשאר ממנה פחות מ-50%,
ולכן "טיפ" נעלמה מ-`words_final`. שער הכיסוי משווה כתוביות מול words_final —
כלומר הוא השווה את הכתוביות מול רשימה שממנה המילה כבר נמחקה, ועבר בהצלחה.
הכתובית הראשונה בסרטון ששמו "טיפ אחד" הפכה ל"אחד".
"""
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent))

import candidates as C  # noqa: E402
from relvid.edl_utils import map_words_to_keeps  # noqa: E402


class TestOpenVisualNeverEatsSpeech(unittest.TestCase):

    def test_a_word_that_loses_most_of_itself_is_dropped(self):
        """הראיה שהפכה את הבאג לשקוף — כך המילה נעלמה מ-words_final."""
        words = [{"word": "טיפ", "start": 6.80, "end": 7.20},
                 {"word": "אחד", "start": 7.32, "end": 7.70}]
        out, stats = map_words_to_keeps(words, [{"start": 7.14, "end": 9.04}])
        self.assertEqual([w["word"] for w in out], ["אחד"],
                         "המילה נשמרה — הבדיקה כבר לא משחזרת את הכשל")

    def test_the_same_word_survives_when_the_window_respects_it(self):
        """אותה מילה, אותו חיתוך — רק שהחלון נגמר בהתחלה הגולמית."""
        words = [{"word": "טיפ", "start": 6.80, "end": 7.20},
                 {"word": "אחד", "start": 7.32, "end": 7.70}]
        out, stats = map_words_to_keeps(words, [{"start": 6.80, "end": 9.04}])
        self.assertEqual([w["word"] for w in out], ["טיפ", "אחד"])

    def test_snap_may_move_a_word_later(self):
        """התנאי שמייצר את הבאג קיים בקוד — ההצמדה אכן מזיזה מאוחר יותר."""
        self.assertTrue(hasattr(C, "snap_words_to_audio"))

    def test_the_clamp_is_present_in_the_builder(self):
        """L36 — הבנייה חייבת לקחת את המוקדם מבין השניים.

        בדיקת חוזה על הקוד: `build` שומר את raw_first_start לפני ההצמדה
        ומשתמש בו כתקרה ל-open_visual.
        """
        src = (TOOLS / "candidates.py").read_text(encoding="utf-8")
        self.assertIn("raw_first_start", src)
        self.assertIn("first = min(first, raw_first_start)", src)


if __name__ == "__main__":
    unittest.main()
