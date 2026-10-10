"""גל 6 — B1 בגימור חי של צ'אט מקביל: גיליון FINAL מול הצפוי בכל 5 הרגעים (קריאה בלבד)."""
import sys, os, cv2, numpy as np
sys.path.insert(0, sys.argv[1] + "/tools")
import broll_vision_qa as B
cases = ["טרה-ראן-באיזה-מקום-תסיים-לפני-הריצה", "אחרי-הריצה-איך-היה", "מי-יסיים-מקום-אחד-מעליך"]
rows = []
for proj in cases:
    W = os.path.expanduser("~/rel-video-work/" + proj)
    plan, _ = B._plan(W)
    for it in plan:
        w = B._win(it)
        if not w:
            continue
        s, e = w
        tiles = []
        for q in (0.2, 0.35, 0.5, 0.65, 0.8):
            tt = s + q * (e - s)
            fr = B._frame(W + "/FINAL.mp4", tt)
            cf = B._frame(B._clip_path(W, it), float(it.get("src_offset") or 0) + (tt - s))
            ex = B.expected_overlay(cf)
            tiles += [cv2.resize(fr, (180, 320)), cv2.resize(ex, (180, 320))]
        row = np.hstack(tiles)
        cv2.putText(row, f"{proj[:14]} {it.get('file','')[:22]} {s:.1f}-{e:.1f}", (6, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        rows.append(row)
        print(proj, it.get("file"), s, e, it.get("src_offset"), it.get("speed"))
cv2.imwrite(sys.argv[1] + "/_opus55_wave6/b1_live_sheet.jpg", np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
