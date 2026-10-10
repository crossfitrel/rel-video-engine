# -*- coding: utf-8 -*-
"""L55 — טייק פתיחה שגוי אינו ההוק (canon_lint._hook_retake_start)."""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import canon_lint as cl


def _w(words):
    return [{"word": t, "start": s, "end": s + 0.3} for t, s in words]


class TestHookRetake(unittest.TestCase):
    def _dir(self, words):
        d = Path(tempfile.mkdtemp())
        (d / "whisper_raw.json").write_text(json.dumps(_w(words), ensure_ascii=False), encoding="utf-8")
        return d

    def test_retake_detected(self):
        d = self._dir([("טיפ", 0.46), ("אחד", 0.8), ("לדאבל", 1.1), ("מה", 2.0),
                       ("טיפ", 6.24), ("אחד", 6.6), ("לדאבל", 6.9), ("אנדרס.", 7.2)])
        self.assertAlmostEqual(cl._hook_retake_start(d), 6.24)

    def test_no_retake_keeps_hook_protected(self):
        d = self._dir([("טיפ", 0.46), ("אחד", 0.8), ("לדאבל", 1.1), ("אנדרס", 1.5),
                       ("הדבר", 3.0), ("הכי", 3.3), ("טוב", 3.6)])
        self.assertIsNone(cl._hook_retake_start(d))

    def test_repeat_after_horizon_is_not_retake(self):
        d = self._dir([("אז", 0.5), ("מה", 0.8), ("עושים", 1.0),
                       ("אז", 45.0), ("מה", 45.3), ("עושים", 45.6)])
        self.assertIsNone(cl._hook_retake_start(d))


if __name__ == "__main__":
    unittest.main()
