#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""התיקון עבד ברפרודוקציה המינימלית ולא בפקודה האמיתית. מה ההבדל?

לקח נעול מהמערכת: *"בידוד על הפקודה האמיתית, לא על שחזור דומה"*. כאן
הכיוון ההפוך של אותה מלכודת — תיקון שאומת על שחזור מינימלי חייב להיבדק
על הפקודה האמיתית לפני שקוראים לו תיקון.

  python3 tools/bench/ov_safeseek_probe.py [--seg 7] [--timeout 20]
"""
from __future__ import annotations

import argparse
import copy
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SYS = Path.home() / ("Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/"
                     "01 - שיווק/תוכן שיווקי/Social Video Editing System")
sys.path.insert(0, str(SYS / "tools"))
from relvid import render as R                                    # noqa: E402

OUT = Path("/tmp/ov_safeseek")


def capture(tl, seg):
    got, real = {}, R.sh

    def fake(cmd, timeout=None, **kw):
        c = [str(x) for x in cmd]
        if "-filter_complex" in c and "fc" not in got:
            got["fc"] = c
            return subprocess.CompletedProcess(args=c, returncode=0, stdout="", stderr="")
        return real(cmd, timeout=timeout, **kw)

    R.sh = fake
    try:
        shutil.rmtree(OUT, ignore_errors=True)
        OUT.mkdir(parents=True, exist_ok=True)
        R.render_segment(tl, seg, OUT, force=True)
    finally:
        R.sh = real
    cmd = got.get("fc")
    if cmd:
        for x in cmd:
            if x.endswith("caps.txt"):
                Path(x).parent.mkdir(parents=True, exist_ok=True)
                R._caption_pngs(tl, seg, Path(x).parent)
                break
    return cmd


def run(cmd, label, timeout):
    t = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        rc, err = r.returncode, (r.stderr or "")[-200:].replace("\n", " ")
    except subprocess.TimeoutExpired:
        rc, err = 124, "TIMEOUT"
    el = time.time() - t
    print(f"{'✅' if rc == 0 else '⏳' if rc == 124 else '❌'} {label:<42} "
          f"{el:6.1f}ש {'' if rc == 0 else err}", flush=True)
    return rc == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=str(Path.home() / "rel-video-work/V3-לולאה"))
    ap.add_argument("--seg", type=int, default=7)
    ap.add_argument("--timeout", type=float, default=20.0)
    a = ap.parse_args()

    tl = R.build_timeline(Path(a.workdir))
    seg = copy.deepcopy(tl.segments[a.seg])
    seg.broll = [seg.broll[0]]
    base = capture(tl, seg)
    if not base:
        print("לא נלכדה פקודה"); return 1
    base[-1] = str(OUT / "v.mkv")

    safe = R._safe_seek_cmd(base, seg)
    if not safe:
        print("‏_safe_seek_cmd החזיר None — ההנחות על מבנה הפקודה נשברו"); return 1
    safe[-1] = str(OUT / "v_safe.mkv")
    run(safe, "safe-seek על הפקודה האמיתית", a.timeout)

    fc = safe.index("-filter_complex") + 1

    def drop_frames(c):
        c = list(c)
        if "-frames:v" in c:
            i = c.index("-frames:v"); c = c[:i] + c[i + 2:]
        return c

    run(drop_frames(safe), "safe-seek בלי -frames:v", a.timeout)

    c = list(safe)
    c[fc] = re.sub(r",tpad=stop_mode=clone:stop_duration=[\d.]+", "", c[fc])
    c[-1] = str(OUT / "v_notpad.mkv")
    run(c, "safe-seek בלי tpad", a.timeout)

    # בלי כתוביות — דרך הקוד האמיתי
    tl2 = copy.deepcopy(tl); tl2.cues = []
    c2 = capture(tl2, copy.deepcopy(seg))
    if c2:
        s2 = R._safe_seek_cmd(c2, seg)
        if s2:
            s2[-1] = str(OUT / "v_nocap.mkv")
            run(s2, "safe-seek בלי כתוביות", a.timeout)

    # בלי אודיו
    c3 = list(safe)
    c3[fc] = re.sub(r";\[0:a\][^;]*\[aout\]", "", c3[fc])
    if "-map" in c3:
        while "[aout]" in c3:
            i = c3.index("[aout]"); c3 = c3[:i - 1] + c3[i + 1:]
    c3[-1] = str(OUT / "v_noaud.mkv")
    run(c3, "safe-seek בלי אודיו", a.timeout)

    print("\n— הגרף האמיתי —")
    print("   " + safe[fc].replace(";", ";\n   "))

    def variant(sub, label, pattern, repl):
        c = list(safe)
        c[fc] = re.sub(pattern, repl, c[fc])
        if c[fc] == safe[fc]:
            print(f"⏭  {label} — אין מה להחליף"); return
        c[-1] = str(OUT / f"v_{sub}.mkv")
        run(c, label, a.timeout)

    variant("nofade", "safe-seek בלי fade על האלפא",
            r"fade=t=in:[^,]*,fade=t=out:[^,]*,", "")
    variant("noenable", "safe-seek בלי enable",
            r":enable='between\(t,[\d.]+,[\d.]+\)'", "")
    variant("nofps", "safe-seek בלי fps=30", r"fps=30,", "")
    # ההבדל שנותר מול הרפרודוקציה שעבדה: שם היה `scale` אמיתי בשרשרת.
    variant("scale", "safe-seek + scale על הבסיס",
            r"\[base\]", "scale=1080:1920[base]")
    variant("fmt", "safe-seek + format=yuv420p על הבסיס",
            r"\[base\]", "format=yuv420p[base]")

    c = list(base)   # בלי safe-seek בכלל, רק scale
    fcb = c.index("-filter_complex") + 1
    c[fcb] = c[fcb].replace("[base]", "scale=1080:1920[base]", 1)
    c[-1] = str(OUT / "v_scale_plain.mkv")
    run(c, "בלי safe-seek + scale על הבסיס", a.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
