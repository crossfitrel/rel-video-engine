# -*- coding: utf-8 -*-
"""L43 — תפר מתחת למיטת בירול אינו תפר נראה.

מקור: פידבק אלי (פרטנר ממומן) 21.8.26 על 8 סרטוני הקמפיין ספט-נוב:
"כל שנייה שאתם לא מדברים ועושים תנועה סתם בלי דיבור. יש שתיקות יותר מדי
של מילי שנייה כזה, לא צריך."

מדידה על אותם 8 סרטונים: 0 פערים מעל 0.6ש · 29 פערים 0.25-0.48ש שמצטברים
ל-10.1ש אוויר מת · מתוכם 17 (6.1ש) מתחת למיטת הבירול ו-12 (4.1ש) חשופים.
"""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import edit_plan as EP


class TestBedCoveredSeams(unittest.TestCase):

    def test_constants_exist(self):
        # הסף החשוף לא זז — הקליברציה של הראל על שוט דיבור סטטי תקפה.
        self.assertEqual(EP.MIN_SAVING_PER_CUT, 0.50)
        self.assertLess(EP.MIN_SAVING_PER_CUT_COVERED, EP.MIN_SAVING_PER_CUT)
        self.assertGreater(EP.BED_EDGE_MARGIN, 0.0)

    def test_no_broll_plan_means_no_coverage(self):
        """מעבר ראשון: אין broll_plan.json ⇒ התנהגות זהה לחלוטין לקודם."""
        self.assertEqual(EP._bed_intervals(Path("/nonexistent-workdir-xyz")), [])
        self.assertFalse(EP._in_bed(5.0, []))
        self.assertFalse(EP._cut_seam_covered(5.0, [(0.0, 10.0)], []))

    def test_bed_edges_are_shrunk_by_margin(self):
        import json, tempfile, os
        d = tempfile.mkdtemp()
        json.dump({"plan": [{"start": 5.0, "end": 20.0}]},
                  open(os.path.join(d, "broll_plan.json"), "w"))
        bed = EP._bed_intervals(Path(d))
        self.assertEqual(len(bed), 1)
        s, e = bed[0]
        self.assertAlmostEqual(s, 5.0 + EP.BED_EDGE_MARGIN, places=6)
        self.assertAlmostEqual(e, 20.0 - EP.BED_EDGE_MARGIN, places=6)
        # קליפ קצר מפי-2 מהמרווח נזרק — אין בו אזור בטוח.
        json.dump({"plan": [{"start": 1.0, "end": 1.1}]},
                  open(os.path.join(d, "broll_plan.json"), "w"))
        self.assertEqual(EP._bed_intervals(Path(d)), [])

    def test_seam_inside_bed_is_covered(self):
        bed = [(5.0, 20.0)]
        # שני keeps: 0-8 ו-12-20 בציר המקור ⇒ התפר בציר התוצר ב-8.0, בתוך המיטה.
        keeps = [(0.0, 8.0), (12.0, 20.0)]
        self.assertTrue(EP._cut_seam_covered(8.0, keeps, bed))

    def test_seam_before_bed_is_exposed(self):
        bed = [(5.0, 20.0)]
        # keep יחיד של 3ש לפני החיתוך ⇒ תפר ב-3.0, לפני תחילת המיטה.
        keeps = [(0.0, 3.0), (4.0, 20.0)]
        self.assertFalse(EP._cut_seam_covered(3.0, keeps, bed))

    def test_covered_threshold_admits_the_eli_gap_band(self):
        """הפער האופייני שאלי סימן (0.25-0.48ש) עובר את הסף המוסתר."""
        for g in (0.25, 0.34, 0.48):
            self.assertGreaterEqual(g, EP.MIN_SAVING_PER_CUT_COVERED,
                                    f"פער {g}ש היה אמור להיחתך מתחת לבירול")
            self.assertLess(g, EP.MIN_SAVING_PER_CUT,
                            f"פער {g}ש חייב להישאר חסום כשהוא חשוף")


if __name__ == "__main__":
    unittest.main(verbosity=2)
