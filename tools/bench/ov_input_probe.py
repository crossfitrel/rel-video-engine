#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""בודק כל קלט בפקודת render_segment בנפרד: כמה פריימים הוא באמת מפיק.

ההשערה שנבדקת: overlay עם `eof_action=pass` על pad שלא קיבל **אף פריים**
ממתין לנצח — ה-filtergraph לא יכול להתקדם, ה-CPU יורד ל-0, ואף שגיאה לא
נכתבת. אם קלט אחד מחזיר 0 פריימים, זה השורש.

  python3 tools/bench/ov_input_probe.py 27.21
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SYS = Path.home() / ("Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/"
                     "01 - שיווק/תוכן שיווקי/Social Video Editing System")
sys.path.insert(0, str(SYS / "tools"))
from relvid import render as R                                    # noqa: E402

W = Path.home() / "rel-video-work/V3-לולאה"


def probe_dur(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True)
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return -1.0


def count_frames(path: str, ss: float, t: float) -> int:
    """כמה פריימים הקלט מפיק **עם אותם -ss/-t** של הפקודה האמיתית."""
    r = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error",
         "-ss", f"{ss:.3f}", "-t", f"{t:.3f}", "-i", path,
         "-map", "0:v:0", "-f", "null", "-"],
        capture_output=True, text=True)
    if r.returncode:
        return -1
    r2 = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
         "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0",
         "-read_intervals", f"{ss}%+{t}", path],
        capture_output=True, text=True)
    try:
        return int((r2.stdout or "0").strip().split(",")[0])
    except Exception:
        return -1


def main() -> int:
    want = float(sys.argv[1]) if len(sys.argv) > 1 else 27.21
    tl = R.build_timeline(W, brand="rel",
                          broll_plan_file=str(W / "broll_plan.json"))
    seg = min(tl.segments, key=lambda s: abs(s.t_in - want))
    print(f"סגמנט {seg.t_in:.2f}-{seg.t_out:.2f} · {len(seg.broll)} בירולים · "
          f"speed={seg.speed}")
    bad = []
    for i, b in enumerate(seg.broll, start=1):
        ss = max(0.0, b.src_offset)
        t = max(0.05, b.end - b.start)
        dur = probe_dur(b.path)
        n = count_frames(b.path, ss, t)
        flag = ""
        if n <= 0:
            flag = "  ⛔ אפס פריימים"
            bad.append(b.path)
        elif ss >= dur:
            flag = "  ⛔ ss מעבר לסוף הקליפ"
            bad.append(b.path)
        elif ss + t > dur + 0.05:
            flag = f"  ⚠️ ss+t={ss + t:.2f} > dur={dur:.2f}"
        print(f"  קלט {i}: ss={ss:6.3f} t={t:5.3f} dur={dur:6.3f} "
              f"frames={n:4d} on={b.start:.2f}-{b.end:.2f}{flag}")
        print(f"          {Path(b.path).name}")
    print(f"\nקלטים בעייתיים: {len(bad)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
