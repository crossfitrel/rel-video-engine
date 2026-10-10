#!/usr/bin/env python3
"""enhance.py — higgsfield-ai-enhancement: שכבת AI ויזואלית על סרטון ממומן שכבר נערך.

Real people. Real message. AI-enhanced attention.
הסרטון המקורי (Control) לא משתנה. נוצר נכס נוסף — AI_VARIANT — עם אותו אודיו (העתקת
stream ביט-לביט), אותן כתוביות (אותם cue_*.png, אותו y), אותו אורך ואותו מבנה; רק פריימים
בתוך 1-3 חלונות (Hook / אמצע / CTA) מוחלפים או מורכבים.

שלבים (כל אחד כותב ל-<project>/ai_enhancement/):
  analyze   → ai_analysis.json   משפטים, Hook, CTA, Offer, חלונות דובר-במצלמה, סטטיות
  plan      → ai_plan.json + plan.md   מתכונים מ-recipes.json, מודל Cost-first, estimate חינם
  keyframes → kf/*.png           פריימי מסירה אמיתיים + הכנה מקומית (חינם)
  generate  → gen/*              Generations בתשלום תחת budget guard (ledger.json) | --proxy = חינם לבדיקה
  compose   → ARIEL_..._AI.mp4   הרכבה פריים-מדויקת + matting ל-CTA + כתוביות + אודיו של ה-Control
  qa        → qa.json + qa/*.jpg בדיקות מדידות + גיליון לעין
  package   → תיקיית מסירה לאלי + experiment.json + experiments.jsonl

ריצה מומלצת: בקונטיינר הענן (torch ל-matting, רשת ל-API), קבצי הפרויקט מועלים מהמק.
"""
from __future__ import annotations
import argparse, json, re, subprocess, hashlib, shutil, sys, time, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

W, H, FPS = 1080, 1920, 30
RECIPES = json.loads((HERE / "recipes.json").read_text())
MODELS = json.loads((HERE / "models.json").read_text())
PROBE_IMG = "https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg"  # ל-estimate בלבד

CTA_RX = re.compile(r"(תשאירו|השאירו|לחצו|הירשמו|תירשמו|שלחו|תשלחו|כתבו|תכתבו|דברו|תדברו|היכנסו|תיכנסו|בואו|תבואו|קבעו|תקבעו)")
OFFER_RX = re.compile(r"(מתנה|במתנה|הטבה|מבצע|חינם|הנחה|ראשונים|-?15)")
STRONG_OFFER_RX = re.compile(r"(מתנה|במתנה|חינם|חודש שני|הנחה)")
PLACE_RX = re.compile(r"(תושבי|אריאל|הסביבה|גרים ב|בשומרון|ביישובים)")


# ───────────────────────────── utils
def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-800:]}")
    return r.stdout


def probe(p) -> dict:
    j = json.loads(sh(["ffprobe", "-v", "error", "-show_entries",
                       "stream=codec_type,width,height,r_frame_rate,nb_frames:format=duration",
                       "-of", "json", str(p)]))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    n, d = v["r_frame_rate"].split("/")
    return {"dur": float(j["format"]["duration"]), "w": v["width"], "h": v["height"],
            "fps": float(n) / float(d), "nb": int(v.get("nb_frames") or 0)}


def sha256(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def frame_at(video, t, out, w=W, h=H):
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
        "-vf", f"scale={w}:{h}:flags=lanczos", str(out)])
    return Path(out)


def cover(im: Image.Image, w=W, h=H) -> Image.Image:
    r = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def read_frames(video, w=W, h=H, fps=FPS, i0=None, n=None):
    """מחזיר list של np.uint8 HxWx3, מנורמל לגודל/קצב היעד (cover crop).
    i0/n: טווח פריימים (לפי אינדקס ב-30fps) — כדי לא לטעון סרטון שלם לזיכרון."""
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},fps={fps}"
    if i0 is not None:
        vf = f"select=between(n\\,{i0}\\,{i0 + n - 1})," + vf.replace(f",fps={fps}", "")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(video), "-vf", vf, "-vsync", "0",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    out, n = [], w * h * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        out.append(np.frombuffer(b, np.uint8).reshape(h, w, 3))
    p.wait()
    return out


def ils(usd, rate=None):
    return round(usd * (rate or MODELS["usd_ils"]), 2)


# ───────────────────────────── project
class Project:
    def __init__(self, proj: str, control: str | None = None, out: str | None = None):
        self.dir = Path(proj).resolve()
        self.ai = Path(out).resolve() if out else self.dir / "ai_enhancement"
        self.ai.mkdir(parents=True, exist_ok=True)
        for d in ("kf", "gen", "qa", "cache"):
            (self.ai / d).mkdir(exist_ok=True)
        self.control = Path(control).resolve() if control else (self.dir / "FINAL.mp4").resolve()
        self.base_clean = next((self.dir / f for f in ("MIXED.mp4", "EXPORT+BROLL.mp4", "EXPORT_TIGHT.mp4")
                                if (self.dir / f).exists()), None)
        self.words = json.loads((self.dir / "words_final.json").read_text())
        bp = self.dir / "broll_plan.json"
        self.broll = json.loads(bp.read_text()) if bp.exists() else {}

    def jpath(self, name):
        return self.ai / name

    def load(self, name):
        return json.loads(self.jpath(name).read_text())

    def save(self, name, obj):
        p = self.jpath(name)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1))
        tmp.replace(p)
        return p


def sentences(words):
    out, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.?!]$", w["word"]):
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return [{"start": s[0]["start"], "end": s[-1]["end"], "text": " ".join(x["word"] for x in s),
             "words": s} for s in out]


def static_score(video, t0, t1, n=6):
    """ממוצע הפרש בין פריימים ברצועה העליונה (רקע). <4 ≈ חצובה."""
    ts = np.linspace(t0 + 0.05, t1 - 0.05, n)
    fr = []
    for t in ts:
        b = sh_bytes(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                      "-vf", "scale=108:192", "-f", "rawvideo", "-pix_fmt", "gray", "-"])
        fr.append(np.frombuffer(b, np.uint8).reshape(192, 108)[:38].astype(float))   # תקרה/רקע עליון, מעל ראש הדובר
    return float(np.mean([np.abs(fr[i] - fr[i + 1]).mean() for i in range(len(fr) - 1)]))


def find_cuts(video, t0, t1, thr=8.0):
    """קאטים (jump cuts) בחלון — הפרש ממוצע ברצועה העליונה בין פריימים עוקבים."""
    b = sh_bytes(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-i", str(video), "-t", f"{t1 - t0:.3f}",
                  "-vf", "scale=108:192", "-f", "rawvideo", "-pix_fmt", "gray", "-"])
    a = np.frombuffer(b, np.uint8).reshape(-1, 192, 108)[:, :38].astype(float)
    d = np.abs(np.diff(a, axis=0)).mean((1, 2))
    return [round(t0 + (k + 1) / FPS, 3) for k in np.where(d > thr)[0]]


def sh_bytes(cmd):
    return subprocess.run(cmd, capture_output=True, check=True).stdout


