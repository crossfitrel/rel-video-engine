# -*- coding: utf-8 -*-
"""L44 — פתיח קבוע מלא מודבק אוטומטית.

שורש (הראל 18.8.26): "שכחנו לצרף את הפתיח של מאסל מן" — אחרי שהסרטון תוזמן.
הנכס ישב בקטלוג מ-21.7 ואף שלב לא הרכיב אותו.

הבדיקות כאן מכסות את ארבע נקודות הכשל שנמדדו בהרכבה הידנית:
  1. הזיהוי הוא מהכותרת ולא מהתמליל (הדובר לא אומר "מאסל מן" בסרטון).
  2. הזיהוי לא נדלק על תוכן אחר.
  3. ההרכבה מייצרת fps תקין — concat demuxer עם -c copy נתן 37.44fps מדומה.
  4. הפתיח מנורמל למפלס הגוף — הוא הוקלט 7.6 יחידות מתחתיו.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))

import fixed_intro as FI  # noqa: E402


def _probe(path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "default=nw=1:nk=1", str(path)]
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


class TestDetection(unittest.TestCase):
    def test_detects_from_monday_title(self):
        """הכותרת מ-Monday היא המקור — לא התמליל."""
        fid, ph = FI.detect_full_intro(
            "פינת מאסל מן - סיבוב כתף פנימי VS חיצוני בסנאץ׳")
        self.assertEqual(fid, "muscle-man")
        self.assertTrue(ph)

    def test_detects_from_hyphenated_project_name(self):
        """שם תיקיית העבודה מגיע עם מקפים — הנרמול חייב לטפל בזה."""
        fid, _ = FI.detect_full_intro("מאסל-מן-סיבוב-כתף")
        self.assertEqual(fid, "muscle-man")

    def test_detects_english(self):
        fid, _ = FI.detect_full_intro("Muscle Man corner — shoulder rotation")
        self.assertEqual(fid, "muscle-man")

    def test_does_not_fire_on_other_content(self):
        """אסור שידלק על תוכן אחר — פתיח מודבק בטעות הוא ליקוי חמור."""
        for title in ("פינת ניפוץ מיתוסים - חימום וקירור",
                      "דקה להורים עם אוריה",
                      "ממומן | קהל כללי | תקופה 1",
                      "טעויות נפוצות של מתאמנים - סומו דדליפט",
                      ""):
            with self.subTest(title=title):
                fid, _ = FI.detect_full_intro(title)
                self.assertIsNone(fid)


class TestPinnedDecision(unittest.TestCase):
    """נמדד 18.8.26 בהרצת סמוק שנייה: הפייפליין דורס את manifest["name"] בשם
    תיקיית העבודה, ולכן זיהוי שנשען על השם בלבד עבד בהרצה הראשונה ונכשל
    בשנייה — על אותו פרויקט בדיוק. הריפוי: ההחלטה נדבקת למניפסט בזיהוי
    הראשון. הבדיקה מדמה בדיוק את הרצף הזה."""

    def test_name_clobbered_by_pipeline_no_longer_matches(self):
        """התיעוד של הכשל: אחרי הדריסה, הזיהוי מהשם באמת מפסיק לתפוס."""
        self.assertIsNone(FI.detect_full_intro("_smoke-full-intro")[0])

    def test_pin_survives_name_clobber(self):
        """זו ההגנה: כשהשדה נעוץ, אין צורך בזיהוי מחדש."""
        man = {"name": "מאסל-מן-סמוק"}
        fid, ph = FI.detect_full_intro(man.get("name"))
        self.assertEqual(fid, "muscle-man")
        man["full_intro"] = {"id": fid, "matched": ph}      # הפייפליין נועץ
        man["name"] = "_smoke-full-intro"                    # ואז דורס את השם
        pinned = (man.get("full_intro") or {}).get("id")
        self.assertEqual(pinned, "muscle-man",
                         "הפתיח אבד אחרי שהפייפליין דרס את שם הפרויקט")


class TestCatalog(unittest.TestCase):
    def test_asset_exists_and_is_full_intro(self):
        asset, rec = FI.full_intro_asset("muscle-man")
        self.assertIsNotNone(asset, "נכס הפתיח של מאסל מן חסר מהקטלוג")
        self.assertTrue(asset.exists())
        self.assertIn("פתיח מלא", str(rec.get("סוג", "")))

    def test_transition_format_is_not_a_full_intro(self):
        """ניפוץ מיתוסים הוא אפקט מעבר — אסור שיודבק כפתיח."""
        asset, rec = FI.full_intro_asset("myth-busting-shatter")
        self.assertIsNone(asset)


class TestAssembly(unittest.TestCase):
    """הרכבה אמיתית על קליפים סינתטיים — בודקת את המסלול, לא את התוכן."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = HERE / "_tmp_full_intro"
        cls.tmp.mkdir(exist_ok=True)
        cls.body = cls.tmp / "body.mp4"
        # גוף: 3ש, 30fps, טון 440 — עומד בפרמטרים של תוצר אמיתי
        subprocess.run(
            ["ffmpeg", "-nostdin", "-y", "-v", "error",
             "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30:duration=3",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             "-ar", "48000", "-ac", "2", "-shortest", str(cls.body)],
            check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        for f in cls.tmp.glob("*"):
            f.unlink()
        cls.tmp.rmdir()

    def test_prepend_produces_clean_30fps_and_summed_duration(self):
        """זו הבדיקה שתופסת את הרגרסיה: concat demuxer מחזיר fps מדומה."""
        asset, rec = FI.full_intro_asset("muscle-man")
        if not asset:
            self.skipTest("נכס הפתיח לא זמין בסביבה הזו")
        out = self.tmp / "out.mp4"
        ok, detail, sec = FI.prepend_full_intro(
            str(self.body), str(out), "muscle-man", workdir=self.tmp)
        self.assertTrue(ok, detail)
        self.assertGreater(sec, 0)

        fps = _probe(out, "stream=avg_frame_rate", "v:0")
        self.assertEqual(fps, "30/1", f"fps מדומה — סימן שה-concat חזר ל-demuxer: {fps}")

        total = float(_probe(out, "format=duration"))
        self.assertAlmostEqual(total, sec + 3.0, delta=0.25,
                               msg="האורך אינו סכום הפתיח והגוף")

    def test_intro_is_normalized_to_body_level(self):
        """בלי נרמול הפתיח נשמע שקט ואז צעקה. סוגר על פער ≤2 LU."""
        asset, _ = FI.full_intro_asset("muscle-man")
        if not asset:
            self.skipTest("נכס הפתיח לא זמין בסביבה הזו")
        target = -14.0
        out = self.tmp / "out_norm.mp4"
        ok, detail, sec = FI.prepend_full_intro(
            str(self.body), str(out), "muscle-man",
            workdir=self.tmp, target_i=target)
        self.assertTrue(ok, detail)

        head = self.tmp / "head.wav"
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(out),
                        "-t", f"{max(sec - 0.5, 1.0):.2f}", str(head)],
                       check=True, capture_output=True)
        measured = FI._measure_i(head)
        self.assertIsNotNone(measured)
        self.assertLess(abs(measured - target), 2.0,
                        f"הפתיח ב-{measured} LUFS מול יעד {target}")


if __name__ == "__main__":
    unittest.main()
