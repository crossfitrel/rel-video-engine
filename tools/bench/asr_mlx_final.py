#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asr_mlx_final.py — השוואה סופית: tools/asr_mlx.py (כפי שנכנס לצנרת) מול ct2 (ברירת המחדל הקיימת).
6 סרטוני ASR-BENCH + כל פרויקט נוסף עם תמליל מתוקן ידנית (עד 14). שער הקבלה (נקבע מראש):
  (1) WER ממוצע של MLX ≤ ct2 · (2) אין סרטון שבו MLX גרוע מ-ct2 ביותר מ-3 נק' WER ·
  (3) אין דילוג (מילים חסרות ≥3 ברצף מול ct2) · (4) חציון הפרש תזמון ≤0.03ש.
  ~/.rel-mlx/bin/python tools/bench/asr_mlx_final.py
"""
import difflib, json, statistics, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1]))
from asr_bench_mlx import WORK, PROJECTS, wer, ct2_words, timing_agreement  # noqa
import asr_mlx as AM  # noqa


def candidates(limit=14):
    out = list(PROJECTS)
    for d in sorted(WORK.iterdir(), key=lambda p: -p.stat().st_mtime):
        if len(out) >= limit:
            break
        if d.name in out or not (d / "EXPORT_TIGHT.mp4").exists():
            continue
        if (d / "correct_transcript.txt").exists():
            out.append(d.name)
    return out


def main():
    from faster_whisper import WhisperModel
    ct2 = WhisperModel("ivrit-ai/whisper-large-v3-turbo-ct2", device="cpu", compute_type="int8",
                       cpu_threads=6, local_files_only=True)
    AM.transcribe(WORK / PROJECTS[0] / "EXPORT_TIGHT.mp4")   # חימום
    rows = []
    for p in candidates():
        d = WORK / p
        vid = d / "EXPORT_TIGHT.mp4"
        truth = next((d / c for c in ("correct_transcript.txt", "edited.txt") if (d / c).exists()), None)
        if not truth:
            continue
        ref = truth.read_text(encoding="utf-8")
        t = time.time(); cw, dur = ct2_words(ct2, vid, 5); ct = time.time() - t
        t = time.time(); mw, _ = AM.transcribe(vid); mt = time.time() - t
        mw2 = [{"w": x["word"], "s": x["start"], "e": x["end"]} for x in mw]
        a, b = [x["w"] for x in cw], [x["w"] for x in mw2]
        gaps = [i2 - i1 for op, i1, i2, _j1, _j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()
                if op in ("delete", "replace") and (i2 - i1) - (_j2 - _j1) >= 3]
        r = {"proj": p, "audio": round(dur, 1), "ct2_wer": wer(ref, " ".join(a)), "mlx_wer": wer(ref, " ".join(b)),
             "ct2_s": round(ct, 1), "mlx_s": round(mt, 1), "ct2_n": len(a), "mlx_n": len(b),
             "skips": gaps, **{"t_" + k: v for k, v in timing_agreement(cw, mw2).items()}}
        print(json.dumps(r, ensure_ascii=False), flush=True)
        rows.append(r)
    n = len(rows)
    s = {"n": n,
         "ct2_wer": round(sum(r["ct2_wer"] for r in rows) / n, 4),
         "mlx_wer": round(sum(r["mlx_wer"] for r in rows) / n, 4),
         "ct2_rtf": round(sum(r["ct2_s"] for r in rows) / sum(r["audio"] for r in rows), 3),
         "mlx_rtf": round(sum(r["mlx_s"] for r in rows) / sum(r["audio"] for r in rows), 3),
         "worst_delta": round(max(r["mlx_wer"] - r["ct2_wer"] for r in rows), 4),
         "videos_with_skip": sum(1 for r in rows if r["skips"]),
         "timing_med": round(float(statistics.median(float(r.get("t_med_start", 0)) for r in rows)), 3)}
    s["accept"] = bool(s["mlx_wer"] <= s["ct2_wer"] and s["worst_delta"] <= 0.03 and
                   s["videos_with_skip"] == 0 and s["timing_med"] <= 0.03)
    print("SUMMARY " + json.dumps(s, ensure_ascii=False), flush=True)
    Path(__file__).with_name("asr_mlx_final.json").write_text(
        json.dumps({"summary": s, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
