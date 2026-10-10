#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L34 — עוגן יושב על המילים שהוא מצטט, לא בתחילת המשפט.

השורש (17.8.26, "בריאות-לקום-מכיסא"): החלון broll_003 נמשך 17.74 שניות
(5.07-22.81). הציטוט שהצדיק את בחירת הקליפ — "לחזק את... תבניות התנועה" —
נמצא בסוף המשפט. הקליפ נצרב על 5.07-8.57ש, כלומר מעל "הרבה אנשים לא שמים
לב לנקודה שבה הם מתחילים להיעזר בידיים": שוט של בק סקוואט על משפט שמדבר
על להישען על הידיים.

חוק ברזל 6 קובע "מה שנאמר קובע מה נראה", והציטוט היה **תנאי לקבלה** —
אבל לא השפיע על הזמן. זה תפס רק בצפייה בגיליון המגע, לא באף שער.
"""
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import broll_director as BD  # noqa: E402

LONG_TEXT = ("הרבה אנשים לא שמים לב לנקודה שבה הם מתחילים להיעזר בידיים כדי "
             "לקום מכיסא או פשוט במעקה כשהם עולים מדרגות כשבפועל הם לא באמת "
             "צריכים את זה אתם פשוט מחפשים דרך שיהיה לכם נוח אבל המטרה שלנו "
             "זה לחזק את כל תבניות התנועה שאנחנו מבצעים")

WIN = {"candidate_id": "broll_003", "out_start": 5.07, "out_end": 22.81,
       "dur_sec": 17.74, "text": LONG_TEXT, "is_stalled": False}


class TestAnchorLandsOnTheQuote(unittest.TestCase):

    def test_late_quote_moves_the_clip_late(self):
        start = BD.anchor_start(WIN, "לחזק את", length=3.5, hard_end=50.0)
        self.assertGreater(
            start, 15.0,
            "העוגן נשאר בתחילת החלון — הוא מאייר מילים אחרות מאלה שהצדיקו אותו")
        self.assertLessEqual(start + 3.5, WIN["out_end"] + 0.01)

    def test_early_quote_stays_early(self):
        start = BD.anchor_start(WIN, "הרבה אנשים", length=3.5, hard_end=50.0)
        self.assertLess(start, 7.0)
        self.assertGreaterEqual(start, WIN["out_start"] - 1e-9)

    def test_never_starts_before_the_window(self):
        start = BD.anchor_start(WIN, "הרבה", length=3.5, hard_end=50.0)
        self.assertGreaterEqual(start, WIN["out_start"] - 1e-9)

    def test_respects_the_cta_guard(self):
        start = BD.anchor_start(WIN, "לחזק את", length=3.5, hard_end=19.0)
        self.assertLessEqual(start + 3.5, 19.0 + 1e-9)

    def test_missing_quote_falls_back_to_window_start(self):
        self.assertEqual(BD.anchor_start(WIN, None, 3.5, 50.0), WIN["out_start"])
        self.assertEqual(BD.anchor_start(WIN, "מילה שאינה במשפט הזה בכלל", 3.5, 50.0),
                         WIN["out_start"])

    def test_short_window_keeps_the_old_behaviour(self):
        """בחלון קצר הקליפ מכסה ממילא כמעט את כל המשפט — ולכן לא מזיזים.

        זה לא ויתור אלא גבול מדוד: הזזה בחלון קצר לא משנה אילו מילים מכוסות,
        אבל כן מזיזה את הקליפ ביחס לשכנו ועלולה לפתוח חור-פנים שסוגר-ההבהוב
        אינו רשאי לסגור (הוא לעולם לא מזיז את הקליפ הבא).
        """
        w = {"out_start": 10.0, "out_end": 12.9, "dur_sec": 2.9,
             "text": "בלי ידיים זו בדיוק הסיבה למה אנחנו עושים סקוואט"}
        self.assertEqual(BD.anchor_start(w, "עושים סקוואט", 2.5, 50.0), 10.0)

    def test_the_seek_threshold_is_explicit(self):
        self.assertGreaterEqual(BD.MIN_WINDOW_FOR_QUOTE_SEEK, 2 * BD.MAX_CLIP_LEN)


if __name__ == "__main__":
    unittest.main()
