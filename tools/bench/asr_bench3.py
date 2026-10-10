#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validation across multiple real projects: medium(current) vs medium+vad vs ivrit-turbo+vad."""
import json, re, sys, time, unicodedata
from pathlib import Path
from faster_whisper import WhisperModel

W = Path("/Users/hayon/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי/Social Video Editing System/_work")
PROJECTS = ["אופן-גים-חיזוק", "מי-אמר-שמאוחר-מידיי", "סקאלת-הבריאות",
            "מאסל-מן-רוטטור-קאף", "שינה-והתאוששות"]
NIQQUD = re.compile(r"[֑-ׇ]")
def norm(t):
    t = NIQQUD.sub("", unicodedata.normalize("NFC", t))
    return [w for w in re.sub(r"[^֐-׿A-Za-z0-9 ]", " ", t).split() if w]
def wer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    d = [[0]*(len(h)+1) for _ in range(len(r)+1)]
    for i in range(len(r)+1): d[i][0] = i
    for j in range(len(h)+1): d[0][j] = j
    for i in range(1, len(r)+1):
        for j in range(1, len(h)+1):
            d[i][j] = min(d[i-1][j]+1, d[i][j-1]+1, d[i-1][j-1] + (r[i-1] != h[j-1]))
    return round(d[len(r)][len(h)]/max(1, len(r)), 4)

VAD = dict(vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
SETUPS = [
    ("medium|now",       "medium", dict(vad_filter=False)),
    ("medium|vad",       "medium", VAD),
    ("ivritTurbo|vad",   "ivrit-ai/whisper-large-v3-turbo-ct2", VAD),
]
rows = []
for label, mname, extra in SETUPS:
    m = WhisperModel(mname, device="cpu", compute_type="int8", cpu_threads=6)
    for pname in PROJECTS:
        d = W / pname
        vid = d / "EXPORT_TIGHT.mp4"
        truth_p = next((d / c for c in ("correct_transcript.txt", "edited.txt") if (d / c).exists()), None)
        if not vid.exists() or truth_p is None:
            continue
        t0 = time.time()
        segs, info = m.transcribe(str(vid), language="he", word_timestamps=True,
                                  beam_size=5, condition_on_previous_text=False, **extra)
        words = [w for s in segs for w in (s.words or [])]
        el = time.time() - t0
        text = " ".join(w.word.strip() for w in words)
        row = {"setup": label, "proj": pname, "audio": round(info.duration, 1), "s": round(el, 1),
               "rtf": round(el/info.duration, 2), "n": len(words),
               "ref_n": len(norm(truth_p.read_text(encoding="utf-8"))),
               "wer": wer(truth_p.read_text(encoding="utf-8"), text)}
        print(json.dumps(row, ensure_ascii=False), flush=True)
        rows.append(row)
    del m
Path("/tmp/relbench/asr_bench3.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
for label, _, _ in SETUPS:
    sub = [r for r in rows if r["setup"] == label]
    if sub:
        print(f"AVG {label}: wer={sum(r['wer'] for r in sub)/len(sub):.4f} "
              f"rtf={sum(r['rtf'] for r in sub)/len(sub):.2f} n={len(sub)}", flush=True)
print("DONE", flush=True)
