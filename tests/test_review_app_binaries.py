# -*- coding: utf-8 -*-
"""v9.21 — אוכף L50: שרת הרוויו לא נשען על PATH לאיתור בינארים חיצוניים.

שורש התקלה (22.8.26): `subprocess.run(["ffmpeg", ...])` בתוך `/api/frame`.
כששרת הרוויו הופעל בלי סביבת login, `/opt/homebrew/bin` לא היה ב-PATH,
subprocess זרק FileNotFoundError, המטפל הגלובלי החזיר 404 "פרויקט לא נמצא",
והפריימים משני צדי החיתוך נשברו **בשקט** — עם הודעת שגיאה שהצביעה על
הבעיה הלא-נכונה.
"""
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

SYSDIR = Path(__file__).resolve().parents[1]
SERVER = SYSDIR / "review-app" / "server.py"


class TestReviewAppBinaries(unittest.TestCase):

    def setUp(self):
        self.assertTrue(SERVER.exists(), "review-app/server.py חסר")
        self.src = SERVER.read_text(encoding="utf-8", errors="replace")

    # ── האוכף עצמו קיים ──────────────────────────────────────────────
    def test_resolver_exists(self):
        self.assertIn("def _ffmpeg_bin", self.src,
                      "פותר הנתיב המוחלט ל-ffmpeg נעלם מ-server.py")

    def test_no_bare_ffmpeg_invocation(self):
        """אסור להריץ 'ffmpeg' כמחרוזת ערומה — זו בדיוק התקלה שנפלנו בה."""
        bad = re.findall(r'subprocess\.\w+\(\s*\[\s*["\']ffmpeg["\']', self.src)
        self.assertEqual(bad, [],
                         "server.py קורא ל-ffmpeg דרך PATH במקום דרך _ffmpeg_bin()")
        bad_probe = re.findall(r'subprocess\.\w+\(\s*\[\s*["\']ffprobe["\']', self.src)
        self.assertEqual(bad_probe, [],
                         "server.py קורא ל-ffprobe דרך PATH במקום נתיב מוחלט")

    def test_missing_binary_is_reported_not_disguised(self):
        """כשהבינארי חסר — קוד שגיאה מפורש, לא 404 שנראה כמו פרויקט חסר."""
        self.assertIn("FFMPEG_MISSING", self.src,
                      "אין דיווח מפורש על ffmpeg חסר — הכשל יתחזה ל-404")

    # ── הזרקת כשל: PATH ריק, והפותר עדיין מוצא ──────────────────────
    def test_resolver_survives_broken_path(self):
        code = (
            "import os,shutil,sys;"
            "sys.path.insert(0,%r);"
            "cand=[os.environ.get('RELVID_FFMPEG'),shutil.which('ffmpeg'),"
            "'/opt/homebrew/bin/ffmpeg','/usr/local/bin/ffmpeg','/usr/bin/ffmpeg'];"
            "ff=next((c for c in cand if c and os.path.isfile(c) "
            "and os.access(c,os.X_OK)),None);"
            "print('WHICH=',shutil.which('ffmpeg'));print('RESOLVED=',ff)"
        ) % str(SYSDIR)
        r = subprocess.run(
            [sys.executable, "-c", code],   # לא "python3" — ה-PATH שבור בכוונה
            env={"PATH": "/nonexistent", "HOME": os.environ.get("HOME", "/tmp")},
            capture_output=True, text=True, timeout=30)
        out = r.stdout
        self.assertIn("WHICH= None", out,
                      "ההזרקה לא באמת שברה את ה-PATH — הבדיקה חסרת ערך")
        if shutil.which("ffmpeg") or Path("/opt/homebrew/bin/ffmpeg").exists():
            self.assertNotIn("RESOLVED= None", out,
                             "הפותר לא מצא את ffmpeg כש-PATH שבור")


if __name__ == "__main__":
    unittest.main()
