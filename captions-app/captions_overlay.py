#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
captions_overlay.py — צריבת כתוביות R.E.L ללא libass
=====================================================
ffmpeg של המאק נבנה בלי libass/drawtext, אז במקום מסנן subtitles אנחנו
מרנדרים כל כתובית כ-PNG שקוף (PIL: פונט וצבע לפי המותג, RTL נכון)
ומרכיבים בשכבת overlay אחת על הסרטון.

סגנון זהה ל-captions_build: מילה אחת בכל פעם, בלי נקודות/פסיקים, לבן עם
מתאר מותג, תחתון-מרכז. חוקי הקיבוץ/הניקוי מיובאים מ-captions_build.
"""
import sys, json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, features

# עברית RTL (24.7.26, אותו לקח כמו thumbnail_build.py — ראה [[feedback_captions_rtl_double_reversal_raqm]]):
# מאז ש-Pillow נבנה מחדש מול libraqm (לתיקון הקאברים), ImageFont.truetype טוען
# את הפונט עם שכבת bidi+shaping מובנית משלו. הפעלת python-bidi/get_display *גם* על
# גבי raqm גורמת להיפוך כפול — הכתובית יוצאת הפוכה לגמרי. RAQM=True → מעבירים טקסט
# לוגי גולמי עם direction="rtl" ו-raqm עושה את זה נכון לבד. fallback ל-get_display
# רק אם אין raqm בבנייה הזו של Pillow.
RAQM = features.check("raqm")

def _bidi_fallback(s):
    from bidi.algorithm import get_display
    return get_display(s)

HERE     = Path(__file__).resolve().parent
TOOLS    = HERE.parent / "tools"
ASSETS   = HERE.parent / "brand-assets"
sys.path.insert(0, str(TOOLS))
from captions_build import group_cues, load_words   # reuse brand grouping/cleaning

WHITE = (255, 255, 255, 255)
# חוק ברזל (הראל 3.8.26): צבע ופונט הם פרופיל אטומי — אין ערבוב בין המותגים.
BRAND_PROFILES = {
    "club": {
        "outline": (135, 29, 31, 255),       # #871d1f
        "font": ASSETS / "Assistant-ExtraBold.ttf",
    },
    "personal": {
        "outline": (0, 119, 182, 255),       # #0077B6
        "font": ASSETS / "Assistant-ExtraBold.ttf",  # תוקן 24.8.26 — Heebo לא פונט המותג
    },
}
BRAND_ALIASES = {"rel": "club", "oshia": "personal"}
BRAND = BRAND_PROFILES["club"]["outline"]   # תאימות לקוד ישן בלבד


def _rotation(path):
    """סיבוב התצוגה (Display Matrix של אייפון וכו'). ffmpeg מסובב אוטומטית
    את הפריים לפני ה-overlay, אז חייבים לרנדר כתוביות בממדי *התצוגה*."""
    for entries in ("stream_side_data=rotation", "stream_tags=rotate"):
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", entries, "-of", "default=nk=1:nw=1", path],
            capture_output=True, text=True).stdout.strip().splitlines()
        if r:
            try:
                return int(float(r[0]))
            except Exception:
                pass
    return 0


def ffprobe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration", "-of", "json", path],
        capture_output=True, text=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    W, H = int(s["width"]), int(s["height"])
    dur = float((j.get("format") or {}).get("duration") or 0)
    if abs(_rotation(path)) % 180 == 90:     # ±90/270 → ממדי תצוגה מתחלפים
        W, H = H, W
    return W, H, dur


def _draw(d, xy, text, font, stroke, outline):
    if RAQM:
        d.text(xy, text, font=font, fill=WHITE, anchor="ms",
               direction="rtl", stroke_width=stroke, stroke_fill=outline)
    else:
        disp = _bidi_fallback(text)           # סדר ויזואלי RTL (עברית) — רק בלי raqm
        d.text(xy, disp, font=font, fill=WHITE, anchor="ms",
               stroke_width=stroke, stroke_fill=outline)


def band_box(cues, W, H, font, stroke, marginv):
    """v7.8 — גובה הרצועה שבה באמת יש כתובית, לפי מדידת ה-bbox האמיתי של כל cue.

    למה: עד v7.6 כל כתובית נצרבה כ-PNG שקוף בגודל **פריים מלא** (1080×1920 RGBA ≈ 8MB
    גולמי), ו-ffmpeg מיזג את כולו על כל פריים — בזבוז של פי ~8 בפיקסלים גם ב-PIL וגם
    ב-overlay, כשהטקסט תופס רצועה של ~240px. עכשיו מרנדרים רק את הרצועה וממקמים אותה
    ב-overlay=0:y0. התוצאה ויזואלית זהה לחלוטין (אותו baseline, אותו מרכוז).
    """
    probe = Image.new("RGBA", (8, 8))
    d = ImageDraw.Draw(probe)
    base_y = H - marginv
    top, bot = base_y, base_y
    for c in cues:
        t = c["text"] if RAQM else _bidi_fallback(c["text"])
        try:
            bb = d.textbbox((W // 2, base_y), t, font=font, anchor="ms",
                            stroke_width=stroke,
                            **({"direction": "rtl"} if RAQM else {}))
        except Exception:
            bb = (0, base_y - int(font.size * 1.4), W, base_y + int(font.size * 0.6))
        top, bot = min(top, bb[1]), max(bot, bb[3])
    pad = max(4, stroke * 2)
    y0 = max(0, int(top) - pad)
    y1 = min(H, int(bot) + pad)
    if (y1 - y0) % 2:                      # גובה זוגי — ידידותי ל-yuv420p
        y1 = min(H, y1 + 1)
    return y0, (y1 - y0)


def render_cue(text, W, band_h, font, stroke, baseline_in_band, path, outline=BRAND):
    """PNG שקוף בגודל רצועת-הכתוביות עם מילה לבנה + מתאר מותג, ממורכז, RTL."""
    img = Image.new("RGBA", (W, band_h), (0, 0, 0, 0))
    _draw(ImageDraw.Draw(img), (W // 2, baseline_in_band), text, font, stroke, outline)
    img.save(str(path), compress_level=1)   # PNG מהיר — הקובץ זמני ונמחק


def burn(words_json, src, out_name, workdir, brand="rel"):
    """מרנדר כתוביות ומרכיב על הסרטון. רץ עם cwd=workdir (נתיבים יחסיים,
    כדי לעקוף את בעיית הרווחים/עברית בנתיב iCloud). מחזיר (ok, err, n_cues)."""
    workdir = Path(workdir)
    W, H, dur = ffprobe(src)
    cues = group_cues(load_words(str(words_json)))
    if not cues:
        return False, "לא זוהה דיבור לכתוביות בסרטון", 0

    canonical_brand = BRAND_ALIASES.get(brand, brand)
    profile = BRAND_PROFILES.get(canonical_brand)
    if not profile:
        return False, "מותג לא חוקי — יש לבחור personal או club", 0
    if not profile["font"].exists():
        return False, f"קובץ הפונט של המותג חסר: {profile['font']}", 0

    scale    = H / 1920.0
    fontsize = max(28, round(120 * scale))
    stroke   = max(3, round(7 * scale))
    marginv  = max(40, round(430 * scale))
    font = ImageFont.truetype(str(profile["font"]), fontsize)

    outline = profile["outline"]
    y0, band_h = band_box(cues, W, H, font, stroke, marginv)
    baseline_in_band = (H - marginv) - y0
    Image.new("RGBA", (W, band_h), (0, 0, 0, 0)).save(str(workdir / "_blank.png"),
                                                      compress_level=1)
    # רינדור מקבילי — PIL משחרר את ה-GIL בציור/שמירה, וזה 100+ קבצים בכל סרטון
    with ThreadPoolExecutor(max_workers=min(6, (os.cpu_count() or 4))) as ex:
        list(ex.map(lambda ic: render_cue(ic[1]["text"], W, band_h, font, stroke,
                                          baseline_in_band,
                                          workdir / f"cue_{ic[0]:04d}.png", outline),
                    list(enumerate(cues))))

    # רשימת concat לאורך ציר הזמן: שקוף בין הכתוביות, מילה בזמן שלה.
    L, t = ["ffconcat version 1.0"], 0.0
    for i, c in enumerate(cues):
        s = float(c["start"]); e = max(float(c["end"]), s + 0.05)
        if s > t + 0.002:
            L += ["file '_blank.png'", f"duration {round(s - t, 3)}"]
        L += [f"file 'cue_{i:04d}.png'", f"duration {round(e - s, 3)}"]
        t = e
    if dur > t + 0.002:
        L += ["file '_blank.png'", f"duration {round(dur - t, 3)}"]
    L.append("file '_blank.png'")            # חזרה אחרונה (דרישת concat)
    (workdir / "caplist.txt").write_text("\n".join(L) + "\n", encoding="utf-8")

    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin",
           "-i", str(src),
           "-f", "concat", "-safe", "0", "-i", "caplist.txt",
           "-filter_complex", f"[0:v][1:v]overlay=0:{y0}:format=auto:eof_action=pass[v]",
           "-map", "[v]", "-map", "0:a?",
           # v7.8 — preset medium→veryfast + crf 18→16. נמדד על סרטון אמיתי (53ש,
           # 1080×1920@30) מול המקור MIXED.mp4:
           #   medium/crf18   22.2ש  SSIM 0.98560
           #   veryfast/crf16  9.6ש  SSIM 0.98577  ← מהיר פי 2.3, איכות זהה-או-טובה-יותר
           # ה-SSIM כמעט זהה כי כל שאר שלבי השרשרת (edl_cut/tighten/broll) כבר עובדים
           # ב-veryfast — האיכות הייתה חסומה שם ממילא, וה-preset האיטי בשלב האחרון רק
           # שרף זמן. הקובץ גדול ב-~15% (מקדם דחיסה פחות יעיל) — זניח לסרטון של דקה.
           "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-movflags", "+faststart", out_name]
    r = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True)
    if r.returncode != 0 or not (workdir / out_name).exists():
        return False, "שגיאת צריבה: " + r.stderr[-900:], len(cues)
    return True, None, len(cues)
