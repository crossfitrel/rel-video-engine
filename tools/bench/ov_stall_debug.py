#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""הצעד שלא נעשה: להסתכל על מה התהליך **חוסם**, לא לנחש.

מריץ את הפקודה האמיתית של `render_segment` עם `-loglevel debug`, ואם אין
פלט חדש N שניות — מצלם `sample` על התהליך התקוע. 0% CPU לאורך זמן היא
חסימה; sample מראה באיזה syscall.

  python3 tools/bench/ov_stall_debug.py [--quiet-secs 25]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

SYS = Path.home() / ("Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/"
                     "01 - שיווק/תוכן שיווקי/Social Video Editing System")
sys.path.insert(0, str(SYS / "tools"))
from relvid import render as R                                    # noqa: E402

W = Path.home() / "rel-video-work/V3-לולאה"
OUT = Path("/tmp/ov_stall_debug")


def build_cmd(t_in=None):
    """משחזר את הפקודה מ-render_segment דרך monkey-patch על sh — כדי
    שהפקודה שנבדקת תהיה **אותה פקודה**, ולא שחזור 'דומה' שכבר עבר בעבר."""
    captured = {}

    real = R.sh

    def fake_sh(cmd, timeout=None, **kw):
        # _caption_pngs קורא ל-sh לפני פקודת הרינדור. לוכדים רק את זו שיש
        # בה filter_complex, ומעבירים את השאר הלאה — אחרת נלכדת הפקודה
        # הלא-נכונה, וזו בדיוק הטעות של "בידוד על שחזור דומה".
        if "-filter_complex" in cmd:
            captured["cmd"] = list(cmd)
            raise SystemExit("captured")
        return real(cmd, timeout=timeout, **kw)

    tl = R.build_timeline(W, brand="rel", broll_plan_file=str(W / "broll_plan.json"))
    segs = [s for s in tl.segments if len(s.broll) >= 1]
    if not segs:
        print("אין סגמנט עם בירול בפרויקט הזה")
        raise SystemExit(2)
    seg = (min(segs, key=lambda s: abs(s.t_in - t_in)) if t_in is not None
           else max(segs, key=lambda s: len(s.broll)))
    print(f"סגמנט {seg.key}: {seg.t_in:.2f}-{seg.t_out:.2f} · "
          f"{len(seg.broll)} בירולים")
    # ה-`finally` של render_segment מוחק את sdir — ושם יושבים ה-PNG של
    # הכתוביות שהפקודה מצביעה אליהם. בלי לנטרל את המחיקה, הפקודה שנלכדה
    # נכשלת מיד (rc=254) ואי אפשר לראות את התקיעה בכלל.
    real_sh, R.sh = R.sh, fake_sh
    real_rm, R.shutil.rmtree = R.shutil.rmtree, lambda *a, **k: None
    try:
        R.render_segment(tl, seg, OUT, force=True)
    except SystemExit:
        pass
    finally:
        R.sh, R.shutil.rmtree = real_sh, real_rm
    return captured.get("cmd"), seg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet-secs", type=float, default=25.0)
    ap.add_argument("--max-secs", type=float, default=180.0)
    ap.add_argument("--t-in", type=float, default=None)
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    cmd, seg = build_cmd(a.t_in)
    if not cmd:
        print("לא נלכדה פקודה — ה-render_segment לא הגיע ל-sh")
        return 2

    # הרצה מחדש של אותה פקודה, רק עם debug במקום error
    dbg = list(cmd)
    dbg[dbg.index("-loglevel") + 1] = "debug"
    (OUT / "cmd.txt").write_text(" ".join(dbg), encoding="utf-8")

    log = open(OUT / "ffmpeg_debug.log", "w", encoding="utf-8", errors="replace")
    p = subprocess.Popen(dbg, stdout=subprocess.DEVNULL, stderr=log,
                         stdin=subprocess.DEVNULL)
    print(f"pid={p.pid} · log={OUT / 'ffmpeg_debug.log'}")

    last_size, last_change, t0 = -1, time.time(), time.time()
    sampled = False
    while p.poll() is None:
        time.sleep(2)
        sz = (OUT / "ffmpeg_debug.log").stat().st_size
        if sz != last_size:
            last_size, last_change = sz, time.time()
        quiet = time.time() - last_change
        if quiet >= a.quiet_secs and not sampled:
            sampled = True
            print(f"⛔ {quiet:.0f}ש בלי פלט — מצלם sample")
            subprocess.run(["sample", str(p.pid), "3", "-file",
                            str(OUT / "sample.txt")], capture_output=True)
            subprocess.run(f"ps -o %cpu,state,wchan -p {p.pid} > "
                           f"{OUT / 'ps.txt'}", shell=True)
            print(f"→ {OUT / 'sample.txt'}")
        if time.time() - t0 > a.max_secs:
            print("⛔ חריגת זמן — הורג")
            p.kill()
            break
    log.close()
    print(f"rc={p.returncode} · {time.time() - t0:.1f}ש · "
          f"log={(OUT / 'ffmpeg_debug.log').stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
