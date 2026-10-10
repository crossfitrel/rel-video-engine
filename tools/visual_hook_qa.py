#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual_hook_qa.py — QA מבוסס-קבלה לפתיחה חזותית (11.9.26).
==========================================================
השאלה כאן אינה "האם יש קפיצת סצנה" (G8 הישן שואל את זה, ונשאר בדיוק כמו
שהוא) אלא "האם מה שעל המסך הוא **מה שהתוכנית המאושרת אמרה**, ולא יותר".

הכלל שנולד מלקח הראל 19.7 (פלאש בשנייה הראשונה) ומלקחי ההבהוב 25.7:
**מעבר מוצהר לעולם אינו פוטר תקלה.** פריים שחור/לבן בודד, A→B→A של פריים
אחד, או תמונה ממקור לא נכון — נבדקים *גם* בנקודת מעבר מוצהרת.

ההשוואה היא מול המקור הנקי (EXPORT) דרך הטרנספורם של התוכנית עצמה, ולכן
חשכה שהגיעה מהצילום נחשבת "בירושה" ולא נענשת.

שערים (שמות קבועים — נסרקים ע"י gate_registry --audit):
  VH1_receipt_valid · VH2_frame_count · VH3_audio_preserved ·
  VH4_picture_matches_plan · VH5_introduced_flash · VH6_transition_events ·
  VH7_plan_contract · VH8_review_binding

שימוש:
  python3 visual_hook_qa.py --clean EXPORT_TIGHT.mp4 --video FINAL_PENDING.mp4 \
      --plan visual_hook_plan.json [--receipt visual_hook_render.json] \
      [--intro-frames 0] [--band-y0 1300 --band-h 300] [--out visual_hook_qa.json]
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from relvid import visual_hook as VH          # noqa: E402

QW, QH = 270, 480          # רזולוציית בדיקה (רבע) — תקלות פריים-שלם גלויות בה בבירור
PAD = 15                   # שכנות סביב ה-cue שנבדקת גם היא


def _decode(path, start, count):
    import numpy as np
    vf = f"select=gte(n\\,{int(start)}),scale={QW}:{QH}:flags=area,format=gray"
    r = subprocess.run([VH.ffbin(), "-nostdin", "-loglevel", "error", "-i", str(path),
                        "-vf", vf, "-fps_mode", "passthrough", "-frames:v", str(int(count)),
                        "-f", "rawvideo", "-"], capture_output=True, timeout=900)
    if r.returncode != 0:
        return None
    a = np.frombuffer(r.stdout, dtype=np.uint8)
    k = a.size // (QW * QH)
    return a[:k * QW * QH].reshape(k, QH, QW)


def _warp(frame, rect):
    import numpy as np
    import cv2
    s = 1.0 / rect[2]
    M = np.array([[s, 0, -rect[0] * QW * s], [0, s, -rect[1] * QH * s]], dtype=np.float64)
    return cv2.warpAffine(frame, M, (QW, QH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def check(clean, video, plan, receipt=None, *, intro_frames=0, band=None,
          approved_digest=None, reservations=None, final_stage=True) -> dict:
    import numpy as np
    gates = []

    def gate(name, ok, detail, hard=True):
        gates.append({"gate": name, "pass": bool(ok), "hard": bool(hard), "detail": detail})

    # VH7 — חוזה התוכנית (צורה) לפני כל מדידה
    errs = VH.validate_plan_shape(plan)
    if plan.get("plan_digest") != VH.digest_plan(plan):
        errs.append("plan_digest אינו תואם לתוכן")
    gate("VH7_plan_contract", not errs, "; ".join(errs) or "תוכנית תקפה")
    # VH8 — התוכנית שהוחלה היא זו שאושרה (כשיש אישור)
    if approved_digest is not None:
        gate("VH8_review_binding", approved_digest == plan.get("plan_digest"),
             f"מאושר {str(approved_digest)[:19]} · הוחל {str(plan.get('plan_digest'))[:19]}")
    # VH1 — קבלת הרינדור קשורה לתוכנית
    if receipt is not None:
        ok = receipt.get("plan_digest") == plan.get("plan_digest") and \
            receipt.get("renderer") in ("v1", "v2") and receipt.get("abi")
        if ok and receipt.get("renderer") == "v1" and (receipt.get("output") or {}).get("encoded"):
            op = (receipt.get("output") or {}).get("path")
            if op and Path(op).exists() and not final_stage:
                ok = VH.file_sha256(op) == receipt["output"].get("sha256")
        gate("VH1_receipt_valid", ok, f"renderer={receipt.get('renderer')} abi={receipt.get('abi')}")
        # VH3 — אודיו
        au = receipt.get("audio") or {}
        if receipt.get("applied") is False:
            gate("VH3_audio_preserved", True, "NO_OP — אין קידוד, האודיו הוא המקור עצמו")
        elif receipt.get("renderer") == "v1":
            gate("VH3_audio_preserved", bool(au.get("equal")), f"md5 בתוך {au.get('input_md5')} · אחרי {au.get('output_md5')}")
        else:
            gate("VH3_audio_preserved", bool(au.get("chain_unchanged")),
                 "v2: שרשרת האודיו של הסגמנטים זהה לזו שבלי התוכנית")
    else:
        gate("VH1_receipt_valid", False, "אין קבלת רינדור — אין פטור לשום אירוע צפוי")
    if errs:
        return _finish(gates, [], 0)

    tl = plan["timeline"]
    pv = VH.probe_video(video)
    want = tl["frame_count"] + int(intro_frames)
    tol = 1 if final_stage else 0
    gate("VH2_frame_count", abs(pv["frame_count"] - want) <= tol,
         f"פוענחו {pv['frame_count']} · צפוי {want} (גוף {tl['frame_count']} + פתיח {intro_frames})")
    if plan["recipe"] == "NO_OP" or not plan["cues"]:
        gate("VH4_picture_matches_plan", True, "NO_OP — אין טיפול לבדוק", hard=True)
        gate("VH5_introduced_flash", True, "NO_OP", hard=True)
        return _finish(gates, [], 0)

    c0 = min(c["start_frame"] for c in plan["cues"])
    c1 = max(c["end_frame"] for c in plan["cues"])
    a = max(0, c0 - PAD)
    b = min(tl["frame_count"], c1 + PAD)
    cl = _decode(clean, a, b - a)
    tv = _decode(video, a + int(intro_frames), b - a)
    if cl is None or tv is None or len(cl) < (b - a) or len(tv) < (b - a):
        gate("VH4_picture_matches_plan", False, "פענוח חלון הבדיקה נכשל או קצר")
        return _finish(gates, [], 0)
    mask = np.ones((QH, QW), dtype=bool)
    if band:
        y0 = int(band["y0"] * QH / 1920)
        y1 = int((band["y0"] + band["h"]) * QH / 1920) + 1
        mask[max(0, y0):min(QH, y1), :] = False
    excl = set()
    for r in reservations or []:
        excl |= set(range(r["start_frame"], r["end_frame"]))

    def rect_for(f):
        for c in plan["cues"]:
            if c["start_frame"] <= f < c["end_frame"]:
                return VH.rect_at(c, f)
        return VH.IDENTITY

    exp = {}
    for i in range(len(cl)):
        f = a + i
        exp[f] = _warp(cl[i], rect_for(f)) if rect_for(f) != VH.IDENTITY else cl[i]
    errs_f = []
    zoom_frames, not_applied = 0, 0
    for i in range(len(tv)):
        f = a + i
        if f in excl:
            errs_f.append(None)
            continue
        t = tv[i].astype(np.int16)
        cands = [exp[g] for g in (f - 1, f, f + 1) if g in exp]      # ±1 פריים — כימות חותמות זמן בלבד
        e_exp = min(float(np.abs(t - e.astype(np.int16))[mask].mean()) for e in cands)
        errs_f.append(e_exp)
        # "מוגדר ≠ עובד": בפריים עם זום ממשי, התמונה חייבת להיות קרובה לטרנספורם
        # יותר מאשר למקור הלא-מטופל. אחרת הטיפול לא הוחל (או הוחל אחר).
        if rect_for(f)[2] < 0.985:
            visible = float(np.abs(exp[f].astype(np.int16) - cl[i].astype(np.int16))[mask].mean())
            if visible > 0.8:                 # הזום באמת משנה את התמונה בפריים הזה
                zoom_frames += 1
                e_id = float(np.abs(t - cl[i].astype(np.int16))[mask].mean())
                if e_exp >= 0.9 * e_id:
                    not_applied += 1
    vals = [e for e in errs_f if e is not None]
    med = sorted(vals)[len(vals) // 2] if vals else 0.0
    thr = max(10.0, 4.0 * med)
    bad = [a + i for i, e in enumerate(errs_f) if e is not None and e > thr]
    missing = zoom_frames >= 5 and not_applied > zoom_frames // 2
    gate("VH4_picture_matches_plan", not bad and not missing,
         (f"הטיפול לא נראה בתמונה: {not_applied}/{zoom_frames} פריימי זום קרובים למקור יותר מלתוכנית"
          if missing else
          f"סטייה חציונית {med:.2f} · סף {thr:.1f} · פריימים חורגים: {bad[:10]}") if (bad or missing) else
         f"כל {len(vals)} הפריימים בחלון תואמים את הטרנספורם של התוכנית (חציון {med:.2f}; "
         f"{zoom_frames - not_applied}/{zoom_frames} פריימי זום מאומתים)")

    # VH5 — שחור/לבן בודד, A→B→A — על הפלט, מול המקור (ירושה לא נענשת)
    flashes = []
    for i in range(1, len(tv) - 1):
        f = a + i
        if f in excl:
            continue
        m_t = float(tv[i][mask].mean())
        m_c = float(cl[i][mask].mean())
        prev_t, next_t = float(tv[i - 1][mask].mean()), float(tv[i + 1][mask].mean())
        if (m_t < 16 or m_t > 235) and not (m_c < 16 or m_c > 235) and \
                abs(prev_t - m_t) > 30 and abs(next_t - m_t) > 30:
            flashes.append({"frame": f, "kind": "black" if m_t < 16 else "white"})
            continue
        d_prev = float(np.abs(tv[i].astype(np.int16) - tv[i - 1])[mask].mean())
        d_next = float(np.abs(tv[i].astype(np.int16) - tv[i + 1])[mask].mean())
        d_skip = float(np.abs(tv[i + 1].astype(np.int16) - tv[i - 1])[mask].mean())
        c_prev = float(np.abs(cl[i].astype(np.int16) - cl[i - 1])[mask].mean())
        c_next = float(np.abs(cl[i].astype(np.int16) - cl[i + 1])[mask].mean())
        if d_prev > 25 and d_next > 25 and d_skip < 0.35 * min(d_prev, d_next) and \
                not (c_prev > 25 and c_next > 25):
            flashes.append({"frame": f, "kind": "a_b_a_burst"})
    gate("VH5_introduced_flash", not flashes,
         f"תקלות שהוכנסו: {flashes[:6]}" if flashes else "אין פריים שחור/לבן בודד ואין A→B→A שלא היו במקור")

    # VH6 — סיווג אירועי סצנה בחלון מול מעברים מוצהרים (דיווח; התקלות נחסמו ב-VH4/VH5)
    events = []
    declared = {int(t["frame"]): t for t in plan.get("declared_transitions") or []}
    for i in range(1, len(tv)):
        f = a + i
        d_t = float(np.abs(tv[i].astype(np.int16) - tv[i - 1])[mask].mean())
        d_c = float(np.abs(cl[i].astype(np.int16) - cl[i - 1])[mask].mean())
        if d_t < 28:
            continue
        near = [k for k in declared if abs(k - f) <= 1]
        cls = "expected_observed" if near else ("inherited" if d_c >= 0.6 * d_t else "unexpected")
        events.append({"body_frame": f, "final_frame": f + int(intro_frames), "class": cls,
                       "mad": round(d_t, 2)})
    for k in declared:
        if not any(abs(e["body_frame"] - k) <= 1 for e in events):
            events.append({"body_frame": k, "final_frame": k + int(intro_frames),
                           "class": "expected_not_detected", "mad": None})
    unexpected = [e for e in events if e["class"] == "unexpected"]
    gate("VH6_transition_events", not unexpected,
         f"אירועים לא מוצהרים: {unexpected[:5]}" if unexpected else
         f"{len(events)} אירועים בחלון, אף אחד לא מוצהר-חסר-הסבר", hard=False)
    return _finish(gates, events, len(vals), median_err=med)


def _finish(gates, events, n, median_err=None):
    hard_fail = [g for g in gates if g["hard"] and not g["pass"]]
    return {"schema_version": 1, "pass": not hard_fail, "gates": gates, "events": events,
            "frames_checked": n, "median_err": median_err,
            "hard_failures": [g["gate"] for g in hard_fail]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--receipt")
    ap.add_argument("--intro-frames", type=int, default=0)
    ap.add_argument("--band-y0", type=int)
    ap.add_argument("--band-h", type=int)
    ap.add_argument("--approved-digest")
    ap.add_argument("--stage", choices=("base", "final"), default="final")
    ap.add_argument("--out")
    a = ap.parse_args()
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    rec = json.loads(Path(a.receipt).read_text(encoding="utf-8")) if a.receipt else None
    band = {"y0": a.band_y0, "h": a.band_h} if a.band_y0 is not None and a.band_h else None
    rep = check(a.clean, a.video, plan, rec, intro_frames=a.intro_frames, band=band,
                approved_digest=a.approved_digest, final_stage=a.stage == "final")
    if a.out:
        VH.atomic_write_json(a.out, rep)
    for g in rep["gates"]:
        print(f"{'✅' if g['pass'] else ('❌' if g['hard'] else '⚠️ ')} {g['gate']:<26} {g['detail'][:150]}")
    print(json.dumps({"pass": rep["pass"]}, ensure_ascii=False))
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
