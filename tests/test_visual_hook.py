#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_visual_hook.py — Visual Hook Engine: חוזים, בחירה, digest ומדיניות (11.9.26).

בלי מדיה ובלי ffmpeg: הקשר וניתוח נבנים כדאטה, כדי שכל כלל בחירה ייבדק
בבידוד. הבדיקות שמריצות ffmpeg אמיתי — ב-test_visual_hook_render.py / _qa.py.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
TOOLS = SYSDIR / "tools"
sys.path.insert(0, str(TOOLS))

from relvid import visual_hook as VH          # noqa: E402

Z = "sha256:" + "0" * 64


def crop_cue(start=40, peak=55, hold_end=85, end=101, scale=1.06):
    r = VH.crop_rect(scale, 0.5, 0.5)
    return {"id": "cue_1", "kind": "crop", "start_frame": start, "end_frame": end,
            "interpolation": "smoothstep",
            "keyframes": [{"frame": start, "rect": list(VH.IDENTITY)},
                          {"frame": peak, "rect": r}, {"frame": hold_end, "rect": r},
                          {"frame": end - 1, "rect": list(VH.IDENTITY)}]}


def base_plan(recipe="SMART_PUNCH_IN", cues=None, fc=600):
    p = {"schema_version": 1, "project_id": "prj_test", "input_digest": Z, "policy_digest": Z,
         "reservation_digest": Z, "recipe": recipe, "recipe_version": 1, "candidate_id": "cand_000000000000",
         "timeline": {"axis": "body_final", "fps_num": 30, "fps_den": 1, "frame_count": fc, "intro_frames": 0},
         "audio_mode": "preserve",
         "evidence": {"word_ids": [0, 1], "quote": "שלום עולם", "grade": "supported", "reviewed_subjects": []},
         "assets": [], "cues": [crop_cue()] if cues is None and recipe != "NO_OP" else (cues or []),
         "declared_transitions": [], "selection": {"actor": "harel", "reason_codes": ["operator_selected"]}}
    p["plan_digest"] = VH.digest_plan(p)
    return p


def fake_context(**over):
    words = [{"id": i, "word": w, "start": s, "end": s + 0.4} for i, (w, s) in
             enumerate([("תושבי", 0.2), ("אריאל", 0.7), ("והסביבה,", 1.2), ("הגוף", 2.0),
                        ("שלכם", 2.5), ("להוכיח", 3.2), ("כלום.", 3.7)])]
    ctx = {"schema_version": 1, "project_id": "prj_test", "workdir": "/nonexistent",
           "body_path": "/nonexistent/EXPORT.mp4",
           "body_probe": {"width": 1080, "height": 1920, "fps_num": 30, "fps_den": 1,
                          "frame_count": 900, "duration": 30.0},
           "words": words, "words_provenance": {"ok": True, "reasons": [], "alignment": None},
           "reservations": [], "reservation_digest": VH.digest([]),
           "intro": {"present": False, "id": None, "source": None, "intro_frames": 0},
           "brand": "rel", "content_type": "value", "speed": 1.0,
           "input_digest": Z, "policy_digest": Z}
    ctx.update(over)
    return ctx


def fake_analysis(ctx, *, faces_per=1, mad=2.0, drift=0.005, entrance=False, cuts=None,
                  motion_box=(0.3, 0.55, 0.4, 0.25), face=(0.4, 0.25, 0.2, 0.12), anchor=True):
    faces = [{"frame": f, "boxes": [list(face)] * faces_per if faces_per else []}
             for f in range(0, 300, 5)]
    if faces_per >= 2:
        faces = [{"frame": f, "boxes": [list(face), [0.05, 0.1, 0.1, 0.06]]} for f in range(0, 300, 5)]
    a = {"schema_version": 1, "project_id": ctx["project_id"], "input_digest": ctx["input_digest"],
         "timeline": {"axis": "body_final", "fps_num": 30, "fps_den": 1,
                      "frame_count": ctx["body_probe"]["frame_count"], "intro_frames": 0},
         "hook": {"word_ids": [0, 1, 2, 3, 4, 5, 6], "quote": " ".join(w["word"] for w in ctx["words"]),
                  "start": 0.2, "end": 4.1,
                  "anchor": ({"word_id": 5, "word": "להוכיח", "start": 3.2, "end": 3.6} if anchor else None)},
         "measurements": {"motion_mad": [mad] * 300, "hard_cuts": cuts or [],
                          "motion_boxes_15f": [list(motion_box)] * 20,
                          "camera": {"scale_drift_max": drift}, "faces": faces,
                          "first_face_frame": 30 if entrance else 0,
                          "intentional_entrance": entrance,
                          "multi_face_ratio_opening": 1.0 if faces_per >= 2 else 0.0},
         "reservations": ctx["reservations"], "evidence": [], "unknowns": []}
    return a


