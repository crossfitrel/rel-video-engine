"""ניתוח v7_rows.*.jsonl — הפרדה חיוביים (FINAL חיים) מול הזרקות, לפי רקע אירוע/רגיל."""
import sys, json, glob
from pathlib import Path
D = Path(sys.argv[1]) / "_opus55_wave6"
KNOWN_BAD = {"קניות-v2"}                      # תקלה אמיתית (פונט ישן) — לא חיובי
recs = []
for f in sorted(glob.glob(str(D / "v7_rows.*.jsonl"))):
    for ln in open(f, encoding="utf-8"):
        recs.append(json.loads(ln))
R = Path.home() / "rel-video-work"
def _dep(name):
    try:
        m = json.loads((R / name / "project_manifest.json").read_text(encoding="utf-8"))
        return m.get("department") or m.get("dept") or ""
    except Exception:
        return ""
ev = lambda r: _dep(r["project"]) == "REL Throwdown"


def q(v, p):
    v = sorted(v)
    return None if not v else round(v[min(len(v) - 1, max(0, int(round(p * (len(v) - 1)))))], 3)


out = {"n_projects": len(recs), "event_projects": sum(1 for r in recs if ev(r))}
pos = {"event": [], "regular": []}
neg = {"event": {}, "regular": {}}
for r in recs:
    k = "event" if ev(r) else "regular"
    if r["project"] not in KNOWN_BAD:
        for c in r["pos"]:
            pos[k].append(dict(c, project=r["project"]))
    for c in r["neg"]:
        neg[k].setdefault(c["kind"], []).append(c)
out["n_pos"] = {k: len(v) for k, v in pos.items()}

# ── garbled: איזה מדד מפריד? מינימום חיוביים מול p95 של השליליים
GARB = ("tofu", "scrambled", "wrong_word", "stale_prev")
for metric in ("f_ok1", "r1", "p1", "r3"):
    row = {}
    for k in ("event", "regular"):
        pv = [c[metric] for c in pos[k] if c["ink_in"] >= 0.23]
        row[k] = {"pos_min": q(pv, 0), "pos_p01": q(pv, 0.01),
                  "neg_p95": {n: q([c[metric] for c in neg[k].get(n, []) if c["ink_in"] >= 0.23], 0.95) for n in GARB},
                  "neg_p50": {n: q([c[metric] for c in neg[k].get(n, []) if c["ink_in"] >= 0.23], 0.5) for n in GARB}}
    out[f"garbled::{metric}"] = row
# החיוביים הנמוכים ביותר ב-f_ok1 (מי הם, ומה r1/p1 שלהם)
allp = pos["event"] + pos["regular"]
out["lowest_f_ok1"] = [{k: c[k] for k in ("project", "t", "text", "f_ok1", "r1", "p1", "ink_out")}
                       for c in sorted(allp, key=lambda c: c["f_ok1"])[:12]]
out["lowest_r1"] = [{k: c[k] for k in ("project", "t", "text", "f_ok1", "r1", "p1", "ink_out")}
                    for c in sorted(allp, key=lambda c: c["r1"])[:12]]

# ── extra_ink: המדד הישן מול רכיבים מחוברים / עמודות מחוץ ל-bbox
DBL = ("doubled", "doubled_far")
for metric in ("ink_out", "n_far", "far_area", "ext_cols", "n_comp"):
    row = {}
    for k in ("event", "regular"):
        pv = [c[metric] for c in pos[k]]
        row[k] = {"pos_max": q(pv, 1), "pos_p99": q(pv, 0.99),
                  "neg_p05": {n: q([c[metric] for c in neg[k].get(n, [])], 0.05) for n in DBL},
                  "neg_p50": {n: q([c[metric] for c in neg[k].get(n, [])], 0.5) for n in DBL}}
    out[f"extra::{metric}"] = row
out["highest_far_area"] = [{k: c[k] for k in ("project", "t", "text", "n_far", "far_area", "ext_cols", "ink_out")}
                           for c in sorted(allp, key=lambda c: -c["far_area"])[:12]]
out["highest_ext_cols"] = [{k: c[k] for k in ("project", "t", "text", "n_far", "far_area", "ext_cols", "ink_out")}
                           for c in sorted(allp, key=lambda c: -c["ext_cols"])[:12]]
# known bad (קניות-v2) — האם עדיין נתפס
for r in recs:
    if r["project"] in KNOWN_BAD:
        out["known_bad"] = {"n": len(r["pos"]), "f_ok1<0.579": sum(1 for c in r["pos"] if c["f_ok1"] < 0.579),
                            "r1_p50": q([c["r1"] for c in r["pos"]], 0.5)}
# ── כללים מועמדים: תפיסה בסף שנותן 0 חיובי-שגוי על כל ה-FINAL החיים
TRUE_DEFECT = {("ההבנה-האנטומית-סוגי-קרעים", 39.25)}   # מילה אחרת על המסך (גל 1, נבדק בעין)
allpos = [c for c in allp if (c["project"], c["t"]) not in TRUE_DEFECT and c["ink_in"] >= 0.23]
def rule_eval(name, score, higher_is_bad, kinds, scope=("event", "regular")):
    ps = [score(c) for c in allpos]
    thr = (max(ps) if higher_is_bad else min(ps))
    res = {"thr_at_fp0": round(thr, 3)}
    for k in scope:
        for n in kinds:
            ns = [score(c) for c in neg[k].get(n, []) if c["ink_in"] >= 0.23]
            if ns:
                res[f"{k}:{n}"] = round(sum(1 for v in ns if (v > thr if higher_is_bad else v < thr)) / len(ns), 3)
    return res
out["rules"] = {
    "garbled:f_ok1": rule_eval("f", lambda c: c["f_ok1"], False, GARB),
    "garbled:r1": rule_eval("r", lambda c: c["r1"], False, GARB),
    "garbled:min(f1,r1+0.1)": rule_eval("m", lambda c: min(c["f_ok1"], c["r1"] + 0.1), False, GARB),
    "garbled:f1*r1": rule_eval("fr", lambda c: c["f_ok1"] * c["r1"], False, GARB),
    "extra:far_area": rule_eval("fa", lambda c: c["far_area"], True, DBL),
    "extra:ink_out": rule_eval("io", lambda c: c["ink_out"], True, DBL),
    "extra:ext_cols": rule_eval("ec", lambda c: c["ext_cols"], True, DBL),
}
for k in ("event", "regular"):
    pv = [c for c in pos[k] if (c["project"], c["t"]) not in TRUE_DEFECT]
    out[f"pos_{k}_f_ok1_min5"] = sorted(round(c["f_ok1"], 3) for c in pv)[:5]
    out[f"pos_{k}_far_area_max5"] = sorted((round(c["far_area"], 3) for c in pv), reverse=True)[:5]
(D / "v7_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k.startswith(("rules","pos_","n_","event","known"))}, ensure_ascii=False, indent=0))
