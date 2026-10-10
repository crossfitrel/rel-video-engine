#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""סריקת וריאנטים על **הפקודה האמיתית** של הסגמנט התקוע.

מה שכבר נשלל במדידה ואין טעם לחזור עליו: אודיו · `-frames:v` · preset/crf ·
`tpad` · `thread_queue_size` · `eof_action` · iCloud · אורך קליפ מול
`src_offset` · מספר הבירולים (6 עובד, 3 נתקע) · אורך הכתוביות (תואם בדיוק).

  python3 tools/bench/ov_variant_sweep.py [--timeout 25]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ov_stall_debug as D                                        # noqa: E402

OUT = Path("/tmp/ov_sweep")


def fc_of(cmd):
    return cmd[cmd.index("-filter_complex") + 1]


def set_fc(cmd, fc):
    c = list(cmd)
    c[c.index("-filter_complex") + 1] = fc
    return c


# ── וריאנטים ──────────────────────────────────────────────────────────────
def v_base_reset_pts(cmd):
    """[base] מקבל setpts=PTS-STARTPTS — מיישר את ציר הראשי לאפס מוחלט."""
    fc = fc_of(cmd).replace("[base]", ",setpts=PTS-STARTPTS[base]", 1)
    return set_fc(cmd, fc)


def v_repeatlast0(cmd):
    return set_fc(cmd, fc_of(cmd).replace("overlay=0:0:eof_action=pass",
                                          "overlay=0:0:eof_action=pass:repeatlast=0"))


def v_no_enable(cmd):
    return set_fc(cmd, re.sub(r":enable='between\(t,[\d.]+,[\d.]+\)'", "",
                              fc_of(cmd)))


def v_broll_shortest(cmd):
    return set_fc(cmd, fc_of(cmd).replace("overlay=0:0:eof_action=pass",
                                          "overlay=0:0:eof_action=pass:shortest=0"))


def v_broll_fps_after_setpts(cmd):
    """fps מחדש **אחרי** ה-setpts של הבירול — הזזת ציר יכולה לשבור CFR."""
    return set_fc(cmd, re.sub(r"(setpts=PTS-STARTPTS\+[\d.]+/TB)(\[br\d+\])",
                              r"\1,fps=30\2", fc_of(cmd)))


def v_fps_mode_cfr(cmd):
    c = list(cmd)
    return c[:-1] + ["-fps_mode", "cfr", c[-1]]


def v_filter_threads1(cmd):
    """‏filter_threads=1 — אם זו תחרות בין תהליכוני ה-filtergraph."""
    c = list(cmd)
    return c[:1] + ["-filter_threads", "1", "-filter_complex_threads", "1"] + c[1:]


def _drop_caption(cmd):
    """מסיר את קלט הכתוביות **ואת ה-overlay שלו** — לא רק cues ריק.
    ‏cues=[] בודק "בלי קלט כתוביות בכלל"; כאן הקלט קיים בפרויקט אבל מוסר
    מהפקודה, וזה מצב אחר."""
    c = list(cmd)
    i = c.index("-f") if "-f" in c else -1
    if i < 0 or c[i + 1] != "concat":
        return c
    del c[i:i + 5]                      # -f concat -safe 0 -i <file>
    fc = fc_of(c)
    fc = re.sub(r";\[\w+\]\[\d+:v\]overlay=0:\d+:format=auto:eof_action=pass\[vcap\]",
                "", fc)
    last_ov = re.findall(r"\[(ov\d+)\]", fc)
    if last_ov:
        fc = fc.replace("[vcap]", f"[{last_ov[-1]}]")
    c = set_fc(c, fc)
    return ["-map" if x == "-map" else x for x in
            [("[" + last_ov[-1] + "]" if x == "[vcap]" else x) for x in c]]


def _drop_audio(cmd):
    c = list(cmd)
    fc = ";".join(p for p in fc_of(c).split(";") if not p.startswith("[0:a]"))
    c = set_fc(c, fc)
    while "[aout]" in c:
        i = c.index("[aout]")
        del c[i - 1:i + 1]
    for k in ("-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"):
        if k in c:
            c.remove(k)
    return c[:-1] + ["-an", c[-1]]


VARIANTS = [
    ("כמו שהוא", lambda c: c),
    ("בלי קלט כתוביות", _drop_caption),
    ("בלי אודיו", _drop_audio),
    ("בלי כתוביות ובלי אודיו", lambda c: _drop_audio(_drop_caption(c))),
    ("base setpts=PTS-STARTPTS", v_base_reset_pts),
    ("overlay repeatlast=0", v_repeatlast0),
    ("overlay shortest=0", v_broll_shortest),
    ("בלי enable=", v_no_enable),
    ("fps אחרי setpts בבירול", v_broll_fps_after_setpts),
    ("-fps_mode cfr", v_fps_mode_cfr),
    ("filter_threads=1", v_filter_threads1),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=25.0)
    ap.add_argument("--t-in", type=float, default=27.21)
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    cmd, seg = D.build_cmd(a.t_in)
    if not cmd:
        return 2
    print(f"סגמנט {seg.t_in:.2f}-{seg.t_out:.2f} · {len(seg.broll)} בירולים · "
          f"timeout={a.timeout}ש\n")

    for name, fn in VARIANTS:
        c = fn(list(cmd))
        c[-1] = str(OUT / f"{abs(hash(name))}.mkv")
        t = time.time()
        try:
            r = subprocess.run(c, capture_output=True, text=True,
                               timeout=a.timeout, stdin=subprocess.DEVNULL)
            rc, err = r.returncode, (r.stderr or "")[-160:].replace("\n", " ")
        except subprocess.TimeoutExpired:
            rc, err = 124, "TIMEOUT"
        el = time.time() - t
        mark = "✅" if rc == 0 else ("⛔ תקוע" if rc == 124 else "❌")
        print(f"  {mark} {name:<28} {el:6.1f}ש rc={rc} {err if rc else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
