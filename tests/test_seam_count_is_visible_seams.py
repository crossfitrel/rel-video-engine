#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L35 — תפר נראה הוא גבול בין קטעים, לא החלטת חיתוך.

השורש (17.8.26, "דקה-להורים"): הגלם צולם משפט-אחרי-משפט, ולכן התוכנית
מכילה עשרות החלטות חיתוך צמודות — פער שקוצץ, המשפט שאחריו שהוסר, הפער
שאחריו. שלושתן יוצאות כגוש אחד ומייצרות **קפיצה אחת** על המסך.

השער ספר החלטות: 48 חיתוכים ב-43.66ש = 1.099/ש, ודיווח כשל חמור — בזמן
שבפועל היו 12 קטעים, כלומר 11 תפרים = 0.252/ש. פי ארבעה.

זה חשוב במיוחד כי הטווח שאליו משווים (0.038-0.191) נמדד בספירת **תפרים
בווידאו** של סרטונים מאושרים, לא בספירת החלטות בתוכנית — כלומר המונה
והמכנה לא היו מאותו עולם.
"""
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import edit_plan as EP  # noqa: E402


class TestSeamCount(unittest.TestCase):

    def test_adjacent_cuts_are_one_seam(self):
        """שלוש החלטות צמודות = גוש אחד = תפר אחד."""
        cuts = [(10.0, 12.0, "gap_a"), (12.0, 15.0, "sent_b"), (15.0, 17.0, "gap_c")]
        keeps = EP.cuts_to_keeps(30.0, cuts)
        self.assertEqual(len(keeps), 2, "החיתוכים הצמודים לא התמזגו לקטע אחד")
        self.assertEqual(len(keeps) - 1, 1)
        self.assertLess(len(keeps) - 1, len(cuts),
                        "ספירת ההחלטות גדולה מספירת התפרים — זה בדיוק הפער שנמדד")

    def test_separated_cuts_are_separate_seams(self):
        cuts = [(10.0, 12.0, "gap_a"), (20.0, 22.0, "gap_b")]
        keeps = EP.cuts_to_keeps(30.0, cuts)
        self.assertEqual(len(keeps) - 1, 2)

    def test_head_and_tail_trims_are_not_seams(self):
        """קיצוץ ראש וזנב אינו קפיצה — הסרטון פשוט מתחיל ונגמר במקום אחר."""
        cuts = [(0.0, 5.0, "open_visual"), (25.0, 30.0, "edge_tail")]
        keeps = EP.cuts_to_keeps(30.0, cuts)
        self.assertEqual(len(keeps), 1)
        self.assertEqual(len(keeps) - 1, 0)

    def test_the_measured_range_is_still_the_reference(self):
        self.assertAlmostEqual(EP.CUTS_PER_SEC_HARD, 0.24, places=3)
        self.assertLess(EP.CUTS_PER_SEC_WARN, EP.CUTS_PER_SEC_HARD)


if __name__ == "__main__":
    unittest.main()
