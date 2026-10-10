# -*- coding: utf-8 -*-
"""
מימוש קבצי בירול מ-iCloud לפני רינדור (v9.5).

הליקוי שנמדד 31.7.26: הרינדור "נתקע" 3.5 דקות על **0% CPU** — בלי שגיאה,
בלי לוג, בלי התקדמות. זה לא היה deadlock בגרף הפילטרים (נבדק: 1/2/3/4/6
overlay-ים באותה שרשרת בדיוק עברו) אלא ffmpeg שנחסם על ה-`read()` הראשון
של קובץ iCloud שלא ירד. עם 2 בירולים זה לא נראה כי שניהם היו מקומיים.

**0% CPU לאורך זמן = I/O חסום, לא לולאה.**
"""
import os, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import broll_director as BD          # noqa: E402


class TestCloudDetection(unittest.TestCase):
    def test_a_real_local_file_is_not_cloud_only(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "clip.mp4"
            f.write_bytes(b"x" * 4096)
            self.assertFalse(BD.is_cloud_only(f))

    def test_an_icloud_placeholder_sibling_marks_cloud_only(self):
        """הזרקת הכשל: כך נראה קובץ שנשמט מהדיסק — הקובץ 'קיים' אבל התוכן לא."""
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "clip.mp4"
            f.write_bytes(b"x" * 4096)
            (Path(d) / ".clip.mp4.icloud").write_bytes(b"")
            self.assertTrue(BD.is_cloud_only(f))

    def test_a_missing_file_is_not_reported_as_local(self):
        self.assertFalse(BD.is_cloud_only(Path("/nope/does/not/exist.mp4")))


class TestMaterialize(unittest.TestCase):
    def test_local_files_are_a_no_op(self):
        with tempfile.TemporaryDirectory() as d:
            fs = []
            for i in range(3):
                f = Path(d) / f"c{i}.mp4"
                f.write_bytes(b"x" * 2048)
                fs.append(str(f))
            rep = BD.materialize(fs)
            self.assertEqual(rep["cloud_only"], 0)
            self.assertEqual(rep["secs"], 0.0)

    def test_a_placeholder_is_picked_up_and_read(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "c.mp4"
            f.write_bytes(b"x" * 2048)
            (Path(d) / ".c.mp4.icloud").write_bytes(b"")
            rep = BD.materialize([str(f)], timeout=5)
            self.assertEqual(rep["cloud_only"], 1)
            self.assertEqual(rep["downloaded"], 1)
            self.assertEqual(rep["failed"], [])

    def test_an_unreadable_file_is_reported_not_swallowed(self):
        """שער שבולע כשל גרוע משער שאין — הכישלון חייב להגיע לדוח."""
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "c.mp4"
            f.write_bytes(b"x" * 2048)
            (Path(d) / ".c.mp4.icloud").write_bytes(b"")
            os.chmod(f, 0o000)
            try:
                rep = BD.materialize([str(f)], timeout=5)
                self.assertEqual(rep["downloaded"], 0)
                self.assertEqual(len(rep["failed"]), 1)
            finally:
                os.chmod(f, 0o644)

    def test_duplicate_paths_are_counted_once(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "c.mp4"
            f.write_bytes(b"x" * 2048)
            (Path(d) / ".c.mp4.icloud").write_bytes(b"")
            rep = BD.materialize([str(f), str(f), str(f)], timeout=5)
            self.assertEqual(rep["cloud_only"], 1)

    def test_none_paths_do_not_crash(self):
        self.assertEqual(BD.materialize([None, None])["cloud_only"], 0)


if __name__ == "__main__":
    unittest.main()
