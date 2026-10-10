# -*- coding: utf-8 -*-
"""L42 — שכבת הבירול לא מאריכה את הסרטון (זנב קפוא).

השורש (הראל 18.8.26): הקלט המשני נפתח בלי `-t`, ולכן היה ארוך מהחלון שלו.
`eof_action=repeat` החזיק את הפריים האחרון של הבסיס עד שכל הקלטים נגמרו —
נמדד 1.70ש של תמונה קפואה בסוף ממומן-ת2.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "tools" / "animation_overlay.py").read_text(encoding="utf-8")


class TestOverlayInputTrimmed(unittest.TestCase):

    def test_broll_does_not_extend_video(self):
        """כל קלט בירול חייב להיפתח עם -t באורך החלון."""
        self.assertIn('"-t"', SRC,
                      "קלט הבירול נפתח בלי -t — הוא יאריך את הפלט מעבר לווידאו")
        m = re.search(r'inputs \+= \[\s*"-t"[^\]]*"-i", f\]', SRC, re.S)
        self.assertIsNotNone(
            m, "-t חייב להופיע על אותו קלט של הבירול, מיד לפני -i")
        self.assertIn("float(e) - float(s)", m.group(0),
                      "אורך החיתוך חייב להיגזר מחלון הבירול (end-start)")

    def test_eof_repeat_still_there(self):
        """התיקון לא מבטל את הלקח הקודם — repeat נשאר, אחרת נחשפות הפנים בתפר."""
        self.assertIn("eof_action=repeat", SRC,
                      "eof_action=repeat הוסר — חשיפת פנים בתפר תחזור (v8.4)")

    def test_trim_has_safety_margin(self):
        """מרווח ביטחון קטן מעבר לחלון, כדי ש-repeat יהיה לו פריים להחזיק."""
        self.assertRegex(SRC, r"float\(s\)\)\s*/\s*spd\s*\+\s*0\.\d+",
                         "חסר מרווח ביטחון ב--t של קלט הבירול")


if __name__ == "__main__":
    unittest.main()
