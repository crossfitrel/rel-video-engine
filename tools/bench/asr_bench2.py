#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ivrit turbo config sweep — find a config that does NOT skip content."""
import json, re, sys, time, unicodedata
from pathlib import Path
from faster_whisper import WhisperModel

AUDIO, TRUTH = sys.argv[1], sys.argv[2]
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
    return round(d[len(r)][len(h)]/max(1, len(r)), 4)

truth = Path(TRUTH).read_text(encoding="utf-8")
MODEL = "ivrit-ai/whisper-large-v3-turbo-ct2"
CFGS = [
    ("base",            dict(vad_filter=False, condition_on_previous_text=False, beam_size=5)),
    ("vad",             dict(vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
                             condition_on_previous_text=False, beam_size=5)),
    ("cond",            dict(vad_filter=False, condition_on_previous_text=True, beam_size=5)),
    ("nsth09",          dict(vad_filter=False, condition_on_previous_text=False, beam_size=5,
                             no_speech_threshold=0.9, compression_ratio_threshold=100.0,
                             log_prob_threshold=None)),
    ("vad+nsth09",      dict(vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
                             condition_on_previous_text=False, beam_size=5,
                             no_speech_threshold=0.9, compression_ratio_threshold=100.0,
                             log_prob_threshold=None)),
]
m = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=6)
out = []
for name, kw in CFGS:
    t0 = time.time()
    segs, info = m.transcribe(AUDIO, language="he", word_timestamps=True, **kw)
    words = [w for s in segs for w in (s.words or [])]
    el = time.time() - t0
    text = " ".join(w.word.strip() for w in words)
    row = {"cfg": name, "s": round(el, 1), "rtf": round(el/info.duration, 3),
           "n": len(words), "wer": wer(truth, text), "text": text}
    print(json.dumps({k: v for k, v in row.items() if k != "text"}, ensure_ascii=False), flush=True)
    out.append(row)
Path("/tmp/relbench/asr_bench2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE", flush=True)
