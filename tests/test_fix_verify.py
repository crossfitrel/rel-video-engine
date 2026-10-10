#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_fix_verify — "קלאוד בודק לפני הראל" (v9.18).

מה נבדק כאן, ולמה דווקא זה:
  * **פסיקת קלאוד לא דורסת את הסימון של הראל, ולהפך** — שניהם על אותה
    רשומה ב-changelog_checks.json; דריסה שקטה הייתה מוחקת עבודה של אחד מהם.
  * **הסבב הממוקד (focus) באמת מוריד את מה שאומת** — זו הבטחת החיסכון
    להראל; אם focus מחזיר את אותם spots, לא חסכנו כלום.
  * **חילוץ מילים מצופות מהערת כתיב** — אותם דפוסים כמו note_corrections;
    דפוס שלא זוהה ⇒ inconclusive, לעולם לא ניחוש.
  * **זיהוי שינוי גבול EDL ליד הנקודה** — הראיה שהתיקון "חיתוך" אכן נכנס.
  * **P14 ב-preflight** — גרסה עם fixes בלי FIX_VERIFY תואם = ממצא; עם
    פסיקות מלאות = שקט. מדווח ולא חוסם (אין סף חוסם לא-מדוד).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))

from relvid import changelog as cl        # noqa: E402
import fix_verify as fv                   # noqa: E402
import preflight_critic as pf             # noqa: E402


class TestClaudeVerdictStorage(unittest.TestCase):
    def test_claude_verdict_and_harel_check_coexist(self):
        with tempfile.TemporaryDirectory() as d:
            cl.set_claude_verdict(d, "art1", "cmt_a", "verified",
                                  evidence="המילה 'ריבוי' נמצאה בכתוביות")
            cl.set_check(d, "art1", "cmt_a", "ok", actor="harel")
            ch = cl.load_checks(d)["art1"]["cmt_a"]
            # הסימון של הראל נשמר, והפסיקה של קלאוד לא נמחקה בדרך
            self.assertEqual(ch["state"], "ok")
            self.assertEqual(ch["claude"]["state"], "verified")
            self.assertIn("ריבוי", ch["claude"]["evidence"])

    def test_harel_first_then_claude(self):
        with tempfile.TemporaryDirectory() as d:
            cl.set_check(d, "art1", "cmt_b", "not_fixed", note="עדיין קופץ")
            cl.set_claude_verdict(d, "art1", "cmt_b", "not_fixed")
            ch = cl.load_checks(d)["art1"]["cmt_b"]
            self.assertEqual(ch["state"], "not_fixed")
            self.assertEqual(ch["note"], "עדיין קופץ")
            self.assertEqual(ch["claude"]["state"], "not_fixed")

    def test_unknown_claude_state_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                cl.set_claude_verdict(d, "a", "i", "maybe")


def _item(iid, t, claude=None, check=None):
    return {"item_id": iid, "kind": "comment", "t": t, "t_end": None,
            "claude": claude or {"state": "pending"},
            "check": check or {"state": "pending"}}


class TestFocusPlan(unittest.TestCase):
    def test_focus_drops_verified_and_flagged(self):
        v = {"items": [
            _item("cmt_1", 5.0, claude={"state": "verified"}),
            _item("cmt_2", 20.0),                                  # לא אומת
            _item("cmt_3", 40.0, claude={"state": "not_fixed"}),   # חזר לתור
            _item("cmt_4", 60.0, claude={"state": "needs_eye"}),   # נשאר
        ]}
        full = cl.review_plan(v)
        focus = cl.review_plan(v, focus=True)
        self.assertEqual(len(full["spots"]), 4)
        self.assertEqual(len(focus["spots"]), 2)
        self.assertLess(focus["covered_secs"], full["covered_secs"])

    def test_focus_drops_what_harel_already_checked(self):
        v = {"items": [_item("cmt_1", 5.0, check={"state": "ok"}),
                       _item("cmt_2", 20.0)]}
        focus = cl.review_plan(v, focus=True)
        self.assertEqual(len(focus["spots"]), 1)

    def test_focus_on_nothing_verified_equals_full(self):
        v = {"items": [_item("cmt_1", 5.0), _item("cmt_2", 20.0)]}
        self.assertEqual(len(cl.review_plan(v, focus=True)["spots"]),
                         len(cl.review_plan(v)["spots"]))


