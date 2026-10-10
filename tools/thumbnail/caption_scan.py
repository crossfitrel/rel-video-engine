#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
caption_scan.py — מאתר פריימים *בלי כתובית צרובה* מתיקיית פריימים שחולצו (fps=4).
חתימת כתובית = פיקסלים כמעט-לבנים הצמודים למתאר כהה (טקסט לבן עם אאוטליין).
מדרג: caption_signal נמוך (נקי) + חדות גבוהה + בהירות שפויה.
פלט: contact sheet לכל סרטון + JSON עם המועמדים הנקיים והטיימסטמפים.
"""
import os, sys, glob, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPS = 4.0  # תואם לחילוץ
BAND_Y0, BAND_Y1 = 0.30, 0.66   # רצועת הכתוביות (אמצע הפריים)
BAND_X0, BAND_X1 = 0.06, 0.94

def dilate_x_y(mask, k=3):
    """דילציה בינארית מלבנית (k בכל כיוון) עי OR של הזזות numpy, ספרבילי."""
    m = mask.copy()
    acc = m.copy()
    for s in range(1, k+1):
        acc[:, s:]  |= m[:, :-s]
        acc[:, :-s] |= m[:, s:]
    m = acc
    acc = m.copy()
    for s in range(1, k+1):
        acc[s:, :]  |= m[:-s, :]
        acc[:-s, :] |= m[s:, :]
    return acc

def analyze(path):
    img = Image.open(path).convert("RGB")
    a = np.asarray(img).astype(np.int16)
    H, W = a.shape[:2]
    gray = a.mean(2)
    y0, y1 = int(H*BAND_Y0), int(H*BAND_Y1)
    x0, x1 = int(W*BAND_X0), int(W*BAND_X1)
    band = a[y0:y1, x0:x1]
    gband = gray[y0:y1, x0:x1]
    near_white = (band.min(2) > 205)
    dark = gband < 70
    dark_d = dilate_x_y(dark, 3)
    text_edge_white = near_white & dark_d
    cap_signal = float(text_edge_white.sum()) / float(near_white.size) * 1000.0
    white_ratio = float(near_white.sum()) / float(near_white.size)
    gx = np.diff(gray, axis=1); gy = np.diff(gray, axis=0)
    sharp = float(gx.var() + gy.var())
    bright = float(gray.mean())
    bright_pen = 1.0 - min(abs(bright - 120)/120.0, 1.0)
    return dict(cap=cap_signal, white=white_ratio, sharp=sharp,
                bright=bright, bpen=bright_pen)

def main():
    base = sys.argv[1]
    out_sheets = os.path.join(base, "sheets")
    os.makedirs(out_sheets, exist_ok=True)
    keys = sorted([d for d in os.listdir(base)
                   if os.path.isdir(os.path.join(base, d)) and d != "sheets"])
    summary = {}
    for key in keys:
        files = sorted(glob.glob(os.path.join(base, key, "f_*.jpg")))
        rows = []
        for f in files:
            n = int(os.path.basename(f).split("_")[1].split(".")[0])
            t = (n - 1) / FPS
            info = analyze(f)
            rows.append(dict(f=f, n=n, t=t, **info))
        if not rows:
            continue
        caps = np.array([r["cap"] for r in rows])
        cap_med = float(np.median(caps))
        cap_thr = max(0.6, cap_med * 0.35)
        clean = [r for r in rows if r["cap"] < cap_thr]
        for r in clean:
            r["score"] = r["sharp"]*1.0 + r["bpen"]*400.0 - r["cap"]*120.0
        clean.sort(key=lambda r: r["score"], reverse=True)
        picked = []
        for r in clean:
            if all(abs(r["t"]-p["t"]) > 0.8 for p in picked):
                picked.append(r)
            if len(picked) >= 12: break
        cols, cw, ch = 4, 270, 480
        rowsN = (len(picked)+cols-1)//cols if picked else 1
        sheet = Image.new("RGB", (cols*cw, rowsN*ch), (24,24,24))
        d = ImageDraw.Draw(sheet)
        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        except: font = ImageFont.load_default()
        for i, r in enumerate(picked):
            im = Image.open(r["f"]).convert("RGB").resize((cw, ch), Image.LANCZOS)
            rr, cc = divmod(i, cols)
            sheet.paste(im, (cc*cw, rr*ch))
            lbl = f"#{i+1}  t={r['t']:.1f}s"
            d.rectangle([cc*cw, rr*ch, cc*cw+200, rr*ch+34], fill=(0,0,0))
            d.text((cc*cw+6, rr*ch+4), lbl, fill=(0,255,120), font=font)
            d.text((cc*cw+6, rr*ch+ch-30), f"cap{r['cap']:.1f} shp{r['sharp']:.0f}",
                   fill=(255,220,0), font=font)
        sp = os.path.join(out_sheets, f"{key}.jpg")
        sheet.save(sp, quality=88)
        summary[key] = dict(
            n_frames=len(rows), cap_median=round(cap_med,2), cap_thr=round(cap_thr,2),
            n_clean=len(clean), sheet=sp,
            top=[dict(rank=i+1, t=round(r["t"],2), cap=round(r["cap"],2),
                      sharp=round(r["sharp"],0), bright=round(r["bright"],0))
                 for i,r in enumerate(picked[:12])])
        print(f"{key}: frames={len(rows)} cap_med={cap_med:.1f} thr={cap_thr:.1f} clean={len(clean)} -> {sp}")
    json.dump(summary, open(os.path.join(base,"scan.json"),"w"), ensure_ascii=False, indent=2)
    print("JSON", os.path.join(base,"scan.json"))

if __name__ == "__main__":
    main()
