# -*- coding: utf-8 -*-
"""בדיקות לשכבת היעילות (v9.30-eff, 22.9.26): חבילת סקיל רזה, תביעות קבצים, baseline."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import skill_pack as SP      # noqa: E402
import work_claim as WC      # noqa: E402
import baseline as BL        # noqa: E402


class TestSkillPack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.info = SP.build(cls.tmp, write_zip=False)
        cls.pack = cls.tmp / SP.SKILL_NAME
        cls.skill = (cls.pack / "SKILL.md").read_text(encoding="utf-8")

    def test_core_within_budget(self):
        # הליבה היא מה שנטען בכל הפעלה — חייבת להישאר קטנה משמעותית מהמאסטר
        self.assertLessEqual(self.info["core_chars"], SP.CORE_MAX_CHARS)
        self.assertLessEqual(self.info["core_lines"], SP.CORE_MAX_LINES)
        self.assertLess(self.info["core_chars"], self.info["master_chars"] / 3)

    def test_description_valid(self):
        self.assertLessEqual(self.info["description_chars"], SP.DESC_MAX)
        front = self.skill.split("---")[1]
        self.assertTrue("TRIGGERS" in front and "NEGATIVE" in front, "description בלי TRIGGERS/NEGATIVE")

    def test_zero_loss_every_master_line_in_references(self):
        _f, body = SP.split_front(SP.MASTER.read_text(encoding="utf-8"))
        blob = "\n".join(p.read_text(encoding="utf-8") for p in (self.pack / "references").glob("*.md"))
        lost = [ln for ln in body.split("\n") if ln.strip() and ln not in blob]
        self.assertEqual(lost, [], f"שורות מהמאסטר שלא נכנסו: {lost[:3]}")

    def test_every_h2_routed_no_misc(self):
        # סעיף חדש במאסטר שלא מופה ב-pack.json נכנס ל-misc.md — מותר אבל צריך מיפוי
        self.assertEqual(self.info["unmapped"], [], "להוסיף route ב-skills/rel-social-video-editor/pack.json")

    def test_every_reference_is_linked_from_core(self):
        for p in (self.pack / "references").glob("*.md"):
            self.assertTrue(f"references/{p.name}" in self.skill, f"{p.name} לא מקושר מהליבה")

    def test_core_mentions_only_existing_references(self):
        import re
        names = {p.name for p in (self.pack / "references").glob("*.md")}
        for m in re.findall(r"`([a-z0-9-]+\.md)`", SP.CORE.read_text(encoding="utf-8")):
            self.assertTrue(m in names | {"SKILL.md", "CORE.md"}, f"CORE מפנה ל-{m} שלא קיים")

    def test_long_references_have_toc(self):
        for p in (self.pack / "references").glob("*.md"):
            t = p.read_text(encoding="utf-8")
            if p.name != "video-canon.md" and t.count("\n") > SP.TOC_MIN_LINES + 3:
                self.assertTrue("## תוכן" in t, f"אין TOC ב-{p.name}")

    def test_check_detects_stale(self):
        real = SP.DIST
        try:
            SP.DIST = self.tmp
            (self.tmp / "BUILD.json").write_text(json.dumps(dict(self.info, master_sha256="x")), encoding="utf-8")
            self.assertEqual(SP.check(), 1)
            (self.tmp / "BUILD.json").write_text(json.dumps(self.info), encoding="utf-8")
            self.assertEqual(SP.check(), 0)
        finally:
            SP.DIST = real


class TestWorkClaim(unittest.TestCase):
    def setUp(self):
        self.real = WC.CLAIMS
        WC.CLAIMS = Path(tempfile.mkdtemp()) / "claims.json"

    def tearDown(self):
        WC.CLAIMS = self.real

    def test_claim_clash_and_release(self):
        self.assertEqual(WC.main(["claim", "tools/x.py", "--by", "A"]), 0)
        self.assertEqual(WC.main(["check", "tools/x.py", "--by", "B"]), 3)
        self.assertEqual(WC.main(["check", "tools/x.py", "--by", "A"]), 0)
        self.assertEqual(WC.main(["claim", "tools/x.py", "--by", "B"]), 3)   # מזהיר על התנגשות
        WC.main(["release", "--by", "A"])
        WC.main(["release", "--by", "B"])
        self.assertEqual(WC.main(["check", "tools/x.py", "--by", "C"]), 0)

    def test_expired_claims_drop(self):
        WC.CLAIMS.write_text(json.dumps({"claims": [{"file": "a", "by": "A", "since": "", "expires": time.time() - 1}]}),
                             encoding="utf-8")
        self.assertEqual(WC.main(["check", "a", "--by", "B"]), 0)

    def test_backup_tag_parse(self):
        self.assertEqual(WC.BAK_TAG.search("gate_registry.py.bak-v930-20260922").group(1), "v930")
        self.assertEqual(WC.BAK_TAG.search("lesson_registry.py.bak-l60-20260922-134334").group(1), "l60")


class TestBaselineDiff(unittest.TestCase):
    def test_new_break_detected_old_debt_ignored(self):
        prev = {"tests": {"ran": 10, "fails": ["t.a"]}, "doctor": {"fail": ["x"], "warn": []}}
        cur = {"tests": {"ran": 11, "fails": ["t.a", "t.b"]}, "doctor": {"fail": ["x"], "warn": ["w"]}}
        ch = BL.diff(prev, cur)
        self.assertIn("🆕❌ בדיקה נשברה: t.b", ch)
        self.assertFalse(any("t.a" in c for c in ch))
        self.assertIn("🆕⚠️ doctor: w", ch)

    def test_diff_tolerates_missing_tests(self):
        self.assertIsInstance(BL.diff({"tests": None}, {"tests": None, "doctor": {}}), list)

    def test_fail_line_parser(self):
        out = "FAIL: test_x (test_mod.Cls.test_x)\nERROR: test_y (test_mod.Cls.test_y)\n"
        self.assertEqual([b for _k, _a, b in BL.FAIL_LINE.findall(out)],
                         ["test_mod.Cls.test_x", "test_mod.Cls.test_y"])


class TestAsrMlx(unittest.TestCase):
    """v9.30-eff — MLX דילג על משפט CTA כשקטע VAD חצה את חלון ה-30ש (asr_mlx_final.json)."""

    def setUp(self):
        import numpy as np
        import asr_mlx as AM
        self.np, self.AM = np, AM

    def test_long_chunk_split_at_quietest_point(self):
        np, AM = self.np, self.AM
        sr = AM.SR
        audio = np.full(int(31.2 * sr), 0.3, dtype=np.float32)
        q = int(15.0 * sr)
        audio[q:q + int(0.3 * sr)] = 0.0              # שקט ב-15ש — שם צריך לחתוך
        out = AM.split_long([{"start": 0, "end": len(audio)}], audio)
        self.assertEqual(len(out), 2)
        self.assertTrue(all((c["end"] - c["start"]) / sr <= AM.MAX_CHUNK_S for c in out))
        self.assertLess(abs(out[0]["end"] / sr - 15.15), 0.3)
        self.assertEqual(out[0]["end"], out[1]["start"])   # רציף — אף דגימה לא נזרקת

    def test_short_chunks_untouched_and_windows_capped(self):
        AM = self.AM
        sr = AM.SR
        chunks = [{"start": i * 10 * sr, "end": (i * 10 + 9) * sr} for i in range(6)]
        audio = self.np.zeros(60 * sr, dtype=self.np.float32)
        self.assertEqual(AM.split_long(chunks, audio), chunks)
        for g in AM.windows(chunks):
            self.assertLessEqual(sum((c["end"] - c["start"]) / sr for c in g), AM.WINDOW_S)

    def test_align_words_falls_back_to_ct2(self):
        src = (TOOLS / "align_words.py").read_text(encoding="utf-8")
        for needle in ("REL_ASR_BACKEND", "if stream is None:", "WhisperModel(", "asr-glossary", "backend={used_backend}"):
            self.assertTrue(needle in src, f"align_words חסר: {needle}")


if __name__ == "__main__":
    unittest.main()
