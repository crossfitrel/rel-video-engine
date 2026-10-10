#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""וריאנטים **בתוך** ההקשר של render_segment — הקבצים הזמניים עדיין חיים."""
import subprocess, sys, time
from pathlib import Path

SYS = Path.home() / ("Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/"
                     "01 - שיווק/תוכן שיווקי/Social Video Editing System")
sys.path.insert(0, str(SYS / "tools"))
from relvid import render as R                                    # noqa: E402

W = Path.home() / "rel-video-work/V3-לולאה"
tl = R.build_timeline(W, brand="rel", broll_plan_file=str(W / "broll_plan.json"))
seg = [s for s in tl.segments if len(s.broll) >= 3][0]
OUT = "/tmp/ovb/out.mkv"


def drop_audio(v):
    fc = v.index("-filter_complex") + 1
    v[fc] = ";".join(p for p in v[fc].split(";") if not p.startswith("[0:a]"))
    while "[aout]" in v:
        i = v.index("[aout]"); del v[i - 1:i + 1]
    for k in ("-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"):
        if k in v:
            v.remove(k)
    return v[:-1] + ["-an", v[-1]]


def drop_frames(v):
    if "-frames:v" in v:
        i = v.index("-frames:v"); del v[i:i + 2]
    return v


def fast(v):
    if "medium" in v:
        v[v.index("medium")] = "ultrafast"
    if "19" in v:
        v[v.index("19")] = "30"
    return v


def drop_tpad(v):
    fc = v.index("-filter_complex") + 1
    v[fc] = v[fc].replace(",tpad=stop_mode=clone:stop_duration=0.5", "")
    return v


def add_tqs(v):
    out, i = [], 0
    while i < len(v):
        if v[i] == "-i":
            out += ["-thread_queue_size", "4096", "-i", v[i + 1]]; i += 2
        else:
            out.append(v[i]); i += 1
    return out


def no_eof_pass(v):
    """eof_action=pass ⇒ repeat. אם overlay מורעב כי הקלט המשני נגמר/מאוחר,
    repeat מחזיק את הפריים האחרון במקום להמתין."""
    fc = v.index("-filter_complex") + 1
    v[fc] = v[fc].replace("eof_action=pass", "eof_action=repeat:repeatlast=1")
    return v


def shortest_off(v):
    fc = v.index("-filter_complex") + 1
    v[fc] = v[fc].replace("overlay=0:0:eof_action=pass",
                          "overlay=0:0:eof_action=pass:shortest=0:repeatlast=0")
    return v


VARIANTS = [("מקור", lambda v: v), ("בלי אודיו", drop_audio),
            ("בלי -frames:v", drop_frames), ("ultrafast/crf30", fast),
            ("בלי tpad-stop", drop_tpad), ("thread_queue_size", add_tqs),
            ("eof_action=repeat", no_eof_pass), ("repeatlast=0", shortest_off)]

_orig = R.sh
DONE = {"n": 0}


def _spy(cmd, *a, **k):
    cmd = [str(c) for c in cmd]
    if "-filter_complex" not in cmd or DONE["n"]:
        return _orig(cmd, *a, **k)
    DONE["n"] = 1
    for tag, fn in VARIANTS:
        v = fn([x for x in cmd])
        v[-1] = OUT
        t0 = time.time()
        try:
            r = subprocess.run(v, capture_output=True, text=True, timeout=45)
            st = "✅" if r.returncode == 0 else f"❌ {(r.stderr or '').strip()[-70:]}"
        except subprocess.TimeoutExpired:
            st = "⏱ נתקע"
            subprocess.run(["pkill", "-f", "ovb/out.mkv"])
        print(f"{tag:<20} {st}  {time.time()-t0:.1f}ש", flush=True)

    class R0:
        returncode, stdout, stderr = 1, "", "probe done"
    return R0()


R.sh = _spy
R.render_segment(tl, seg, W / ".rendercache", force=True)
