#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
מדידת התפר בפועל — v9.11.

לא בודק זמנים בתוכנית אלא **פיקסלים בפלט**. הטענה שנבדקת: בירול שחוצה גבול
חיתוך אינו חושף את הדובר באף פריים בגבול. שתי השכבות שיכולות לשבור זאת:
  1. הקצה נעצר לפני הגבול            → `broll_director.snap_to_cuts`
  2. `fade` על אלפא בתפר הפנימי      → `render.mark_seam_fades` / `broll_fragment`
  3. `eof_action=pass` בסוף קליפ     → פריים בסיס אחד בכל תפר (v8.4)

רץ על מדיה סינתטית (דובר = ירוק בוהק, בירול = כחול), דרך **קוד הרינדור עצמו**
ולא דרך שחזור "דומה" של הפקודה. מדפיס JSON ויוצא 1 על חשיפה.

    python3 tools/bench/ov_seam_probe.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from relvid import render as R  # noqa: E402

W, H, FPS = 1080, 1920, 30
SPEAKER = "0x00C000"      # "פנים" — ירוק. חשיפה = פריים ירוק בגבול.
BROLL = "0x0000C0"


def sh(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def synth(path, color, secs):
    sh(["ffmpeg", "-y", "-f", "lavfi", "-i",
        f"color=c={color}:s={W}x{H}:r={FPS}:d={secs}",
        "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={secs}",
        "-shortest", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(path)])


def frame_is_speaker(video, t):
    """דגימת פריים בודד: האם הוא ירוק (דובר) או כחול (בירול)."""
    d = Path(tempfile.mkdtemp())
    try:
        png = d / "f.png"
        sh(["ffmpeg", "-y", "-ss", f"{t:.4f}", "-i", str(video),
            "-frames:v", "1", "-vf", "scale=8:8", str(png)])
        if not png.exists():
            return None
        r = sh(["ffprobe", "-v", "error", "-f", "lavfi", "-i",
                f"movie={png},signalstats", "-show_entries",
                "frame_tags=lavfi.signalstats.UAVG,lavfi.signalstats.VAVG",
                "-of", "json"])
        tags = json.loads(r.stdout)["frames"][0]["tags"]
        u = float(tags["lavfi.signalstats.UAVG"])
        return u < 128.0          # ירוק: U נמוך. כחול: U גבוה.
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    d = Path(tempfile.mkdtemp(prefix="seam-probe-"))
    try:
        inp, br = d / "INPUT.mp4", d / "broll.mp4"
        synth(inp, SPEAKER, 12)
        synth(br, BROLL, 8)

        # שני סגמנטים = גבול חיתוך אחד בציר הפלט, ב-t=4.0
        segs = [R.Segment(src=str(inp), t_in=0.0, t_out=4.0, out_start=0.0, idx=0),
                R.Segment(src=str(inp), t_in=7.0, t_out=11.0, out_start=4.0, idx=1)]
        for s in segs:
            s.n_frames = int(round(s.dur * FPS))

        # בירול שחוצה את הגבול — בדיוק המצב שהראל תיאר
        clips = [R.BrollClip(path=str(br), start=2.0, end=6.0, src_offset=0.5)]
        R.mark_seam_fades(clips)
        R._clip_to_segments(
            clips, segs, lambda c: (c.start, c.end),
            lambda seg, c, ls, le, off: seg.broll.append(
                R.broll_fragment(c, ls, le, off)))

        tl = R.Timeline(workdir=d, input_path=inp, segments=segs,
                        band={"y0": 1500, "h": 200}, brand="rel", crf=19)
        cache = d / "cache"
        cache.mkdir()
        # מפתח המטמון נקבע ב-build_timeline; כאן עוקפים אותו ולכן מציבים ידנית.
        # בלי זה שני הסגמנטים חולקים מפתח ריק, והשני מקבל את הקובץ של הראשון —
        # כשל של הבדיקה שנראה בדיוק כמו כשל של המוצר.
        for s in segs:
            s.key = R._segment_key(tl, s)
        t0 = time.time()
        res = [R.render_segment(tl, s, cache) for s in segs]
        secs = round(time.time() - t0, 1)
        if any(r.get("path") is None for r in res):
            print(json.dumps({"ok": False, "stage": "render", "secs": secs,
                              "stalled": [r.get("stalled") for r in res],
                              "err": [(r.get("stderr") or "")[-300:] for r in res]},
                             ensure_ascii=False))
            return 1

        master = d / "OUT.mp4"
        lst = d / "c.txt"
        lst.write_text("".join(f"file '{r['path']}'\n" for r in res), encoding="utf-8")
        sh(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
            "-c", "copy", str(master)])

        # דגימה צפופה סביב הגבול: ±4 פריימים. כל אחד מהם חייב להיות בירול.
        probes = [round(4.0 + k / FPS, 4) for k in range(-4, 5)]
        exposed = [t for t in probes if frame_is_speaker(master, t) is True]
        ok = not exposed
        print(json.dumps({
            "ok": ok, "secs": secs, "boundary": 4.0,
            "fragments": [[len(s.broll), [(b.fade_in, b.fade_out) for b in s.broll]]
                          for s in segs],
            "probed": probes, "speaker_exposed_at": exposed,
            "why": "כל פריים בגבול מכוסה בבירול" if ok else
                   "פריים דובר נחשף בגבול — התפר שבור"}, ensure_ascii=False))
        return 0 if ok else 1
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
