#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""התכנסות: מצמצמים את **הפקודה האמיתית** צעד-צעד עד שהתקיעה נעלמת.

מצב הפתיחה (‏31.7.26): הרפרודוקציה המינימלית נרפאת ב-`-noaccurate_seek`,
והפקודה האמיתית לא. ההבדל המבני היחיד שנשאר הוא **שרשרת הנרמול**:
  אמיתי:      `setsar=1,fps=30,setparams=...`   (בלי scale — הקלט כבר 1080×1920)
  רפרודוקציה: `scale=1080:1920...,crop,setsar`  (עם scaler אמיתי)

כל צעד מסיר/מוסיף חוליה אחת. הצעד הראשון שבו הזמן צונח — הוא החוליה.
כל וריאציה נבנית מהפקודה שנלכדה, ולא מפקודה שנכתבה מחדש.

  python3 tools/bench/ov_converge.py [--seg 7] [--timeout 15]
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

OUT = Path("/tmp/ov_converge")


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


def run(cmd, label, timeout, n=0):
    c = list(cmd)
    c[-1] = str(OUT / f"c{n}.mkv")
    t = time.time()
    try:
        r = subprocess.run(c, capture_output=True, text=True, timeout=timeout)
        rc, err = r.returncode, (r.stderr or "")[-140:].replace("\n", " ")
    except subprocess.TimeoutExpired:
        rc, err = 124, "TIMEOUT"
    el = time.time() - t
    print(f"{'✅' if rc == 0 else '⏳' if rc == 124 else '❌'} {label:<44} "
          f"{el:6.1f}ש {'' if rc == 0 else err}", flush=True)
    return rc == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=str(Path.home() / "rel-video-work/V3-לולאה"))
    ap.add_argument("--seg", type=int, default=7)
    ap.add_argument("--timeout", type=float, default=15.0)
    a = ap.parse_args()

    tl = R.build_timeline(Path(a.workdir))
    seg = copy.deepcopy(tl.segments[a.seg])
    seg.broll = [seg.broll[0]]
    base = capture(tl, seg)
    if not base:
        print("לא נלכדה פקודה"); return 1
    fc = base.index("-filter_complex") + 1
    g0 = base[fc]

    def var(g, label, n):
        c = list(base); c[fc] = g
        return run(c, label, a.timeout, n)

    run(list(base), "בקרה — הפקודה האמיתית", a.timeout, 0)

    # 1. scaler אמיתי על **הבסיס בלבד** (הפרודיוסר, לא הצרכן)
    g1 = g0.replace("[base];", ",scale=1080:1920[base];", 1)
    var(g1, "scale על הבסיס", 1)

    # 2. scaler על **השכבה בלבד**
    g2 = g0.replace("[br1];", ",scale=1080:1920[br1];", 1)
    var(g2, "scale על השכבה", 2)

    # 3. על שניהם
    g3 = g1.replace("[br1];", ",scale=1080:1920[br1];", 1)
    var(g3, "scale על שניהם", 3)

    # 4. format=yuv420p על הבסיס (העתקת פריים בלי scaler)
    var(g0.replace("[base];", ",format=yuv420p[base];", 1),
        "format=yuv420p על הבסיס", 4)

    # 5. בלי setparams (מטא-דאטה בלבד)
    var(re.sub(r",setparams=[^,\[]*", "", g0), "בלי setparams", 5)

    # 6. בלי fps בשרשראות הנרמול (משאירים את זה שאחרי ה-overlay)
    g6 = g0.replace("setsar=1,fps=30,", "setsar=1,", 2)
    var(g6, "בלי fps בנרמול", 6)

    # 7. הבסיס עובר דרך trim מפורש (מנתק את הזרימה מה-seek)
    var(g0.replace("[0:v]", "[0:v]trim=start=0,setpts=PTS-STARTPTS,", 1),
        "trim+setpts על הבסיס", 7)

    # 8. **אותה פקודה בדיוק, ffmpeg 7** — האם זו רגרסיה של 8.x?
    #    זו השאלה היחידה שממנה נגזרת גם מסקנה וגם פתרון מעשי (נעילת גרסה).
    alt = Path("/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg")
    if alt.exists():
        c = list(base); c[0] = str(alt)
        run(c, "אותה פקודה — ffmpeg 7", a.timeout, 8)
    else:
        print("⏭  ffmpeg@7 לא מותקן — brew install ffmpeg@7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
