#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_vision — מה **רואים** בקליפ, לא מה כתוב בשם שלו.

השורש (הראל + ביקורת Sol, 31.7.26): הסרטון הבטיח "המקום כולו שלכם, בלי
תור", והמצע הראה שיעור מלא. הקליפ נקרא "חימום עם מוט מתאמנת" ותויג
`יחיד` — **התווית שיקרה, והמערכת האמינה לה.** כל שכבת הבחירה עד כה נשענה
על מחרוזות: שם קובץ, תגיות, קטגוריה. אף אחת מהן לא הסתכלה על הפיקסלים.

הכלי הזה דוגם פריימים וסופר אנשים. הפלט הוא **ראיה**, ולכן הוא מה שהשער
בקוד אוכף — לא התיוג.

⛔ **סטטוס: נמדד ונפסל כשער. לא מחובר לצינור.** (31.7.26)
הרצה על 35 הקליפים המאומתים החזירה `solo: 31, pair: 4` — כלומר כמעט הכול
"יחיד". בפועל: "ברפיז בשיעור" (שיעור מלא) קיבל `med=0`, "שיעור ילדים"
קיבל `solo`, ו"חימום עם מוט" — הקליפ שהראל ראה בו שיעור עמוס — קיבל `pair`.
‏Haar+HOG על צילום חדר כושר, כשרוב האנשים לא פונים למצלמה, פשוט לא סופר.

**זו בדיוק אותה טעות שהכלי הזה נבנה כדי לתקן: אות שמשקר.** לכן הוא נשאר
ככלי מדידה ידני בלבד, ואינו חוסם דבר. השער האמיתי דורש מודל-ראייה שמסתכל
על הפריימים (כמו שאדם עושה) — ראה `פרומפט-המשך-V5.md` §1.

    python3 broll_vision.py --catalog-scan            # בונה/מרענן את המטמון
    python3 broll_vision.py --file X.mp4              # קליפ בודד

מטמון: `בירולים/vision-cache.json`, ממופתח ‏file+mtime+size — קליפ שהוחלף
נסרק מחדש מעצמו.
"""
import argparse, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAMPLES = 5          # פריימים לקליפ — 5 מספיקים לקבוע יחיד/זוג/קבוצה
MIN_FACE = 0.045     # גובה פנים מינימלי כשבר מגובה הפריים (מסנן רעש רקע)

# ספי הצפיפות. נמדדו על הבריכה המאומתת (34 קליפים) ב-31.7.26.
CROWD_SOLO, CROWD_PAIR = 1, 2


def _cache_path():
    cfg = json.loads((HERE / "broll-catalog-config.json").read_text(encoding="utf-8"))
    return Path(cfg["catalog_path"]).parent / "vision-cache.json"


def _key(p):
    st = Path(p).stat()
    return f"{Path(p).name}|{int(st.st_mtime)}|{st.st_size}"


def analyze(path, samples=SAMPLES):
    """סופר אנשים בפריימים דגומים. מחזיר ראיה, לא דעה."""
    import cv2
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {"ok": False, "why": "לא ניתן לפתוח"}
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    hc = getattr(cv2.data, "haarcascades", "")
    front = cv2.CascadeClassifier(hc + "haarcascade_frontalface_default.xml")
    prof = cv2.CascadeClassifier(hc + "haarcascade_profileface.xml")
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    counts, bright = [], []
    for i in range(samples):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (i + 0.5) / samples) if n else 0)
        ok, fr = cap.read()
        if not ok or fr is None:
            continue
        h, w = fr.shape[:2]
        small = cv2.resize(fr, (int(w * 480 / h), 480)) if h > 480 else fr
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        mh = MIN_FACE * small.shape[0]
        boxes = []
        for c in (front, prof):
            if c.empty():
                continue
            for (x, y, bw, bh) in c.detectMultiScale(gray, 1.15, 5,
                                                     minSize=(int(mh), int(mh))):
                boxes.append((x, y, bw, bh))
        # HOG תופס גופים שהפנים בהם לא מול המצלמה — בשוט אימון זה הרוב
        try:
            rects, _ = hog.detectMultiScale(small, winStride=(8, 8), scale=1.07)
            for (x, y, bw, bh) in rects:
                boxes.append((x, y + bh // 6, bw, bh // 4))
        except cv2.error:
            pass
        counts.append(len(_dedupe(boxes)))
        bright.append(float(gray.mean()))
    cap.release()
    if not counts:
        return {"ok": False, "why": "אין פריימים"}

    pmax, pmed = max(counts), sorted(counts)[len(counts) // 2]
    crowd = ("solo" if pmed <= CROWD_SOLO else
             "pair" if pmed <= CROWD_PAIR else "group")
    return {"ok": True, "people_max": pmax, "people_median": pmed,
            "crowd": crowd, "per_frame": counts,
            "brightness": round(sum(bright) / len(bright), 1)}


def _dedupe(boxes, iou=0.35):
    out = []
    for b in sorted(boxes, key=lambda r: -r[2] * r[3]):
        if all(_iou(b, o) < iou for o in out):
            out.append(b)
    return out


def _iou(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    return inter / max(1, aw * ah + bw * bh - inter)


def load_cache():
    p = _cache_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def vision_for(paths, cache=None, write=True, limit=None):
    """מחזיר {file: evidence} — מהמטמון, וסורק רק את מה שחסר."""
    cache = load_cache() if cache is None else cache
    out, dirty, scanned = {}, False, 0
    for p in paths:
        if not p or not Path(p).exists():
            continue
        k = _key(p)
        if k not in cache:
            if limit is not None and scanned >= limit:
                continue
            cache[k] = analyze(p)
            scanned += 1
            dirty = True
        out[Path(p).name] = cache[k]
    if dirty and write:
        _cache_path().write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--catalog-scan", action="store_true")
    ap.add_argument("--verified-only", action="store_true",
                    help="רק הקליפים שב-verified_member_files (הבריכה בפועל)")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.file:
        print(json.dumps(analyze(a.file), ensure_ascii=False, indent=1))
        return 0
    if not a.catalog_scan:
        ap.error("‏--file או --catalog-scan")
    cfg = json.loads((HERE / "broll-catalog-config.json").read_text(encoding="utf-8"))
    items = json.loads(Path(cfg["catalog_path"]).read_text(encoding="utf-8"))["items"]
    if a.verified_only:
        ver = set(cfg.get("verified_member_files", []))
        items = [i for i in items if i["file"] in ver]
    res = vision_for([i["path"] for i in items], limit=a.limit)
    by = {}
    for v in res.values():
        by[v.get("crowd", "?") if v.get("ok") else "כשל"] = \
            by.get(v.get("crowd", "?") if v.get("ok") else "כשל", 0) + 1
    print(f"נסרקו/נטענו {len(res)} קליפים · {by}")
    for i in items:
        v = res.get(i["file"], {})
        if v.get("ok"):
            print(f"  {v['crowd']:<6} med={v['people_median']} max={v['people_max']}  {i['file'][:52]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
