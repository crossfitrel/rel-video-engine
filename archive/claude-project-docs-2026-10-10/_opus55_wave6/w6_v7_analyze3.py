"""ניתוח על כל ה-cues של כל FINAL חי (v7_full) — כלל garbled חדש: g1 = f_ok1 × r1.
לכל סף: המקסימום פר-סרטון של cues מתחת לסף (חיובי-שגוי), ותפיסה פר-cue בהזרקות (v7_rows)."""
import sys, json, glob
from pathlib import Path
D = Path(sys.argv[1]) / "_opus55_wave6"
full = [json.loads(l) for f in sorted(glob.glob(str(D / "v7_full.*.jsonl"))) for l in open(f, encoding="utf-8")]
inj = [json.loads(l) for f in sorted(glob.glob(str(D / "v7_rows.*.jsonl"))) for l in open(f, encoding="utf-8")]
BAD = {"קניות-v2"}
TRUE_DEFECT = {("ההבנה-האנטומית-סוגי-קרעים", 39.25)}
g1 = lambda c: c["f_ok1"] * c["r1"]
out = {"n_videos": len(full), "n_cues": sum(len(r["pos"]) for r in full if r["project"] not in BAD)}
grid = {}
for t100 in range(24, 40):
    thr = t100 / 100.0
    per = []
    for r in full:
        if r["project"] in BAD:
            continue
        ps = [c for c in r["pos"] if c["ink_in"] >= 0.23 and (r["project"], c["t"]) not in TRUE_DEFECT]
        per.append((sum(1 for c in ps if g1(c) < thr), r["project"], len(ps)))
    per.sort(reverse=True)
    catch = {}
    for kind in ("tofu", "scrambled", "wrong_word", "stale_prev"):
        ns = [g1(c) for r in inj for c in r["neg"] if c["kind"] == kind and c["ink_in"] >= 0.23]
        catch[kind] = round(sum(1 for v in ns if v < thr) / len(ns), 4)
    kb = [c for r in full if r["project"] in BAD for c in r["pos"] if c["ink_in"] >= 0.23]
    grid[thr] = {"worst": per[:3], "videos_with_1plus": sum(1 for p in per if p[0] >= 1),
                 "catch": catch, "known_bad": (sum(1 for c in kb if g1(c) < thr), len(kb))}
    print(thr, grid[thr]["worst"][:2], grid[thr]["videos_with_1plus"], catch, grid[thr]["known_bad"])
# f_ok1 הישן על כל ה-cues (לבדיקת הכלל הנוכחי ≥3 ו-≥25%)
old = []
for r in full:
    ps = [c for c in r["pos"] if c["ink_in"] >= 0.23]
    n = sum(1 for c in ps if c["f_ok1"] < 0.579)
    old.append((n, round(n / max(1, len(ps)), 3), r["project"]))
out["old_rule_worst"] = sorted(old, reverse=True)[:4]
print("old f_ok1<0.579:", out["old_rule_worst"])
td = [c for r in full for c in r["pos"] if (r["project"], c["t"]) in TRUE_DEFECT]
out["true_defect_g1"] = [round(g1(c), 3) for c in td]
print("true defect g1:", out["true_defect_g1"])
out["grid"] = {str(k): v for k, v in grid.items()}
(D / "v7_analysis3.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
