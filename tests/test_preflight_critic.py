# -*- coding: utf-8 -*-
"""המבקר האחרון לפני הראל — בדיקות הזרקת-כשל על כל בדיקת-כאב.

כל בדיקה כאן משחזרת ליקוי שהראל דיווח עליו במילים שלו, ומוודאת שהמבקר
תופס אותו **על התוכנית שהוחלה בפועל** — כלומר גם אם השכבה שהייתה אמורה
למנוע אותו (snap_to_cuts / close_small_holes) נסוגה בהחלפת מנוע עתידית.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import preflight_critic as PF
import broll_director as BD


def W(tmp, keeps, plan_items=None, plan_meta=None):
    w = Path(tmp)
    (w / "edl.json").write_text(json.dumps(
        {"keep_segments": keeps}, ensure_ascii=False), encoding="utf-8")
    if plan_items is not None:
        doc = {"plan": plan_items}
        doc.update(plan_meta or {})
        (w / "broll_plan.json").write_text(json.dumps(doc, ensure_ascii=False),
                                           encoding="utf-8")
    # v9.44 (P22): פרויקט "נקי" = גם הוק מוצהר ונבדק על גיליון. בלי זה P22 מחזיר high (נבדק ב-test_hook_plan)
    (w / "HOOK_PLAN.json").write_text(json.dumps(
        {"version": 1, "technique": "action_first", "anchor_type": "action",
         "t0": "התרגיל רץ בפריים 0", "sheet": "HOOK_SHEET.jpg"}, ensure_ascii=False), encoding="utf-8")
    (w / "HOOK_SHEET.jpg").write_bytes(b"")
    return w


# ציר: שני קטעים 0-20 ו-22-52 → קאט אחד בציר הפלט ב-20.0, משך 50ש.
KEEPS = [{"start": 0.0, "end": 20.0}, {"start": 22.0, "end": 52.0}]


def checks_of(doc, sev=None):
    return [f["check"] for f in doc["findings"]
            if sev is None or f["severity"] == sev]


class TestCutFlash(unittest.TestCase):
    """הראל 1.8.26: "אם קטע נגמר ב-1.5ש, הבירול חייב להיגמר ב-1.55 ולא ב-1.4"."""

    def test_broll_ending_just_before_cut_is_flagged(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS, [{"id": "b1", "label": "סקוואט",
                              "insert_at": 17.0, "insert_end": 19.6}])
            doc = PF.run(w, out_dur=50.0)
            self.assertIn("P1_cut_flash", checks_of(doc, "high"))
            self.assertFalse(doc["verdict"]["ready_for_harel"])

    def test_broll_crossing_cut_is_clean(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS, [{"id": "b1", "label": "סקוואט",
                              "insert_at": 17.0,
                              "insert_end": 20.0 + BD.CUT_OVERHANG + 0.01}])
            doc = PF.run(w, out_dur=50.0)
            self.assertNotIn("P1_cut_flash", checks_of(doc))

    def test_far_broll_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS, [{"id": "b1", "label": "רחוק",
                              "insert_at": 6.0, "insert_end": 9.0}])
            doc = PF.run(w, out_dur=50.0)
            self.assertNotIn("P1_cut_flash", checks_of(doc))


class TestBrollShape(unittest.TestCase):
    def test_short_clip_is_a_blink(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS, [{"id": "b1", "label": "קצר",
                              "insert_at": 6.0, "insert_end": 7.0}])
            doc = PF.run(w, out_dur=50.0)
            self.assertIn("P2_broll_min_len", checks_of(doc, "high"))

    def test_adjacent_gap_is_a_blink(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS, [
                {"id": "b1", "label": "א", "insert_at": 6.0, "insert_end": 8.5},
                {"id": "b2", "label": "ב", "insert_at": 9.0, "insert_end": 11.5}])
            doc = PF.run(w, out_dur=50.0)
            self.assertIn("P3_adjacent_blink", checks_of(doc, "high"))

    def test_hook_and_cta_guard(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS, [
                {"id": "b1", "label": "על ההוק", "insert_at": 1.0, "insert_end": 3.9},
                {"id": "b2", "label": "על הסיטיאיי", "insert_at": 45.0, "insert_end": 48.0}])
            doc = PF.run(w, out_dur=50.0)
            self.assertEqual(
                checks_of(doc, "high").count("P4_hook_cta_guard"), 2)

    def test_declared_bed_end_overrides_cta_guard(self):
        """דוקטרינת המרה מוצהרת: מצע עד bed_end אינו ליקוי (V3-לולאה, 16.8)."""
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS, [
                {"id": "b1", "label": "מצע", "role": "bed",
                 "insert_at": 40.0, "insert_end": 44.0}],
                plan_meta={"doctrine": {"mode": "continuous_bed", "bed_end": 44.0}})
            doc = PF.run(w, out_dur=50.0)
            self.assertNotIn("P4_hook_cta_guard", checks_of(doc))
            # אבל עוגן באותו מקום — עדיין ליקוי
            w2 = W(tempfile.mkdtemp(), KEEPS, [
                {"id": "b1", "label": "עוגן", "role": "anchor",
                 "insert_at": 40.0, "insert_end": 44.0,
                 "reason": "מצטט", "sent_text": "מצטט משהו"}],
                plan_meta={"doctrine": {"mode": "continuous_bed", "bed_end": 44.0}})
            doc2 = PF.run(w2, out_dur=50.0)
            self.assertIn("P4_hook_cta_guard", checks_of(doc2, "high"))


class TestAnchorContext(unittest.TestCase):
    def test_topic_picked_plan_is_flagged(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS,
                  [{"id": "b1", "label": "x", "insert_at": 6.0, "insert_end": 8.5}],
                  plan_meta={"picked_by": "topic"})
            doc = PF.run(w, out_dur=50.0)
            self.assertIn("P5_anchor_without_quote", checks_of(doc, "high"))

    def test_anchor_reason_not_quoting_is_flagged(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS, [{
                "id": "b1", "label": "ראיון", "role": "anchor",
                "insert_at": 6.0, "insert_end": 8.5,
                "reason": "קליפ יפה של מתאמנת מחייכת",
                "sent_text": "המנוי כולל גישה חופשית לכל השעות"}])
            doc = PF.run(w, out_dur=50.0)
            self.assertIn("P5_anchor_without_quote", checks_of(doc, "high"))

    def test_quoting_anchor_is_clean(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS, [{
                "id": "b1", "label": "שעות", "role": "anchor",
                "insert_at": 6.0, "insert_end": 8.5,
                "reason": "מצטט: גישה חופשית לכל השעות — רואים את הלוח",
                "sent_text": "המנוי כולל גישה חופשית לכל השעות"}])
            doc = PF.run(w, out_dur=50.0)
            self.assertNotIn("P5_anchor_without_quote", checks_of(doc))


class TestVerdictAndRollup(unittest.TestCase):
    def test_clean_project_is_ready(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS, [{"id": "b1", "label": "נקי",
                              "insert_at": 6.0, "insert_end": 9.0}])
            doc = PF.run(w, out_dur=55.0)
            self.assertTrue(doc["verdict"]["ready_for_harel"],
                            doc["verdict"]["summary"])
            self.assertTrue((Path(t) / "PREFLIGHT.json").exists())

    def test_duration_out_of_target_is_medium(self):
        # v9.25 (L67): אין יותר יעד 50-65. ערך 42ש = בתוך היעד; 110ש בלי נימוק = MED;
        # עם length_reason במניפסט = LOW בלבד. אף אחד מהם לא חוסם.
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS)
            doc = PF.run(w, out_dur=42.0)
            self.assertNotIn("P6_duration", checks_of(doc, "medium"))
            doc = PF.run(w, out_dur=110.0)
            self.assertIn("P6_duration", checks_of(doc, "medium"))
            self.assertTrue(doc["verdict"]["ready_for_harel"])
            (Path(w) / "project_manifest.json").write_text(
                json.dumps({"content_type": "value", "length_reason": "סיפור עם מתח"}),
                encoding="utf-8")
            doc = PF.run(w, out_dur=110.0)
            self.assertNotIn("P6_duration", checks_of(doc, "medium"))

    def test_advisory_gate_rollup(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS)
            (w / "qa_report.json").write_text(json.dumps({
                "gates": [{"gate": "G2_silence", "pass": False, "hard": False,
                           "detail": "חור 0.7ש ב-31.2"}]}), encoding="utf-8")
            doc = PF.run(w, out_dur=55.0)
            self.assertIn("P7_advisory_gate_open", checks_of(doc, "medium"))

    def test_no_plan_no_broll_findings(self):
        with tempfile.TemporaryDirectory() as t:
            w = W(t, KEEPS)
            doc = PF.run(w, out_dur=55.0)
            # השוואה לשמות מפורשים ולא לתחילית: מ-v9.14 קיים P13, והבדיקה
            # מבוססת-התחילית הייתה תופסת אותו כאילו היה ממצא תלוי-תוכנית.
            plan_dependent = {
                "P1_cut_flash", "P2_broll_min_len", "P3_adjacent_blink",
                "P4_hook_cta_guard", "P5_anchor_without_quote"}
            for c in checks_of(doc):
                self.assertNotIn(c, plan_dependent)


class TestCaptionVisionSeverity(unittest.TestCase):
    """v9.34 — P20 HIGH רק על blocking_hits; פסיקת false_positive מתועדת → LOW."""
    def _run(self, cv, verdict=None):
        with tempfile.TemporaryDirectory() as d:
            W = Path(d)
            (W / "CAPTION_VISION.json").write_text(json.dumps(cv), encoding="utf-8")
            if verdict:
                (W / "CAPTION_VISION_VERDICT.json").write_text(json.dumps(verdict), encoding="utf-8")
            f = []
            PF.check_caption_vision(f, W)
            return [x for x in f if x["check"] == "P20_caption_vision"]

    BASE = {"measured": True, "n_measured": 70, "f_ok_median": 0.85,
            "counts": {"garbled_cue": 2}, "blocking_flags": ["garbled_cue", "garbled"]}

    def test_below_block_threshold_is_not_high(self):
        cv = dict(self.BASE, blocking_hits={})
        sev = {x["severity"] for x in self._run(cv)}
        self.assertNotIn(PF.HIGH, sev)

    def test_real_blocking_hit_is_high(self):
        cv = dict(self.BASE, counts={"garbled_cue": 4}, blocking_hits={"garbled_cue": 4})
        self.assertIn(PF.HIGH, {x["severity"] for x in self._run(cv)})

    def test_legacy_output_without_hits_stays_cautious(self):
        self.assertIn(PF.HIGH, {x["severity"] for x in self._run(dict(self.BASE))})

    def test_documented_false_positive_is_low(self):
        cv = dict(self.BASE, counts={"garbled_cue": 4}, blocking_hits={"garbled_cue": 4})
        v = {"verdict": "false_positive", "evidence": "sheet read"}
        self.assertEqual({x["severity"] for x in self._run(cv, v)}, {PF.LOW})

    def test_verdict_without_evidence_is_ignored(self):
        cv = dict(self.BASE, counts={"garbled_cue": 4}, blocking_hits={"garbled_cue": 4})
        self.assertIn(PF.HIGH, {x["severity"] for x in self._run(cv, {"verdict": "false_positive"})})


class TestWaivers(unittest.TestCase):
    """v9.34 — פסיקה מתועדת מורידה ל-LOW רק עם גיליון קיים ומדיה זהה."""
    def _setup(self, d, **kw):
        W = Path(d)
        (W / "FINAL.mp4").write_bytes(b"x" * 10)
        (W / "sheet.jpg").write_bytes(b"j")
        wv = {"check": "P13_vision_bundle", "match": "V5_dead_silence",
              "evidence": "הצבעה = תשובה", "sheet": "sheet.jpg",
              "media": PF.media_stamp(W, "FINAL.mp4")}
        wv.update(kw)
        (W / "PREFLIGHT_WAIVERS.json").write_text(json.dumps([wv]), encoding="utf-8")
        return W

    def _f(self):
        return [PF.F("P13_vision_bundle", PF.HIGH, "V5_dead_silence נכשל", "x")]

    def test_valid_waiver_lowers(self):
        with tempfile.TemporaryDirectory() as d:
            W = self._setup(d); f = self._f(); PF.apply_waivers(f, W)
            self.assertEqual(f[0]["severity"], PF.LOW)

    def test_changed_media_voids_waiver(self):
        with tempfile.TemporaryDirectory() as d:
            W = self._setup(d); (W / "FINAL.mp4").write_bytes(b"y" * 11)
            f = self._f(); PF.apply_waivers(f, W)
            self.assertEqual(f[0]["severity"], PF.HIGH)

    def test_missing_sheet_voids_waiver(self):
        with tempfile.TemporaryDirectory() as d:
            W = self._setup(d, sheet="nope.jpg"); f = self._f(); PF.apply_waivers(f, W)
            self.assertEqual(f[0]["severity"], PF.HIGH)

    def test_non_matching_detail_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            W = self._setup(d, match="V1_first_frame"); f = self._f(); PF.apply_waivers(f, W)
            self.assertEqual(f[0]["severity"], PF.HIGH)


class TestPlanIsWhatWasBurned(unittest.TestCase):
    """v9.34 — broll_plan.json שלא נצרב (items_applied=[]) לא מייצר P1."""
    def _w(self, d, applied):
        W = Path(d)
        (W / "FINAL.mp4").write_bytes(b"x")
        (W / "broll_plan.json").write_text(json.dumps({"plan": [
            {"id": "a1", "insert_at": 1.0, "insert_end": 3.0},
            {"id": "b2", "insert_at": 5.0, "insert_end": 7.0}]}), encoding="utf-8")
        (W / "project_manifest.json").write_text(json.dumps(
            {"finish_prefs": {"broll": {"items_applied": applied}}}), encoding="utf-8")
        return W

    def test_skipped_broll_means_no_plan(self):
        with tempfile.TemporaryDirectory() as d:
            _, plan = PF.load_plan(self._w(d, []))
            self.assertEqual(plan, [])

    def test_partial_applied_filters(self):
        with tempfile.TemporaryDirectory() as d:
            _, plan = PF.load_plan(self._w(d, [{"id": "b2"}]))
            self.assertEqual([p["id"] for p in plan], ["b2"])

    def test_no_final_keeps_plan(self):
        with tempfile.TemporaryDirectory() as d:
            W = self._w(d, []); (W / "FINAL.mp4").unlink()
            _, plan = PF.load_plan(W)
            self.assertEqual(len(plan), 2)


if __name__ == "__main__":
    unittest.main()
