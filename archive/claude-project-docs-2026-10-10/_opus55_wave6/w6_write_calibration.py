"""כתיבת תוצאות גל 6 לקובץ הכיול של caption_vision — מהמדידות עצמן (לא מספרים ידניים)."""
import json, sys
from pathlib import Path
S = Path(sys.argv[1]); D = S / "_opus55_wave6"
CAL = S / "tools" / "caption-vision-calibration.json"
doc = json.loads(CAL.read_text(encoding="utf-8"))
a3 = json.loads((D / "v7_analysis3.json").read_text(encoding="utf-8"))
a2 = json.loads((D / "v7_analysis2.json").read_text(encoding="utf-8"))
a1 = json.loads((D / "v7_analysis.json").read_text(encoding="utf-8"))
THR = 0.30
row = a3["grid"][str(THR)]
worst = row["worst"][0]
assert worst[0] < 3, worst                      # FP=0 ברמת הסרטון עם min_hits=3
assert min(row["catch"]["scrambled"], row["catch"]["wrong_word"]) >= 0.95, row["catch"]
p = doc["params"]
p["g1_max"] = THR
if "garbled_cue" not in p["blocking"]:
    p["blocking"].append("garbled_cue")
p.setdefault("min_hits", {})["garbled_cue"] = 3
ev = doc["evidence"]
ev["pos_false_garbled_cue"] = 0.0
ev["garbled_cue_w6"] = {
    "date": "2026-09-23", "metric": "g1 = f_ok1 × r1 (סבולת 1px)", "g1_max": THR, "min_hits": 3,
    "positives": f"{a3['n_cues']} cues — כל ה-cues של {a3['n_videos'] - 1} FINAL חיים (13 Throwdown), בלי קניות-v2",
    "worst_live_video": {"cues_below": worst[0], "project": worst[1], "n_cues": worst[2]},
    "videos_with_any_cue_below": row["videos_with_1plus"],
    "next_step_thr_0.31_worst": a3["grid"]["0.31"]["worst"][0][0],
    "catch_per_cue_injection": row["catch"],
    "known_bad_kniyot_v2": row["known_bad"],
    "true_defect_hahavana_39_25_g1": a3["true_defect_g1"],
    "why_not_f_ok1": "f_ok1 לבד: החיובי הנמוך 0.512 (דרג-לי 'דני', רקע אירוע) מתחת ל-p95 של שליליים — "
                     "רקע אדום-לבן מוריד precision; recall לא נפגע. g1 שוקל recall.",
    "stale_prev_not_caught": "מילה קודמת שלא נוקתה (חפיפה במקום) — 0.13% נתפס; כשל אחר, לא garbled",
    "evidence": "_opus55_wave6/v7_full.*.jsonl · v7_rows.*.jsonl · w6_v7_analyze3.py",
}
ev["extra_ink_components_w6"] = {
    "date": "2026-09-23", "verdict": "נמדד ונפל — לא נכנס לקוד",
    "metric": "רכיב מחובר של דיו-כתובית (שטח ≥15% מהצפוי) מחוץ ל-bbox הצפוי ±24px",
    "fp0_threshold_far_area": a1["rules"]["extra:far_area"]["thr_at_fp0"],
    "catch_at_fp0": {k: v for k, v in a1["rules"]["extra:far_area"].items() if ":" in k},
    "ink_out_catch_at_fp0": {k: v for k, v in a1["rules"]["extra:ink_out"].items() if ":" in k},
    "combined_catch": a2["extra_combined"],
    "why": "החיוביים עם רכיב רחוק הם לוגו R.E.L על חולצת המועדון (לבן במתאר אדום) ורצועות יד — "
           "נבדק בעין (extra_far_pos_sheet.jpg). כפילות שחופפת את המילה מתמזגת לרכיב אחד.",
}
ev["face_eyes_w6"] = {
    "date": "2026-09-23", "haar_hits": 35, "cues": 3656, "videos": 50,
    "true_by_eye": 4, "eyes_ge2": {"tp": 4, "fp": 0},
    "dynamic_marginv": "marginv 330 מנקה 4/4 האמיתיות — כולן ב-2 שניות סלפי של סרטון אחד (1/50). "
                       "לא מומש: 4 cues מ-3,656, ומחיר של קפיצת מיקום; הגלאי המאומת מדווח אותם ל-P20",
    "evidence": "_opus55_wave6/face_rows.json · face_eyes.json · face_sheet_0.jpg",
}
doc["measured_at_w6"] = "2026-09-23"
CAL.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", p["blocking"], p["g1_max"], worst)
