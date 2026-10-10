#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""הזרקת-כשל ממוקדת: כמה overlay-ים בשרשרת אחת ffmpeg עוד סוגר?
מריץ את אותה שרשרת בדיוק שנתקעה, עם timeout, ומשווה שתי צורות בנייה."""
import json, subprocess, sys, time
from pathlib import Path

W = Path.home() / "rel-video-work/V3-לולאה"
plan = json.loads((W / "broll_plan.json").read_text(encoding="utf-8"))["plan"]
BASE = str(W / "INPUT.mp4")
NORM = ("setsar=1,fps=30,setparams=color_primaries=bt709:color_trc=bt709:"
        "colorspace=bt709:range=tv")


def build(n, mode):
    clips = [p for p in plan if Path(p["path"]).exists()][:n]
    dur = sum(2.7 for _ in clips)
    cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
           "-ss", "27.210", "-to", f"{27.210 + dur:.3f}", "-i", BASE]
    for p in clips:
        cmd += ["-ss", f"{p['src_offset']:.3f}", "-t", "2.700", "-i", p["path"]]
    parts, cur, t = [f"[0:v]{NORM}[base]"], "base", 0.0
    for i, _ in enumerate(clips, start=1):
        bs, be = t, t + 2.7
        if mode == "setpts":
            parts.append(f"[{i}:v]{NORM},format=yuva420p,"
                         f"fade=t=in:st=0:d=0.12:alpha=1,"
                         f"fade=t=out:st=2.58:d=0.12:alpha=1,"
                         f"setpts=PTS-STARTPTS+{bs:.3f}/TB[br{i}]")
        else:   # tpad — הקלט המשני זורם מ-t=0 ולכן overlay אף פעם לא מורעב
            parts.append(f"[{i}:v]{NORM},format=yuva420p,"
                         f"fade=t=in:st=0:d=0.12:alpha=1,"
                         f"fade=t=out:st=2.58:d=0.12:alpha=1,"
                         f"setpts=PTS-STARTPTS"
                         + (f",tpad=start_duration={bs:.3f}:start_mode=add:"
                            f"color=black@0.0" if bs > 0.001 else "")
                         + f"[br{i}]")
        parts.append(f"[{cur}][br{i}]overlay=0:0:eof_action=pass:"
                     f"enable='between(t,{bs:.3f},{be:.3f})'[ov{i}]")
        cur = f"ov{i}"
        t = be
    cmd += ["-filter_complex", ";".join(parts), "-map", f"[{cur}]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
            "-an", f"/tmp/ovprobe_{mode}_{n}.mp4"]
    return cmd


for mode in ("setpts", "tpad"):
    for n in (1, 2, 3, 4, 6):
        t0 = time.time()
        try:
            r = subprocess.run(build(n, mode), capture_output=True, text=True,
                               timeout=45)
            ok = "✅" if r.returncode == 0 else f"❌ rc={r.returncode}"
            err = (r.stderr or "").strip().splitlines()[-1:] or [""]
            print(f"{mode:<7} n={n}  {ok}  {time.time()-t0:.1f}ש  {err[0][:70]}")
        except subprocess.TimeoutExpired:
            print(f"{mode:<7} n={n}  ⏱ נתקע (>45ש)")
            subprocess.run(["pkill", "-f", f"ovprobe_{mode}_{n}"])
