#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""‏seg7 (31.23-34.24) נתקע · seg6 ו-seg8 עם אותם קליפים לא. מה שונה?

מבודד **בתוך הסגמנט**: כל בירול לבד, ואז שינוי פרמטר אחד בכל פעם, על
הפקודה האמיתית של `render_segment` (לא שחזור דומה — שחזור דומה כבר עבר
בזמן שהאמיתי נתקע).

  python3 tools/bench/ov_seg7_probe.py [--seg 7] [--timeout 25]
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

SYS = Path.home() / ("Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/"
                     "01 - שיווק/תוכן שיווקי/Social Video Editing System")
sys.path.insert(0, str(SYS / "tools"))
from relvid import render as R                                    # noqa: E402

OUT = Path("/tmp/ov_seg7_probe")


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=duration,nb_frames,r_frame_rate,"
                        "avg_frame_rate,codec_name:format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def frames_in_range(path, ss, t):
    """כמה פריימים ffmpeg באמת מפיק לטווח שהפקודה מבקשת."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{ss:.3f}",
                        "-t", f"{t:.3f}", "-i", str(path), "-f", "null", "-",
                        "-stats_period", "1000"], capture_output=True, text=True)
    r2 = subprocess.run(["ffprobe", "-v", "error", "-read_intervals",
                         f"{ss}%+{t}", "-select_streams", "v:0",
                         "-show_entries", "frame=pts_time", "-of", "csv=p=0",
                         str(path)], capture_output=True, text=True)
    pts = [x for x in (r2.stdout or "").strip().splitlines() if x]
    return len(pts), (pts[:3], pts[-2:] if pts else [])


def run(tl, seg, label, timeout) -> tuple[bool, float]:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    R.SEGMENT_SOFT_TIMEOUT = timeout
    t = time.time()
    r = R.render_segment(tl, seg, OUT, force=True)
    el = time.time() - t
    ok = bool(r.get("path"))
    print(f"{'✅' if ok else '⏳'} {label:<42} {el:6.1f}ש", flush=True)
    return ok, el


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=str(Path.home() / "rel-video-work/V3-לולאה"))
    ap.add_argument("--seg", type=int, default=7)
    ap.add_argument("--timeout", type=float, default=25.0)
    a = ap.parse_args()

    tl = R.build_timeline(Path(a.workdir))
    seg = tl.segments[a.seg]
    print(f"seg{a.seg}  {seg.t_in:.2f}-{seg.t_out:.2f}  n_frames={seg.n_frames}")
    for i, b in enumerate(seg.broll):
        info = probe(b.path)
        st = (info.get("streams") or [{}])[0]
        n, sample = frames_in_range(b.path, b.src_offset, b.end - b.start)
        print(f"  br{i}: {b.start:.2f}-{b.end:.2f} off={b.src_offset:.2f} "
              f"len={b.end - b.start:.2f}")
        print(f"       קובץ: dur={st.get('duration')} nb_frames={st.get('nb_frames')} "
              f"fps={st.get('avg_frame_rate')} codec={st.get('codec_name')}")
        print(f"       פריימים בטווח המבוקש: {n}  {sample}")

    # ── בידוד: כל בירול לבד ──
    for i in range(len(seg.broll)):
        s2 = copy.deepcopy(seg)
        s2.broll = [seg.broll[i]]
        run(tl, s2, f"רק br{i}", a.timeout)
    s3 = copy.deepcopy(seg)
    s3.broll = []
    run(tl, s3, "בלי בירול בכלל", a.timeout)

    # ── מוטציות על הבירול התקוע: משנים **משתנה אחד** בכל פעם ──
    bad = 0
    muts = [
        ("start 0.00 → 0.10", lambda b: setattr(b, "start", 0.10)),
        ("src_offset 2.32 → 0.40", lambda b: setattr(b, "src_offset", 0.40)),
        ("end 0.88 → 1.50 (ארוך יותר)", lambda b: setattr(b, "end", 1.50)),
        ("fade 0.12 → 0", lambda b: setattr(b, "fade", 0.0)),
        ("הקובץ של br1 באותם זמנים",
         lambda b: setattr(b, "path", seg.broll[1].path)),
    ]
    for label, fn in muts:
        s = copy.deepcopy(seg)
        s.broll = [copy.deepcopy(seg.broll[bad])]
        fn(s.broll[0])
        run(tl, s, label, a.timeout)

    # ── סריקת אורך: איפה בדיוק הגבול? ──
    print("\n— סריקת אורך הבירול —")
    for ln in (0.40, 0.60, 0.80, 0.88, 1.00, 1.20, 1.40, 1.50):
        s = copy.deepcopy(seg)
        s.broll = [copy.deepcopy(seg.broll[bad])]
        s.broll[0].end = s.broll[0].start + ln
        run(tl, s, f"אורך {ln:.2f}ש", a.timeout)

    # ── אותו בירול בדיוק, על בסיס אחר: אורך או אינטראקציה? ──
    print("\n— אותו בירול על בסיס אחר —")
    for j in (5, 6, 8):
        s = copy.deepcopy(tl.segments[j])
        b = copy.deepcopy(seg.broll[bad])
        b.start, b.end = 0.0, 0.88
        s.broll = [b]
        run(tl, s, f"בסיס seg{j} ({s.t_in:.2f}-{s.t_out:.2f}) + בירול 0.88ש",
            a.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
