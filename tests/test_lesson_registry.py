# -*- coding: utf-8 -*-
"""רשומת הלקחים — 'אין לקח בלי אוכף', והאודיט תופס אוכף שנעלם.

הלקח שהוליד את הרשומה: fade-בתפר ו-eof_action נסוגו בשקט בהחלפת המנוע
ל-v2 וחזרו למסך של הראל (v9.11). הבדיקות כאן הן הזרקת-כשל: לא רק
"האודיט עובר", אלא "האודיט נכשל כשהאוכף באמת נעלם".
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import lesson_registry as LR


class TestRegistryShape(unittest.TestCase):
    def test_every_lesson_has_enforcers_and_fields(self):
        for lid, rec in LR.LESSONS.items():
            self.assertTrue(rec.get("enforced_by"), f"{lid}: לקח בלי אוכף")
            for f in ("lesson", "origin", "layer"):
                self.assertTrue(rec.get(f), f"{lid}: חסר {f}")

    def test_audit_passes_on_real_repo(self):
        ok, problems = LR.audit()
        self.assertTrue(ok, "אודיט הלקחים נכשל:\n" + "\n".join(problems))

    def test_director_lessons_are_stable_ordered(self):
        a = LR.director_lessons()
        b = LR.director_lessons()
        self.assertEqual(a, b)
        self.assertTrue(a, "אין אף לקח director_relevant")


class TestFailureInjection(unittest.TestCase):
    """הזרקת-כשל: אוכף שנעלם חייב להפיל את האודיט."""

    def _with_injected(self, enforcer):
        saved = dict(LR.LESSONS)
        LR.LESSONS = dict(saved)
        LR.LESSONS["L99_injected"] = LR.L(
            "לקח מוזרק לבדיקה", "בדיקה", "process", [enforcer])
        try:
            return LR.audit()
        finally:
            LR.LESSONS = saved

    def test_missing_code_pattern_fails(self):
        ok, problems = self._with_injected(
            {"kind": "code", "file": "tools/broll_director.py",
             "pattern": r"SYMBOL_THAT_DOES_NOT_EXIST_123"})
        self.assertFalse(ok)
        self.assertTrue(any("L99_injected" in p for p in problems))

    def test_missing_file_fails(self):
        ok, problems = self._with_injected(
            {"kind": "test", "file": "tests/test_no_such_file_123.py"})
        self.assertFalse(ok)

    def test_missing_gate_fails(self):
        ok, problems = self._with_injected(
            {"kind": "gate", "gate": "no_such_tool:no_such_gate"})
        self.assertFalse(ok)

    def test_wrong_gate_enforcement_fails(self):
        # G2_silence חייב להישאר advisory — אישור הראל הוא המילה האחרונה.
        ok, problems = self._with_injected(
            {"kind": "gate", "gate": "qa_gates:G2_silence",
             "enforcement": "blocking"})
        self.assertFalse(ok)

    def test_lesson_without_enforcers_fails(self):
        saved = dict(LR.LESSONS)
        LR.LESSONS = dict(saved)
        LR.LESSONS["L99_naked"] = {"lesson": "x", "origin": "y",
                                   "layer": "process", "enforced_by": [],
                                   "director_relevant": False}
        try:
            ok, problems = LR.audit()
        finally:
            LR.LESSONS = saved
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
