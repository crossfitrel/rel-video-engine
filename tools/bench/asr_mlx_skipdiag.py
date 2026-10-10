#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""אבחון הדילוג של MLX ב"מי-אמר-שמאוחר-מידיי": איפה נופלות המילים ואיזה גודל חלון מחזיר אותן."""
import difflib, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1]))
from asr_bench_mlx import WORK, wer, ct2_words  # noqa
import asr_mlx as AM  # tools/asr_mlx.py

P = sys.argv[1] if len(sys.argv) > 1 else "מי-אמר-שמאוחר-מידיי"
d = WORK / P
vid = d / "EXPORT_TIGHT.mp4"
truth = next((d / c for c in ("correct_transcript.txt", "edited.txt") if (d / c).exists()))
ref = truth.read_text(encoding="utf-8")
from faster_whisper import WhisperModel
ct2 = WhisperModel("ivrit-ai/whisper-large-v3-turbo-ct2", device="cpu", compute_type="int8", cpu_threads=6,
                   local_files_only=True)
cw, _ = ct2_words(ct2, vid, 5)
for win in (28.0, 15.0, 8.0, 0.0):
    AM.WINDOW_S = win if win else 0.001   # 0 ⇒ כל קטע VAD לבד
    t = time.time()
    mw, _ = AM.transcribe(vid)
    el = time.time() - t
    a = [x["w"] for x in cw]
    b = [x["word"] for x in mw]
    miss = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op in ("delete", "replace") and i2 - i1 >= 3:
            miss.append((round(cw[i1]["s"], 1), round(cw[i2 - 1]["e"], 1), " ".join(a[i1:i2])[:80]))
    print(json.dumps({"window": win, "s": round(el, 1), "n": len(mw), "ct2_n": len(cw),
                      "wer": wer(ref, " ".join(b)), "ct2_wer": wer(ref, " ".join(a)), "missing": miss},
                     ensure_ascii=False), flush=True)