# ───────────────────────────── analyze
def cmd_analyze(P: Project, a):
    dur = probe(P.control)["dur"]
    S = sentences(P.words)
    bed0, bed1 = P.broll.get("bed_start"), P.broll.get("bed_end")
    on_cam = []
    if bed0 is not None:
        on_cam = [[0.0, round(bed0, 3)], [round(bed1, 3), round(dur, 3)]]
    hook = S[0]
    cta = next((s for s in reversed(S) if CTA_RX.search(s["text"])), S[-1])
    body = [s for s in S if s is not cta and s is not hook]
    offer = (next((s for s in body if STRONG_OFFER_RX.search(s["text"])), None)
             or next((s for s in body if OFFER_RX.search(s["text"])), None))
    # גבול Hook: סוף המילה האחרונה שמסתיימת עד 1.8ש (שם הדובר "נכנס")
    hw = [w for w in hook["words"] if w["end"] <= 1.8]
    hook_T = round(hw[-1]["end"], 3) if hw else 1.5
    base = P.base_clean or P.control
    post = on_cam[1] if on_cam else [cta["start"], dur]
    res = {
        "control": str(P.control), "control_sha256": sha256(P.control), "duration": round(dur, 3),
        "base_clean": str(P.base_clean) if P.base_clean else None,
        "sentences": [{k: s[k] for k in ("start", "end", "text")} for s in S],
        "on_camera": on_cam,
        "hook": {"sentence": hook["text"], "start": hook["start"], "end": hook["end"], "handoff_T": hook_T,
                 "place_ref": bool(PLACE_RX.search(hook["text"]))},
        "offer": ({"sentence": offer["text"], "start": offer["start"], "end": offer["end"],
                   "inside_broll": bool(bed0 is not None and offer["start"] >= bed0)} if offer else None),
        "cta": {"sentence": cta["text"], "start": cta["start"], "end": cta["end"],
                "on_camera_window": post},
    }
    cuts = find_cuts(base, post[0] + 0.05, post[1] - 0.05)
    res["cta"]["cuts_in_on_camera"] = cuts
    near = [c for c in cuts if cta["start"] - 0.6 <= c <= cta["start"] + 0.4]
    res["cta"]["window_start"] = near[0] if near else round(cta["start"] - 0.15, 3)
    # סטטיות נמדדת רק בתוך הסגמנט הרציף של ה-CTA (אחרי ה-jump cut)
    ws = res["cta"]["window_start"]
    res["cta"]["static_score"] = round(static_score(base, ws + 0.05, post[1] - 0.05), 2)
    res["cta"]["static_bg"] = res["cta"]["static_score"] < 4.0
    P.save("ai_analysis.json", res)
    print(json.dumps({k: res[k] for k in ("hook", "offer", "cta", "on_camera")}, ensure_ascii=False, indent=1))


# ───────────────────────────── plan
def est_usd(model, dur_s, extra=None):
    import hf_client as hf
    m = next(x for x in MODELS["video_tiers"] if x["id"] == model)
    body = {m["first_field"]: PROBE_IMG, "prompt": "x", "duration": dur_s, **m["fixed"]}
    if m["last_frame"]:
        body[m["last_frame"]] = PROBE_IMG
    try:
        return hf.estimate(model, body)["usd"]
    except Exception:
        return m["price_usd"].get(f"{dur_s}s")


def img_usd(model, res="2k"):
    m = next(x for x in MODELS["image_tiers"] if x["id"] == model)
    return m["price_usd"].get(res) or m["price_usd"].get("default")


def cmd_plan(P: Project, a):
    A = P.load("ai_analysis.json")
    dur = A["duration"]
    rp = MODELS["retry_priors"]
    shots = []
    # HOOK
    if A["hook"]["place_ref"] and not a.no_hook:
        r = RECIPES["hook_aerial_dive"]; T = A["hook"]["handoff_T"]
        v = est_usd(r["model_pref"][0], r["gen_duration"]); i = img_usd(r["first_frame"]["gen"])
        shots.append({"id": "hook", "role": "hook", "recipe": "hook_aerial_dive", "window": [0.0, T],
                      "sentence": " ".join(w["word"] for w in P.words if w["end"] <= T + 0.01),
                      "effect": "צילום אווירי של עיר על גבעה בזריחה → צלילה דרך הגג לתוך המועדון → נחיתה על הפריים האמיתי",
                      "purpose": r["purpose"], "kpi": r["kpi"], "model": r["model_pref"][0],
                      "items": [{"kind": "image", "id": "hook_first", "model": r["first_frame"]["gen"], "usd": i},
                                {"kind": "video", "id": "hook_video", "model": r["model_pref"][0], "usd": v}],
                      "retry_prior": rp[r["retry_prior"]]})
    # MID (offer → match-cut)
    off = A.get("offer")
    if off and off["inside_broll"] and A["cta"]["static_bg"] and A["on_camera"] and not a.no_mid:
        r = RECIPES["mid_empty_spot_reveal"]
        bed1 = A["on_camera"][1][0]
        ws = next((w["start"] for w in P.words if w["start"] >= off["start"] - 0.01), off["start"])
        ws = max(ws - 0.05, bed1 - 4.0)
        v = est_usd(r["model_pref"][0], r["gen_duration"])
        shots.append({"id": "mid", "role": "mid", "recipe": "mid_empty_spot_reveal", "window": [round(ws, 3), bed1],
                      "sentence": " ".join(w["word"] for w in P.words if ws - 0.01 <= w["start"] < bed1),
                      "effect": "הנקודה שבה הדוברת תשב — ריקה ועמומה; אור חם נדלק מעליה → match-cut לאותו פריים כשהיא יושבת שם",
                      "purpose": r["purpose"], "kpi": r["kpi"], "model": r["model_pref"][0],
                      "items": [{"kind": "video", "id": "mid_video", "model": r["model_pref"][0], "usd": v}],
                      "retry_prior": rp[r["retry_prior"]]})
    # CTA
    if A["cta"]["static_bg"] and not a.no_cta:
        r = RECIPES["cta_open_light_matte"]
        cs = A["cta"]["window_start"]
        v = est_usd(r["model_pref"][0], r["gen_duration"])
        i = img_usd("alibaba/qwen-image-3/edit")
        shots.append({"id": "cta", "role": "cta", "recipe": "cta_open_light_matte", "window": [cs, dur],
                      "sentence": A["cta"]["sentence"],
                      "effect": "הדוברת נשארת אמיתית (matting); מאחוריה המועדון 'נפתח' — אור זריחה זהוב, קרן אור על הרצפה אל המצלמה ואל כפתור ה-CTA, push-in איטי",
                      "purpose": r["purpose"], "kpi": r["kpi"], "model": r["model_pref"][0],
                      "items": [{"kind": "image", "id": "clean_plate", "model": "alibaba/qwen-image-3/edit", "usd": i},
                                {"kind": "image", "id": "cta_last", "model": "alibaba/qwen-image-3/edit", "usd": i},
                                {"kind": "video", "id": "cta_video", "model": r["model_pref"][0], "usd": v}],
                      "retry_prior": rp[r["retry_prior"]]})
    for s in shots:
        base = sum(x["usd"] for x in s["items"])
        s["est_usd"] = round(base * (1 + s["retry_prior"]), 3)
        s["est_ils"] = ils(s["est_usd"])
    total = round(sum(s["est_usd"] for s in shots), 3)
    plan = {"project": P.dir.name, "control": A["control"], "control_sha256": A["control_sha256"],
            "duration": dur, "usd_ils": MODELS["usd_ils"], "prices_checked": MODELS["checked_at"],
            "shots": shots, "est_total_usd": total, "est_total_ils": ils(total),
            "budget": {"target_ils": [10, 20], "cap_ils": 20.0}, "within_budget": ils(total) <= 20.0}
    P.save("ai_plan.json", plan)
    (P.ai / "plan.md").write_text(plan_md(plan), encoding="utf-8")
    print(plan_md(plan))


def _t(x):
    return f"{int(x // 60):02d}:{x % 60:04.1f}"


def plan_md(plan):
    L = [f"# תוכנית AI Enhancement — {plan['project']}", ""]
    for s in plan["shots"]:
        lab = {"hook": "Hook", "mid": "Mid-video Enhancement", "cta": "CTA"}[s["role"]]
        end = "סיום" if s["role"] == "cta" else _t(s["window"][1])
        L += [f"**{_t(s['window'][0])}–{end} — {lab}**",
              f"המשפט: {s['sentence']}", f"האפקט: {s['effect']}",
              f"{'למה הוא אמור לחזק פעולה' if s['role']=='cta' else 'למה'}: {', '.join(s['purpose'])} · KPI: {s['kpi']}",
              f"מודל: {s['model']} (+ " + ", ".join(i['model'] for i in s['items'] if i['kind'] == 'image') + ")" if any(i['kind']=='image' for i in s['items']) else f"מודל: {s['model']}",
              f"עלות צפויה: ₪{s['est_ils']} (כולל סיכון Retry {int(s['retry_prior']*100)}%)", ""]
    L += [f"**Estimated total AI cost: ₪{plan['est_total_ils']}** (${plan['est_total_usd']}, שער {plan['usd_ils']})"]
    return "\n".join(L)


