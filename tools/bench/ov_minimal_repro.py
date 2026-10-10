#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""‏2×2: מי בעל הבאג — הבסיס או השכבה? ומה הרפרודוקציה המינימלית?

מה שכבר נשלל **על הפקודה האמיתית** (‏31.7.26): filter_complex_threads ·
threads · genpts · tpad · eof_action=repeat · shortest=0 · ‎-frames:v ·
שכבת הכתוביות · ריפוד שקוף · enable. הפלט קופא על `frame=25 / 0.76ש`.

לכן מפרקים לשני צדדים:
  בסיס אמיתי + שכבה סינתטית   → אם נתקע, הבעיה בבסיס
  בסיס סינתטי + שכבה אמיתית   → אם נתקע, הבעיה בשכבה
  שניהם סינתטיים               → רפרודוקציה מינימלית לדיווח upstream

  python3 tools/bench/ov_minimal_repro.py [--timeout 20]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

W = Path.home() / "rel-video-work/V3-לולאה"
BASE_SRC = W / "INPUT.mp4"
T_IN, T_OUT = 31.23, 34.24
OVL = 0.88          # אורך השכבה שנתקע (‎≥1.4 עובר)
OUT = Path("/tmp/ov_min")

NORM = ("scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1")


def run(label, args, timeout):
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error"] + args
    t = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        rc, err = r.returncode, (r.stderr or "")[-180:].replace("\n", " ")
    except subprocess.TimeoutExpired:
        rc, err = 124, "TIMEOUT"
    el = time.time() - t
    print(f"{'✅' if rc == 0 else '⏳' if rc == 124 else '❌'} {label:<38} "
          f"{el:6.1f}ש {'' if rc == 0 else err}", flush=True)
    return rc == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--brollpath", default=None)
    a = ap.parse_args()

    broll = a.brollpath
    if not broll:
        import json
        plan = json.loads((W / "broll_plan.json").read_text(encoding="utf-8"))
        broll = plan["plan"][0]["path"]

    dur = T_OUT - T_IN
    g = (f"[0:v]{NORM}[base];"
         f"[1:v]{NORM},format=yuva420p,setpts=PTS-STARTPTS[br];"
         f"[base][br]overlay=0:0:eof_action=pass[o];"
         f"[o]fps=30[vout]")

    # 1) בסיס אמיתי + שכבה אמיתית — הרפרודוקציה כפי שהיא
    run("בסיס אמיתי + שכבה אמיתית",
        ["-ss", f"{T_IN}", "-to", f"{T_OUT}", "-i", str(BASE_SRC),
         "-ss", "2.32", "-t", f"{OVL}", "-i", str(broll),
         "-filter_complex", g, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         str(OUT / "a.mkv")], a.timeout)

    # 2) בסיס אמיתי + שכבה סינתטית
    run("בסיס אמיתי + שכבה סינתטית",
        ["-ss", f"{T_IN}", "-to", f"{T_OUT}", "-i", str(BASE_SRC),
         "-f", "lavfi", "-t", f"{OVL}", "-i",
         f"color=c=red:s=1080x1920:r=30",
         "-filter_complex", g, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         str(OUT / "b.mkv")], a.timeout)

    # 3) בסיס סינתטי + שכבה אמיתית
    run("בסיס סינתטי + שכבה אמיתית",
        ["-f", "lavfi", "-t", f"{dur}", "-i",
         f"testsrc=s=1080x1920:r=30",
         "-ss", "2.32", "-t", f"{OVL}", "-i", str(broll),
         "-filter_complex", g, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         str(OUT / "c.mkv")], a.timeout)

    # 4) שניהם סינתטיים
    run("שניהם סינתטיים",
        ["-f", "lavfi", "-t", f"{dur}", "-i", f"testsrc=s=1080x1920:r=30",
         "-f", "lavfi", "-t", f"{OVL}", "-i", f"color=c=red:s=1080x1920:r=30",
         "-filter_complex", g, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         str(OUT / "d.mkv")], a.timeout)

    # 5) בסיס אמיתי **בלי seek** (העתקה מראש) + שכבה אמיתית
    pre = OUT / "base_cut.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
                    "-ss", f"{T_IN}", "-to", f"{T_OUT}", "-i", str(BASE_SRC),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-an", str(pre)], capture_output=True)
    run("בסיס חתוך-מראש (בלי -ss) + שכבה",
        ["-i", str(pre), "-ss", "2.32", "-t", f"{OVL}", "-i", str(broll),
         "-filter_complex", g, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         str(OUT / "e.mkv")], a.timeout)

    # ── מועמדי תיקון: לנרמל את הזמנים של הבסיס במקום להימנע מ--ss ──
    print("\n— מועמדי תיקון —")
    g_sp = (f"[0:v]setpts=PTS-STARTPTS,{NORM}[base];"
            f"[1:v]{NORM},format=yuva420p,setpts=PTS-STARTPTS[br];"
            f"[base][br]overlay=0:0:eof_action=pass[o];"
            f"[o]fps=30[vout]")
    run("setpts=PTS-STARTPTS על הבסיס",
        ["-ss", f"{T_IN}", "-to", f"{T_OUT}", "-i", str(BASE_SRC),
         "-ss", "2.32", "-t", f"{OVL}", "-i", str(broll),
         "-filter_complex", g_sp, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         str(OUT / "f.mkv")], a.timeout)

    run("-avoid_negative_ts make_zero על הקלט",
        ["-avoid_negative_ts", "make_zero",
         "-ss", f"{T_IN}", "-to", f"{T_OUT}", "-i", str(BASE_SRC),
         "-ss", "2.32", "-t", f"{OVL}", "-i", str(broll),
         "-filter_complex", g, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         str(OUT / "h.mkv")], a.timeout)

    run("-noaccurate_seek",
        ["-noaccurate_seek", "-ss", f"{T_IN}", "-to", f"{T_OUT}", "-i", str(BASE_SRC),
         "-ss", "2.32", "-t", f"{OVL}", "-i", str(broll),
         "-filter_complex", g, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         str(OUT / "i.mkv")], a.timeout)

    # trim בגרף במקום -to בקלט (הקלט נפתח מ-T_IN וזורם)
    g_tr = (f"[0:v]trim=duration={dur:.3f},setpts=PTS-STARTPTS,{NORM}[base];"
            f"[1:v]{NORM},format=yuva420p,setpts=PTS-STARTPTS[br];"
            f"[base][br]overlay=0:0:eof_action=pass[o];"
            f"[o]fps=30[vout]")
    run("trim בגרף במקום -to",
        ["-ss", f"{T_IN}", "-i", str(BASE_SRC),
         "-ss", "2.32", "-t", f"{OVL}", "-i", str(broll),
         "-filter_complex", g_tr, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         str(OUT / "j.mkv")], a.timeout)

    # ‎-ss **אחרי** ‎-i = seek בצד הפלט: מפענח מההתחלה ומשליך בשלב אחר.
    run("-ss אחרי -i (seek בצד הפלט)",
        ["-i", str(BASE_SRC), "-ss", f"{T_IN}", "-to", f"{T_OUT}",
         "-ss", "2.32", "-t", f"{OVL}", "-i", str(broll),
         "-filter_complex", g, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         str(OUT / "k.mkv")], a.timeout)

    # ‎-noaccurate_seek + trim מפצה בגרף: מדויק **וגם** בלי הנתיב התקוע.
    kf = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
         "-show_entries", "frame=pts_time", "-of", "csv=p=0",
         "-read_intervals", f"{max(0, T_IN - 12):.2f}%{T_IN:.2f}", str(BASE_SRC)],
        capture_output=True, text=True)
    kts = [float(x.rstrip(",")) for x in (kf.stdout or "").split() if x.rstrip(",")]
    kts = [t for t in kts if t <= T_IN]
    delta = T_IN - (kts[-1] if kts else T_IN)
    g_na = (f"[0:v]trim=start={delta:.3f}:duration={dur:.3f},setpts=PTS-STARTPTS,"
            f"{NORM}[base];"
            f"[1:v]{NORM},format=yuva420p,setpts=PTS-STARTPTS[br];"
            f"[base][br]overlay=0:0:eof_action=pass[o];"
            f"[o]fps=30[vout]")
    run(f"-noaccurate_seek + trim מפצה ({delta:.2f}ש)",
        ["-noaccurate_seek", "-ss", f"{T_IN}", "-i", str(BASE_SRC),
         "-ss", "2.32", "-t", f"{OVL}", "-i", str(broll),
         "-filter_complex", g_na, "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         str(OUT / "l.mkv")], a.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
