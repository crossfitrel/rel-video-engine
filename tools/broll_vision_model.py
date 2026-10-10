#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_vision_model — מה **רואים** בקליפ, לפי מודל-ראייה ולא לפי גלאי פיקסלים.

הרקע: `broll_vision.py` (Haar+HOG) נמדד ונפסל ב-31.7.26 — הוא החזיר `solo`
על "ברפיז בשיעור" (שיעור מלא) ועל "שיעור ילדים". גלאי פנים על צילום חדר
כושר, כשרוב האנשים לא פונים למצלמה, פשוט לא סופר. **אות שמשקר גרוע מאין
אות**, ולכן הוא לא חובר לשום שער.

כאן הפאס מסתכל על הפריימים כמו שאדם מסתכל: 3 פריימים לקליפ, גיליון-מגע,
ומודל שמחזיר תשובה מובנית. הפלט הוא ראיה שנשמרת במטמון פר-קליפ.

**שדות התשובה** (לכל קליפ):
  people      — כמה אנשים נראים בפריים (0 = אין אדם)
  crowding    — empty | solo | few | busy | full_class
  shot        — wide | medium | close
  faces       — true אם פנים מזוהות בפריים (v9.7: בלי פנים אין אימות זהות)
  camera      — static | handheld | moving
  note        — משפט אחד, למה זה מה שרואים

מטמון: `בירולים/vision-cache-model.json`, ממופתח `file|mtime|size` — קליפ
שהוחלף נסרק מעצמו מחדש. **קליפ אינו נסרק פעמיים.**

    python3 broll_vision_model.py sheets  --files a.mp4 b.mp4 --out DIR
    python3 broll_vision_model.py request --proj P --files ... --out DIR
    python3 broll_vision_model.py apply   --proj P
    python3 broll_vision_model.py status
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

CFG = HERE / "broll-catalog-config.json"
FRAMES_PER_CLIP = 3
CELL_W, CELL_H = 300, 533
CLIPS_PER_SHEET = 6

CROWDING = ("empty", "solo", "few", "busy", "full_class")
SHOTS = ("wide", "medium", "close")
CAMERA = ("static", "handheld", "moving")


def cache_path() -> Path:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    return Path(cfg["catalog_path"]).parent / "vision-cache-model.json"


def clip_key(p) -> str:
    """מפתח יציב לקליפ. `mtime`+`size` ולא זמן-ריצה — ערך שמשתנה בלי
    שהקלט השתנה שובר את ה-digest של הפאס (הלקח מ-v9.5)."""
    st = Path(p).stat()
    return f"{Path(p).name}|{int(st.st_mtime)}|{st.st_size}"


def load_cache() -> dict:
    p = cache_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_cache(c: dict) -> None:
    p = cache_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def lookup(path) -> dict | None:
    return load_cache().get(clip_key(path))


def missing(paths) -> list:
    """מי עדיין בלי ראיה. זה מה שמגדיר את היקף הסריקה הבאה."""
    c = load_cache()
    out, seen = [], set()
    for p in paths:
        try:
            k = clip_key(p)
        except OSError:
            continue
        if k not in c and k not in seen:
            seen.add(k)
            out.append(p)
    return out


# ─────────────────────────────────────────────── גיליונות-מגע
def _strip(path, dest_dir: Path, ref: str):
    """שלושה פריימים לאורך הקליפ. פריים בודד אינו מספיק להכריע 'שיעור מלא
    או יחיד' — אדם נכנס לפריים, המצלמה זזה, והרגע הראשון משקר."""
    from PIL import Image
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        dur = float((r.stdout or "0").strip())
    except ValueError:
        dur = 3.0
    band = Image.new("RGB", (CELL_W * FRAMES_PER_CLIP, CELL_H), "black")
    for k, frac in enumerate((0.2, 0.5, 0.8)):
        f = dest_dir / f"{ref}_{k}.jpg"
        if not f.exists():
            cmd = ["ffmpeg", "-nostdin", "-loglevel", "error",
                   "-ss", f"{max(0.05, dur * frac):.2f}", "-i", str(path),
                   "-frames:v", "1",
                   "-vf", f"scale={CELL_W - 4}:{CELL_H - 4}"
                          f":force_original_aspect_ratio=decrease,"
                          f"pad={CELL_W}:{CELL_H}:(ow-iw)/2:(oh-ih)/2:black",
                   "-y", str(f)]
            if subprocess.run(cmd, capture_output=True).returncode:
                return None
        band.paste(Image.open(f).convert("RGB"), (k * CELL_W, 0))
    return band


