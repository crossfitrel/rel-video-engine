#!/usr/bin/env python3
"""בונה keep_segments מגבולות אנרגיה נמדדים (silencedetect) ולא מתזמוני whisper.

L53 — תזמוני whisper מרופדים בשני הקצוות ואינם מפת דיבור.
נמדד ב-27.8.26 על "גאה-בצוות": whisper טען ש-"בו." נגמר ב-44.41 בעוד הדיבור
נגמר אקוסטית ב-43.51 (‏0.90ש ריפוד) — כלומר חיתוך לפי whisper השאיר כמעט
שנייה של הדובר יושב בשקט ומוריד מבט. באותו סרטון whisper טען ש-"לסיכום"
מתחיל ב-71.07 בעוד האונסט האמיתי 70.69 (‏0.38ש) — חיתוך לפי whisper בלע את
תחילת המילה. שתי התלונות של הראל היו אותו שורש.

הכלל: **גבול חיתוך נגזר מאנרגיה. whisper קובע מה נאמר, לא מתי.**
"""
from __future__ import annotations
import argparse, json, re, subprocess, shutil
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

HEAD_PAD = 0.22          # הובלה לפני האונסט האקוסטי
TAIL_PAD = 0.18          # זנב אחרי סוף האנרגיה
MERGE_GAP = 0.95         # פאוזה קצרה מזה נשארת בתוך הבלוק (ההידוק יטפל)
MIN_SPAN = 0.60          # ספאן קצר מזה = רעש, לא דיבור
MIN_SEP = 0.10           # מרווח מינימלי בין קטעים סמוכים


def probe_duration(video: str) -> float:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", video], capture_output=True, text=True)
    return float(r.stdout.strip())


def detect_silences(video: str, noise_db: float = -40.0, min_dur: float = 0.30):
    r = subprocess.run([FFMPEG, "-nostdin", "-i", video, "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_dur}",
                        "-f", "null", "-"], capture_output=True, text=True)
    out, cur = [], None
    for line in r.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            cur = float(m.group(1))
            continue
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m:
            out.append((cur if cur is not None else 0.0, float(m.group(1))))
            cur = None
    if cur is not None:
        out.append((cur, None))
    return out


def speech_spans(silences, total: float):
    spans, prev = [], 0.0
    for a, b in silences:
        if a > prev + 0.01:
            spans.append([prev, a])
        prev = b if b is not None else total
    if prev < total - 0.01:
        spans.append([prev, total])
    return spans


def build_segments(video: str, head=HEAD_PAD, tail=TAIL_PAD, merge=MERGE_GAP):
    total = probe_duration(video)
    spans = speech_spans(detect_silences(video), total)
    merged = []
    for s, e in spans:
        if merged and s - merged[-1][1] < merge:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    merged = [m for m in merged if m[1] - m[0] >= MIN_SPAN]
    segs = []
    for s, e in merged:
        st, en = max(0.0, s - head), min(total, e + tail)
        if segs and st < segs[-1]["end"] + MIN_SEP:
            st = segs[-1]["end"] + MIN_SEP
        segs.append({"start": round(st, 2), "end": round(en, 2)})
    return segs, merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--video", default="INPUT.mp4")
    ap.add_argument("--head", type=float, default=HEAD_PAD)
    ap.add_argument("--tail", type=float, default=TAIL_PAD)
    ap.add_argument("--merge", type=float, default=MERGE_GAP)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    W = Path(a.workdir).resolve()
    segs, merged = build_segments(str(W / a.video), a.head, a.tail, a.merge)
    kept = round(sum(s["end"] - s["start"] for s in segs), 2)
    print(json.dumps({"speech_spans": merged, "keep_segments": segs,
                      "kept": kept, "segments": len(segs)}, ensure_ascii=False))
    if a.apply:
        p = W / "edl.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        d["keep_segments"] = segs
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print("APPLIED")


if __name__ == "__main__":
    main()
