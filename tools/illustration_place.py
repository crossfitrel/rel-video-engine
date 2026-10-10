#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
illustration_place — איפה ההמחשה יושבת בפריים, ולמה דווקא שם.

הראל, 21.8.26: *"שווה לוודא שזה לא מסתיר את הראש של מי שמדבר. אולי לשים את
זה במרכז. ולהוריד את הרקע השחור."*

עד כאן המיקום היה **מספר קבוע** (500×524 ב-x=290,y=0) שנמדד פעם אחת על
סרטון אחד. זה עובד בדיוק עד הסרטון הבא, שבו הדובר עומד גבוה יותר, או יושב,
או שיש שניים בפריים. מיקום נכון אינו קבוע — הוא **נגזר מהפריים עצמו**.

שלוש שכבות, מהחזקה לחלשה
------------------------
1. **פנים** — אזור אסור מוחלט. אם גלאי הפנים רץ, `IL8_face_occlusion` חוסם.
   אם הגלאי אינו זמין, השער **מדווח ואינו חוסם** — אי אפשר לחסום על סמך
   משהו שלא נמדד (עקרון 1 של הפרויקט).
2. **רצועת הכתוביות** — אזור אסור מוחלט, נגזר מהקאנון ולא מהתמונה.
3. **מפת עומס** — תנועה + אנרגיית-קצוות פר-תא. הראש והידיים הם החם ביותר
   בריל דיבור-למצלמה, ולכן זה מוצא את "האזור המת" גם בלי גלאי פנים.
   פרוקסי, ומסומן ככזה בדוח.

שובר-שוויון: **מרכוז אופקי**, ואז שטח גדול יותר. שני מיקומים באותו עומס —
המרכז מנצח, כי הוא נראה מכוון ולא כמו משהו שנדחף לפינה.

הרקע
----
`alpha_from_backdrop` מוציא את הרקע השחור של האיור ומשאיר את האנטומיה
צפה מעל הווידאו, עם הילה כהה רכה שמחזיקה ניגודיות גם על רקע בהיר.

שימוש
-----
  python3 illustration_place.py --video FINAL.mp4 --from 22.6 --to 28.6 \\
      --card-aspect 0.954 --json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

# רצועת הכתוביות — מהקאנון (תחתון-מרכז, 1080×1920). לא נמדד מהתמונה בכוונה:
# הכתוביות נצרבות אחרי המיקום, ולכן מדידה שלהן כאן היא מדידה של העבר.
CAPTION_BAND = (0.66, 1.00)      # שבר מגובה הפריים
HEAD_PAD = 0.035                 # מרווח סביב קופסת הפנים, שבר מגובה הפריים
MIN_CARD_W = 0.40                # רוחב קלף מינימלי, שבר מרוחב הפריים
MAX_CARD_W = 0.72
# רוחבי מועמד. הקטנים נכנסו ב-21.8.26 כדי ש**מרכוז** יהיה בכלל אפשרי: כשהדובר
# עומד גבוה בפריים, קלף רחב לא יכול להיות גם ממורכז וגם לא לגעת בראש, והפותר
# נאלץ לדחוף אותו לפינה. עדיף קלף קטן במרכז מקלף גדול בפינה.
CARD_WIDTHS = (0.72, 0.64, 0.56, 0.48, 0.42, 0.38, 0.34, 0.30)
CENTRE_WEIGHT = 0.85      # כמה שווה מרכוז מול עומס. הראל 21.8.26: "אולי במרכז"

# ── הרצועה המועדפת: **מתחת לראש, מעל הכתוביות** (הראל 21.8.26) ──────────
# זו רצועת הגוף. שלוש סיבות שהיא מנצחת את הרצועה שמעל הראש:
#   • היא בקו המבט. העין כבר על הפנים, וההמחשה נופלת לשדה הראייה בלי קפיצה.
#   • היא גבוהה יותר — פי שניים מהמקום שמעל הראש בפריים אנכי טיפוסי — ולכן
#     הקלף שנכנס בה גדול יותר וקריא יותר.
#   • מעל הראש יש בדרך כלל תקרה, שילוט ודגלונים; שם ההמחשה נראית כמו באנר
#     שהודבק על הסרטון, לא כמו חלק ממנו.
# **העדפה, לא חוק** — הראל אמר "אולי". רצועה צרה מדי או עמוסה מדי ⇒ הפותר
# חוזר למקום הטוב הבא ומדווח למה.
BAND_BONUS = 0.42         # כמה שווה לשבת ברצועה המועדפת
BAND_MIN_H = 0.16         # רצועה נמוכה מזה אינה מכילה קלף קריא
DEFAULT_FACE_BOTTOM = 0.42  # כשאין מדידת פנים — הערכה, ומסומנת ככזו
GRID = 28                        # רזולוציית מפת העומס


