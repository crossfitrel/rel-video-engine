#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""visual_hook_calibration.py — דוגמאות כיול לפיילוט (11.9.26). לא תוצר פרסום, לא משנה מדיניות.

המעטפת והיוריסטיקות ב-visual_hook_policy.json מסומנות calibrated:false. כדי שהראל
יכייל אותן על דוגמאות אמיתיות ולא על ניחוש, הכלי לוקח פרויקטים מהסריקה שנפסלו
**רק** על סף לא-מכויל (unsafe_crop / semantic_unknown — כל שאר הבדיקות עברו),
מרפה את הסף בזיכרון בלבד, בסולם מהעדין לחזק, ומרנדר תצוגת גוף 12ש על העותק:
  probe  → calibration_probe.json (מה חורג ובכמה, איזו הרפיה מספיקה)
  render → comparisons/כיול/NN_<שם>/ צד-בצד + פריים-שיא, ו-comparisons/כיול/כיול.json
  variant <שם> <scale> → אותו פרויקט מאושר בעוצמה אחרת (תצוגת גוף)
פסילות מוגנות (פתיח, כניסה מכוונת, כמה אנשים, בירול, קאט, תנועת מצלמה קיימת) לא
מורפות לעולם — שם NO_OP הוא ההחלטה הנכונה ולא סף שמחכה לכיול.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
SYSDIR = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))
from relvid.paths import work_root              # noqa: E402
from relvid import visual_hook as VH            # noqa: E402
from relvid import hook_render as HR            # noqa: E402
import visual_hook_compare as CMP               # noqa: E402

SCAN = work_root() / ".e2e" / "visual-hook" / "scan"
OUT = SYSDIR / "handoff" / "visual-hook-engine" / "comparisons" / "כיול"
CALIBRATABLE = {"unsafe_crop", "semantic_unknown"}

LADDER = {
    "unsafe_crop": [
        ("margin0", "בלי שוליים (0 במקום 3%)"),
        ("head_only", "רק הראש מוגן — ידיים/גוף מותר שייחתכו בשוליים"),
        ("head_only_margin0", "רק הראש מוגן ובלי שוליים"),
    ],
    "semantic_unknown": [
        ("faces50", "מספיק פנים יחידות ב-50% מהדגימות (במקום 70%)"),
        ("faces40", "מספיק פנים יחידות ב-40% מהדגימות"),
    ],
}


def relaxed(policy, analysis, step):
    pol, ana = copy.deepcopy(policy), analysis
    env, heur = pol["crop_envelope"], pol["eligibility_heuristics"]
    if step in ("margin0", "head_only_margin0"):
        env["margin_frac"] = 0.0
    if step.startswith("head_only"):
        ana = copy.deepcopy(analysis)
        ana["measurements"]["motion_boxes_15f"] = []
    if step == "faces50":
        heur["min_single_face_ratio"] = 0.5
    if step == "faces40":
        heur["min_single_face_ratio"] = 0.4
    return pol, ana


