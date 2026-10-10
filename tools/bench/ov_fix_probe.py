#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""מה **מרפא** את התקיעה — על הפקודה האמיתית, לא על שחזור דומה.

מה שכבר נמדד (‏31.7.26, `ov_seg7_probe`):
  • seg7 (31.23-34.24, בסיס 3.01ש) + בירול **קצר מ-1.4ש** ⇒ תקיעה.
    ‏0.40/0.60/0.80/0.88/1.00/1.20 נתקעים · 1.40/1.50 עוברים.
  • **אותו בירול בדיוק** על seg5/seg6/seg8 ⇒ עובר. כלומר אינטראקציה
    בין הבסיס לאורך השכבה, לא "קליפ פגום" ולא "בירול קצר".
  • ‏ffmpeg 8.1 — מתזמן חוטים חדש. `filter_threads` כבר נשלל, אבל
    ‏**`filter_complex_threads` מעולם לא נבדק**, והוא זה ששולט על
    filter_complex בפועל.

הכלי לוכד את פקודת ה-ffmpeg האמיתית מ-`render_segment` ומריץ וריאציות
שלה. כל וריאציה משנה **דבר אחד**.

  python3 tools/bench/ov_fix_probe.py [--seg 7] [--timeout 20]
"""
from __future__ import annotations

import argparse
import copy
import shutil
import subprocess
import sys
import time
from pathlib import Path

SYS = Path.home() / ("Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/"
                     "01 - שיווק/תוכן שיווקי/Social Video Editing System")
sys.path.insert(0, str(SYS / "tools"))
from relvid import render as R                                    # noqa: E402

OUT = Path("/tmp/ov_fix_probe")


def capture_cmd(tl, seg):
    """הפקודה האמיתית, דרך monkey-patch על sh — לא שחזור."""
    got = {}
    real = R.sh

    def fake(cmd, timeout=None, **kw):
        c = [str(x) for x in cmd]
        if "-filter_complex" in c and "filter_complex" not in got:
            got["filter_complex"] = c
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
    cmd = got.get("filter_complex")
    if not cmd:
        return None
    # `render_segment` מנקה את תיקיית העבודה בסוף, ואיתה caps.txt שהפקודה
    # מצביעה עליו. מייצרים אותו מחדש **באותו נתיב** דרך הפונקציה האמיתית —
    # לא משכתבים את הפקודה, כי הפקודה היא כל העניין.
    sdir = OUT / f"_w_{seg.key if hasattr(seg, 'key') else ''}"
    for i, x in enumerate(cmd):
        if x.endswith("caps.txt"):
            sdir = Path(x).parent
            break
    sdir.mkdir(parents=True, exist_ok=True)
    R._caption_pngs(tl, seg, sdir)
    return cmd


def run(cmd, label, timeout) -> tuple[bool, float]:
    t = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        rc, err = r.returncode, (r.stderr or "")[-160:].replace("\n", " ")
    except subprocess.TimeoutExpired:
        rc, err = 124, "TIMEOUT"
    el = time.time() - t
    ok = rc == 0
    print(f"{'✅' if ok else '⏳' if rc == 124 else '❌'} {label:<44} "
          f"{el:6.1f}ש {'' if ok else err}", flush=True)
    return ok, el


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=str(Path.home() / "rel-video-work/V3-לולאה"))
    ap.add_argument("--seg", type=int, default=7)
    ap.add_argument("--timeout", type=float, default=20.0)
    a = ap.parse_args()

    tl = R.build_timeline(Path(a.workdir))
    seg = copy.deepcopy(tl.segments[a.seg])
    seg.broll = [seg.broll[0]]           # הבירול שנתקע, לבד
    base = capture_cmd(tl, seg)
    if not base:
        print("לא נלכדה פקודת filter_complex")
        return 1
    out_i = len(base) - 1
    base[out_i] = str(OUT / "variant.mkv")

    def with_args(extra, at=1):
        c = list(base)
        c[at:at] = extra
        return c

    print(f"פקודה נלכדה · {len(base)} ארגומנטים\n")
    run(list(base), "כמו שהוא (בקרה — אמור להיתקע)", a.timeout)
    run(with_args(["-filter_complex_threads", "1"]),
        "-filter_complex_threads 1", a.timeout)
    run(with_args(["-filter_complex_threads", "2"]),
        "-filter_complex_threads 2", a.timeout)
    run(with_args(["-threads", "1"]), "-threads 1", a.timeout)
    run(with_args(["-fflags", "+genpts"]), "-fflags +genpts", a.timeout)

    fc = base.index("-filter_complex") + 1

    def graph_sub(old, new, label):
        c = list(base)
        c[fc] = c[fc].replace(old, new)
        if c[fc] == base[fc]:
            print(f"⏭  {label} — אין מה להחליף")
            return
        run(c, label, a.timeout)

    graph_sub("tpad=stop_mode=clone:stop_duration=0.5", "null", "בלי tpad")
    graph_sub(":eof_action=pass", ":eof_action=repeat", "eof_action=repeat")
    graph_sub("eof_action=pass:enable=", "eof_action=pass:shortest=0:enable=",
              "shortest=0 מפורש")

    # הסרת ‎-frames:v (הוא ה-terminator; אולי הוא זה שמחכה)
    if "-frames:v" in base:
        i = base.index("-frames:v")
        c = base[:i] + base[i + 2:]
        run(c, "בלי -frames:v", a.timeout)

    # הסרת שכבת הכתוביות לגמרי (קלט concat + ה-overlay שלה)
    caps_i = next((i for i, x in enumerate(base) if str(x).endswith("caps.txt")), None)
    if caps_i is not None:
        c = list(base)
        c[fc] = "".join(part for part in [c[fc]])  # placeholder — נבנה למטה
        g = base[fc]
        # מסירים את החוליה [X][N:v]overlay...[vcap] ומחברים את הקודם ל-vout
        import re as _re
        m = _re.search(r";\[([a-z0-9]+)\]\[\d+:v\]overlay=[^;]*\[vcap\]", g)
        if m:
            g2 = g[:m.start()] + g[m.end():]
            g2 = g2.replace("[vcap]", f"[{m.group(1)}]")
            c[fc] = g2
            del c[caps_i - 4:caps_i + 1]   # -f concat -safe 0 -i caps.txt
            run(c, "בלי שכבת כתוביות", a.timeout)

    # דיבוג: מה הפילטר אומר לפני שהוא קופא
    print("\n— לוג debug של הבקרה (30 שורות אחרונות) —")
    c = with_args(["-loglevel", "debug"])
    for i, x in enumerate(c):
        if x == "-loglevel" and c[i + 1] == "error":
            c[i + 1] = "debug"
    try:
        r = subprocess.run(c, capture_output=True, text=True, timeout=a.timeout)
        tail = (r.stderr or "").splitlines()[-30:]
    except subprocess.TimeoutExpired as e:
        tail = (e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes)
                else (e.stderr or "")).splitlines()[-30:]
    for ln in tail:
        print("   " + ln[:150])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
