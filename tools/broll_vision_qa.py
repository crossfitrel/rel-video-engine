#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_vision_qa.py — הבירולים כפי שהם ב-FINAL, לא כפי שתוכננו (v9.30, 22.9.26)
==============================================================================

שערי הבירול עד היום (broll_brief_gate / seam / sequence) שופטים את **התוכנית**
ואת תוויות הקטלוג. ארבע שאלות שאף אחד מהם לא שאל את הפריים:

  B1 landed     הקליפ שתוכנן באמת על המסך בחלון שלו? (FINAL מול רינדור צפוי של
                הקליפ, ומול הבסיס של הדובר באותו רגע). תוכנית ≠ תוצר — אותה משפחה
                של HSPU (נצרב מקובץ אחר) ושל eof_action (פנים בתפר).
  B2 burned_text הקליפ נושא טקסט גרפי צרוב (שכבה סטטית על מצלמה שזזה) — קאנון 5.
                נמדד על הקליפ במאגר, פעם אחת לקליפ (מטמון mtime|size).
  B3 identity   בירול של הראל בתוכן מועדון (ספריית "הראל חיון" / personal_tags /
                identity=harel? מהאימות הוויזואלי) — הראל 25.7.26.
  B4 anchor     הקליפ מאייר את המשפט שמעליו (L: literal transcript anchor). שיפוט
                מודלי על גיליון פריים+משפט, נשמר כדאטה עם sha של ה-FINAL, בדפוס
                של fix_verify. בלי פסק-דין = "לא נמדד", לא PASS.

מה חוסם — רק מה שנמדד (עקרון 1): הספים ב-broll-vision-calibration.json.

שימוש
-----
  python3 broll_vision_qa.py check --workdir W [--strict]
  python3 broll_vision_qa.py anchor-request --workdir W      # גיליון + request
  python3 broll_vision_qa.py anchor-apply --workdir W        # BROLL_ANCHOR_VERDICT.json
  python3 broll_vision_qa.py scan-pool [--limit N]           # B2 על כל המאגר
  python3 broll_vision_qa.py calibrate W1 W2 ... [--write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
CALIB = HERE / "broll-vision-calibration.json"
CFG = HERE / "broll-catalog-config.json"
OVR = HERE / "broll-tags-override.json"

DEFAULTS = {
    "land_min": 0.55,          # NCC מול הרינדור הצפוי של הקליפ
    "land_margin": 0.10,       # וגבוה ב-X מהדמיון לבסיס של הדובר
    "text_static_min": 0.012,  # שבר שטח של דיו-טקסט סטטי כשהמצלמה זזה
    "source": "default_unmeasured",
    "blocking": [],
}


def load_calibration():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CALIB.read_text(encoding="utf-8")).get("params", {}))
    except Exception:
        pass
    return cfg


# ═══════════════════════════════════════════════════════════════════════
def _frame(path, t):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(round(t * fps))))
    ok, fr = cap.read()
    cap.release()
    return fr if ok else None


def expected_overlay(clip_bgr, W=1080, H=1920):
    """אותו גרף של animation_overlay (--width 1080 --blur 0): רקע cover-crop
    מוחשך 0.12 + חזית ברוחב מלא ממורכזת."""
    h, w = clip_bgr.shape[:2]
    s = max(W / w, H / h)
    bg = cv2.resize(clip_bgr, (int(w * s + .5), int(h * s + .5)))
    y, x = (bg.shape[0] - H) // 2, (bg.shape[1] - W) // 2
    bg = bg[y:y + H, x:x + W].astype(np.int16) - 31
    bg = np.clip(bg, 0, 255).astype(np.uint8)
    fh = max(1, int(h * W / w))
    fg = cv2.resize(clip_bgr, (W, fh))
    out = bg.copy()
    y0 = (H - fh) // 2
    if 0 <= y0 and fh <= H:
        out[y0:y0 + fh] = fg
    else:
        c = (fh - H) // 2
        out[:] = fg[c:c + H]
    return out


_SAMPLES = {}
SAMPLE_STEP_SEC = 0.25     # v9.32 — צפיפות דגימת הקליפ (היה 8 פריימים לכל הקליפ)
SAMPLE_MAX = 160