def build_sheets(paths, out: Path) -> list:
    """גיליון = 6 קליפים, כל אחד רצועה של 3 פריימים, עם ref צרוב."""
    from PIL import Image, ImageDraw, ImageFont
    out.mkdir(parents=True, exist_ok=True)
    (out / "_f").mkdir(exist_ok=True)
    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf", 44)
    except OSError:
        font = ImageFont.load_default()

    items, sheets = [], []
    for i, p in enumerate(paths, 1):
        items.append((f"c{i:03d}", p))

    per = CLIPS_PER_SHEET
    for s in range(0, len(items), per):
        chunk = items[s:s + per]
        sheet = Image.new("RGB", (CELL_W * FRAMES_PER_CLIP, CELL_H * len(chunk)),
                          "black")
        draw = ImageDraw.Draw(sheet)
        for k, (ref, p) in enumerate(chunk):
            band = _strip(p, out / "_f", ref)
            if band is None:
                continue
            sheet.paste(band, (0, k * CELL_H))
            draw.rectangle([6, k * CELL_H + 6, 132, k * CELL_H + 62], fill="black")
            draw.text((14, k * CELL_H + 10), ref, fill="yellow", font=font)
        dst = out / f"vision_{s // per + 1:02d}.jpg"
        sheet.save(dst, quality=86)
        sheets.append(str(dst))
    return sheets


# ─────────────────────────────────────────────── חוזה התשובה
def validate(answer: dict, refs: dict) -> dict:
    """אוכפת שכל ref קיים ושכל ערך בטווח. תשובה חלקית **נדחית** —
    ‏`clips` חסר או ערך לא-מוכר הם בדיוק המצב שבו אות משקר נכנס פנימה."""
    if not isinstance(answer, dict) or "clips" not in answer:
        raise ValueError("תשובה בלי מפתח clips")
    out = {}
    for c in answer["clips"]:
        ref = c.get("ref")
        if ref not in refs:
            raise ValueError(f"ref לא קיים במרחב: {ref}")
        if c.get("crowding") not in CROWDING:
            raise ValueError(f"{ref}: crowding לא חוקי: {c.get('crowding')}")
        if c.get("shot") not in SHOTS:
            raise ValueError(f"{ref}: shot לא חוקי: {c.get('shot')}")
        if c.get("camera") not in CAMERA:
            raise ValueError(f"{ref}: camera לא חוקי: {c.get('camera')}")
        people = c.get("people")
        if not isinstance(people, int) or people < 0 or people > 60:
            raise ValueError(f"{ref}: people לא חוקי: {people}")
        if not isinstance(c.get("faces"), bool):
            raise ValueError(f"{ref}: faces חייב להיות בוליאני")
        # עקביות פנימית: לא ייתכן 'שיעור מלא' עם אדם אחד.
        if c["crowding"] in ("busy", "full_class") and people < 3:
            raise ValueError(f"{ref}: crowding={c['crowding']} אבל people={people}")
        if c["crowding"] == "solo" and people != 1:
            raise ValueError(f"{ref}: crowding=solo אבל people={people}")
        if c["crowding"] == "empty" and people != 0:
            raise ValueError(f"{ref}: crowding=empty אבל people={people}")
        out[ref] = {"people": people, "crowding": c["crowding"],
                    "shot": c["shot"], "faces": c["faces"],
                    "camera": c["camera"], "note": (c.get("note") or "")[:200]}
    seen = set(out) & set(refs)
    if len(seen) != len(refs):
        raise ValueError(f"חסרים קליפים בתשובה: {sorted(set(refs) - seen)[:5]}")
    return out


