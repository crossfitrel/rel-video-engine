#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
asr_bench_mlx.py — האם MLX (Metal) מאיץ את התמלול בלי לפגוע בדיוק? (v9.30-eff, 22.9.26)
====================================================================================
ASR-BENCH.md (25.7.26) קבע "GPU/Metal — CTranslate2 הוא CPU-בלבד על מק. אין מה
לחפש" — נכון ל-CTranslate2, אבל אותו מודל ivrit-ai turbo קיים גם ב-MLX
(mlx-community/ivrit-ai-whisper-large-v3-turbo-mlx) שרץ על ה-GPU של ה-M4.
התמלול הוא ~50% מזמן הגימור (ASR-BENCH), ולכן זו ההאצה הגדולה ביותר הזמינה.

אותה מתודולוגיה בדיוק כמו asr_bench3: אותם 6 סרטונים, אותו ground-truth מתוקן
ידנית, אותה נרמול WER. בנוסף — **הסכמת תזמון מילים** מול ct2 (הכתוביות והחיתוך
האקוסטי נשענים על start/end, לא רק על הטקסט).

VAD: אותו Silero VAD של faster-whisper (min_silence 500ms) — מוחל לפני MLX ומופה
חזרה בדיוק כמו ש-faster-whisper עושה (SpeechTimestampsMap). בלי VAD turbo מדלג על
משפטים (ASR-BENCH מלכודת 1) — לכן אין תצורת MLX בלי VAD.

  ~/.rel-mlx/bin/python tools/bench/asr_bench_mlx.py [--out tools/bench/asr_bench_mlx.json]
"""
import difflib
import json
import re
import statistics
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np

WORK = Path.home() / "rel-video-work"
PROJECTS = ["ההבנה-האנטומית-סוגי-אחיזות", "אופן-גים-חיזוק", "מי-אמר-שמאוחר-מידיי",
            "סקאלת-הבריאות", "מאסל-מן-רוטטור-קאף", "שינה-והתאוששות"]
CT2 = "ivrit-ai/whisper-large-v3-turbo-ct2"
MLX = "mlx-community/ivrit-ai-whisper-large-v3-turbo-mlx"
NIQQUD = re.compile(r"[֑-ׇ]")


def norm(t):
    t = NIQQUD.sub("", unicodedata.normalize("NFC", t))
    return [w for w in re.sub(r"[^֐-׿A-Za-z0-9 ]", " ", t).split() if w]


def wer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    return round(d[len(r)][len(h)] / max(1, len(r)), 4)


def ct2_words(model, path, beam):
    segs, info = model.transcribe(str(path), language="he", word_timestamps=True, vad_filter=True,
                                  vad_parameters=dict(min_silence_duration_ms=500),
                                  beam_size=beam, condition_on_previous_text=False)
    return [{"w": w.word.strip(), "s": float(w.start), "e": float(w.end)}
            for s in segs for w in (s.words or []) if w.word.strip()], info.duration


def mlx_words(path):
    import mlx_whisper
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps, SpeechTimestampsMap
    sr = 16000
    audio = decode_audio(str(path), sampling_rate=sr)
    chunks = get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=500))
    if not chunks:
        return [], len(audio) / sr
    speech = np.concatenate([audio[c["start"]:c["end"]] for c in chunks]).astype(np.float32)
    res = mlx_whisper.transcribe(speech, path_or_hf_repo=MLX, language="he", word_timestamps=True,
                                 condition_on_previous_text=False, verbose=None)
    tsmap = SpeechTimestampsMap(chunks, sr)
    out = []
    for seg in res.get("segments", []):
        for w in seg.get("words", []):
            t = w["word"].strip()
            if not t:
                continue
            mid = (w["start"] + w["end"]) / 2
            ci = tsmap.get_chunk_index(mid)
            out.append({"w": t, "s": float(tsmap.get_original_time(w["start"], ci)),
                        "e": float(tsmap.get_original_time(w["end"], ci, is_end=True))})
    return out, len(audio) / sr


def timing_agreement(a, b):
    na = [NIQQUD.sub("", x["w"]) for x in a]
    nb = [NIQQUD.sub("", x["w"]) for x in b]
    sm = difflib.SequenceMatcher(a=na, b=nb, autojunk=False)
    ds, de = [], []
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            ds.append(abs(a[blk.a + k]["s"] - b[blk.b + k]["s"]))
            de.append(abs(a[blk.a + k]["e"] - b[blk.b + k]["e"]))
    if not ds:
        return {}
    ds.sort()
    return {"matched": len(ds), "of": len(a), "med_start": round(statistics.median(ds), 3),
            "p90_start": round(ds[int(0.9 * (len(ds) - 1))], 3), "med_end": round(statistics.median(de), 3)}


def main():
    out_path = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else \
        Path(__file__).with_name("asr_bench_mlx.json")
    from faster_whisper import WhisperModel
    rows = []
    # טעינה קרה — הצנרת מריצה align_words כתהליך חדש בכל פעם, ולכן הטעינה נספרת
    t0 = time.time()
    ct2 = WhisperModel(CT2, device="cpu", compute_type="int8", cpu_threads=6, local_files_only=True)
    load_ct2 = round(time.time() - t0, 2)
    import mlx_whisper  # noqa
    t0 = time.time()
    first = True
    for p in PROJECTS:
        d = WORK / p
        vid = d / "EXPORT_TIGHT.mp4"
        truth = next((d / c for c in ("correct_transcript.txt", "edited.txt") if (d / c).exists()), None)
        if not vid.exists() or not truth:
            continue
        ref = truth.read_text(encoding="utf-8")
        r = {"proj": p}
        for label, fn in (("ct2_b5", lambda: ct2_words(ct2, vid, 5)),
                          ("mlx", lambda: mlx_words(vid))):
            t = time.time()
            words, dur = fn()
            el = time.time() - t
            if label == "mlx" and first:
                r["mlx_first_call_incl_load"] = True
                first = False
            r[label] = {"s": round(el, 1), "rtf": round(el / dur, 3), "n": len(words),
                        "wer": wer(ref, " ".join(x["w"] for x in words))}
            r["audio"] = round(dur, 1)
            r["_" + label] = words
        r["timing"] = timing_agreement(r["_ct2_b5"], r["_mlx"])
        r["ref_n"] = len(norm(ref))
        print(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}, ensure_ascii=False), flush=True)
        rows.append(r)
    summ = {"load_ct2_s": load_ct2}
    for label in ("ct2_b5", "mlx"):
        sub = [r[label] for r in rows]
        summ[label] = {"wer_avg": round(sum(x["wer"] for x in sub) / len(sub), 4),
                       "rtf_avg": round(sum(x["rtf"] for x in sub) / len(sub), 3),
                       "s_total": round(sum(x["s"] for x in sub), 1)}
    rows_steady = rows[1:]  # בלי הקריאה הראשונה (טעינת MLX + קומפילציית Metal)
    if rows_steady:
        summ["mlx_steady_rtf"] = round(sum(r["mlx"]["rtf"] for r in rows_steady) / len(rows_steady), 3)
        summ["ct2_steady_rtf"] = round(sum(r["ct2_b5"]["rtf"] for r in rows_steady) / len(rows_steady), 3)
    summ["timing_med_start"] = round(statistics.median(r["timing"].get("med_start", 0) for r in rows), 3)
    print("SUMMARY " + json.dumps(summ, ensure_ascii=False), flush=True)
    out_path.write_text(json.dumps({"summary": summ, "rows": [{k: v for k, v in r.items()
                                                              if not k.startswith("_")} for r in rows]},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    Path("/tmp/eff/asr_words.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