class TestRegistryAndPolicy(unittest.TestCase):
    def test_registry_has_eleven_entries_only_mvp_runnable(self):
        reg = VH.load_registry()
        self.assertEqual(len(reg), 11)
        runnable = sorted(r for r in reg if VH.recipe_runnable(reg, r))
        self.assertEqual(runnable, ["NO_OP", "SMART_PUNCH_IN"])

    def test_fallbacks_terminate_in_noop(self):
        reg = VH.load_registry()
        for rid in reg:
            cur, seen = rid, set()
            while cur != "NO_OP":
                self.assertNotIn(cur, seen)
                seen.add(cur)
                fb = reg[cur]["fallbacks"]
                cur = "NO_OP" if "NO_OP" in fb else fb[0]

    def test_broken_fallback_chain_rejected(self):
        doc = json.loads(VH.REGISTRY_PATH.read_text(encoding="utf-8"))
        for r in doc["recipes"]:
            if r["id"] == "FREEZE_CALLOUT":
                r["fallbacks"] = ["FREEZE_CALLOUT"]
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "r.json"
            p.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaises(VH.HookError):
                VH.load_registry(p)

    def test_policy_default_off_and_no_auto_cohort(self):
        pol = VH.load_policy()
        self.assertEqual(pol["default_mode"], "off")
        self.assertEqual(pol["auto_cohorts"], [])
        self.assertIsNone(pol["auto_min_margin"])
        self.assertFalse(pol["crop_envelope"]["calibrated"])
        self.assertEqual(pol["max_accents"], 0)

    def test_policy_digest_ignores_doc_fields(self):
        pol = VH.load_policy()
        p2 = dict(pol, _doc="שונה")
        self.assertEqual(VH.policy_digest(pol), VH.policy_digest(p2))
        p3 = copy.deepcopy(pol)
        p3["crop_envelope"]["margin_frac"] = 0.05
        self.assertNotEqual(VH.policy_digest(pol), VH.policy_digest(p3))


class TestDigest(unittest.TestCase):
    def test_key_order_independent(self):
        self.assertEqual(VH.digest({"a": 1, "b": [1, 2]}), VH.digest({"b": [1, 2], "a": 1}))

    def test_float_normalization(self):
        self.assertEqual(VH.digest({"x": 1.0}), VH.digest({"x": 1}))
        self.assertEqual(VH.digest({"x": 0.1234564}), VH.digest({"x": 0.123456}))

    def test_nan_rejected(self):
        with self.assertRaises(VH.HookError):
            VH.digest({"x": float("nan")})

    def test_plan_digest_excludes_its_own_field(self):
        p = base_plan()
        d = p["plan_digest"]
        p["plan_digest"] = "sha256:" + "f" * 64
        self.assertEqual(VH.digest_plan(p), d)