PROMPT = """אתה פאס ראייה בצינור עריכת סרטוני סושיאל של מועדון קרוספיט.

לפניך גיליונות. כל שורה היא קליפ אחד, מסומן ב-ref צהוב משמאל, ובה שלושה
פריימים לאורך הקליפ (20%, 50%, 80%).

לכל ref החזר אובייקט:
  ref       — המזהה בדיוק כפי שמופיע
  people    — כמה **בני אדם** נראים בפריימים (המקסימום מבין השלושה). 0 אם אין
  crowding  — empty (אין אדם) | solo (אחד) | few (2-3) | busy (4-8) |
              full_class (שיעור מלא, 9+ או שורת מתאמנים)
  shot      — wide (רואים את הרחבה/החלל) | medium (גוף מלא) | close (פרט)
  faces     — true אם אפשר לזהות פנים של מישהו בפריים, אחרת false
  camera    — static | handheld | moving
  note      — משפט קצר בעברית: מה רואים

חוקי ברזל:
1. ספור מה שרואים, לא מה שהשם מרמז. אנשים ברקע נספרים.
2. ‏`faces` הוא false גם כשיש אדם אבל הפנים הפוכות/מהגב/חתוכות.
3. אל תשאיר ref בלי תשובה.

החזר JSON יחיד: {"clips":[...]}"""


# ─────────────────────────────────────────────── CLI
def _refs_for(paths) -> dict:
    return {f"c{i:03d}": str(p) for i, p in enumerate(paths, 1)}


def _paths_from(a) -> list:
    """שמות קבצים בעברית עם רווחים שוברים העברה דרך shell — `--files-from`
    הוא המסלול האמין, ורשימה בקובץ היא גם ראיה למה נסרק."""
    if getattr(a, "files_from", None):
        return [l for l in Path(a.files_from).read_text(
            encoding="utf-8").splitlines() if l.strip()]
    return list(a.files or [])


def cmd_request(a) -> int:
    paths = [p for p in _paths_from(a) if Path(p).exists()]
    todo = missing(paths) if not a.force else paths
    if not todo:
        print(f"אין מה לסרוק — כל {len(paths)} הקליפים כבר במטמון")
        return 0
    out = Path(a.out).expanduser()
    refs = _refs_for(todo)
    sheets = build_sheets(todo, out)
    req = {"role": "vision", "prompt": PROMPT, "sheets": sheets,
           "refs": {r: Path(p).name for r, p in refs.items()},
           "keys": {r: clip_key(p) for r, p in refs.items()}}
    (out / "request.json").write_text(
        json.dumps(req, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"לסריקה: {len(todo)} קליפים · {len(sheets)} גיליונות → {out}")
    for s in sheets:
        print("  " + s)
    print(f"\nכתוב את התשובה אל: {out / 'answer.json'}")
    return 0


def cmd_apply(a) -> int:
    out = Path(a.out).expanduser()
    req = json.loads((out / "request.json").read_text(encoding="utf-8"))
    ans = json.loads((out / "answer.json").read_text(encoding="utf-8"))
    got = validate(ans, req["refs"])
    cache = load_cache()
    for ref, val in got.items():
        cache[req["keys"][ref]] = dict(val, file=req["refs"][ref],
                                       source="model", prompt="vision.v1.0")
    save_cache(cache)
    print(f"נשמרו {len(got)} קליפים במטמון · סה\"כ {len(cache)}")
    return 0


def cmd_status(a) -> int:
    c = load_cache()
    from collections import Counter
    print(f"קליפים במטמון: {len(c)}")
    print("crowding:", dict(Counter(v.get("crowding") for v in c.values())))
    print("shot:", dict(Counter(v.get("shot") for v in c.values())))
    print("faces=false:", sum(1 for v in c.values() if v.get("faces") is False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("request"); r.add_argument("--files", nargs="+")
    r.add_argument("--files-from"); r.add_argument("--out", required=True)
    r.add_argument("--force", action="store_true")
    r.set_defaults(fn=cmd_request)
    p = sub.add_parser("apply"); p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_apply)
    s = sub.add_parser("status"); s.set_defaults(fn=cmd_status)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
