"""v9.36 (28.9.26) — ספריית מוזיקה מגוונת ומתויגת. L107."""
import json, sys, tempfile, time, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class TestMusicCatalogV2(unittest.TestCase):
    def setUp(self):
        self.cat = json.loads((ROOT / "tools" / "music-catalog.json").read_text(encoding="utf-8"))["tracks"]
        self.files = sorted(p.name for p in (ROOT / "brand-assets" / "music").glob("*.mp3"))

    def test_every_track_is_tagged(self):
        for f in self.files:
            t = self.cat.get(f)
            self.assertIsNotNone(t, f"{f} חסר בקטלוג")
            for k in ("genre", "energy_level", "sound_family", "moods", "use_cases"):
                self.assertIn(k, t, f"{f} חסר {k}")
            self.assertFalse(t.get("isAiGenerated"), f"{f} מסומן AI")

    def test_new_sources_carry_a_license(self):
        for f, t in self.cat.items():
            if t.get("source") in ("pixabay", "mixkit"):
                self.assertTrue(t.get("license") and t.get("source_url"), f)
                self.assertNotEqual(t.get("vocals"), "lyrics", f)

    def test_pick_music_varies_sound_family(self):
        import local_finish_pipeline as L
        orig = L.ROTATION_STATE
        with tempfile.TemporaryDirectory() as d:
            L.ROTATION_STATE = Path(d) / "rot.json"
            try:
                fams = []
                for _ in range(4):
                    fams.append(self.cat[L.pick_music("value", None).name].get("sound_family"))
                    time.sleep(1.05)
            finally:
                L.ROTATION_STATE = orig
        self.assertEqual(len(fams), len(set(fams)), f"משפחות חוזרות: {fams}")


if __name__ == "__main__":
    unittest.main()
