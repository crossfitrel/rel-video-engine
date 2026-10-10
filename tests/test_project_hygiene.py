import subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProjectHygieneTest(unittest.TestCase):
    def test_self_test_flags_media_and_junk(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "project_hygiene.py"), "--self-test"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