def clip_samples(path, step=SAMPLE_STEP_SEC, cap_n=SAMPLE_MAX):
    """פריימים לאורך הקליפ כל step שניות (עד cap_n), כבר מוכנים ל-ncc. מטמון לריצה.
    v9.32 (23.9.26): 8 דגימות לקליפ שלם החמיצו את הקליפ הנכון כשהרגע שעל המסך
    נפל בין הדגימות — בקמפיין הקליפ היה על המסך (ncc 0.9999 בהיסט של 0.8ש)
    ונמדד 0.43 ⇒ 'לא נחת' שגוי. קריאה רציפה (בלי seek) — מהירה ומדויקת."""
    k = str(path)
    if k not in _SAMPLES:
        cap = cv2.VideoCapture(k)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        every = max(1, int(round(fps * step)))
        if N and N / every > cap_n:
            every = int(np.ceil(N / cap_n))
        out, j = [], 0
        while True:
            ok = cap.grab()
            if not ok:
                break
            if j % every == 0:
                ok, fr = cap.retrieve()
                if ok:
                    out.append(_prep(expected_overlay(fr)))
            j += 1
        cap.release()
        _SAMPLES[k] = out
    return _SAMPLES[k]


def best_clip_sim(fr, path, exact=None):
    """הדמיון הטוב ביותר בין הפריים לקליפ — ברגע המחושב ולאורך כל הקליפ (כל 0.25ש).
    השאלה היא 'איזה קליפ', לא 'איזו מילישנייה' (22.9.26); v9.32 — דגימה צפופה."""
    pf = _prep(fr)
    sims = [float((pf * x).sum()) for x in clip_samples(path)]
    if exact is not None:
        sims.append(ncc(fr, expected_overlay(exact)))
    return max(sims) if sims else None


WIN_POSITIONS = (0.2, 0.35, 0.5, 0.65, 0.8)


def window_sim(video, t0, s, e, path, exact_at=None, positions=WIN_POSITIONS):
    """v9.32 — B1 מודד כמה רגעים בתוך החלון ולוקח חציון: רגע בודד יכול ליפול על
    מעבר/תפר (2 פריימים של חצייה) או על פריים מטושטש; חציון של 5 עמיד לשניהם."""
    vals = []
    for f in positions:
        t = s + (e - s) * f
        fr = _frame(video, t0 + t)
        if fr is None:
            continue
        ex = exact_at(t) if exact_at else None
        v = best_clip_sim(fr, path, ex)
        if v is not None:
            vals.append(v)
    return (float(np.median(vals)) if vals else None), vals


