# -*- coding: utf-8 -*-
"""
בחירת מנוע רינדור ושעון-עצר על סגמנט (v9.5).

הליקוי: ‏v2 צורב בירול בתוך קידוד הסגמנט, וזה נתקע על מצע — 0% CPU, בלי
שגיאה. שני דברים נשברו כאן, ולשניהם יש בדיקה:
  1. **המדיניות** — מצע ≥3 בירולים חייב לעבור ל-v1, אוטומטית.
  2. **הדיווח** — `sh(timeout=1800)` המתין חצי שעה בשקט. חצי שעה של שתיקה
     אינה "עדיין רץ".
"""
import os, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


class TestSegmentTimeout(unittest.TestCase):
    def test_timeout_is_a_measured_budget_not_half_an_hour(self):
        from relvid import render as R
        self.assertLessEqual(R.SEGMENT_TIMEOUT, 600,
                             "תקציב הזמן לסגמנט חזר להיות שתיקה ארוכה")
        self.assertGreaterEqual(R.SEGMENT_TIMEOUT, 60,
                                "תקציב קצר מדי ייכשל על סגמנט איטי לגיטימי")

    def test_render_segment_uses_the_budget_and_not_a_literal(self):
        import inspect
        from relvid import render as R
        src = inspect.getsource(R.render_segment)
        self.assertIn("SEGMENT_TIMEOUT", src)
        self.assertNotIn("timeout=1800", src)

    def test_the_budget_is_overridable_for_debugging(self):
        self.assertIn("REL_SEGMENT_TIMEOUT",
                      Path(Path(__file__).resolve().parents[1] /
                           "tools/relvid/render.py").read_text(encoding="utf-8"))


class TestEngineChoice(unittest.TestCase):
    """v9.7: הבחירה נמדדת פר-סגמנט ולא נגזרת ממספר הבירולים.

    ‏31.7.26 נמדד שסגמנט עם 6 בירולים מרנדר ב-9.1ש בעוד אחר עם 3 (וגם עם
    אחד) נתקע — כלומר ספירת קליפים אינה מנבאת תקיעה, בשני הכיוונים.
    """

    def test_choice_is_not_derived_from_clip_count(self):
        src = (Path(__file__).resolve().parents[1] /
               "tools/local_finish_pipeline.py").read_text(encoding="utf-8")
        # השער הישן קרא את מספר הקליפים מהתוכנית והשווה לסף. אם הוא חוזר,
        # הבדיקה נופלת.
        self.assertNotIn("from relvid.render import MATTRESS_MIN_CLIPS", src)

    def test_stall_is_detected_by_measurement(self):
        from relvid.render import SEGMENT_SOFT_TIMEOUT
        self.assertGreater(SEGMENT_SOFT_TIMEOUT, 10)
        self.assertLess(SEGMENT_SOFT_TIMEOUT, 120)
        src = (Path(__file__).resolve().parents[1] /
               "tools/relvid/render.py").read_text(encoding="utf-8")
        # תקציב קצר מוחל רק על סגמנט עם overlay — סגמנט כבד בלי בירול
        # לא אמור להיפסל כ"תקוע".
        self.assertIn("SEGMENT_SOFT_TIMEOUT if seg.broll else SEGMENT_TIMEOUT", src)
        self.assertIn('"stalled": r.returncode == 124', src)

    def test_pipeline_downgrades_v2_to_v1_on_a_stall(self):
        """הזרקת הכשל: תקיעה מדווחת חייבת לצאת כ-v1, לא כשגיאת גימור."""
        src = (Path(__file__).resolve().parents[1] /
               "tools/local_finish_pipeline.py").read_text(encoding="utf-8")
        self.assertIn('rs.get("stalled")', src)
        self.assertIn('a.render_engine = "v1"', src)
        i = src.index('rs.get("stalled")')
        self.assertNotIn("fail(", src[i:i + 200],
                         "תקיעה ידועה אינה כישלון גימור — היא נפילה מסודרת")

    def test_stall_is_distinguished_from_a_real_ffmpeg_error(self):
        src = (Path(__file__).resolve().parents[1] /
               "tools/relvid/render.py").read_text(encoding="utf-8")
        self.assertIn('"stalled": True', src)
        self.assertIn("stalled_segments", src)

    def test_the_downgrade_is_reported_not_silent(self):
        """מדיניות שמשנה את המנוע בלי לומר זאת היא הפתעה, לא החלטה."""
        src = (Path(__file__).resolve().parents[1] /
               "tools/local_finish_pipeline.py").read_text(encoding="utf-8")
        i = src.index('a.render_engine = "v1"')
        self.assertIn("report.append", src[i:i + 400])


if __name__ == "__main__":
    unittest.main()
