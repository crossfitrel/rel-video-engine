#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""שער G9 — כל מילה שנצרבת היא מילה בעברית (30.7.26).

שורש: נצרבו "ועל כל צפוף" בהוק, "הציעות", "בשוט הצהריים" ואף שער לא הסתכל
על המילים. כל בדיקה כאן היא הזרקת-כשל — היא מוודאת שהשער **נכשל** כשצריך.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

import he_lexicon as LEX                                      # noqa: E402
import caption_lexicon_qa as G9                               # noqa: E402


def proj(words, fix=None):
    d = Path(tempfile.mkdtemp())
    (d / "words_final.json").write_text(json.dumps(
        [{"word": w, "start": 1.0 + i * 0.3, "end": 1.2 + i * 0.3}
         for i, w in enumerate(words)], ensure_ascii=False), encoding="utf-8")
    if fix is not None:
        (d / "transcript_fix.json").write_text(json.dumps(fix, ensure_ascii=False),
                                               encoding="utf-8")
    return d


class TestG9(unittest.TestCase):
    def test_real_errors_are_caught(self):
        """שלוש השגיאות שנצרבו בפועל — כולן חייבות להיתפס."""
        d = proj(["אתם", "מתאמנים", "ועל", "כל", "צפוף", "הציעות", "בשוט"],
                 fix={"applied": [], "approved": [], "needs_manual": []})
        rep, code = G9.check(d)
        found = {x["word"] for x in rep["unknown"]}
        self.assertTrue({"ועל", "הציעות", "בשוט"} <= found, found)
        self.assertEqual(code, 1)
        self.assertTrue(rep["blocking"])

    def test_correction_makes_word_acceptable(self):
        """מילה שהמגיה תיקן בביטחון גבוה — מותרת."""
        d = proj(["הציוד", "זמין"],
                 fix={"applied": [{"i": 0, "from": "הציעות", "to": "הציוד",
                                   "confidence": 0.95, "why": "ר"}],
                      "approved": [], "needs_manual": []})
        rep, code = G9.check(d)
        self.assertEqual(code, 0, rep["unknown"])

    def test_open_question_blocks_the_whole_run(self):
        """שאלת תמלול פתוחה אחת עוצרת פרסום — גם אם כל המילים בלקסיקון."""
        d = proj(["כושר", "טוב"],
                 fix={"applied": [], "approved": [],
                      "needs_manual": [{"i": 0, "w": "ועל", "why": "לא הכרעתי"}]})
        rep, code = G9.check(d)
        self.assertEqual(code, 1)
        self.assertEqual(len(rep["unresolved_questions"]), 1)

    def test_open_question_does_not_block_identical_valid_words(self):
        """הזרקת-כשל על באג אמיתי: המגיה סימן אינדקס שהמילה בו 'כל', והשער
        חסם את כל 5 המופעים התקינים של 'כל'. ההתאמה היא ברמת הריצה, לא הטוקן."""
        d = proj(["כל", "כל", "כל"],
                 fix={"applied": [], "approved": [],
                      "needs_manual": [{"i": 3, "w": "כל", "why": "חלק מצירוף משובש"}]})
        rep, code = G9.check(d)
        self.assertEqual(len(rep["unknown"]), 0)          # אף מילה תקינה לא סומנה
        self.assertEqual(len(rep["unresolved_questions"]), 1)   # שאלה אחת, לא שלוש

    def test_hebrew_geresh_equals_ascii_apostrophe(self):
        """הזרקת-כשל: "ג׳ים" (גרש עברי) ו-"ג'ים" (אפוסטרוף) הן אותה מילה.
        בלי זה השער חסם מונח מותג תקין."""
        self.assertEqual(LEX.norm("ג׳ים"), LEX.norm("ג\'ים"))
        lex, _ = LEX.load()
        self.assertIn(LEX.norm("ג׳ים"), lex)

    def test_report_never_claims_zero_when_it_found_something(self):
        """הזרקת-כשל על הדיווח עצמו. הגרסה הראשונה הדפיסה 'אפס מילים לא
        מוכרות' בזמן שהחזיקה 9 — כי הדגל non-blocking דרס את הניסוח."""
        d = proj(["הציעות", "בשוט"])          # בלי transcript_fix ⇒ לא חוסם
        rep, code = G9.check(d)
        self.assertEqual(code, 0)             # לא חוסם
        self.assertFalse(rep["blocking"])
        self.assertFalse(rep["ok"])           # אבל **לא** מדווח שהכל תקין
        self.assertGreaterEqual(len(rep["unknown"]), 2)

    def test_lexicon_never_built_from_raw_asr(self):
        """הקורפוס הגולמי מכיל את השיבושים עצמם — 'הציעות' מופיעה ב-7
        פרויקטים כי אותו מקור הועתק. הלקסיקון חייב לבוא רק ממקור מתוקן."""
        # בדיקה התנהגותית ולא טקסטואלית: הלקסיקון שנבנה בפועל **אינו** מכיל
        # את השיבושים, למרות שהם מופיעים ב-7-8 קבצי whisper_raw בעץ העבודה.
        lex, d = LEX.load()
        for bad in ("הציעות", "בשוט", "ועל"):
            self.assertNotIn(bad, lex, f"'{bad}' דלף ללקסיקון — כנראה נבנה מקורפוס גולמי")
        self.assertGreater(d["sources"]["corrected_files"], 5)

    def test_approve_grows_lexicon(self):
        """כל אישור מצמצם את רשימת ההדק בריצה הבאה — זה מה שמדייק את
        המערכת מעצמה."""
        before, _ = LEX.load()
        w = "מילתבדיקהסינתטית"
        self.assertNotIn(w, before)
        LEX.approve([w], why="בדיקה")
        after, d = LEX.load()
        self.assertIn(w, after)
        # ניקוי כדי לא לזהם את הלקסיקון האמיתי
        d["approved"].pop(w, None)
        d["words"] = sorted(set(d["words"]) - {w})
        d["n_words"] = len(d["words"])
        LEX.LEX_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestPhraseCorrections(unittest.TestCase):
    """תיקון רב-מילה→מילה, דטרמיניסטי, לפני ששואלים את המודל.
    זה המנגנון שגורם לשיבוש שאושר פעם אחת לא להישאל שוב לעולם."""

    def test_glossary_holds_the_confirmed_hook_fix(self):
        import json as _j
        g = _j.loads((LEX.HERE / "asr-glossary.json").read_text(encoding="utf-8"))
        self.assertEqual((g.get("phrase_corrections") or {}).get("ועל כל"), "והמקום")

    def test_merge_keeps_span_and_word_count(self):
        """שני טוקנים → מילה אחת: הזמן נשמר מקצה לקצה, מספר המילים יורד ב-1."""
        import edit_director as D
        words = [{"word": "אתם", "start": 0.0, "end": 0.9},
                 {"word": "מתאמנים", "start": 0.9, "end": 1.74},
                 {"word": "ועל", "start": 1.74, "end": 2.06},
                 {"word": "כל", "start": 2.06, "end": 2.18},
                 {"word": "צפוף,", "start": 2.18, "end": 2.84}]
        out, applied = D._apply_phrase_corrections(words, {"ועל כל": "והמקום"})
        self.assertEqual(len(out), 4)
        self.assertEqual(out[2]["word"], "והמקום")
        self.assertAlmostEqual(out[2]["start"], 1.74, places=3)
        self.assertAlmostEqual(out[2]["end"], 2.18, places=3)   # קצה הטוקן השני
        self.assertEqual(applied[0]["merged_tokens"], 2)

    def test_no_match_is_a_noop(self):
        import edit_director as D
        words = [{"word": "שלום", "start": 0.0, "end": 0.5}]
        out, applied = D._apply_phrase_corrections(words, {"ועל כל": "והמקום"})
        self.assertEqual(out, words)
        self.assertEqual(applied, [])
