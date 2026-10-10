#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ביסקציה על הסגמנט התקוע — דרך render_segment עצמו, לא דרך שחזור.

נמדד 31.7.26: סגמנט 27.21-34.24 עם **3** בירולים נתקע, בעוד 34.85-49.11
עם **6** בירולים מרנדר ב-9.1ש. כלומר `MATTRESS_MIN_CLIPS=3` נשען על הכללה
שגויה. כאן מנטרלים רכיב אחד בכל פעם ומודדים.

  python3 tools/bench/ov_bisect.py [--t-in 27.21] [--timeout 45]
"""
from __future__ import annotations

import argparse
import copy
import shutil
import sys
import time
from pathlib import Path

SYS = Path.home() / ("Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/"
                     "01 - שיווק/תוכן שיווקי/Social Video Editing System")
sys.path.insert(0, str(SYS / "tools"))
from relvid import render as R                                    # noqa: E402

W = Path.home() / "rel-video-work/V3-לולאה"
OUT = Path("/tmp/ov_bisect")


def run(tl, seg, label: str) -> tuple[bool, float]:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    t = time.time()
    r = R.render_segment(tl, seg, OUT, force=True)
    el = time.time() - t
    ok = bool(r.get("path"))
    print(f"  {label:<34} {'OK  ' if ok else 'תקוע'} {el:6.1f}ש")
    return ok, el


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--t-in", type=float, default=27.21)
    ap.add_argument("--timeout", type=float, default=45.0)
    a = ap.parse_args()
    R.SEGMENT_TIMEOUT = a.timeout

    tl = R.build_timeline(W, brand="rel",
                          broll_plan_file=str(W / "broll_plan.json"))
    base = min(tl.segments, key=lambda s: abs(s.t_in - a.t_in))
    print(f"סגמנט {base.t_in:.2f}-{base.t_out:.2f} · "
          f"{len(base.broll)} בירולים · timeout={a.timeout}ש\n")

    run(tl, copy.deepcopy(base), "כמו שהוא")

    # 1) כל בירול לבדו — מבודד "האם זה קליפ מסוים"
    for i in range(len(base.broll)):
        s = copy.deepcopy(base)
        s.broll = [copy.deepcopy(base.broll[i])]
        run(tl, s, f"רק בירול {i + 1}")

    # 2) זוגות — מבודד "האם זה צירוף"
    for i, j in ((0, 1), (0, 2), (1, 2)):
        s = copy.deepcopy(base)
        s.broll = [copy.deepcopy(base.broll[i]), copy.deepcopy(base.broll[j])]
        run(tl, s, f"בירולים {i + 1}+{j + 1}")

    # 3) בלי בירול בכלל — מבודד "האם זה הסגמנט עצמו"
    s = copy.deepcopy(base)
    s.broll = []
    run(tl, s, "בלי בירול")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
