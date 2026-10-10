"""שער איזון מגדרי בבריכת הבירול (v9.7) + הפרדת people מ-audience.

הרקע: הראל, 31.7.26 — "יש בירולים רק של נשים? מה עם קצת גברים."
נמדד אז: 34/34 נשים. הסיבה לא הייתה באג בקוד אלא **תווית שנגזרה משם הקובץ**.
הבדיקות כאן מגנות על שני דברים שאי אפשר להחזיר בשקט:
  1. `people` (מה שנצפה) גובר על `audience`/`tags` (מה שנכתב בשם).
  2. `people` אינו `audience` — שדה נפרד, אחרת קליפ משיעור מעורב היה נחסם
     מסרטון שמכוון לנשים.
"""
import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

from system_doctor import clip_gender  # noqa: E402


class TestClipGender(unittest.TestCase):
    def test_people_overrides_filename_label(self):
        """התווית משקרת, הפריים לא. זו הטעות שהולידה את השדה."""
        item = {"people": ["גברים"], "tags": ["מתאמנת", "נשים"], "audience": []}
        self.assertEqual(clip_gender(item), "m")

    def test_kids_not_counted_in_balance(self):
        """'שיעור ילדים' נספר עד v9.7 כ'נשים' וניפח את הצד הרוב."""
        self.assertEqual(clip_gender({"people": ["ילדים"], "tags": ["ילדים"]}), "?")

    def test_unverified_clip_is_unknown_not_guess(self):
        self.assertEqual(clip_gender({"tags": ["דדליפט"], "audience": []}), "?")

    def test_legacy_fallback_still_works(self):
        self.assertEqual(clip_gender({"tags": ["נשים"]}), "w")
        self.assertEqual(clip_gender({"audience": ["גברים"]}), "m")


class TestPoolBalance(unittest.TestCase):
    """הבריכה בפועל — לא מוק. אם מישהו יצמצם אותה, הבדיקה תיפול."""

    @classmethod
    def setUpClass(cls):
        cfg = json.loads((TOOLS / "broll-catalog-config.json")
                         .read_text(encoding="utf-8"))
        cat = json.loads(Path(cfg["catalog_path"]).read_text(encoding="utf-8"))["items"]
        dis = {d.get("file") for d in cfg.get("disabled_files", []) if d.get("file")}
        ver = set(cfg["verified_member_files"])
        cls.pool = [i for i in cat if i["file"] in ver and i["file"] not in dis]

    def test_minority_at_least_15_percent(self):
        g = [clip_gender(i) for i in self.pool]
        w, m = g.count("w"), g.count("m")
        self.assertGreater(w + m, 0)
        self.assertGreaterEqual(min(w, m) / (w + m), 0.15,
                                f"בריכה חד-מגדרית: {w} נשים · {m} גברים")

    def test_fail_injection_single_gender_pool_is_caught(self):
        """הזרקת כשל: בריכה שכולה נשים חייבת לרדת מתחת לסף."""
        g = ["w"] * 34 + ["m"] * 0
        w, m = g.count("w"), g.count("m")
        self.assertLess(min(w, m) / max(1, w + m), 0.15)

    def test_people_is_not_written_into_audience(self):
        """audience = למי הקליפ מיועד. אסור שהאימות הוויזואלי ידלוף לשם —
        אחרת קליפ משיעור מעורב ייחסם מסרטון שמכוון לנשים."""
        leaked = [i["file"] for i in self.pool
                  if "גברים" in (i.get("people") or [])
                  and "גברים" in (i.get("audience") or [])]
        self.assertEqual(leaked, [], f"people דלף ל-audience: {leaked[:3]}")

    def test_whole_pool_visually_verified(self):
        missing = [i["file"] for i in self.pool if not i.get("people")]
        self.assertEqual(missing, [],
                         f"{len(missing)} קליפים בבריכה בלי אימות ויזואלי")


if __name__ == "__main__":
    unittest.main()
