# -*- coding: utf-8 -*-
"""v9.37 — שכבת Motion Graphics: השערים שאינם תלויים בדפדפן/וידאו.

הזרקת כשל: כל בדיקה כאן נכשלת אם השער המתאים ב-motion_build מוסר או מוחלש
(MG4 שמקבל מילה מומצאת, MG1 שמקבל טקסט ברצועת הכתוביות, MG2 שמשווה פנים
לקופסאות מזמן אחר, MG3 שהופך לחוסם בלי כיול)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import motion_build as mb  # noqa: E402


def words(*pairs):
    return [{"word": w, "start": s, "end": s + 0.3} for w, s in pairs]


TR = words(("למה", 0.0), ("יש", 0.4), ("שתי", 1.0), ("העצמות", 1.3), ("באמה,", 1.7),
           ("הרדיוס", 2.2), ("והאולנה,", 2.6), ("תכתבו", 3.0), ("לנו", 3.3), ("בתגובות.", 3.5))


def plan(events, facts=None, duration=10.0, tail=0.0):
    return {"duration": duration, "tail": tail, "facts": facts or [], "events": events, "_path": "x"}


class TextFidelity(unittest.TestCase):
    def test_transcript_words_pass_with_hebrew_prefixes(self):
        p = plan([{"id": "a", "type": "forearm", "start": 0, "end": 3, "title": "שתי העצמות באמה",
                   "label_radius": "רדיוס", "label_ulna": "אולנה"}])
        self.assertTrue(mb.gate_text_fidelity(p, TR)["ok"])

    def test_invented_word_blocks(self):
        p = plan([{"id": "a", "type": "kinetic_title", "start": 0, "end": 2, "text": "שתי העצמות החזקות"}])
        g = mb.gate_text_fidelity(p, TR)
        self.assertFalse(g["ok"])
        self.assertIn("החזקות", g["detail"])

    def test_invented_number_blocks(self):
        p = plan([{"id": "s", "type": "stat", "start": 0, "end": 2, "value": 70, "unit": "אחוז", "label": "למה"}])
        self.assertFalse(mb.gate_text_fidelity(p, TR)["ok"])

    def test_fact_needs_source(self):
        ev = [{"id": "n", "type": "name_reveal", "start": 0, "end": 2, "name": "נבו ינאי", "role": "למה"}]
        self.assertFalse(mb.gate_text_fidelity(plan(ev, [{"text": "נבו ינאי"}]), TR)["ok"])
        self.assertTrue(mb.gate_text_fidelity(plan(ev, [{"text": "נבו ינאי", "source": "monday:1:אחראי"}]), TR)["ok"])

    def test_nested_texts_are_checked(self):
        p = plan([{"id": "p", "type": "poll", "start": 0, "end": 4,
                   "options": [{"text": "מתח מומצא", "at": 1}], "comment": {"text": "תכתבו לנו בתגובות", "at": 3}}])
        self.assertFalse(mb.gate_text_fidelity(p, TR)["ok"])


class Schema(unittest.TestCase):
    def test_unknown_template_and_bad_window(self):
        g = mb.gate_schema(plan([{"id": "a", "type": "nope", "start": 0, "end": 1},
                                 {"id": "b", "type": "stat", "start": 5, "end": 4}]))
        self.assertFalse(g["ok"])

    def test_tail_extends_valid_range(self):
        ev = [{"id": "e", "type": "end_card", "start": 10, "end": 13}]
        self.assertFalse(mb.gate_schema(plan(ev))["ok"])
        self.assertTrue(mb.gate_schema(plan(ev, tail=3.0))["ok"])

    def test_accent_must_be_list(self):
        # 22.10.26: accent כמחרוזת עבר את כל השערים ונפל רק ברינדור (MG6 — map is not a function)
        ev = {"id": "k", "type": "kinetic_title", "start": 0, "end": 2, "text": "3 שאלות"}
        self.assertFalse(mb.gate_schema(plan([dict(ev, accent="3")]))["ok"])
        self.assertTrue(mb.gate_schema(plan([dict(ev, accent=["3"])]))["ok"])


class Dosage(unittest.TestCase):
    def test_dosage_is_reporting_until_calibrated(self):
        ev = [{"id": str(i), "type": "chips", "start": i, "end": i + 0.9, "items": []} for i in range(9)]
        g = mb.gate_dosage(plan(ev))
        self.assertEqual(g["level"], "reporting")
        self.assertFalse(g["calibrated"])

    def test_overlap_by_design_is_not_tight(self):
        ev = [{"id": "h", "type": "kinetic_title", "start": 0, "end": 5},
              {"id": "c", "type": "chips", "start": 1.8, "end": 5, "items": []}]
        self.assertNotIn("צפופים", mb.gate_dosage(plan(ev))["detail"])


class SuppressWindows(unittest.TestCase):
    def test_bool_and_explicit_window(self):
        p = plan([{"id": "a", "type": "quote", "start": 1, "end": 3, "suppress_captions": True},
                  {"id": "b", "type": "poll", "start": 4, "end": 9, "suppress_captions": [4, 6]},
                  {"id": "c", "type": "chips", "start": 9, "end": 9.5}])
        self.assertEqual(mb.suppress_windows(p), [[1.0, 3.0], [4.0, 6.0]])


class MeasureGates(unittest.TestCase):
    def _m(self, box):
        return {"events": [{"id": "a", "type": "chips", "start": 0, "end": 2, "boxes": [box],
                            "samples": [{"t": 1.0, "boxes": [box]}]}],
                "fonts": [{"family": "Assistant", "weight": "800", "status": "loaded"},
                          {"family": "Ploni", "weight": "700", "status": "loaded"}], "errors": []}

    def test_text_in_caption_band_blocks(self):
        gs = {g["gate"]: g for g in mb.gates_from_measure(self._m({"x0": 100, "y0": 1200, "x1": 900, "y1": 1320, "text": "מתח"}))}
        self.assertFalse(gs["MG1_safe_zone"]["ok"])

    def test_textless_diagram_may_cover_frame(self):
        gs = {g["gate"]: g for g in mb.gates_from_measure(self._m({"x0": 0, "y0": 0, "x1": 1080, "y1": 1920, "text": ""}))}
        self.assertTrue(gs["MG1_safe_zone"]["ok"])

    def test_missing_brand_font_blocks(self):
        m = self._m({"x0": 100, "y0": 400, "x1": 900, "y1": 500, "text": "מתח"})
        m["fonts"][1]["status"] = "error"
        gs = {g["gate"]: g for g in mb.gates_from_measure(m)}
        self.assertFalse(gs["MG5_brand_fonts"]["ok"])


class Faces(unittest.TestCase):
    def test_faces_compared_at_same_time(self):
        box = {"x0": 300, "y0": 300, "x1": 800, "y1": 500, "text": "שאלה"}
        m = {"events": [{"id": "q", "type": "kinetic_title", "start": 0, "end": 4, "boxes": [box],
                         "samples": [{"t": 0.5, "boxes": [box]}, {"t": 3.5, "boxes": []}]}]}
        p = plan([{"id": "q", "type": "kinetic_title", "start": 0, "end": 4, "text": "למה"}])
        # פנים רק ב-3.5 (כשהטקסט כבר יצא) ⇒ אין חפיפה
        late = lambda video, t: ([[0.3, 0.15, 0.7, 0.27]] if t > 3 else [], "haar:test")
        self.assertTrue(mb.gate_faces("x.mp4", p, m, detect=late, dur=10.0)["ok"])
        # פנים ב-0.5 כשהטקסט על המסך ⇒ חוסם
        early = lambda video, t: ([[0.3, 0.15, 0.7, 0.27]] if t < 1 else [], "haar:test")
        self.assertFalse(mb.gate_faces("x.mp4", p, m, detect=early, dur=10.0)["ok"])

    def test_unmeasured_is_reported_not_silent_pass(self):
        box = {"x0": 300, "y0": 300, "x1": 800, "y1": 500, "text": "שאלה"}
        m = {"events": [{"id": "q", "type": "kinetic_title", "start": 0, "end": 2, "boxes": [box],
                         "samples": [{"t": 1.0, "boxes": [box]}]}]}
        p = plan([{"id": "q", "type": "kinetic_title", "start": 0, "end": 2, "text": "למה"}])
        g = mb.gate_faces("x.mp4", p, m, detect=lambda v, t: (None, "unavailable:no-cv2"), dur=10.0)
        self.assertFalse(g["measured"])
        self.assertEqual(g["level"], "reporting")


class CleanFaces(unittest.TestCase):
    def test_body_box_under_face_is_dropped_and_persistence_counts_frames(self):
        face = [0.43, 0.30, 0.62, 0.40]
        shorts = [0.31, 0.54, 0.86, 0.85]          # 590px "פנים" על המכנסיים (דמו 4.10.26)
        out = mb._clean_faces([[face], [face, shorts], [face]])
        self.assertIn(face, out)
        self.assertNotIn(shorts, out)

    def test_single_frame_blip_is_not_a_face(self):
        out = mb._clean_faces([[], [[0.1, 0.6, 0.3, 0.7]], []])
        self.assertEqual(out, [])


class PipelineWiring(unittest.TestCase):
    def test_finish_pipeline_runs_motion_before_music_and_filters_captions(self):
        src = (HERE.parent / "tools" / "local_finish_pipeline.py").read_text(encoding="utf-8")
        i_mg, i_music = src.index('st.step("motion")'), src.index('st.step("music")')
        self.assertLess(i_mg, i_music)
        self.assertIn("words_captions_mg.json", src)

    def test_layer_is_one_overlay_without_seek(self):
        src = (HERE.parent / "tools" / "motion_build.py").read_text(encoding="utf-8")
        body = src[src.index("def composite("):src.index("def _tile(")]
        self.assertEqual(body.count("overlay="), 1)
        self.assertNotIn('"-ss"', body)


class V938Templates(unittest.TestCase):
    """v9.38 — 13 תבניות חדשות + ערכות צבע + backdrop + telestrator עם פריים קפוא."""
    def test_every_type_has_a_js_template_and_back(self):
        import re
        js = "".join(t.read_text(encoding="utf-8") for t in (HERE.parent / "tools" / "motion" / "templates").glob("*.js"))
        defined = set(re.findall(r"REL\.define\('([a-z_]+)'", js))
        self.assertEqual(defined, mb.TYPES)

    def test_nested_texts_in_new_templates_are_checked(self):
        for ev in ({"winner": {"text": "אלוף מומצא", "at": 1}}, {"marks": [{"text": "חצות מומצאת", "at": 1}]},
                   {"labels": [{"text": "קו מומצא", "x": 100, "y": 400}]}, {"places": ["מומצא"]},
                   {"chip": {"text": "נוכח מומצא", "at": 1}}, {"by": "רופא מומצא"}):
            p = plan([{"id": "e", "type": "podium", "start": 0, "end": 3, **ev}])
            self.assertFalse(mb.gate_text_fidelity(p, TR)["ok"], ev)

    def test_fullscreen_and_fixed_events_skip_zone_resolution(self):
        evs = [{"id": "a", "type": "timeline", "start": 0, "end": 2, "bg": True, "label": "למה"},
               {"id": "b", "type": "telestrator", "start": 2, "end": 4},
               {"id": "c", "type": "kinetic_title", "start": 4, "end": 6, "text": "למה"}]
        p = plan(evs)
        calls = []
        det = lambda v, t: (calls.append(t) or [], "haar:test")
        mb.resolve_zones("x.mp4", p, detect=det, dur=10.0)
        self.assertTrue(all(4 <= t <= 6 for t in calls))
        self.assertNotIn("zone", evs[0]); self.assertNotIn("zone", evs[1]); self.assertIn(evs[2]["zone"], ("top", "body"))
        p2 = plan([dict(evs[2], zone=None)]); p2["backdrop"] = True
        calls.clear(); mb.resolve_zones("x.mp4", p2, detect=det, dur=10.0)
        self.assertEqual(calls, [])

    def test_freeze_frame_text_is_checked_against_the_frozen_frame(self):
        box = {"x0": 300, "y0": 300, "x1": 800, "y1": 500, "text": "באותו קו"}
        m = {"events": [{"id": "f", "type": "telestrator", "start": 2, "end": 4, "boxes": [box],
                         "samples": [{"t": 2.5, "boxes": [box]}]}]}
        p = plan([{"id": "f", "type": "telestrator", "start": 2, "end": 4, "freeze_at": 7.0}])
        # פנים רק בפריים הקפוא (7.0) — לא בזמן האירוע ⇒ חייב לחסום
        det = lambda v, t: ([[0.3, 0.15, 0.7, 0.27]] if abs(t - 7.0) < 0.01 else [], "haar:test")
        self.assertFalse(mb.gate_faces("x.mp4", p, m, detect=det, dur=10.0)["ok"])

    def test_personal_theme_and_backdrop_exist(self):
        css = (HERE.parent / "tools" / "motion" / "lib" / "rel-motion.css").read_text(encoding="utf-8")
        js = (HERE.parent / "tools" / "motion" / "lib" / "rel-motion.js").read_text(encoding="utf-8")
        self.assertIn('body[data-theme="personal"]{--rel-red:#0077B6', css)
        self.assertIn("plan.backdrop", js)
        self.assertIn("text-wrap:balance", css)


class CaptionsAcrossMgGap(unittest.TestCase):
    def test_short_word_does_not_join_across_suppressed_window(self):
        import captions_build as cb
        ws = [{"word": "עם", "start": 28.75, "end": 29.0}, {"word": "רוצים", "start": 31.83, "end": 32.1}]
        cues = cb.group_cues(ws)
        self.assertEqual([c["text"] for c in cues], ["עם", "רוצים"])
        self.assertLess(cues[0]["end"], 29.5)


class V939HarelFeedback(unittest.TestCase):
    """v9.39 — פסיקות הראל על 4 הדמואים (4.10.26): צבע, מלבן סביב תגיות, צלילים, מעברים, 20% הראל."""
    def test_color_tags_must_equal_base(self):
        orig = mb.base_color
        try:
            hlg = {"pix_fmt": "yuv420p", "color_range": "tv", "color_space": "bt2020nc",
                   "color_transfer": "arib-std-b67", "color_primaries": "bt2020"}
            bad = dict(hlg, color_space="bt709")
            mb.base_color = lambda v: hlg if v == "base" else bad
            g = mb.gate_color("base", "out")
            self.assertFalse(g["ok"]); self.assertEqual(g["level"], "blocking")
            mb.base_color = lambda v: hlg
            self.assertTrue(mb.gate_color("base", "out")["ok"])
        finally:
            mb.base_color = orig

    def test_composite_keeps_base_matrix_and_tags(self):
        src = (HERE.parent / "tools" / "motion_build.py").read_text(encoding="utf-8")
        body = src[src.index("def composite("):src.index("def _tile(")]
        self.assertIn("out_color_matrix", body)
        self.assertNotIn('"-colorspace", "bt709"', body)

    def test_sfx_thinned_varied_and_capped(self):
        evs = [{"id": "a", "type": "chips", "start": 0, "end": 9,
                "sfx": [{"at": t, "kind": k} for t, k in ((0.1, "whoosh"), (0.5, "pop"), (1.3, "hit"), (1.6, "pop"),
                                                           (2.6, "pop"), (3.6, "pop"), (5.0, "whoosh"), (6.2, "whoosh"))]}]
        kept, dropped = mb.plan_sfx(plan(evs))
        times = [a for a, _k, _d in kept]
        self.assertTrue(all(b - a >= mb.SFX_MIN_GAP for a, b in zip(times, times[1:])))
        for at, _k, _d in kept:
            self.assertLessEqual(sum(1 for x in times if 0 <= at - x < mb.SFX_CAP_WIN), mb.SFX_CAP_N)
        self.assertIn("hit", [k for _a, k, _d in kept])
        wh = [k for _a, k, _d in kept if k.startswith("whoosh")]
        self.assertEqual(len(set(wh)), len(wh))          # אותו whoosh לא חוזר ברצף
        self.assertTrue(dropped)

    def test_no_reveal_clips_the_shadow(self):
        js = "".join(t.read_text(encoding="utf-8") for t in (HERE.parent / "tools" / "motion" / "templates").glob("*.js"))
        self.assertNotIn("inset(0 0 0", js)
        self.assertNotIn("inset(0 100%", js)
        core = (HERE.parent / "tools" / "motion" / "lib" / "rel-motion.js").read_text(encoding="utf-8")
        self.assertIn("REL.CLIP", core)
        self.assertIn("yPercent:200", core)

    def test_full_mg_has_transitions_and_base_windows(self):
        core = (HERE.parent / "tools" / "motion" / "lib" / "rel-motion.js").read_text(encoding="utf-8")
        self.assertIn("REL.transitions", core)
        self.assertIn("base_windows", core)
        p = plan([{"id": "k", "type": "kinetic_title", "start": 0, "end": 5, "text": "למה"}], duration=50)
        p.update(backdrop=True, opaque=True, base_windows=[[10, 20]])
        self.assertFalse(mb.gate_schema(p)["ok"])         # חלונות בסיס דורשים אלפא
        p["opaque"] = False
        self.assertTrue(mb.gate_schema(p)["ok"])
        g = mb.gate_base_share(p)                          # 10ש מתוך 50 = 20% — היעד של הראל
        self.assertTrue(g["ok"]); self.assertAlmostEqual(g["share"], 0.2, places=2)
        p["base_windows"] = []
        self.assertFalse(mb.gate_base_share(p)["ok"])      # MG מלא בלי הראל במצלמה — מדווח


class NameSparkle(unittest.TestCase):
    """8.10.26 — האפקט הקבוע לשם מתאמן: קשת + נצנצים + צליל sparkle אוטומטי."""
    def test_registered_and_template_exists(self):
        self.assertIn("name_sparkle", mb.TYPES)
        self.assertTrue((mb.MOT / "templates" / "name_sparkle.js").exists())

    def test_auto_sparkle_sfx_replaces_entry_whoosh(self):
        evs = [{"id": "n", "type": "name_sparkle", "start": 2.0, "end": 5.0, "name": "נבו ינאי",
                "sfx": [{"at": 2.0, "kind": "whoosh"}]}]
        kept, _ = mb.plan_sfx(plan(evs))
        self.assertEqual([k for _, k, _ in kept], ["sparkle"])

    def test_sparkle_wins_over_near_sound(self):
        evs = [{"id": "a", "type": "chips", "start": 1.6, "end": 2.2, "items": [], "sfx": [{"at": 1.7, "kind": "pop"}]},
               {"id": "n", "type": "name_sparkle", "start": 2.0, "end": 5.0, "name": "נבו ינאי"}]
        kept, _ = mb.plan_sfx(plan(evs))
        self.assertEqual([k for _, k, _ in kept], ["sparkle"])

    def test_freeze_picker_exists_and_degrades(self):
        # בלי וידאו קריא ⇒ None (התבנית רצה בלי הקפאה), לא חריגה
        self.assertIsNone(mb.pick_smile_frame("/nonexistent.mp4", 0, 1))

    def test_attach_freezes_without_base_keeps_live(self):
        p = plan([{"id": "n", "type": "name_sparkle", "start": 2.0, "end": 5.0, "name": "נבו ינאי"}])
        mb.attach_freezes(p, None)
        self.assertNotIn("freeze_src", p["events"][0])

    def test_string_freeze_at_does_not_break_face_gate(self):
        p = plan([{"id": "n", "type": "name_sparkle", "start": 0, "end": 2, "name": "נבו ינאי", "freeze_at": "smile"}])
        g = mb.gate_faces("x.mp4", p, {"events": []}, detect=lambda v, t: ([], "stub"), dur=10)
        self.assertTrue(g["ok"])

    def test_propose_skips_team(self):
        import tempfile, json as _j
        with tempfile.TemporaryDirectory() as td:
            W = mb.Path(td)
            (W / "project_manifest.json").write_text(_j.dumps({"finish_prefs": {"motion": {"people": [
                {"name": "נבו ינאי", "role": "מתאמן"}, {"name": "הראל חיון", "role": "בעלים ומנהל"},
                {"name": "מישהו", "role": "x", "team": True}]}}}), encoding="utf-8")
            names = [c.get("name") for c in mb.propose(W)["candidates"] if c["type"] == "name_sparkle"]
        self.assertEqual(names, ["נבו ינאי"])

    def test_unflattering_pick_means_no_freeze(self):
        orig = mb.pick_smile_frame
        try:
            mb.pick_smile_frame = lambda *a, **k: {"t": 1.0, "flattering": False, "smile_bs": 0.1, "jaw": 0.4,
                                                    "yaw": 0.0, "zoom_origin": "50% 30%", "method": "best-face"}
            p = plan([{"id": "n", "type": "name_sparkle", "start": 0.5, "end": 3.0, "name": "נבו ינאי"}])
            notes = mb.attach_freezes(p, mb.Path("/nonexistent.mp4"))
            self.assertIsNone(p["events"][0]["freeze_at"])
            self.assertIn("אין חיוך מחמיא", " ".join(notes))
        finally:
            mb.pick_smile_frame = orig

    def test_insert_remaps_timeline(self):
        # הראל 8.10.26: הסרטון נעצר לקטע השם — כל מה שאחרי זז ב-hold, המילים זזות, האורך מתארך
        p = plan([{"id": "n", "type": "name_sparkle", "start": 2.0, "end": 5.0, "name": "נבו ינאי",
                   "freeze_src": "data:x", "freeze_at": 2.8},
                  {"id": "c", "type": "chips", "start": 6.0, "end": 8.0, "items": [{"text": "א", "at": 6.5}],
                   "sfx": [{"at": 6.0, "kind": "pop"}], "suppress_captions": [6.0, 7.0]},
                  {"id": "k", "type": "kinetic_title", "start": 0.2, "end": 1.5, "text": "א", "word_times": [0.2, 0.6]}])
        p["duration"] = 10.0
        ins = mb.plan_inserts(p)
        self.assertEqual([(i["at"], i["dur"]) for i in ins], [(2.0, mb.INSERT_HOLD)])
        mb.remap_for_inserts(p, ins)
        ev = {e["id"]: e for e in p["events"]}
        H = mb.INSERT_HOLD
        self.assertEqual(ev["n"]["end"], round(2.0 + H, 3))
        self.assertEqual(ev["c"]["start"], round(6.0 + H, 3))
        self.assertEqual(ev["c"]["items"][0]["at"], round(6.5 + H, 3))
        self.assertEqual(ev["c"]["sfx"][0]["at"], round(6.0 + H, 3))
        self.assertEqual(ev["c"]["suppress_captions"], [round(6.0 + H, 3), round(7.0 + H, 3)])
        self.assertEqual(ev["k"]["word_times"], [0.2, 0.6])
        self.assertEqual(p["duration"], round(10.0 + H, 3))
        w = mb.shift_words([{"word": "א", "start": 1.0, "end": 1.4}, {"word": "ב", "start": 2.1, "end": 2.5}], ins)
        self.assertEqual((w[0]["start"], w[1]["start"]), (1.0, round(2.1 + H, 3)))

    def test_insert_false_keeps_overlay(self):
        p = plan([{"id": "n", "type": "name_sparkle", "start": 2.0, "end": 5.0, "name": "נבו ינאי",
                   "freeze_src": "data:x", "freeze_at": 2.8, "insert": False}])
        self.assertEqual(mb.plan_inserts(p), [])

    def test_opt_out(self):
        evs = [{"id": "n", "type": "name_sparkle", "start": 2.0, "end": 5.0, "name": "נבו ינאי", "no_auto_sfx": True}]
        self.assertEqual(mb.plan_sfx(plan(evs))[0], [])


if __name__ == "__main__":
    unittest.main()


class WordAnchorsV949(unittest.TestCase):
    """v9.49 (17.10.26) — עוגני מילה: זמני MG נגזרים מ-words_final ולא מחושבים בראש.
    הזרקת כשל: resolve_anchors שמתעלם מ-n / מקבל התאמת שורש לפני מדויקת / MG12 שלא חוסם ⇒ נכשל."""
    W = words(("השאלה", 0.0), ("האלה", 1.0), ("לא", 2.0), ("רק", 2.4), ("לא", 3.0), ("וכושר,", 4.0), ("וכושר", 5.0))

    def _p(self, ev, bw=None):
        p = plan([ev]); p["base_windows"] = bw or []; mb.resolve_anchors(p, self.W); return p

    def test_exact_before_stem(self):
        # L140: "השאלה"→שורש "אלה" תפס את "האלה" כשהעוגן חיפש מילה מאוחרת יותר
        p = self._p({"id": "a", "type": "stat", "start": {"w": "האלה"}, "end": 3, "value": 1})
        self.assertEqual(p["events"][0]["start"], 1.0)

    def test_occurrence_and_after(self):
        p = self._p({"id": "a", "type": "stat", "start": {"w": "לא", "n": 2}, "end": {"w": "רק", "after": 2.1}, "value": 1})
        self.assertEqual((p["events"][0]["start"], p["events"][0]["end"]), (3.0, 2.4))

    def test_nested_lists_and_base_windows(self):
        p = self._p({"id": "a", "type": "board_list", "start": 0, "end": 6,
                     "items": [{"text": "x", "at": {"w": "וכושר", "n": 2}}]}, bw=[[0, {"w": "רק"}]])
        self.assertEqual(p["events"][0]["items"][0]["at"], 5.0)
        self.assertEqual(p["base_windows"][0][1], 2.4)

    def test_missing_anchor_blocks(self):
        p = self._p({"id": "a", "type": "stat", "start": {"w": "מומצא"}, "end": 3, "value": 1})
        g = mb.gate_anchors(p)
        self.assertFalse(g["ok"]); self.assertEqual(g["level"], "blocking")

    def test_pipe_is_line_break_not_word(self):
        p = plan([{"id": "a", "type": "board_title", "start": 0, "end": 3, "text": "לא רק | וכושר"}])
        self.assertTrue(mb.gate_text_fidelity(p, self.W)["ok"])


class NoNegativeTransitionL139(unittest.TestCase):
    """L139: מעבר בזמן שלילי (חלון בסיס שמתחיל ב-0) הזיז את כל הטיימליין ב-1.27ש. אוכף בקוד הליבה."""
    def test_core_guards(self):
        js = (HERE.parent / "tools" / "motion" / "lib" / "rel-motion.js").read_text(encoding="utf-8")
        self.assertIn("if (s0 > 0.3) evs.push", js)
        self.assertIn("Math.max(0, t0 - 0.24)", js)

    def test_board_templates_registered(self):
        for t in ("board_title", "spectrum", "board_list", "board_strike", "board_steps", "board_years"):
            self.assertIn(t, mb.FULL_TYPES)
        for t in ("board_poll", "source_tag"):
            self.assertIn(t, mb.OVERLAY_TYPES)
