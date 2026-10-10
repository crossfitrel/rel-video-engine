"""סריקת V7 על כל ה-FINAL החיים (קריאה בלבד — write=False; גיליון רק לממצאים, לתיקיית הראיות)."""
import sys, json, time, shutil
from pathlib import Path
S = sys.argv[1]; sys.path.insert(0, S + "/tools")
import caption_vision as cv
R = Path.home() / "rel-video-work"
out = Path(S) / "_opus55_wave1"
cands = sorted([p.parent for p in R.glob("*/FINAL.mp4") if (p.parent / "words_final.json").exists()
                and not p.parent.name.startswith("_")], key=lambda p: -(p / "FINAL.mp4").stat().st_mtime)
cands = cands[: int(sys.argv[2]) if len(sys.argv) > 2 else 40]
rows = []
for W in cands:
    t = time.time()
    try:
        d = cv.analyze(W, sheet=False, write=False)
    except Exception as e:
        print(W.name, "ERR", e); continue
    rows.append({"project": W.name, "ok": d.get("ok"), "n": d.get("n_measured"), "cues": d.get("n_cues"),
                 "f_med": d.get("f_ok_median"), "counts": d.get("counts"), "offset": d.get("intro_offset_sec"),
                 "offset_source": d.get("offset_source"), "brand": d.get("brand"), "brand_found": d.get("brand_found"),
                 "sec": round(time.time() - t, 1)})
    print(json.dumps(rows[-1], ensure_ascii=False))
(out / "sweep_caption_vision.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
