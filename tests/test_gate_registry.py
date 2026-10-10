# -*- coding: utf-8 -*-
"""
רגרסיה על **הרשומה של השערים** — לא על השערים עצמם.

הראל, 31.7.26: "שדברים לא ייפלו בין הכסאות, ושהמערכת תהיה עם קו מחשבה
עצמאי ולא בינארית." שתי הדרישות האלה נשמרות רק אם יש בדיקה שנכשלת כשהן
נשברות:

  * שער חדש בקוד שאיש לא רשם ⇒ הוא נפל בין הכסאות. הבדיקה נכשלת.
  * שער ברשומה שנעלם מהקוד ⇒ הרשומה משקרת. הבדיקה נכשלת.
  * שער בלי `protects`/`cost_of_blocking`/`fallback` ⇒ הוא אומר רק "לא".
  * **שער חוסם עם סף לא-מדוד** ⇒ בדיוק ההגדרה של "בינארי מתוך עצלנות".

כל בדיקה כאן מלווה בהזרקת-כשל, כי בדיקה שלא ראיתי אותה נכשלת אינה בדיקה.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import gate_registry as GR                          # noqa: E402


class TestRegistryCoversTheCode(unittest.TestCase):
    def test_every_gate_in_code_is_registered_and_vice_versa(self):
        ok, problems = GR.audit()
        self.assertTrue(ok, "\n".join(problems))

    def test_a_gate_missing_from_the_registry_fails_the_audit(self):
        """הזרקת כשל: שער שרץ בקוד ואינו ברשומה."""
        saved = GR.GATES.pop("qa_gates:G2_silence")
        try:
            ok, problems = GR.audit()
            self.assertFalse(ok)
            self.assertTrue(any("G2_silence" in p for p in problems))
        finally:
            GR.GATES["qa_gates:G2_silence"] = saved

    def test_a_registry_entry_with_no_gate_in_code_fails_the_audit(self):
        """ההזרקה ההפוכה: רשומה שממציאה שער שאינו קיים."""
        GR.GATES["qa_gates:G99_imaginary"] = GR.G(
            "qa_gates", GR.BLOCKING, "כלום", "כלום", "כלום")
        try:
            ok, problems = GR.audit()
            self.assertFalse(ok)
            self.assertTrue(any("G99_imaginary" in p for p in problems))
        finally:
            GR.GATES.pop("qa_gates:G99_imaginary")


class TestEveryGateExplainsItself(unittest.TestCase):
    def test_three_fields_present_everywhere(self):
        missing = [f"{k}.{f}" for k, e in GR.GATES.items()
                   for f in ("protects", "cost_of_blocking", "fallback")
                   if not e.get(f)]
        self.assertEqual([], missing)

    def test_unknown_gate_is_visible_not_silent(self):
        a = GR.annotate("qa_gates", "לא_קיים")
        self.assertEqual("unknown", a["registry"])

    def test_annotate_returns_the_reason_for_a_real_gate(self):
        a = GR.annotate("canon_lint", "approve_publish_gate")
        self.assertIn("אישור", a["protects"])
        self.assertEqual(GR.BLOCKING, a["enforcement"])


class TestNoBlockingGateRestsOnAnUnmeasuredNumber(unittest.TestCase):
    """זו ההבחנה שהראל ביקש, כקוד: חסימה מותרת כשהעלות אינה מתקזזת —
    לא כשהסף הוא מספר עגול שאיש לא מדד."""

    def test_no_blocking_gate_is_unmeasured(self):
        bad = [k for k, e in GR.GATES.items()
               if e["enforcement"] == GR.BLOCKING
               and e["threshold_source"] == GR.UNMEASURED]
        self.assertEqual([], bad,
                         "שער חוסם עם סף לא-מדוד — או למדוד אותו או להוריד לדיווח")

    def test_the_rule_would_catch_a_violation(self):
        GR.GATES["qa_gates:G98_round"] = GR.G(
            "qa_gates", GR.BLOCKING, "א", "ב", "ג", "42", GR.UNMEASURED)
        try:
            bad = [k for k, e in GR.GATES.items()
                   if e["enforcement"] == GR.BLOCKING
                   and e["threshold_source"] == GR.UNMEASURED]
            self.assertIn("qa_gates:G98_round", bad)
        finally:
            GR.GATES.pop("qa_gates:G98_round")

    def test_gates_that_can_never_fail_are_marked_as_such(self):
        """פונקציה שתמיד מחזירה 'עבר' היא שקר שקט אלא אם היא מוצהרת."""
        for k in ("canon_lint:no_graphics_logo", "canon_lint:naming",
                  "canon_lint:final_exists"):
            self.assertTrue(GR.GATES[k]["always_true"], k)
            self.assertEqual(GR.REPORTING, GR.GATES[k]["enforcement"], k)


class TestTheReasonReachesTheReport(unittest.TestCase):
    """לא מספיק שהנימוק ברשומה — הוא חייב להיכנס לדוח עצמו."""

    def test_canon_lint_embeds_the_reason_in_its_check_record(self):
        import canon_lint
        canon_lint.checks.clear()
        canon_lint.add("hook_protected", "HARD_FAIL", True, "בדיקה")
        rec = canon_lint.checks[-1]
        self.assertIn("why", rec)
        self.assertIn("הוק", rec["why"]["protects"])
        self.assertTrue(rec["why"]["fallback"])
        canon_lint.checks.clear()

    def test_system_doctor_embeds_the_reason(self):
        import system_doctor
        system_doctor.checks.clear()
        system_doctor.add("work root off iCloud", "PASS", "ok")
        self.assertIn("iCloud", system_doctor.checks[-1]["why"]["protects"])
        system_doctor.checks.clear()


class TestSequenceQaProducesDebtNotJustBlame(unittest.TestCase):
    """שער שאומר רק 'לא' לא סיים את העבודה: כשכל המצע `medium`, הליקוי
    אינו בסרטון אלא בבריכה — והפלט הוא רשימת שוטים לצלם."""

    def test_all_medium_pool_yields_a_wide_shot_debt(self):
        import broll_sequence_qa as SQ
        seq = [{"shot": "medium"} for _ in range(12)]
        debt = SQ.shot_debt(seq, [])
        self.assertIn("wide", [d["need"] for d in debt])

    def test_a_varied_sequence_owes_nothing(self):
        import broll_sequence_qa as SQ
        seq = [{"shot": "wide"}, {"shot": "medium"}, {"shot": "close"}]
        self.assertEqual([], SQ.shot_debt(seq, []))


if __name__ == "__main__":
    unittest.main()
