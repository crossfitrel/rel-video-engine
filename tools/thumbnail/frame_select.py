#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
frame_select.py — בורר פריים אוטומטי ל-Thumbnail של CrossFit R.E.L
חולץ פריים בולט מסרטון *לפני הכתוביות* (EXPORT) לשימוש כרקע ל-Thumbnail.
ניקוד: פנים פרונטליות (גודל+מיקום עליון) + חדות (Laplacian) + בהירות שפויה.
פלט: best.png (1080x1920) + candidates.jpg (contact sheet לאימות).
"""
import sys, os, argparse, cv2, numpy as np

def laplacian_sharpness(gray):
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def score_frame(bgr, face_cascade):
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    sharp = laplacian_sharpness(gray)
    bright = gray.mean()
    # penalty for too dark / too bright
    bright_pen = 1.0 - min(abs(bright - 125) / 125.0, 1.0)  # 1 at mid, 0 at extremes
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6,
                                          minSize=(int(w*0.10), int(w*0.10)))
    face_score = 0.0
    best_face = None
    for (fx, fy, fw, fh) in faces:
        area = (fw*fh) / float(w*h)
        cy = (fy + fh/2.0) / h
        # prefer faces in the upper 70% (text band sits in lower third)
        pos_bonus = 1.0 if cy < 0.55 else (0.5 if cy < 0.70 else 0.15)
        s = area * 100.0 * pos_bonus
        if s > face_score:
            face_score = s; best_face = (fx, fy, fw, fh)
    # normalized sharpness (cap)
    sharp_n = min(sharp / 400.0, 1.0)
    total = face_score * 3.0 + sharp_n * 1.5 + bright_pen * 1.0
    return total, dict(sharp=sharp, bright=bright, faces=len(faces), face_score=face_score, face=best_face)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default="frames_out")
    ap.add_argument("--step", type=float, default=0.4, help="sampling step seconds")
    ap.add_argument("--skip-head", type=float, default=1.5)
    ap.add_argument("--skip-tail", type=float, default=1.0)
    ap.add_argument("--topn", type=int, default=8)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = total / fps
    fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    t = args.skip_head
    results = []
    while t < dur - args.skip_tail:
        cap.set(cv2.CAP_PROP_POS_MSEC, t*1000.0)
        ok, frame = cap.read()
        if not ok:
            t += args.step; continue
        sc, info = score_frame(frame, fc)
        results.append((sc, t, frame, info))
        t += args.step
    cap.release()
    if not results:
        print("NO_FRAMES"); sys.exit(1)

    results.sort(key=lambda r: r[0], reverse=True)
    best_sc, best_t, best_frame, best_info = results[0]
    cv2.imwrite(os.path.join(args.out, "best.png"), best_frame)

    # contact sheet of top N (dedupe by >=0.8s apart)
    chosen = []
    for sc, tt, fr, info in results:
        if all(abs(tt-ct) > 0.8 for ct,_ in chosen):
            chosen.append((tt, fr))
        if len(chosen) >= args.topn: break
    cols = 4
    rows = (len(chosen)+cols-1)//cols
    cw, ch = 270, 480
    sheet = np.full((rows*ch, cols*cw, 3), 30, np.uint8)
    for i,(tt,fr) in enumerate(chosen):
        r,c = divmod(i, cols)
        thumb = cv2.resize(fr, (cw, ch))
        cv2.putText(thumb, f"{tt:.1f}s", (8,28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
        sheet[r*ch:(r+1)*ch, c*cw:(c+1)*cw] = thumb
    cv2.imwrite(os.path.join(args.out, "candidates.jpg"), sheet)

    print(f"BEST t={best_t:.2f}s score={best_sc:.2f} faces={best_info['faces']} "
          f"sharp={best_info['sharp']:.0f} bright={best_info['bright']:.0f}")
    print("OUT", os.path.join(args.out, "best.png"))

if __name__ == "__main__":
    main()
