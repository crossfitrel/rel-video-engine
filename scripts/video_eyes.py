#!/usr/bin/env python3
"""
video_eyes.py — נותן ל-Claude "עיניים" לניתוח וידאו.

הרעיון: מודל שפה לא יכול "לצפות" בוידאו, אבל כן יכול לראות תמונות ולקרוא טקסט.
הכלי הזה מפרק וידאו ל-4 ערוצי מידע שהמודל באמת קולט:

  1. VISION   — בחירת פריימים מונחית-תנועה (צפוף איפה שקורה משהו) + חיתוכי סצנה
                + דילול כפילויות, מוגשים כגיליונות מגע עם חותמת זמן על כל אריח.
  2. SPEECH   — תמלול מדויק עם חותמות זמן (faster-whisper, תומך עברית).
  3. RHYTHM   — מפת תנועה ב-4 דגימות לשנייה, רשימת שוטים, אורך כל שוט, קצב חיתוכים.
  4. SOUND    — עוצמת שמע לאורך זמן, זיהוי שתיקות, אנרגיה.

הפלט: תיקיית bundle שהמודל קורא — report.md + contact_*.jpg + transcript.srt + data.json

שימוש:
  python3 video_eyes.py analyze VIDEO [--model medium|large-v3] [--lang he]
                                      [--max-frames 48] [--grid auto|4x3] [--no-audio]
  python3 video_eyes.py strip  VIDEO 00:01:23 --window 2 --count 12   # פריים-אחר-פריים
  python3 video_eyes.py frame  VIDEO 00:01:23.5                        # פריים בודד באיכות מלאה
  python3 video_eyes.py probe  VIDEO
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------- utilities

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def hhmmss(t):
    t = max(0.0, float(t))
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}" if h else f"{m:02d}:{s:06.3f}"


def srt_ts(t):
    t = max(0.0, float(t))
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    if ms == 1000:
        ms, s = 0, s + 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_ts(text):
    """מקבל 12.5 / 1:05 / 00:01:05.250 ומחזיר שניות."""
    text = str(text).strip()
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    parts = text.split(":")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return total


# ---------------------------------------------------------------- probe

def probe(path):
    r = sh(["ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        raise SystemExit(f"ffprobe failed: {r.stderr[:400]}")
    data = json.loads(r.stdout)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    fmt = data.get("format", {})

    fps = 0.0
    if v and v.get("avg_frame_rate", "0/0") != "0/0":
        num, den = v["avg_frame_rate"].split("/")
        fps = float(num) / float(den) if float(den) else 0.0

    dur = float(fmt.get("duration") or (v or {}).get("duration") or 0)
    w, h = (int(v["width"]), int(v["height"])) if v else (0, 0)
    rot = 0
    for sd in (v or {}).get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    disp_w, disp_h = (h, w) if abs(rot) in (90, 270) else (w, h)

    return {
        "path": str(path),
        "filename": Path(path).name,
        "duration_sec": round(dur, 3),
        "duration_hms": hhmmss(dur),
        "width": w, "height": h,
        "display_width": disp_w, "display_height": disp_h,
        "orientation": "vertical" if disp_h > disp_w else ("square" if disp_h == disp_w else "horizontal"),
        "aspect": round(disp_w / disp_h, 3) if disp_h else None,
        "fps": round(fps, 3),
        "video_codec": (v or {}).get("codec_name"),
        "audio_codec": (a or {}).get("codec_name"),
        "has_audio": a is not None,
        "audio_channels": (a or {}).get("channels"),
        "audio_sample_rate": (a or {}).get("sample_rate"),
        "bitrate_kbps": round(int(fmt.get("bit_rate", 0)) / 1000) if fmt.get("bit_rate") else None,
        "size_mb": round(int(fmt.get("size", 0)) / 1e6, 2) if fmt.get("size") else None,
    }


# ---------------------------------------------------------------- scene cuts

def detect_scenes(path, threshold=0.28):
    """מחזיר רשימת חותמות זמן של חיתוכי סצנה. פס ניתוח מוקטן = מהיר."""
    r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-filter:v", f"scale=320:-2,select='gt(scene,{threshold})',showinfo",
            "-an", "-f", "null", "-"])
    times = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    return sorted(set(round(t, 3) for t in times))


# ---------------------------------------------------------------- motion map

def motion_map(path, duration, sample_fps=4.0):
    """אנרגיית תנועה לכל דגימה — מזהה קצב עריכה, תזוזת מצלמה, סטטיות."""
    import numpy as np
    W, H = 160, 90
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
           "-vf", f"fps={sample_fps},scale={W}:{H}", "-pix_fmt", "gray",
           "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    fsize = W * H
    prev = None
    vals = []
    while True:
        buf = p.stdout.read(fsize)
        if len(buf) < fsize:
            break
        cur = np.frombuffer(buf, dtype=np.uint8).astype(np.int16)
        if prev is not None:
            vals.append(float(np.abs(cur - prev).mean()))
        prev = cur
    p.stdout.close()
    p.wait()
    series = [{"t": round(i / sample_fps, 2), "motion": round(v, 2)} for i, v in enumerate(vals)]
    return series


def summarize_motion(series):
    if not series:
        return {}
    vals = [s["motion"] for s in series]
    vals_sorted = sorted(vals)
    n = len(vals_sorted)

    def pct(p):
        return round(vals_sorted[min(n - 1, int(p * n))], 2)

    still = [s for s in series if s["motion"] < 1.0]
    return {
        "mean": round(sum(vals) / n, 2),
        "p10": pct(0.10), "median": pct(0.5), "p90": pct(0.90),
        "max": round(max(vals), 2),
        "static_ratio": round(len(still) / n, 3),
        "peaks": [s["t"] for s in sorted(series, key=lambda x: -x["motion"])[:8]],
    }


# ---------------------------------------------------------------- audio

def audio_levels(path, duration):
    """RMS ל-0.5 שנייה + זיהוי שתיקות."""
    r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-af", "aresample=8000,asetnsamples=4000,astats=metadata=1:reset=1,"
                   "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
            "-f", "null", "-"])
    levels = []
    t = None
    for line in r.stdout.splitlines():
        m = re.match(r"frame:\d+\s+pts:\d+\s+pts_time:([0-9.]+)", line)
        if m:
            t = float(m.group(1))
        m2 = re.search(r"RMS_level=(-?[0-9.inf]+)", line)
        if m2 and t is not None:
            v = m2.group(1)
            db = -91.0 if "inf" in v else float(v)
            levels.append({"t": round(t, 2), "db": round(db, 1)})
    s = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-af", "silencedetect=noise=-32dB:d=0.6", "-f", "null", "-"])
    silences = []
    start = None
    for line in s.stderr.splitlines():
        a = re.search(r"silence_start: (-?[0-9.]+)", line)
        b = re.search(r"silence_end: ([0-9.]+)", line)
        if a:
            start = float(a.group(1))
        if b and start is not None:
            silences.append({"start": round(max(0, start), 2), "end": round(float(b.group(1)), 2)})
            start = None
    return levels, silences


def transcribe(path, out_dir, lang=None, model_size="medium"):
    from faster_whisper import WhisperModel
    wav = out_dir / "audio.wav"
    sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-vn", "-ac", "1", "-ar", "16000", str(wav)])
    if not wav.exists() or wav.stat().st_size < 1000:
        return None

    model = WhisperModel(model_size, device="cpu", compute_type="int8",
                         cpu_threads=max(1, os.cpu_count() or 2))
    # תמיד מזהים שפה בפועל — גם כשהמשתמש כפה אחת. כך אפשר להתריע על אי-התאמה.
    detected, detected_p = None, None
    try:
        detected, detected_p, _ = model.detect_language(str(wav))
    except Exception:
        pass
    segments, info = model.transcribe(
        str(wav), language=lang, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        beam_size=5, condition_on_previous_text=False,
    )
    segs = []
    for s in segments:
        txt = s.text.strip()
        if txt:
            segs.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": txt})

    srt = out_dir / "transcript.srt"
    with srt.open("w", encoding="utf-8") as f:
        for i, s in enumerate(segs, 1):
            f.write(f"{i}\n{srt_ts(s['start'])} --> {srt_ts(s['end'])}\n{s['text']}\n\n")

    txt_path = out_dir / "transcript.txt"
    txt_path.write_text(
        "\n".join(f"[{hhmmss(s['start'])}] {s['text']}" for s in segs), encoding="utf-8")

    wav.unlink(missing_ok=True)
    words = sum(len(s["text"].split()) for s in segs)
    speech_sec = sum(s["end"] - s["start"] for s in segs)
    return {
        "language": info.language,
        "language_probability": round(float(info.language_probability or 0), 3),
        "detected_language": detected,
        "detected_probability": round(float(detected_p), 3) if detected_p is not None else None,
        "forced_language": lang,
        "segments": segs,
        "word_count": words,
        "speech_seconds": round(speech_sec, 1),
        "words_per_minute": round(words / (speech_sec / 60), 1) if speech_sec > 5 else None,
        "model": model_size,
    }


# ---------------------------------------------------------------- frames

def pick_timestamps(duration, scenes, max_frames, motion_series=None, baseline=1.5):
    """בחירת פריימים מונחית-תנועה.

    במקום רשת אחידה טיפשה: בונים 'עקומת עניין' לאורך הזמן (תנועה + רצפה קבועה),
    ומפזרים את תקציב הפריימים בצעדים שווים על *העניין המצטבר*. התוצאה — דגימה
    צפופה איפה שקורה משהו (תנועה, ביצוע תרגיל, חיתוך מהיר) ודלילה בקטעים סטטיים.
    חיתוכי סצנה, פריים ראשון ופריים אחרון נכפים תמיד.
    """
    forced = {round(max(0.0, duration * 0.01), 3), round(max(0.0, duration - 0.3), 3)}
    for t in scenes:
        if 0 <= t < duration:
            forced.add(round(min(duration - 0.05, t + 0.25), 3))
    forced = sorted(t for t in forced if 0 <= t < duration)

    room = max_frames - len(forced)
    if room <= 0:
        step = len(forced) / max_frames
        return sorted({forced[int(i * step)] for i in range(max_frames)}), \
            {"scenes": len(scenes), "mode": "scenes-only", "forced": len(forced)}

    if motion_series:
        ts_axis = [s["t"] for s in motion_series]
        weights = [s["motion"] + baseline for s in motion_series]
    else:  # אין מפת תנועה → נפילה חיננית לרשת אחידה
        n = max(2, int(duration * 2))
        ts_axis = [i * duration / n for i in range(n)]
        weights = [1.0] * n

    cum, acc = [], 0.0
    for w in weights:
        acc += w
        cum.append(acc)
    total = cum[-1] or 1.0

    picks = []
    for i in range(room):
        target = total * (i + 0.5) / room
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum[mid] < target:
                lo = mid + 1
            else:
                hi = mid
        picks.append(round(min(duration - 0.05, ts_axis[lo]), 3))

    ts = sorted(set(forced) | set(picks))
    return ts, {"scenes": len(scenes), "mode": "motion-weighted" if motion_series else "uniform",
                "forced": len(forced), "sampled": len(picks)}


def extract_frames(path, timestamps, frames_dir, width=640):
    frames_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for i, t in enumerate(timestamps):
        f = frames_dir / f"f{i:03d}_{t:08.2f}.jpg"
        r = sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                "-vf", f"scale={width}:-2:flags=lanczos", "-q:v", "3", str(f)])
        if f.exists() and f.stat().st_size > 0:
            out.append({"t": t, "file": str(f)})
    return out


def dedupe(frames, cutoff=4, max_gap=8.0):
    """מסיר פריימים כמעט-זהים (perceptual hash), אבל אף פעם לא יוצר חור בציר הזמן
    גדול מ-max_gap שניות — כדי שהכיסוי הכרונולוגי יישאר שלם."""
    if cutoff <= 0:
        return frames, 0
    try:
        import imagehash
        from PIL import Image
    except ImportError:
        return frames, 0
    kept, hashes, removed = [], [], 0
    last_t = None
    for fr in frames:
        h = imagehash.dhash(Image.open(fr["file"]), hash_size=12)
        dup = any(h - prev <= cutoff for prev in hashes[-3:])
        gap_ok = last_t is None or (fr["t"] - last_t) < max_gap
        if dup and gap_ok:
            removed += 1
            Path(fr["file"]).unlink(missing_ok=True)
            continue
        hashes.append(h)
        kept.append(fr)
        last_t = fr["t"]
    return kept, removed


def contact_sheets(frames, out_dir, grid=(4, 3), sheet_width=1400, label_h=26):
    """גיליונות מגע — כל אריח עם חותמת זמן ומספר. זה מה שהמודל 'רואה'."""
    from PIL import Image, ImageDraw, ImageFont
    cols, rows = grid
    per = cols * rows
    tile_w = sheet_width // cols
    font_path = next((f for f in FONT_CANDIDATES if os.path.exists(f)), None)
    font = ImageFont.truetype(font_path, 16) if font_path else ImageFont.load_default()

    sheets = []
    for si in range(0, len(frames), per):
        chunk = frames[si:si + per]
        with Image.open(chunk[0]["file"]) as im0:
            ar = im0.height / im0.width
        tile_h = int(tile_w * ar)
        cell_h = tile_h + label_h
        sheet = Image.new("RGB", (tile_w * cols, cell_h * math.ceil(len(chunk) / cols)), (17, 17, 17))
        d = ImageDraw.Draw(sheet)
        for k, fr in enumerate(chunk):
            cx, cy = (k % cols) * tile_w, (k // cols) * cell_h
            with Image.open(fr["file"]) as im:
                im = im.convert("RGB").resize((tile_w, tile_h), Image.LANCZOS)
                sheet.paste(im, (cx, cy))
            idx = si + k
            d.rectangle([cx, cy + tile_h, cx + tile_w, cy + cell_h], fill=(17, 17, 17))
            d.text((cx + 6, cy + tile_h + 4), f"#{idx:03d}  {hhmmss(fr['t'])}",
                   fill=(255, 214, 0), font=font)
            d.rectangle([cx, cy, cx + tile_w - 1, cy + cell_h - 1], outline=(45, 45, 45))
        p = out_dir / f"contact_{len(sheets) + 1:02d}.jpg"
        sheet.save(p, quality=88)
        sheets.append({"file": str(p), "frames": [f["t"] for f in chunk],
                       "range": [chunk[0]["t"], chunk[-1]["t"]]})
    return sheets


# ---------------------------------------------------------------- shots

def shot_list(scenes, duration):
    cuts = [0.0] + [c for c in scenes if 0.2 < c < duration - 0.2] + [duration]
    shots = []
    for i in range(len(cuts) - 1):
        shots.append({"n": i + 1, "start": round(cuts[i], 2), "end": round(cuts[i + 1], 2),
                      "len": round(cuts[i + 1] - cuts[i], 2)})
    return shots


# ---------------------------------------------------------------- report

def write_report(out_dir, meta, sheets, shots, motion_sum, silences, tr, frames, notes):
    L = []
    A = L.append
    A(f"# ניתוח וידאו — {meta['filename']}\n")
    A("> קרא את קבצי `contact_*.jpg` בכלי Read כדי לראות את הפריימים בפועל, "
      "ואת `transcript.txt` לתמלול מסונכרן. אל תסיק מסקנות ויזואליות בלי לפתוח את הגיליונות.\n")

    A("## מפרט טכני\n")
    A(f"- אורך: **{meta['duration_hms']}** ({meta['duration_sec']}s) · {meta['fps']} fps")
    A(f"- רזולוציה: **{meta['display_width']}x{meta['display_height']}** ({meta['orientation']}, יחס {meta['aspect']})")
    A(f"- קודק: {meta['video_codec']} / אודיו: {meta['audio_codec'] or 'אין'} · "
      f"{meta['size_mb']} MB · {meta['bitrate_kbps']} kbps\n")

    A("## גיליונות מגע (VISION)\n")
    for s in sheets:
        A(f"- `{Path(s['file']).name}` — {hhmmss(s['range'][0])} → {hhmmss(s['range'][1])} "
          f"({len(s['frames'])} פריימים)")
    A(f"\nסה\"כ {len(frames)} פריימים נבחרים. לזום על רגע ספציפי:\n"
      f"`python3 video_eyes.py frame \"{meta['path']}\" 00:01:23.5`\n")

    A("## רשימת שוטים (RHYTHM)\n")
    if len(shots) <= 1:
        A("- שוט רציף אחד — אין חיתוכי עריכה שזוהו.\n")
    else:
        lens = [s["len"] for s in shots]
        A(f"- **{len(shots)} שוטים**, אורך ממוצע **{round(sum(lens)/len(lens),2)}s**, "
          f"קצר ביותר {min(lens)}s, ארוך ביותר {max(lens)}s")
        A(f"- קצב: **{round(len(shots)/(meta['duration_sec']/60),1)} חיתוכים לדקה**\n")
        A("| # | התחלה | סוף | אורך |")
        A("|---|-------|-----|------|")
        for s in shots[:60]:
            A(f"| {s['n']} | {hhmmss(s['start'])} | {hhmmss(s['end'])} | {s['len']}s |")
        if len(shots) > 60:
            A(f"| ... | | | +{len(shots)-60} שוטים נוספים ב-data.json |")
        A("")

    A("## תנועה\n")
    if motion_sum:
        A(f"- ממוצע {motion_sum['mean']} · חציון {motion_sum['median']} · שיא {motion_sum['max']}")
        A(f"- **{round(motion_sum['static_ratio']*100)}%** מהזמן כמעט סטטי (מצלמה/נושא ללא תזוזה)")
        A(f"- רגעי שיא תנועה: {', '.join(hhmmss(t) for t in motion_sum['peaks'])}\n")

    A("## שמע\n")
    if silences:
        tot = sum(s["end"] - s["start"] for s in silences)
        A(f"- {len(silences)} מקטעי שתיקה (>0.6s), סה\"כ {round(tot,1)}s "
          f"({round(tot/meta['duration_sec']*100)}% מהאורך)")
        for s in silences[:12]:
            A(f"  - {hhmmss(s['start'])} → {hhmmss(s['end'])} ({round(s['end']-s['start'],1)}s)")
        A("")
    else:
        A("- לא זוהו מקטעי שתיקה משמעותיים.\n")

    A("## דיבור (SPEECH)\n")
    if tr:
        A(f"- שפה: **{tr['language']}** (ביטחון {tr['language_probability']}) · מודל {tr['model']}")
        A(f"- {tr['word_count']} מילים ב-{tr['speech_seconds']}s דיבור"
          + (f" · **{tr['words_per_minute']} מילים לדקה**" if tr["words_per_minute"] else ""))
        A(f"- קבצים: `transcript.txt` (עם חותמות זמן), `transcript.srt`\n")
        A("### 10 השניות הראשונות (ההוק)\n")
        for s in tr["segments"]:
            if s["start"] < 10:
                A(f"- `[{hhmmss(s['start'])}]` {s['text']}")
        A("")
    else:
        A("- אין אודיו או שהתמלול דולג.\n")

    if notes:
        A("## הערות ריצה\n")
        for n in notes:
            A(f"- {n}")
        A("")

    (out_dir / "report.md").write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------- commands

def cmd_analyze(a):
    src = Path(a.video).expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"לא נמצא קובץ: {src}")
    out = Path(a.out).expanduser().resolve() if a.out else src.parent / f"{src.stem}_eyes"
    if out.exists() and a.clean:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    frames_dir = out / "frames"
    notes = []

    meta = probe(src)
    print(f"[1/6] {meta['duration_hms']} · {meta['display_width']}x{meta['display_height']} · {meta['fps']}fps", flush=True)

    scenes = detect_scenes(src, a.scene)
    series = motion_map(src, meta["duration_sec"])
    msum = summarize_motion(series)
    print(f"[2/6] {len(scenes)} חיתוכי סצנה · תנועה ממוצעת {msum.get('mean')}", flush=True)

    ts, pick_info = pick_timestamps(meta["duration_sec"], scenes, a.max_frames, series)
    frames = extract_frames(src, ts, frames_dir, width=a.frame_width)
    max_gap = a.max_gap if a.max_gap is not None else max(2.0, meta["duration_sec"] / 8)
    frames, removed = dedupe(frames, cutoff=a.dedupe, max_gap=max_gap)
    if removed:
        notes.append(f"דוללו {removed} פריימים כמעט-זהים (סף {a.dedupe}, חור מקס' {round(max_gap,1)}s).")
    print(f"[3/6] {len(frames)} פריימים ({pick_info['mode']}, {removed} כפילויות הוסרו)", flush=True)

    if a.grid == "auto":
        # אריח אנכי גבוה → יותר עמודות ופחות שורות, אחרת הגיליון יוצא ענק וצר
        cols, rows = {"vertical": (6, 2), "square": (5, 3), "horizontal": (4, 3)}[meta["orientation"]]
    else:
        cols, rows = (int(x) for x in a.grid.lower().split("x"))
    sheets = contact_sheets(frames, out, grid=(cols, rows), sheet_width=a.sheet_width)
    print(f"[4/6] {len(sheets)} גיליונות מגע", flush=True)

    shots = shot_list(scenes, meta["duration_sec"])
    print(f"[5/6] {len(shots)} שוטים", flush=True)

    levels, silences, tr = [], [], None
    if meta["has_audio"] and not a.no_audio:
        levels, silences = audio_levels(src, meta["duration_sec"])
        try:
            tr = transcribe(src, out, lang=a.lang, model_size=a.model)
            if tr and a.lang and tr.get("detected_language") and tr["detected_language"] != a.lang:
                notes.append(f"⚠️ נכפתה שפה '{a.lang}' אך זוהתה בפועל "
                             f"'{tr['detected_language']}' ({tr['detected_probability']}) — "
                             f"התמלול כנראה שגוי. להריץ שוב בלי --lang.")
            if tr and (tr.get("detected_probability") or 1) < 0.6:
                notes.append(f"⚠️ ביטחון זיהוי שפה נמוך ({tr['detected_probability']}) — "
                             f"לאמת את התמלול או להריץ עם --model large-v3.")
        except Exception as e:
            notes.append(f"תמלול נכשל: {type(e).__name__}: {e}")
    elif not meta["has_audio"]:
        notes.append("לקובץ אין רצועת אודיו.")
    print(f"[6/6] תמלול: {tr['word_count'] if tr else 0} מילים", flush=True)

    params = {k: v for k, v in vars(a).items() if k != "func"}
    data = {"meta": meta, "scenes": scenes, "shots": shots, "frames": frames,
            "sheets": sheets, "motion_summary": msum, "motion_series": series,
            "audio_levels": levels, "silences": silences,
            "transcript": tr, "params": params, "pick_info": pick_info}
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(out, meta, sheets, shots, msum, silences, tr, frames, notes)

    print(f"\n✅ bundle: {out}")
    print(f"   קרא: {out}/report.md")
    for s in sheets:
        print(f"   ראה: {s['file']}")


def cmd_frame(a):
    src = Path(a.video).expanduser().resolve()
    t = parse_ts(a.timestamp)
    dest = Path(a.out) if a.out else src.parent / f"{src.stem}_t{t:.2f}.jpg"
    vf = f"scale={a.width}:-2:flags=lanczos" if a.width else "null"
    r = sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", "-vf", vf, "-q:v", "2", str(dest)])
    if r.returncode != 0 or not dest.exists():
        raise SystemExit(r.stderr[:400])
    print(dest)


def cmd_strip(a):
    """רצועת פריימים צפופה סביב רגע — לניתוח תנועה/טכניקה פריים-אחר-פריים.
    למשל: בדיקת עומק סקוואט, מסלול המוט בסנאץ', רגע נחיתה, מעבר בעריכה."""
    src = Path(a.video).expanduser().resolve()
    meta = probe(src)
    center = parse_ts(a.timestamp)
    half = a.window / 2.0
    start = max(0.0, center - half)
    end = min(meta["duration_sec"], center + half)
    step = (end - start) / max(1, a.count - 1) if a.count > 1 else 0
    ts = [round(start + i * step, 3) for i in range(a.count)]

    out = Path(a.out).expanduser().resolve() if a.out else src.parent / f"{src.stem}_strip_{center:.2f}"
    out.mkdir(parents=True, exist_ok=True)
    frames = extract_frames(src, ts, out / "frames", width=a.frame_width)
    if not frames:
        raise SystemExit("לא חולצו פריימים")
    cols, rows = (int(x) for x in a.grid.lower().split("x"))
    sheets = contact_sheets(frames, out, grid=(cols, rows), sheet_width=a.sheet_width)
    print(f"רצועה: {hhmmss(start)} → {hhmmss(end)} · {len(frames)} פריימים · "
          f"מרווח {round(step,3)}s ({round(1/step,1) if step else '—'} fps)")
    for s in sheets:
        print(f"ראה: {s['file']}")


