# -*- coding: utf-8 -*-
"""שער ההמחשה — מינון, עוגן, אזורי מגן, ואימות ישות→אזור.

הראל 21.8.26: *"זה אחלה וצריכים להשתמש בזה בחוכמה ובמינון נכון. בגג פעם
אחת או שניים במקרים חריגים בסרטון ולא בכל סרטון."* + *"הסימונים על השרירים
עכשיו לא היו מדויקים כשהוא ציין אותם."*

הבדיקות כאן הן **הזרקת-כשל**: לכל שער יש מקרה שבו הוא חייב לחסום, ולא רק
מקרה שבו הוא עובר. שער שאי אפשר להכשיל אינו שער.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import illustration_gate as IG  # noqa: E402


DUR = 56.0
KEEPS = [{"start": 0.0, "end": DUR}]

FOUR_MUSCLES = {
    "start": 20.0, "end": 27.0,
    "text": "זה לא שריר אחד, אלא קבוצה של ארבעה שרירים — אינפרספינטוס, "
            "סופרספינטוס, סאבסקפולריס וטרס מינור",
}
PLAIN = {"start": 30.0, "end": 36.0,
         "text": "בואו נדבר על מה שקורה אצלנו במועדון בשבוע הקרוב"}
MECH = {"start": 38.0, "end": 44.0,
        "text": "התפקיד של המנגנון הזה הוא לייצב את המפרק לאורך כל טווח התנועה"}


def manifest(ct="value"):
    return {"content_type": ct}


class TestEligibility(unittest.TestCase):
    def test_conversion_is_blocked(self):
        v = IG.decide(manifest("conversion"), {}, [FOUR_MUSCLES], KEEPS, DUR)
        self.assertEqual(v["decision"], "none")
        self.assertFalse(v["gates"][0]["ok"])

    def test_unknown_content_type_is_blocked_by_default(self):
        """נכשל-סגור: מה שלא ברשימה לא מקבל המחשה."""
        v = IG.decide(manifest("קמפיין-חדש"), {}, [FOUR_MUSCLES], KEEPS, DUR)
        self.assertEqual(v["n"], 0)

    def test_value_content_is_eligible(self):
        v = IG.decide(manifest("value"), {}, [FOUR_MUSCLES], KEEPS, DUR)
        self.assertTrue(v["gates"][0]["ok"])


class TestCandidates(unittest.TestCase):
    def test_picks_the_enumerated_anatomy_sentence(self):
        v = IG.decide(manifest(), {}, [PLAIN, FOUR_MUSCLES], KEEPS, DUR)
        self.assertEqual(v["n"], 1)
        self.assertIn("anatomy", v["picks"][0]["entity_classes"])

    def test_sentence_without_unfilmable_entity_is_not_a_candidate(self):
        v = IG.decide(manifest(), {}, [PLAIN], KEEPS, DUR)
        self.assertEqual(v["n"], 0)
        self.assertEqual(v["n_candidates"], 0)

    def test_quote_anchor_present_on_every_pick(self):
        """IL2 — המחשה בלי ציטוט מהמשפט היא קישוט."""
        v = IG.decide(manifest(), {}, [FOUR_MUSCLES], KEEPS, DUR)
        for p in v["picks"]:
            self.assertTrue(p["quote"], "המחשה בלי ציטוט")

    def test_short_run_is_rejected(self):
        short = dict(FOUR_MUSCLES, start=20.0, end=21.4)
        v = IG.decide(manifest(), {}, [short], KEEPS, DUR)
        self.assertEqual(v["n"], 0)


class TestGuardZones(unittest.TestCase):
    def test_hook_is_trimmed_not_the_whole_sentence(self):
        s = dict(FOUR_MUSCLES, start=0.0, end=12.0)
        v = IG.decide(manifest(), {}, [s], KEEPS, DUR)
        self.assertEqual(v["n"], 1)
        self.assertGreaterEqual(v["picks"][0]["start"], IG.HOOK_GUARD - 1e-6)

    def test_candidate_entirely_inside_cta_is_dropped(self):
        s = dict(FOUR_MUSCLES, start=DUR - 6.0, end=DUR - 0.5)
        v = IG.decide(manifest(), {}, [s], KEEPS, DUR)
        self.assertEqual(v["n"], 0)


class TestDosage(unittest.TestCase):
    """L47 — המחשה היא אירוע, לא פיצ'ר."""

    def test_max_per_video_is_one(self):
        self.assertEqual(IG.MAX_PER_VIDEO, 1)

    def test_two_strong_candidates_yield_at_most_two(self):
        a = dict(FOUR_MUSCLES, start=10.0, end=17.0)
        b = dict(FOUR_MUSCLES, start=25.0, end=32.0)
        v = IG.decide(manifest(), {}, [a, b], KEEPS, DUR)
        self.assertLessEqual(v["n"], IG.MAX_PER_VIDEO_EXCEPTION)

    def test_second_pick_is_flagged_as_exception_with_a_reason(self):
        a = dict(FOUR_MUSCLES, start=10.0, end=17.0)
        b = dict(FOUR_MUSCLES, start=25.0, end=32.0)
        v = IG.decide(manifest(), {}, [a, b], KEEPS, DUR)
        for p in v["picks"][1:]:
            self.assertTrue(p.get("exception"))
            self.assertTrue(p.get("exception_reason"))

    def test_weak_candidate_alone_does_not_pass_the_threshold(self):
        v = IG.decide(manifest(), {}, [MECH], KEEPS, DUR)
        self.assertEqual(v["n"], 0, "מנגנון בלבד אינו מספיק כדי להצדיק המחשה")

    def test_total_seconds_within_budget(self):
        a = dict(FOUR_MUSCLES, start=10.0, end=17.0)
        b = dict(FOUR_MUSCLES, start=25.0, end=32.0)
        v = IG.decide(manifest(), {}, [a, b], KEEPS, DUR)
        self.assertLessEqual(v["total_sec"], v["budget"]["max_total_sec"] + 1e-6)

    def test_recent_usage_raises_the_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            led = Path(d) / "ledger.json"
            led.write_text(json.dumps({"videos": [
                {"project": f"p{i}", "n_illustrations": 1} for i in range(4)]}),
                encoding="utf-8")
            hot = IG.decide(manifest(), {}, [FOUR_MUSCLES], KEEPS, DUR, ledger_path=led)
            cold = IG.decide(manifest(), {}, [FOUR_MUSCLES], KEEPS, DUR,
                             ledger_path=Path(d) / "empty.json")
            self.assertGreater(hot["threshold"], cold["threshold"],
                               "שימוש תכוף לא העלה את הסף")


