#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gallery_calibrate.py — בונה את מעטפת הייחוס מהבירולים שהראל כבר אישר.

"כל סף נגזר ממדידה של סרטונים שהראל אישר, לא מניחוש."

קורא את catalog.json, דוגם 3 פריימים מכל בירול (25%/50%/75%), מודד,
לוקח חציון לכל קליפ, ומחשב אחוזונים על פני כל הספרייה.

    python3 gallery_calibrate.py --build   [--limit N]

פלט: gallery_reference.json  — {metric: {p01,p05,p25,p50,p75,p95,n}}
"""
import argparse, json, subprocess, sys, tempfile, os
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gallery_metrics import frame_metrics

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
CATALOG = PROJ / "בירולים" / "catalog.json"
OUT = HERE / "gallery_reference.json"
METRICS = ["sharp", "bright", "contrast", "colorful", "clip_hi", "clip_lo", "entropy"]


def grab_frame(video, t, dest):
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
           "-frames:v", "1", "-vf", "scale=-2:512", "-y", str(dest)]
    r = subprocess.run(cmd, capture_output=True, timeout=90)
    return r.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) > 0


def clip_metrics(video, dur, tmpdir):
    vals = []
    for frac in (0.25, 0.5, 0.75):
        t = max(0.0, (dur or 3.0) * frac)
        f = Path(tmpdir) / "f.jpg"
        if f.exists():
            f.unlink()
        if not grab_frame(video, t, f):
            continue
        try:
            with Image.open(f) as im:
                im.load()
                vals.append(frame_metrics(im))
        except Exception:
            continue
    if not vals:
        return None
    return {m: float(np.median([v[m] for v in vals])) for m in METRICS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if not a.build:
        ap.error("use --build")

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    items = cat["items"]
    if a.limit:
        items = items[:a.limit]

    rows, skipped = [], 0
    with tempfile.TemporaryDirectory() as td:
        for i, it in enumerate(items, 1):
            p = Path(it["path"])
            if not p.exists():
                skipped += 1
                continue
            m = clip_metrics(p, it.get("dur", 3.0), td)
            if m is None:
                skipped += 1
                continue
            m["_id"] = it["id"]
            m["_file"] = it["file"]
            rows.append(m)
            if i % 25 == 0:
                print(f"  ...{i}/{len(items)} (ok={len(rows)} skip={skipped})", flush=True)

    if not rows:
        print("FAIL: אפס בירולים נמדדו — אין ממה לגזור סף", file=sys.stderr)
        sys.exit(2)

    env = {}
    for m in METRICS:
        v = np.array([r[m] for r in rows], dtype=float)
        env[m] = {
            "p01": round(float(np.percentile(v, 1)), 4),
            "p05": round(float(np.percentile(v, 5)), 4),
            "p25": round(float(np.percentile(v, 25)), 4),
            "p50": round(float(np.percentile(v, 50)), 4),
            "p75": round(float(np.percentile(v, 75)), 4),
            "p95": round(float(np.percentile(v, 95)), 4),
        }
    out = {
        "built_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_catalog": str(CATALOG),
        "n_clips_measured": len(rows),
        "n_skipped": skipped,
        "work_height": 512,
        "envelope": env,
        "per_clip": rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"REFERENCE OK: {len(rows)} בירולים נמדדו (דילוג {skipped}) → {OUT}")
    for m in METRICS:
        e = env[m]
        print(f"  {m:9s} p05={e['p05']:>10.3f}  p50={e['p50']:>10.3f}  p95={e['p95']:>10.3f}")


if __name__ == "__main__":
    main()
