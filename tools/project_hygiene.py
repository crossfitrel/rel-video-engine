#!/usr/bin/env python3
"""project_hygiene — שומר שתיקיית הידע (הפרויקט ב-claude.ai / התיקייה המסונכרנת) נשארת ידע בלבד.

v10 ענן (10.10.26): הפרויקט התמלא ב-853 קבצי מדיה/תוצרים (5.6GB) ונגמר המקום.
מדיה, תוצרי עבודה, לוגים, .bak וסקריפטים חד-פעמיים חיים ב-Drive של hayonhq (REL Video Cloud/)
או בריפו — לא בתיקייה המסונכרנת.

שימוש:
  project_hygiene.py scan <תיקייה> [--json]   → exit 1 אם נמצאו קבצים אסורים
  project_hygiene.py --self-test

סריקה מדלגת על קוד/ספריות שנשארים במק עד הכיבוי המקומי (KEEP_DIRS) — הם מחוץ לסנכרון הידע.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MEDIA_EXT = {
    ".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mp3", ".wav", ".m4a", ".aac", ".flac",
    ".png", ".jpg", ".jpeg", ".heic", ".gif", ".webp", ".tif", ".tiff", ".psd",
    ".zip", ".tar", ".gz", ".skill", ".ttf", ".otf", ".woff", ".woff2", ".pdf",
}
JUNK_RE = re.compile(
    r"(\.bak(-|$)|\.log$|\.jsonl$|\.err$|\.tmp$|^FINAL_prev_|^EXPORT|^MIXED|^clip_\d+|"
    r"להדבקה\.md$|^_opus55_|^_td26_|^_qa_|^_cmp$|^_hf_demo$|^_baseline_)"
)
# תיקיות שנשארות במק עד כיבוי המערכת המקומית (קוד/ספריות שה-fallback צריך). לא נסרקות.
KEEP_DIRS = {"tools", "tests", "review-app", "captions-app", "scripts", "golden", "skills",
             "בירולים", "בירולים - מיכאל לוי 28.5", "brand-assets", "_intake-inbox",
             "תוצרי-אנימציה", "deliverables", ".git", "node_modules", "__pycache__"}
MAX_TEXT_BYTES = 400_000  # מסמך ידע גדול מזה = כנראה דאמפ/לוג


def violations(root: Path) -> list[dict]:
    out = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in KEEP_DIRS for part in rel.parts):
            continue
        if p.name == ".DS_Store" or not p.is_file():
            continue
        why = None
        if p.suffix.lower() in MEDIA_EXT:
            why = "media"
        elif any(JUNK_RE.search(part) for part in rel.parts):
            why = "junk"
        elif p.stat().st_size > MAX_TEXT_BYTES:
            why = "oversize"
        if why:
            out.append({"path": str(rel), "bytes": p.stat().st_size, "why": why})
    return out


def _self_test() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "docs").mkdir()
        (r / "docs" / "ok.md").write_text("ידע")
        (r / "a.mp4").write_bytes(b"0")
        (r / "CHANGELOG.md.bak-v948").write_text("x")
        (r / "_td26_vision").mkdir()
        (r / "_td26_vision" / "x.json").write_text("{}")
        (r / "tools").mkdir()
        (r / "tools" / "sfx.wav").write_bytes(b"0")  # KEEP_DIRS — לא נספר
        v = {x["path"]: x["why"] for x in violations(r)}
        assert v == {"a.mp4": "media", "CHANGELOG.md.bak-v948": "junk",
                     "_td26_vision/x.json": "junk"}, v
    print("project_hygiene self-test ✓")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--self-test"]:
        return _self_test()
    if len(argv) < 2 or argv[0] != "scan":
        print(__doc__)
        return 2
    v = violations(Path(argv[1]))
    if "--json" in argv:
        print(json.dumps(v, ensure_ascii=False, indent=1))
    else:
        mb = sum(x["bytes"] for x in v) / 1e6
        print(f"project_hygiene: {len(v)} קבצים אסורים ({mb:.1f}MB)" if v else "project_hygiene: נקי ✓")
        for x in v[:15]:
            print(f"  [{x['why']}] {x['path']}")
    return 1 if v else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
