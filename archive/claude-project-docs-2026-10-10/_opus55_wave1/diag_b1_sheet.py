import sys, os, json, cv2, numpy as np
sys.path.insert(0, sys.argv[1] + "/tools")
import broll_vision_qa as B
cases = [("ממומן-ת1-סטודנטים", 41.03), ("ממומן-ת1-סטודנטים", 35.65), ("ממומן-ת4-סטודנטים", 28.83), ("ממומן-ת3-תושבים", 32.16)]
tiles = []
for proj, tt in cases:
    W = os.path.expanduser("~/rel-video-work/" + proj)
    plan, d = B._plan(W)
    it = [i for i in plan if B._win(i) and abs(sum(B._win(i)) / 2 - tt) < 0.05][0]
    s, e = B._win(it)
    fr = B._frame(W + "/FINAL.mp4", tt)
    cp = B._clip_path(W, it)
    cf = B._frame(cp, float(it.get("src_offset") or 0) + (tt - s))
    ex = B.expected_overlay(cf)
    print(proj, tt, it.get("src_offset"), s, e, os.path.getmtime(cp) > os.path.getmtime(W + "/FINAL.mp4"), it.get("speed"), list(it.keys())[:14])
    row = np.hstack([cv2.resize(fr, (270, 480)), cv2.resize(ex, (270, 480))])
    tiles.append(row)
cv2.imwrite(sys.argv[1] + "/_opus55_wave1/b1_bad.jpg", np.vstack([np.hstack(tiles[:2]), np.hstack(tiles[2:])]))
