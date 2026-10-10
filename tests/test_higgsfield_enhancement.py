#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v9.35 (25.9.26) — higgsfield-ai-enhancement: אוכפים לשומר התקציב ולגבולות המודול.
=====================================================================
הראל 25.9.26: "₪20 היא תקרת הוצאה ללא אישור. לפני כל פעולה בתשלום:
Actual Spend + Cost of Next Generation + Expected Retry Risk". ה-Control לא משתנה.

  א. השומר זורק BudgetExceeded כשההקרנה חוצה ₪20 — גם כשהפעולה עצמה זולה.
  ב. failed/nsfw לא נספרים כהוצאה (Higgsfield לא מחייב אותם).
  ג. עדיפות תקציבית Hook/CTA 40/40, אמצע 20 — מי שמשנה את זה מפיל בדיקה.
  ד. Offer לא נבחר מתוך משפט ה-Hook/CTA (באג שנתפס בפיילוט: "הטבה" ב-Hook).
  ה. פירוק caplist — סכום הזמנים = אורך הסרטון (כתוביות נשארות מסונכרנות).
  ו. הלקוח לא מדפיס את הסוד (repr/שגיאה).
stdlib + numpy/PIL בלבד. בלי רשת.
"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
HF = HERE.parent / "tools" / "higgsfield"
sys.path.insert(0, str(HF))

from budget import Ledger, BudgetExceeded, DEFAULTS  # noqa: E402


class TestBudget(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="hfb_")
        self.L = Ledger(Path(self.d) / "ledger.json")

    def test_a_cap_blocks_projection(self):
        # הוצאה של ₪18.6 (=$6) + פעולה של $0.5 עם סיכון Retry 80% ⇒ 18.6+1.55+1.24 > 20
        self.L.record(role="cta", shot="x", charged_usd=6.0, status="completed")
        with self.assertRaises(BudgetExceeded):
            self.L.check("hook", 0.5, 0.8)

    def test_a_small_ok(self):
        info = self.L.check("hook", 0.139, 0.8)
        self.assertTrue(info["ok"])
        self.assertLess(info["projected_ils"], 1.0)

    def test_b_failed_not_charged(self):
        self.L.record(role="hook", shot="x", charged_usd=0.0, status="failed")
        self.L.record(role="hook", shot="x", charged_usd=0.139, status="completed")
        self.assertAlmostEqual(self.L.spent_usd(), 0.139, places=4)
        self.assertEqual(self.L.summary()["failed_uncharged"], 1)

    def test_c_priority_hook_cta(self):
        self.assertEqual(DEFAULTS["cap_ils"], 20.0)
        self.assertEqual(DEFAULTS["alloc"], {"hook": 0.4, "cta": 0.4, "mid": 0.2})

    def test_ledger_never_stores_body(self):
        e = self.L.record(role="hook", shot="x", body={"image_url": "u", "prompt": "p"}, charged_usd=0)
        self.assertNotIn("body", e)
        self.assertIn("body_hash", e)


class TestAnalysis(unittest.TestCase):
    def test_d_offer_not_from_hook(self):
        import enhance
        words = []
        t = 0.0
        for sent in ["תושבי אריאל מחפשים סיבה, יש לנו הטבה מטורפת.", "אצלנו בונים מסגרת.",
                     "אז יאללה, חודש שני במתנה לראשונים.", "תשאירו לנו פרטים."]:
            for w in sent.split():
                words.append({"word": w, "start": t, "end": t + 0.3}); t += 0.3
        S = enhance.sentences(words)
        hook, cta = S[0], S[-1]
        body = [s for s in S if s is not cta and s is not hook]
        offer = (next((s for s in body if enhance.STRONG_OFFER_RX.search(s["text"])), None)
                 or next((s for s in body if enhance.OFFER_RX.search(s["text"])), None))
        self.assertIn("במתנה", offer["text"])
        self.assertTrue(enhance.CTA_RX.search(cta["text"]))
        self.assertTrue(enhance.PLACE_RX.search(hook["text"]))

    def test_e_caplist_sums_to_duration(self):
        import enhance
        d = Path(tempfile.mkdtemp())
        (d / "caplist.txt").write_text("ffconcat version 1.0\nfile '_blank.png'\nduration 0.19\n"
                                       "file 'cue_0000.png'\nduration 0.68\nfile '_blank.png'\nduration 1.13\n"
                                       "file '_blank.png'\n")
        seq = enhance.parse_caplist(d / "caplist.txt")
        self.assertAlmostEqual(seq[-1][1], 2.0, places=3)
        self.assertEqual(seq[1][2], "cue_0000.png")


class TestSecret(unittest.TestCase):
    def test_f_secret_not_in_errors(self):
        import hf_client as hf
        os.environ["HF_KEY"] = "kid:SUPERSECRET"
        try:
            h = hf._h()
            self.assertEqual(h["Authorization"], "Key kid:SUPERSECRET")
            err = hf.HFError(403, '{"detail":"not_enough_credits"}')
            self.assertNotIn("SUPERSECRET", str(err))
        finally:
            del os.environ["HF_KEY"]

    def test_recipes_have_purpose_and_kpi(self):
        r = json.loads((HF / "recipes.json").read_text())
        allowed = {"Attention", "Explanation", "Emotion", "Transformation", "Action"}
        for k, v in r.items():
            if k.startswith("_"):
                continue
            self.assertTrue(set(v["purpose"]) <= allowed and v["purpose"], k)
            self.assertTrue(v["kpi"], k)
            self.assertIn(v["role"], ("hook", "mid", "cta"), k)
        self.assertIn("Action", r["cta_open_light_matte"]["purpose"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
