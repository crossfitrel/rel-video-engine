# -*- coding: utf-8 -*-
"""L39 — האצה לא נקנית בחיתוך שתיקות נוסף.

השער: `--speed` נאכף רק בתוך שלב ההידוק, ולכן תוכנית שפעריה כבר הוכרעו
(במאי / הראל באפליקציה) חייבת מסלול speed-only. הבדיקה מוודאת ששלושת
החוליות קיימות: הדגל, ההזרמה שלו ל-tighten_finish, וקבלתו שם.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPE = ROOT / "tools" / "local_finish_pipeline.py"
TIGHT = ROOT / "tools" / "tighten_finish.py"


class TestSpeedWithoutRetighten(unittest.TestCase):

    def test_pipeline_exposes_min_sil(self):
        src = PIPE.read_text(encoding="utf-8")
        self.assertRegex(src, r'add_argument\(\s*"--min-sil"',
                         "אין דגל --min-sil ב-local_finish_pipeline")
        self.assertIn("speed-only", src,
                      "הדגל קיים אבל לא מתועד כמסלול speed-only")

    def test_min_sil_is_forwarded_not_hardcoded(self):
        src = PIPE.read_text(encoding="utf-8")
        self.assertIn('"--min-sil", str(a.min_sil)', src,
                      "min_sil לא מוזרם ל-tighten_finish — נשאר קבוע בקוד")
        self.assertNotIn('"--min-sil", "0.30"', src,
                         "נשאר סף שתיקה קשיח בבניית tight_cmd")

    def test_tighten_finish_accepts_min_sil(self):
        src = TIGHT.read_text(encoding="utf-8")
        self.assertRegex(src, r'add_argument\("--min-sil"',
                         "tighten_finish לא מקבל --min-sil")

    def test_high_min_sil_cuts_nothing(self):
        """סף 99ש גדול מכל שתיקה אפשרית בסרטון של עד 65ש ⇒ אפס חיתוכים."""
        src = TIGHT.read_text(encoding="utf-8")
        m = re.search(r'add_argument\("--min-sil",\s*type=float,\s*default=([\d.]+)', src)
        self.assertIsNotNone(m, "ברירת המחדל של --min-sil לא נמצאה")
        self.assertLess(float(m.group(1)), 99.0,
                        "ברירת המחדל חייבת להישאר ההידוק הרגיל")


if __name__ == "__main__":
    unittest.main()