# ───────────────────────────── keyframes (free)
def dim(im: Image.Image, spec: dict) -> Image.Image:
    a = np.asarray(im.convert("RGB")).astype(np.float32) / 255
    a = np.power(a, spec.get("gamma", 1.9)) * spec.get("gain", 0.45)
    g = a.mean(2, keepdims=True); a = a * (1 - spec.get("desat", .35)) + g * spec.get("desat", .35)
    a[..., 2] *= 1.06   # קריר מעט — 'לפני'
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def cmd_keyframes(P: Project, a):
    plan = P.load("ai_plan.json")
    base = P.base_clean or P.control
    kf = P.ai / "kf"
    for s in plan["shots"]:
        if s["id"] == "hook":
            frame_at(base, s["window"][1], kf / "hook_last_real.png")
        if s["id"] == "cta":
            frame_at(base, s["window"][0], kf / "cta_real.png")
        if s["id"] == "mid":
            frame_at(base, s["window"][1] + 0.02, kf / "mid_after_real.png")
    print(sorted(p.name for p in kf.iterdir()))


# ───────────────────────────── generate (paid, budget-guarded)
def _upload(P, path):
    import hf_client as hf
    cache = P.ai / "cache" / "uploads.json"
    c = json.loads(cache.read_text()) if cache.exists() else {}
    k = sha256(path)
    if k not in c:
        c[k] = hf.upload(path); cache.write_text(json.dumps(c, indent=1))
    return c[k]


def _to_png_1080(src, dst):
    cover(Image.open(src).convert("RGB")).save(dst)
    return Path(dst)


def cmd_generate(P: Project, a):
    from budget import Ledger, BudgetExceeded
    import gen, hf_client as hf
    plan = P.load("ai_plan.json")
    L = Ledger(P.ai / "ledger.json")
    G, K = P.ai / "gen", P.ai / "kf"
    only = set(a.shot or [])
    by = {s["id"]: s for s in plan["shots"]}
    att = a.attempt

    def want(i):
        return not only or i in only

    def model_for(shot, esc):
        pref = RECIPES[by[shot]["recipe"]]["model_pref"]
        return pref[min(esc, len(pref) - 1)] if esc else by[shot]["model"]

    def vid_body(model, first, last, prompt, dur):
        m = next(x for x in MODELS["video_tiers"] if x["id"] == model)
        b = {m["first_field"]: _upload(P, first), "prompt": prompt, "duration": dur, **m["fixed"]}
        if last is not None:
            b[m["last_frame"]] = _upload(P, last)
        return b

    if a.proxy:
        return proxy_generate(P, plan)

    try:
        # סדר עדיפות תקציבי: CTA ו-Hook קודם, אמצע אחרון (אם נגמר התקציב — האמצע נופל)
        if "cta" in by:
            r = RECIPES["cta_open_light_matte"]
            if want("clean_plate") or want("cta"):
                if not (G / "clean_plate.png").exists() or "clean_plate" in only:
                    body = {"image_urls": [_upload(P, K / "cta_real.png")], "resolution": "2k", "aspect_ratio": "9:16",
                            "prompt": "Remove the woman sitting on the black plyo boxes completely, as if she was never there. "
                                      "Reconstruct what is behind her naturally: the black and wooden plyo boxes, the dumbbell rack, "
                                      "the window and the gym wall. Keep every other pixel identical: same camera, framing, lens, "
                                      "daylight and colors. Photorealistic, no people.",
                            "negative_prompt": "person, woman, people, text, watermark"}
                    raw = gen.run(L, "cta", "clean_plate", "alibaba/qwen-image-3/edit", body,
                                  G / f"clean_plate_raw_a{att}.png", MODELS["retry_priors"]["image_edit"], att)
                    _to_png_1080(raw, G / "clean_plate.png")
                    align_plate(P)
            if want("cta_last") or want("cta"):
                if not (G / "cta_last.png").exists() or "cta_last" in only:
                    lf = r["last_frame"]
                    body = {"image_urls": [_upload(P, G / "clean_plate.png")], "resolution": "2k",
                            "aspect_ratio": "9:16", "prompt": lf["prompt"],
                            "negative_prompt": "person, people, text, watermark, different camera angle"}
                    raw = gen.run(L, "cta", "cta_last", lf["gen"], body, G / f"cta_last_raw_a{att}.png",
                                  MODELS["retry_priors"]["image_edit"], att)
                    _to_png_1080(raw, G / "cta_last.png")
            if want("cta_video") or want("cta"):
                mdl = model_for("cta", a.escalate)
                body = vid_body(mdl, G / "clean_plate.png", G / "cta_last.png", r["prompt"], r["gen_duration"])
                gen.run(L, "cta", "cta_video", mdl, body, G / f"cta_video_a{att}.mp4", by["cta"]["retry_prior"], att)
                shutil.copy(G / f"cta_video_a{att}.mp4", G / "cta_video.mp4")
        if "hook" in by:
            r = RECIPES["hook_aerial_dive"]
            if want("hook_first") or want("hook"):
                if not (G / "hook_first.png").exists() or "hook_first" in only:
                    ff = r["first_frame"]
                    body = {"prompt": ff["prompt"], "resolution": "2k", "aspect_ratio": "9:16",
                            "negative_prompt": "text, watermark, logo, people close-up, fisheye"}
                    raw = gen.run(L, "hook", "hook_first", ff["gen"], body, G / f"hook_first_raw_a{att}.png",
                                  MODELS["retry_priors"]["image_edit"], att)
                    _to_png_1080(raw, G / "hook_first.png")
            if want("hook_video") or want("hook"):
                mdl = model_for("hook", a.escalate)
                body = vid_body(mdl, G / "hook_first.png", K / "hook_last_real.png", r["prompt"], r["gen_duration"])
                gen.run(L, "hook", "hook_video", mdl, body, G / f"hook_video_a{att}.mp4", by["hook"]["retry_prior"], att)
                shutil.copy(G / f"hook_video_a{att}.mp4", G / "hook_video.mp4")
        if "mid" in by and (want("mid_video") or want("mid")):
            r = RECIPES["mid_empty_spot_reveal"]
            mid_frames(P)
            mdl = model_for("mid", a.escalate)
            body = vid_body(mdl, K / "mid_first_dim.png", K / "mid_last_plate.png", r["prompt"], r["gen_duration"])
            gen.run(L, "mid", "mid_video", mdl, body, G / f"mid_video_a{att}.mp4", by["mid"]["retry_prior"], att)
            shutil.copy(G / f"mid_video_a{att}.mp4", G / "mid_video.mp4")
    except BudgetExceeded as e:
        print("⛔ BUDGET GUARD:", e); print("→ Re-plan זול יותר (--no-mid / מודל tier 0) לפני בקשת אישור מהראל")
        sys.exit(3)
    except hf.NoCredits:
        print("⛔ אין יתרה בחשבון ה-API של Higgsfield (403 not_enough_credits). טעינה = פעולה כספית → אישור הראל.")
        sys.exit(4)
    print(json.dumps(L.summary(), ensure_ascii=False))


def align_plate(P):
    """ה-clean plate מיושר לפריים האמיתי (ECC multistart על שוליים+תקרה) — כל מה שבא אחריו
    (פריים סיום CTA, קליפ הרקע, פריים mid) יורש את הגאומטריה הנכונה."""
    G, K = P.ai / "gen", P.ai / "kf"
    cp = np.asarray(Image.open(G / "clean_plate.png").convert("RGB"))
    real = np.asarray(Image.open(K / "cta_real.png").convert("RGB"))
    M = register(cp, real, side_mask(), multistart=True)
    if M is not None:
        Image.fromarray(cp).save(G / "clean_plate_unaligned.png")
        Image.fromarray(warp(cp, M)).save(G / "clean_plate.png")
        print(f"clean_plate aligned cc={register.last_cc:.3f}")


