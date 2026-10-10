# -*- coding: utf-8 -*-
"""מיקום ההמחשה בפריים — לא מסתיר את הראש, מעדיף מרכז, בלי רקע שחור.

הראל 21.8.26: *"שווה לוודא שזה לא מסתיר את הראש של מי שמדבר. אולי לשים את
זה במרכז. ולהוריד את הרקע השחור."*

הזרקת-כשל: לכל כלל יש מקרה שבו הוא חייב לפסול, ולא רק מקרה שבו הוא עובר.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import illustration_place as IP  # noqa: E402

W, H = 1080, 1920
AR = 0.954                      # יחס הקלף (1040x1090)
FACE_TOP = [0.33, 0.24, 0.63, 0.40]     # דובר שעומד גבוה בפריים
FACE_MID = [0.34, 0.40, 0.62, 0.55]


class TestForbiddenZones(unittest.TestCase):
    def test_placement_never_overlaps_the_face(self):
        p = IP.solve_placement([FACE_TOP], None, AR, W, H)
        self.assertTrue(p["ok"])
        self.assertEqual(IP._overlap(p["box"], FACE_TOP), 0.0)

    def test_placement_never_enters_the_caption_band(self):
        p = IP.solve_placement([FACE_TOP], None, AR, W, H)
        band = [0.0, IP.CAPTION_BAND[0], 1.0, IP.CAPTION_BAND[1]]
        self.assertEqual(IP._overlap(p["box"], band), 0.0)

    def test_head_pad_is_respected(self):
        """לא מספיק לא לגעת — צריך מרווח, אחרת הקלף 'מלקק' את הראש."""
        p = IP.solve_placement([FACE_TOP], None, AR, W, H)
        padded = [FACE_TOP[0] - IP.HEAD_PAD, FACE_TOP[1] - IP.HEAD_PAD,
                  FACE_TOP[2] + IP.HEAD_PAD, FACE_TOP[3] + IP.HEAD_PAD]
        self.assertEqual(IP._overlap(p["box"], padded), 0.0)

    def test_no_legal_placement_means_no_illustration(self):
        """כיסוי פנים אינו פשרה — אם אין מקום, ההמחשה יורדת."""
        wall = [[0.0, 0.0, 1.0, IP.CAPTION_BAND[0]]]
        p = IP.solve_placement(wall, None, AR, W, H)
        self.assertFalse(p["ok"])
        self.assertIn("יורדת", p["why"])


class TestCentringPreference(unittest.TestCase):
    """הראל: 'אולי לשים את זה במרכז'."""

    def test_prefers_centre_when_the_frame_allows(self):
        p = IP.solve_placement([FACE_MID], None, AR, W, H)
        self.assertTrue(p["ok"])
        self.assertLess(p["off_centre"], 0.06, "הקלף לא ממורכז אף שהיה מקום")

    def test_small_widths_exist_so_centring_stays_reachable(self):
        self.assertLessEqual(min(IP.CARD_WIDTHS), 0.34,
                             "בלי רוחב קטן, מרכוז בלתי-אפשרי כשהדובר גבוה בפריים")

    def test_busy_area_is_avoided(self):
        import numpy as np
        busy = np.zeros((IP.GRID, IP.GRID), dtype="float32")
        busy[:IP.GRID // 2, :] = 1.0            # החצי העליון עמוס
        p = IP.solve_placement([FACE_MID], busy, AR, W, H)
        self.assertTrue(p["ok"])
        self.assertLess(p["busy_cost"], 0.9)


class TestPreferredBand(unittest.TestCase):
    """הראל 21.8.26: 'אולי מעל הכתוביות מתחת לראש היה יותר טוב'."""

    def test_lands_below_the_head_and_above_the_captions(self):
        p = IP.solve_placement([FACE_TOP], None, AR, W, H)
        self.assertTrue(p["ok"])
        self.assertTrue(p["in_preferred_band"], "לא נחת ברצועת הגוף אף שהיא פנויה")
        self.assertGreaterEqual(p["box"][1], FACE_TOP[3])
        self.assertLessEqual(p["box"][3], IP.CAPTION_BAND[0] + 1e-6)

    def test_band_is_reported_with_its_geometry(self):
        p = IP.solve_placement([FACE_TOP], None, AR, W, H)
        b = p["band"]
        self.assertIn("top", b); self.assertIn("bottom", b); self.assertIn("usable", b)
        self.assertEqual(b["face_bottom_source"], "measured")

    def test_narrow_band_falls_back_and_says_why(self):
        """דובר שעומד נמוך ⇒ רצועה צרה ⇒ נסיגה מדווחת, לא כישלון שקט."""
        low = [0.33, 0.50, 0.63, 0.62]
        p = IP.solve_placement([low], None, AR, W, H)
        self.assertTrue(p["ok"])
        self.assertFalse(p["in_preferred_band"])
        self.assertIsNotNone(p["band"]["why_not"])

    def test_band_is_a_preference_not_a_hard_rule(self):
        self.assertGreater(IP.BAND_BONUS, 0.0)
        self.assertLess(IP.BAND_BONUS, 1.0, "בונוס ≥1 הופך העדפה לחוק")

    def test_assumed_face_bottom_is_marked_as_assumed(self):
        p = IP.solve_placement(None, None, AR, W, H)
        self.assertEqual(p["band"]["face_bottom_source"], "assumed")


class TestFalsePositiveFaces(unittest.TestCase):
    """L52 — חיובי-שגוי מוחק את האזור שעליו נחת."""

    def test_persistent_cluster_beats_an_intermittent_one(self):
        real = [0.34, 0.25, 0.52, 0.35]
        shirt = [0.39, 0.46, 0.54, 0.55]
        per_frame = [[real, shirt] if i < 4 else [real] for i in range(8)]
        kept = IP._persistent_faces(per_frame)
        self.assertTrue(all(abs(b[1] - real[1]) < 0.05 for b in kept),
                        "ההדפס על החולצה נשאר ומוחק את רצועת הגוף")
        self.assertEqual(len(kept), 8)

    def test_two_real_speakers_are_both_kept(self):
        a = [0.10, 0.25, 0.28, 0.35]
        b = [0.62, 0.25, 0.80, 0.35]
        per_frame = [[a, b] for _ in range(8)]
        self.assertEqual(len(IP._persistent_faces(per_frame)), 16)

    def test_no_detections_is_empty_not_a_crash(self):
        self.assertEqual(IP._persistent_faces([[], [], []]), [])

    def test_false_positive_no_longer_kills_the_band(self):
        real = [0.34, 0.25, 0.52, 0.35]
        shirt = [0.39, 0.46, 0.54, 0.55]
        kept = IP._persistent_faces([[real, shirt] if i < 3 else [real] for i in range(8)])
        p = IP.solve_placement(kept, None, AR, W, H)
        self.assertTrue(p["in_preferred_band"])


class TestOcclusionGate(unittest.TestCase):
    """IL8. חוסם כשנמדד, מסמן כשלא — L51."""

    def test_blocks_when_measured_and_overlapping(self):
        bad = {"ok": True, "box": [0.30, 0.20, 0.70, 0.45]}
        g = IP.occlusion_check(bad, [FACE_TOP], "haar")
        self.assertFalse(g["ok"])
        self.assertTrue(g["measured"])

    def test_passes_when_measured_and_clear(self):
        good = {"ok": True, "box": [0.30, 0.00, 0.70, 0.18]}
        g = IP.occlusion_check(good, [FACE_TOP], "haar")
        self.assertTrue(g["ok"])
        self.assertTrue(g["measured"])

    def test_unmeasured_is_marked_not_silently_passed(self):
        good = {"ok": True, "box": [0.30, 0.00, 0.70, 0.18]}
        g = IP.occlusion_check(good, None, "unavailable:no-cascade")
        self.assertFalse(g["measured"], "'לא נמדד' חייב להיות דאטה, לא PASS שקט")
        self.assertIn("לא נמדד", g["detail"])

    def test_gate_is_registered_as_blocking(self):
        import gate_registry as GR
        g = GR.GATES["illustration_place:IL8_face_occlusion"]
        self.assertEqual(g["enforcement"], GR.BLOCKING)


class TestTransparentBackdrop(unittest.TestCase):
    """הראל: 'ולהוריד את הרקע השחור'."""

    def _img(self):
        from PIL import Image
        im = Image.new("RGB", (64, 64), (0x14, 0x10, 0x11))
        for y in range(20, 44):
            for x in range(20, 44):
                im.putpixel((x, y), (200, 90, 80))
        return im

    def test_backdrop_becomes_transparent(self):
        out = IP.alpha_from_backdrop(self._img(), halo=0)
        self.assertEqual(out.getpixel((2, 2))[3], 0, "הרקע לא הוסר")

    def test_subject_stays_opaque(self):
        out = IP.alpha_from_backdrop(self._img(), halo=0)
        self.assertGreater(out.getpixel((32, 32))[3], 240, "הנושא נחתך")

    def test_halo_keeps_contrast_on_bright_footage(self):
        plain = IP.alpha_from_backdrop(self._img(), halo=0)
        haloed = IP.alpha_from_backdrop(self._img(), halo=10)
        self.assertGreater(haloed.getpixel((14, 32))[3], plain.getpixel((14, 32))[3],
                           "אין הילה — האיור ייבלע על רקע בהיר")

    def test_builder_defaults_to_transparent(self):
        src = (Path(__file__).resolve().parent.parent /
               "tools" / "illustration_build.py").read_text(encoding="utf-8")
        self.assertIn("transparent: bool = True", src)


if __name__ == "__main__":
    unittest.main()