def overflow(analysis, cand, policy):
    """לכל מסגרת במעטפת: בכמה (שבר מהפריים) הראש / מעטפת התנועה חורגים מהמסגרת."""
    meas = analysis["measurements"]
    anchor = (analysis.get("hook") or {}).get("anchor")
    if not anchor:
        return None
    peak = int(round(anchor["start"] * VH.FPS))
    start, end = peak - 15, peak + 60
    faces = [x for x in meas.get("faces") or [] if start <= x["frame"] < end]
    heads = [VH._head_box(fb) for x in faces for fb in x["boxes"]]
    mb = meas.get("motion_boxes_15f") or []
    motion = [mb[i] for i in range(start // 15, min(len(mb), (end + 14) // 15)) if mb[i]]
    if not heads:
        return None
    cs = sorted((fb[0] + fb[2] / 2, fb[1] + fb[3] / 2) for x in faces for fb in x["boxes"])
    fcx, fcy = cs[len(cs) // 2]

    def over(boxes, r):
        return max([max(r[0] - b[0], r[1] - b[1], b[0] + b[2] - (r[0] + r[2]), b[1] + b[3] - (r[1] + r[3]), 0.0)
                    for b in boxes] or [0.0])
    rows = []
    for s in (1.06, 1.04):
        for cx, cy, tag in ((0.5, 0.5, "center"), (0.5, fcy, "face_vertical"), (fcx, fcy, "face")):
            r = VH.crop_rect(s, cx, cy)
            rows.append({"scale": s, "center": tag, "head_over": round(over(heads, r), 4),
                         "motion_over": round(over(motion, r), 4)})
    return min(rows, key=lambda x: (x["head_over"], x["motion_over"]))


def probe() -> dict:
    scan = json.loads((SCAN / "scan_results.json").read_text(encoding="utf-8"))
    reg, pol = VH.load_registry(), VH.load_policy()
    out = []
    for row in scan:
        rs = set(row.get("crop_reasons") or [])
        if row.get("suggestion") != "NO_OP" or not rs or not rs <= CALIBRATABLE:
            continue
        wd = SCAN / row["project"]
        ctx = VH.build_context(wd, policy=pol)
        ana = VH.analyze(ctx, pol)
        base = next(c for c in VH.discover(ctx, ana, reg, pol) if c["recipe"] == "SMART_PUNCH_IN")
        rec = {"project": row["project"], "reasons": sorted(rs), "overflow": overflow(ana, base, pol),
               "relaxation": None, "relaxation_he": None, "candidate": None}
        for reason in sorted(rs):
            for step, he in LADDER[reason]:
                p2, a2 = relaxed(pol, ana, step)
                c = next(x for x in VH.discover(ctx, a2, reg, p2) if x["recipe"] == "SMART_PUNCH_IN")
                if c["eligible"]:
                    rec.update(relaxation=step, relaxation_he=he, candidate=c)
                    break
                left = set(c["reason_codes"]) - CALIBRATABLE
                if left:
                    rec["blocked_after_relax"] = sorted(left)
                    break
            if rec["candidate"]:
                break
        print(json.dumps({k: v for k, v in rec.items() if k != "candidate"}, ensure_ascii=False))
        out.append(rec)
    doc = {"n": len(out), "rows": out}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "calibration_probe.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def _render(idx, name, wd, ctx, ana, cand, label_left, file_tag, extra):
    stem = f"{idx:02d}_{name}"
    d = OUT / stem
    d.mkdir(parents=True, exist_ok=True)
    plan = VH.make_plan(ctx, ana, cand, {"actor": "harel", "reason_codes": ["operator_selected"]})
    errs = VH.validate_plan(plan, ctx, VH.load_registry())
    if errs:
        raise VH.HookError("HOOK_PLAN_INVALID", "; ".join(errs))
    body = VH.resolve_body(wd)
    A, B = d / f"{stem}__A_מקור.mp4", d / f"{stem}__B_{file_tag}.mp4"
    CMP.ff("-i", body, "-t", "12", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", A)
    HR.render_preview(body, plan, B, seconds=12.0)
    hdr = d / "_hdr.png"
    CMP.header_png(hdr, "מקור", label_left)
    CMP.ff("-i", A, "-i", B, "-loop", "1", "-i", hdr, "-filter_complex",
           "[0:v]scale=540:960[a];[1:v]scale=540:960[b];[b][a]hstack=inputs=2[s];[2:v]scale=1080:96,format=yuv420p[h];"
           "[h][s]vstack=inputs=2[v]", "-map", "[v]", "-map", "0:a", "-t", "12", "-c:v", "libx264", "-crf", "20",
           "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
           d / f"{stem}__צד-בצד.mp4")
    hdr.unlink(missing_ok=True)
    cue = plan["cues"][0]
    peak = cue["keyframes"][1]["frame"] + 8
    CMP.still_pair(A, B, peak, VH.rect_at(cue, peak), d / f"{stem}__פריים-שיא.jpg", left_label=label_left)
    (d / f"{stem}__plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    anchor = (ana.get("hook") or {}).get("anchor") or {}
    return {"idx": idx, "name": name, "dir": stem, "scale": round(1 / cue["keyframes"][1]["rect"][2], 3),
            "center": cand["params"].get("center"),
            "window_sec": [round(cue["start_frame"] / 30, 2), round(cue["end_frame"] / 30, 2)],
            "anchor": anchor.get("word"), "plan_digest": plan["plan_digest"], "publishable": False, **extra}


def render(limit=None) -> dict:
    probe_doc = json.loads((OUT / "calibration_probe.json").read_text(encoding="utf-8"))
    reg, pol = VH.load_registry(), VH.load_policy()
    built, idx = [], 0
    rows = [r for r in probe_doc["rows"] if r.get("relaxation")]
    order = {s: i for L in LADDER.values() for i, (s, _) in enumerate(L)}
    rows.sort(key=lambda r: (order[r["relaxation"]], r["project"]))
    for r in rows[:limit]:
        idx += 1
        wd = SCAN / r["project"]
        ctx = VH.build_context(wd, policy=pol)
        ana = VH.analyze(ctx, pol)
        p2, a2 = relaxed(pol, ana, r["relaxation"])
        cand = next(x for x in VH.discover(ctx, a2, reg, p2) if x["recipe"] == "SMART_PUNCH_IN")
        built.append(_render(idx, r["project"], wd, ctx, ana, cand, "גבולי · לכיול", "גבולי",
                             {"kind": "calibration", "rejected_for": r["reasons"], "relaxation": r["relaxation"],
                              "relaxation_he": r["relaxation_he"], "overflow": r["overflow"]}))
        print(json.dumps(built[-1], ensure_ascii=False))
    doc = {"built": built, "probe_n": probe_doc["n"]}
    (OUT / "כיול.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def variant(project: str, scale: float, idx: int = 90) -> dict:
    reg, pol = VH.load_registry(), copy.deepcopy(VH.load_policy())
    pol["crop_envelope"]["peak_scale_candidates"] = [float(scale)]
    wd = SCAN / project
    ctx = VH.build_context(wd, policy=VH.load_policy())
    ana = VH.analyze(ctx, VH.load_policy())
    cand = next(x for x in VH.discover(ctx, ana, reg, pol) if x["recipe"] == "SMART_PUNCH_IN")
    if not cand["eligible"]:
        raise SystemExit(f"{project} @×{scale}: {cand['reason_codes']}")
    res = _render(idx, f"{project}-×{scale}", wd, ctx, ana, cand, "הדגשה עדינה יותר", f"הדגשה-{scale}",  # בלי ספרות בכותרת: PIL בלי raqm הופך אותן
                  {"kind": "variant", "project": project})
    p = OUT / "כיול.json"
    doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"built": []}
    doc["built"] = [b for b in doc["built"] if b["dir"] != res["dir"]] + [res]
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if cmd == "probe":
        probe()
    elif cmd == "render":
        render(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif cmd == "variant":
        variant(sys.argv[2], float(sys.argv[3]))
