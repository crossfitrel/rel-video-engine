#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
illustration_build — מהאיור אל הקלף: מסכות, אימות, קומפוזיציה, רינדור, הרכבה.

`illustration_gate` מחליט **אם ואיפה**. הכלי הזה מבצע. הוא מקומי לחלוטין,
דטרמיניסטי, ועולה אפס: האיורים נוצרים ב-Gemini (Nano Banana) דרך הדפדפן
לפי `rel-chatgpt-graphics`, וכל השאר קורה כאן.

הצינור
------
  1. `segment`  — חילוץ אזורי השריר מהאיור עצמו לפי צבע. המסכה **נגזרת
                  מהאיור**, ולכן היא בהכרח ברישום מושלם מולו.
  2. `regions`  — מיפוי ישות→אזור + **תמונת בדיקה**. זה IL5, והוא נכשל-סגור:
                  בלי אימות אין המחשה (L46, הראל 21.8.26).
  3. `compose`  — קומפוזיציה בפורמט HyperFrames (HTML + טיימליין GSAP מושהה),
                  כשכל תמונה ומסכה **מוטמעות base64 inline**.
  4. `render`   — Chrome headless דוגם את הטיימליין פריים-פריים.
  5. `card`     — פריימים עם אלפא ופינות מעוגלות → overlay על ה-EXPORT הנקי.

שתי מלכודות שעלו ב-21.8.26 ונצרבו כלקח L48
------------------------------------------
  • **`mask-image` מ-`file://` נחסם ב-Chrome** (ERR_FAILED) והשכבה נעלמת
    בשקט — הפריים שחור, ה-DOM וה-computed style נראים תקינים לחלוטין.
    לכן כל נכס מוטמע `data:image/png;base64` / `data:image/jpeg;base64`.
  • **סקריפט הרנטיים של HyperFrames מרוקן את הקומפוזיציה ברינדור מקומי.**
    `hyperframe.runtime` מוסר לפני הרינדור; הקומפוזיציה עצמה נשארת תקפה
    לענן, שם הרנטיים דווקא נדרש.

שימוש
-----
  python3 illustration_build.py segment  --base A.png --out W/illus
  python3 illustration_build.py regions  --workdir W --map '{"אינפרספינטוס":"infra"}'
  python3 illustration_build.py compose  --workdir W --cues cues.json
  python3 illustration_build.py render   --workdir W
  python3 illustration_build.py card     --workdir W --base FINAL.mp4 --at 22.6