class TestPlanShape(unittest.TestCase):
    def assertInvalid(self, plan, needle=None):
        errs = VH.validate_plan_shape(plan)
        self.assertTrue(errs, "expected errors")
        if needle:
            self.assertTrue(any(needle in e for e in errs), errs)

    def test_valid_crop_and_noop(self):
        self.assertEqual(VH.validate_plan_shape(base_plan()), [])
        self.assertEqual(VH.validate_plan_shape(base_plan("NO_OP")), [])

    def test_unknown_schema_version(self):
        p = base_plan(); p["schema_version"] = 2
        self.assertInvalid(p, "schema_version")

    def test_unknown_key_like_filter_string(self):
        p = base_plan(); p["ffmpeg_filter"] = "drawtext=text=x"
        self.assertInvalid(p, "מפתחות לא מוכרים")

    def test_nan_in_rect(self):
        p = base_plan(); p["cues"][0]["keyframes"][1]["rect"][0] = float("nan")
        self.assertInvalid(p)

    def test_non_monotonic_keyframes(self):
        p = base_plan(); p["cues"][0]["keyframes"][2]["frame"] = 50
        self.assertInvalid(p, "עולים")

    def test_out_of_range_frames(self):
        p = base_plan(fc=80)
        self.assertInvalid(p, "טווח")

    def test_wrong_aspect(self):
        p = base_plan(); p["cues"][0]["keyframes"][1]["rect"] = [0.02, 0.02, 0.96, 0.9]
        self.assertInvalid(p, "יחס")

    def test_rect_outside_frame(self):
        p = base_plan(); p["cues"][0]["keyframes"][1]["rect"] = [0.1, 0.0, 0.95, 0.95]
        self.assertInvalid(p, "חורג")

    def test_scale_above_registry_max(self):
        p = base_plan(cues=[crop_cue(scale=1.2)])
        self.assertInvalid(p, "scale")

    def test_exit_must_be_identity(self):
        p = base_plan(); p["cues"][0]["keyframes"][-1]["rect"] = VH.crop_rect(1.02, 0.5, 0.5)
        self.assertInvalid(p, "זהות")

    def test_noop_requires_empty_arrays(self):
        p = base_plan("NO_OP"); p["cues"] = [crop_cue()]
        self.assertInvalid(p, "NO_OP")

    def test_audio_mode_must_preserve(self):
        p = base_plan(); p["audio_mode"] = "replace"
        self.assertInvalid(p, "preserve")

    def test_disabled_recipe_rejected(self):
        p = base_plan("PAYOFF_PREVIEW", cues=[])
        self.assertInvalid(p, "לא משוחרר")

    def test_unknown_recipe_rejected(self):
        p = base_plan("MAGIC_ZOOM", cues=[])
        self.assertInvalid(p, "לא מוכר")

    def test_bad_asset_path_and_hash(self):
        p = base_plan("NO_OP")
        p["assets"] = [{"id": "a", "sha256": "md5:x", "approved_root_relative_path": "../../etc/passwd",
                        "source_frame_range": [0, 10], "role": "x"}]
        errs = VH.validate_plan_shape(p)
        self.assertTrue(any("נתיב" in e for e in errs) and any("checksum" in e for e in errs), errs)

    def test_two_cues_is_an_accent_and_rejected(self):
        p = base_plan(cues=[crop_cue(), crop_cue(start=150, peak=165, hold_end=180, end=200)])
        self.assertInvalid(p, "בדיוק cue אחד")

    def test_tampered_digest_detected(self):
        p = base_plan()
        p["cues"][0]["keyframes"][1]["rect"] = VH.crop_rect(1.04, 0.5, 0.5)
        errs = VH.validate_plan(p)
        self.assertTrue(any("plan_digest" in e for e in errs), errs)


