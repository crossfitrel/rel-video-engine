"""גל 5 — איסוף אזורי טקסט (Vision) על הבריכה + הזרקות. פלט JSONL מצטבר (אפשר לחדש)."""
import json, random, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import broll_vision_qa as B
import diag_b2_ocr as D  # noqa  (ocr())

OUT = Path(__file__).parent / "b2_ocr_samples.jsonl"
n_pos = int(sys.argv[1]); n_neg = int(sys.argv[2])
done = set()
if OUT.exists():
    for ln in OUT.read_text().splitlines():
        r = json.loads(ln); done.add((r["kind"], r["clip"]))
_c, cat = B._catalog()
items = [i for i in cat.values() if Path(i["path"]).exists()]
random.Random(11).shuffle(items)
tmp = Path(tempfile.mkdtemp(prefix="b2c_"))
with OUT.open("a") as f:
    for k, it in enumerate(items[:max(n_pos, n_neg)]):
        name = Path(it["path"]).name
        if k < n_pos and ("pos", name) not in done:
            d = D.ocr(it["path"])
            f.write(json.dumps({"kind": "pos", "clip": name, "ocr": d, "motion": B.text_static_score(it["path"])}, ensure_ascii=False) + "\n"); f.flush()
        if k < n_neg and ("neg", name) not in done:
            dst = tmp / "inj.mp4"
            B.inject_text(it["path"], dst)
            d = D.ocr(dst)
            f.write(json.dumps({"kind": "neg", "clip": name, "ocr": d, "motion": B.text_static_score(dst)}, ensure_ascii=False) + "\n"); f.flush()