class TestExpectedTokens(unittest.TestCase):
    def test_star_pattern(self):
        self.assertEqual(fv.parse_expected_tokens("צריך להיות ריבוי*"), ["ריבוי"])

    def test_instead_pattern(self):
        self.assertEqual(fv.parse_expected_tokens("מתאמנת במקום מתאמן"),
                         ["מתאמנת"])

    def test_quoted_velo_pattern(self):
        toks = fv.parse_expected_tokens('"חוגי ילדים" ולא "חוגילדים"')
        self.assertIn("חוגי", toks)
        self.assertIn("ילדים", toks)

    def test_no_pattern_means_no_tokens(self):
        self.assertEqual(fv.parse_expected_tokens("ההוק חלש בעיניי"), [])

    def test_words_in_window(self):
        words = [{"word": "שלום", "start": 3.0}, {"word": "ריבוי", "start": 5.0},
                 {"word": "מוקדם", "start": 40.0}]
        r = fv.words_in_window(words, ["ריבוי", "מוקדם"], 5.0, win=6.0)
        self.assertEqual(r["found"], ["ריבוי"])
        self.assertEqual(r["missing"], ["מוקדם"])


class TestEdlChangeNear(unittest.TestCase):
    def test_change_near_point_is_detected(self):
        prev = [{"start": 0, "end": 10}, {"start": 12, "end": 30}]
        cur = [{"start": 0, "end": 10}, {"start": 14, "end": 30}]   # הגבול זז
        r = fv.boundaries_changed_near(prev, cur, src_t=13.0)
        self.assertTrue(r["changed_near"])

    def test_change_far_from_point_is_not_the_fix(self):
        prev = [{"start": 0, "end": 10}, {"start": 12, "end": 30}]
        cur = [{"start": 0, "end": 10}, {"start": 12, "end": 27}]   # שינוי ב-30→27
        r = fv.boundaries_changed_near(prev, cur, src_t=13.0)
        self.assertFalse(r["changed_near"])
        self.assertGreater(r["n_changed_total"], 0)

    def test_no_timecode_is_not_comparable(self):
        r = fv.boundaries_changed_near([], [], None)
        self.assertFalse(r["comparable"])


class TestPreflightP14(unittest.TestCase):
    def _mk_workdir(self, d, fixes, with_fv=False, verdicts=None):
        w = Path(d)
        aid = "art_x"
        adir = w / "artifacts" / aid
        adir.mkdir(parents=True)
        (adir / "artifact.json").write_text(json.dumps({
            "artifact_id": aid, "version": 5, "created_at": "2026-08-18T10:00:00",
            "fixes": fixes}), encoding="utf-8")
        if with_fv:
            (w / "FIX_VERIFY.json").write_text(json.dumps({
                "artifact_id": aid}), encoding="utf-8")
        if verdicts:
            (w / "changelog_checks.json").write_text(json.dumps({
                aid: {k: {"claude": {"state": v}} for k, v in verdicts.items()}}),
                encoding="utf-8")
        return w

    def test_fixes_without_fix_verify_is_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            w = self._mk_workdir(d, fixes=[{"comment_id": "c1"}])
            findings = []
            pf.check_fix_verify(findings, w)
            self.assertTrue(any(f["check"] == "P14_fixes_unverified"
                                for f in findings))

    def test_fully_verdicted_round_is_silent(self):
        with tempfile.TemporaryDirectory() as d:
            w = self._mk_workdir(d, fixes=[{"comment_id": "c1"}],
                                 with_fv=True, verdicts={"cmt_c1": "verified"})
            findings = []
            pf.check_fix_verify(findings, w)
            self.assertEqual(findings, [])

    def test_claude_not_fixed_is_high(self):
        with tempfile.TemporaryDirectory() as d:
            w = self._mk_workdir(d, fixes=[{"comment_id": "c1"}],
                                 with_fv=True, verdicts={"cmt_c1": "not_fixed"})
            findings = []
            pf.check_fix_verify(findings, w)
            self.assertTrue(any(f["severity"] == "high" for f in findings))

    def test_no_fixes_no_findings(self):
        with tempfile.TemporaryDirectory() as d:
            w = self._mk_workdir(d, fixes=[])
            findings = []
            pf.check_fix_verify(findings, w)
            self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