class TestSemanticValidation(unittest.TestCase):
    def test_input_digest_change_is_review_stale(self):
        ctx = fake_context()
        p = base_plan(fc=900)
        p["evidence"]["word_ids"] = [0, 1]
        p["evidence"]["quote"] = "תושבי אריאל"
        p["reservation_digest"] = ctx["reservation_digest"]
        p["plan_digest"] = VH.digest_plan(p)
        self.assertEqual(VH.validate_plan(p, ctx), [])
        ctx2 = fake_context(input_digest="sha256:" + "1" * 64)
        errs = VH.validate_plan(p, ctx2)
        self.assertEqual(VH.stale_code(errs), "HOOK_REVIEW_STALE")

    def test_reservation_overlap_rejected(self):
        resv = [{"kind": "broll", "start_frame": 60, "end_frame": 120, "ref": "x.mp4"}]
        ctx = fake_context(reservations=resv, reservation_digest=VH.digest(resv))
        p = base_plan(fc=900)
        p["evidence"].update(word_ids=[0], quote="תושבי")
        p["reservation_digest"] = ctx["reservation_digest"]
        p["plan_digest"] = VH.digest_plan(p)
        errs = VH.validate_plan(p, ctx)
        self.assertTrue(any("שכבה מוגנת" in e for e in errs), errs)

    def test_reservation_change_outside_cue_keeps_approval(self):
        ctx = fake_context()
        p = base_plan(fc=900)
        p["evidence"].update(word_ids=[0], quote="תושבי")
        p["reservation_digest"] = ctx["reservation_digest"]
        p["plan_digest"] = VH.digest_plan(p)
        far = [{"kind": "broll", "start_frame": 600, "end_frame": 700, "ref": "other.mp4"}]
        ctx2 = fake_context(reservations=far, reservation_digest=VH.digest(far))
        self.assertEqual(VH.validate_plan(p, ctx2), [])
        near = [{"kind": "broll", "start_frame": 105, "end_frame": 200, "ref": "x.mp4"}]
        ctx3 = fake_context(reservations=near, reservation_digest=VH.digest(near))
        self.assertEqual(VH.stale_code(VH.validate_plan(p, ctx3)), "HOOK_REVIEW_STALE")

    def test_quote_must_match_words(self):
        ctx = fake_context()
        p = base_plan(fc=900)
        p["evidence"].update(word_ids=[0, 1], quote="מילים שלא נאמרו")
        p["reservation_digest"] = ctx["reservation_digest"]
        p["plan_digest"] = VH.digest_plan(p)
        self.assertTrue(any("quote" in e for e in VH.validate_plan(p, ctx)))

    def test_treatment_requires_word_provenance(self):
        ctx = fake_context(words_provenance={"ok": False, "reasons": ["words_exceed_body"]})
        p = base_plan(fc=900)
        p["evidence"].update(word_ids=[0], quote="תושבי")
        p["reservation_digest"] = ctx["reservation_digest"]
        p["plan_digest"] = VH.digest_plan(p)
        self.assertTrue(any("מאומתות-דור" in e for e in VH.validate_plan(p, ctx)))


