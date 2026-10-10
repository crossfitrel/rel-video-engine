#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Batch word-timestamp alignment for all R.E.L videos (run on Mac venv). Model loaded once.
import json
from faster_whisper import WhisperModel
WS = "/Users/hayon/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי/Social Video Editing System"
jobs = [
 ("_work/קרסול/קרסול - סופי (אנימציות + כתוביות).mp4", "_work/_align/karsol.json"),
 ("_work/טיפ אחד - עוריות/טיפ עוריות - סופי (כתוביות).mp4", "_work/_align/oriot.json"),
 ("_work/טיפ אחד - בוקס ג׳אמפ אובר/טיפ בוקס ג׳אמפ אובר - סופי (כתוביות).mp4", "_work/_align/box.json"),
 ("_work/ילדים מתאמנים גם בקיץ/ילדים בקיץ - סופי (אנימציה + כתוביות).mp4", "_work/_align/yeladim.json"),
 ("_work/קליקים/קליקים - סופי (זכוכית + כתוביות).mp4", "_work/_align/klikim.json"),
]
m = WhisperModel("small", device="cpu", compute_type="int8")
for a, o in jobs:
    try:
        segs, info = m.transcribe(f"{WS}/{a}", language="he", word_timestamps=True,
                                  vad_filter=False, beam_size=5, condition_on_previous_text=False)
        words = [{"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3),
                  "prob": round(w.probability, 3)} for s in segs for w in (s.words or []) if w.word.strip()]
        json.dump(words, open(f"{WS}/{o}", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"OK {o} {len(words)} words dur={info.duration:.1f}", flush=True)
    except Exception as e:
        print(f"ERR {o}: {e}", flush=True)
print("BATCH DONE", flush=True)
