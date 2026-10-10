#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
בדיקות note_corrections (v7.8) — התיקונים שהראל כותב בהערות, אוטומטית.
הכלל הנבדק החשוב ביותר: **עדיף לא לתקן מאשר לתקן לא נכון** — מילה מסומנת עמומה
חייבת להגיע ל-needs_manual ולא להפוך לניחוש (רגרסיה אמיתית שנתפסה 25.7.26:
"לפני*" הפך בטעות את "לנו" התקין ל"לפני").
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))

import note_corrections as nc  # noqa: E402


def work(tmp, comments, transcript):
    d = Path(tmp) / "פרויקט"
    d.mkdir(parents=True, exist_ok=True)
    (d / "comments.json").write_text(
        json.dumps([{"comment_id": f"c{i}", "text": t, "actor": "harel", "status": "open"}
                    for i, t in enumerate(comments)], ensure_ascii=False), encoding="utf-8")
    (d / "edited.txt").write_text(transcript, encoding="utf-8")
    return d


def run(d, *args):
    r = subprocess.run([sys.executable, str(TOOLS / "note_corrections.py"),
                        "--workdir", str(d), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


class TestParsing(unittest.TestCase):
    def test_explicit_pair_x_not_y(self):
        pairs, stars, _ = nc.parse_notes(["בקרוספיט* ולא קרוספית"])
        self.assertIn(("קרוספית", "בקרוספיט", "A_not"), pairs)

    def test_instead_of_is_reported_not_applied(self):
        """'X במקום Y' דו-משמעי בעברית ⇒ לעולם לא מוחל אוטומטית, רק מדווח.
        נמדד על ההערות האמיתיות: 3 מתוך 4 התאמות היו בכיוון ההפוך."""
        pairs, _, amb = nc.parse_notes(["אני האבא במקום אני דואגת"])
        self.assertEqual(pairs, [])
        self.assertEqual(amb[0]["a"], "אני האבא")
        self.assertEqual(amb[0]["b"], "אני דואגת")

    def test_reverse_direction_instead_is_not_applied(self):
        pairs, _, amb = nc.parse_notes(
            ["לקחת את הקטע שהוא עושה טעות במקום את הקטע הנכון"])
        self.assertEqual(pairs, [])
        self.assertTrue(amb)

    def test_star_keeps_context(self):
        _, stars, _ = nc.parse_notes(["רחוקות* מהאוזניים"])
        self.assertEqual(stars[0][0], "רחוקות")
        self.assertEqual(stars[0][2], "מהאוזניים")   # עוגן ימני


class TestSafety(unittest.TestCase):
    def test_function_word_is_never_a_target(self):
        """'לפני*' לא יהפוך את 'לנו' התקין — מילת תפקוד ברשימת העצירה."""
        stars = [("לפני", "", "")]
        resolved, manual = nc.resolve_stars(stars, "יש לנו מועדון גדול".split(), [])
        self.assertEqual(resolved, [])
        self.assertEqual(manual[0]["word"], "לפני")

    def test_ambiguous_goes_to_manual(self):
        stars = [("חכו", "", "רגע")]
        resolved, manual = nc.resolve_stars(
            stars, "ככה לכם נכון הזו וכל רגע".split(), [])
        self.assertEqual(resolved, [])
        self.assertTrue(manual)

    def test_anchor_resolves_confidently(self):
        stars = [("רחוקות", "", "מהאוזניים")]
        resolved, _ = nc.resolve_stars(
            stars, "הכתפיים חוקות מהאוזניים תמיד".split(), [])
        self.assertEqual(resolved, [("חוקות", "רחוקות", "B_star_anchored")])

    def test_already_correct_is_noop(self):
        stars = [("רחוקות", "", "מהאוזניים")]
        resolved, manual = nc.resolve_stars(
            stars, "הכתפיים רחוקות מהאוזניים".split(), [])
        self.assertEqual(resolved, [])
        self.assertEqual(manual, [])


class TestApply(unittest.TestCase):
    def test_whole_word_only(self):
        """החלפה על ליבת מילה שלמה — לא substring (שלא ישבש מילה מכילה)."""
        text, n, _ = nc.apply_pairs("גישות פגישות והגישות", [("גישות", "פגישות", "A_not")])
        self.assertEqual(n, 1)
        self.assertEqual(text.split()[0], "פגישות")
        self.assertEqual(text.split()[2], "והגישות")

    def test_punctuation_preserved(self):
        text, n, _ = nc.apply_pairs("זה סריך, נכון?", [("סריך", "צריך", "A_not")])
        self.assertEqual(text, "זה צריך, נכון?")

    def test_end_to_end_writes_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = work(tmp, ["צריך* ולא סריך"], "זה סריך לעבוד")
            rep = run(d, "--apply")
            self.assertEqual(rep["applied"], 1)
            self.assertTrue(rep["written"])
            self.assertIn("צריך", (d / "edited.txt").read_text(encoding="utf-8"))

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = work(tmp, ["צריך* ולא סריך"], "זה סריך לעבוד")
            rep = run(d)
            self.assertFalse(rep["written"])
            self.assertIn("סריך", (d / "edited.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
