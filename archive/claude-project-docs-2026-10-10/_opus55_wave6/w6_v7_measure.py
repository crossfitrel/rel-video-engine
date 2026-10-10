"""גל 6 (v9.34) — מדידת V7 לפני תיקון: garbled על רקעי אירוע + מדד extra_ink חדש.

קריאה בלבד (write=False). לכל FINAL חי: מדדים מורחבים פר-cue (חיוביים).
לכל פרויקט עם EXPORT 9:16: הזרקות על אותו רקע (שליליים), כולל כפילות רחוקה.
פלט: JSONL פר-פרויקט ב-_opus55_wave6/v7_rows.jsonl (ניתן להמשיך אחרי קריסה).

  $P _opus55_wave6/w6_v7_measure.py SYSTEM_DIR [--per-video 60] [--neg-per-video 30]
"""
import sys, json, time, os
from pathlib import Path
S = Path(sys.argv[1]); sys.path.insert(0, str(S / "tools"))
import numpy as np, cv2
import caption_vision as cv
from captions_build import group_cues, load_words
from PIL import ImageFont

PER = int(sys.argv[sys.argv.index("--per-video") + 1]) if "--per-video" in sys.argv else 60
NEG = int(sys.argv[sys.argv.index("--neg-per-video") + 1]) if "--neg-per-video" in sys.argv else 30
SH = sys.argv[sys.argv.index("--shard") + 1] if "--shard" in sys.argv else "0/1"
SK, SN = (int(x) for x in SH.split("/"))
POS_ONLY = "--pos-only" in sys.argv
OUT = S / "_opus55_wave6" / (f"v7_full.{SK}.jsonl" if POS_ONLY else f"v7_rows.{SK}.jsonl")
R = Path.home() / "rel-video-work"
SKIP = {"טרה-ראן-באיזה-מקום-תסיים-לפני-הריצה", "אחרי-הריצה-איך-היה", "מי-יסיים-מקום-אחד-מעליך"}  # תביעות rerun
WORDS_OVERRIDE = {"טיפ-אחד-HSPU": "words_final3.json"}   # נמדד בגל 1
cfg = cv.load_calibration()
OUTL = {"club": cv.co.BRAND_PROFILES["club"]["outline"][:3],
        "personal": cv.co.BRAND_PROFILES["personal"]["outline"][:3]}


def prf(obs, exp, region, tol):
    o = obs & region
    no, ne = int(o.sum()), int(exp.sum())
    if no == 0 or ne == 0:
        return 0.0, 0.0
    p = float((o & cv._dil(exp, tol)).sum()) / no
    r = float((exp & cv._dil(o, tol)).sum()) / ne
    return round(p, 3), round(r, 3)


def extras(band, text, g, W, used, obs_all):
    a_ok, bb, w_ok = cv.render_mask(text, g, W, "rtl")
    a_rev, _, _ = cv.render_mask(text, g, W, "reversed")
    region = cv._dil(a_ok | a_rev, cv.REGION_PAD)
    obs, obs_w = obs_all[used], obs_all[used + ":fill"]
    exp_area = max(1, int(a_ok.sum()))
    p1, r1 = prf(obs_w, w_ok, region, 1)
    p3, r3 = prf(obs_w, w_ok, region, 3)
    # רכיבים מחוברים של דיו-כתובית (מתאר+מילוי) ברצועה כולה
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv._dil(obs, 2).astype(np.uint8), 8)
    x0, _, x1, _ = bb
    comps, far = [], []
    for k in range(1, n):
        area = int((obs & (lab == k)).sum())
        if area < 0.15 * exp_area:
            continue
        cx0, cw = int(st[k, 0]), int(st[k, 2])
        comps.append(round(area / exp_area, 3))
        if cx0 + cw < x0 - 24 or cx0 > x1 + 24:
            far.append(round(area / exp_area, 3))
    colsum = obs.sum(axis=0)
    ext = int(((colsum >= 4) & ((np.arange(W) < x0 - 24) | (np.arange(W) > x1 + 24))).sum())
    return {"p1": p1, "r1": r1, "p3": p3, "r3": r3, "n_comp": len(comps), "n_far": len(far),
            "far_area": max(far) if far else 0.0, "ext_cols": round(ext / max(1, x1 - x0), 3),
            "exp_w": int(x1 - x0)}


def positives(W):
    wf = WORDS_OVERRIDE.get(W.name)
    video, words, brand, intro = cv.project_inputs(W, words=(W / wf) if wf else None)
    cues = group_cues(load_words(str(words)))
    cap = cv2.VideoCapture(str(video)); Wv = int(cap.get(3)); Hv = int(cap.get(4)); cap.release()
    g = cv.geometry(cues, Wv, Hv, brand)
    if intro is None:
        intro, _ = cv.estimate_offset(video, cues, g)
    idx = [i for i, c in enumerate(cues) if c["end"] - c["start"] >= 0.07]
    if PER and len(idx) > PER:
        st = len(idx) / float(PER); idx = [idx[int(k * st)] for k in range(PER)]
    times = [intro + (cues[i]["start"] + cues[i]["end"]) / 2 for i in idx]
    frames, _ = cv.sample_frames(video, times)
    want = "personal" if cv.co.BRAND_ALIASES.get(brand, brand) == "personal" else "club"
    rows = []
    for i, t, fr in zip(idx, times, frames):
        if fr is None:
            continue
        band = fr[g["y0"]:g["y0"] + g["band_h"]]
        oa = cv.ink_mask(band, OUTL)
        other = "club" if want == "personal" else "personal"
        used = other if int(oa[other].sum()) > 2 * max(1, int(oa[want].sum())) else want
        m = cv.score_cue(band, cues[i]["text"], g, Wv, used, oa, cfg)
        m.update(extras(band, cues[i]["text"], g, Wv, used, oa))
        m["flags"] = cv.classify(m, cues[i]["text"], Wv, cfg, [])
        rows.append({"kind": "pos", "t": round(t, 2), "text": cues[i]["text"], **m})
    return rows, brand