"""
from __future__ import annotations

import argparse
import base64
import os
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME = os.environ.get("CHROME_PATH") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"  # ענן: CHROME_PATH מ-cloud/env.sh

CARD_W, CARD_H = 1040, 1090      # קנבס הקומפוזיציה (2x גודל הקלף על המסך)
FPS = 30


def jload(p, d=None):
    p = Path(p)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return d


def jdump(p, o):
    Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
# 1. סגמנטציה — האזורים נגזרים מהאיור, לא מצוירים עליו
# ═══════════════════════════════════════════════════════════════════════
def segment(base_png: Path, outdir: Path) -> dict:
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    outdir.mkdir(parents=True, exist_ok=True)
    im = Image.open(base_png).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    sat = a.max(axis=2) - a.min(axis=2)
    muscle = (R > G + 22) & (R > B + 22) & (R > 70) & (sat > 28)
    muscle = ndimage.binary_opening(muscle, np.ones((5, 5)))
    muscle = ndimage.binary_closing(muscle, np.ones((9, 9)))
    muscle = ndimage.binary_fill_holes(muscle)
    lab, n = ndimage.label(muscle)
    sizes = ndimage.sum(muscle, lab, range(1, n + 1))
    comps = []
    for i in np.argsort(sizes)[::-1]:
        if sizes[i] < 3000:
            continue
        cid = int(i) + 1
        ys, xs = np.where(lab == cid)
        comps.append({"id": cid, "px": int(sizes[i]),
                      "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]})
    np.save(outdir / "labels.npy", lab.astype(np.int32))
    doc = {"source": str(base_png), "size": list(im.size), "components": comps}
    jdump(outdir / "segment.json", doc)
    print(f"[segment] {len(comps)} אזורים · {im.size[0]}x{im.size[1]}")
    for c in comps:
        print(f"   id={c['id']}  px={c['px']}  bbox={c['bbox']}")
    return doc


def _mask_png(arr, path, crop, out_size, blur=2.0):
    """מסכה נשמרת RGBA (לבן + אלפא). CSS ממסך לפי **אלפא** — מסכה בגווני
    אפור בלבד מתפרשת כאטומה לגמרי, וזה כשל שקט."""
    import numpy as np
    from PIL import Image, ImageFilter
    m = Image.fromarray((np.asarray(arr) * 255).astype("uint8"))
    m = m.crop(crop).resize(out_size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(blur))
    w = Image.new("RGBA", out_size, (255, 255, 255, 0))
    w.putalpha(m.convert("L"))
    w.save(path)


def _hue_sat_val(rgb01):
    import numpy as np
    mx = rgb01.max(axis=2); mn = rgb01.min(axis=2)
    d = mx - mn + 1e-6
    r, g, b = rgb01[..., 0], rgb01[..., 1], rgb01[..., 2]
    h = np.zeros_like(mx)
    m = (mx == r); h[m] = ((g - b)[m] / d[m]) % 6
    m = (mx == g); h[m] = ((b - r)[m] / d[m]) + 2
    m = (mx == b); h[m] = ((r - g)[m] / d[m]) + 4
    return (h * 60.0) % 360.0, np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0), mx


def _muscle_mask(rgb_i16):
    import numpy as np
    from scipy import ndimage
    R, G, B = rgb_i16[..., 0], rgb_i16[..., 1], rgb_i16[..., 2]
    sat = rgb_i16.max(axis=2) - rgb_i16.min(axis=2)
    m = (R > G + 22) & (R > B + 22) & (R > 70) & (sat > 28)
    return ndimage.binary_fill_holes(ndimage.binary_closing(m, np.ones((9, 9))))


DEFAULT_BANDS = {"supra": (200, 280), "infra": (75, 175), "teres": (35, 70)}


def masks_from_atlas(outdir: Path, atlas_png: Path, base_png: Path, crop,
                     bands: dict | None = None) -> dict:
    """**השיטה המועדפת.** במקום לנחש קו-תפר בין שני שרירים סמוכים שנוגעים
    בצבע, מבקשים מהמאייר לצבוע כל שריר בגוון רווי אחר — ואז ההפרדה היא
    שאלה של צבע, לא של קריאת גריד בעין.

    הראל, 21.8.26: *"ה-Teres Minor לא מדויק בגיליון."* השורש: קו התפר סומן
    ידנית אחרי ששלוש שיטות אוטומטיות נכשלו (ארוזיה מורפולוגית · חיתוך לפי
    בהירות · חיתוך לפי רצועת הגיד החיוורת) — כי השרירים **באמת** נוגעים
    בצבע באיור, ולכן לא קיים בו חתך שניתן למצוא. הפתרון אינו אלגוריתם טוב
    יותר; הוא **לבקש קלט שניתן להפריד**.

    `atlas` הוא רינדור נוסף של אותה קומפוזיציה עם צבעי-מפתח. הוא משמש
    **למסכות בלבד** — הלוח שמוצג לצופה נשאר האיור היפה. לכן חובה למדוד את
    ההתלכדות בין השניים (`registration.iou`); אטלס שאינו מיושר מייצר מסכות
    שנראות סבירות ומאירות את המקום הלא-נכון.
    """
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    bands = bands or DEFAULT_BANDS
    at = np.asarray(Image.open(atlas_png).convert("RGB")).astype(np.float32) / 255.0
    base = np.asarray(Image.open(base_png).convert("RGB")).astype(np.int16)
    if at.shape[:2] != base.shape[:2]:
        raise SystemExit("אטלס ובסיס בגדלים שונים — אי אפשר למפות מסכות")
    hue, sat, val = _hue_sat_val(at)
    colored = (sat > 0.35) & (val > 0.18)
    built, sizes = {}, {}
    for name, (lo, hi) in bands.items():
        m = colored & (hue >= lo) & (hue <= hi)
        m = ndimage.binary_closing(ndimage.binary_opening(m, np.ones((5, 5))), np.ones((9, 9)))
        m = ndimage.binary_fill_holes(m)
        l, n = ndimage.label(m)
        if n:
            sz = ndimage.sum(m, l, range(1, n + 1))
            m = l == (int(np.argmax(sz)) + 1)
        built[name] = m
        sizes[name] = int(m.sum())
        _mask_png(m, outdir / f"mask_{name}.png", crop, (CARD_W, CARD_H))

    allm = np.zeros_like(next(iter(built.values())))
    for m in built.values():
        allm |= m
    bm = _muscle_mask(base)
    iou = float((bm & allm).sum()) / float(max(1, (bm | allm).sum()))
    doc = {"sizes": sizes, "bands": {k: list(v) for k, v in bands.items()},
           "registration": {"iou": round(iou, 4), "threshold": 0.85,
                            "ok": iou >= 0.85,
                            "note": "סף לא-מדוד (מדידה אחת). מדווח; IL5 הוא "
                                    "החוסם — הגיליון מראה חוסר-יישור לעין"}}
    jdump(outdir / "atlas_report.json", doc)
    print(f"[atlas] {', '.join(f'{k}={v}' for k, v in sizes.items())} · "
          f"רישום IoU={iou:.4f} {'✓' if iou >= 0.85 else '✗'}")
    return doc


def masks(outdir: Path, crop, assign: dict, seam: dict | None = None) -> dict:
    """מסלול נסיגה: הקצאת רכיבים ידנית + קו-תפר שנקרא מגריד. עובד, אבל
    התפר הוא **הנקודה שבה טעות מתגנבת** (הראל 21.8.26). מעדיפים `atlas`."""
    """assign: {"infra": [id,...], "supra": [id,...]}. seam (אופציונלי):
    {"from": "infra", "to": "teres", "polyline": [[x,y],...], "x_min": 520}
    — פיצול שני שרירים סמוכים שנוגעים בצבע. **התפר הוא הנקודה שבה טעות
    מתגנבת**, ולכן הוא חייב לעבור `regions` (IL5) לפני שמישהו מרנדר."""
    import numpy as np
    lab = np.load(outdir / "labels.npy")
    H, W = lab.shape
    yy, xx = np.mgrid[0:H, 0:W]
    built = {}
    for name, ids in assign.items():
        built[name] = np.isin(lab, list(ids))
    if seam:
        src, dst = seam["from"], seam["to"]
        pl = seam["polyline"]
        sy = np.interp(np.arange(W), [p[0] for p in pl], [p[1] for p in pl])
        below = built[src] & (yy > sy[None, :]) & (xx > float(seam.get("x_min", 0)))
        built[dst] = below
        built[src] = built[src] & ~below
    for name, arr in built.items():
        _mask_png(arr, outdir / f"mask_{name}.png", crop, (CARD_W, CARD_H))
    print(f"[masks] {', '.join(built)}")
    return {k: int(v.sum()) for k, v in built.items()}


# ═══════════════════════════════════════════════════════════════════════
# 2. אימות ישות→אזור — IL5 / L46
# ═══════════════════════════════════════════════════════════════════════
CHECK_COLORS = [(90, 200, 255), (255, 90, 90), (255, 220, 70),
                (150, 255, 150), (220, 130, 255)]


def regions(workdir: Path, illus: Path, mapping: dict, plates: dict) -> dict:
    """מייצר `illustration_regions.json` + `illustration_check.png` — כל אזור
    צבוע בצבע אחר **על הלוח שאליו הוא שייך**, כדי שאפשר יהיה לראות שהשם
    והאזור תואמים.

    mapping: {"אינפרספינטוס": "infra"} או {"סאבסקפולריס": {"region":"sub","plate":"ant"}}
    plates:  {"post": "base_crop.jpg", "ant": "ant_crop.jpg"}

    **הלוח הוא חלק מהאימות, לא פרט טכני.** הגרסה הראשונה צבעה את מסכת
    הסאבסקפולריס (שנגזרה מהאיור הקדמי) על גבי הלוח האחורי, והתמונה נראתה
    שגויה — הגיליון תפס את זה בריצה הראשונה, וזה בדיוק מה שהוא נועד לעשות.

    `verified` נשאר False עד שמישהו (קלאוד או הראל) הסתכל ואישר. השער
    נכשל-סגור, כי בדיוק כאן נפלה הטעות שהראל דיווח עליה ב-21.8.26."""
    from PIL import Image
    bases = {k: Image.open(illus / v).convert("RGB") for k, v in plates.items()}
    sheets = {k: v.copy() for k, v in bases.items()}
    recs = []
    for i, (entity, spec) in enumerate(mapping.items()):
        region = spec if isinstance(spec, str) else spec.get("region")
        plate = "post" if isinstance(spec, str) else spec.get("plate", "post")
        mp = illus / f"mask_{region}.png"
        if not mp.exists() or plate not in sheets:
            recs.append({"entity": entity, "region": region, "plate": plate,
                         "verified": False,
                         "note": "אין קובץ מסכה" if not mp.exists() else "אין לוח כזה"})
            continue
        m = Image.open(mp).convert("RGBA").getchannel("A")
        col = CHECK_COLORS[i % len(CHECK_COLORS)]
        sheets[plate] = Image.composite(
            Image.blend(sheets[plate], Image.new("RGB", bases[plate].size, col), 0.55),
            sheets[plate], m)
        recs.append({"entity": entity, "region": region, "plate": plate,
                     "verified": False, "check_color": list(col)})

    order = [k for k in ("post", "ant") if k in sheets] + \
            [k for k in sheets if k not in ("post", "ant")]
    w = sum(sheets[k].width for k in order)
    h = max(sheets[k].height for k in order)
    combined = Image.new("RGB", (w, h), (20, 16, 17))
    x = 0
    for k in order:
        combined.paste(sheets[k], (x, 0))
        x += sheets[k].width
    sheet = "illustration_check.png"
    combined.save(Path(workdir) / sheet)
    doc = {"regions": recs, "check_sheet": sheet, "plates": order,
           "how_to_verify": "לפתוח את illustration_check.png (לוח לכל תצוגה, "
                            "משמאל לימין: " + ", ".join(order) + "), לוודא שכל "
                            "ישות צבועה באזור הנכון **בלוח הנכון**, ואז "
                            "verified=true לכל רשומה. IL5 חוסם עד אז."}
    jdump(Path(workdir) / "illustration_regions.json", doc)
    print(f"[regions] {len(recs)} ישויות · {len(order)} לוחות · תמונת בדיקה: "
          f"{sheet} · verified=false (חסום עד אימות)")
    return doc


# ═══════════════════════════════════════════════════════════════════════
# 3. קומפוזיציה — HyperFrames contract, הכל inline
# ═══════════════════════════════════════════════════════════════════════
def _b64(p: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(Path(p).read_bytes()).decode()


def compose(workdir: Path, illus: Path, cues: list[dict], dur: float,
            plates: dict) -> Path:
    """cues: [{"region":"infra","on":1.30,"off":2.72,"plate":"post"}, ...]
    plates: {"post": "base_crop.jpg", "ant": "ant_crop.jpg"} (ant אופציונלי)."""
    tpl = (HERE / "illustration" / "composition.tpl.html").read_text(encoding="utf-8")
    css_plates, css_masks, dom, js = [], [], [], []
    for key, fn in plates.items():
        css_plates.append(f"      --plate-{key}: url({_b64(illus / fn, 'image/jpeg')});")
    used = sorted({c["region"] for c in cues})
    for r in used:
        u = _b64(illus / f"mask_{r}.png", "image/png")
        css_masks.append(
            f"      #hl-{r}, #gl-{r} {{ -webkit-mask-image:url({u}); mask-image:url({u}); }}")
    for key in plates:
        layers = "".join(
            f'<div class="hl" id="hl-{c["region"]}"><div class="plate p-{key}"></div>'
            f'<div class="tint"></div><div class="lift"></div></div>'
            f'<div class="glow" id="gl-{c["region"]}"></div>'
            for c in cues if c.get("plate", "post") == key)
        dom.append(f'<div class="face" id="face-{key}"'
                   f'{"" if key == "post" else " style=\"opacity:0;\""}>'
                   f'<div id="fx-{key}" class="plate p-{key}"></div>{layers}</div>')
    for c in cues:
        js.append("      light(%r, %r, %.3f, %.3f);" %
                  (c["region"], c.get("plate", "post"), float(c["on"]), float(c["off"])))
    out = (tpl.replace("/*PLATES*/", "\n".join(css_plates))
              .replace("/*MASKS*/", "\n".join(css_masks))
              .replace("<!--DOM-->", "\n            ".join(dom))
              .replace("/*CUES*/", "\n".join(js))
              .replace("__DUR__", f"{dur:.3f}")
              .replace("__W__", str(CARD_W)).replace("__H__", str(CARD_H)))
    p = Path(workdir) / "illustration.html"
    p.write_text(out, encoding="utf-8")
    print(f"[compose] {p.name} · {len(out)} bytes · {len(cues)} רמזים · {dur:.2f}ש")
    return p


# ═══════════════════════════════════════════════════════════════════════
# 4. רינדור מקומי
# ═══════════════════════════════════════════════════════════════════════
def render(workdir: Path, html: Path | None = None, fps: int = FPS) -> Path:
    """מסיר את סקריפט `hyperframe.runtime` (הוא מרוקן את הקומפוזיציה מקומית),
    ואז Chrome headless דוגם את הטיימליין המושהה פריים-פריים."""
    W = Path(workdir)
    html = Path(html or (W / "illustration.html"))
    src = html.read_text(encoding="utf-8")
    local = W / "illustration.local.html"
    local.write_text(
        "\n".join(l for l in src.splitlines() if "hyperframe.runtime" not in l),
        encoding="utf-8")
    frames = W / "illus_frames"
    js = HERE / "illustration" / "render_frames.js"
    # cwd = תיקיית הכלי, כדי ש-node ימצא את puppeteer-core שמותקן שם ולא
    # יהיה תלוי ב-NODE_PATH של מי שהריץ.
    subprocess.run(["node", str(js), str(local), str(frames), str(fps)],
                   check=True, cwd=str(HERE / "illustration"))
    print(f"[render] {len(list(frames.glob('*.png')))} פריימים → {frames}")
    return frames


# ═══════════════════════════════════════════════════════════════════════
# 5. קלף + הרכבה
# ═══════════════════════════════════════════════════════════════════════
def card(workdir: Path, base_video: Path, at: float, w=None, h=None, x=None, y=None,
         radius=26, out: Path | None = None, transparent: bool = True) -> Path:
    """הרכבת הקלף על הסרטון.

    שני שינויים מ-21.8.26, שניהם מהראל:
      • *"שווה לוודא שזה לא מסתיר את הראש של מי שמדבר. אולי לשים את זה
        במרכז."* → המיקום **נפתר מהפריים** (`illustration_place`) ולא מוזן
        כמספר קבוע. מספר קבוע נכון בדיוק לסרטון אחד.
      • *"ולהוריד את הרקע השחור."* → ברירת המחדל `transparent=True`: הרקע
        של האיור מוסר, האנטומיה צפה מעל הרחבה, ונשארת הילה כהה רכה כדי
        שהאיור לא ייבלע על רקע בהיר.
    """
    from PIL import Image, ImageDraw
    W = Path(workdir)
    frames = sorted((W / "illus_frames").glob("*.png"))
    if not frames:
        raise SystemExit("אין פריימים — להריץ render קודם")
    n, fi = len(frames), 9

    place = None
    if None in (w, h, x, y):
        import illustration_place as IP
        src = Image.open(frames[0])
        place = IP.plan(base_video, at, at + n / FPS, src.width / src.height)
        if not place["gate"]["ok"]:
            raise SystemExit("IL8_face_occlusion — " + place["gate"]["detail"])
        px = place["placement"]["px"]
        w, h, x, y = px["w"], px["h"], px["x"], px["y"]
        jdump(W / "illustration_placement.json", place)
        band = "ברצועה המועדפת" if place["placement"].get("in_preferred_band") \
            else "מחוץ לרצועה: " + str(place["placement"]["band"].get("why_not"))
        print(f"[place] {w}x{h}@({x},{y}) · {band} · {place['gate']['detail']}")

    # ההילה מסתגלת לרקע. איור צף מעל רחבה ריקה צריך כמעט כלום; אותו איור מעל
    # חליפת שרירים מודפסת מתחרה בדפוס שמאחוריו ונבלע. `busy_cost` כבר נמדד
    # בפותר המיקום, אז אין כאן ניחוש — רק שימוש במה שנמדד.
    halo_s = 0.55
    if place is not None:
        halo_s = min(0.88, 0.45 + 0.9 * float(place["placement"].get("busy_cost", 0)))

    dst = W / "illus_card"
    dst.mkdir(exist_ok=True)
    rr = Image.new("L", (w, h), 0)
    ImageDraw.Draw(rr).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    for i, f in enumerate(frames):
        src = Image.open(f)
        if transparent:
            import illustration_place as IP
            im = IP.alpha_from_backdrop(src, halo=18, halo_strength=halo_s) \
                   .resize((w, h), Image.LANCZOS)
            base_a = im.getchannel("A")
        else:
            im = src.convert("RGB").resize((w, h), Image.LANCZOS)
            im.putalpha(rr)
            base_a = rr
        k = (i + 1) / fi if i < fi else ((n - i) / fi if i >= n - fi else 1.0)
        if k < 1.0:
            im.putalpha(base_a.point(lambda v, k=k: int(v * k)))
        im.save(dst / ("%05d.png" % i))
    mov = W / "illus_card.mov"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-framerate", str(FPS),
                    "-i", str(dst / "%05d.png"), "-c:v", "qtrle", str(mov),
                    "-loglevel", "error"], check=True)
    end = at + n / FPS
    out = Path(out or (W / "WITH_ILLUS.mp4"))
    subprocess.run([
        "ffmpeg", "-nostdin", "-y", "-i", str(base_video),
        "-itsoffset", str(at), "-i", str(mov),
        "-filter_complex",
        f"[0:v][1:v]overlay=x={x}:y={y}:eof_action=pass:"
        f"enable='between(t,{at},{end:.2f})',format=yuv420p[v]",
        "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "19",
        "-preset", "medium", "-c:a", "copy", "-r", str(FPS), str(out),
        "-loglevel", "error"], check=True)
    print(f"[card] {out.name} · {n} פריימים · {at}→{end:.2f}ש · {w}x{h}@({x},{y})")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="בניית המחשה ויזואלית — מקומי, אפס עלות")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("segment"); s.add_argument("--base", required=True); s.add_argument("--out", required=True)
    m = sub.add_parser("masks"); m.add_argument("--out", required=True)
    m.add_argument("--crop", required=True); m.add_argument("--assign", required=True)
    m.add_argument("--seam")
    at = sub.add_parser("atlas"); at.add_argument("--out", required=True)
    at.add_argument("--atlas", required=True); at.add_argument("--base", required=True)
    at.add_argument("--crop", required=True); at.add_argument("--bands")
    r = sub.add_parser("regions"); r.add_argument("--workdir", required=True)
    r.add_argument("--illus", required=True); r.add_argument("--map", required=True)
    r.add_argument("--plates", required=True)
    c = sub.add_parser("compose"); c.add_argument("--workdir", required=True)
    c.add_argument("--illus", required=True); c.add_argument("--cues", required=True)
    c.add_argument("--dur", type=float, required=True); c.add_argument("--plates", required=True)
    d = sub.add_parser("render"); d.add_argument("--workdir", required=True)
    k = sub.add_parser("card"); k.add_argument("--workdir", required=True)
    k.add_argument("--base", required=True); k.add_argument("--at", type=float, required=True)
    k.add_argument("--out")

    a = ap.parse_args()
    if a.cmd == "segment":
        segment(Path(a.base), Path(a.out))
    elif a.cmd == "masks":
        masks(Path(a.out), tuple(json.loads(a.crop)), json.loads(a.assign),
              json.loads(a.seam) if a.seam else None)
    elif a.cmd == "atlas":
        masks_from_atlas(Path(a.out), Path(a.atlas), Path(a.base),
                         tuple(json.loads(a.crop)),
                         json.loads(a.bands) if a.bands else None)
    elif a.cmd == "regions":
        regions(Path(a.workdir), Path(a.illus), json.loads(a.map), json.loads(a.plates))
    elif a.cmd == "compose":
        compose(Path(a.workdir), Path(a.illus), json.loads(Path(a.cues).read_text()),
                a.dur, json.loads(a.plates))
    elif a.cmd == "render":
        render(Path(a.workdir))
    elif a.cmd == "card":
        card(Path(a.workdir), Path(a.base), a.at, out=Path(a.out) if a.out else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
