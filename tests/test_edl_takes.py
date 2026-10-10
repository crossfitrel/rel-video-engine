#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
בדיקות v6.4/v7.9 — זיהוי טייקים כושלים ומיפוי מילים.
כל בדיקה כאן נולדה מפידבק אמיתי של הראל על "ניפוץ מיתוסים" (25.7.26).
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

import edl_build as eb                                    # noqa: E402
from relvid.edl_utils import map_words_to_keeps           # noqa: E402


def words_from(pairs, t0=0.0, gap=0.15):
    """[(מילה, משך)] → רשימת מילים עם תזמון; gap גדול מפריד משפטים."""
    out, t = [], t0
    for w, d in pairs:
        if w == "|":                      # מפריד משפטים (שקט)
            t += d
            continue
        out.append({"word": w, "start": round(t, 3), "end": round(t + d, 3), "prob": 0.9})
        t += d + gap
    return out


class TestContainment(unittest.TestCase):
    def test_partial_retake_is_detected(self):
        """'לבנות תנועה חזקה לאורך זמן' מוכל ב'...לבנות תנועה חזקה ונכונה לאורך זמן'.
        sent_sim נותן ~0.65 (מתחת ל-0.72) ולכן פספס — containment תופס."""
        a = "לבנות תנועה חזקה לאורך זמן"
        b = "או לאבחון שיעזור לכם לבנות תנועה חזקה ונכונה לאורך זמן"
        self.assertLess(eb.sent_sim(a, b), 0.72)
        self.assertGreaterEqual(eb.containment(a, b), 0.82)

    def test_unrelated_sentences_are_not_contained(self):
        a = "מתיחות אחרי אימון לא משפיעות על כאב שרירים"
        b = "מוזמנים להגיע אלינו לטיפול שיקל על הגוף"
        self.assertLess(eb.containment(a, b), 0.5)


class TestTakeMarkers(unittest.TestCase):
    def run_build(self, words, end):
        with tempfile.TemporaryDirectory() as tmp:
            wp = Path(tmp) / "w.json"
            wp.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([sys.executable, str(TOOLS / "edl_build.py"),
                                "--words", str(wp), "--out-dir", tmp, "--end", str(end)],
                               capture_output=True, text=True)
            assert r.returncode == 0, r.stderr
            return json.loads((Path(tmp) / "edl.json").read_text(encoding="utf-8"))

    def test_standalone_marker_sentence_is_cut(self):
        ws = words_from([("היום", .4), ("נדבר", .4), ("על", .3), ("תנועה", .5), ("|", 1.2),
                         ("סבבה", .5), ("|", 1.2),
                         ("וזה", .4), ("באמת", .4), ("עוזר", .5), ("לגוף", .5)], t0=8.0)
        edl = self.run_build(ws, 25.0)
        reasons = " ".join(c["reason"] for c in edl["auto_cuts"])
        self.assertIn("סבבה", reasons)

    def test_content_word_ending_is_not_cut(self):
        """'זה מרגיש טוב' — 'טוב' מילת תוכן בסוף משפט; אסור שתיחתך."""
        ws = words_from([("אחרי", .4), ("אימון", .5), ("זה", .3), ("מרגיש", .5), ("טוב", .5)],
                        t0=8.0)
        edl = self.run_build(ws, 15.0)
        reasons = " ".join(c["reason"] for c in edl["auto_cuts"])
        self.assertNotIn("אישור-טייק", reasons)


class TestMapWords(unittest.TestCase):
    def test_word_inside_cut_is_dropped_and_rest_shifts(self):
        w = [{"word": "א", "start": 0.0, "end": 1.0},
             {"word": "ב", "start": 2.0, "end": 3.0},
             {"word": "ג", "start": 5.0, "end": 6.0}]
        keeps = [{"start": 0.0, "end": 1.5}, {"start": 4.5, "end": 7.0}]
        out, stats = map_words_to_keeps(w, keeps)
        self.assertEqual([x["word"] for x in out], ["א", "ג"])
        self.assertEqual(stats["dropped"], 1)
        self.assertAlmostEqual(out[1]["start"], 2.0, places=2)

    def test_partial_overlap_below_threshold_is_dropped(self):
        w = [{"word": "חצי", "start": 0.9, "end": 1.9}]
        out, stats = map_words_to_keeps(w, [{"start": 0.0, "end": 1.0}])
        self.assertEqual(out, [])
        self.assertEqual(stats["dropped"], 1)

    def test_no_words_lost_when_nothing_is_cut(self):
        w = [{"word": f"w{i}", "start": i * 1.0, "end": i * 1.0 + 0.5} for i in range(20)]
        out, stats = map_words_to_keeps(w, [{"start": 0.0, "end": 30.0}])
        self.assertEqual(stats["out"], 20)
        self.assertEqual(stats["dropped"], 0)


if __name__ == "__main__":
    unittest.main()