def mid_frames(P):
    """פריים סיום ל-mid = ה-clean plate מיושר (ECC, חינם) לפריים האמיתי שאחרי ה-match-cut,
    כדי שהקאט לדוברת יהיה באותו פריים בדיוק גם אם המצלמה זזה בין הטייקים."""
    G, K = P.ai / "gen", P.ai / "kf"
    cp = np.asarray(Image.open(G / "clean_plate.png").convert("RGB"))
    ref = np.asarray(Image.open(K / "cta_real.png").convert("RGB"))
    tgt = np.asarray(Image.open(K / "mid_after_real.png").convert("RGB"))
    M = register(ref, tgt, side_mask())          # warp(ref,M) ≈ tgt
    Image.fromarray(warp(cp, M)).save(K / "mid_last_plate.png")
    dim(Image.open(K / "mid_last_plate.png"), RECIPES["mid_empty_spot_reveal"]["first_frame"]).save(K / "mid_first_dim.png")


def proxy_generate(P, plan):
    """תחליפים מקומיים חינמיים — רק לבדיקת צנרת ההרכבה. מסומנים PROXY בכל פריים."""
    G, K = P.ai / "gen", P.ai / "kf"
    tag = lambda im: (ImageDraw.Draw(im).text((30, 30), "PROXY — NOT AI", fill=(255, 0, 0)), im)[1]
    by = {s["id"]: s for s in plan["shots"]}
    if "cta" in by:
        cp = Image.open(K / "cta_real.png").convert("RGB"); cp.save(G / "clean_plate.png")
        warm = ImageEnhance.Brightness(cp).enhance(1.25)
        arr = np.asarray(warm).astype(np.float32); arr[..., 0] *= 1.12; arr[..., 2] *= 0.85
        Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(G / "cta_last.png")
        _xfade(G / "clean_plate.png", G / "cta_last.png", G / "cta_video.mp4", 3)
    if "hook" in by:
        sky = Image.new("RGB", (W, H)); d = ImageDraw.Draw(sky)
        for y in range(H):
            d.line([(0, y), (W, y)], fill=(int(250 - y / H * 120), int(190 - y / H * 90), int(120 + y / H * 40)))
        tag(sky).save(G / "hook_first.png")
        _xfade(G / "hook_first.png", K / "hook_last_real.png", G / "hook_video.mp4", 3)
    if "mid" in by:
        mid_frames(P)
        _xfade(K / "mid_first_dim.png", K / "mid_last_plate.png", G / "mid_video.mp4", 3)
    (G / "PROXY").write_text("gen/ contains local stand-ins, not AI output\n")
    print("proxy ready")


def _xfade(a, b, out, d):
    sh(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", str(d), "-i", str(a), "-loop", "1", "-t", str(d), "-i", str(b),
        "-filter_complex", f"[0:v][1:v]xfade=transition=fade:duration={d - 0.2}:offset=0.1,format=yuv420p,fps=24",
        "-t", str(d), "-c:v", "libx264", "-crf", "16", str(out)])


# ───────────────────────────── captions
def parse_caplist(path: Path):
    L = path.read_text().splitlines(); t = 0.0; seq = []; i = 1
    while i < len(L):
        if L[i].startswith("file") and i + 1 < len(L) and L[i + 1].startswith("duration"):
            f = L[i].split("'")[1]; d = float(L[i + 1].split()[1]); seq.append((t, t + d, f)); t += d; i += 2
        else:
            i += 1
    return seq


def ensure_cues(P: Project):
    """cue_*.png + caplist.txt של הגימור המקורי. אם נוקו (cleanup_work) — מרנדרים מחדש
    בדיוק באותו קוד (captions-app/captions_overlay.burn) לתיקיית cache."""
    if (P.dir / "caplist.txt").exists() and (P.dir / "cue_0000.png").exists():
        return P.dir
    cdir = P.ai / "cache" / "cues"; cdir.mkdir(parents=True, exist_ok=True)
    if not (cdir / "caplist.txt").exists():
        sys.path.insert(0, str(HERE.parent.parent / "captions-app"))
        import captions_overlay as co
        ok, err, n = co.burn(str(P.dir / "words_final.json"), str(P.control), "_tmp_burn.mp4", str(cdir), brand="rel")
        if not ok:
            raise RuntimeError(err)
    return cdir


def detect_caption_y(P: Project, cdir: Path, seq):
    """y של רצועת הכתוביות — נמדד מול ה-Control (מינימום שגיאה), לא מנוחש."""
    if not P.base_clean:
        return None
    c = next(s for s in seq if s[2] != "_blank.png" and s[1] - s[0] > 0.2)
    t = (c[0] + c[1]) / 2
    ctl = np.asarray(Image.open(frame_at(P.control, t, P.ai / "cache" / "_c.png")).convert("RGB"), float)
    base = Image.open(frame_at(P.base_clean, t, P.ai / "cache" / "_m.png")).convert("RGBA")
    cue = Image.open(cdir / c[2]).convert("RGBA")
    best = (1e9, None)
    for y in range(max(0, H - 700), H - cue.height):
        im = base.copy(); im.alpha_composite(cue, (0, y))
        e = np.abs(np.asarray(im.convert("RGB"), float)[y - 40:y + cue.height + 40] - ctl[y - 40:y + cue.height + 40]).mean()
        best = min(best, (e, y))
    return best[1]


# ───────────────────────────── compose
def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def color_match_params(src, ref, mask):
    """ממוצע/סטיית תקן לכל ערוץ באזור הרקע — Reinhard פשוט, מחושב פעם אחת (פריים ראשון)."""
    m = mask > 0.5
    s = src[m].astype(np.float32); r = ref[m].astype(np.float32)
    return s.mean(0), s.std(0) + 1e-3, r.mean(0), r.std(0) + 1e-3


def apply_cm(img, p):
    sm, ss, rm, rs = p
    return np.clip((img.astype(np.float32) - sm) / ss * rs + rm, 0, 255)


def register(src, ref, mask, multistart=False):
    """יישור (ECC affine) של src ל-ref על אזור הרקע בלבד. warp(src,M) ≈ ref.
    multistart: מודלי עריכת תמונה נוטים 'לקרב'/להזיז את הפריים (נמדד בפיילוט: ×0.9, cc 0.89)
    — מתחילים מרשת של זומים והזזות ובוחרים את ההתאמה הטובה ביותר."""
    import cv2
    s = cv2.cvtColor(src, cv2.COLOR_RGB2GRAY).astype(np.float32)
    r = cv2.cvtColor(ref, cv2.COLOR_RGB2GRAY).astype(np.float32)
    sc = 0.25
    s2, r2 = cv2.resize(s, None, fx=sc, fy=sc), cv2.resize(r, None, fx=sc, fy=sc)
    m2 = cv2.resize((mask > 0.5).astype(np.uint8), (s2.shape[1], s2.shape[0]))
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6)

    def ecc(a, b, m, M0):
        try:
            return cv2.findTransformECC(a, b, M0.copy(), cv2.MOTION_AFFINE, crit, m, 5)
        except cv2.error:
            return None
    M0 = np.eye(2, 3, dtype=np.float32)
    if multistart:   # רשת גסה ב-1/8 ואז עידון ב-1/4
        a3, b3 = cv2.resize(r2, None, fx=.5, fy=.5), cv2.resize(s2, None, fx=.5, fy=.5)
        m3 = cv2.resize(m2, (a3.shape[1], a3.shape[0]))
        cands = []
        for z in (0.85, 0.9, 0.95, 1.0, 1.05):
            for d in ((0, 0), (-15, 0), (15, 0), (0, -15), (0, 15)):
                res = ecc(a3, b3, m3, np.array([[z, 0, d[0]], [0, z, d[1]]], np.float32))
                if res:
                    cands.append(res)
        if cands:
            M0 = max(cands, key=lambda x: x[0])[1].copy(); M0[:, 2] *= 2
    res = ecc(r2, s2, m2, M0)
    if res is None:
        return None
    best = res
    M = best[1]; M[:, 2] /= sc
    register.last_cc = float(best[0])
    return M


def side_mask():
    """רקע בלי הדובר (כשאין matte): תקרה + שוליים."""
    m = np.zeros((H, W), np.float32); m[:400] = 1; m[:, :180] = 1; m[:, 900:] = 1
    return m


