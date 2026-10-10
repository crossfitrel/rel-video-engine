#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_director.py — שכבת הספק וחמשת הפאסים (V2 שלב 1).

מה נבדק כאן זה בדיוק מה שמבדיל את V2 מ-v1:
  * המודל בוחר מתוך מרחב סופי. תשובה שממציאה מזהה נדחית לפני שנגעו במדיה.
  * ה-digest יציב על פני ריצות. באג אמיתי שנתפס כאן: built_at זלג ל-payload
    של הפאס הבא, ואז המפתח השתנה בכל ריצה וה-cache אף פעם לא נפגע.
  * backend=replay משחזר ריצה שלמה בלי אדם בלולאה.
"""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
TOOLS = SYSDIR / "tools"
sys.path.insert(0, str(TOOLS))

from relvid import provider as P            # noqa: E402
import edit_director as D                   # noqa: E402


def tmpproj():
    d = Path(tempfile.mkdtemp(prefix="reldir_"))
    return d


CANDS = {
    "schema_version": 1,
    "source": {"total_dur": 30.0},
    "sentences": [
        {"i": 0, "start": 0.0, "end": 5.0, "text": "משפט ראשון", "n_words": 2},
        {"i": 1, "start": 7.0, "end": 12.0, "text": "משפט שני", "n_words": 2},
        {"i": 2, "start": 13.0, "end": 20.0, "text": "משפט שלישי", "n_words": 2},
    ],
    "candidates": [
        {"candidate_id": "gap_0001", "kind": "inter_word_gap", "t_start": 5.0, "t_end": 7.0,
         "prev_word": "ראשון", "next_word": "משפט",
         "features": {"gap_sec": 2.0, "sentence_boundary": True,
                      "gap_is_true_silence": True, "breath_detected": False,
                      "motion_mean": 0.02, "motion_lower_mean": 0.03},
         "hard_constraints": {"is_hook": False, "cut_would_touch_word": False}},
        {"candidate_id": "gap_0002", "kind": "inter_word_gap", "t_start": 12.0, "t_end": 13.0,
         "features": {"gap_sec": 1.0, "breath_detected": True, "motion_lower_mean": 0.06}},
        {"candidate_id": "sent_002", "kind": "sentence_span", "t_start": 13.0, "t_end": 20.0,
         "text": "משפט שלישי",
         "features": {"n_words": 2, "dur_sec": 7.0, "duplicate_similarity": 0.4},
         "hard_constraints": {"is_hook": False, "cut_would_touch_word": False}},
    ],
}


# ══════════════════════════════════════════ מרחב ההחלטות
class TestCandidateSpace(unittest.TestCase):
    def test_unknown_id_rejected(self):
        """הליבה של V2: מזהה שלא קיים במרחב לא מגיע למדיה."""
        with self.assertRaises(P.ProviderError) as cm:
            P.validate_answer({"decisions": [{"candidate_id": "gap_9999"}]},
                              allowed_ids={"gap_0001"})
        self.assertIn("9999", str(cm.exception))

    def test_known_id_accepted(self):
        ans = {"decisions": [{"candidate_id": "gap_0001", "action": "cut"}]}
        self.assertIs(P.validate_answer(ans, allowed_ids={"gap_0001", "gap_0002"}), ans)

    def test_ids_found_at_any_depth(self):
        """מזהה מומצא שקבור עמוק בתשובה נתפס באותה מידה."""
        deep = {"a": {"b": [{"c": {"candidate_id": "ghost"}}]}}
        with self.assertRaises(P.ProviderError):
            P.validate_answer(deep, allowed_ids={"gap_0001"})

    def test_candidate_ids_list_form(self):
        with self.assertRaises(P.ProviderError):
            P.validate_answer({"x": {"candidate_ids": ["gap_0001", "nope"]}},
                              allowed_ids={"gap_0001"})

    def test_required_keys(self):
        with self.assertRaises(P.ProviderError):
            P.validate_answer({"decisions": []}, required_keys=("decisions", "brief"))

    def test_non_dict_rejected(self):
        with self.assertRaises(P.ProviderError):
            P.validate_answer([1, 2, 3])


# ══════════════════════════════════════════ יציבות המפתח
class TestDigest(unittest.TestCase):
    def test_stable(self):
        p = {"z": 1, "a": [1, 2, {"k": "ערך"}]}
        self.assertEqual(P.digest("director", p), P.digest("director", p))

    def test_key_order_irrelevant(self):
        self.assertEqual(P.digest("director", {"a": 1, "b": 2}),
                         P.digest("director", {"b": 2, "a": 1}))

    def test_role_changes_key(self):
        p = {"a": 1}
        self.assertNotEqual(P.digest("director", p), P.digest("reviewer", p))

    def test_payload_changes_key(self):
        self.assertNotEqual(P.digest("director", {"a": 1}), P.digest("director", {"a": 2}))

    def test_prompt_text_is_in_key(self):
        """עריכת קובץ פרומפט חייבת לפסול cache — אחרת חוזה חדש עם תשובה ישנה."""
        orig = P.prompt_text
        p = {"a": 1}
        before = P.digest("director", p)
        P.prompt_text = lambda role: orig(role) + "\nשורה חדשה"
        try:
            self.assertNotEqual(before, P.digest("director", p))
        finally:
            P.prompt_text = orig

    def test_no_volatile_metadata_downstream(self):
        """
        רגרסיה: understanding.json נכתב עם built_at, והאובייקט המעודכן הועבר
        לבמאי. ה-digest השתנה בכל ריצה וה-cache אף פעם לא נפגע.
        """
        und = {"story": {}, "pauses": []}
        d1 = P.digest("director", {"brief": {}, "understanding": und, "candidates": []})
        # מה שנכתב לקובץ לא נוגע במה שנשלח הלאה
        _file_copy = dict(und, built_at="2026-01-01 00:00:00", schema_version=1)
        d2 = P.digest("director", {"brief": {}, "understanding": und, "candidates": []})
        self.assertEqual(d1, d2)
        self.assertNotEqual(d1, P.digest("director", {"brief": {}, "understanding": _file_copy,
                                                      "candidates": []}))


# ══════════════════════════════════════════ backends
class TestBackends(unittest.TestCase):
    def test_replay_without_cache_fails_loudly(self):
        pv = P.Provider(tmpproj(), backend="replay", verbose=False)
        with self.assertRaises(P.ProviderError) as cm:
            pv.ask("director", {"a": 1})
        self.assertIn("replay", str(cm.exception))

    def test_chat_writes_card_then_reads_answer(self):
        d = tmpproj()
        pv = P.Provider(d, backend="chat", verbose=False)
        payload = {"a": 1}
        with self.assertRaises(P.NeedsHuman) as cm:
            pv.ask("director", payload, required_keys=("decisions",))
        card = Path(cm.exception.req_path)
        self.assertTrue(card.exists())
        txt = card.read_text(encoding="utf-8")
        self.assertIn("director/plan_v1.", txt)   # גרסת הפרומפט מוטבעת בכרטיס
        self.assertIn('"a": 1', txt)               # הקלט המלא בכרטיס
        Path(cm.exception.resp_path).write_text(
            json.dumps({"decisions": []}), encoding="utf-8")
        got = pv.ask("director", payload, required_keys=("decisions",))
        self.assertEqual(got, {"decisions": []})
        # ומעכשיו זה ב-cache, כלומר replay יעבוד
        pv2 = P.Provider(d, backend="replay", verbose=False)
        self.assertEqual(pv2.ask("director", payload, required_keys=("decisions",)),
                         {"decisions": []})

    def test_chat_answer_still_validated(self):
        """תשובה שהודבקה ידנית לא מקבלת פטור מבדיקת המרחב."""
        d = tmpproj()
        pv = P.Provider(d, backend="chat", verbose=False)
        payload = {"a": 1}
        try:
            pv.ask("director", payload, allowed_ids={"gap_0001"})
        except P.NeedsHuman as e:
            Path(e.resp_path).write_text(
                json.dumps({"decisions": [{"candidate_id": "gap_0009"}]}), encoding="utf-8")
        with self.assertRaises(P.ProviderError):
            pv.ask("director", payload, allowed_ids={"gap_0001"})

    def test_cache_record_carries_provenance(self):
        d = tmpproj()
        pv = P.Provider(d, backend="chat", verbose=False)
        try:
            pv.ask("scorer", {"a": 1})
        except P.NeedsHuman as e:
            Path(e.resp_path).write_text(json.dumps({"scores": {}}), encoding="utf-8")
        pv.ask("scorer", {"a": 1})
        rec = json.loads(next(Path(d, "ai_cache").glob("scorer.*.json")).read_text(encoding="utf-8"))
        for k in ("role", "prompt_version", "digest", "source", "created_at", "input_digest"):
            self.assertIn(k, rec)
        self.assertEqual(rec["prompt_version"], "scorer/rubric_v1.0")

    def test_extract_json_from_fenced_text(self):
        self.assertEqual(P._extract_json('בבקשה:\n```json\n{"a": 1}\n```\nזהו'), {"a": 1})

    def test_extract_json_failure(self):
        with self.assertRaises(P.ProviderError):
            P._extract_json("אין כאן JSON")


# ══════════════════════════════════════════ לוגיקת הפאסים
class TestPasses(unittest.TestCase):
    def test_slim_keeps_hard_constraints(self):
        """מגבלה קשיחה שלא מגיעה למודל היא מגבלה שהוא יפר."""
        s = D._slim_candidate(CANDS["candidates"][0])
        self.assertIn("hard_constraints", s)
        self.assertIn("gap_sec", s["features"])
        self.assertEqual(s["prev_word"], "ראשון")

    def test_slim_keeps_sentence_features(self):
        s = D._slim_candidate(CANDS["candidates"][2])
        self.assertEqual(s["text"], "משפט שלישי")
        self.assertIn("duplicate_similarity", s["features"])

    def test_normalize_maps_actions(self):
        raw = {"decisions": [
            {"candidate_id": "gap_0001", "action": "tighten", "tighten_to": 0.6,
             "confidence": 0.9, "reason": "ר"},
            {"candidate_id": "sent_002", "action": "flag", "confidence": 0.4, "reason": "ר"},
            {"candidate_id": "gap_0002", "action": "keep", "confidence": 0.8, "reason": "ר"}]}
        plan = D.normalize_plan(raw, {})
        acts = {d["candidate_id"]: d["action"] for d in plan["decisions"]}
        self.assertEqual(acts["gap_0001"], "tighten_to")
        self.assertEqual(acts["sent_002"], "suggest_only")
        self.assertEqual(acts["gap_0002"], "keep")
        self.assertEqual(plan["decisions"][0]["value"], 0.6)

    def test_normalize_is_deterministic(self):
        raw = {"decisions": [{"candidate_id": "gap_0001", "action": "keep",
                              "confidence": 0.9, "reason": "ר"}]}
        self.assertEqual(D.normalize_plan(raw, {})["plan_id"],
                         D.normalize_plan(raw, {})["plan_id"])

    def test_weighted_score(self):
        scores = {k: {"score": 8.0} for k in D.WEIGHTS}
        self.assertEqual(D.weighted(scores), 8.0)

    def test_weighted_ignores_missing_dimensions(self):
        self.assertEqual(D.weighted({"hook": {"score": 6.0}, "story": {"score": 8.0}}), 7.0)

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(D.WEIGHTS.values()), 1.0, places=6)

    def test_edited_transcript_is_blind(self):
        """המבקר מקבל את מה שהצופה מקבל — בלי נימוקים ובלי ביטחון."""
        d = tmpproj()
        (d / "candidates.json").write_text(json.dumps(CANDS, ensure_ascii=False), encoding="utf-8")
        plan = {"decisions": [{"candidate_id": "gap_0001", "action": "tighten_to",
                               "value": 0.2, "confidence": 0.9, "reason": "סוד"}]}
        tr = D.edited_transcript(d, plan, CANDS)
        blob = json.dumps(tr, ensure_ascii=False)
        self.assertNotIn("סוד", blob)
        self.assertNotIn("confidence", blob)
        self.assertIn("gap_sec", blob)

    def test_edited_transcript_drops_removed_sentence(self):
        d = tmpproj()
        plan = {"decisions": [{"candidate_id": "sent_002", "action": "cut",
                               "confidence": 0.9, "reason": "ר"}]}
        tr = D.edited_transcript(d, plan, CANDS)
        texts = [x.get("text") for x in tr if "text" in x]
        self.assertIn("משפט ראשון", texts)
        self.assertNotIn("משפט שלישי", texts)

    def test_edited_transcript_gap_reflects_the_cut(self):
        d = tmpproj()
        plan = {"decisions": [{"candidate_id": "gap_0001", "action": "tighten_to",
                               "value": 0.2, "confidence": 0.9, "reason": "ר"}]}
        tr = D.edited_transcript(d, plan, CANDS)
        gaps = [x["gap_sec"] for x in tr if "gap_sec" in x]
        self.assertAlmostEqual(gaps[0], 0.2, places=2)   # 2.0ש במקור → 0.2ש בפועל


if __name__ == "__main__":
    unittest.main(verbosity=2)
