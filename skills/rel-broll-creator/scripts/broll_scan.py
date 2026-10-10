#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_scan.py — סורק סרטון ארוך ומאתר את הקטעים הרציפים הטובים לבירולים.
שלב 1 של מצב "סרטון ארוך → בירולים".

מה הוא עושה:
  1. scene detection (ffmpeg) → מוצא את גבולות השוטים (קומפילציה = הרבה חתכים).
  2. מסנן shots רציפים באורך ≥ --min-dur (קצרים מדי = לא בירול טוב).
  3. אפשר להחריג טווחי-זמן שכבר השתמשת בהם (--exclude) — לבאצ' שני "מחלקים אחרים".
  4. מפיק contact sheet (פריים אמצעי לכל מועמד, פרוס באריחים) + candidates.json.

** הבחירה היא ויזואלית **: אחרי הריצה, פתח/קרא את ה-contact sheet, ובחר את
המועמדים הטובים והמגוונים (אקשן, אינטנסיביות, קהל/קהילה) — דלג על לוגו, מעברים,
שוטים חשוכים, וכפילויות. ה-idx בכל אריח = ה-#N שמודפס למטה (סדר row-major).

שימוש:
  python3 broll_scan.py --video VIDEO --out OUTDIR [--min-dur 2.0] [--scene 0.35]
                        [--exclude 11.4,25.2,...] [--thumb-w 300] [--tile 6x6]

הסביבה: רץ יפה בסנדבוקס (יש ffmpeg, והסרטון שהועלה נמצא ב-uploads). כתוב את ה-OUTDIR
לתיקיית outputs כדי שתוכל לקרוא את ה-contact sheet (מיפוי נתיב host).
"""
import argparse
import glob
import json
import os
import subprocess


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", path],
        capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def scene_cuts(video, scene_thr):
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", video,
         "-filter:v", f"select='gt(scene,{scene_thr})',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True)
    cuts = []
    for line in r.stderr.splitlines():
        if "pts_time:" in line:
            try:
                cuts.append(float(line.split("pts_time:")[1].split()[0]))
            except (ValueError, IndexError):
                pass
    return cuts


def main():
    ap = argparse.ArgumentParser(description="סריקת סרטון ארוך לקטעי בירול מועמדים")
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True, help="תיקיית פלט ל-contact sheet + candidates.json")
    ap.add_argument("--min-dur", type=float, default=2.0, help="אורך שוט מינימלי (שניות)")
    ap.add_argument("--scene", type=float, default=0.35, help="סף scene detection (0-1)")
    ap.add_argument("--exclude", default="", help="טווחי-start להחרגה, comma-separated (כבר בשימוש)")
    ap.add_argument("--thumb-w", type=int, default=300)
    ap.add_argument("--tile", default="6x6")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    dur = ffprobe_duration(args.video)
    cuts = sorted(set([0.0] + scene_cuts(args.video, args.scene) + [dur]))
    shots = [(cuts[i], cuts[i + 1], cuts[i + 1] - cuts[i]) for i in range(len(cuts) - 1)]

    excl = [float(x) for x in args.exclude.split(",") if x.strip()]
    cand = [(s, e, d) for s, e, d in shots
            if d >= args.min_dur and all(abs(s - u) > 1.2 for u in excl)]

    tdir = os.path.join(args.out, "thumbs")
    os.makedirs(tdir, exist_ok=True)
    for f in glob.glob(tdir + "/*.jpg"):
        os.remove(f)
    for n, (s, e, d) in enumerate(cand):
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-ss", f"{s + d / 2}", "-i", args.video, "-frames:v", "1",
             "-vf", f"scale={args.thumb_w}:-1", f"{tdir}/c{n:03d}.jpg"])
    for f in glob.glob(f"{args.out}/contact_*.jpg"):
        os.remove(f)
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-framerate", "1",
         "-pattern_type", "glob", "-i", f"{tdir}/c*.jpg",
         "-vf", f"tile={args.tile}:padding=3:color=white", "-q:v", "3",
         f"{args.out}/contact_%02d.jpg"])

    json.dump([{"idx": n, "start": round(s, 2), "end": round(e, 2), "dur": round(d, 2)}
               for n, (s, e, d) in enumerate(cand)],
              open(f"{args.out}/candidates.json", "w"), ensure_ascii=False)

    sheets = sorted(os.path.basename(x) for x in glob.glob(f"{args.out}/contact_*.jpg"))
    print(json.dumps({"candidates": len(cand), "duration": round(dur, 1),
                      "sheets": sheets, "tile": args.tile}, ensure_ascii=False))
    for n, (s, e, d) in enumerate(cand):
        print(f"#{n}: {s:.0f}-{e:.0f}s ({d:.1f}s)")


if __name__ == "__main__":
    main()
