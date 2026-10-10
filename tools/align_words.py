#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
align_words.py — R.E.L Social Video Editing System
==================================================
מקור-אמת לתזמון מילים: forced word-timestamps עם faster-whisper.
מחליף את ההערכה הפרופורציונלית (transcript_to_words.py) בתזמון אמיתי
שנמדד מהאודיו — כל מילה מקבלת start/end אמיתי + probability.

רץ על המק (venv: /Users/hayon/.rel-whisper) כי הסנדבוקס מוגבל ב-45ש
(הורדת מודל + inference לא נכנסים). הפלט (words JSON) נכתב לדיסק האמיתי,
והסנדבוקס קורא אותו לבניית ה-ASS + צריבה.

שימוש:
  python align_words.py AUDIO_OR_VIDEO OUT.json [model] [lang]
    model: auto (ברירת מחדל, = ivrit-ai/whisper-large-v3-turbo-ct2 + VAD — v7.8,
           25.7.26) | tiny/base/small/medium/large-v3 | כל מזהה מודל של HuggingFace.
           ההחלפה נמדדה על 6 סרטונים אמיתיים מול תמליל מתוקן — ראה ASR-BENCH.md
           ואת ההערה מתחת ל-MODEL_ALIASES.
    lang:  he (ברירת מחדל)

מילון תיקון (24.7.26): אחרי forced-timestamps מופעל pass של asr-glossary.json —
תיקון אוטומטי לשיבושים חוזרים ומתועדים (א/ע, ה חסרה, ק/כ וכו') שגם medium לא
תמיד תופס. התאמה מדויקת על ליבת המילה בלבד (לא substring), פיסוק נשמר.
להוסיף שיבוש חדש שחוזר על עצמו → tools/asr-glossary.json, לא כאן בקוד.

פלט: [{"word","start","end","prob"}...] לפי סדר הדיבור.
"""
import sys, json, re, os, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
GLOSSARY_PATH = HERE / "asr-glossary.json"

audio = sys.argv[1]
out = sys.argv[2]
model_name = sys.argv[3] if len(sys.argv) > 3 else "auto"
lang = sys.argv[4] if len(sys.argv) > 4 else "he"

# v7.8 (25.7.26) — מודל ברירת המחדל הוחלף אחרי מדידה על 6 סרטונים אמיתיים עם תמליל
# מתוקן כ-ground-truth (ראה ASR-BENCH.md). על "ההבנה-האנטומית-סוגי-אחיזות":
#     medium (מה שהיה)                 51.3ש · WER 15.75%
#     large-v3                         85.7ש · WER 10.27%
#     ivrit-ai turbo + VAD (החדש)      26.7ש · WER  7.53%
# כלומר: **פי 2 מהר וחצי מהשגיאות**. זו התשובה הישירה לתלונה החוזרת ביותר של הראל
# ("מלא שגיאות כתיב בכתוביות") — המודל מכוונן לעברית (ivrit.ai), לא ג'נרי.
# ⚠️ VAD חובה: בלעדיו turbo *מדלג על משפטים שלמים* (נמדד: 124 מילים במקום 143,
# WER 18.5%) — פגם ידוע של turbo. vad_filter=True מבטל את הדילוג לגמרי.
# ⚠️ language="he" חובה — זיהוי-שפה אוטומטי נפגע באימון של ivrit.ai (מצוין בכרטיס המודל).
MODEL_ALIASES = {
    "auto": "ivrit-ai/whisper-large-v3-turbo-ct2",
    "rel":  "ivrit-ai/whisper-large-v3-turbo-ct2",
    "turbo-he": "ivrit-ai/whisper-large-v3-turbo-ct2",
}
resolved_model = MODEL_ALIASES.get(model_name, model_name)

NIQQUD = re.compile(r"[֑-ׇ]")
CORE = re.compile(r"([א-ת0-9A-Za-z']+)")

def load_glossary():
    try:
        data = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
        return data.get("corrections", {})
    except Exception:
        return {}

def apply_glossary(word, glossary):
    """מתקן רק אם ליבת-המילה (בלי ניקוד/פיסוק) תואמת בדיוק מפתח במילון —
    שומר על כל הפיסוק/רווחים מסביב כמו שהם."""
    if not glossary:
        return word
    m = CORE.search(NIQQUD.sub("", word))
    if not m:
        return word
    core = m.group(1)
    fix = glossary.get(core)
    if not fix or fix == core:
        return word
    return word[:m.start()] + fix + word[m.end():]

glossary = load_glossary()

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
    # cpu_threads=6: ה-M4 הוא 4 ליבות ביצוע + 6 חיסכון. ברירת המחדל (0=כל הליבות)
    # פורסת עבודה גם על ליבות-החיסכון האיטיות וכל צעד ממתין לאיטית ביותר.
    # local_files_only: המודל כבר במטמון — בלי זה כל ריצה פונה ל-HF Hub לבדוק עדכון
    # (נמדד: 2.7ש טעינה מול 1.7ש offline, ותלות מיותרת ברשת באמצע גימור).
    try:
        model = WhisperModel(resolved_model, device="cpu", compute_type="int8",
                             cpu_threads=6, local_files_only=True)
    except Exception:
        model = WhisperModel(resolved_model, device="cpu", compute_type="int8", cpu_threads=6)
    segments, info = model.transcribe(
        audio, language=lang, word_timestamps=True,
        vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
        beam_size=5, condition_on_previous_text=False,
    )
    stream = [(w.word, w.start, w.end, w.probability) for seg in segments for w in (seg.words or [])]
    duration = info.duration

words = []
n_fixed = 0
for w_word, w_start, w_end, w_prob in stream:
    t = w_word.strip()
    if not t:
        continue
    fixed = apply_glossary(t, glossary)
    if fixed != t:
        n_fixed += 1
    ws, we = float(w_start), float(w_end)
    # v7.9 — תיקון רב-מילה ("לגופנאים" → "לגוף תנאים"): מפצלים למילים נפרדות
    # ומחלקים את משך המילה המקורית לפי אורך התווים. בלי זה הכתובית הייתה
    # מציגה שתי מילים במסך אחד — הפרה של כלל "מילה אחת בכל כתובית".
    parts = fixed.split()
    if len(parts) > 1:
        tot = sum(len(x) for x in parts) or 1
        cur = ws
        for x in parts:
            seg = (we - ws) * (len(x) / tot)
            words.append({"word": x, "start": round(cur, 3),
                          "end": round(min(we, cur + seg), 3),
                          "prob": round(float(w_prob), 3)})
            cur += seg
        continue
    words.append({
        "word": fixed,
        "start": round(ws, 3),
        "end": round(we, 3),
        "prob": round(float(w_prob), 3),
    })
with open(out, "w", encoding="utf-8") as fh:
    json.dump(words, fh, ensure_ascii=False, indent=1)
print(f"OK {len(words)} words -> {out}  (model={resolved_model}, backend={used_backend}, vad=on, lang={lang}, "
      f"dur={duration:.1f}s, glossary_fixes={n_fixed})", flush=True)
# onnxruntime>=1.28 (Silero VAD) קורס ב-SIGABRT בכיבוי (ORT telemetry teardown) — יציאה קשיחה אחרי שהפלט נכתב.
sys.stdout.flush(); sys.stderr.flush()
os._exit(0)
