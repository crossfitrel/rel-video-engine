"""גל 6 (v9.34) — face בכתוביות: האם marginv דינמי משפר בלי לפגוע בקריאות?

מדידה לפני תיקון, קריאה בלבד:
 1. דיוק הגלאי: כל cue שבו Haar מצא פנים שחותכות את מלבן הכתובית — גיליון
    (פריים מלא מוקטן, פנים בירוק, כתובית באדום) לקריאה בעין.
 2. סימולציה: לכל cue, לכל marginv חלופי — האם הכתובית הייתה חותכת פנים;
    ומדיניות דינמית (הזזה רק ב-cue עם פגיעה, למיקום הקרוב שפנוי) —
    כמה פגיעות נפתרות, וכמה קפיצות-מיקום נוספות לדקה (עלות הקריאות: העין
    צריכה לחפש את הכתובית מחדש בכל קפיצה).
פלט: _opus55_wave6/face_rows.json + face_sheet_*.jpg
"""
import sys, json
from pathlib import Path
S = Path(sys.argv[1]); sys.path.insert(0, str(S / "tools"))
import numpy as np, cv2
import caption_vision as cv
from captions_build import group_cues, load_words

R = Path.home() / "rel-video-work"
OUTD = S / "_opus55_wave6"
SKIP = {"טרה-ראן-באיזה-מקום-תסיים-לפני-הריצה", "אחרי-הריצה-איך-היה", "מי-יסיים-מקום-אחד-מעליך", "קניות-v2"}
ALTS = [230, 330, 430, 530, 630, 730, 830]       # 430 = הקאנון (לפני סקייל)
PER = 80
rows, hits = [], []
for p in sorted(R.glob("*/FINAL.mp4")):
    W = p.parent
    if W.name.startswith("_") or W.name in SKIP or not (W / "words_final.json").exists():
        continue
    video, words, brand, intro = cv.project_inputs(W)
    cues = group_cues(load_words(str(words)))
    cap = cv2.VideoCapture(str(video)); Wv = int(cap.get(3)); Hv = int(cap.get(4))
    dur = (cap.get(7) or 0) / (cap.get(5) or 30); cap.release()
    g = cv.geometry(cues, Wv, Hv, brand)
    if intro is None:
        intro, _ = cv.estimate_offset(video, cues, g)
    idx = [i for i, c in enumerate(cues) if c["end"] - c["start"] >= 0.07]
    if len(idx) > PER:
        st = len(idx) / float(PER); idx = [idx[int(k * st)] for k in range(PER)]
    times = [intro + (cues[i]["start"] + cues[i]["end"]) / 2 for i in idx]
    frames, _ = cv.sample_frames(video, times)
    sc = Hv / 1920.0
    for i, t, fr in zip(idx, times, frames):
        if fr is None:
            continue
        fc = cv.faces(fr) or []
        _, bb, _ = cv.render_mask(cues[i]["text"], g, Wv, "rtl")
        x0, y0b, x1, y1b = bb
        hgt = y1b - y0b
        base_bot = g["y0"] + y1b                     # תחתית הכתובית במיקום הנוכחי
        rec = {"p": W.name, "t": round(t, 2), "text": cues[i]["text"], "faces": [list(map(int, f)) for f in fc],
               "cap": [int(x0), int(g["y0"] + y0b), int(x1), int(base_bot)], "alt": {}}
        for mv in ALTS:
            dy = round((430 - mv) * sc)              # marginv גדול = כתובית גבוהה יותר
            cy0, cy1 = g["y0"] + y0b + dy, base_bot + dy
            rec["alt"][mv] = any(f[0] < x1 and f[0] + f[2] > x0 and f[1] < cy1 and f[1] + f[3] > cy0 for f in fc)
        rows.append(rec)
        if rec["alt"][430]:
            small = cv2.resize(fr, (270, 480))
            s = 270.0 / Wv
            for f in fc:
                cv2.rectangle(small, (int(f[0] * s), int(f[1] * s)), (int((f[0] + f[2]) * s), int((f[1] + f[3]) * s)), (0, 255, 0), 2)
            cv2.rectangle(small, (int(x0 * s), int(rec["cap"][1] * s)), (int(x1 * s), int(base_bot * s)), (0, 0, 255), 2)
            cv2.putText(small, f"{len(hits)}", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            hits.append(small)
    print(W.name, sum(1 for r in rows if r["p"] == W.name and r["alt"][430]), flush=True)

for k in range(0, len(hits), 24):
    chunk = hits[k:k + 24]
    while len(chunk) % 6:
        chunk.append(np.zeros_like(hits[0]))
    grid = np.vstack([np.hstack(chunk[r * 6:(r + 1) * 6]) for r in range(len(chunk) // 6)])
    cv2.imwrite(str(OUTD / f"face_sheet_{k // 24}.jpg"), grid, [cv2.IMWRITE_JPEG_QUALITY, 80])
(OUTD / "face_rows.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
print("DONE", len(rows), "hits", len(hits))
