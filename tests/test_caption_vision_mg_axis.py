# -*- coding: utf-8 -*-
"""v10 — V7 העצמאי חייב למדוד על ציר words_after_mg.json כשה-MG הכניס הקפאה."""
import os, sys, tempfile, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import caption_vision as cvm  # noqa: E402


class TestMgAxis(unittest.TestCase):
    def test_prefers_words_after_mg_when_newer(self):
        with tempfile.TemporaryDirectory() as d:
            W = Path(d)
            (W / "words_final.json").write_text("[]", encoding="utf-8")
            time.sleep(0.01)
            (W / "words_after_mg.json").write_text("[]", encoding="utf-8")
            _, words, _, _ = cvm.project_inputs(W)
            self.assertEqual(words.name, "words_after_mg.json")

    def test_stale_words_after_mg_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            W = Path(d)
            (W / "words_after_mg.json").write_text("[]", encoding="utf-8")
            old = time.time() - 100
            os.utime(W / "words_after_mg.json", (old, old))
            (W / "words_final.json").write_text("[]", encoding="utf-8")
            _, words, _, _ = cvm.project_inputs(W)
            self.assertEqual(words.name, "words_final.json")


if __name__ == "__main__":
    unittest.main()
