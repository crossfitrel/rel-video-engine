"""L136 — ראיית בירול שורדת העתקה שמשנה mtime (git checkout בענן)."""
import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import broll_vision_model as VM  # noqa: E402


class TestClipKeyCopy(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.clip = self.d / "בירול - בדיקה.mp4"
        self.clip.write_bytes(b"x" * 1234)
        os.utime(self.clip, (1_700_000_000, 1_700_000_000))
        self.cache = self.d / "vision-cache-model.json"
        self.cache.write_text(json.dumps({VM.clip_key(self.clip): {"crowding": "solo"}}), encoding="utf-8")
        self.p = mock.patch.object(VM, "cache_path", lambda: self.cache)
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_lookup_survives_mtime_change(self):
        os.utime(self.clip, (1_800_000_000, 1_800_000_000))   # "checkout"
        self.assertEqual(VM.lookup(self.clip), {"crowding": "solo"})
        self.assertEqual(VM.missing([self.clip]), [])

    def test_changed_content_is_still_missing(self):
        self.clip.write_bytes(b"y" * 999)
        self.assertIsNone(VM.lookup(self.clip))
        self.assertEqual(VM.missing([self.clip]), [self.clip])


if __name__ == "__main__":
    unittest.main()
