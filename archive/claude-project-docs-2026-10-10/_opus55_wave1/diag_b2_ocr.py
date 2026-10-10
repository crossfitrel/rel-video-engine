"""גל 5 — B2 עם גילוי אזורי טקסט של Vision: הבריכה מול אותם קליפים + כיתוב מוזרק."""
import json, random, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import broll_vision_qa as B

BIN = Path.home() / ".rel-bin" / "vision_ocr"


def ocr(p, n=6):
    r = subprocess.run([str(BIN), str(p), str(n)], capture_output=True, text=True, timeout=120)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def summarize(d):
    rows = []
    for f in d["frames"]:
        rs = [x for x in f["rects"] if x["chars"] >= 3]
        rows.append([[round(v, 3) for v in x["box"]] + [x["chars"]] for x in rs])
    return rows


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    _c, cat = B._catalog()
    items = [i for i in cat.values() if Path(i["path"]).exists()]
    random.Random(3).shuffle(items)
    tmp = Path(tempfile.mkdtemp(prefix="b2o_"))
    for it in items[:n]:
        a = ocr(it["path"])
        dst = tmp / "inj.mp4"
        B.inject_text(it["path"], dst)
        b = ocr(dst)
        print(json.dumps({"clip": Path(it["path"]).name, "orig": summarize(a) if a else None,
                          "inj": summarize(b) if b else None}, ensure_ascii=False))
