"""גל 5 — למה B1 'לא נחת' בקמפיין? לכל פריט לא-נחת: דמיון ב-FINAL, ב-EXPORT+BROLL,
וחיפוש היסט זמן ±4ש ב-FINAL. קריאה בלבד."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import broll_vision_qa as B

WR = Path.home() / "rel-video-work"
cfg = json.loads((Path(B.__file__).parent / "broll-vision-calibration.json").read_text())["params"]
out = []
for name in sys.argv[1:]:
    W = WR / name
    items, meta = B._plan(W)
    intro, rec = B._intro(W)
    fin = W / "FINAL.mp4"; ebb = W / "EXPORT+BROLL.mp4"
    for it in items:
        r = B.b1_landed(W, it, fin, intro, cfg)
        if not r.get("measured") or r.get("landed"):
            continue
        s, e = B._win(it); cp = B._clip_path(W, it)
        cf = B._frame(cp, float(it.get("src_offset") or 0) + (e - s) / 2)
        row = {"p": name, "file": Path(cp).name, "win": [s, e], "intro": intro, "fin": r}
        if ebb.exists():
            row["ebb"] = B.b1_landed(W, it, ebb, 0.0, cfg)
        best = (None, -9)
        for k in range(-40, 41):
            dt = k / 10
            fr = B._frame(fin, intro + (s + e) / 2 + dt)
            if fr is None or cf is None:
                continue
            v = B.best_clip_sim(fr, cp, cf)
            if v is not None and v > best[1]:
                best = (dt, v)
        row["best_shift"] = best
        out.append(row)
        print(json.dumps(row, ensure_ascii=False))
