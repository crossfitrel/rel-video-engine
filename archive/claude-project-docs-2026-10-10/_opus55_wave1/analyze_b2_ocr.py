"""גל 5 — ניתוח B2: האם אזורי טקסט עקביים (Vision) מפרידים כיתוב צרוב מהבריכה."""
import json, sys
from pathlib import Path

rows = [json.loads(l) for l in (Path(__file__).parent / "b2_ocr_samples.jsonl").read_text().splitlines()]


def iou(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx)); iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    u = aw * ah + bw * bh - inter
    return inter / u if u else 0


def same_band(a, b):
    """אותה שורת טקסט: מרכז אנכי זהה (±0.012) וגובה דומה — הרוחב משתנה בין פריימים
    כי Vision מפצל/מאחד מילים עבריות אחרת בכל פריים."""
    ca, cb = a[1] + a[3] / 2, b[1] + b[3] / 2
    return abs(ca - cb) <= 0.012 and 0.6 <= (a[3] / b[3] if b[3] else 0) <= 1.6


MATCH = same_band if "--band" in sys.argv else (lambda a, b: iou(a, b) >= 0.5)


def tracks(d, min_chars=3, min_h=0.0):
    fr = [[x for x in f["rects"] if x["chars"] >= min_chars and x["box"][3] >= min_h] for f in d["frames"]]
    best = 0; best_box = None
    for i, f in enumerate(fr):
        for r in f:
            n = sum(1 for g in fr if any(MATCH(r["box"], s["box"]) for s in g))
            if n > best:
                best, best_box = n, r
    return best, (best_box or {}).get("box"), len(fr)


def feats(r):
    d = r["ocr"]
    if not d or not d.get("frames"):
        return None
    p, box, nf = tracks(d)
    p2, _, _ = tracks(d, min_chars=4, min_h=0.018)
    m = r.get("motion") or {}
    return {"persist": p / max(1, nf), "persist_big": p2 / max(1, nf), "box": box,
            "moving": m.get("measured", False), "static_frac": m.get("static_text_frac")}


F = {"pos": [], "neg": []}
for r in rows:
    f = feats(r)
    if f:
        F[r["kind"]].append((r["clip"], f))
for key in ("persist", "persist_big"):
    for thr in (0.5, 0.67, 0.84, 1.0):
        fp = [c for c, f in F["pos"] if f[key] >= thr]
        tp = [c for c, f in F["neg"] if f[key] >= thr]
        fpm = [c for c, f in F["pos"] if f[key] >= thr and f["moving"]]
        tpm = [c for c, f in F["neg"] if f[key] >= thr and f["moving"]]
        print(f"{key}≥{thr}: pos {len(fp)}/{len(F['pos'])} · neg {len(tp)}/{len(F['neg'])} "
              f"| moving-only: pos {len(fpm)}/{sum(f['moving'] for _, f in F['pos'])} neg {len(tpm)}/{sum(f['moving'] for _, f in F['neg'])}")
if "-v" in sys.argv:
    for c, f in sorted(F["pos"], key=lambda x: -x[1]["persist_big"])[:12]:
        print("POS", round(f["persist_big"], 2), f["moving"], f["box"], c)
    for c, f in sorted(F["neg"], key=lambda x: x[1]["persist_big"])[:8]:
        print("NEG", round(f["persist_big"], 2), f["moving"], f["box"], c)