def _prep(x):
    x = cv2.resize(x, (1080, 1920))[int(1920 * .2):int(1920 * .6)]
    g = cv2.cvtColor(cv2.resize(x, (54, 40), interpolation=cv2.INTER_AREA),
                     cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    g -= g.mean()
    n = np.linalg.norm(g)
    return g / n if n else g


def ncc(a, b):
    """דמיון מבני מוקטן, על רצועת 20%-60% מהגובה (מעל הכתוביות, בלי ה-UI)."""
    return float((_prep(a) * _prep(b)).sum())


def _catalog():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    from animation_overlay import resolve_media   # L162: נתיבי מק → שורש הריפו ב-runner
    cat = json.loads(Path(resolve_media(cfg["catalog_path"])).read_text(encoding="utf-8"))["items"]
    return cfg, {i["file"]: i for i in cat}


def _override():
    try:
        return json.loads(OVR.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _plan(W):
    """מה נצרב בפועל. items_applied במניפסט (נכתב בגימור, v7.6) הוא רשומת התוצר;
    broll_plan.json הוא הכוונה. נמדד 22.9.26: בשני סרטונים מאושרים התוכנית לא
    הוחלה בכלל (items_applied=[]) ובשלישי הקליפ הראשון הושמט (מגן ה-Hook) —
    מדידה מול התוכנית הייתה מדווחת 'לא נחת' על משהו שמעולם לא נועד לנחות."""
    d = {}
    try:
        d = json.loads((Path(W) / "broll_plan.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    plan = [p for p in (d.get("plan") or []) if isinstance(p, dict)]
    try:
        m = json.loads((Path(W) / "project_manifest.json").read_text(encoding="utf-8"))
        fb = (m.get("finish_prefs") or {}).get("broll") or {}
        if "items_applied" in fb:
            applied = [i for i in (fb.get("items_applied") or []) if isinstance(i, dict)]
            # items_applied ישן שמר רק חלק מהשדות — משלימים מהתוכנית לפי file+insert_at
            by = {(Path(p.get("path") or p.get("file") or "").name, p.get("insert_at")): p for p in plan}
            full, seen = [], set()
            for a in applied:
                k = (Path(a.get("path") or a.get("file") or "").name, a.get("insert_at"))
                if k in seen:        # v9.32 — אותה רשומה פעמיים (ממומן-ת1-סטודנטים) נספרה כשני בירולים
                    continue
                seen.add(k)
                full.append(dict(by.get(k, {}), **{x: y for x, y in a.items() if y is not None}))
            d = dict(d, _source="items_applied",
                     _planned_not_applied=max(0, len(plan) - len(full)))
            return full, d
    except Exception:
        pass
    return plan, dict(d, _source="plan")


def _win(it):
    """חלון הבירול — תוכניות ישנות כתבו start/end במקום insert_at/insert_end."""
    s = it.get("insert_at", it.get("start"))
    e = it.get("insert_end", it.get("end"))
    if s is None or e is None:
        return None
    return float(s), float(e)


_CAT_BY_NAME = None


def _clip_path(W, it):
    """נתיב הקליפ; נתיב שזז (קטלוג הועבר — feedback_broll_catalog_stale_path_trap)
    נפתר לפי שם הקובץ מהקטלוג החי."""
    global _CAT_BY_NAME
    raw = (it.get("path") or it.get("file") or "").strip()
    if not raw:
        return Path("/nonexistent")
    p = Path(raw)
    if not p.is_absolute():
        p = Path(W) / p
    if p.exists():
        return p
    from animation_overlay import resolve_media   # L159 (1.11.26): broll_plan מהמק ב-runner של Actions
    rp = Path(resolve_media(str(p)))
    if rp.exists():
        return rp
    if _CAT_BY_NAME is None:
        try:
            _CAT_BY_NAME = {Path(i["path"]).name: i["path"] for i in _catalog()[1].values()}
        except Exception:
            _CAT_BY_NAME = {}
    alt = _CAT_BY_NAME.get(p.name)
    return Path(resolve_media(alt)) if alt else p


def _intro(W):
    """היסט פתיח: FINAL_PROVENANCE; אם לא רשום — מ-CAPTION_VISION.json שכבר אמד אותו
    מהפיקסלים, ואחרת אמידה חיה (caption_vision.estimate_offset). מאסל-מן 1.8.26:
    פתיח 10.1ש שלא נרשם הפיל את שני הבירולים שלו ל'לא נחת'."""
    try:
        prov = json.loads((Path(W) / "FINAL_PROVENANCE.json").read_text(encoding="utf-8"))
        if "intro_offset_sec" in prov:
            return float(prov.get("intro_offset_sec") or 0.0), True
    except Exception:
        pass
    try:
        cvj = json.loads((Path(W) / "CAPTION_VISION.json").read_text(encoding="utf-8"))
        if cvj.get("intro_offset_sec") is not None:
            return float(cvj["intro_offset_sec"]), False
    except Exception:
        pass
    try:
        import caption_vision as CVM
        video, words, brand, _ = CVM.project_inputs(Path(W))
        if video.exists() and words.exists():
            cues = CVM.group_cues(CVM.load_words(str(words)))
            cap = cv2.VideoCapture(str(video))
            Wv, Hv = int(cap.get(3)), int(cap.get(4)); cap.release()
            off, _q = CVM.estimate_offset(video, cues, CVM.geometry(cues, Wv, Hv, brand))
            return float(off), False
    except Exception:
        pass
    return 0.0, False


def _base_video(W):
    for n in ("EXPORT_TIGHT.mp4", "EXPORT.mp4"):
        if (Path(W) / n).exists():
            return Path(W) / n
    return None


def _brand(W):
    try:
        return json.loads((Path(W) / "project_manifest.json").read_text(encoding="utf-8")).get("brand") or "rel"
    except Exception:
        return "rel"


# ═══════════════════════════════════════════════════════════════════════
def b1_landed(W, it, video, intro, cfg):
    if _win(it) is None:
        return {"measured": False, "why": "אין חלון בתוכנית"}
    s, e = _win(it)
    t = (s + e) / 2.0
    cp = _clip_path(W, it)
    if not cp.exists() or _frame(video, intro + t) is None:
        return {"measured": False, "why": "אין פריים/קליפ"}
    so = float(it.get("src_offset") or 0.0)
    sim_clip, per = window_sim(video, intro, s, e, cp, lambda tt: _frame(cp, so + (tt - s)))
    if sim_clip is None:
        return {"measured": False, "why": "קליפ לא נקרא"}
    base = _base_video(W)
    sim_base = None
    if base is not None:
        bs = []
        for f in WIN_POSITIONS:
            tt = s + (e - s) * f
            a, b = _frame(video, intro + tt), _frame(base, tt)
            if a is not None and b is not None:
                bs.append(ncc(a, b))
        sim_base = float(np.median(bs)) if bs else None
    landed = sim_clip >= cfg["land_min"] and (sim_base is None or sim_clip >= sim_base + cfg["land_margin"])
    return {"measured": True, "t": round(intro + t, 2), "sim_clip": round(sim_clip, 3),
            "per_position": [round(v, 3) for v in per],
            "sim_base": None if sim_base is None else round(sim_base, 3), "landed": bool(landed)}


def b3_identity(it, brand, cat, ov, cfg_cat):
    f = it.get("file") or Path(it.get("path", "")).name
    p = it.get("path") or ""
    c = cat.get(f) or {}
    personal = set(cfg_cat.get("personal_tags") or [])
    why = []
    if "/הראל חיון/" in p:
        why.append("ספריית הראל חיון")
    if personal & set(c.get("tags") or []):
        why.append("personal_tags")
    if (ov.get(f) or {}).get("identity", "").startswith("harel"):
        why.append("אימות ויזואלי: הראל בפריים")
    club = (brand or "rel") in ("rel", "club")
    return {"harel_clip": bool(why), "why": why, "violation": bool(why) and club}


# ── B2: טקסט גרפי צרוב = שכבה סטטית על מצלמה שזזה ─────────────────────────
TEXT_CACHE_NAME = "burned-text-cache.json"


def _text_cache_path():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    return Path(cfg["catalog_path"]).parent / TEXT_CACHE_NAME


def text_static_score(path, n=6):
    """שבר השטח שבו יש קצוות-טקסט צפופים **שלא זזים** בין פריימים בזמן שהתמונה
    כולה כן זזה. שלט על הקיר זז עם המצלמה; כיתוב שנצרב בעריכה לא זז.
    מצלמה סטטית = אי אפשר להפריד ⇒ measured=false (עקרון 11)."""
    cap = cv2.VideoCapture(str(path))
    N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if N < 10:
        cap.release()
        return {"measured": False, "why": "קליפ קצר מדי"}
    frames = []
    for k in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(N * (0.1 + 0.8 * k / (n - 1))))
        ok, fr = cap.read()
        if ok:
            g = cv2.cvtColor(cv2.resize(fr, (270, 480)), cv2.COLOR_BGR2GRAY)
            frames.append(g)
    cap.release()
    if len(frames) < 3:
        return {"measured": False, "why": "פחות מ-3 פריימים"}
    st = np.stack(frames).astype(np.float32)
    motion = float(np.mean(np.abs(np.diff(st, axis=0))))
    if motion < 4.0:
        return {"measured": False, "why": f"מצלמה ותמונה כמעט סטטיות (תנועה {motion:.1f})",
                "motion": round(motion, 2)}
    edges = [cv2.Canny(f, 80, 200) > 0 for f in frames]
    stable_edges = np.logical_and.reduce(edges)
    static_px = np.std(st, axis=0) < 6.0
    # קצוות צפופים (טקסט) = חלון 9x9 עם ≥18 פיקסלי קצה יציבים
    dens = cv2.boxFilter((stable_edges & static_px).astype(np.float32), -1, (9, 9),
                         normalize=False)
    textish = dens >= 18
    frac = float(textish.mean())
    return {"measured": True, "motion": round(motion, 2), "static_text_frac": round(frac, 4)}


def scan_pool(limit=0, force=False):
    cfg, cat = _catalog()
    cp = _text_cache_path()
    cache = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
    items = [i for i in cat.values() if Path(i["path"]).exists()]
    if limit:
        items = items[:limit]
    n = 0
    for it in items:
        st = Path(it["path"]).stat()
        key = f"{it['file']}|{int(st.st_mtime)}|{st.st_size}"
        if key in cache and not force:
            continue
        cache[key] = dict(text_static_score(it["path"]), file=it["file"])
        n += 1
    tmp = cp.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, cp)
    return cache, n


def text_lookup(path):
    cp = _text_cache_path()
    if not cp.exists() or not Path(path).exists():
        return None
    st = Path(path).stat()
    return json.loads(cp.read_text(encoding="utf-8")).get(
        f"{Path(path).name}|{int(st.st_mtime)}|{st.st_size}")


# ── B4: עיגון למשפט — שיפוט מודלי כדאטה ────────────────────────────────────
def _sha(p, n=4 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        h.update(fh.read(n))
    h.update(str(Path(p).stat().st_size).encode())
    return h.hexdigest()[:16]


def _words_in(W, s, e):
    try:
        w = json.loads((Path(W) / "words_final.json").read_text(encoding="utf-8"))
        w = w if isinstance(w, list) else w.get("words", [])
    except Exception:
        return ""
    return " ".join(x["word"] for x in w if float(x["end"]) > s - 0.8 and float(x["start"]) < e + 0.3)


def anchor_request(W, video=None):
    from PIL import Image, ImageDraw, ImageFont
    W = Path(W)
    video = Path(video) if video else W / "FINAL.mp4"
    plan, _ = _plan(W)
    intro, _ = _intro(W)
    if not plan:
        return None
    sys.path.insert(0, str(HERE.parent / "captions-app"))
    import captions_overlay as co
    font = ImageFont.truetype(str(co.BRAND_PROFILES["club"]["font"]), 30)
    rows, reqs = [], []
    for k, it in enumerate(plan, 1):
        if _win(it) is None:
            continue
        s, e = _win(it)
        fr = _frame(video, intro + (s + e) / 2)
        if fr is None:
            continue
        th = cv2.resize(fr, (270, 480))
        txt = _words_in(W, s, e)
        img = Image.new("RGB", (900, 480), (24, 24, 24))
        img.paste(Image.fromarray(th[..., ::-1]), (0, 0))
        d = ImageDraw.Draw(img)
        d.text((285, 12), f"w{k:02d}  {s:.1f}-{e:.1f}s", font=font, fill=(255, 220, 0))
        # עברית: raqm מסדר RTL; שבירת שורות גסה
        words, line, y = txt.split(), "", 60
        for wd in words:
            if len(line) + len(wd) > 26:
                d.text((880, y), line, font=font, fill="white", anchor="ra", direction="rtl")
                y += 40; line = ""
            line = (line + " " + wd).strip()
        if line:
            d.text((880, y), line, font=font, fill="white", anchor="ra", direction="rtl")
        d.text((285, 430), (it.get("file") or "")[:40], font=ImageFont.truetype(
            str(co.BRAND_PROFILES["club"]["font"]), 18), fill=(150, 150, 150))
        rows.append(np.asarray(img)[..., ::-1])
        reqs.append({"ref": f"w{k:02d}", "file": it.get("file"), "window": [s, e],
                     "sentence": txt})
    if not rows:
        return None
    sheet = W / "broll_anchor_sheet.jpg"
    cv2.imwrite(str(sheet), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    req = {"final_sha": _sha(video), "sheet": str(sheet), "windows": reqs,
           "prompt": "לכל wNN: האם מה שנראה בפריים מאייר את המילים שנאמרות בחלון "
                     "(עיגון מילולי — לא נושא-על)? החזר {\"windows\":[{\"ref\",\"anchored\":bool,"
                     "\"burned_text\":bool,\"harel_in_frame\":bool,\"why\"}]} — שורה לכל ref."}
    (W / "BROLL_ANCHOR_REQUEST.json").write_text(json.dumps(req, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    return req


def anchor_apply(W, video=None):
    W = Path(W)
    video = Path(video) if video else W / "FINAL.mp4"
    req = json.loads((W / "BROLL_ANCHOR_REQUEST.json").read_text(encoding="utf-8"))
    ans = json.loads((W / "BROLL_ANCHOR_ANSWER.json").read_text(encoding="utf-8"))
    refs = {r["ref"] for r in req["windows"]}
    got = {a["ref"]: a for a in ans.get("windows", [])}
    if set(got) != refs:
        raise SystemExit(f"תשובה חלקית: חסרים {sorted(refs - set(got))}")
    for a in got.values():
        for k in ("anchored", "burned_text", "harel_in_frame"):
            if not isinstance(a.get(k), bool):
                raise SystemExit(f"{a['ref']}: {k} חייב להיות בוליאני")
    if req["final_sha"] != _sha(video):
        raise SystemExit("ה-FINAL השתנה מאז הבקשה — הפסיקה מתארת קובץ אחר")
    v = {"final_sha": req["final_sha"], "windows": list(got.values()),
         "n_not_anchored": sum(1 for a in got.values() if not a["anchored"]),
         "source": "claude-vision"}
    (W / "BROLL_ANCHOR_VERDICT.json").write_text(json.dumps(v, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    return v


# ═══════════════════════════════════════════════════════════════════════
def check(W, video=None, cfg=None, write=True, intro_offset=None):
    cfg = cfg or load_calibration()
    W = Path(W)
    video = Path(video) if video else W / "FINAL.mp4"
    plan, _d = _plan(W)
    out = {"workdir": str(W), "video": str(video), "n_broll": len(plan), "items": [],
           "counts": {}, "threshold_source": cfg["source"], "blocking_flags": cfg["blocking"]}
    if not plan or not video.exists():
        out.update(measured=False, ok=None, why="אין בירולים בתוכנית" if not plan else "אין FINAL")
        if write:
            (W / "BROLL_VISION.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        return out
    out["plan_source"] = _d.get("_source")
    out["planned_not_applied"] = _d.get("_planned_not_applied", 0)
    if intro_offset is not None:                   # הצינור יודע את intro_sec בוודאות
        intro, recorded = float(intro_offset), True
    else:
        intro, recorded = _intro(W)
    brand = _brand(W)
    cfg_cat, cat = _catalog()
    ov = _override()
    for it in plan:
        r = {"file": it.get("file"), "window": list(_win(it) or []), "flags": []}
        r["B1"] = b1_landed(W, it, video, intro, cfg)
        if r["B1"].get("measured") and not r["B1"]["landed"]:
            r["flags"].append("not_landed")
        tx = text_lookup(_clip_path(W, it))
        r["B2"] = tx
        if tx and tx.get("measured") and tx["static_text_frac"] >= cfg["text_static_min"]:
            r["flags"].append("burned_text")
        r["B3"] = b3_identity(it, brand, cat, ov, cfg_cat)
        if r["B3"]["violation"]:
            r["flags"].append("harel_in_club")
        out["items"].append(r)
        for f in r["flags"]:
            out["counts"][f] = out["counts"].get(f, 0) + 1
    # B4 — פסק-דין קיים ותואם ל-FINAL?
    vp = W / "BROLL_ANCHOR_VERDICT.json"
    b4 = {"status": "not_measured"}
    if vp.exists():
        v = json.loads(vp.read_text(encoding="utf-8"))
        b4 = {"status": "stale" if v.get("final_sha") != _sha(video) else "fresh",
              "n_not_anchored": v.get("n_not_anchored")}
        if b4["status"] == "fresh" and v.get("n_not_anchored"):
            out["counts"]["not_anchored"] = v["n_not_anchored"]
    out["B4"] = b4
    out["intro_offset_sec"] = intro
    out["intro_recorded"] = recorded
    hits = {k: v for k, v in out["counts"].items() if k in cfg["blocking"]}
    out.update(measured=True, blocking_hits=hits, ok=not hits)
    if write:
        (W / "BROLL_VISION.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


# ═══════════════════════════════════════════════════════════════════════
def calibrate(workdirs, seed=7):
    """B1: חיוביים = הקליפ שתוכנן בחלון שלו (FINAL מאושר). שליליים = קליפ אחר
    מהמאגר באותו רגע, והבסיס של הדובר באותו רגע (הבירול לא נחת)."""
    rnd = random.Random(seed)
    cfg_cat, cat = _catalog()
    pool = [i["path"] for i in cat.values() if Path(i["path"]).exists()]
    pos, neg_other, pos_margin, neg_base_margin, pos_items, pos_full = [], [], [], [], [], []
    used = []
    for W in workdirs:
        W = Path(W)
        plan, _ = _plan(W)
        video = W / "FINAL.mp4"
        if not plan or not video.exists():
            continue
        intro, _ = _intro(W)
        base = _base_video(W)
        used.append(W.name)
        for it in plan:
            if _win(it) is None:
                continue
            s, e = _win(it)
            t = (s + e) / 2
            cp = _clip_path(W, it)
            if _frame(video, intro + t) is None or not cp.exists():
                continue
            so0 = float(it.get("src_offset") or 0.0)
            # v9.32 — אותה מדידה בדיוק כמו b1_landed: 5 רגעים בחלון, חציון
            sc, _per = window_sim(video, intro, s, e, cp, lambda tt: _frame(cp, so0 + (tt - s)))
            if sc is None:
                continue
            pos.append(sc)
            pos_items.append((W.name, cp.name, round(sc, 3)))
            pos_full.append((sc, None))
            other = rnd.choice([x for x in pool if Path(x).name != cp.name])
            so, _ = window_sim(video, intro, s, e, other)
            if so is not None:
                neg_other.append(so)
            if base is not None:
                bs, nb = [], []
                for f in WIN_POSITIONS:
                    tt = s + (e - s) * f
                    a, b = _frame(video, intro + tt), _frame(base, tt)
                    if a is not None and b is not None:
                        bs.append(ncc(a, b))
                        nb.append(best_clip_sim(b, cp) or 0.0)
                if bs:
                    pos_margin.append(sc - float(np.median(bs)))
                    pos_full[-1] = (sc, pos_margin[-1])
                    # שלילי: אילו הבירול לא נחת, ה-FINAL היה הבסיס עצמו
                    neg_base_margin.append(float(np.median(nb)) - 1.0)
    q = lambda v, p: round(sorted(v)[min(len(v) - 1, int(p * (len(v) - 1)))], 3) if v else None
    p = dict(DEFAULTS)
    ev = {"videos": used, "n_pos": len(pos), "pos_sim_min": q(pos, 0), "pos_sim_p05": q(pos, .05),
          "neg_other_sim_p95": q(neg_other, .95), "neg_other_sim_max": q(neg_other, 1),
          "pos_margin_min": q(pos_margin, 0), "neg_base_margin_max": q(neg_base_margin, 1),
          "pos_lowest": sorted(pos_items, key=lambda x: x[2])[:6],
          "method": "v9.32: 5 רגעים בחלון (20%-80%), חציון; קליפ נדגם כל 0.25ש"}
    # v9.32 — כשיש הפרדה מלאה (החיובי הנמוך מעל השלילי הגבוה) הסף באמצע ביניהם;
    # אחרת נסיגה ל-p95 של השליליים (ואז החסימה לא תידלק כי caught/fp לא יעמדו)
    if pos and neg_other and min(pos) > max(neg_other):
        p["land_min"] = round((min(pos) + max(neg_other)) / 2, 3)
    elif pos and neg_other and min(pos) > q(neg_other, .95):
        p["land_min"] = round((min(pos) + q(neg_other, .95)) / 2, 3)
    p["land_margin"] = round(min(0.10, max(0.0, (ev["pos_margin_min"] or 0.1) / 2)), 3)
    p["source"] = "measured"
    # FP = בדיוק ההחלטה של b1_landed: מתחת לסף **או** לא מעל הבסיס במרווח
    fp = sum(1 for v, m in pos_full
             if v < p["land_min"] or (m is not None and m < p["land_margin"])) / max(1, len(pos_full))
    caught = sum(1 for v in neg_other if v < p["land_min"]) / max(1, len(neg_other))
    ev.update(pos_false_not_landed=round(fp, 4), neg_other_caught=round(caught, 4))
    p["blocking"] = ["not_landed"] if fp == 0 and caught >= 0.95 else []
    return {"params": p, "evidence": ev,
            "_readme": "ספי broll_vision_qa. B1: חיוביים = FINAL בחלונות הבירול המתוכננים; "
                       "שליליים = קליפ אקראי מהמאגר באותו פריים."}


def inject_text(src, dst, text="מה זה קרוספיט?", seconds=4.0):
    """קליפ עם כיתוב גרפי צרוב (סטטי) — בדיוק מה שנפסל בקציר 21.8.26."""
    from PIL import Image, ImageDraw, ImageFont
    sys.path.insert(0, str(HERE.parent / "captions-app"))
    import captions_overlay as co
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w, h = int(cap.get(3)), int(cap.get(4))
    vw = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    font = ImageFont.truetype(str(co.BRAND_PROFILES["club"]["font"]), max(24, int(h * 0.035)))
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((w // 2, int(h * 0.18)), text, font=font, anchor="mm",
                             fill=(255, 255, 255, 255), direction="rtl")
    la = np.asarray(lay).astype(np.float32)
    al = la[..., 3:4] / 255.0
    for _ in range(int(fps * seconds)):
        ok, fr = cap.read()
        if not ok:
            break
        fr = (fr.astype(np.float32) * (1 - al) + la[..., :3][..., ::-1] * al).astype(np.uint8)
        vw.write(fr)
    cap.release(); vw.release()


def calibrate_text(n=40, seed=3):
    """B2: חיוביים = הבריכה (נמדד במטמון); שליליים = אותם קליפים + כיתוב סטטי מוזרק."""
    import tempfile
    rnd = random.Random(seed)
    cp = _text_cache_path()
    cache = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
    posv = [v["static_text_frac"] for v in cache.values() if v.get("measured")]
    _cfg, cat = _catalog()
    items = [i for i in cat.values() if Path(i["path"]).exists()]
    rnd.shuffle(items)
    tmp = Path(tempfile.mkdtemp(prefix="b2_"))
    negv, unmeasured = [], 0
    for it in items[:n]:
        dst = tmp / "inj.mp4"
        inject_text(it["path"], dst)
        r = text_static_score(dst)
        if r.get("measured"):
            negv.append(r["static_text_frac"])
        else:
            unmeasured += 1
    q = lambda v, p: round(sorted(v)[min(len(v) - 1, int(p * (len(v) - 1)))], 4) if v else None
    ev = {"n_pos": len(posv), "pos_max": q(posv, 1), "pos_p99": q(posv, .99),
          "n_neg": len(negv), "neg_min": q(negv, 0), "neg_p05": q(negv, .05),
          "neg_unmeasured_static_camera": unmeasured}
    thr = None
    if posv and negv and q(negv, .05) > max(posv):
        thr = round((max(posv) + q(negv, .05)) / 2, 4)
    fp = (sum(1 for v in posv if thr is not None and v >= thr) / len(posv)) if posv else None
    caught = (sum(1 for v in negv if thr is not None and v >= thr) / len(negv)) if negv else None
    ev.update(threshold=thr, pos_false=fp, neg_caught=caught)
    return ev


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("--workdir", required=True)
    c.add_argument("--video"); c.add_argument("--strict", action="store_true")
    c.add_argument("--intro-offset", type=float, default=None)
    r = sub.add_parser("anchor-request"); r.add_argument("--workdir", required=True); r.add_argument("--video")
    a = sub.add_parser("anchor-apply"); a.add_argument("--workdir", required=True); a.add_argument("--video")
    s = sub.add_parser("scan-pool"); s.add_argument("--limit", type=int, default=0)
    s.add_argument("--force", action="store_true")
    k = sub.add_parser("calibrate"); k.add_argument("workdirs", nargs="+"); k.add_argument("--write", action="store_true")
    kt = sub.add_parser("calibrate-text"); kt.add_argument("--n", type=int, default=40)
    x = ap.parse_args()
    if x.cmd == "check":
        d = check(x.workdir, x.video, intro_offset=x.intro_offset)
        if d.get("measured") is False:
            print(f"— בירולים: לא נמדד ({d.get('why')})"); return 0
        icon = "✅" if d["ok"] else "🔴"
        print(f"{icon} בירולים ב-FINAL: {d['n_broll']} · "
              + (" · ".join(f"{k} {v}" for k, v in sorted(d["counts"].items())) or "אפס ממצאים")
              + f" · B4 {d['B4']['status']} · ספים: {d['threshold_source']}")
        return (0 if d["ok"] else 1) if x.strict else 0
    if x.cmd == "anchor-request":
        r = anchor_request(x.workdir, x.video)
        print(json.dumps(r, ensure_ascii=False, indent=1) if r else "אין בירולים"); return 0
    if x.cmd == "anchor-apply":
        v = anchor_apply(x.workdir, x.video)
        print(f"✅ פסק-דין נשמר · לא מעוגנים: {v['n_not_anchored']}/{len(v['windows'])}"); return 0
    if x.cmd == "scan-pool":
        cache, n = scan_pool(x.limit, x.force)
        m = [v for v in cache.values() if v.get("measured")]
        print(f"נסרקו {n} חדשים · במטמון {len(cache)} · נמדדו {len(m)}"); return 0
    if x.cmd == "calibrate-text":
        print(json.dumps(calibrate_text(x.n), ensure_ascii=False, indent=1)); return 0
    if x.cmd == "calibrate":
        doc = calibrate(x.workdirs)
        print(json.dumps(doc, ensure_ascii=False, indent=1))
        if x.write:
            CALIB.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0


if __name__ == "__main__":
    sys.exit(main())
