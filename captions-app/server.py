#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — אפליקציית כתוביות R.E.L (מחליפה את Captions.ai)
============================================================
מעלים סרטון → בוחרים מותג במפורש → מתמללים → מתקנים טקסט → צורבים כתוביות
בפרופיל אטומי (פונט+צבע) → מורידים.

נשען על אותו מנוע של מערכת העריכה (../tools):
  - faster-whisper (venv ~/.rel-whisper) — תזמון מילים אמיתי
  - align_reconcile.py — מיזוג הטקסט המתוקן עם התזמון האמיתי
  - captions_build.py — חוקי הקיבוץ/ניקוי/צבעים/פונט של המותג (reuse)
"""
import os, sys, json, subprocess, threading, uuid, re, shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file, Response

APP_DIR  = Path(__file__).resolve().parent
SYS_DIR  = APP_DIR.parent                      # Social Video Editing System
TOOLS    = SYS_DIR / "tools"
FONTSDIR = SYS_DIR / "brand-assets"   # Assistant-ExtraBold.ttf
FONT_TTF = FONTSDIR / "Assistant-ExtraBold.ttf"
JOBS     = Path.home() / "Library" / "Caches" / "REL-Captions"  # מחוץ ל-iCloud (לא מסונכרן)
JOBS.mkdir(parents=True, exist_ok=True)

VENV_PY    = sys.executable                     # אותו python שמריץ אותנו
MODEL_NAME = "small"                            # טוב לעברית, מהיר (נטען פעם אחת)
LANG       = "he"
PORT       = 5111
APP_VERSION = "2.0.0"

BRAND_ALIASES = {"rel": "club", "oshia": "personal"}
BRANDS = {
    "club": {
        "label": "המועדון — CrossFit R.E.L",
    },
    "personal": {
        "label": "אושיה — הראל חיון",
    },
}

def canonical_brand(value):
    value = BRAND_ALIASES.get(str(value or "").strip().lower(), str(value or "").strip().lower())
    return value if value in BRANDS else None

sys.path.insert(0, str(TOOLS))
from captions_build import (group_cues, load_words, BRAND_OUTLINE_ASS,
                            WHITE_ASS, FONT_NAME, fmt_ts)

# ---------- מודל Whisper חם (נטען פעם אחת, מסדר בקשות) ----------
_model = None
_lock = threading.Lock()

def get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
    return _model

def warmup():
    try:
        with _lock:
            get_model()
        print("✅ מודל Whisper מוכן")
    except Exception as e:
        print("⚠️ אזהרת חימום מודל:", e)

def ffprobe_wh(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", path],
        capture_output=True, text=True).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"])

def build_ass(cues, w, h):
    """סגנון מותג זהה ל-captions_build, אבל PlayRes לפי הרזולוציה האמיתית
    (כך גם סרטון לא-אנכי לא מתעוות). הגדלים נגזרים יחסית לגובה 1920."""
    scale = h / 1920.0
    fontsize = max(28, round(120 * scale))
    marginv  = max(40, round(430 * scale))
    outline  = max(3, round(7 * scale))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,{FONT_NAME},{fontsize},{WHITE_ASS},{WHITE_ASS},{BRAND_OUTLINE_ASS},&H80000000,-1,0,0,0,100,100,0,0,1,{outline},0,2,40,40,{marginv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    out = [header]
    for c in cues:
        out.append(f"Dialogue: 0,{fmt_ts(c['start'])},{fmt_ts(c['end'])},Pop,,0,0,0,,{c['text']}\n")
    return "".join(out)

# ---------- Flask ----------
import captions_overlay   # צריבה ללא libass (PIL overlay)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024  # 4GB

ACCESS_PASSWORD = "rel2026"   # סיסמת גישה — כל שם משתמש + הסיסמה הזו

@app.before_request
def _require_password():
    if request.path == "/health":
        return  # ניטור ללא סיסמה
    auth = request.authorization
    if not auth or auth.password != ACCESS_PASSWORD:
        return Response("נדרשת סיסמה", 401,
                        {"WWW-Authenticate": 'Basic realm="R.E.L Captions"'})

@app.get("/")
def index():
    return send_file(str(APP_DIR / "index.html"))

@app.get("/health")
def health():
    return jsonify(ok=True, version=APP_VERSION, brands=list(BRANDS))

@app.post("/transcribe")
def transcribe():
    f = request.files.get("video")
    if not f or not f.filename:
        return jsonify(error="לא התקבל קובץ וידאו"), 400
    brand = canonical_brand(request.form.get("brand"))
    if not brand:
        return jsonify(error="חובה לבחור מותג: אושיה או מועדון"), 400
    job = uuid.uuid4().hex[:12]
    d = JOBS / job
    d.mkdir(parents=True, exist_ok=True)
    base = re.sub(r"[^\w.\-]+", "_", os.path.splitext(f.filename)[0]) or "video"
    ext  = (os.path.splitext(f.filename)[1] or ".mp4").lower()
    src  = d / f"input{ext}"
    f.save(str(src))
    try:
        with _lock:
            model = get_model()
            segments, info = model.transcribe(
                str(src), language=LANG, word_timestamps=True, vad_filter=False,
                beam_size=5, condition_on_previous_text=False)
            words, lines = [], []
            for seg in segments:
                st = (seg.text or "").strip()
                if st:
                    lines.append(st)
                for wd in (seg.words or []):
                    t = (wd.word or "").strip()
                    if not t:
                        continue
                    words.append({"word": t, "start": round(float(wd.start), 3),
                                  "end": round(float(wd.end), 3),
                                  "prob": round(float(wd.probability), 3)})
    except Exception as e:
        return jsonify(error=f"שגיאת תמלול: {e}"), 500
    json.dump(words, open(d / "whisper_words.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    (d / "meta.json").write_text(json.dumps(
        {"src": str(src), "dur": round(float(info.duration), 2), "base": base,
         "brand": brand}),
        encoding="utf-8")
    return jsonify(job=job, text="\n".join(lines),
                   duration=round(float(info.duration), 2), words=len(words),
                   brand=brand, brand_label=BRANDS[brand]["label"])

@app.post("/burn")
def burn():
    data = request.get_json(force=True) or {}
    job = data.get("job", "")
    edited = data.get("text", "")
    d = JOBS / job
    if not job or not d.exists():
        return jsonify(error="job לא נמצא"), 404
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    src, dur, base = meta["src"], meta.get("dur", 99999), meta.get("base", "video")
    brand = canonical_brand(meta.get("brand"))
    if not brand:
        return jsonify(error="המותג חסר ב-job — התחילו מחדש ובחרו מותג"), 400
    (d / "edited.txt").write_text(edited, encoding="utf-8")
    wh = d / "whisper_words.json"
    words_json = d / "words.json"
    # מיזוג הטקסט המתוקן עם התזמון האמיתי (reuse align_reconcile.py)
    rec = subprocess.run([VENV_PY, str(TOOLS / "align_reconcile.py"), str(wh),
        str(d / "edited.txt"), str(words_json), "--end", str(dur)],
        capture_output=True, text=True)
    if rec.returncode != 0 or not words_json.exists():
        words_json = wh   # נפילה לאחור: תזמון+טקסט גולמי של whisper
    # צריבה ב-PIL overlay (ה-ffmpeg המקומי בלי libass)
    ok, err, n = captions_overlay.burn(words_json, src, "captioned.mp4", d, brand=brand)
    if not ok:
        return jsonify(error=err), 500
    return jsonify(job=job, cues=n, brand=brand,
                   result=f"/result/{job}", download=f"/download/{job}")

@app.get("/resume/<job>")
def resume(job):
    """שחזור job קיים אחרי רענון דף (או job שהוזן חיצונית) — קורא meta+words מהדיסק."""
    d = JOBS / job
    if not job or not d.exists():
        return jsonify(error="job לא נמצא"), 404
    meta_p = d / "meta.json"
    wh = d / "whisper_words.json"
    if not meta_p.exists() or not wh.exists():
        return jsonify(error="קבצי job חסרים"), 404
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    words = json.loads(wh.read_text(encoding="utf-8"))
    text = " ".join((w.get("word") or "").strip() for w in words if (w.get("word") or "").strip())
    brand = canonical_brand(meta.get("brand"))
    if not brand:
        return jsonify(error="המותג חסר ב-job הישן"), 409
    return jsonify(job=job, text=text, duration=meta.get("dur", 0), words=len(words),
                   brand=brand, brand_label=BRANDS[brand]["label"])

@app.get("/result/<job>")
def result(job):
    p = JOBS / job / "captioned.mp4"
    if not p.exists():
        return "not found", 404
    return send_file(str(p), mimetype="video/mp4", conditional=True)

@app.get("/download/<job>")
def download(job):
    p = JOBS / job / "captioned.mp4"
    if not p.exists():
        return "not found", 404
    base = "video"
    mp = JOBS / job / "meta.json"
    if mp.exists():
        base = json.loads(mp.read_text(encoding="utf-8")).get("base", "video")
    return send_file(str(p), as_attachment=True,
                     download_name=f"{base}_כתוביות.mp4")

def purge_old(days=2):
    """ניקוי job-ים ישנים (וידאו זמני) כדי לא למלא דיסק."""
    import time
    cutoff = time.time() - days * 86400
    for p in JOBS.glob("*"):
        try:
            if p.is_dir() and p.stat().st_mtime < cutoff:
                shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass

if __name__ == "__main__":
    purge_old()
    threading.Thread(target=warmup, daemon=True).start()
    print(f"\n🎬 אפליקציית הכתוביות של R.E.L רצה — http://127.0.0.1:{PORT}\n")
    app.run(host="127.0.0.1", port=PORT, threaded=True)