def sample_frames(video, t0, t1, n=8):
    """דגימת פריימים אמיתיים מהחלון. אין ניחוש על סמך 'איפה דוברים בדרך כלל'."""
    import numpy as np
    from PIL import Image
    out = []
    with tempfile.TemporaryDirectory() as d:
        for i in range(n):
            t = t0 + (t1 - t0) * (i / max(1, n - 1))
            p = Path(d) / f"{i:03d}.png"
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-ss", f"{t:.3f}",
                            "-i", str(video), "-frames:v", "1",
                            "-vf", "scale=360:-1", str(p), "-loglevel", "error"],
                           check=False)
            if p.exists():
                out.append(np.asarray(Image.open(p).convert("L")).astype("float32"))
    return out


def face_boxes(video, t0, t1, n=8):
    """קופסאות פנים מנורמלות (0..1). מחזיר (boxes, method).

    `method == "unavailable"` אינו "אין פנים" — הוא **לא נמדד**, וזה הבדל
    שקובע אם IL8 חוסם או מדווח. OpenCV 5 הפסיק לארוז את קבצי ה-Haar, ולכן
    המצב הזה נפוץ יותר ממה שנדמה."""
    try:
        import cv2
    except Exception:
        return None, "unavailable:no-cv2"
    hc = getattr(getattr(cv2, "data", None), "haarcascades", "") or ""
    xml = Path(hc) / "haarcascade_frontalface_default.xml"
    if not xml.exists():
        return None, "unavailable:no-cascade"
    casc = cv2.CascadeClassifier(str(xml))
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return None, "unavailable:no-video"
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    per_frame, raw = [], 0
    for i in range(n):
        t = t0 + (t1 - t0) * (i / max(1, n - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, fr = cap.read()
        if not ok or fr is None:
            continue
        h, w = fr.shape[:2]
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        per_frame.append([[float(x) / w, float(y) / h,
                           float(x + fw) / w, float(y + fh) / h]
                          for (x, y, fw, fh) in
                          casc.detectMultiScale(g, 1.15, 5, minSize=(60, 60))])
        raw += len(per_frame[-1])
    cap.release()
    boxes = _persistent_faces(per_frame)
    return boxes, f"haar:{len(boxes)}/{raw}"


def _persistent_faces(per_frame, radius=0.12, keep_ratio=0.6):
    """Haar מחזיר גם חיוביים-שגויים, ובסרטון של מאסל מן הוא מצא "פנים" על
    **חליפת השרירים המודפסת** — אשכול שלם על החזה, בגודל דומה לפנים
    האמיתיות. אשכול כזה מחק את כל רצועת הגוף כאזור אסור ודחף את ההמחשה
    בחזרה מעל הראש (21.8.26).

    שטח לבדו אינו מבדיל בין השניים — הם באותו סדר גודל. מה שכן מבדיל:
    **התמדה**. הפנים של הדובר נמצאות כמעט בכל פריים שנדגם ובאותו מקום;
    ההדפס על החולצה מופיע לסירוגין. לכן מאשכלים לפי מרכז, ומדרגים כל אשכול
    ב-(שיעור הפריימים שבהם נראה) × (שטח ממוצע). מי שנופל מתחת ל-60%
    מהמוביל — לא פנים. מדווחים כמה נשמרו מתוך כמה נמצאו."""
    flat = [(i, b) for i, fr in enumerate(per_frame) for b in fr]
    if not flat:
        return []
    clusters: list[dict] = []
    for i, b in flat:
        c = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        for cl in clusters:
            if abs(c[0] - cl["c"][0]) < radius and abs(c[1] - cl["c"][1]) < radius:
                cl["boxes"].append(b); cl["frames"].add(i)
                k = len(cl["boxes"])
                cl["c"] = ((cl["c"][0] * (k - 1) + c[0]) / k,
                           (cl["c"][1] * (k - 1) + c[1]) / k)
                break
        else:
            clusters.append({"c": c, "boxes": [b], "frames": {i}})
    n = max(1, len(per_frame))
    for cl in clusters:
        area = sum((b[2] - b[0]) * (b[3] - b[1]) for b in cl["boxes"]) / len(cl["boxes"])
        cl["score"] = (len(cl["frames"]) / n) * area
    best = max(cl["score"] for cl in clusters)
    return [b for cl in clusters if cl["score"] >= keep_ratio * best for b in cl["boxes"]]


def busy_map(frames, grid=GRID):
    """כמה 'קורה' בכל תא: תנועה בין פריימים + אנרגיית קצוות. פרוקסי לראש
    ולידיים, ומסומן ככזה — הוא לא יודע מה הוא רואה."""
    import numpy as np
    if not frames:
        return None
    h, w = frames[0].shape
    acc = np.zeros((grid, grid), dtype="float32")
    ys = np.linspace(0, h, grid + 1).astype(int)
    xs = np.linspace(0, w, grid + 1).astype(int)

    def cells(m):
        return np.array([[m[ys[r]:ys[r + 1], xs[c]:xs[c + 1]].mean()
                          for c in range(grid)] for r in range(grid)], dtype="float32")

    for a, b in zip(frames, frames[1:]):
        acc += cells(np.abs(a - b))
    gy, gx = np.gradient(frames[len(frames) // 2])
    acc += 0.6 * cells(np.abs(gy) + np.abs(gx))
    if acc.max() > 0:
        acc /= acc.max()
    return acc


def _overlap(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


def solve_placement(faces, busy, card_aspect, frame_w=1080, frame_h=1920,
                    caption_band=CAPTION_BAND):
    """מחזיר מיקום מנורמל + ניקוד מפורק. שובר-שוויון: מרכוז אופקי, ואז שטח."""
    import numpy as np
    band = [0.0, caption_band[0], 1.0, caption_band[1]]
    forbidden = [band]
    for f in (faces or []):
        forbidden.append([max(0.0, f[0] - HEAD_PAD), max(0.0, f[1] - HEAD_PAD),
                          min(1.0, f[2] + HEAD_PAD), min(1.0, f[3] + HEAD_PAD)])

    # הרצועה המועדפת: מסוף קופסת הפנים הנמוכה ביותר ועד ראש רצועת הכתוביות.
    if faces:
        face_bottom = max(f[3] for f in faces)
        band_src = "measured"
    else:
        face_bottom = DEFAULT_FACE_BOTTOM
        band_src = "assumed"
    band_top = min(0.95, face_bottom + HEAD_PAD)
    band_bot = caption_band[0]
    band_ok = (band_bot - band_top) >= BAND_MIN_H
    pref = [0.0, band_top, 1.0, band_bot]

    best = None
    for wf in CARD_WIDTHS:
        cw = wf
        ch = cw * frame_w / card_aspect / frame_h          # שמירת יחס הקלף
        if ch >= 0.95:
            continue
        for cx in np.linspace(0.0, 1.0 - cw, 21):
            for cy in np.linspace(0.0, 1.0 - ch, 29):
                box = [cx, cy, cx + cw, cy + ch]
                hard = sum(_overlap(box, f) for f in forbidden)
                if hard > 1e-6:
                    continue
                if busy is not None:
                    g = busy.shape[0]
                    r0, r1 = int(cy * g), max(int(cy * g) + 1, int((cy + ch) * g))
                    c0, c1 = int(cx * g), max(int(cx * g) + 1, int((cx + cw) * g))
                    cost = float(busy[r0:r1, c0:c1].mean())
                else:
                    cost = 0.0
                centred = abs((cx + cw / 2) - 0.5)
                # ברצועה המועדפת = הקלף **כולו** בתוכה, לא רק נוגע בה.
                in_band = bool(band_ok and cy >= band_top - 1e-6
                               and cy + ch <= band_bot + 1e-6)
                score = (cost + CENTRE_WEIGHT * centred - 0.22 * cw
                         - (BAND_BONUS if in_band else 0.0))
                if best is None or score < best["score"]:
                    best = {"score": round(score, 5), "busy_cost": round(cost, 4),
                            "off_centre": round(centred, 4), "w_frac": round(cw, 4),
                            "in_preferred_band": in_band,
                            "box": [round(v, 4) for v in box]}
    if best is None:
        return {"ok": False, "why": "אין מיקום שאינו נוגע בפנים או ברצועת הכתוביות "
                                    "— ההמחשה יורדת. כיסוי פנים אינו פשרה"}
    best["band"] = {"top": round(band_top, 4), "bottom": round(band_bot, 4),
                    "height": round(band_bot - band_top, 4),
                    "usable": band_ok, "face_bottom_source": band_src,
                    "why_not": None if best["in_preferred_band"] else
                               ("הרצועה נמוכה מ-%.2f ולכן אינה מכילה קלף קריא"
                                % BAND_MIN_H if not band_ok else
                                "נמצא מיקום טוב יותר מחוץ לרצועה")}
    x0, y0, x1, y1 = best["box"]
    px = {"x": int(round(x0 * frame_w)), "y": int(round(y0 * frame_h)),
          "w": int(round((x1 - x0) * frame_w)), "h": int(round((y1 - y0) * frame_h))}
    px["w"] -= px["w"] % 2
    px["h"] -= px["h"] % 2
    return {"ok": True, **best, "px": px}


def occlusion_check(place, faces, method):
    """IL8. חוסם רק כשנמדד — אחרת מדווח, ומסמן שהמידע חסר."""
    if not place.get("ok"):
        return {"ok": False, "gate": "IL8_face_occlusion", "measured": bool(faces),
                "detail": place.get("why", "אין מיקום חוקי")}
    if faces is None:
        return {"ok": True, "gate": "IL8_face_occlusion", "measured": False,
                "detail": f"גלאי הפנים אינו זמין ({method}) — המיקום נבחר לפי מפת "
                          "עומס בלבד. מדווח, לא חוסם: אי אפשר לחסום על מה שלא נמדד"}
    ov = float(max([_overlap(place["box"], f) for f in faces], default=0.0))
    return {"ok": bool(ov <= 1e-6), "gate": "IL8_face_occlusion", "measured": True,
            "detail": (f"{len(faces)} קופסאות פנים נמדדו · חפיפה {ov:.5f}"
                       if ov <= 1e-6 else
                       f"הקלף מכסה פנים (חפיפה {ov:.4f}) — פסול")}


def alpha_from_backdrop(img_rgb, bg=(0x14, 0x10, 0x11), tol=42, feather=2.5,
                        halo=14, halo_strength=0.55):
    """מוציא את הרקע של האיור ומשאיר את האנטומיה צפה מעל הווידאו.

    הראל 21.8.26: *"ולהוריד את הרקע השחור."* קופסה שחורה על הפריים היא
    כרזה; אנטומיה שצפה מעל הרחבה היא חלק מהסרטון. ההילה הכהה הרכה נשארת —
    בלעדיה האיור נבלע ברגע שהרקע מאחוריו בהיר."""
    import numpy as np
    from PIL import Image, ImageFilter
    a = np.asarray(img_rgb.convert("RGB")).astype("float32")
    d = np.sqrt(((a - np.array(bg, dtype="float32")) ** 2).sum(axis=2))
    al = np.clip((d - tol) / max(1.0, tol * feather), 0, 1)
    alpha = Image.fromarray((al * 255).astype("uint8")).filter(
        ImageFilter.GaussianBlur(1.2))
    out = img_rgb.convert("RGBA")
    out.putalpha(alpha)
    if halo:
        glow = alpha.filter(ImageFilter.GaussianBlur(halo)).point(
            lambda v: int(v * halo_strength))
        shadow = Image.new("RGBA", out.size, (0, 0, 0, 0))
        shadow.putalpha(glow)
        out = Image.alpha_composite(shadow, out)
    return out


def plan(video, t0, t1, card_aspect=0.954, frames=8) -> dict:
    faces, method = face_boxes(video, t0, t1, frames)
    busy = busy_map(sample_frames(video, t0, t1, frames))
    place = solve_placement(faces, busy, card_aspect)
    gate = occlusion_check(place, faces, method)
    return {"video": str(video), "window": [t0, t1], "card_aspect": card_aspect,
            "face_method": method, "n_faces": (len(faces) if faces is not None else None),
            "busy_measured": busy is not None,
            "placement": place, "gate": gate}


def main() -> int:
    ap = argparse.ArgumentParser(description="איפה ההמחשה יושבת בפריים")
    ap.add_argument("--video", required=True)
    ap.add_argument("--from", dest="t0", type=float, required=True)
    ap.add_argument("--to", dest="t1", type=float, required=True)
    ap.add_argument("--card-aspect", type=float, default=0.954)
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    d = plan(a.video, a.t0, a.t1, a.card_aspect, a.frames)
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 0
    p = d["placement"]
    print(f"■ מיקום {'✓' if p.get('ok') else '✗'}")
    if p.get("ok"):
        b = p.get("band", {})
        print(f"  {p['px']['w']}x{p['px']['h']} ב-({p['px']['x']},{p['px']['y']}) · "
              f"עומס {p['busy_cost']} · סטייה מהמרכז {p['off_centre']}")
        print(f"  רצועה מועדפת (מתחת לראש, מעל הכתוביות) "
              f"{b.get('top')}-{b.get('bottom')} · "
              f"{'✓ בתוכה' if p.get('in_preferred_band') else '✗ ' + str(b.get('why_not'))}")
    print(f"  פנים: {d['face_method']} ({d['n_faces']})")
    print(f"  {'✓' if d['gate']['ok'] else '✗'} {d['gate']['gate']} — {d['gate']['detail']}")
    return 0 if d["gate"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
