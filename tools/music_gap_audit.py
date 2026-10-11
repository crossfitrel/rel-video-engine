#!/usr/bin/env python3
"""L135 — ביקורת gap דיבור↔מוזיקה על ריליז שגומרו: dialog_I של קלט המיקס מול מפלס המוזיקה בדוח.
שימוש: $REL_PY tools/music_gap_audit.py [--root ~/rel-video-work] [--n 60]"""
import argparse, json, pathlib, re, subprocess

def dialog_i(p):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-vn", "-af", "loudnorm=print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    m = re.search(r'"input_i"\s*:\s*"([-\d.]+)"', r.stderr)
    return float(m.group(1)) if m else None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=str(pathlib.Path.home() / "rel-video-work"))
    ap.add_argument("--n", type=int, default=60); a = ap.parse_args()
    pol = json.loads((pathlib.Path(__file__).parent / "music-level-policy.json").read_text(encoding="utf-8"))
    rows = []
    for rep in sorted(pathlib.Path(a.root).glob("*/FINISH_REPORT.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:a.n]:
        d = rep.parent; t = rep.read_text(errors="ignore")
        g = list(d.glob("MIXED.mp4.musicgap.json"))
        if g:
            mg = json.loads(g[0].read_text(encoding="utf-8")).get("measured") or {}
            if mg: rows.append((mg["gap_lu"], d.name, "measured")); continue
        m = re.search(r"- מוזיקה: .*?@ (?:פתיח [-\d.]+ → דיבור )?([-\d.]+)", t)
        base = next((d / f for f in ("EXPORT+BROLL.mp4", "EXPORT_TIGHT.mp4", "EXPORT.mp4") if (d / f).exists()), None)
        if not m or not base: continue
        di = dialog_i(base)
        if di is not None: rows.append((round(di - float(m.group(1)), 1), d.name, "report"))
    for gap, name, src in sorted(rows):
        flag = "⛔" if gap < pol["min_speech_gap_lu"] - pol["gate_tolerance_lu"] else "  "
        print(f"{flag} {gap:5.1f} LU  {name}  ({src})")

if __name__ == "__main__":
    main()
