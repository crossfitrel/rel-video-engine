#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""הצעד האחרון: להתכנס משני הכיוונים בבת-אחת.

מה שידוע: הרפרודוקציה המינימלית נרפאת ב-`-noaccurate_seek`; הפקודה
האמיתית לא — גם אחרי הסרת כתוביות **או** אודיו **או** `-frames:v`, כל אחד
בנפרד. גם ffmpeg 7 נתקע ⇒ **זו אינה רגרסיה של 8.x.**

כאן מסירים את **כל** ההבדלים יחד. אם זה עובר — מחזירים אחד-אחד עד שזה
נשבר, וזו החוליה. אם זה נתקע — ההבדל אינו באף אחד מהם.

  python3 tools/bench/ov_final_probe.py [--seg 7] [--timeout 15]
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

OUT = Path("/tmp/ov_final")


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
    return got.get("fc")


def strip_all(cmd, seg, *, drop_caps=True, drop_audio=True,
              drop_frames=True, light_encode=True):
    """מפשיט את הפקודה האמיתית עד למבנה הרפרודוקציה — בלי לכתוב אותה מחדש."""
    c = list(cmd)
    fc = c.index("-filter_complex") + 1
    g = c[fc]
    if drop_caps:
        m = re.search(r";\[([a-z0-9]+)\]\[\d+:v\]overlay=[^;]*\[vcap\]", g)
        if m:
            g = g[:m.start()] + g[m.end():]
            g = g.replace("[vcap]", f"[{m.group(1)}]")
        i = next((k for k, x in enumerate(c) if str(x).endswith("caps.txt")), None)
        if i is not None:
            # ‏6 ארגומנטים: ‎-f concat ‎-safe 0 ‎-i caps.txt. מחיקת 5 השאירה
            # ‎"-f" יתום, ואז ffmpeg בלע את ‎"-filter_complex" כערך שלו והגרף
            # הפך לקובץ פלט — "Error opening output files". באג בכלי המדידה,
            # לא בפקודה. (אותו באג היה גם ב-ov_fix_probe.)
            del c[i - 5:i + 1]
            fc = c.index("-filter_complex") + 1
    if drop_audio:
        g = re.sub(r";?\[0:a\][^;]*\[aout\]", "", g)
        while "[aout]" in c:
            k = c.index("[aout]")
            c = c[:k - 1] + c[k + 1:]
        if "-c:a" in c:
            k = c.index("-c:a"); c = c[:k] + c[k + 2:]
        for opt in ("-ar", "-ac"):
            if opt in c:
                k = c.index(opt); c = c[:k] + c[k + 2:]
        c.insert(len(c) - 1, "-an")
        fc = c.index("-filter_complex") + 1
    c[fc] = g
    if drop_frames and "-frames:v" in c:
        k = c.index("-frames:v"); c = c[:k] + c[k + 2:]
    if light_encode:
        for opt, val in (("-crf", "23"), ("-preset", "veryfast")):
            if opt in c:
                c[c.index(opt) + 1] = val
    return c


def nframes(p) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-count_frames", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    try:
        return int((r.stdout or "0").strip().rstrip(",") or 0)
    except ValueError:
        return 0


def run(cmd, label, timeout, n=0, expect=0):
    """‏rc=0 אינו הצלחה. **מוודאים שיצאו פריימים.**

    נתפס 31.7.26: וריאציית `-noaccurate_seek` לבדה החזירה rc=0 ב-0.2ש —
    ונרשמה כ"תיקון". הקובץ היה 674 בייט עם **אפס פריימים**. מדידה שלא
    בודקת את התוצר שלה היא בדיוק "מוגדר ≠ עובד".
    """
    c = list(cmd)
    out = OUT / f"f{n}.mkv"
    c[-1] = str(out)
    t = time.time()
    try:
        r = subprocess.run(c, capture_output=True, text=True, timeout=timeout)
        rc, err = r.returncode, (r.stderr or "")[-160:].replace("\n", " ")
    except subprocess.TimeoutExpired:
        rc, err = 124, "TIMEOUT"
    el = time.time() - t
    fr = nframes(out) if rc == 0 else 0
    ok = rc == 0 and fr >= max(1, int(expect * 0.9))
    mark = "✅" if ok else ("🫥" if rc == 0 else ("⏳" if rc == 124 else "❌"))
    extra = f"{fr} פריימים" if rc == 0 else err
    if rc == 0 and not ok:
        extra += "  ← rc=0 אבל התוצר ריק/חסר"
    print(f"{mark} {label:<46} {el:6.1f}ש {extra}", flush=True)
    return ok


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

    exp = seg.n_frames or 90
    bare = strip_all(base, seg)
    run(bare, "מופשט לגמרי", a.timeout, 0, exp)
    safe = R._safe_seek_cmd(bare, seg)
    if safe:
        run(safe, "מופשט + safe-seek", a.timeout, 1, exp)

    # ── הצעד המכריע: אותה פקודה בדיוק, **גרף בסגנון הרפרודוקציה** ──
    # מה שנשאר בגרף האמיתי ולא היה ברפרודוקציה שעבדה: `format=yuva420p`,
    # שני `fade` על האלפא, `enable=between`, `tpad`. כל אחד נבדק לחוד
    # ונשלל — כאן כולם יחד.
    fc = bare.index("-filter_complex") + 1
    b = seg.broll[0]
    NORM = ("scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,setsar=1")
    g_min = (f"[0:v]{NORM}[base];"
             f"[1:v]{NORM},format=yuva420p,setpts=PTS-STARTPTS+{b.start:.3f}/TB[br];"
             f"[base][br]overlay=0:0:eof_action=pass[o];"
             f"[o]fps=30[vout]")
    c = list(bare); c[fc] = g_min
    run(c, "מופשט + גרף מינימלי", a.timeout, 2, exp)
    s = R._safe_seek_cmd(c, seg)
    if s:
        run(s, "מופשט + גרף מינימלי + safe-seek", a.timeout, 3, exp)

    # ── ומה שנשאר: **אופציות הפלט**. הרפרודוקציה שעבדה לא נשאה אותן. ──
    def drop(cmd, *opts):
        c2 = list(cmd)
        for o in opts:
            while o in c2:
                k = c2.index(o)
                c2 = c2[:k] + c2[k + 2:]
        return c2

    if s:
        run(drop(s, "-r"), "…בלי -r 30 (המרת קצב בצד הפלט)", a.timeout, 4, exp)
        run(drop(s, "-colorspace", "-color_primaries", "-color_trc",
                 "-color_range"), "…בלי דגלי צבע", a.timeout, 5, exp)
        run(drop(s, "-profile:v", "-level", "-pix_fmt"),
            "…בלי profile/level/pix_fmt", a.timeout, 6, exp)
        run(drop(s, "-r", "-colorspace", "-color_primaries", "-color_trc",
                 "-color_range", "-profile:v", "-level", "-pix_fmt"),
            "…בלי כל אופציות הפלט", a.timeout, 7, exp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
