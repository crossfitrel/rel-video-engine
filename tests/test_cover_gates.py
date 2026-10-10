#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_cover_gates.py — בדיקות הזרקת-כשל לשערי הקאבר (v9.12, 2.8.26).

הכלל בפרויקט: כל שער חדש מקבל בדיקת הזרקת-כשל **וגם** בדיקה על הדיווח שלו.
שער שלא הוכח שהוא נכשל כשצריך — הוא שער שלא הוכח שהוא קיים.

השערים כאן נולדו מקאבר אחד שהראל פסל ב-2.8.26: פריים עם כתובית צרובה
("אז מה" מבצבץ מתחת לקופסה), שורה אחת במקום שתיים, ופריים עם עיניים
חצי-עצומות. שלושתם היו "כללים בסקיל" ולא שערים בקוד.
"""
import json
import os
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
THUMB = os.path.join(TOOLS, "thumbnail")
sys.path.insert(0, THUMB)
sys.path.insert(0, TOOLS)

import cover_guard                      # noqa: E402
import cover_make                       # noqa: E402
import thumbnail_build as tb            # noqa: E402

FONTS = os.path.join(THUMB, "fonts")


def _clean_frame(path, w=1080, h=1920):
    """פריים 'צילום' בלי כתובית — רעש בגוונים טבעיים."""
    rng = np.random.default_rng(7)
    a = rng.integers(40, 190, (h, w, 3), dtype=np.uint8)
    Image.fromarray(a).save(path)
    return path


def _captioned_frame(path, stroke=(31, 29, 135)):
    """אותו פריים + כתובית צרובה אמיתית: גליף לבן עם מתאר בצבע המותג,
    ב-y≈0.776 — בדיוק איפה ש-captions_overlay צורב אותה (marginv=430)."""
    _clean_frame(path)
    img = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(os.path.join(FONTS, "PloniBold.otf"), 120)
    d.text((540, 1490), "מה", font=f, fill=(255, 255, 255), anchor="ms",
           stroke_width=7, stroke_fill=stroke[::-1])   # PIL=RGB, cfg=BGR
    img.save(path)
    return path


class TestCaptionGuard(unittest.TestCase):
    """G-COVER1 — פריים עם כתובית צרובה לא הופך לקאבר."""

    def test_calibration_is_measured_not_guessed(self):
        p = os.path.join(THUMB, "cover-guard-calibration.json")
        self.assertTrue(os.path.exists(p), "אין קובץ כיול — הסף היה ניחוש")
        c = json.load(open(p, encoding="utf-8"))
        self.assertEqual(c["params"]["threshold_source"], "measured")
        ev = c["evidence"]
        self.assertTrue(ev["separation"], "אין הפרדה בין נקי לצרוב")
        self.assertLess(ev["false_block_rate"], 0.05)
        self.assertGreaterEqual(ev["projects_with_pairs"], 5)

    def test_clean_frame_passes(self):
        with tempfile.TemporaryDirectory() as td:
            p = _clean_frame(os.path.join(td, "clean.png"))
            self.assertTrue(cover_guard.caption_signal(_imread(p))["pass"])

    def test_captioned_frame_blocks(self):
        """הזרקת כשל: אותו פריים בדיוק, רק עם כתובית — חייב להיחסם."""
        with tempfile.TemporaryDirectory() as td:
            p = _captioned_frame(os.path.join(td, "cap.png"))
            rep = cover_guard.caption_signal(_imread(p))
            self.assertFalse(rep["pass"], f"כתובית צרובה לא נתפסה: {rep}")
            with self.assertRaises(SystemExit):
                cover_guard.assert_clean_frame(p)

    def test_personal_brand_stroke_also_caught(self):
        """המתאר הכחול של המותג האישי — זה בדיוק המקרה שנפל ב-2.8.26."""
        with tempfile.TemporaryDirectory() as td:
            p = _captioned_frame(os.path.join(td, "cap_blue.png"),
                                 stroke=(182, 119, 0))
            self.assertFalse(cover_guard.caption_signal(_imread(p))["pass"])

    def test_report_carries_threshold_and_source(self):
        """בדיקה על הדיווח: לא מספיק שהשער עובד — הוא חייב להסביר."""
        with tempfile.TemporaryDirectory() as td:
            p = _clean_frame(os.path.join(td, "c.png"))
            rep = cover_guard.caption_signal(_imread(p))
            self.assertIn("threshold", rep)
            self.assertEqual(rep["threshold_source"], "measured")
            self.assertIn("score", rep)


class TestTwoLines(unittest.TestCase):
    """G-COVER2 — קאבר הוא תמיד שתי שורות."""

    def test_missing_subtitle_blocks_in_builder(self):
        with tempfile.TemporaryDirectory() as td:
            p = _clean_frame(os.path.join(td, "c.png"))
            out = os.path.join(td, "o.png")
            for bad in (None, "", "   "):
                with self.assertRaises(SystemExit):
                    tb.build(p, "כותרת", bad, out)

    def test_missing_subtitle_blocks_in_entry_point(self):
        with tempfile.TemporaryDirectory() as td:
            p = _clean_frame(os.path.join(td, "c.png"))
            with self.assertRaises(SystemExit):
                cover_make.make(frame=p, title="כותרת", subtitle="",
                                out=os.path.join(td, "o.png"))

    def test_two_lines_builds_and_reports(self):
        with tempfile.TemporaryDirectory() as td:
            p = _clean_frame(os.path.join(td, "c.png"))
            out = os.path.join(td, "o.png")
            rep = cover_make.make(frame=p, title="מה זה באמת",
                                  subtitle="להיות בעל מועדון", out=out,
                                  brand="personal")
            self.assertTrue(os.path.exists(out))
            self.assertEqual(rep["lines"], 2)
            self.assertTrue(rep["sub_font"].startswith("Studentit"))
            self.assertEqual(rep["box_rgb"], [0, 119, 182])


class TestStudentit(unittest.TestCase):
    """G-COVER3 — התת-כותרת בפונט המותג, ובלי נפילה שקטה."""

    def test_sub_font_is_studentit(self):
        self.assertTrue(tb.SUB_FONT_IS_STUDENTIT)
        self.assertTrue(os.path.exists(tb.SUB_FONT))

    def test_no_builder_draws_subtitle_in_another_font(self):
        for name in ("thumbnail_build.py", "cover_build.py"):
            src = open(os.path.join(THUMB, name), encoding="utf-8").read()
            for line in src.splitlines():
                s = line.strip()
                var = s.split("=")[0].strip() if "=" in s else ""
                if var == "SUB_FONT" and "os.path.join" in s:
                    self.assertIn("Studentit", s, f"{name}: {s}")


class TestFrameQuality(unittest.TestCase):
    """G-COVER4 — מדווח ומדרג, לא פוסל."""

    def test_no_face_scores_zero_and_explains(self):
        with tempfile.TemporaryDirectory() as td:
            p = _clean_frame(os.path.join(td, "c.png"))
            q = cover_guard.frame_quality(_imread(p))
            self.assertEqual(q["score"], 0.0)
            self.assertIn("אין פנים", q["why"])

    def test_quality_is_reporting_not_blocking(self):
        """פריים גרוע לא מפיל בנייה — הוא רק מקבל ציון נמוך."""
        with tempfile.TemporaryDirectory() as td:
            p = _clean_frame(os.path.join(td, "c.png"))
            out = os.path.join(td, "o.png")
            cover_make.make(frame=p, title="כותרת", subtitle="תת כותרת", out=out)
            self.assertTrue(os.path.exists(out))


class TestRegistry(unittest.TestCase):
    """כל שער חדש רשום — אחרת הוא נופל בין הכיסאות."""

    def test_all_four_gates_registered_with_three_fields(self):
        import gate_registry as gr
        for g in ("G-COVER1_clean_source", "G-COVER2_two_lines",
                  "G-COVER3_studentit", "G-COVER4_frame_quality"):
            e = gr.GATES.get(f"cover_make:{g}")
            self.assertIsNotNone(e, f"{g} לא ברשומה")
            for field in ("protects", "cost_of_blocking", "fallback"):
                self.assertTrue(e[field], f"{g}: {field} ריק")

    def test_blocking_gates_have_measured_or_canon_threshold(self):
        import gate_registry as gr
        for g in ("G-COVER1_clean_source", "G-COVER2_two_lines", "G-COVER3_studentit"):
            e = gr.GATES[f"cover_make:{g}"]
            self.assertEqual(e["enforcement"], "blocking")
            self.assertIn(e["threshold_source"], ("measured", "canon", "physical"),
                          f"{g}: שער חוסם עם סף לא-מדוד")


def _imread(p):
    import cv2
    return cv2.imread(p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