def cmd_probe(a):
    print(json.dumps(probe(Path(a.video).expanduser().resolve()), ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="נותן ל-Claude עיניים לניתוח וידאו")
    sub = p.add_subparsers(dest="cmd", required=True)

    an = sub.add_parser("analyze")
    an.add_argument("video")
    an.add_argument("--out")
    an.add_argument("--lang", default=None, help="he / en / None=זיהוי אוטומטי")
    an.add_argument("--model", default="medium", help="tiny|base|small|medium|large-v3")
    an.add_argument("--max-frames", type=int, default=48)
    
    an.add_argument("--scene", type=float, default=0.28, help="סף זיהוי חיתוך סצנה")
    an.add_argument("--grid", default="auto", help="auto | 4x3 | 6x2 ...")
    an.add_argument("--sheet-width", type=int, default=1400)
    an.add_argument("--frame-width", type=int, default=640)
    an.add_argument("--dedupe", type=int, default=4, help="0=כבוי")
    an.add_argument("--max-gap", type=float, default=None,
                    help="חור מקסימלי בציר הזמן שדילול כפילויות מורשה ליצור")
    an.add_argument("--no-audio", action="store_true")
    an.add_argument("--clean", action="store_true")
    an.set_defaults(func=cmd_analyze)

    fr = sub.add_parser("frame")
    fr.add_argument("video")
    fr.add_argument("timestamp")
    fr.add_argument("--out")
    fr.add_argument("--width", type=int, default=1200)
    fr.set_defaults(func=cmd_frame)

    st = sub.add_parser("strip", help="רצועת פריימים צפופה סביב רגע (ניתוח טכניקה)")
    st.add_argument("video")
    st.add_argument("timestamp")
    st.add_argument("--window", type=float, default=2.0, help="חלון בשניות סביב הרגע")
    st.add_argument("--count", type=int, default=12, help="כמה פריימים בחלון")
    st.add_argument("--grid", default="4x3")
    st.add_argument("--sheet-width", type=int, default=1500)
    st.add_argument("--frame-width", type=int, default=700)
    st.add_argument("--out")
    st.set_defaults(func=cmd_strip)

    pr = sub.add_parser("probe")
    pr.add_argument("video")
    pr.set_defaults(func=cmd_probe)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
