#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thumbnail_build.py — מנוע Thumbnail נעול-מותג ל-CrossFit R.E.L
תבנית קבועה: רקע פריים cover 1080x1920, קופסה אדומה #871d1f בשקיפות 70%,
כותרת Ploni Bold לבנה (auto-fit), תת-כותרת Studentit לבנה (קטנה יותר). RTL.

עברית RTL: כש-Pillow נבנה עם raqm (libraqm) — מעבירים את הטקסט הלוגי כמו שהוא עם
direction="rtl" ו-raqm מבצע bidi+shaping נכון. אסור להפעיל python-bidi/get_display
על גבי raqm — זה גורם להיפוך כפול (טקסט הפוך). fallback ל-get_display רק כשאין raqm.
"""
import os, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont, features, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
TITLE_FONT = os.path.join(FONTS, "PloniBold.otf")
# v6 (26.7.26) — **הפונט המלא**. הראל ייצא מ-Canva PDF עם כל תווי Studentit,
# וה-PDF הכיל את הפונט מוטמע כ-TrueType (EFT_Studentit) — חילצנו אותו כמו-שהוא.
# 271 תווים: 27 אותיות + ניקוד + ספרות + לטינית + פיסוק מלא + גרש/גרשיים + ₪.
# נמדד: גובה האות א = 0.6400 מה-em, זהה ל-subset הישן (0.6401) ⇒ אותו גודל
# אופטי באותו point-size, בלי לגעת ב-SUB_RATIO.
# זה מסיים את התקלה החוזרת "התת-כותרת בפונט הלא-נכון": הסיבה היחידה שהיא
# נפלה לפונט אחר הייתה שהקובץ הישן היה specimen subset בלי פיסוק וספרות.
SUB_FONT   = os.path.join(FONTS, "Studentit-Full.ttf")
if not os.path.exists(SUB_FONT):
    SUB_FONT = os.path.join(FONTS, "Studentit-Specimen-Subset.ttf")
SUB_FONT_TIER2 = os.path.join(FONTS, "Bagira-Specimen-Subset.otf")  # פונט משלים — אישור הראל 24.7.26
SUB_FONT_FALLBACK = TITLE_FONT  # Ploni Bold — רשת ביטחון סופית (כיסוי מלא)
# v6 26.7.26 — **הוסרה שרשרת הנפילה הישנה** (DanaYad → Playpen → Ploni).
# היא נועדה למקרה שקובץ הפונט חסר, אבל בפועל היא הייתה דלת אחורית שקטה
# להחלפת פונט התת-כותרת. עכשיו: אם אין Studentit — נופלים בקול, לא בשקט.
if not os.path.exists(SUB_FONT):
    raise SystemExit(
        f"❌ פונט התת-כותרת חסר: {SUB_FONT}\n"
        f"   Studentit הוא כלל מותג קשיח לתת-כותרת. אין נפילה לפונט אחר.\n"
        f"   העתק מחדש מ-brand-assets/fonts/Studentit-Full.ttf")
SUB_FONT_IS_STUDENTIT = os.path.basename(SUB_FONT).startswith("Studentit")

# 24.7.26 — שני קבצי הפונט שהראל סיפק הם "Specimen Subset": מכילים רק תת-סט מוגבל של
# תווים (נבדק ב-fontTools, קודי unicode מדויקים). תת-כותרת עם תו מחוץ לתת-הסט של פונט
# נתון נופלת לפונט הבא בשרשרת — לא נשארת עם גליף ריבועי/חסר:
#   1) Studentit (SUB_FONT)   — 27 האותיות העבריות (כולל סופיות) + רווח בלבד. בלי ספרות/
#      פיסוק/לועזית.
#   2) Bagira (SUB_FONT_TIER2) — משלים: כל 27 האותיות העבריות + רווח + ספרות 0-9 + פיסוק/
#      סימנים נפוצים (! # $ % ) * + , . : ? @ [ { ₪ € וכו') + ניקוד חלקי. עדיין בלי אותיות
#      לועזיות (A-Z/a-z).
#   3) Ploni Bold (SUB_FONT_FALLBACK) — כיסוי מלא (כולל לועזית), רשת ביטחון סופית.
# אם וכשיגיעו קבצים מלאים יותר של הפונטים — אפשר להסיר/להרחיב את סטי התווים האלה.
SUB_FONT_ALLOWED = set(" אבגדהוזחטיךכלםמןנסעףפץצקרשת")
_BAGIRA_CODEPOINTS = [
    0x0020, 0x0021, 0x0023, 0x0024, 0x0025, 0x0029, 0x002A, 0x002B, 0x002C, 0x002E,
    0x0030, 0x0031, 0x0032, 0x0033, 0x0034, 0x0035, 0x0036, 0x0037, 0x0038, 0x0039,
    0x003A, 0x003F, 0x0040, 0x005B, 0x007B, 0x00A4, 0x00A9, 0x00B1, 0x00D7,
    0x05B7, 0x05B8, 0x05BC, 0x05BE, 0x05C6,
    0x05D0, 0x05D1, 0x05D2, 0x05D3, 0x05D4, 0x05D5, 0x05D6, 0x05D7, 0x05D8, 0x05D9,
    0x05DA, 0x05DB, 0x05DC, 0x05DD, 0x05DE, 0x05DF, 0x05E0, 0x05E1, 0x05E2, 0x05E3,
    0x05E4, 0x05E5, 0x05E6, 0x05E7, 0x05E8, 0x05E9, 0x05EA,
    0x05F4, 0x203D, 0x20AA, 0x20AC, 0x20BF, 0x2190, 0x2762, 0x27BF, 0xFB4F,
]
SUB_FONT_TIER2_ALLOWED = set(chr(c) for c in _BAGIRA_CODEPOINTS)

W, H = 1080, 1920
BRAND = (135, 29, 31)      # #871d1f
BAND_ALPHA = int(round(0.70 * 255))   # שקיפות 70%
WHITE = (255, 255, 255)
MARGIN_X = 70              # שוליים אופקיים לטקסט
BAND_CENTER_Y = 0.725     # מרכז אנכי של הקופסה (יחס מהגובה)
PAD_Y = 40                # ריפוד אנכי בתוך הקופסה
GAP = 6                   # מרווח כותרת↔תת-כותרת
TITLE_START = 260         # גודל כותרת התחלתי (auto-shrink)
SUB_RATIO = 0.85          # 23.7.26 v2 — כלל קדוש של אוריה: "הכיתוב למעלה (כותרת) צריך
                          # להיות יותר גדול מהלמטה (תת-כותרת)". הופעל מחדש (אחרי שהיה
                          # dead code בגרסה הקודמת מאותו יום) — אבל עכשיו נגזר מ-tfont.size
                          # (הגודל המתאים בפועל של הכותרת, אחרי shrink-to-fit) ולא מ-
                          # TITLE_START (קבוע שלא מייצג את מה שבאמת מוצג). היסטוריה: קודם
                          # SUB_RATIO*TITLE_START לא הגביל כלום (טקסטים קצרים מ-max_w תמיד),
                          # אחר-כך fit עצמאי בלי תקרה בכלל יצר תת-כותרת גדולה מהכותרת עצמה
                          # (126px מול 80px) — הפוך מהכוונה. עכשיו: sub_start = tfont.size *
                          # SUB_RATIO מבטיח שהתת-כותרת תמיד קטנה מהכותרת בפועל, לא משנה
                          # כמה קצר טקסט הכותרת. ראה גם כלל "פחות מלל" — טקסט קאבר קצר
                          # (כותרת 2-3 מילים, תת-כותרת קצרה) מייצר את שתי השורות גדולות
                          # וקריאות בהתאם.
SUB_MIN_SIZE = 40         # רצפת גודל לתת-כותרת (לא תרד מתחת לזה גם בטקסט ארוך)
SUB_STROKE_RATIO = 0      # ללא פסאודו-בולד בקאברי המועדון (נעול נפרד עבור אושיה — ראה make_cover.py)

RAQM = features.check("raqm")   # Pillow עם libraqm? → bidi+shaping מובנה

def _bidi_fallback(s):
    from bidi.algorithm import get_display
    return get_display(s)

def draw_rtl(d, xy, text, font, fill, anchor, stroke_width=0, stroke_fill=None):
    """ציור טקסט עברי בכיוון RTL נכון. stroke_width>0 = פסאודו-בולד (לפונט חד-משקל כמו Studentit)."""
    if RAQM:
        d.text(xy, text, font=font, fill=fill, anchor=anchor, direction="rtl",
               stroke_width=stroke_width, stroke_fill=stroke_fill or fill)
    else:
        d.text(xy, _bidi_fallback(text), font=font, fill=fill, anchor=anchor,
               stroke_width=stroke_width, stroke_fill=stroke_fill or fill)

def measure_rtl(d, text, font):
    if RAQM:
        return d.textlength(text, font=font, direction="rtl")
    return d.textlength(_bidi_fallback(text), font=font)

# ─── v5 (הראל 26.7.26) — תת-כותרת נשארת Studentit, תמיד ─────────────────────
# "למה אתה כל פעם מפספס את הפונט בתת-כותרת? תיקנתי אותך על זה כמה פעמים."
# שורש כפול, שנמדד ולא שוער:
#   1) הקובץ Studentit-Specimen-Subset.ttf הוא **subset**: 27 אותיות עבריות
#      בלבד — אפס ספרות, אפס פיסוק (נבדק ב-cmap בפועל). גם Bagira חסר גרש.
#   2) הקוד הפיל את **כל** התת-כותרת ל-Ploni Bold ברגע שתו אחד לא נתמך, ולא
#      אמר על זה מילה — הפלט הדפיס רק "OK title_size/sub_size". לכן "מנוי
#      אופן ג'ים צהריים" (גרש אחד!) יצא כולו ב-Ploni, ואני לא ראיתי.
# התיקון: החלפת-פונט **פר-תו** במקום פר-מחרוזת. האותיות תמיד Studentit;
# רק תו לא-נתמך (גרש/ספרה/פיסוק) נלקח מפונט הגיבוי. בנוסף — דיווח רועש.
def font_coverage(path):
    """סט התווים שהפונט באמת תומך בהם — נגזר מה-cmap, לא מרשימה קשיחה
    (רשימה קשיחה נוטה להתנתק מהקובץ; זה מה שקרה כאן)."""
    try:
        from fontTools.ttLib import TTFont
        t = TTFont(path, fontNumber=0, lazy=True)
        cov = set()
        for tb in t["cmap"].tables:
            cov |= {chr(c) for c in tb.cmap.keys()}
        return cov
    except Exception:
        return None

def draw_rtl_mixed(d, xy, text, main_font, fb_font, fill, anchor,
                   coverage, stroke_width=0, stroke_fill=None):
    """מצייר RTL כשכל תו מצויר בפונט שתומך בו. מחזיר רשימת תווי-גיבוי."""
    fallback_chars = [c for c in text if c not in coverage and c != " "]
    if not fallback_chars:
        draw_rtl(d, xy, text, main_font, fill, anchor, stroke_width, stroke_fill)
        return []
    # פיצול לרצפים לפי כיסוי, ציור מימין לשמאל לפי רוחב מצטבר
    runs, cur, cur_ok = [], "", None
    for ch in text:
        ok = (ch in coverage) or ch == " "
        if cur_ok is None or ok == cur_ok:
            cur += ch; cur_ok = ok
        else:
            runs.append((cur, cur_ok)); cur, cur_ok = ch, ok
    if cur:
        runs.append((cur, cur_ok))
    widths = [measure_rtl(d, t, main_font if ok else fb_font) for t, ok in runs]
    total = sum(widths)
    cx, cy = xy
    x_right = cx + total / 2.0          # anchor אופקי במרכז
    for (t, ok), w in zip(runs, widths):
        f = main_font if ok else fb_font
        d.text((x_right - w, cy), t, font=f, fill=fill, anchor="l" + anchor[1],
               direction="rtl" if RAQM else None,
               stroke_width=stroke_width, stroke_fill=stroke_fill or fill)
        x_right -= w
    return fallback_chars

def autocrop_black(img, thr=18):
    """חיתוך מסגרות שחורות (letterbox/pillarbox) שנצרבו בפריים המקור."""
    a = np.asarray(img.convert("RGB"))
    mask = a.max(2) > thr
    ys = np.where(mask.any(1))[0]
    xs = np.where(mask.any(0))[0]
    if len(ys) == 0 or len(xs) == 0:
        return img
    return img.crop((int(xs[0]), int(ys[0]), int(xs[-1])+1, int(ys[-1])+1))

def cover_crop(img, w, h):
    iw, ih = img.size
    scale = max(w/iw, h/ih)
    nw, nh = int(iw*scale+0.5), int(ih*scale+0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    x, y = (nw-w)//2, (nh-h)//2
    return img.crop((x, y, x+w, y+h))

def cover(img, w, h):
    """ממלא תמיד את יחס ה-Thumbnail (9:16) בלי מסגרות שחורות.
    מקור ~9:16 → cover-crop. מקור אחר (ריבועי/לרוחב) → blur-fill: רקע מטושטש
    שממלא את הפריים + התוכן החד במרכז. לעולם לא letterbox שחור."""
    img = autocrop_black(img)
    iw, ih = img.size
    ar, target = iw/ih, w/h
    if abs(ar - target) < 0.06:                  # כבר ~9:16
        return cover_crop(img, w, h)
    # blur-fill: רקע cover מטושטש + התוכן ממורכז (fit-width אם רחב, אחרת fit-height)
    bg = cover_crop(img, w, h).filter(ImageFilter.GaussianBlur(45))
    bg = Image.eval(bg, lambda p: int(p*0.82))   # מעט כהה כדי שהתוכן יבלוט
    if ar > target:                              # מקור רחב → fit לרוחב
        fw = w; fh = max(1, int(ih*(w/iw)+0.5)); fg = img.resize((fw, fh), Image.LANCZOS)
        bg.paste(fg, (0, (h-fh)//2))
    else:                                        # מקור צר → fit לגובה
        fh = h; fw = max(1, int(iw*(h/ih)+0.5)); fg = img.resize((fw, fh), Image.LANCZOS)
        bg.paste(fg, ((w-fw)//2, 0))
    return bg

def fit_font(draw, text, font_path, max_w, start, min_size=46):
    s = start
    while s > min_size:
        f = ImageFont.truetype(font_path, s)
        if measure_rtl(draw, text, f) <= max_w:
            return f
        s -= 2
    return ImageFont.truetype(font_path, min_size)

def line_h(font):
    a, d = font.getmetrics()
    return a + d

def build(frame_path, title, subtitle, out_path,
          band_center=BAND_CENTER_Y, title_start=TITLE_START, box_color=None, sub_ratio=None):
    # ── v9.12 (2.8.26) — שני השערים שהיו "נוהל" והפכו לקוד ────────────────
    # שורש: הכללים "מ-EXPORT נקי" ו"תמיד 2 שורות" חיו בסקיל בלבד, ולכן כל
    # קריאה ישירה יכלה להפר אותם בשקט (וכך יצא הקאבר עם "אז מה" מבצבץ).
    # הם יושבים כאן, בבונה עצמו, ולא רק במעטפת — כדי שגם קריאה ישירה
    # מסקריפט אד-הוק לא תוכל לעקוף אותם.
    if not (subtitle or "").strip():                       # G-COVER2
        raise SystemExit(
            "❌ שער G-COVER2: קאבר חייב שתי שורות — כותרת + תת-כותרת (Studentit).\n"
            "   כלל קאנון. אין בונה קאבר בשורה אחת.")
    import cover_guard as _cg                              # G-COVER1
    _cg.assert_clean_frame(frame_path)
    box_rgb = box_color or BRAND
    sub_ratio = SUB_RATIO if sub_ratio is None else sub_ratio
    bg = Image.open(frame_path).convert("RGB")
    bg = cover(bg, W, H)
    base = bg.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    max_w = W - 2*MARGIN_X
    tfont = fit_font(od, title, TITLE_FONT, max_w, title_start)
    sfont = None
    if subtitle:
        # 23.7.26 v2 — ראה הערת SUB_RATIO למעלה: תקרת גודל התת-כותרת נגזרת מהגודל
        # המתאים בפועל של הכותרת (tfont.size), לא מקבוע קבוע — כלל קדוש: כותרת תמיד
        # גדולה מתת-כותרת.
        # v9.29 (22.9.26): היה `* SUB_RATIO` — הפרמטר sub_ratio (ו---sub-ratio ב-CLI)
        # נבלע בשקט. נמצא כשהזרקת "תת-כותרת גדולה" ל-cover_vision לא הזריקה כלום.
        sub_start = max(SUB_MIN_SIZE, int(tfont.size * sub_ratio))
        # 24.7.26 — שרשרת כיסוי-תווים בת 3 שלבים (ראה הערה ליד SUB_FONT_ALLOWED):
        # Studentit → Bagira → Ploni Bold. כל שלב נבדק בנפרד; התת-כותרת כולה מצוירת
        # בפונט הראשון בשרשרת שמכסה את כל התווים שלה (לא מערבבים פונטים בתוך שורה אחת).
        # v5 26.7.26 — התת-כותרת **תמיד** Studentit. במקום להחליף את כל
        # המחרוזת בגלל תו בודד (מה שהפיל אותה ל-Ploni בכל כותרת עם גרש/ספרה),
        # רק התו הלא-נתמך נלקח מפונט הגיבוי. הכיסוי נגזר מה-cmap האמיתי.
        sub_font_path = SUB_FONT
        sub_cov = font_coverage(SUB_FONT) or SUB_FONT_ALLOWED
        sub_fb_path = (SUB_FONT_TIER2 if os.path.exists(SUB_FONT_TIER2)
                       else SUB_FONT_FALLBACK)
        fb_cov = font_coverage(sub_fb_path) or set()
        missing_all = [c for c in subtitle
                       if c not in sub_cov and c not in fb_cov and c != " "]
        if missing_all:   # אף פונט בשרשרת לא מכסה — כאן כן צריך פונט מלא
            sub_fb_path = SUB_FONT_FALLBACK
            fb_cov = font_coverage(sub_fb_path) or set()
        sfont = fit_font(od, subtitle, sub_font_path, max_w, sub_start, min_size=SUB_MIN_SIZE)

    th = line_h(tfont)
    sh = line_h(sfont) if sfont else 0
    block_h = th + (GAP + sh if sfont else 0)

    cy = int(H * band_center)
    block_top = cy - block_h//2
    band_top = block_top - PAD_Y
    band_bot = block_top + block_h + PAD_Y

    # קופסה אדומה ברוחב מלא, שקיפות 70%
    od.rectangle([0, band_top, W, band_bot], fill=box_rgb + (BAND_ALPHA,))

    # טקסט RTL (anchor mm = מרכז)
    cx = W//2
    ty = block_top + th//2
    draw_rtl(od, (cx, ty), title, tfont, WHITE, "mm")
    sub_fallback_chars = []
    if sfont:
        sy = block_top + th + GAP + sh//2
        sub_stroke = max(2, round(sfont.size * SUB_STROKE_RATIO)) if SUB_STROKE_RATIO > 0 else 0
        fbfont = ImageFont.truetype(sub_fb_path, sfont.size)
        sub_fallback_chars = draw_rtl_mixed(od, (cx, sy), subtitle, sfont, fbfont,
                                            WHITE, "mm", sub_cov,
                                            stroke_width=sub_stroke)

    out = Image.alpha_composite(base, overlay).convert("RGB")
    out.save(out_path, "PNG", quality=95)
    # ── דיווח רועש על פונטים (v5 26.7.26) ──────────────────────────────────
    # התקלה החוזרת "התת-כותרת בפונט הלא-נכון" שרדה כי הפלט מעולם לא אמר
    # באיזה פונט היא צוירה. מעכשיו הפונט מודפס תמיד, וכל תו-גיבוי מדווח
    # מפורשות — אי אפשר לפספס בלי להתעלם.
    sub_font_name = os.path.basename(sub_font_path) if sfont else "-"
    print(f"OK raqm={RAQM} title_size={tfont.size} sub_size={sfont.size if sfont else '-'} "
          f"band=({band_top},{band_bot}) -> {out_path}")
    print(f"   פונט כותרת: {os.path.basename(TITLE_FONT)}")
    print(f"   פונט תת-כותרת: {sub_font_name}")
    if sfont and not sub_font_name.startswith("Studentit"):
        print(f"   ❌ שגיאה: התת-כותרת לא צוירה ב-Studentit! (כלל מותג קשיח)")
    if sub_fallback_chars:
        print(f"   ⚠️ {len(sub_fallback_chars)} תווים נלקחו מ-{os.path.basename(sub_fb_path)} "
              f"כי Studentit לא מכיל אותם: {' '.join(sorted(set(sub_fallback_chars)))} "
              f"— האותיות עצמן נשארו Studentit")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--band-center", type=float, default=BAND_CENTER_Y)
    ap.add_argument("--title-start", type=int, default=TITLE_START)
    ap.add_argument("--box-color", default=None, help="hex צבע קופסה, למשל 0077B6 למותג האישי")
    ap.add_argument("--width", type=int, default=1080, help="רוחב קנבס (9:16=1080×1920, ריבועי=1080×1080)")
    ap.add_argument("--height", type=int, default=1920, help="גובה קנבס — חייב להתאים ליחס הסרטון! ריבועי→1080")
    ap.add_argument("--sub-ratio", type=float, default=None, help="עוקף SUB_RATIO (ברירת מחדל נעולה 0.85)")
    a = ap.parse_args()
    global W, H
    W, H = a.width, a.height
    bc = None
    if a.box_color:
        h = a.box_color.lstrip("#")
        bc = (int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))
    build(a.frame, a.title, a.subtitle or None, a.out, a.band_center, a.title_start, box_color=bc, sub_ratio=a.sub_ratio)

if __name__ == "__main__":
    main()
