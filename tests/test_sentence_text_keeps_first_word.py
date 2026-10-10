#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L31 — שיוך מילה→משפט אחרי ההגהה לא רשאי לאבד את המילה הראשונה.

השורש (17.8.26, "טיפ-אחד-בטן-בר"): גבולות המשפטים ב-candidates.json נבנים
מזמני מילים אחרי `snap_words_to_audio`; `pass_proofread` קורא את
`whisper_raw` הלא-מוצמד ומסנן לפי חלון הזמן של המשפט. ההפרש קטן (~0.3ש)
אבל שיטתי ותמיד באותו כיוון — המילה הראשונה נופלת מחוץ לחלון.

נמדד: sent_000 "טיפ אחד לטוז טו בר" → "אחד לטוז טו בר". המילה שנותנת
לפורמט את שמו נעלמה בדיוק מהטקסט שהמבקר ושכבת הבירול רואים. הכתוביות
נבנות מהמילים ולכן לא נפגעו — וזה מה שהסתיר את זה מכל שער קיים.
"""
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))


class _StubProvider:
    """מחזיר תשובת מגיה ריקה — הבדיקה נוגעת רק בשיוך שאחריה."""
    def ask(self, role, payload, **kw):
        return {"corrections": [], "approved": [], "needs_manual": []}


class TestSentenceTextKeepsFirstWord(unittest.TestCase):

    def setUp(self):
        import edit_director as ED
        self.ED = ED
        self.tmp = Path(__file__).resolve().parent / "_tmp_l31"
        self.tmp.mkdir(exist_ok=True)
        # זמני מילים כפי שהם ב-whisper_raw (לא מוצמדים)
        self.words = [
            {"word": "טיפ", "start": 6.80, "end": 7.20},
            {"word": "אחד", "start": 7.32, "end": 7.70},
            {"word": "לטוז", "start": 7.82, "end": 8.40},
            {"word": "טו", "start": 8.74, "end": 8.90},
            {"word": "בר.", "start": 8.92, "end": 9.04},
            {"word": "אז", "start": 18.11, "end": 18.40},
            {"word": "תנועה", "start": 18.75, "end": 19.20},
        ]
        import json
        (self.tmp / "whisper_raw.json").write_text(
            json.dumps(self.words, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_first_word_of_each_sentence_survives(self):
        # גבולות המשפט מגיעים מזמנים **מוצמדים** — 7.14 ולא 6.80.
        sents = [{"i": 0, "start": 7.14, "end": 9.04, "text": "טיפ אחד לטוז טו בר."},
                 {"i": 1, "start": 18.11, "end": 19.20, "text": "אז תנועה"}]
        self.ED.pass_proofread(_StubProvider(), self.tmp, sents)
        self.assertIn("טיפ", sents[0]["text"],
                      "המילה הראשונה של המשפט נפלה מ-s['text'] — "
                      "המבקר ושכבת הבירול יראו משפט קטום")
        self.assertTrue(sents[0]["text"].startswith("טיפ"))
        self.assertIn("אז", sents[1]["text"])

    def test_words_are_not_stolen_across_sentences(self):
        """התיקון מרחיב את השיוך — הוא לא רשאי לשכפל או לגנוב מילים."""
        sents = [{"i": 0, "start": 7.14, "end": 9.04, "text": ""},
                 {"i": 1, "start": 18.11, "end": 19.20, "text": ""}]
        self.ED.pass_proofread(_StubProvider(), self.tmp, sents)
        joined = (sents[0]["text"] + " " + sents[1]["text"]).split()
        self.assertEqual(len(joined), len(set(joined)),
                         "מילה שויכה ליותר ממשפט אחד")
        self.assertNotIn("תנועה", sents[0]["text"])
        self.assertNotIn("בר.", sents[1]["text"])


if __name__ == "__main__":
    unittest.main()
