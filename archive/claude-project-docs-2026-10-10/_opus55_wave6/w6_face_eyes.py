"""גל 6 — האם אימות עיניים בתוך תיבת הפנים מנקה את ה-face של Haar? (35 פגיעות, 4 אמיתיות בעין)."""
import sys, json, os
from pathlib import Path
S = Path(sys.argv[1]); sys.path.insert(0, str(S / "tools"))
import cv2
import caption_vision as cv
D = S / "_opus55_wave6"
rows = json.loads((D / "face_rows.json").read_text(encoding="utf-8"))
hits = [r for r in rows if r["alt"]["430"]]
TRUE = {17, 18, 19, 20}                  # נקבע בעין על face_sheet_0.jpg (סלפי, הכתובית על הסנטר)
eye = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml"))
R = Path.home() / "rel-video-work"
res = []
for k, h in enumerate(hits):
    fr, _ = cv.sample_frames(R / h["p"] / "FINAL.mp4", [h["t"]])
    fr = fr[0]
    x0, y0, x1, y1 = h["cap"]
    hitboxes = [f for f in h["faces"] if f[0] < x1 and f[0] + f[2] > x0 and f[1] < y1 and f[1] + f[3] > y0]
    best = 0
    for (fx, fy, fw, fh) in hitboxes:
        roi = cv2.cvtColor(fr[fy:fy + int(fh * 0.6), fx:fx + fw], cv2.COLOR_BGR2GRAY)
        s = 160.0 / max(1, fw)
        roi = cv2.equalizeHist(cv2.resize(roi, None, fx=s, fy=s))
        e = eye.detectMultiScale(roi, 1.1, 6, minSize=(14, 14))
        best = max(best, len(e))
    res.append({"k": k, "true": k in TRUE, "eyes": best})
for thr in (1, 2):
    tp = sum(1 for r in res if r["true"] and r["eyes"] >= thr)
    fp = sum(1 for r in res if not r["true"] and r["eyes"] >= thr)
    print(f"eyes>={thr}: TP {tp}/4  FP {fp}/31")
print([(r["k"], r["eyes"]) for r in res])
(D / "face_eyes.json").write_text(json.dumps(res), encoding="utf-8")