class TestCandidatesAndSelection(unittest.TestCase):
    def setUp(self):
        self.reg = VH.load_registry()
        self.pol = VH.load_policy()

    def _cands(self, ctx=None, **kw):
        ctx = ctx or fake_context()
        return ctx, VH.discover(ctx, fake_analysis(ctx, **kw), self.reg, self.pol)

    def test_static_single_subject_is_eligible(self):
        ctx, c = self._cands()
        crop = next(x for x in c if x["recipe"] == "SMART_PUNCH_IN")
        self.assertTrue(crop["eligible"], crop["reason_codes"])
        self.assertEqual(crop["evidence_grade"], "supported")
        cue = crop["cues"][0]
        self.assertEqual(cue["keyframes"][0]["rect"], VH.IDENTITY)
        self.assertEqual(cue["keyframes"][-1]["frame"], cue["end_frame"] - 1)

    def test_noop_always_present_and_eligible(self):
        _ctx, c = self._cands(faces_per=0)
        noop = next(x for x in c if x["recipe"] == "NO_OP")
        self.assertTrue(noop["eligible"])

    def test_motion_is_not_payoff(self):
        _ctx, c = self._cands(mad=40.0)
        crop = next(x for x in c if x["recipe"] == "SMART_PUNCH_IN")
        self.assertFalse(crop["eligible"])
        self.assertIn("strong_motion", crop["reason_codes"])

    def test_unknown_subject_selects_noop(self):
        ctx, c = self._cands(faces_per=0)
        sel, why = VH.select(ctx, c, None, "shadow", self.pol)
        self.assertEqual(sel["recipe"], "NO_OP")
        self.assertIn("semantic_unknown", sel["reason_codes"])

    def test_multi_person_selects_noop(self):
        ctx, c = self._cands(faces_per=2)
        sel, _ = VH.select(ctx, c, None, "shadow", self.pol)
        self.assertEqual(sel["recipe"], "NO_OP")
        self.assertIn("multi_person", sel["reason_codes"])

    def test_full_intro_defaults_to_noop(self):
        ctx = fake_context(intro={"present": True, "id": "muscle-man", "source": "title", "intro_frames": 304})
        ctx, c = self._cands(ctx)
        sel, _ = VH.select(ctx, c, None, "shadow", self.pol)
        self.assertEqual(sel["recipe"], "NO_OP")
        self.assertIn("fixed_intro_present", sel["reason_codes"])

    def test_intentional_entrance_protected(self):
        _ctx, c = self._cands(entrance=True)
        self.assertIn("intentional_entrance", next(x for x in c if x["recipe"] == "NO_OP")["reason_codes"])

    def test_existing_camera_push_selects_noop(self):
        _ctx, c = self._cands(drift=0.2)
        self.assertIn("existing_camera_motion", next(x for x in c if x["recipe"] == "SMART_PUNCH_IN")["reason_codes"])

    def test_unsafe_crop_when_motion_reaches_edges(self):
        _ctx, c = self._cands(motion_box=(0.0, 0.3, 1.0, 0.6))
        crop = next(x for x in c if x["recipe"] == "SMART_PUNCH_IN")
        self.assertIn("unsafe_crop", crop["reason_codes"])

    def test_broll_reservation_shortens_hold_or_blocks(self):
        resv = [{"kind": "broll", "start_frame": 118, "end_frame": 200, "ref": "b.mp4"}]
        ctx = fake_context(reservations=resv, reservation_digest=VH.digest(resv))
        _ctx, c = self._cands(ctx)
        crop = next(x for x in c if x["recipe"] == "SMART_PUNCH_IN")
        if crop["eligible"]:
            self.assertLessEqual(crop["cues"][0]["end_frame"], 118)
        else:
            self.assertIn("reservation_conflict", crop["reason_codes"])

    def test_stale_words_block_treatment(self):
        ctx = fake_context(words_provenance={"ok": False, "reasons": ["words_audio_offset"], "alignment": None})
        _ctx, c = self._cands(ctx)
        self.assertIn("stale_transcript", next(x for x in c if x["recipe"] == "SMART_PUNCH_IN")["reason_codes"])

    def test_disabled_recipes_never_eligible(self):
        _ctx, c = self._cands()
        for x in c:
            if x["recipe"] not in ("NO_OP", "SMART_PUNCH_IN"):
                self.assertFalse(x["eligible"])

    def test_select_ignores_high_score_on_unreleased_recipe(self):
        ctx, c = self._cands()
        fake = copy.deepcopy(next(x for x in c if x["recipe"] == "SMART_PUNCH_IN"))
        fake.update(recipe="PAYOFF_PREVIEW", candidate_id="cand_ffffffffffff", eligible=True,
                    score={"net": 99.0})
        sel, _ = VH.select(ctx, c + [fake], None, "shadow", self.pol)
        self.assertNotEqual(sel["recipe"], "PAYOFF_PREVIEW")

    def test_explicit_disable_dominates(self):
        ctx, c = self._cands()
        sel, why = VH.select(ctx, c, {"enabled": False, "selected_candidate_id": c[1]["candidate_id"]},
                             "auto", self.pol)
        self.assertEqual(sel["recipe"], "NO_OP")
        self.assertEqual(why["reason_codes"], ["explicit_disabled"])

    def test_auto_without_approved_cohort_is_noop(self):
        ctx, c = self._cands()
        sel, why = VH.select(ctx, c, None, "auto", self.pol)
        self.assertEqual(sel["recipe"], "NO_OP")
        self.assertIn("auto_cohort_not_approved", why["reason_codes"])

    def test_shadow_suggests_but_never_applies(self):
        ctx, c = self._cands()
        sel, why = VH.select(ctx, c, None, "shadow", self.pol)
        self.assertEqual(sel["recipe"], "SMART_PUNCH_IN")
        plan = VH.make_plan(ctx, fake_analysis(ctx), sel, why)
        rep = VH.build_report(ctx, fake_analysis(ctx), c, sel, why, plan, mode="shadow", applied=False)
        self.assertFalse(rep["applied"])
        self.assertEqual(rep["label_he"], "פתיחה חזותית: ללא שינוי")
        self.assertFalse(rep["claims_retention_uplift"])

    def test_deterministic_plan(self):
        ctx, c1 = self._cands()
        _ctx, c2 = self._cands()
        s1, w1 = VH.select(ctx, c1, None, "shadow", self.pol)
        s2, w2 = VH.select(ctx, c2, None, "shadow", self.pol)
        a = fake_analysis(ctx)
        self.assertEqual(VH.make_plan(ctx, a, s1, w1)["plan_digest"], VH.make_plan(ctx, a, s2, w2)["plan_digest"])

    def test_generated_plan_validates(self):
        ctx, c = self._cands()
        sel, why = VH.select(ctx, c, None, "shadow", self.pol)
        plan = VH.make_plan(ctx, fake_analysis(ctx), sel, why)
        self.assertEqual(VH.validate_plan_shape(plan), [])


