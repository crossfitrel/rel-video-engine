#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""האם v2 עדיין נתקע — ועל איזה סגמנט בדיוק. מדידה, לא זיכרון.

הסגמנט שנרשם כתקוע (‏27.21-34.24) כבר לא קיים בציר: ה-EDL השתנה מאז
והוא פוצל לשלושה. **אסור להסיק מכשל ישן על ציר חדש** — לכן מודדים כל
סגמנט מחדש, אחד-אחד, ורושמים זמן ו-rc.

  python3 tools/bench/ov_segment_timing.py [--timeout 60] [--only 3,4]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

SYS = Path.home() / ("Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/"
                     "01 - שיווק/תוכן שיווקי/Social Video Editing System")
sys.path.insert(0, str(SYS / "tools"))
from relvid import render as R                                    # noqa: E402

OUT = Path("/tmp/ov_segment_timing")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=str(Path.home() / "rel-video-work/V3-לולאה"))
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--only", default=None, help="אינדקסים מופרדים בפסיק")
    ap.add_argument("--json", dest="out_json", default="/tmp/ov_segment_timing.json")
    a = ap.parse_args()

    R.SEGMENT_SOFT_TIMEOUT = a.timeout
    tl = R.build_timeline(Path(a.workdir))
    idxs = ([int(x) for x in a.only.split(",")] if a.only
            else list(range(len(tl.segments))))

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in idxs:
        seg = tl.segments[i]
        t = time.time()
        r = R.render_segment(tl, seg, OUT, force=True)
        el = time.time() - t
        row = {"i": i, "t_in": seg.t_in, "t_out": seg.t_out,
               "n_broll": len(seg.broll), "secs": round(el, 1),
               "ok": bool(r.get("path")), "stalled": bool(r.get("stalled"))}
        rows.append(row)
        mark = "✅" if row["ok"] else ("⏳" if row["stalled"] else "❌")
        print(f"{mark} seg{i:<3} {seg.t_in:7.2f}-{seg.t_out:7.2f} "
              f"broll={len(seg.broll)} {el:6.1f}ש", flush=True)

    Path(a.out_json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                encoding="utf-8")
    bad = [r for r in rows if not r["ok"]]
    print(f"\n{'❌' if bad else '✅'} {len(rows)} סגמנטים · "
          f"{len(bad)} נכשלו/נתקעו · סה\"כ {sum(r['secs'] for r in rows):.0f}ש")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
