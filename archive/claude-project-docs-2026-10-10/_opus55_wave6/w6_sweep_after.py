"""אחרי התיקון: caption_vision.analyze האמיתי (הקוד והכיול החדשים) על כל FINAL חי — קריאה בלבד.
  $P w6_sweep_after.py SYSTEM_DIR k/n"""
import sys, json, time
from pathlib import Path
S = sys.argv[1]; sys.path.insert(0, S + "/tools")
import caption_vision as cv
SK, SN = (int(x) for x in sys.argv[2].split("/"))
R = Path.home() / "rel-video-work"
SKIP = {"טרה-ראן-באיזה-מקום-תסיים-לפני-הריצה", "אחרי-הריצה-איך-היה", "מי-יסיים-מקום-אחד-מעליך"}
WORDS_OVERRIDE = {"טיפ-אחד-HSPU": "words_final3.json"}
out = Path(S) / "_opus55_wave6" / f"sweep_after.{SK}.jsonl"
cands = sorted(p.parent for p in R.glob("*/FINAL.mp4") if (p.parent / "words_final.json").exists()
               and not p.parent.name.startswith("_") and p.parent.name not in SKIP)
for j, W in enumerate(cands):
    if j % SN != SK:
        continue
    t = time.time()
    wf = WORDS_OVERRIDE.get(W.name)
    d = cv.analyze(W, words=(W / wf) if wf else None, sheet=False, write=False)
    rec = {"project": W.name, "ok": d.get("ok"), "n": d.get("n_measured"), "counts": d.get("counts"),
           "blocking_hits": d.get("blocking_hits"),
           "face_raw": sum(1 for c in d.get("cues", []) if c.get("face_raw")),
           "sec": round(time.time() - t, 1)}
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False), flush=True)
print("DONE")
