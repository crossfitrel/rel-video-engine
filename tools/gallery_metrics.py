#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gallery_metrics.py — שכבת המדידה המשותפת לקציר הגלריה.

עיקרון: אותה מדידה בדיוק על שני הצדדים —
  (א) פריימים מ-447 הבירולים שהראל כבר אישר  → מעטפת ייחוס
  (ב) התצוגות המקדימות מספריית Photos          → מועמדים

כדי שההשוואה תהיה כנה, כל פריים מנורמל לגובה קבוע (WORK_H) לפני המדידה.
בלי הנרמול הזה "חדות" של JPEG מוקטן לא ניתנת להשוואה לפריים במלוא הרזולוציה.

תלויות: PIL + numpy בלבד (אין cv2 על המק הזה).
"""
import numpy as np
from PIL import Image

WORK_H = 512  # גובה עבודה אחיד לכל מדידה

_LAP = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)


def _conv3(a, k):
    """קונבולוציה 3x3 ידנית (מהיר מספיק, בלי scipy)."""
    p = np.pad(a, 1, mode="edge")
    out = np.zeros_like(a, dtype=np.float32)
    for dy in range(3):
        for dx in range(3):
            w = k[dy, dx]
            if w:
                out += w * p[dy:dy + a.shape[0], dx:dx + a.shape[1]]
    return out


def normalize(im: Image.Image) -> Image.Image:
    if im.mode != "RGB":
        im = im.convert("RGB")
    w, h = im.size
    if h != WORK_H:
        im = im.resize((max(1, round(w * WORK_H / h)), WORK_H), Image.BILINEAR)
    return im


def frame_metrics(im: Image.Image) -> dict:
    """מדדים על פריים בודד. כל הערכים בלתי-תלויים ברזולוציית המקור."""
    im = normalize(im)
    rgb = np.asarray(im, dtype=np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b

    sharp = float(_conv3(lum, _LAP).var())

    # colorfulness (Hasler & Susstrunk 2003)
    rg = np.abs(r - g)
    yb = np.abs(0.5 * (r + g) - b)
    colorful = float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))

    # שיעור פיקסלים שרופים / שחורים — מזהה חשיפה גרועה
    clip_hi = float((lum > 250).mean())
    clip_lo = float((lum < 5).mean())

    # אחידות: פריים כמעט-ריק (קיר, תקרה, מסך שחור)
    hist = np.histogram(lum, bins=32, range=(0, 255))[0].astype(np.float32)
    p = hist / max(1.0, hist.sum())
    entropy = float(-(p[p > 0] * np.log2(p[p > 0])).sum())

    return {
        "sharp": round(sharp, 2),
        "bright": round(float(lum.mean()), 2),
        "contrast": round(float(lum.std()), 2),
        "colorful": round(colorful, 2),
        "clip_hi": round(clip_hi, 4),
        "clip_lo": round(clip_lo, 4),
        "entropy": round(entropy, 3),
    }


def metrics_from_path(path: str) -> dict:
    with Image.open(path) as im:
        im.load()
        return frame_metrics(im)
