#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""הפלט קופא **בדיוק על EOF של הבירול** — שתי בדיקות שנגזרות מזה.

הראיה (‏31.7.26, `-loglevel debug` על הפקודה האמיתית): הבירול הוא 0.88ש,
והפלט תקוע על `frame=25 time=00:00:00.76` — כלומר ברגע שהקלט השני נגמר.
‏`eof_action=repeat` לא עזר, `shortest=0` לא עזר, `-frames:v` לא עזר.

  A. בלי שכבת הכתוביות — האם השרשור של **שני overlay** הוא המפעיל?
  B. ריפוד שקוף: הבירול לא נגמר לפני הבסיס בכלל (`tpad` על אלפא) —
     אם אין EOF באמצע, אין מקרה-קצה של framesync.

  python3 tools/bench/ov_eof_probe.py [--seg 7] [--timeout 20]
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

OUT = Path("/tmp/ov_eof_probe")


def capture(tl, seg):
    got, real = {}, R.sh

    def fake(cmd, timeout=None, **kw):
        c = [str(x) for x in cmd]
        if "-filter_complex" in c and "fc" not in got:
            got["fc"] = c
            return subprocess.CompletedProcess(args=c, returncode=0,
                                               stdout="", stderr="")
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
    print(f"{'✅' if rc == 0 else '⏳' if rc == 124 else '❌'} {label:<40} "
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
    fc = base.index("-filter_complex") + 1
    run(list(base), "בקרה", a.timeout)

    # ── A. בלי כתוביות — דרך הקוד האמיתי, לא ניתוח מחרוזות ──
    tl2 = copy.deepcopy(tl)
    tl2.cues = []
    seg2 = copy.deepcopy(seg)
    cmd2 = capture(tl2, seg2)
    if cmd2:
        cmd2[-1] = str(OUT / "v_nocap.mkv")
        run(cmd2, "בלי שכבת כתוביות", a.timeout)

    # ── B. ריפוד שקוף: הבירול לא נגמר לפני הבסיס ──
    seg_dur = seg.t_out - seg.t_in
    g = base[fc]
    m = re.search(r"setpts=PTS-STARTPTS\+([\d.]+)/TB\[br1\]", g)
    if m:
        pad = max(0.1, seg_dur + 1.0)
        g2 = g.replace(m.group(0),
                       f"tpad=stop_mode=add:stop_duration={pad:.2f}:"
                       f"color=#00000000,setpts=PTS-STARTPTS+{m.group(1)}/TB[br1]")
        c = list(base); c[fc] = g2; c[-1] = str(OUT / "v_pad.mkv")
        run(c, "ריפוד שקוף לבירול (tpad add)", a.timeout)

        # B2 — ריפוד **וגם** בלי enable (המסגרת השקופה כבר עושה את העבודה)
        g3 = re.sub(r":enable='between\(t,[\d.]+,[\d.]+\)'", "", g2)
        c = list(base); c[fc] = g3; c[-1] = str(OUT / "v_pad2.mkv")
        run(c, "ריפוד שקוף + בלי enable", a.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