class TestInterpolation(unittest.TestCase):
    def test_identity_outside_and_at_boundaries(self):
        c = crop_cue()
        self.assertEqual(VH.rect_at(c, 39), VH.IDENTITY)
        self.assertEqual([round(v, 9) for v in VH.rect_at(c, 40)], VH.IDENTITY)
        self.assertEqual(VH.rect_at(c, 100), VH.IDENTITY)
        self.assertEqual(VH.rect_at(c, 101), VH.IDENTITY)

    def test_peak_and_monotonic_ramp(self):
        c = crop_cue()
        w = [VH.rect_at(c, f)[2] for f in range(40, 56)]
        self.assertTrue(all(b <= a + 1e-12 for a, b in zip(w, w[1:])))
        self.assertAlmostEqual(VH.rect_at(c, 60)[2], 1 / 1.06, places=5)

    def test_smoothstep_has_zero_slope_at_ends(self):
        self.assertAlmostEqual(VH.smoothstep(0.0), 0.0)
        self.assertAlmostEqual(VH.smoothstep(1.0), 1.0)
        self.assertLess(VH.smoothstep(0.02), 0.002)


class TestWordsProvenance(unittest.TestCase):
    def test_words_beyond_body_are_stale(self):
        w = [{"id": 0, "word": "a", "start": 0.0, "end": 1.0}, {"id": 1, "word": "b", "start": 40, "end": 41}]
        self.assertIn("words_exceed_body", VH.words_provenance(w, {"duration": 30.0})["reasons"])

    def test_words_ending_early_are_stale(self):
        w = [{"id": 0, "word": "a", "start": 0.0, "end": 1.0}]
        self.assertIn("words_end_early", VH.words_provenance(w, {"duration": 30.0})["reasons"])

    def test_matching_words_ok(self):
        w = [{"id": 0, "word": "a", "start": 0.0, "end": 1.0}, {"id": 1, "word": "b", "start": 28, "end": 29.8}]
        self.assertTrue(VH.words_provenance(w, {"duration": 30.0})["ok"])


class TestEditToken(unittest.TestCase):
    def _w(self, t):
        w = Path(t)
        (w / "edl.json").write_text(json.dumps({"review": {"cuts": [[1, 2]], "hook_move": None, "speed": 1.0},
                                                "keep_segments": [{"start": 0, "end": 1}]}), encoding="utf-8")
        (w / "revisions").mkdir()
        (w / "revisions" / "index.json").write_text(json.dumps({"head": "rev_a"}), encoding="utf-8")
        return w

    def test_revision_head_change_without_content_change_keeps_token(self):
        with tempfile.TemporaryDirectory() as t:
            w = self._w(t)
            a = VH.edit_token(w)
            (w / "revisions" / "index.json").write_text(json.dumps({"head": "rev_b"}), encoding="utf-8")
            self.assertEqual(a, VH.edit_token(w))

    def test_cut_or_transcript_change_changes_token(self):
        with tempfile.TemporaryDirectory() as t:
            w = self._w(t)
            a = VH.edit_token(w)
            (w / "edited.txt").write_text("טקסט מתוקן", encoding="utf-8")
            b = VH.edit_token(w)
            self.assertNotEqual(a, b)
            e = json.loads((w / "edl.json").read_text(encoding="utf-8"))
            e["review"]["cuts"] = [[1, 3]]
            (w / "edl.json").write_text(json.dumps(e), encoding="utf-8")
            self.assertNotEqual(b, VH.edit_token(w))


if __name__ == "__main__":
    unittest.main()
