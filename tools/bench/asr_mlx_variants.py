#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asr_mlx_variants.py — למה MLX דילג על 13 מילים ב"מי-אמר-שמאוחר-מידיי", ואיזו תצורה סוגרת את זה.

תצורות (כולן עם אותו Silero VAD):
  base     — כמו ב-asr_bench_mlx (אודיו-דיבור משורשר, ברירות המחדל של mlx_whisper)
  nosp     — no_speech_threshold=None (בלי דילוג "אין דיבור" על חלון שלם)
  windows  — חלונות ≤28ש לפי גבולות VAD, כל חלון מתומלל לבד (כמו batched pipeline של faster-whisper)
  win_nosp — windows + no_speech_threshold=None
  ~/.rel-mlx/bin/python tools/bench/asr_mlx_variants.py
"""
import json, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from asr_bench_mlx import WORK, PROJECTS, MLX, wer, norm, timing_agreement, ct2_words  # noqa

SR = 16000


def run_mlx(path, windows=False, nosp=False):
    import mlx_whisper
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    audio = decode_audio(str(path), sampling_rate=SR)
    chunks = get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=500))
    groups = [[c] for c in chunks] if not windows else []
    if windows:
        cur, dur = [], 0
        for c in chunks:
            L = (c["end"] - c["start"]) / SR
            if cur and dur + L > 28:
                groups.append(cur); cur, dur = [], 0
            cur.append(c); dur += L
        if cur:
            groups.append(cur)
    else:
        groups = [chunks]
    kw = dict(path_or_hf_repo=MLX, language="he", word_timestamps=True,
              condition_on_previous_text=False, verbose=None)
    if nosp:
        kw["no_speech_threshold"] = None
    out = []
    for g in groups:
        speech = np.concatenate([audio[c["start"]:c["end"]] for c in g]).astype(np.float32)
        # מיפוי זמן בתוך הקבוצה → זמן מקורי
        offs, acc = [], 0
        for c in g:
            offs.append((acc, c["start"] / SR, (c["end"] - c["start"]) / SR)); acc += (c["end"] - c["start"]) / SR

        def orig(t, is_end=False):
            for a0, s0, L in offs:
                if t < a0 + L or (is_end and t <= a0 + L):
                    return s0 + max(0.0, t - a0)
            a0, s0, L = offs[-1]
            return s0 + min(L, t - a0)
        res = mlx_whisper.transcribe(speech, **kw)
        for seg in res.get("segments", []):
            for w in seg.get("words", []):
                t = w["word"].strip()
                if t:
                    out.append({"w": t, "s": orig(w["start"]), "e": orig(w["end"], True)})
    return out, len(audio) / SR


def main():
    from faster_whisper import WhisperModel
    ct2 = WhisperModel("ivrit-ai/whisper-large-v3-turbo-ct2", device="cpu", compute_type="int8",
                       cpu_threads=6, local_files_only=True)
    run_mlx(WORK / PROJECTS[0] / "EXPORT_TIGHT.mp4")   # חימום (טעינה + Metal)
    rows = []
    for p in PROJECTS:
        d = WORK / p
        vid = d / "EXPORT_TIGHT.mp4"
        truth = next((d / c for c in ("correct_transcript.txt", "edited.txt") if (d / c).exists()), None)
        ref = truth.read_text(encoding="utf-8")
        ref_w, _ = ct2_words(ct2, vid, 5)
        r = {"proj": p, "ct2_wer": wer(ref, " ".join(x["w"] for x in ref_w)), "ct2_n": len(ref_w)}
        for name, kw in (("base", {}), ("nosp", {"nosp": True}), ("windows", {"windows": True}),
                         ("win_nosp", {"windows": True, "nosp": True})):
            t = time.time()
            ws, dur = run_mlx(vid, **kw)
            r[name] = {"s": round(time.time() - t, 1), "n": len(ws),
                       "wer": wer(ref, " ".join(x["w"] for x in ws)),
                       "t_med": timing_agreement(ref_w, ws).get("med_start"),
                       "t_p90": timing_agreement(ref_w, ws).get("p90_start")}
        print(json.dumps(r, ensure_ascii=False), flush=True)
        rows.append(r)
    for name in ("base", "nosp", "windows", "win_nosp"):
        print(f"AVG {name}: wer={sum(r[name]['wer'] for r in rows)/len(rows):.4f} "
              f"s={sum(r[name]['s'] for r in rows):.1f} · ct2 wer={sum(r['ct2_wer'] for r in rows)/len(rows):.4f}",
              flush=True)
    Path(__file__).with_name("asr_mlx_variants.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
