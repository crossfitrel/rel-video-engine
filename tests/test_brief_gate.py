"""שער סתירה-לבריף + פאס הראייה (v9.7).

הרקע: הסרטון הבטיח "המקום כולו שלכם, בלי תור", והמצע הראה שיעור מלא.
הקליפ נקרא "חימום עם מוט מתאמנת" ותויג `יחיד` — התווית שיקרה והמערכת
האמינה לה. השער כאן מכריע לפי מה שרואים.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import broll_brief_gate as BG        # noqa: E402
import broll_vision_model as VM      # noqa: E402

OPEN_GYM_BRIEF = {
    "goal": "לגרום לצופה להשאיר פרטים כדי לתפוס מקום ב-Open Gym",
    "single_cta": "אם בא לכם את השעות השקטות לעצמכם — תשאירו לנו פרטים",
    "must_keep": ["המקום כולו שלכם — רחבה פתוחה וכל הציוד זמין, בלי תור"],
}
VALUE_BRIEF = {"goal": "להסביר איך לשפר סקוואט", "must_keep": ["טכניקה"]}


class TestClaims(unittest.TestCase):
    def test_solitude_claim_detected(self):
        c = BG.claims(OPEN_GYM_BRIEF)
        self.assertTrue(c["solitude"])
        self.assertTrue(c["solitude_evidence"])

    def test_no_claim_on_a_value_brief(self):
        """בריף בלי הבטחת-שקט לא אמור לחסום כלום — אחרת השער חוסם רוחבית."""
        self.assertFalse(BG.claims(VALUE_BRIEF)["solitude"])


class TestCheck(unittest.TestCase):
    def _v(self, **kw):
        base = {"people": 1, "crowding": "solo", "shot": "medium",
                "faces": True, "camera": "static"}
        base.update(kw)
        return base

    def test_full_class_blocked(self):
        ok, why = BG.check(self._v(people=10, crowding="full_class"),
                           BG.claims(OPEN_GYM_BRIEF), strict=True)
        self.assertFalse(ok)
        self.assertIn("סותר", why)

    def test_busy_blocked(self):
        ok, _ = BG.check(self._v(people=5, crowding="busy"),
                         BG.claims(OPEN_GYM_BRIEF), strict=True)
        self.assertFalse(ok)

    def test_solo_allowed(self):
        ok, _ = BG.check(self._v(), BG.claims(OPEN_GYM_BRIEF), strict=True)
        self.assertTrue(ok)

    def test_label_cannot_override_pixels(self):
        """הזרקת הכשל המרכזית: תווית 'יחיד' על שיעור מלא — נחסם בכל זאת."""
        clip = self._v(people=10, crowding="full_class")
        ok, _ = BG.check(clip, BG.claims(OPEN_GYM_BRIEF), strict=True)
        self.assertFalse(ok, "התווית גברה על מה שרואים — זה הבאג המקורי")

    def test_fails_closed_without_vision_in_conversion(self):
        """בלי ראיה, בהמרה — נחסם. אחרת די לא לסרוק קליפ כדי לעקוף את השער."""
        ok, why = BG.check(None, BG.claims(OPEN_GYM_BRIEF), strict=True)
        self.assertFalse(ok)
        self.assertIn("אין ראיה", why)

    def test_non_conversion_is_not_blocked_without_vision(self):
        ok, _ = BG.check(None, BG.claims(OPEN_GYM_BRIEF), strict=False)
        self.assertTrue(ok)


class TestVisionContract(unittest.TestCase):
    def test_rejects_internally_inconsistent_answer(self):
        """'שיעור מלא' עם אדם אחד הוא אות שמשקר — נדחה בשער החוזה."""
        refs = {"c001": "a.mp4"}
        bad = {"clips": [{"ref": "c001", "people": 1, "crowding": "full_class",
                          "shot": "wide", "faces": True, "camera": "static"}]}
        with self.assertRaises(ValueError):
            VM.validate(bad, refs)

    def test_rejects_unknown_ref(self):
        with self.assertRaises(ValueError):
            VM.validate({"clips": [{"ref": "zzz", "people": 1,
                                    "crowding": "solo", "shot": "medium",
                                    "faces": True, "camera": "static"}]},
                        {"c001": "a.mp4"})

    def test_rejects_partial_answer(self):
        with self.assertRaises(ValueError):
            VM.validate({"clips": []}, {"c001": "a.mp4"})

    def test_accepts_a_valid_answer(self):
        got = VM.validate(
            {"clips": [{"ref": "c001", "people": 11, "crowding": "full_class",
                        "shot": "wide", "faces": False, "camera": "static",
                        "note": "שיעור מלא"}]}, {"c001": "a.mp4"})
        self.assertEqual(got["c001"]["crowding"], "full_class")


class TestRealPool(unittest.TestCase):
    """על הבריכה בפועל — לא מוק."""

    @classmethod
    def setUpClass(cls):
        cfg = json.loads((ROOT / "tools" / "broll-catalog-config.json")
                         .read_text(encoding="utf-8"))
        cat = json.loads(Path(cfg["catalog_path"]).read_text(encoding="utf-8"))["items"]
        dis = {d.get("file") for d in cfg.get("disabled_files", [])}
        ver = set(cfg["verified_member_files"])
        cls.pool = [i for i in cat if i["file"] in ver and i["file"] not in dis]

    def test_every_pool_clip_has_vision_evidence(self):
        """בלי כיסוי מלא, השער נכשל-סגור וחוסם קליפים תקינים."""
        missing = []
        for it in self.pool:
            try:
                if VM.lookup(it["path"]) is None:
                    missing.append(it["file"])
            except OSError:
                missing.append(it["file"])
        self.assertEqual(missing, [], f"{len(missing)} קליפים בלי ראיה ויזואלית")

    def test_the_clip_harel_complained_about_is_blocked(self):
        """'חימום עם מוט מתאמנת' — הקליפ שהראל ראה בו שיעור עמוס."""
        hit = [i for i in self.pool if "חימום עם מוט" in i["file"]]
        if not hit:
            self.skipTest("הקליפ אינו בבריכה")
        v = VM.lookup(hit[0]["path"])
        ok, _ = BG.check(v, BG.claims(OPEN_GYM_BRIEF), strict=True)
        self.assertFalse(ok, "הקליפ שהראל התלונן עליו עבר את השער")

    def test_enough_clips_survive_for_a_bed(self):
        """שער שחוסם הכול אינו שער, הוא תקלה. מצע דורש ~10 קליפים."""
        cl = BG.claims(OPEN_GYM_BRIEF)
        ok = [i for i in self.pool
              if BG.check(VM.lookup(i["path"]), cl, strict=True)[0]]
        self.assertGreaterEqual(len(ok), 12, f"נשארו {len(ok)} — מעט מדי למצע")


if __name__ == "__main__":
    unittest.main()