def negatives(W, brand):
    wf = WORDS_OVERRIDE.get(W.name)
    words = (W / wf) if wf else W / "words_final.json"
    clean = W / "EXPORT.mp4"
    cues = group_cues(load_words(str(words)))
    cap = cv2.VideoCapture(str(clean)); Ws = int(cap.get(3)); Hs = int(cap.get(4)); cap.release()
    if not Ws or abs(Ws / float(Hs) - 1080 / 1920.0) > 0.02:
        return []
    Wv, Hv = 1080, 1920
    g = cv.geometry(cues, Wv, Hv, brand)
    want = "personal" if cv.co.BRAND_ALIASES.get(brand, brand) == "personal" else "club"
    idx = [i for i, c in enumerate(cues) if c["end"] - c["start"] >= 0.07]
    if len(idx) > NEG:
        st = len(idx) / float(NEG); idx = [idx[int(k * st)] for k in range(NEG)]
    frames, _ = cv.sample_frames(clean, [(cues[i]["start"] + cues[i]["end"]) / 2 for i in idx])
    alt = str(S / "tools" / "thumbnail" / "fonts" / "PloniBold.otf")
    altf = ImageFont.truetype(alt, g["font"].size) if os.path.exists(alt) else None
    rows = []
    for k, (i, fr) in enumerate(zip(idx, frames)):
        if fr is None:
            continue
        if fr.shape[1] != Wv:
            fr = cv2.resize(fr, (Wv, Hv), interpolation=cv2.INTER_AREA)
        bg = fr[g["y0"]:g["y0"] + g["band_h"]]
        text = cues[i]["text"]; other = cues[idx[(k + 7) % len(idx)]]["text"]
        letters = text.replace(" ", "")
        scr = (text[1:] + text[0]) if len(letters) >= 3 else None
        _, bb, _ = cv.render_mask(text, g, Wv, "rtl"); _, bbo, _ = cv.render_mask(other, g, Wv, "rtl")
        wt, wo = bb[2] - bb[0], bbo[2] - bbo[0]
        dfar = -int(wt / 2 + wo / 2 + 60)
        var = {
            "synthetic_ok": cv._composite(bg, text, g, Wv),
            "reversed": cv._composite(bg, text, g, Wv, "reversed"),
            "tofu": cv._composite(bg, "□" * max(1, len(letters)), g, Wv),
            "scrambled": cv._composite(bg, scr, g, Wv) if scr and scr != text else None,
            "wrong_word": cv._composite(bg, other, g, Wv) if other != text else None,
            "wrong_font": cv._composite(bg, text, g, Wv, font=altf) if altf else None,
            "doubled": cv._composite(cv._composite(bg, text, g, Wv), other, g, Wv, dx=-260),
            "doubled_far": cv._composite(cv._composite(bg, text, g, Wv), other, g, Wv, dx=dfar),
            "stale_prev": cv._composite(cv._composite(bg, other, g, Wv), text, g, Wv),  # מילה קודמת לא נוקתה
        }
        for name, band in var.items():
            if band is None:
                continue
            oa = cv.ink_mask(band, OUTL)
            m = cv.score_cue(band, text, g, Wv, want, oa, cfg)
            m.update(extras(band, text, g, Wv, want, oa))
            rows.append({"kind": name, "text": text, **m})
    return rows


done = set()
if OUT.exists():
    for ln in OUT.read_text(encoding="utf-8").splitlines():
        try:
            done.add(json.loads(ln)["project"])
        except Exception:
            pass
cands = sorted(p.parent for p in R.glob("*/FINAL.mp4") if (p.parent / "words_final.json").exists()
               and not p.parent.name.startswith("_") and p.parent.name not in SKIP)
for j, W in enumerate(cands):
    if j % SN != SK:
        continue
    if W.name in done:
        continue
    t0 = time.time()
    try:
        man = json.loads((W / "project_manifest.json").read_text(encoding="utf-8"))
    except Exception:
        man = {}
    try:
        pos, brand = positives(W)
        neg = negatives(W, brand) if (W / "EXPORT.mp4").exists() and not POS_ONLY else []
    except Exception as e:
        print(W.name, "ERR", repr(e), flush=True); continue
    rec = {"project": W.name, "department": man.get("department"), "brand": brand,
           "pos": pos, "neg": neg, "sec": round(time.time() - t0, 1)}
    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(W.name, len(pos), len(neg), rec["sec"], flush=True)
print("DONE", flush=True)
