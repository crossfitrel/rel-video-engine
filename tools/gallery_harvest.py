#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gallery_harvest.py — קציר בירולים מספריית התמונות של הראל.

משפך ארבע-שלבי. כל שלב זול מקודמו וזורק את מה שאפשר לזרוק בחינם,
כדי ששלב יקר (הורדה מ-iCloud / שיפוט מודלי) יראה רק מועמדים אמיתיים.

  scan     שלב 1 — מטא-דאטה מ-Photos.sqlite (חינם, קריאה בלבד)
  screen   שלב 2 — מדידה טכנית על התצוגה המקדימה המקומית מול המעטפת הנמדדת
  sheets   שלב 3 — גיליונות מגע לשיפוט תוכן מודלי
  verdict  שלב 3ב — קליטת פסקי-הדין של המודל לפנקס
  fetch    שלב 4 — הורדת מקור מ-iCloud רק למי שעבר הכל
  status   דוח מצב הפנקס

הפנקס (gallery_ledger.json) זוכר כל נכס שנבדק אי-פעם ואת הסיבה שנפסל,
כדי שהריצה השבועית לעולם לא תבדוק את אותו סרטון פעמיים.
"""
import argparse, datetime, glob, json, os, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gallery_metrics import metrics_from_path

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
LIB = Path.home() / "Pictures" / "Icloud Photos.photoslibrary"
LEDGER = HERE / "gallery_ledger.json"
REFERENCE = HERE / "gallery_reference.json"
EPOCH = datetime.datetime(2001, 1, 1)

# שערי מטא-דאטה — קשיחים, לא נגזרים ממדידה (מגבלות פורמט, לא איכות)
MIN_DUR = 2.0
MAX_DUR = 180.0
MIN_SIDE = 720


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"created_at": now(), "assets": {}}


def save_ledger(led):
    led["updated_at"] = now()
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")


def derivative_for(uuid):
    hits = sorted(glob.glob(str(LIB / "resources" / "derivatives" / uuid[0] / f"{uuid}_*")))
    # 105_c = תצוגת גלילה מלאה; 102 = מוקטן. מעדיפים את הגדול.
    hits.sort(key=lambda p: os.path.getsize(p), reverse=True)
    return hits[0] if hits else None


def original_for(directory, filename):
    p = LIB / "originals" / (directory or "") / (filename or "")
    return str(p) if p.exists() else None


# ---------------------------------------------------------------- scan
def cmd_scan(a):
    since = datetime.datetime.strptime(a.since, "%Y-%m-%d")
    cut = (since - EPOCH).total_seconds()
    db = LIB / "database" / "Photos.sqlite"
    if not db.exists():
        print(f"FAIL: לא נמצאה ספריית Photos ב-{db}", file=sys.stderr)
        sys.exit(2)
    con = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
    rows = con.execute(
        """SELECT ZUUID,ZDIRECTORY,ZFILENAME,ZDURATION,ZWIDTH,ZHEIGHT,ZDATECREATED,
                  ZHIDDEN,ZVISIBILITYSTATE,ZFAVORITE
           FROM ZASSET WHERE ZKIND=1 AND ZTRASHEDSTATE=0 AND ZDATECREATED>?""", (cut,)).fetchall()
    con.close()

    led = load_ledger()
    assets = led["assets"]
    stats = {"seen": len(rows), "already_known": 0, "new_candidate": 0}
    rej = {}

    for uuid, d, f, dur, w, h, dc, hid, vis, fav in rows:
        if uuid in assets:
            stats["already_known"] += 1
            continue
        dur = dur or 0.0
        w, h = w or 0, h or 0
        reason = None
        if hid:
            reason = "hidden"
        elif vis != 0:
            reason = "not_in_library"
        elif dur < MIN_DUR:
            reason = "too_short"
        elif dur > MAX_DUR:
            reason = "too_long"
        elif min(w, h) < MIN_SIDE:
            reason = "low_res"
        elif h <= w:
            reason = "landscape"          # בירול = אנכי. לרוחב = חוב, לא פסילה סופית.
        else:
            deriv = derivative_for(uuid)
            if not deriv:
                reason = "no_local_preview"

        rec = {
            "uuid": uuid, "file": f, "dur": round(dur, 2), "w": w, "h": h,
            "created": (EPOCH + datetime.timedelta(seconds=dc)).strftime("%Y-%m-%d") if dc else None,
            "favorite": bool(fav), "directory": d,
            "first_seen": now(),
        }
        if reason:
            rec.update(stage="rejected", stage_reason=reason)
            rej[reason] = rej.get(reason, 0) + 1
        else:
            rec.update(stage="candidate", deriv=derivative_for(uuid))
            stats["new_candidate"] += 1
        assets[uuid] = rec

    save_ledger(led)
    print(f"SCAN OK: {stats['seen']} סרטונים מאז {a.since} · "
          f"{stats['new_candidate']} מועמדים חדשים · {stats['already_known']} כבר בפנקס")
    for k, v in sorted(rej.items(), key=lambda x: -x[1]):
        print(f"  נפסל · {k}: {v}")


# ---------------------------------------------------------------- screen
def cmd_screen(a):
    if not REFERENCE.exists():
        print("FAIL: אין gallery_reference.json — להריץ gallery_calibrate.py --build קודם",
              file=sys.stderr)
        sys.exit(2)
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    env = ref["envelope"]
    led = load_ledger()
    assets = led["assets"]

    gates = {
        "sharp":    ("min", env["sharp"]["p05"]),
        "contrast": ("min", env["contrast"]["p05"]),
        "entropy":  ("min", env["entropy"]["p05"]),
        "bright":   ("range", (env["bright"]["p01"], 235.0)),
        "clip_lo":  ("max", max(0.10, env["clip_lo"]["p95"] * 3)),
        "clip_hi":  ("max", max(0.10, env["clip_hi"]["p95"] * 3)),
    }
    print("שערים נגזרים מ-%d בירולים מאושרים:" % ref["n_clips_measured"])
    for k, (kind, v) in gates.items():
        print(f"  {k:9s} {kind:6s} {v}")

    todo = [u for u, r in assets.items() if r.get("stage") == "candidate"]
    if a.limit:
        todo = todo[:a.limit]
    passed = 0
    rej = {}
    for i, u in enumerate(todo, 1):
        r = assets[u]
        dv = r.get("deriv")
        if not dv or not os.path.exists(dv):
            r.update(stage="rejected", stage_reason="preview_vanished")
            rej["preview_vanished"] = rej.get("preview_vanished", 0) + 1
            continue
        try:
            m = metrics_from_path(dv)
        except Exception as e:
            r.update(stage="rejected", stage_reason="preview_unreadable")
            rej["preview_unreadable"] = rej.get("preview_unreadable", 0) + 1
            continue
        r["metrics"] = m
        fail = None
        for key, (kind, v) in gates.items():
            x = m[key]
            if kind == "min" and x < v:
                fail = f"{key}_low"
            elif kind == "max" and x > v:
                fail = f"{key}_high"
            elif kind == "range" and not (v[0] <= x <= v[1]):
                fail = f"{key}_out_of_range"
            if fail:
                break
        if fail:
            r.update(stage="rejected", stage_reason=f"tech_{fail}")
            rej[f"tech_{fail}"] = rej.get(f"tech_{fail}", 0) + 1
        else:
            r.update(stage="screened", screened_at=now())
            passed += 1
        if i % 200 == 0:
            print(f"  ...{i}/{len(todo)}", flush=True)

    save_ledger(led)
    print(f"SCREEN OK: {passed}/{len(todo)} עברו את השער הטכני")
    for k, v in sorted(rej.items(), key=lambda x: -x[1]):
        print(f"  נפסל · {k}: {v}")


# ---------------------------------------------------------------- status
def cmd_status(a):
    led = load_ledger()
    st = {}
    for r in led["assets"].values():
        st[r.get("stage", "?")] = st.get(r.get("stage", "?"), 0) + 1
    print(f"פנקס: {len(led['assets'])} נכסים · עודכן {led.get('updated_at')}")
    for k, v in sorted(st.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    reasons = {}
    for r in led["assets"].values():
        if r.get("stage") == "rejected":
            reasons[r.get("stage_reason")] = reasons.get(r.get("stage_reason"), 0) + 1
    if reasons:
        print("סיבות פסילה:")
        for k, v in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"  {k}: {v}")


# ---------------------------------------------------------------- sheets
SHEET_DIR = HERE / "_gallery_work"
COLS, ROWS = 5, 4              # 20 מועמדים לגיליון
CELL_W, CELL_H = 300, 533      # 9:16


def _font(size):
    from PIL import ImageFont
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    from PIL import ImageFont as IF
    return IF.load_default()


def cmd_sheets(a):
    from PIL import Image, ImageDraw
    led = load_ledger()
    todo = sorted([u for u, r in led["assets"].items() if r.get("stage") == "screened"])
    if not todo:
        print("אין מועמדים בשלב screened — להריץ screen קודם")
        return
    SHEET_DIR.mkdir(exist_ok=True)
    for f in SHEET_DIR.glob("sheet_*.jpg"):
        f.unlink()
    per = COLS * ROWS
    manifest = {}
    n_sheets = (len(todo) + per - 1) // per
    fnt = _font(30)
    for si in range(n_sheets):
        chunk = todo[si * per:(si + 1) * per]
        sheet = Image.new("RGB", (COLS * CELL_W, ROWS * CELL_H), (18, 18, 18))
        dr = ImageDraw.Draw(sheet)
        for k, u in enumerate(chunk):
            r = led["assets"][u]
            x, y = (k % COLS) * CELL_W, (k // COLS) * CELL_H
            try:
                with Image.open(r["deriv"]) as im:
                    im = im.convert("RGB")
                    im.thumbnail((CELL_W - 8, CELL_H - 42), Image.LANCZOS)
                    sheet.paste(im, (x + (CELL_W - im.width) // 2, y + 36))
            except Exception:
                dr.rectangle([x + 4, y + 36, x + CELL_W - 4, y + CELL_H - 4], fill=(60, 20, 20))
            label = f"{si+1}-{k+1}"
            dr.rectangle([x, y, x + CELL_W, y + 34], fill=(135, 29, 31))
            dr.text((x + 8, y + 2), f"{label}   {r['dur']}s  {r['created']}", font=fnt, fill=(255, 255, 255))
            manifest[label] = u
        p = SHEET_DIR / f"sheet_{si+1:02d}.jpg"
        sheet.save(p, quality=88)
        print(f"  {p.name}  ({len(chunk)} מועמדים)")
    (SHEET_DIR / "sheet_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"SHEETS OK: {n_sheets} גיליונות · {len(todo)} מועמדים → {SHEET_DIR}")


CATEGORIES = ["אימון-כוח", "אימון-קרדיו", "אימון-גימנסטיקה", "אווירה-מועדון",
              "מאמן-והדרכה", "תחרויות-ואירועים", "ילדים", "שיקום-והתאוששות",
              "קהילה-וצוות", "משרד-וניהול", "כלליים"]


def normalize_category(c):
    """שער קטגוריה: רק ערכים מהרשימה נכנסים. שגיאת כתיב מתוקנת לפי הדמיון הקרוב."""
    c = (c or "").strip()
    if c in CATEGORIES:
        return c, None
    import difflib
    m = difflib.get_close_matches(c, CATEGORIES, n=1, cutoff=0.75)
    if m:
        return m[0], f"{c}→{m[0]}"
    return "כלליים", f"{c}→כלליים(לא מוכר)"


def cmd_verdict(a):
    """קולט פסקי-דין מודליים. פורמט: [{"label":"1-3","verdict":"accept","category":"אימון-כוח","desc":"סקוואט מוט"}]"""
    led = load_ledger()
    manifest = json.loads((SHEET_DIR / "sheet_manifest.json").read_text(encoding="utf-8"))
    data = json.loads(Path(a.file).read_text(encoding="utf-8"))
    ok = {"accept": 0, "reject": 0}
    unknown = []
    fixes = []
    for row in data:
        u = manifest.get(row["label"])
        if not u or u not in led["assets"]:
            unknown.append(row["label"])
            continue
        r = led["assets"][u]
        v = row["verdict"]
        if v == "accept":
            cat, fixed = normalize_category(row.get("category"))
            if fixed:
                fixes.append(fixed)
            r.update(stage="accepted", category=cat,
                     desc=row.get("desc", ""), judged_at=now(), judged_by="vision")
            ok["accept"] += 1
        else:
            r.update(stage="rejected", stage_reason="vision_" + row.get("reason", "not_relevant"),
                     judged_at=now(), judged_by="vision")
            ok["reject"] += 1
    save_ledger(led)
    print(f"VERDICT OK: {ok['accept']} אושרו · {ok['reject']} נפסלו"
          + (f" · {len(unknown)} תוויות לא מוכרות: {unknown[:8]}" if unknown else ""))
    if fixes:
        import collections as _c
        print("  קטגוריות תוקנו:", dict(_c.Counter(fixes)))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan");   s.add_argument("--since", default="2026-02-21"); s.set_defaults(fn=cmd_scan)
    s = sub.add_parser("screen"); s.add_argument("--limit", type=int, default=0);  s.set_defaults(fn=cmd_screen)
    s = sub.add_parser("sheets"); s.set_defaults(fn=cmd_sheets)
    s = sub.add_parser("verdict"); s.add_argument("--file", required=True); s.set_defaults(fn=cmd_verdict)
    s = sub.add_parser("status"); s.set_defaults(fn=cmd_status)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
