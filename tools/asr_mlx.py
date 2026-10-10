#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
asr_mlx.py — תמלול ivrit-ai turbo על ה-GPU של המק (MLX/Metal) — v9.30-eff, 22.9.26
===============================================================================
רץ ב-venv נפרד (`~/.rel-mlx`: mlx-whisper + faster-whisper לשכבת ה-VAD בלבד), כדי
לא לגעת בסביבת הצנרת (`~/.rel-whisper`). `align_words.py` קורא לו כתהליך-בן
כשהמנוע הוא mlx, ונופל חזרה ל-CTranslate2 בכל כשל — הצנרת לא נשברת לעולם.

למה חלונות וקטעים ≤20ש (נמדד, tools/bench/asr_mlx_*.json):
בלי חלוקה, MLX דילג על משפט ה-CTA כולו ב"מי-אמר-שמאוחר-מידיי" (13 מילים, WER
12.7%→25.3%) — קטע VAD יחיד של 31.2ש חצה את חלון ה-30ש של Whisper. לכן כל קטע
ארוך מ-20ש מפוצל בנקודה השקטה ביותר, וקטעים מקובצים לחלונות ≤28ש.

VAD: אותו Silero של faster-whisper, min_silence 500ms (ASR-BENCH מלכודת 1 —
turbo בלי VAD מדלג על משפטים). language="he" חובה (מלכודת 2).

  ~/.rel-mlx/bin/python tools/asr_mlx.py AUDIO_OR_VIDEO OUT_RAW.json
פלט: [{"word","start","end","prob"}...] גולמי (בלי מילון תיקון — align_words מחיל).
"""
import json
import os, sys
import time

import numpy as np

MODEL = "mlx-community/ivrit-ai-whisper-large-v3-turbo-mlx"
SR = 16000
WINDOW_S = 28.0


MAX_CHUNK_S = 20.0


def split_long(chunks, audio):
    """קטע VAD ארוך מ-20ש מפוצל בנקודה השקטה ביותר (±2ש סביב נקודת החלוקה).
    נמדד 22.9.26: קטע יחיד של 31.2ש ב"מי-אמר-שמאוחר-מידיי" חצה את חלון ה-30ש של
    Whisper, ו-MLX דילג על משפט ה-CTA כולו (13 מילים); אותו משפט לבד תומלל נכון."""
    out = []
    frame = int(0.05 * SR)
    for c in chunks:
        s, e = c["start"], c["end"]
        while (e - s) / SR > MAX_CHUNK_S:
            n = int(np.ceil((e - s) / SR / MAX_CHUNK_S))
            target = s + (e - s) // n
            lo, hi = max(s + SR, target - 2 * SR), min(e - SR, target + 2 * SR)
            best, best_rms = target, None
            for p in range(lo, hi - frame, frame):
                rms = float(np.sqrt(np.mean(audio[p:p + frame] ** 2)))
                if best_rms is None or rms < best_rms:
                    best, best_rms = p + frame // 2, rms
            out.append({"start": s, "end": best})
            s = best
        out.append({"start": s, "end": e})
    return out


def windows(chunks):
    groups, cur, dur = [], [], 0.0
    for c in chunks:
        L = (c["end"] - c["start"]) / SR
        if cur and dur + L > WINDOW_S:
            groups.append(cur)
            cur, dur = [], 0.0
        cur.append(c)
        dur += L
    if cur:
        groups.append(cur)
    return groups


def transcribe(path):
    import mlx_whisper
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    audio = decode_audio(str(path), sampling_rate=SR)
    chunks = split_long(get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=500)), audio)
    words = []
    for g in windows(chunks):
        speech = np.concatenate([audio[c["start"]:c["end"]] for c in g]).astype(np.float32)
        offs, acc = [], 0.0
        for c in g:
            L = (c["end"] - c["start"]) / SR
            offs.append((acc, c["start"] / SR, L))
            acc += L

        def orig(t, is_end=False):
            for a0, s0, L in offs:
                if t < a0 + L or (is_end and t <= a0 + L):
                    return s0 + max(0.0, t - a0)
            a0, s0, L = offs[-1]
            return s0 + min(L, t - a0)

        res = mlx_whisper.transcribe(speech, path_or_hf_repo=MODEL, language="he", word_timestamps=True,
                                     condition_on_previous_text=False, verbose=None)
        for seg in res.get("segments", []):
            for w in seg.get("words", []):
                t = w["word"].strip()
                if t:
                    words.append({"word": t, "start": round(orig(w["start"]), 3),
                                  "end": round(orig(w["end"], True), 3),
                                  "prob": round(float(w.get("probability", 0.0)), 3)})
    return words, len(audio) / SR


def main():
    src, out = sys.argv[1], sys.argv[2]
    t0 = time.time()
    words, dur = transcribe(src)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(words, fh, ensure_ascii=False, indent=1)
    print(f"OK mlx {len(words)} words dur={dur:.1f}s in {time.time() - t0:.1f}s", flush=True)
    # onnxruntime>=1.28 (Silero VAD) קורס ב-SIGABRT בכיבוי — מרוץ ב-telemetry teardown של ORT.
    # הפלט כבר נכתב; יציאה קשיחה מדלגת על ה-destructors של C++ ומחזירה rc=0 נקי.
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
