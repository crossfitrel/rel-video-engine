#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""visual_hook_scan.py — ניתוח shadow על **עותקים** של כל הפרויקטים בתיקיית העבודה (11.9.26).

מטרה: למצוא אילו פתיחות קיימות המנוע היה מציע להדגיש, כדי שהראל יוכל להשוות
על דוגמאות אמיתיות — בלי לגעת בפרויקט אמיתי. כל פרויקט משובט (APFS) לתוך
.e2e/visual-hook/scan/<שם>/ עם project_id בדיקה, ורק שם נכתבים קבצי הניתוח.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
sys.path.insert(0, str(TOOLS))
from relvid.paths import work_root                    # noqa: E402
from relvid import visual_hook as VH                  # noqa: E402

WORK = work_root()
OUT = WORK / ".e2e" / "visual-hook" / "scan"
KEEP = ("INPUT.mp4", "EXPORT.mp4", "EXPORT_TIGHT.mp4", "edl.json", "tight_keeps.json", "words_final.json",
        "sentences_tight.json", "broll_plan.json", "illustration_plan.json", "project_manifest.json",
        "FINAL_PROVENANCE.json", "segment_sources.json")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for d in sorted(WORK.iterdir()):
        if not d.is_dir() or d.name.startswith((".", "_")):
            continue
        if not (d / "words_final.json").exists() or not VH.resolve_body(d).exists() \
                or not (d / "project_manifest.json").exists():
            continue
        c = OUT / d.name
        if c.exists():
            shutil.rmtree(c)
        c.mkdir(parents=True)
        for n in KEEP:
            if (d / n).exists():
                r = subprocess.run(["cp", "-c", "-p", str(d / n), str(c / n)], capture_output=True)
                if r.returncode != 0:
                    shutil.copy2(d / n, c / n)
        m = json.loads((c / "project_manifest.json").read_text(encoding="utf-8"))
        for k in ("monday_item_id", "schedule_approval", "state_override", "media"):
            m.pop(k, None)
        m["source_project_id"] = m.get("project_id")
        m["project_id"] = "prj_vhscan" + str(abs(hash(d.name)) % 10**6)
        m["name"] = d.name
        (c / "project_manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        t0 = time.time()
        try:
            res = VH.run_selection(c, mode="shadow")
            p = res["plan"]
            crop = next(x for x in res["candidates"] if x["recipe"] == "SMART_PUNCH_IN")
            rows.append({"project": d.name, "content_type": res["context"]["content_type"],
                         "suggestion": p["recipe"], "reasons": p["selection"]["reason_codes"],
                         "crop_reasons": crop["reason_codes"], "score": (crop.get("score") or {}).get("net"),
                         "cue": crop["cues"][0] if crop["cues"] else None,
                         "anchor": ((res["analysis"]["hook"] or {}).get("anchor") or {}).get("word"),
                         "secs": round(time.time() - t0, 1)})
        except Exception as e:
            rows.append({"project": d.name, "error": str(e)[:200]})
        print(json.dumps(rows[-1], ensure_ascii=False))
    (OUT / "scan_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    elig = [r for r in rows if r.get("suggestion") == "SMART_PUNCH_IN"]
    print(f"\nנסרקו {len(rows)} · הצעת הדגשה: {len(elig)} · שגיאות: {sum(1 for r in rows if 'error' in r)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