def m3(M):
    return np.vstack([M, [0, 0, 1]]).astype(np.float32)


def warp(img, M):
    import cv2
    if M is None:
        return img
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)


def matte(frames, cache: Path):
    """alpha לדוברת (RobustVideoMatting, mobilenetv3). נשמר ל-cache כי זה החלק היקר."""
    if cache.exists():
        z = np.load(cache)["a"]
        if len(z) == len(frames):
            return z
    import torch
    rvm = Path(__import__("os").environ.get("RVM_DIR", str(HERE / "_rvm")))
    sys.path.insert(0, str(rvm))
    from model import MattingNetwork
    m = MattingNetwork("mobilenetv3").eval()
    m.load_state_dict(torch.load(rvm / "rvm_mobilenetv3.pth", map_location="cpu"))
    rec, out = [None] * 4, []
    with torch.no_grad():
        for f in frames:
            x = torch.from_numpy(f.copy()).permute(2, 0, 1).float().div(255).unsqueeze(0)
            _, pha, *rec = m(x, *rec, downsample_ratio=0.25)
            out.append((pha[0, 0].clamp(0, 1).numpy() * 255).astype(np.uint8))
    z = np.stack(out); np.savez_compressed(cache, a=z)
    return z


def push(img, s, cx=540, cy=760):
    if s <= 1.0001:
        return img
    import cv2
    M = np.array([[s, 0, cx - s * cx], [0, s, cy - s * cy]], np.float32)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def voronoi_shards(n=64, seed=7):
    """רסיסי זכוכית (Voronoi) — מחושב פעם אחת. צפוף יותר סביב המרכז (נקודת השבירה)."""
    import cv2
    rng = np.random.default_rng(seed)
    pts = np.concatenate([rng.normal([W / 2, H * 0.42], [W * 0.22, H * 0.18], (n // 2, 2)),
                          rng.uniform([0, 0], [W, H], (n - n // 2, 2))])
    pts = np.clip(pts, 1, [W - 2, H - 2])
    sub = cv2.Subdiv2D((0, 0, W, H))
    for p in pts:
        sub.insert((float(p[0]), float(p[1])))
    facets, centers = sub.getVoronoiFacetList([])
    shards = []
    for f, c in zip(facets, centers):
        poly = np.clip(np.array(f, np.float32), [0, 0], [W - 1, H - 1])
        d = np.array(c) - [W / 2, H * 0.42]; dist = np.linalg.norm(d) + 1e-3
        shards.append({"poly": poly, "c": np.array(c, np.float32), "dir": d / dist,
                       "delay": float(min(0.35, dist / 2600)), "rot": float(rng.uniform(-50, 50)),
                       "spd": float(rng.uniform(0.8, 1.4))})
    return shards


def hook_v2v_frame(v, clip, i, t):
    """עולם אפור (V2V) + הדוברת האמיתית (matte) עד רגע השבירה; ואז הזכוכית מתנפצת לעבר
    המצלמה וחושפת את המועדון האמיתי. הדוברת תמיד אמיתית, תמיד מעל הכל."""
    import cv2
    real = v["real"][min(i, len(v["real"]) - 1)].astype(np.float32)
    al = v["alpha"][min(i, len(v["alpha"]) - 1)].astype(np.float32)[..., None] / 255
    k = min(len(clip) - 1, int(round(t * FPS)))
    g = clip[k].astype(np.float32)
    lum = g.mean(2, keepdims=True); g = g * (1 - v["desat"]) + lum * v["desat"]; g *= 0.88
    t0, d = v["shatter"], v["sh_dur"]
    if t < t0:
        return real * al + g * (1 - al)
    p = (t - t0) / d
    canvas = real.copy()
    if p < 1:
        # רסיסים עפים בלי 'פרצוף אפור': מוחקים את הדוברת מהשכבה האפורה (inpaint ברזולוציה 1/4)
        a4 = cv2.resize((al[..., 0] > 0.12).astype(np.uint8), (W // 4, H // 4))
        a4 = cv2.dilate(a4, np.ones((9, 9), np.uint8))
        g4 = cv2.inpaint(cv2.resize(g, (W // 4, H // 4)).clip(0, 255).astype(np.uint8), a4, 6, cv2.INPAINT_TELEA)
        gm = cv2.resize(cv2.GaussianBlur(a4.astype(np.float32), (0, 0), 2), (W, H))[..., None]
        g = g * (1 - gm) + cv2.resize(g4, (W, H)).astype(np.float32) * gm
        layer = np.zeros_like(real); acc = np.zeros(real.shape[:2], np.float32)
        for sh in v["shards"]:
            q = min(1.0, max(0.0, (p - sh["delay"]) / (1 - sh["delay"]))) ** 2 * sh["spd"]
            if q >= 1.2:
                continue
            m = np.zeros(real.shape[:2], np.float32)
            cv2.fillConvexPoly(m, sh["poly"].astype(np.int32), 1.0)
            sc = 1 + 1.6 * q; ang = sh["rot"] * q
            tx, ty = sh["dir"] * 1400 * q + np.array([0, 500 * q * q])
            M = cv2.getRotationMatrix2D((float(sh["c"][0]), float(sh["c"][1])), ang, sc)
            M[:, 2] += (tx, ty)
            pw = cv2.warpAffine(g, M, (W, H), flags=cv2.INTER_LINEAR)
            mw = cv2.warpAffine(m, M, (W, H), flags=cv2.INTER_LINEAR) * max(0.0, 1 - q / 1.2)
            layer = layer * (1 - mw[..., None]) + pw * mw[..., None]
            acc = np.maximum(acc, mw)
        # סדקים דקים זוהרים שמתפשטים מנקודת הפגיעה החוצה (~4 פריימים), לא רשת גרפית על כל המסך
        if p < 0.2:
            edges = np.zeros(real.shape[:2], np.float32)
            for sh in v["shards"]:
                cv2.polylines(edges, [sh["poly"].astype(np.int32)], True, 1.0, 1, cv2.LINE_AA)
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            rad = np.hypot(xx - W / 2, yy - H * 0.42)
            reach = 250 + 1500 * (p / 0.2)
            front = np.clip((reach - rad) / 220, 0, 1)
            edges *= front
            glow = cv2.GaussianBlur(edges, (0, 0), 3.5) * 1.8 + edges * 0.9
            layer = layer + glow[..., None] * np.array([230, 242, 255], np.float32) * (1 - p / 0.2) * 0.9
        canvas = canvas * (1 - acc[..., None]) + layer * acc[..., None]
    out = real * al + canvas * (1 - al)
    if p < 0.3:   # רעד מצלמה קצר ודועך ברגע הפגיעה
        amp = 14 * (1 - p / 0.3)
        rng = np.random.default_rng(int(t * 1000))
        dx, dy = rng.uniform(-amp, amp, 2)
        out = cv2.warpAffine(out.astype(np.float32), np.float32([[1.02, 0, dx - 10.8], [0, 1.02, dy - 19.2]]),
                             (W, H), borderMode=cv2.BORDER_REFLECT)
    return np.clip(out, 0, 255)


_GRID = None


def hook_ripple_frame(v, clip, i, t):
    """'גל מציאות': הדוברת (אמיתית, matting) הולכת בעולם אפור (V2V). ברגע המילה, גל צבע יוצא
    ממנה החוצה ומחזיר את המועדון האמיתי — שפת הגל עם עיוות רדיאלי, סטייה כרומטית וזוהר חם.
    שתי השכבות חולקות את אותה תנועת מצלמה (V2V על אותו צילום) ⇒ אין החלקה."""
    import cv2
    global _GRID
    if _GRID is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); _GRID = (xx, yy)
    xx, yy = _GRID
    real = v["real"][min(i, len(v["real"]) - 1)].astype(np.float32)
    a8 = v["alpha"][min(i, len(v["alpha"]) - 1)]
    al = a8.astype(np.float32)[..., None] / 255
    k = min(len(clip) - 1, int(round(t * FPS)))
    g = clip[k].astype(np.float32)
    lum = g.mean(2, keepdims=True); g = g * (1 - v["desat"]) + lum * v["desat"]; g *= 0.9
    t0, d = v["ripple_at"], v["ripple_dur"]
    if t < t0:
        return real * al + g * (1 - al)
    p = min(1.0, (t - t0) / d)
    if p >= 1.0:
        return real
    # מרכז הגל = מרכז המסה של הדוברת (חזה/פנים)
    ys, xs = np.nonzero(a8[::8, ::8] > 128)
    cx, cy = (float(xs.mean() * 8), float(ys.mean() * 8 * 0.85)) if len(xs) else (W / 2, H * 0.45)
    pe = p * p * (3 - 2 * p)
    R = 80 + 2300 * (0.35 * p + 0.65 * pe)               # גל שרואים אותו נוסע, לא הבזק
    rad = np.hypot(xx - cx, yy - cy) + 1e-3
    band = 170.0
    e = (rad - R) / band                                   # 0 על השפה
    ring = np.exp(-e * e * 2.5)                            # פרופיל השפה
    # עיוות רדיאלי (עדשה) רק באזור השפה
    disp = ring * 30 * (1 - p * 0.5)
    ux, uy = (xx - cx) / rad, (yy - cy) / rad
    def sample(img, s):
        return cv2.remap(np.ascontiguousarray(img, dtype=np.float32), (xx - ux * disp * s).astype(np.float32), (yy - uy * disp * s).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    rs = np.dstack([sample(real[..., c], 1 + 0.12 * (c - 1)) for c in range(3)])   # סטייה כרומטית
    gs = sample(g, 1.0)
    inside = np.clip(0.5 - e * 1.6, 0, 1)[..., None]      # מעבר רך בתוך הגל
    out = rs * inside + gs * (1 - inside)
    glow = (ring ** 2)[..., None] * np.array([255, 205, 150], np.float32) * 0.32 * (1 - p)
    out = out + glow
    # ניצוצות קטנים על השפה
    rng = np.random.default_rng(int(t * 1000))
    n = 40
    ang = rng.uniform(0, 2 * np.pi, n); rr = R + rng.normal(0, 25, n)
    px = (cx + np.cos(ang) * rr).astype(int); py = (cy + np.sin(ang) * rr).astype(int)
    ok = (px > 2) & (px < W - 3) & (py > 2) & (py < H - 3)
    spark = np.zeros((H, W), np.float32); spark[py[ok], px[ok]] = 1.0
    spark = cv2.GaussianBlur(spark, (0, 0), 1.6) * 16
    out = out + spark[..., None] * np.array([255, 235, 200], np.float32) * (1 - p)
    zoom = 1 + 0.035 * (1 - p) ** 2                        # 'פאנץ'' קטן ברגע הפגיעה
    if zoom > 1.001:
        M = np.float32([[zoom, 0, cx - zoom * cx], [0, zoom, cy - zoom * cy]])
        out = cv2.warpAffine(out, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        realz = cv2.warpAffine(real, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        alz = cv2.warpAffine(al, M, (W, H))[..., None] if al.ndim == 3 else al
    else:
        realz, alz = real, al
    return np.clip(realz * alz + out * (1 - alz), 0, 255)


WHIP_TAIL = (41, 25, 11)   # אורך גרעין ה-motion blur (px) בשלושת הפריימים האמיתיים שאחרי הקאט


def whip_cut(clip):
    """פריים הקאט בקליפ ה-Hook = הטשטוש המקסימלי ב-60% האחרונים (ה-whip לתוך המועדון).
    אחריו המודל מייצר את הדוברת — גבול 'בלי בני אדם מיוצרים'. נמדד בפיילוט: פריים 48/72."""
    sh_ = [float(np.abs(np.diff(f[::8, ::8].mean(2), axis=1)).mean()) for f in clip]
    lo = int(len(clip) * 0.4)
    return lo + int(np.argmin(sh_[lo:]))


def motion_blur(img, L):
    import cv2
    if L <= 1:
        return img
    k = np.zeros((L, 1), np.float32); k[:, 0] = 1.0 / L      # אנכי — המצלמה צוללת מלמעלה
    return cv2.filter2D(img, -1, k, borderType=cv2.BORDER_REFLECT)


def cmd_compose(P: Project, a):
    plan = P.load("ai_plan.json")
    G = P.ai / "gen"
    proxy = (G / "PROXY").exists()
    ctl = probe(P.control); N = round(ctl["dur"] * FPS)
    by = {s["id"]: s for s in plan["shots"] if not (a.only and s["id"] not in a.only)}
    cdir = ensure_cues(P); seq = parse_caplist(cdir / "caplist.txt")
    y0 = a.caption_y or detect_caption_y(P, cdir, seq)
    cue_img = {}

    def cue_at(t):
        for s0, s1, f in seq:
            if s0 <= t < s1:
                if f == "_blank.png":
                    return None
                if f not in cue_img:
                    cue_img[f] = np.asarray(Image.open(cdir / f).convert("RGBA"))
                return cue_img[f]
        return None

    def with_cap(fr, t):
        c = cue_at(t)
        if c is None:
            return fr
        out = fr.astype(np.float32); al = c[..., 3:4].astype(np.float32) / 255
        out[y0:y0 + c.shape[0]] = out[y0:y0 + c.shape[0]] * (1 - al) + c[..., :3] * al
        return out

    ai = {}
    for sid in by:
        v = G / f"{sid}_video.mp4"
        if not v.exists():
            raise SystemExit(f"חסר {v.name} — להריץ generate")
        ai[sid] = read_frames(v)
    # פריימים נקיים (בלי כתוביות) רק בטווחים שצריך
    base = {}
    hook_cut, hook_tail, v2v = None, {}, None
    tails = {}
    hook_mode = RECIPES.get(by.get("hook", {}).get("recipe", ""), {}).get("compose") if "hook" in by else None
    mid_mode = RECIPES.get(by.get("mid", {}).get("recipe", ""), {}).get("compose") if "mid" in by else None
    if hook_mode in ("v2v_matte_shatter", "v2v_matte_ripple"):
        r = RECIPES[by["hook"]["recipe"]]
        h1 = int(round(by["hook"]["window"][1] * FPS))
        hseg = read_frames(P.base_clean, i0=0, n=h1)
        halpha = matte(hseg, P.ai / "cache" / f"alpha_hook_0_{h1}.npz")
        v2v = {"real": hseg, "alpha": halpha, "shatter": r.get("shatter_at"), "sh_dur": r.get("shatter_dur"),
               "shards": voronoi_shards(r.get("n_shards", 64), seed=7) if hook_mode == "v2v_matte_shatter" else None,
               "desat": r.get("grey_desat", 0.7), "mode": hook_mode,
               "ripple_at": r.get("ripple_at"), "ripple_dur": r.get("ripple_dur", 0.55)}
    elif "hook" in by:
        hi = int(round(by["hook"]["window"][1] * FPS))
        hook_cut = whip_cut(ai["hook"])
        # 3 פריימים אמיתיים אחרי הקאט עם motion blur יורד — ממשיך את ה-whip לצילום
        if P.base_clean:
            for k, f in enumerate(read_frames(P.base_clean, i0=hi, n=len(WHIP_TAIL))):
                hook_tail[hi + k] = motion_blur(f, WHIP_TAIL[k])
    if mid_mode == "replace_window_flash":
        me = int(round(by["mid"]["window"][1] * FPS))
        tails.update({me + k: ("flash_out", 1 - (k + 1) / 4) for k in range(3)})
    # CTA: matte + registration + color-match
    cta_ctx = None
    if "cta" in by:
        cs = by["cta"]["window"][0]; i0 = int(round(cs * FPS))
        seg = read_frames(P.base_clean, i0=i0 - 1, n=N - i0 + 1)
        for k, f in enumerate(seg):
            base[i0 - 1 + k] = f
        alpha = matte(seg, P.ai / "cache" / f"alpha_{i0}.npz")
        bgmask = (alpha[1] < 20).astype(np.float32)
        first_ai = ai["cta"][0]
        M0 = register(first_ai, seg[1], bgmask)            # AI → פריים הייחוס
        if M0 is None:
            M0 = np.eye(2, 3, dtype=np.float32)
        cmp = color_match_params(warp(first_ai, M0), seg[1], bgmask)
        # matchmove: תנועת המצלמה האמיתית (דריפט עד ~30px) מוחלת על הרקע של ה-AI
        track = {}
        for k in range(1, len(seg)):
            mk = ((alpha[k] < 20) & (alpha[1] < 20)).astype(np.float32)
            Mi = register(seg[1], seg[k], mk)
            Mi = np.eye(2, 3, dtype=np.float32) if Mi is None else Mi
            track[i0 - 1 + k] = (m3(M0) @ m3(Mi))[:2]
        cta_ctx = {"i0": i0, "alpha": alpha, "track": track, "cm": cmp}

    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", str(P.control), "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-crf", str(a.crf), "-preset", "slow", "-pix_fmt", "yuv420p",
                            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                            "-c:a", "copy", "-movflags", "+faststart", str(P.ai / "_compose_tmp.mp4")],
                           stdin=subprocess.PIPE)
    ctl_frames = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(P.control), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                  stdout=subprocess.PIPE)
    seams = {}
    for i in range(N):
        b = ctl_frames.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        fr = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        t = i / FPS; out = None
        for sid, s in by.items():
            w0, w1 = s["window"]
            if not (w0 - 1e-6 <= t < w1 - 1e-6):
                continue
            clip = ai[sid]; u = (t - w0) / (w1 - w0)
            if sid == "hook" and v2v is not None:
                fn = hook_ripple_frame if v2v["mode"] == "v2v_matte_ripple" else hook_v2v_frame
                out = with_cap(fn(v2v, clip, i, t), t)
            elif sid == "hook":
                # רק עד שיא ה-whip (הטשטוש המקסימלי) — אחריו המודל מצייר את הדוברת ⇒ לא משתמשים
                k = min(hook_cut, int(round(u * hook_cut)))
                out = with_cap(clip[k].astype(np.float32), t)
            elif sid == "mid":
                k = min(len(clip) - 1, int(round(u * (len(clip) - 1))))
                mf = clip[k].astype(np.float32)
                if mid_mode == "replace_window_flash":      # 4 פריימים אחרונים: הלבנה → קאט לדוברת
                    rem = int(round((w1 - t) * FPS))
                    if rem <= 4:
                        x = (5 - rem) / 5; mf = mf * (1 - x) + 255 * x
                out = with_cap(mf, t)
            elif sid == "cta":
                c = cta_ctx; j = i - c["i0"] + 1
                ks = int(round(RECIPES[by["cta"]["recipe"]].get("clip_start", 0) * FPS))   # דילוג על פתיח סטטי בקליפ
                k = min(len(clip) - 1, ks + int(round(u * (len(clip) - 1 - ks))))
                bg = apply_cm(warp(clip[k], c["track"].get(i, next(iter(c["track"].values())))), c["cm"])
                real = base[min(i, max(base))].astype(np.float32)
                x = min(1.0, (t - w0) / 0.25)                     # כניסה רכה לרקע ה-AI
                bg = real * (1 - x) + bg * x
                al = c["alpha"][min(j, len(c["alpha"]) - 1)].astype(np.float32)[..., None] / 255
                comp = real * al + bg * (1 - al)
                comp = push(np.clip(comp, 0, 255).astype(np.uint8), 1 + (RECIPES[by["cta"]["recipe"]]["push_in"] - 1) * ease(u))
                out = with_cap(comp.astype(np.float32), t)
        if out is None and i in tails and tails[i][0] == "flash_out":
            x = tails[i][1] * 0.85; out = fr.astype(np.float32) * (1 - x) + 255 * x
        if out is None and i in hook_tail:
            out = with_cap(hook_tail[i].astype(np.float32), t)
        if out is None:
            out = fr
        enc.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close(); enc.wait(); ctl_frames.wait()
    name = a.name or f"{P.dir.name}_AI{'_PROXY' if proxy else ''}.mp4"
    dst = P.ai / name
    (P.ai / "_compose_tmp.mp4").replace(dst)
    meta = {"output": str(dst), "sha256": sha256(dst), "caption_y": y0, "proxy": proxy,
            "shots": {k: v["window"] for k, v in by.items()}, "built_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    P.save("compose.json", meta)
    print(json.dumps(meta, ensure_ascii=False, indent=1))


# ───────────────────────────── QA (measured)
def _psnr(a, b):
    m = np.mean((a.astype(float) - b.astype(float)) ** 2)
    return 99.0 if m == 0 else 10 * math.log10(255 ** 2 / m)


def cmd_qa(P: Project, a):
    meta = P.load("compose.json"); plan = P.load("ai_plan.json")
    out = Path(meta["output"]); q = {}
    pc, po = probe(P.control), probe(out)
    q["G1_duration_equal"] = {"control": round(pc["dur"], 3), "ai": round(po["dur"], 3),
                              "pass": abs(pc["dur"] - po["dur"]) < 0.05}
    am = lambda p: sh(["ffmpeg", "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy", "-f", "md5", "-"]).strip()
    q["G2_audio_bit_identical"] = {"pass": am(P.control) == am(out)}
    q["G3_format"] = {"w": po["w"], "h": po["h"], "fps": round(po["fps"], 2),
                      "pass": (po["w"], po["h"]) == (W, H) and abs(po["fps"] - 30) < .01}
    wins = [s["window"] for s in plan["shots"]]
    inside = lambda t: any(w0 - 0.1 <= t <= w1 + 0.1 for w0, w1 in wins)
    ts = [t for t in np.arange(0.3, pc["dur"] - 0.1, 0.9) if not inside(t)]
    ps = []
    for t in ts:
        f1 = np.asarray(Image.open(frame_at(P.control, t, P.ai / "cache/_q1.png")).convert("RGB"))
        f2 = np.asarray(Image.open(frame_at(out, t, P.ai / "cache/_q2.png")).convert("RGB"))
        ps.append(_psnr(f1, f2))
    q["G4_outside_windows_unchanged"] = {"min_psnr": round(min(ps), 1), "n": len(ps), "pass": min(ps) >= 33}
    # seams
    seams = {}
    for s in plan["shots"]:
        w0, w1 = s["window"]
        for side, t in (("in", w0), ("out", w1)):
            if t >= pc["dur"] - 0.05 or t <= 0.01:
                continue
            j = []
            for v in (out, P.control):
                f1 = np.asarray(Image.open(frame_at(v, t - 1 / FPS, P.ai / "cache/_s1.png")).convert("L"), float)
                f2 = np.asarray(Image.open(frame_at(v, t + 1 / FPS, P.ai / "cache/_s2.png")).convert("L"), float)
                j.append(round(float(np.abs(f1 - f2).mean()), 1))
            seams[f"{s['id']}_{side}"] = {"ai": j[0], "control": j[1]}
    hk = seams.get("hook_out"); blur_ratio = None
    hs = next((s for s in plan["shots"] if s["id"] == "hook"), None)
    hmode = RECIPES.get(hs["recipe"], {}).get("compose") if hs else None
    if hs and hmode in ("v2v_matte_shatter", "v2v_matte_ripple"):
        # אחרי השבירה הפריימים אמיתיים ⇒ היציאה מהחלון חייבת להיות חלקה כמו ב-Control
        ok5 = hk is None or hk["ai"] <= max(12.0, hk["control"] * 2.5)
        q["G5_seam"] = {"mean_abs_diff": seams, "pass": ok5,
                        "note": "Hook V2V+shatter: יציאה מהחלון לצילום האמיתי חייבת להיות חלקה"}
    elif hs:   # הקאט ל-Hook מוסתר בתוך ה-whip: הפריים האחרון של ה-AI חייב להיות מטושטש (חדות < 50% מהחציון)
        def sharp(t):
            g = np.asarray(Image.open(frame_at(out, t, P.ai / "cache/_s3.png")).convert("L"), float)[:1300]
            return float(np.abs(np.diff(g, axis=1)).mean())
        T = hs["window"][1]
        med = float(np.median([sharp(x) for x in np.linspace(0.1, T - 0.3, 5)]))
        blur_ratio = round(sharp(T - 1.5 / FPS) / med, 2)
    if not (hs and hmode in ("v2v_matte_shatter", "v2v_matte_ripple")):
        q["G5_seam"] = {"mean_abs_diff": seams, "hook_whip_blur_ratio": blur_ratio,
                        "pass": blur_ratio is None or blur_ratio < 0.5,
                        "note": "Hook: קאט בתוך שיא ה-whip (בלי דוברת מיוצרת) — נבדקת חדות הפריים לפני הקאט, לא גודל הקפיצה. mid_in/mid_out/cta_in = קאטים מכוונים"}
    # sheet
    tt = sorted({round(x, 2) for s in plan["shots"] for x in np.linspace(s["window"][0], min(s["window"][1], pc["dur"] - 0.05), 6)})
    ims = [cover(Image.open(frame_at(out, t, P.ai / f"qa/f_{t:.2f}.jpg")), 216, 384) for t in tt]
    cols = 6; rows = math.ceil(len(ims) / cols)
    sheet = Image.new("RGB", (216 * cols, 404 * rows), "white"); d = ImageDraw.Draw(sheet)
    for n, (t, im) in enumerate(zip(tt, ims)):
        x, y = (n % cols) * 216, (n // cols) * 404
        sheet.paste(im, (x, y + 20)); d.text((x + 4, y + 4), f"{t:.2f}s", fill="black")
    sheet.save(P.ai / "qa" / "ai_windows_sheet.jpg", quality=85)
    q["pass"] = all(v.get("pass", True) for v in q.values() if isinstance(v, dict))
    q["vision_check"] = "חובה: לפתוח qa/ai_windows_sheet.jpg — עיוותי פנים/ידיים, טקסט מומצא, 'AI slop', רציפות במסירה"
    P.save("qa.json", q)
    print(json.dumps(q, ensure_ascii=False, indent=1))


# ───────────────────────────── package + experiment
def cmd_package(P: Project, a):
    meta = P.load("compose.json"); plan = P.load("ai_plan.json")
    from budget import Ledger
    L = Ledger(P.ai / "ledger.json")
    if meta.get("proxy") and not a.allow_proxy:
        raise SystemExit("⛔ הגרסה בנויה מ-PROXY — לא נמסרת לאלי")
    dest = Path(a.dest); dest.mkdir(parents=True, exist_ok=True)
    c = dest / f"{a.prefix}_CONTROL.mp4"; v = dest / f"{a.prefix}_AI.mp4"
    shutil.copy2(P.control, c); shutil.copy2(meta["output"], v)
    assert sha256(c) == plan["control_sha256"], "ה-Control השתנה!"
    exp = {"experiment_id": f"{a.prefix}_{time.strftime('%Y%m%d')}", "created": time.strftime("%Y-%m-%d"),
           "hypothesis": "שכבת AI ב-Hook וב-CTA (אותו דובר/תסריט/Offer/CTA) משפרת את כלכלת הקמפיין — לא רק צפיות",
           "variable": "AI visual layer only", "control": {"file": c.name, "sha256": sha256(c)},
           "variant": {"file": v.name, "sha256": sha256(v), "shots": plan["shots"]},
           "ai_spend": L.summary(), "held_constant": ["audience", "offer", "copy", "cta", "placements", "budget/day", "run length", "landing page"],
           "success_rule": "הצלחה = CPL טוב ב-15%+ ואיכות ליד/סגירות לא יורדות. צפיות גבוהות בלי שיפור ב-CPL/CAC ≠ הצלחה",
           "metrics_chain": ["hook_rate_3s", "thruplay_rate", "avg_watch_time", "ctr_link", "leads", "cpl",
                             "lead_quality (פגישת יעדים שנקבעה/התקיימה)", "closes", "cac"],
           "results": {"control": {}, "ai": {}}}
    (dest / "experiment.json").write_text(json.dumps(exp, ensure_ascii=False, indent=1), encoding="utf-8")
    (dest / "בריף לאלי - ניסוי AI.md").write_text(eli_brief(exp, c.name, v.name, a), encoding="utf-8")
    P.save("experiment.json", exp)
    with open(HERE / "experiments.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({k: exp[k] for k in ("experiment_id", "created", "control", "variant", "ai_spend")},
                           ensure_ascii=False) + "\n")
    print(json.dumps({"dest": str(dest), "control": c.name, "ai": v.name, "spend": L.summary()}, ensure_ascii=False, indent=1))


def eli_brief(exp, cname, vname, a):
    """טקסט מסירה לאלי — ווצאפ בשם הראל. בלי אמוג'י מיותר, CTA אחד (להרים את הניסוי)."""
    return f"""# בריף לאלי — ניסוי AI מול Control ({a.prefix})

## הודעת ווצאפ (להעתקה)

אהלן אלי!
מצורפות שתי גרסאות של אותו סרטון ל{a.period or 'תקופה הבאה'} — תושבי אריאל והסביבה:
{cname} — הסרטון כמו שהוא.
{vname} — אותו סרטון בדיוק (אותו קול, תסריט, הצעה ו-CTA), עם שכבה ויזואלית בפתיחה ובסיום.

אני רוצה לבדוק רק את ההבדל הזה, אז כל השאר זהה:
Meta A/B Test (Experiments) — שני ad sets זהים, 50/50 מתוך התקציב של התקופה.
אותו קהל, אותם Placements, אותו טקסט, אותה כותרת, אותו כפתור, אותו עמוד נחיתה ואותו תאריך התחלה וסיום.
הדבר היחיד שמשתנה: utm_content=control בגרסה הראשונה ו-utm_content=ai בשנייה, כדי שנוכל לעקוב עד סגירה.

בסוף הריצה אני צריך לכל גרסה: Hook rate (צפיות 3 שניות), ThruPlay, CTR, לידים ו-CPL.
את האיכות והסגירות אני מושך מהמערכת שלנו לפי ה-utm.

הקבצים מוכנים כמו שהם — 1080x1920, כתוביות צרובות, שמע מנורמל.
תגיד לי אם חסר משהו.
— הראל | קרוספיט אריאל

## לנו (לא לשליחה)
- כלל הצלחה: {exp['success_rule']}
- שרשרת מדדים: {' → '.join(exp['metrics_chain'])}
- עלות שכבת ה-AI: ₪{exp['ai_spend'].get('spent_ils')}
"""


def cmd_prices(P, a):
    import hf_client as hf
    for m in MODELS["video_tiers"]:
        for d in (3, 5):
            if d < m["durations"][0]:
                continue
            print(m["id"], f"{d}s", est_usd(m["id"], d))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["analyze", "plan", "keyframes", "generate", "compose", "qa", "package", "prices"])
    ap.add_argument("project", help="תיקיית הפרויקט ב-rel-video-work")
    ap.add_argument("--control", help="נתיב ה-Control (ברירת מחדל: FINAL.mp4 של הפרויקט)")
    ap.add_argument("--out", help="תיקיית עבודה (ברירת מחדל: <project>/ai_enhancement)")
    ap.add_argument("--no-hook", action="store_true"); ap.add_argument("--no-mid", action="store_true")
    ap.add_argument("--no-cta", action="store_true")
    ap.add_argument("--shot", action="append", help="generate: רק שוט/פריט מסוים (אפשר כמה)")
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--escalate", type=int, default=0, help="1 = המודל הבא ב-model_pref (Escalation)")
    ap.add_argument("--proxy", action="store_true", help="generate: תחליפים מקומיים חינמיים לבדיקת צנרת")
    ap.add_argument("--only", action="append"); ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--caption-y", type=int); ap.add_argument("--name")
    ap.add_argument("--dest"); ap.add_argument("--prefix", default="ARIEL_CAMPAIGN")
    ap.add_argument("--allow-proxy", action="store_true")
    ap.add_argument("--period", help="package: שם התקופה לבריף (למשל 'תקופה 2 — 05.10')")
    a = ap.parse_args()
    P = Project(a.project, a.control, a.out)
    globals()[f"cmd_{a.cmd}"](P, a)


if __name__ == "__main__":
    main()
