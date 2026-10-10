# -*- coding: utf-8 -*-
"""
רגרסיה על **חוב הצילום** — הפלט שהופך "לא" ל"הנה מה לצלם".

הליקוי שנמדד 31.7.26: הבריכה של סרטון האופן-ג'ים היא `medium` 30 ·
`close` 1 · **`wide` 0**. שער חוסם על גיוון-שוט היה מפיל כל סרטון המרה,
כי אין מה לבחור. הפלט הנכון אינו פסילה אלא פריט צילום.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import broll_shot_debt as SD                            # noqa: E402


class _FakeVM:
    def __init__(self, mapping):
        self.mapping = mapping

    def lookup(self, p):
        return self.mapping.get(p)


class TestPoolGapsMeasureThePoolNotTheVideo(unittest.TestCase):
    def setUp(self):
        self._orig = sys.modules.get("broll_vision_model")

    def tearDown(self):
        if self._orig is not None:
            sys.modules["broll_vision_model"] = self._orig
        else:
            sys.modules.pop("broll_vision_model", None)

    def _gaps(self, shots):
        paths = {str(i): f"/c/{i}.mp4" for i in range(len(shots))}
        sys.modules["broll_vision_model"] = _FakeVM(
            {f"/c/{i}.mp4": {"shot": s} for i, s in enumerate(shots)})
        return SD.pool_gaps({"_paths": paths})

    def test_a_pool_with_no_wide_shots_owes_a_wide_shot(self):
        gaps = self._gaps(["medium"] * 30 + ["close"])
        needs = {g["need"]: g for g in gaps}
        self.assertIn("wide", needs)
        self.assertEqual("high", needs["wide"]["severity"])
        self.assertIn("0 מתוך 31", needs["wide"]["evidence"])

    def test_a_balanced_pool_owes_nothing(self):
        self.assertEqual([], self._gaps(["wide"] * 10 + ["medium"] * 10
                                        + ["close"] * 10))

    def test_a_pool_too_small_to_conclude_from_says_nothing(self):
        """שלושה קליפים אינם ראיה להטיה. 'לא יודע' עדיף על חוב מומצא."""
        self.assertEqual([], self._gaps(["medium", "medium", "close"]))


class TestBoardItemsCarryReasonAndSource(unittest.TestCase):
    def test_each_item_names_the_video_it_came_from(self):
        debt = {"project": "אופן-גים", "pool": [
            {"kind": "pool", "need": "wide", "why": SD.NEEDED_SHOTS["wide"],
             "evidence": "0 מתוך 31", "severity": "high"}],
            "sentences": [{"sentence": "אוזניות", "why": "אין שוט", "at": 12.5}],
            "sequence": []}
        items = SD.board_items(debt)
        self.assertEqual(2, len(items))
        for it in items:
            self.assertEqual("אופן-גים", it["source"])
            self.assertTrue(it["what"] and it["goal"])

    def test_six_sentence_debts_become_one_item_not_six(self):
        """שישה פריטים לסרטון אחד הם רעש, לא רשימה."""
        debt = {"project": "X", "pool": [], "sequence": [],
                "sentences": [{"sentence": f"משפט {i}", "why": "אין שוט"}
                              for i in range(6)]}
        items = SD.board_items(debt)
        self.assertEqual(1, len(items))
        self.assertEqual(6, items[0]["what"].count("• "))


class TestCollectReadsRealArtifacts(unittest.TestCase):
    def test_project_name_is_human_readable_not_an_id(self):
        """פריט בורד בשם prj_942bdcbb127f אינו אומר לאף אחד מאיזה סרטון הוא בא."""
        with tempfile.TemporaryDirectory() as d:
            W = Path(d)
            (W / "project_manifest.json").write_text(json.dumps(
                {"project_id": "prj_deadbeef", "name": "אופן-גים-צהריים",
                 "dept": "קרוספיט אריאל"}), encoding="utf-8")
            (W / "broll_plan.json").write_text(json.dumps(
                {"shot_list": [{"sentence": "אוזניות", "why_no_clip": "אין שוט",
                                "at": 12.5}]}), encoding="utf-8")
            debt = SD.collect(W)
        self.assertEqual("אופן-גים-צהריים", debt["project"])
        self.assertEqual(1, len(debt["sentences"]))

    def test_missing_artifacts_do_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            debt = SD.collect(d)
        self.assertEqual([], debt["sentences"])
        self.assertEqual([], SD.board_items(debt))


if __name__ == "__main__":
    unittest.main()
