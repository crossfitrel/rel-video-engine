# -*- coding: utf-8 -*-
"""patch align_words.py — מנוע MLX אופציונלי עם נסיגה ל-ct2 (v9.30-eff)."""
import sys, shutil
from pathlib import Path
p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8")
assert "REL_ASR_BACKEND" not in t, "already patched"
shutil.copy2(p, str(p) + ".bak-v930eff-20260922")
t = t.replace("import sys, json, re\nfrom pathlib import Path\nfrom faster_whisper import WhisperModel\n",
"import sys, json, re, os, subprocess\nfrom pathlib import Path\n", 1)
old_start = "glossary = load_glossary()\n"
i = t.index(old_start)
j = t.index("words = []\nn_fixed = 0\n")
k = t.index("for seg in segments:\n    for w in (seg.words or []):\n        t = w.word.strip()\n        if not t:\n            continue\n")
new_mid = '''glossary = load_glossary()

# v9.30-eff (22.9.26) — מנוע MLX על ה-GPU של המק. אותו מודל ivrit-ai turbo, אותו VAD,
# פי ~3.4 מהר (RTF 0.13 מול 0.46) ו-WER לא גרוע מ-ct2 על 6 סרטוני ASR-BENCH
# (tools/bench/asr_mlx_variants.json · ASR-BENCH.md §MLX). רץ ב-venv נפרד (~/.rel-mlx)
# דרך tools/asr_mlx.py; **כל כשל ⇒ נסיגה שקטה-אך-מדווחת ל-CTranslate2** — הצנרת לא נשברת.
# בחירה: REL_ASR_BACKEND=mlx|ct2 (ברירת מחדל: mlx כשהמודל הוא ברירת המחדל וה-venv קיים).
MLX_PY = Path.home() / ".rel-mlx" / "bin" / "python"
backend = os.environ.get("REL_ASR_BACKEND", "mlx")
used_backend = "ct2"
stream = None      # [(word, start, end, prob)]
duration = 0.0
if backend == "mlx" and resolved_model == MODEL_ALIASES["auto"] and MLX_PY.exists():
    raw_path = out + ".mlx_raw.json"
    try:
        r = subprocess.run([str(MLX_PY), str(HERE / "asr_mlx.py"), audio, raw_path],
                           capture_output=True, text=True, timeout=1800)
        if r.returncode == 0:
            raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
            stream = [(w["word"], w["start"], w["end"], w.get("prob", 0.0)) for w in raw]
            duration = raw[-1]["end"] if raw else 0.0
            used_backend = "mlx"
        else:
            print(f"WARN mlx נכשל (rc={r.returncode}) — נסיגה ל-ct2: {(r.stderr or '')[-200:]}", file=sys.stderr)
    except Exception as e:
        print(f"WARN mlx נכשל ({e}) — נסיגה ל-ct2", file=sys.stderr)
    finally:
        try:
            Path(raw_path).unlink()
        except OSError:
            pass

if stream is None:
    from faster_whisper import WhisperModel
'''
# keep ct2 block (model creation + transcribe) but indent under `if stream is None:`
ct2_block = t[i + len(old_start):j]
ct2_lines = ct2_block.strip("\n").split("\n")
ct2_ind = "\n".join(("    " + ln) if ln.strip() else ln for ln in ct2_lines)
ct2_tail = '''
    stream = [(w.word, w.start, w.end, w.probability) for seg in segments for w in (seg.words or [])]
    duration = info.duration

'''
loop_new = "for w_word, w_start, w_end, w_prob in stream:\n        t = w_word.strip()\n        if not t:\n            continue\n"
body = t[j:k] + loop_new + t[k + len("for seg in segments:\n    for w in (seg.words or []):\n        t = w.word.strip()\n        if not t:\n            continue\n"):]
# dedent the loop body one level (was nested in two loops)
lines = body.split("\n")
out_lines = []
in_loop = False
for ln in lines:
    if ln.startswith("for w_word, w_start"):
        in_loop = True
        out_lines.append(ln)
        continue
    if in_loop and ln.startswith("json.dump(words"):
        in_loop = False
    if in_loop and ln.startswith("        "):
        ln = ln[4:]
    out_lines.append(ln)
body = "\n".join(out_lines)
body = body.replace("ws, we = float(w.start), float(w.end)", "ws, we = float(w_start), float(w_end)")
body = body.replace('"prob": round(float(w.probability), 3)', '"prob": round(float(w_prob), 3)')
body = body.replace('(model={resolved_model}, vad=on, lang={lang}, "\n      f"dur={info.duration:.1f}s, glossary_fixes={n_fixed})"',
                    '(model={resolved_model}, backend={used_backend}, vad=on, lang={lang}, "\n      f"dur={duration:.1f}s, glossary_fixes={n_fixed})"')
t = t[:i] + new_mid + ct2_ind + ct2_tail + body
p.write_text(t, encoding="utf-8")
print("patched")
