# -*- coding: utf-8 -*-
"""v9.26 — אפליקציית הרוויו על הפייתון הנכון ובבעלות launchd (system_doctor).
הזרקת-כשל לכל מצב שנמצא בפועל ב-19.9.26."""
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))
import system_doctor as SD  # noqa: E402

PY = SD.REVIEW_PY


class TestReviewAppVerdict(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(SD.review_app_verdict(PY, True, "100", True, "100")[0], "PASS")

    def test_injected_system_python_fails(self):
        st, d = SD.review_app_verdict("/usr/bin/python3", False, "100", False, "100")
        self.assertEqual(st, "FAIL")
        self.assertIn("flask", d)

    def test_injected_orphan_server_and_crash_loop(self):
        """המצב של 19.9.26: שרת nohup ידני על 5112, launchd מנסה שוב ושוב."""
        st, d = SD.review_app_verdict(PY, True, "31075", True, "16977")
        self.assertEqual(st, "WARN")
        self.assertIn("יתום", d)

    def test_listener_not_from_venv_fails(self):
        self.assertEqual(SD.review_app_verdict(PY, True, "100", False, "100")[0], "FAIL")

    def test_no_plist_fails(self):
        self.assertEqual(SD.review_app_verdict(None, True, None, False, None)[0], "FAIL")

    def test_launcher_prefers_venv_and_launchd(self):
        src = (TOOLS.parent / "review-app" / "▶ הפעל רוויו R.E.L.command").read_text(encoding="utf-8")
        self.assertIn(".rel-whisper/bin/python", src)
        self.assertIn("launchctl kickstart", src)


if __name__ == "__main__":
    unittest.main()
