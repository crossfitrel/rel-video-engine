#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ASR bench: medium vs large-v3 vs ivrit turbo — speed + WER vs ground truth."""
import json, re, sys, time, unicodedata
from pathlib import Path
from faster_whisper import WhisperModel

AUDIO = sys.argv[1]
TRUTH = sys.argv[2] if len(sys.argv) > 2 else None
OUT = Path("/tmp/relbench/asr_bench_results.json")

NIQQUD = re.compile(r"[֑-ׇ]")
def norm(t):
    t = NIQQUD.sub("", unicodedata.normalize("NFC", t))
    t = re.sub(r"[^֐-׿A-Za-z0-9 ]", " ", t)
    return [w for w in t.split() if w]

def wer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    d = [[0]*(len(h)+1) for _ in range(len(r)+1)]
    for i in range(len(r)+1): d[i][0] = i
    for j in range(len(h)+1): d[0][j] = j
    for i in range(1, len(r)+1):
        for j in range(1, len(h)+1):
            d[i][j] = min(d[i-1][j]+1, d[i][j-1]+1, d[i-1][j-1] + (r[i-1] != h[j-1]))
    return d[len(r)][len(h)] / max(1, len(r)), len(r), len(h)

MODELS = [
    ("medium",      dict(cpu_threads=0), {}),
    ("medium-t6",   dict(cpu_threads=6), {}),
    ("large-v3",    dict(cpu_threads=6), {}),
    ("ivrit-ai/whisper-large-v3-turbo-ct2", dict(cpu_threads=6), {}),
]
truth = Path(TRUTH).read_text(encoding="utf-8") if TRUTH and Path(TRUTH).exists() else None
res = []
for name, mkw, tkw in MODELS:
    try:
        t0 = time.time()
        m = WhisperModel(name, device="cpu", compute_type="int8", **mkw)
        load = time.time() - t0
        t0 = time.time()
        segs, info = m.transcribe(AUDIO, language="he", word_timestamps=True,
                                  vad_filter=False, beam_size=5,
                                  condition_on_previous_text=False, **tkw)
        words = [w for s in segs for w in (s.words or [])]
        el = time.time() - t0
        text = " ".join(w.word.strip() for w in words)
        row = {"model": name, "threads": mkw.get("cpu_threads"), "load_s": round(load, 1),
               "transcribe_s": round(el, 1), "audio_s": round(info.duration, 1),
               "rtf": round(el / max(info.duration, .01), 3), "n_words": len(words),
               "text": text}
        if truth:
            w_, nr, nh = wer(truth, text)
            row.update(wer=round(w_, 4), ref_words=nr, hyp_words=nh)
        print(json.dumps({k: v for k, v in row.items() if k != "text"}, ensure_ascii=False), flush=True)
        res.append(row)
        del m
    except Exception as e:
        print(f"FAIL {name}: {e}", flush=True)
        res.append({"model": name, "error": str(e)})
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("WROTE", OUT, flush=True)
