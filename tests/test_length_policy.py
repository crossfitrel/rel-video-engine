# -*- coding: utf-8 -*-
"""v9.25 — מדיניות אורך לפי סוג תוכן (L67). הראל 19.9.26: "לא כל סרטון חייב להיות
מוגבל עד 60 שניות". כולל הזרקת-כשל: תקרת 60 שחוזרת לאחד הכלים = כשל."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))
import length_policy as LP  # noqa: E402


class TestBands(unittest.TestCase):
    def test_value_75s_is_in_target(self):
        r = LP.evaluate(75, "value")
        self.assertTrue(r["hard_ok"] and r["in_target"] and r["reason_ok"])
        self.assertEqual(r["level"], "ok")

    def test_conversion_prefers_short(self):
        self.assertEqual(LP.evaluate(35, "conversion")["level"], "ok")
        self.assertEqual(LP.evaluate(55, "conversion")["level"], "soft")
        self.assertEqual(LP.evaluate(70, "conversion")["level"], "soft")     # v9.26: נימוק רק מעל 90
        self.assertEqual(LP.evaluate(95, "conversion")["level"], "reason")

    def test_over_90_needs_reason_for_value(self):
        self.assertEqual(LP.evaluate(110, "value")["level"], "reason")
        r = LP.evaluate(110, "value", "סיפור עם מתח עד הסוף")
        self.assertTrue(r["reason_ok"])
        self.assertEqual(r["level"], "soft")

    def test_podcast_reason_threshold_is_120(self):
        self.assertTrue(LP.evaluate(110, "podcast")["reason_ok"])
        self.assertFalse(LP.evaluate(125, "podcast")["reason_ok"])

    def test_hard_bounds(self):
        self.assertEqual(LP.evaluate(181, "value", "x")["level"], "hard")
        self.assertEqual(LP.evaluate(10, "conversion")["level"], "hard")
        self.assertTrue(LP.evaluate(14, "conversion")["hard_ok"])   # ריל 14ש שלנו = 2,609 reach

    def test_unknown_type_falls_back_to_value(self):
        self.assertEqual(LP.evaluate(70, "???")["content_type"], "value")
        self.assertEqual(LP.evaluate(70, None)["content_type"], "value")

    def test_from_workdir_reads_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "project_manifest.json").write_text(json.dumps(
                {"content_type": "conversion", "length_reason": "הדגמה"}), encoding="utf-8")
            self.assertEqual(LP.from_workdir(d), ("conversion", "הדגמה"))


class TestNo60Cap(unittest.TestCase):
    """הזרקת-כשל מבנית: אף כלי לא אוכף יותר 60/65 כתקרה."""
    FILES = ["qa_gates.py", "canon_lint.py", "preflight_critic.py", "edit_plan.py",
             "local_finish_pipeline.py", "edl_build.py"]
    PATTERNS = [r"dur\s*>\s*60\.0", r"<=\s*65(\.0)?\b", r"kept\s*>\s*6[05]\b",
                r"50(\.0)?\s*<=\s*\w+\s*<=\s*65", r"target_len_sec"]

    def test_no_60s_cap_anywhere(self):
        for f in self.FILES:
            src = (TOOLS / f).read_text(encoding="utf-8")
            for pat in self.PATTERNS:
                self.assertIsNone(re.search(pat, src),
                                  f"{f}: תקרת אורך קשיחה חזרה ({pat}) — לעבור דרך length_policy")

    def test_all_layers_use_length_policy(self):
        for f in self.FILES:
            src = (TOOLS / f).read_text(encoding="utf-8")
            self.assertIn("length_policy", src, f"{f} לא קורא ל-length_policy")

    def test_review_app_has_no_fixed_target(self):
        html = (TOOLS.parent / "review-app" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("TARGET_LEN", html)
        self.assertIn("lenVerdict", html)

    def test_injected_cap_is_caught(self):
        """מוכיח שהבדיקה עצמה תופסת: מזריקים תקרה ישנה ומוודאים שה-regex מוצא אותה."""
        injected = "if dur > 60.0 and not a.allow_long:\n    fail('x')"
        self.assertTrue(any(re.search(p, injected) for p in self.PATTERNS))


class TestHarelNumbers(unittest.TestCase):
    """v9.26 — המספרים של הראל (19.9 ערב) הם המקור: שיווקי/הוק 20-45 · ערך/סיפור/חיבור
    45-90 · נימוק מעל 90. כל עותק של המספרים (אפליקציה, סקיל, רשומות, runbook) נגזר מהם."""
    HAREL = {"conversion": (20.0, 45.0, 90.0), "value": (45.0, 90.0, 90.0),
             "story": (45.0, 90.0, 90.0), "connection": (45.0, 90.0, 90.0),
             "personal": (45.0, 90.0, 90.0), "throwdown_value": (45.0, 90.0, 90.0)}
    STALE = [r"20-50\s*ש?\b", r"40-90", r"target:\[40,90\]", r"target:\[20,50\]",
             r"reason_above:60"]
    COPIES = ["review-app/index.html", "tools/gate_registry.py", "tools/lesson_registry.py",
              "tools/PIPELINE.md", "skills/rel-social-video-editor/SKILL.md"]

    def test_bands_equal_harel(self):
        for ct, (lo, hi, ra) in self.HAREL.items():
            b = LP.BANDS[ct]
            self.assertEqual((tuple(b["target"]), b["reason_above"]), ((lo, hi), ra), ct)

    def test_no_stale_copy(self):
        root = TOOLS.parent
        for f in self.COPIES:
            p = root / f
            if not p.exists():
                continue
            src = p.read_text(encoding="utf-8")
            for pat in self.STALE:
                self.assertIsNone(re.search(pat, src), f"{f}: מספר אורך ישן ({pat}) — ליישר ל-length_policy")

    def test_app_fallback_matches_policy(self):
        html = (TOOLS.parent / "review-app" / "index.html").read_text(encoding="utf-8")
        m = re.search(r"conversion:\{target:\[(\d+),(\d+)\],reason_above:(\d+)", html)
        self.assertIsNotNone(m)
        self.assertEqual(tuple(float(x) for x in m.groups()), self.HAREL["conversion"])

    def test_injected_stale_number_is_caught(self):
        """הזרקת-כשל: עותק ישן 20-50 בטבלה חייב להיתפס."""
        self.assertTrue(any(re.search(p, "| המרה | 20-50ש | 60ש |") for p in self.STALE))
        self.assertTrue(any(re.search(p, "conversion:{target:[20,50],reason_above:60") for p in self.STALE))


class TestQaGatesWiring(unittest.TestCase):
    def test_qa_gates_g1c_exists_and_soft(self):
        src = (TOOLS / "qa_gates.py").read_text(encoding="utf-8")
        i = src.index('gate("G1c_length_reason"')
        self.assertIn("hard=False", src[i:i + 400])

    def test_pipeline_passes_content_type_to_qa(self):
        src = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")
        self.assertIn('"--content-type", a.content_type]', src)


if __name__ == "__main__":
    unittest.main()
