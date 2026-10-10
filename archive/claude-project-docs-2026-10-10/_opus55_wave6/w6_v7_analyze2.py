"""ניתוח משני: (1) כלל ספירה פר-סרטון ל-garbled (כמה cues מתחת לסף בכל FINAL חי)
(2) extra_ink משולב (far_area OR ink_out) (3) גיליון לחיוביים עם רכיב רחוק — לעין."""
import sys, json, glob
from pathlib import Path
import numpy as np, cv2
S = Path(sys.argv[1]); D = S / "_opus55_wave6"
sys.path.insert(0, str(S / "tools"))
recs = [json.loads(l) for f in sorted(glob.glob(str(D / "v7_rows.*.jsonl"))) for l in open(f, encoding="utf-8")]
BAD = {"קניות-v2"}
TRUE_DEFECT = {("ההבנה-האנטומית-סוגי-קרעים", 39.25)}
out = {}
for mname, fn in (("f_ok1", lambda c: c["f_ok1"]), ("f1*r1", lambda c: c["f_ok1"] * c["r1"])):
    grid = {}
    for thr in np.arange(0.25, 0.66, 0.01):
        worst = (0, 0.0, "")
        for r in recs:
            if r["project"] in BAD:
                continue
            ps = [c for c in r["pos"] if c["ink_in"] >= 0.23 and (r["project"], c["t"]) not in TRUE_DEFECT]
            n = sum(1 for c in ps if fn(c) < thr)
            frac = n / max(1, len(ps))
            if (n, frac) > worst[:2]:
                worst = (n, round(frac, 3), r["project"])
        negs = {}
        for kind in ("tofu", "scrambled", "wrong_word"):
            ns = [fn(c) for r in recs for c in r["neg"] if c["kind"] == kind and c["ink_in"] >= 0.23]
            negs[kind] = round(sum(1 for v in ns if v < thr) / len(ns), 3)
        kb = [c for r in recs if r["project"] in BAD for c in r["pos"]]
        grid[round(float(thr), 2)] = {"worst_live": worst, "catch": negs,
                                      "known_bad_frac": round(sum(1 for c in kb if fn(c) < thr) / max(1, len(kb)), 3)}
    out[mname] = grid
allpos = [dict(c, project=r["project"]) for r in recs if r["project"] not in BAD for c in r["pos"]]
comb = lambda c, a, b: c["far_area"] > a or c["ink_out"] > b
a, b = max(c["far_area"] for c in allpos), max(c["ink_out"] for c in allpos)
out["extra_combined"] = {"far_thr": a, "ink_thr": b, **{
    k: round(sum(1 for r in recs for c in r["neg"] if c["kind"] == k and comb(c, a, b)) /
             max(1, sum(1 for r in recs for c in r["neg"] if c["kind"] == k)), 3) for k in ("doubled", "doubled_far")}}
(D / "v7_analysis2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for m in ("f_ok1", "f1*r1"):
    for thr, v in out[m].items():
        if thr in (0.28, 0.3, 0.33, 0.36, 0.4, 0.45, 0.5, 0.52, 0.55, 0.58, 0.6):
            print(m, thr, v)
print(out["extra_combined"])
# גיליון: החיוביים עם רכיב רחוק (n_far=1) — רצועת הכתובית מה-FINAL
import caption_vision as cv
from captions_build import group_cues, load_words
tiles = []
top = sorted((c for c in allpos if c["n_far"] >= 1), key=lambda c: -c["far_area"])[:9]
R = Path.home() / "rel-video-work"
for c in top:
    W = R / c["project"]
    video, words, brand, intro = cv.project_inputs(W)
    fr, _ = cv.sample_frames(video, [c["t"]])
    if fr[0] is None:
        continue
    cues = group_cues(load_words(str(words)))
    g = cv.geometry(cues, fr[0].shape[1], fr[0].shape[0], brand)
    band = fr[0][max(0, g["y0"] - 60):g["y0"] + g["band_h"] + 20]
    band = cv2.resize(band, (900, int(900 * band.shape[0] / band.shape[1])))
    cv2.putText(band, f"{c['far_area']} {c['t']}", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    tiles.append(band)
if tiles:
    w = max(t.shape[1] for t in tiles)
    cv2.imwrite(str(D / "extra_far_pos_sheet.jpg"), np.vstack([cv2.copyMakeBorder(t, 0, 4, 0, w - t.shape[1], cv2.BORDER_CONSTANT) for t in tiles]))
