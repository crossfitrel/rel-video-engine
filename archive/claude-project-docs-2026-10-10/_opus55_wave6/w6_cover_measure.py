"""גל 6 (v9.34) — קאבר garbled: ייחוס ברמת מילה (מדידה לפני תיקון).

הייחוס הקיים (cover_vision.manual_layout) משווה שורה שלמה — מילה משובשת אחת
בתת-כותרת של 4 מילים מדוללת בשלוש תקינות (תפיסה 50%). כאן: גבולות המילים
נלקחים מהפריסה הידנית (ידועים), מוקרנים יחסית על bbox הדיו בפועל, ו-F נמדד
לכל מילה בנפרד. חיוביים: קאברי cover_make. שליליים: הבונה הקנוני עם
(א) כל המילים מעורבבות (ההזרקה של גל 1) (ב) מילה אחת בלבד מעורבבת (קשה).

  $P _opus55_wave6/w6_cover_measure.py SYSTEM_DIR
"""
import sys, json, os, tempfile, contextlib, io
from pathlib import Path
S = Path(sys.argv[1]); sys.path.insert(0, str(S / "tools" / "thumbnail"))
import numpy as np, cv2
import cover_vision as cvv
import thumbnail_build as tb
from PIL import Image, ImageDraw

R = Path.home() / "rel-video-work"
OUT = S / "_opus55_wave6" / "cover_rows.json"


def layout_words(text, kind, size=200, reverse=False):
    """כמו manual_layout, ומחזיר גם טווחי x לכל מילה (בקואורדינטות התמונה)."""
    fonts = cvv._fonts_for(kind, size)
    pieces = []          # (unit, font, word_idx)
    wi = 0
    runs, cur, cur_he = [], "", None
    for ch in text:
        he = not (ch.isascii() and ch.isalnum())
        if cur_he is None or he == cur_he or ch == " ":
            cur += ch; cur_he = he if cur_he is None or ch != " " else cur_he
        else:
            runs.append((cur, cur_he)); cur, cur_he = ch, he
    if cur:
        runs.append((cur, cur_he))
    for t, he in runs:
        for u in (list(t) if he else [t]):
            if u == " ":
                wi += 1
            f = next((fo for fo, cov in fonts if cov is None or all(c in cov or c == " " for c in u)),
                     fonts[-1][0])
            pieces.append((u, f, wi))
    widths = [max(1, int(round(f.getlength(u)))) for u, f, _ in pieces]
    Wt = sum(widths) + 20
    img = Image.new("L", (Wt, int(size * 1.8)), 0)
    d = ImageDraw.Draw(img)
    spans = {}
    x = Wt - 10 if not reverse else 10
    for (u, f, w_i), w in zip(pieces, widths):
        if not reverse:
            x -= w; x0 = x
        else:
            x0 = x; x += w
        d.text((x0, int(size * 1.2)), u, font=f, fill=255, anchor="ls")
        if u != " ":
            a, b = spans.get(w_i, (x0, x0 + w))
            spans[w_i] = (min(a, x0), max(b, x0 + w))
    return np.asarray(img) > 127, [spans[k] for k in sorted(spans)]


def word_scores(obs, text, kind):
    ref, spans = layout_words(text, kind)
    ys, xs = np.where(ref)
    oy, ox = np.where(obs)
    if not len(xs) or not len(ox):
        return []
    rx0, rx1 = xs.min(), xs.max() + 1
    ox0, ox1 = ox.min(), ox.max() + 1
    sc = (ox1 - ox0) / float(rx1 - rx0)
    out = []
    for (a, b) in spans:
        a, b = max(a, rx0), min(b, rx1)
        if b - a < 4:
            continue
        pad = 2
        ra, rb = int(a) - pad, int(b) + pad
        oa, ob = int(ox0 + (a - rx0) * sc) - pad, int(ox0 + (b - rx0) * sc) + pad
        r_sl = np.zeros_like(ref); r_sl[:, max(0, ra):rb] = ref[:, max(0, ra):rb]
        o_sl = np.zeros_like(obs); o_sl[:, max(0, oa):ob] = obs[:, max(0, oa):ob]
        out.append(round(cvv.fscore(o_sl, r_sl), 3))
    return out


def measure(png, title, subtitle, brand):
    r = cvv.analyze(png, title, subtitle, brand)
    ch = r.get("checks", {})
    lines = (ch.get("CV2_two_lines") or {}).get("lines") or []
    if len(lines) < 2:
        return {"flags": r.get("flags"), "n_lines": len(lines)}
    bgr = cv2.imread(str(png)); rgb = bgr[..., ::-1]
    top, bot, _ = cvv.find_box(rgb, cvv.load_calibration())
    _, white = cvv.text_lines(rgb, top, bot, cvv.load_calibration())
    res = {"flags": r.get("flags"), "n_lines": 2,
           "line_f": [(x["line"], x["f_ok"]) for x in (ch.get("CV5_order") or {}).get("lines", [])]}
    for kind, txt, (y0, y1) in (("title", title, lines[0]), ("sub", subtitle, lines[1])):
        m = white[y0 - top:y1 - top]
        res[f"w_{kind}"] = word_scores(m, txt, kind)
    return res


def scramble(x, only_one=False):
    ws = x.split(" "); done = False
    out = []
    for w in ws:
        if len(w) > 2 and not (only_one and done):
            out.append(w[1:] + w[0]); done = True
        else:
            out.append(w)
    return " ".join(out)


rows = {"pos": [], "neg": {}}
tmp = tempfile.mkdtemp(prefix="w6cov_")
for W in sorted(R.glob("*/cover_report.json")):
    W = W.parent
    if W.name.startswith("_") or not (W / "thumbnail.png").exists():
        continue
    rep = json.loads((W / "cover_report.json").read_text(encoding="utf-8"))
    t, s, b = rep.get("title"), rep.get("subtitle"), rep.get("brand", "rel")
    png = Path(rep.get("out") or W / "thumbnail.png")
    if not png.exists():
        png = W / "thumbnail.png"
    if not t or not s:
        continue
    rows["pos"].append({"w": W.name, "title": t, "sub": s, **measure(png, t, s, b)})
    frame = rep.get("frame")
    if not frame or not os.path.exists(frame):
        continue
    box = cvv.BRANDS.get(b)
    for kind, (tt, ss) in {"scr_all": (scramble(t), scramble(s)),
                           "scr_one_sub": (t, scramble(s, True)),
                           "scr_one_title": (scramble(t, True), s)}.items():
        if (tt, ss) == (t, s):
            continue
        out = os.path.join(tmp, f"{W.name}_{kind}.png")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                tb.build(frame, tt, ss, out, box_color=box)
        except SystemExit:
            continue
        rows["neg"].setdefault(kind, []).append({"w": W.name, **measure(out, t, s, b)})
    print(W.name, flush=True)
OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE", len(rows["pos"]), {k: len(v) for k, v in rows["neg"].items()})
