#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""visual_hook_fixtures.py — עותקי E2E מבודדים ל-Visual Hook Engine (11.9.26).

קורא את handoff/visual-hook-engine/evidence/sample_audit.json ובונה לכל אחד
משבעת הסרטונים עותק ב-<work_root>/.e2e/visual-hook/caseNN/:
  * מדיה: שיבוט APFS (`cp -c`) — אפס מקום, ובלתי-תלוי במקור (כתיבה לעותק לא
    נוגעת במקור). בלי APFS — עותק רגיל.
  * JSON: עותק. project_manifest מקבל project_id בדיקה (prj_vhtestNN), ומנוקה
    מ-monday_item_id / schedule_approval / state_override — כך שאף חיפוש לפי
    שם/מזהה לא יגיע לפריט אמיתי ב-Monday/Metricool.
  * לא מועתקים: artifacts/, runs/, FINAL*, revisions/, corrections.jsonl.

שימוש:  python3 tools/bench/visual_hook_fixtures.py [--force]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
SYSDIR = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from relvid.paths import work_root   # noqa: E402

AUDIT = SYSDIR / "handoff" / "visual-hook-engine" / "evidence" / "sample_audit.json"
MEDIA = ("INPUT.mp4", "EXPORT.mp4", "EXPORT_TIGHT.mp4")
JSONS = ("edl.json", "tight_keeps.json", "words_final.json", "words_pre_tight.json",
         "whisper_raw.json", "whisper_export.json", "whisper_export_tight.json",
         "sentences.json", "sentences_tight.json", "broll_plan.json", "FINAL_PROVENANCE.json",
         "edited.txt", "correct_transcript.txt", "words_corrected.json", "transcript_fix.json",
         "segment_sources.json", "illustration_plan.json", "brief.json", "intent_card.md")
SCRUB = ("monday_item_id", "schedule_approval", "state_override", "media")


def clone(src: Path, dst: Path):
    r = subprocess.run(["cp", "-c", "-p", str(src), str(dst)], capture_output=True)
    if r.returncode != 0:
        shutil.copy2(src, dst)


def build(force=False, extra_projects=()) -> list:
    root = work_root() / ".e2e" / "visual-hook"
    root.mkdir(parents=True, exist_ok=True)
    out = []
    samples = json.loads(AUDIT.read_text(encoding="utf-8"))
    # פרויקטים נוספים שהסריקה מצאה להם מועמד (visual_hook_scan.py) — אותו בידוד בדיוק
    for name in extra_projects:
        samples.append({"project": name, "project_id": None,
                        "source": str(work_root() / name / "EXPORT_TIGHT.mp4")})
    for i, s in enumerate(samples, start=1):
        src = Path(s["source"]).parent
        case = root / f"case{i:02d}"
        if case.exists() and not force:
            out.append({"case": case.name, "project": s["project"], "status": "exists"})
            continue
        if case.exists():
            shutil.rmtree(case)
        case.mkdir(parents=True)
        for n in MEDIA:
            if (src / n).exists():
                clone(src / n, case / n)
        for n in JSONS:
            if (src / n).exists():
                shutil.copy2(src / n, case / n)
        mani = json.loads((src / "project_manifest.json").read_text(encoding="utf-8")) \
            if (src / "project_manifest.json").exists() else {}
        for k in SCRUB:
            mani.pop(k, None)
        mani["source_project_id"] = mani.get("project_id") or s["project_id"]
        mani["project_id"] = f"prj_vhtest{i:02d}"
        mani["name"] = s["project"]
        mani["e2e_fixture"] = {"source_dir": str(src), "purpose": "visual-hook-engine",
                               "never_publish": True}
        fp = mani.get("finish_prefs") or {}
        mani["finish_prefs"] = {k: v for k, v in fp.items() if k in ("music", "broll")}
        (case / "project_manifest.json").write_text(json.dumps(mani, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")
        ss = json.loads((case / "segment_sources.json").read_text(encoding="utf-8")) \
            if (case / "segment_sources.json").exists() else {}
        for ov in ss.get("overrides") or []:
            p = Path(str(ov.get("src", "")))
            if p.name and not p.is_absolute() and (src / p).exists() and not (case / p).exists():
                clone(src / p, case / p)
        out.append({"case": case.name, "project": s["project"], "status": "built",
                    "expected": s.get("expected")})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--extra", nargs="*", default=[], help="שמות פרויקטים נוספים (case08 והלאה)")
    a = ap.parse_args()
    for row in build(a.force, a.extra):
        print(json.dumps(row, ensure_ascii=False))