class TestBrollOverlap(unittest.TestCase):
    """IL6 — רעיון ויזואלי אחד בכל רגע."""

    def test_overlapping_broll_penalises_the_candidate(self):
        clean = IG.decide(manifest(), {}, [FOUR_MUSCLES], KEEPS, DUR)
        with_broll = IG.decide(manifest(), {}, [FOUR_MUSCLES], KEEPS, DUR,
                               broll_items=[{"start": 21.0, "end": 26.0}])
        self.assertLess(with_broll["candidates"][0]["worth"],
                        clean["candidates"][0]["worth"])


class TestRegionVerification(unittest.TestCase):
    """IL5 / L46 — הסימון שנדלק חייב להיות השריר שנאמר."""

    def _wd(self, doc=None, sheet=True):
        d = Path(tempfile.mkdtemp())
        if doc is not None:
            (d / "illustration_regions.json").write_text(
                json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        if sheet:
            (d / "illustration_check.png").write_bytes(b"x")
        return d

    def test_missing_file_blocks(self):
        self.assertFalse(IG.region_verified(self._wd())["ok"])

    def test_unverified_entity_blocks(self):
        d = self._wd({"regions": [{"entity": "אינפרספינטוס", "verified": False}],
                      "check_sheet": "illustration_check.png"})
        r = IG.region_verified(d)
        self.assertFalse(r["ok"])
        self.assertIn("אינפרספינטוס", r["detail"])

    def test_missing_check_sheet_blocks(self):
        d = self._wd({"regions": [{"entity": "x", "verified": True}],
                      "check_sheet": "illustration_check.png"}, sheet=False)
        self.assertFalse(IG.region_verified(d)["ok"])

    def test_fully_verified_passes(self):
        d = self._wd({"regions": [{"entity": "אינפרספינטוס", "verified": True},
                                  {"entity": "טרס מינור", "verified": True}],
                      "check_sheet": "illustration_check.png"})
        self.assertTrue(IG.region_verified(d)["ok"])


class TestTimelineDetection(unittest.TestCase):
    """משפטים בציר הפלט מול ציר המקור — מיפוי בציר הלא-נכון מחזיר אפס
    מועמדים **בשקט**, וזה נראה בדיוק כמו 'אין מה להמחיש'."""

    def test_output_timeline_is_detected(self):
        keeps = [{"start": 100.0, "end": 160.0}]
        self.assertEqual(IG.timeline_of([FOUR_MUSCLES], keeps, DUR), "output")

    def test_source_timeline_is_detected(self):
        keeps = [{"start": 0.0, "end": 30.0}]
        s = {"start": 100.0, "end": 110.0, "text": FOUR_MUSCLES["text"]}
        self.assertEqual(IG.timeline_of([s], keeps, 25.0), "source")


class TestBuildEnforcers(unittest.TestCase):
    """L48 — הנכסים חייבים להיות inline base64, והרנטיים מוסר ברינדור מקומי."""

    def test_build_inlines_assets_as_base64(self):
        src = (Path(__file__).resolve().parent.parent /
               "tools" / "illustration_build.py").read_text(encoding="utf-8")
        self.assertIn("base64.b64encode", src)
        self.assertIn("data:image/png;base64", src + "data:image/png;base64")

    def test_build_strips_hyperframe_runtime_for_local_render(self):
        src = (Path(__file__).resolve().parent.parent /
               "tools" / "illustration_build.py").read_text(encoding="utf-8")
        self.assertIn("hyperframe.runtime", src)


class TestAtlasRegistration(unittest.TestCase):
    """IL7 / L49 — שני שרירים סמוכים שנוגעים בצבע אינם ניתנים להפרדה
    מהאיור. מפרידים **במקור**: אטלס בצבעי-מפתח, ומודדים את הרישום."""

    def _wd(self, doc=None):
        d = Path(tempfile.mkdtemp())
        (d / "illus").mkdir()
        if doc is not None:
            (d / "illus" / "atlas_report.json").write_text(
                json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return d

    def test_no_atlas_is_not_a_failure(self):
        r = IG.atlas_registration(self._wd())
        self.assertTrue(r["ok"])
        self.assertIn("נסיגה", r["detail"])

    def test_good_registration_passes(self):
        d = self._wd({"registration": {"iou": 0.9157, "threshold": 0.85, "ok": True}})
        self.assertTrue(IG.atlas_registration(d)["ok"])

    def test_misaligned_atlas_is_flagged(self):
        d = self._wd({"registration": {"iou": 0.41, "threshold": 0.85, "ok": False}})
        r = IG.atlas_registration(d)
        self.assertFalse(r["ok"])
        self.assertIn("0.41", r["detail"])

    def test_builder_exposes_the_atlas_path(self):
        src = (Path(__file__).resolve().parent.parent /
               "tools" / "illustration_build.py").read_text(encoding="utf-8")
        self.assertIn("def masks_from_atlas", src)
        self.assertIn("registration", src)


class TestGateRegistryWiring(unittest.TestCase):
    def test_all_gates_registered(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import gate_registry as GR
        names = [k for k in GR.GATES if k.startswith("illustration_gate:")]
        self.assertEqual(len(names), 7, f"נמצאו {len(names)} שערים במקום 7")
        blocking = [n for n in names
                    if GR.GATES[n]["enforcement"] == GR.BLOCKING]
        self.assertEqual(len(blocking), 6, "IL1-IL6 חייבים לחסום")
        self.assertEqual(
            GR.GATES["illustration_gate:IL7_atlas_registration"]["enforcement"],
            GR.ADVISORY, "IL7 מדווח — הסף נשען על מדידה אחת")


if __name__ == "__main__":
    unittest.main()
