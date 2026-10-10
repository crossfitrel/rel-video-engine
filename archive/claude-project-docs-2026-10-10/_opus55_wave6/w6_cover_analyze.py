"""ניתוח cover_rows.json — ייחוס ברמת מילה: כותרת (Assistant) מול תת-כותרת (Studentit)."""
import json, sys
from pathlib import Path
D = Path(sys.argv[1]) / "_opus55_wave6"
d = json.loads((D / "cover_rows.json").read_text(encoding="utf-8"))
title_of = {p["w"]: p["title"] for p in d["pos"]}
sub_of = {p["w"]: p["sub"] for p in d["pos"]}
out = {}


def heb_min(r, text, key):
    ws, sc = text.split(" "), r.get(key) or []
    if len(ws) != len(sc):
        return None
    v = [s for w, s in zip(ws, sc) if not any(c.isascii() and c.isalnum() for c in w)]
    return min(v) if v else None


pos = [p for p in d["pos"] if p.get("n_lines") == 2]
for line, key, txt in (("title", "w_title", title_of), ("sub", "w_sub", sub_of)):
    pv = sorted(x for x in (heb_min(p, txt[p["w"]], key) for p in pos) if x is not None)
    res = {"pos_n": len(pv), "pos_min3": pv[:3]}
    for kind in ("scr_one_title" if line == "title" else "scr_one_sub", "scr_all"):
        rows = [r for r in d["neg"][kind] if r.get("n_lines") == 2]
        nv = sorted(x for x in (heb_min(r, txt[r["w"]], key) for r in rows) if x is not None)
        thr = pv[0] if pv else None
        res[kind] = {"n": len(nv), "p50": nv[len(nv) // 2] if nv else None, "max3": nv[-3:],
                     "catch_below_pos_min": (sum(1 for v in nv if v < thr), len(nv)) if thr else None,
                     "line_level_flag": sum(1 for r in rows if any(f.startswith(("garbled_" + line, "reversed_" + line))
                                                                   for f in (r.get("flags") or [])))}
    out[line] = res
(D / "cover_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
