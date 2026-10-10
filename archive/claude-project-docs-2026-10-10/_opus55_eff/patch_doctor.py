# -*- coding: utf-8 -*-
"""v9.30-eff: שני בדיקות doctor (asr backend · skill pack sync) + רשומות ב-gate_registry."""
import shutil, sys
from pathlib import Path
root = Path(sys.argv[1])
doc, reg = root / "tools/system_doctor.py", root / "tools/gate_registry.py"
d, g = doc.read_text(encoding="utf-8"), reg.read_text(encoding="utf-8")
assert "asr backend" not in d and "asr backend" not in g, "already patched"
shutil.copy2(doc, str(doc) + ".bak-v930eff-20260922")
shutil.copy2(reg, str(reg) + ".bak-v930eff-20260922")
anchor = '    if sys.platform == "darwin":\n        try:\n            add("review-app python", *_review_app_probe())'
assert anchor in d
new = '''    # v9.30-eff — מנוע התמלול: MLX (Metal) עם נסיגה ל-ct2. נסיגה שקטה = איטי פי ~3
    # בלי שאף אחד יודע (עקרון 11) — לכן זה נבדק כאן ולא רק ב-stderr של align_words.
    _mlx_py = Path.home() / ".rel-mlx" / "bin" / "python"
    _mlx_model = (Path.home() / ".cache" / "huggingface" / "hub" /
                  "models--mlx-community--ivrit-ai-whisper-large-v3-turbo-mlx")
    if os.environ.get("REL_ASR_BACKEND", "mlx") != "mlx":
        add("asr backend", "PASS", f"ct2 (REL_ASR_BACKEND={os.environ.get('REL_ASR_BACKEND')})")
    elif not _mlx_py.exists():
        add("asr backend", "WARN", "~/.rel-mlx חסר — התמלול נופל ל-ct2 (פי ~3 איטי). "
            "התקנה: python3.12 -m venv ~/.rel-mlx && ~/.rel-mlx/bin/pip install mlx-whisper faster-whisper==1.2.1")
    else:
        _r = run([str(_mlx_py), "-c", "import mlx_whisper, faster_whisper.vad"], timeout=60)
        _ok = getattr(_r, "returncode", 1) == 0 if not isinstance(_r, tuple) else _r[0] == 0
        if not _ok:
            add("asr backend", "WARN", "~/.rel-mlx קיים אבל mlx_whisper לא נטען — נסיגה ל-ct2")
        elif not _mlx_model.exists():
            add("asr backend", "WARN", "מודל MLX לא במטמון — הריצה הראשונה תוריד ~1.6GB")
        else:
            add("asr backend", "PASS", "mlx (ivrit-ai turbo על Metal) · נסיגה ל-ct2 בכשל")

    # v9.30-eff — הסקיל המותקן נגזר מהמאסטר (tools/skill_pack.py). dist ישן = הצ'אט הבא
    # טוען הוראות מיושנות (נמדד 22.9.26: המותקן היה v9.22 כשהמאסטר v9.29).
    try:
        import skill_pack as _SP
        import io, contextlib
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _st = _SP.check()
        add("skill pack sync", "PASS" if _st == 0 else "WARN", _buf.getvalue().strip()[:200])
    except Exception as e:
        add("skill pack sync", "WARN", f"לא נבדק: {e}")

'''
d = d.replace(anchor, new + anchor, 1)
ganchor = ' "vision gates calibrated": ('
assert ganchor in g
gnew = ''' "asr backend": (
     "v9.30-eff: התמלול רץ ב-MLX על ה-GPU (פי ~3 מ-ct2, WER לא גרוע — tools/bench/asr_mlx_final.json). "
     "venv שנשבר מחזיר בשקט ל-ct2 האיטי",
     "אפס — בדיקת סביבה", "‏WARN עם פקודת התקנה; הצנרת ממשיכה ב-ct2"),
 "skill pack sync": (
     "v9.30-eff: החבילה המותקנת בקלאוד נגזרת מהמאסטר; dist ישן = הוראות מיושנות בכל צ'אט "
     "(22.9.26: המותקן היה v9.22 מול מאסטר v9.29)",
     "אפס — השוואת hash", "‏WARN + skill_pack.py build והתקנה מחדש"),
'''
g = g.replace(ganchor, gnew + ganchor, 1)
doc.write_text(d, encoding="utf-8")
reg.write_text(g, encoding="utf-8")
print("patched doctor+registry")
