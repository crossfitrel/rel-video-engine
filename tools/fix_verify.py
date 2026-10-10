#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_verify — "קלאוד בודק לפני הראל": אימות פר-הערה של סבב תיקונים, עם ראיות.
============================================================================
הראל 18.8.26: *"מה שלוקח לי כרגע הכי הרבה זמן זה לעבור כל סרטון כל פעם שיש
תיקונים ולוודא שהכל פיקס. יש לך דרך לייעל את זה ולקחת בזה חלק?"*

v9.15 נתן להראל את "מה תוקן בגרסה הזו" — רשימת התיקונים של כל גרסה עם סבב
שמנגן רק את הנקודות. אבל את *האימות* עדיין עשה הראל: כל נקודה, כל סבב.
כאן האימות עובר לקלאוד, והראל נשאר עם שיפוט הטעם בלבד:

1. **מדידה (הקובץ הזה).** לכל תיקון בגרסה — בדיקת-מכונה לפי קטגוריה
   (מילה מתוקנת בכתוביות · גבול חיתוך שאכן זז · רמת מוזיקה בחלון · בירול
   שאכן נכנס/יצא) + גיליון-מגע של הפריימים סביב הנקודה, מהגרסה עצמה.
2. **עין (קלאוד, חוק הראייה).** קלאוד קורא את הגיליונות ב-Read ופוסק פר-פריט
   דרך `review_cli.py fix-verdict` — verified / not_fixed / needs_eye.
   פסיקת not_fixed מחזירה את ההערה לתור **לפני** שהראל בכלל פתח את הסרטון.
3. **סבב ממוקד (האפליקציה).** review_plan_focus מנגן להראל רק את מה שקלאוד
   לא אימת. תיקון שאומת מוצג עם 🤖 והראל חופשי לדגום — לא חייב.

עקרונות:
- **מדידה אינה פסיקה.** בדיקת-המכונה היא ראיה; הפסיקה היא של קלאוד אחרי
  שקרא את הגיליונות (חוק הראייה, v9.14). אין שער חוסם כאן — הכל מדווח.
- **ציר לא ודאי ⇒ inconclusive, לא ניחוש.** חיפוש מילים רץ רק כשהגרסה היא
  ה-FINAL החי (שם words_final.json באמת מתאר אותה); אחרת מדווח שאי אפשר.
- **הראיות נשמרות.** FIX_VERIFY.json + fix_verify/<artifact>/sheet_*.jpg
  נשארים בפרויקט, ומוגשים לאפליקציה.

שימוש:
  python3 tools/fix_verify.py --workdir W [--artifact ID] [--reel] [--json]
פלט: {W}/FIX_VERIFY.json · {W}/fix_verify/{artifact_id}/sheet_<item>.jpg
      [--reel ⇒ {W}/fix_verify/{artifact_id}/CHECK_REEL.mp4]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from relvid import read_json, now_ts                     # noqa: E402
from relvid import artifacts as art_mod                  # noqa: E402
from relvid import changelog as cl_mod                   # noqa: E402

PAD = 2.5                 # כמו review_plan — אותו חלון שהראל היה בודק
SHEET_COLS, SHEET_ROWS = 4, 2
EDL_NEAR_TOL = 3.0        # שינוי גבול בטווח ±3ש מהנקודה = "השינוי המבוקש"
WORD_WIN = 8.0            # חלון חיפוש מילים — רחב בכוונה (אי-ודאות צירים)


def sh(cmd, timeout=180):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired as e:
        err = e.stderr
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        return 124, f"timeout: {err or ''}"
    except FileNotFoundError as e:
        return 127, str(e)


# ═══════════════════════════════════════════ בדיקות-מכונה טהורות (נבדקות)
def parse_expected_tokens(text):
    """מה ההערה ביקשה לראות בכתוביות — מחולץ מדפוסי התיקון המוכרים.

    אותם דפוסים כמו note_corrections: 'מילה*' · '"X" ולא "Y"' · 'X במקום Y'.
    מחזיר רשימת מילים שצריכות **להופיע** (המילה הנכונה, לא השגויה).
    """
    if not text:
        return []
    toks = []
    toks += [m.group(1) for m in re.finditer(r"([\w\u0590-\u05FF]{2,})\*", text)]
    for m in re.finditer(r"[\"“„']([^\"”“„']{2,40})[\"”“„']\s*(?:ולא|במקום)", text):
        toks += m.group(1).split()
    for m in re.finditer(r"([\w\u0590-\u05FF]{2,})\s+(?:ולא|במקום)\s+[\w\u0590-\u05FF]{2,}",
                         text):
        toks.append(m.group(1))
    seen, out = set(), []
    for t in toks:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def words_in_window(words, tokens, t_center, win=WORD_WIN):
    """אילו מהמילים המצופות נמצאות בפועל בחלון הזמן. ראיה, לא פסיקה."""
    if not tokens or t_center is None:
        return {"searched": bool(tokens), "found": [], "missing": list(tokens or [])}
    lo, hi = float(t_center) - win, float(t_center) + win
    bag = [w.get("word", "").strip() for w in words
           if lo <= float(w.get("start", 0)) <= hi]
    joined = " ".join(bag)
    found = [t for t in tokens if t in joined]
    return {"searched": True, "found": found,
            "missing": [t for t in tokens if t not in found],
            "window_text": joined[:300]}


def _bounds(keeps):
    out = []
    for k in keeps or []:
        out += [round(float(k["start"]), 2), round(float(k["end"]), 2)]
    return out


def boundaries_changed_near(prev_keeps, cur_keeps, src_t, tol=EDL_NEAR_TOL):
    """האם בין שתי התוכניות השתנה גבול חיתוך ליד הנקודה (בציר המקור)."""
    if src_t is None:
        return {"comparable": False, "changed_near": False}
    pb, cb = set(_bounds(prev_keeps)), set(_bounds(cur_keeps))
    delta = pb.symmetric_difference(cb)
    near = [b for b in sorted(delta) if abs(b - float(src_t)) <= tol]
    return {"comparable": True, "changed_near": bool(near),
            "changed_bounds_near": near[:6], "n_changed_total": len(delta)}


# ═══════════════════════════════════════════════════ מדידות על המדיה
def extract_sheet(video, s, e, out_jpg):
    """גיליון-מגע אחד לפריט: 8 פריימים על פני חלון הבדיקה. הקריאה שלו ב-Read
    היא הצפייה של קלאוד (חוק הראייה) — הגיליון הוא הראיה, לא הדוח."""
    n = SHEET_COLS * SHEET_ROWS
    dur = max(0.4, e - s)
    rc, log = sh(["ffmpeg", "-y", "-ss", f"{max(0.0, s):.2f}", "-t", f"{dur:.2f}",
                  "-i", str(video),
                  "-vf", f"fps={n / dur:.4f},scale=300:-2,tile={SHEET_COLS}x{SHEET_ROWS}",
                  "-frames:v", "1", "-q:v", "4", str(out_jpg)])
    return rc == 0 and Path(out_jpg).is_file()


def measure_loudness(video, s, e):
    rc, log = sh(["ffmpeg", "-nostats", "-ss", f"{max(0.0, s):.2f}",
                  "-t", f"{max(0.4, e - s):.2f}", "-i", str(video),
                  "-filter_complex", "ebur128", "-f", "null", "-"])
    if rc != 0:
        return None
    m = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", log)
    return float(m[-1]) if m else None


def _badge_png(label, path):
    """באדג' N/M כתמונה (PIL) — ffmpeg של המק נבנה בלי drawtext, ולכן
    הבאדג' נצרב ב-overlay, אותו מסלול שכבר מוכח בצנרת הבירולים."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Helvetica.ttc", 56)
    except Exception:
        font = ImageFont.load_default()
    img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = d.textbbox((0, 0), label, font=font)
    w, h = box[2] - box[0] + 44, box[3] - box[1] + 32
    img = Image.new("RGBA", (w, h), (0, 0, 0, 150))
    d = ImageDraw.Draw(img)
    d.text((22 - box[0], 16 - box[1]), label, font=font, fill=(255, 255, 255, 255))
    img.save(path)
    return True


def build_reel(video, spots, out_mp4, workdir):
    """CHECK_REEL.mp4 — רק קטעי הבדיקה, עם באדג' N/M. לצפייה מהטלפון/Monday."""
    tmp = Path(workdir) / "fix_verify" / "_reel_parts"
    tmp.mkdir(parents=True, exist_ok=True)
    parts = []
    n = len(spots)
    for i, sp in enumerate(spots):
        p = tmp / f"part_{i:02d}.mp4"
        badge = tmp / f"badge_{i:02d}.png"
        has_badge = _badge_png(f"{i + 1}/{n}", badge)
        cmd = ["ffmpeg", "-y", "-ss", f"{sp['start']:.2f}",
               "-t", f"{max(0.4, sp['end'] - sp['start']):.2f}",
               "-i", str(video)]
        if has_badge:
            cmd += ["-i", str(badge),
                    "-filter_complex", "[0:v][1:v]overlay=40:90"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", str(p)]
        rc, log = sh(cmd, timeout=300)
        if rc == 0 and p.is_file():
            parts.append(p)
        badge.unlink(missing_ok=True)
    if not parts:
        return False
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    rc, log = sh(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                  "-c", "copy", str(out_mp4)], timeout=300)
    for p in parts:
        p.unlink(missing_ok=True)
    lst.unlink(missing_ok=True)
    try:
        tmp.rmdir()
    except OSError:
        pass
    return rc == 0 and Path(out_mp4).is_file()


# ═══════════════════════════════════════════════════════ הרצה על גרסה
def machine_checks(workdir, item, art, live_final_aid, prev_tl, cur_tl):
    """בדיקת-המכונה של פריט אחד. מחזירה dict ראיות — לא פסיקה."""
    w = Path(workdir)
    cat = item.get("category") or ""
    kind = item.get("kind")
    out = {"status": "inconclusive", "detail": ""}

    if kind == "mechanical":
        out.update(status="measured",
                   detail="עובדה שנמדדה מהרשומות בזמן הבנייה — אין מה לאמת מעבר")
        return out

    if cat in ("transcript", "captions"):
        toks = parse_expected_tokens(item.get("title") or "")
        if not toks:
            out["detail"] = "לא זוהה דפוס תיקון-כתיב בהערה — נשאר לעין"
            return out
        if art["artifact_id"] != live_final_aid:
            out["detail"] = ("words_final.json מתאר את ה-FINAL החי, לא את הגרסה "
                             "הזו — אין ציר ודאי לחיפוש")
            return out
        words = read_json(w / "words_final.json", []) or []
        if isinstance(words, dict):
            words = words.get("words") or []
        res = words_in_window(words, toks, item.get("t"))
        out["words"] = res
        if res["found"] and not res["missing"]:
            out.update(status="found",
                       detail=f"המילים המתוקנות נמצאו בחלון: {', '.join(res['found'])}")
        elif res["found"]:
            out.update(status="partial",
                       detail=f"נמצאו {res['found']}, חסרות {res['missing']}")
        else:
            out.update(status="not_found",
                       detail=f"המילים {toks} לא נמצאו בחלון — לבדוק בעין")
        return out

    if cat in ("edit", "pacing", "hook"):
        prev_keeps = (prev_tl or {}).get("keeps")
        cur_keeps = (cur_tl or {}).get("keeps")
        src_t = item.get("src_t", item.get("origin_time"))
        if not prev_keeps or not cur_keeps:
            out["detail"] = "אין snapshot ציר לאחת הגרסאות — אי אפשר להשוות EDL"
            return out
        res = boundaries_changed_near(prev_keeps, cur_keeps, src_t)
        out["edl"] = res
        if res["changed_near"]:
            out.update(status="edl_changed",
                       detail=f"גבול חיתוך השתנה ליד הנקודה: {res['changed_bounds_near']}")
        elif res["n_changed_total"]:
            out.update(status="edl_changed_elsewhere",
                       detail=f"ה-EDL השתנה ({res['n_changed_total']} גבולות) אבל לא "
                              f"ליד הנקודה — לבדוק בעין")
        else:
            out.update(status="not_found",
                       detail="ה-EDL לא השתנה בין הגרסאות — התיקון כנראה לא נכנס")
        return out

    if cat == "audio":
        if item.get("t") is not None and Path(art["path"]).is_file():
            s = max(0.0, float(item["t"]) - PAD)
            e = float(item.get("t_end") or item["t"]) + PAD
            lufs = measure_loudness(art["path"], s, e)
            if lufs is not None:
                out.update(status="measured", lufs_window=lufs,
                           detail=f"עוצמה בחלון: {lufs:.1f} LUFS — להשוות לתלונה באוזן")
                return out
        out["detail"] = "לא נמדדה עוצמה — לבדוק באוזן"
        return out

    if cat == "broll":
        plan = read_json(w / "broll_plan.json", {}) or {}
        clips = [p for p in (plan.get("plan") or [])
                 if p.get("insert_at") is not None]
        t = item.get("t")
        if t is None:
            out["detail"] = "אין טיימקוד — אי אפשר לבדוק חפיפת בירול"
            return out
        lo, hi = float(t) - PAD, float(item.get("t_end") or t) + PAD
        over = [{"label": p.get("label") or p.get("id"),
                 "at": [p["insert_at"], p["insert_end"]]}
                for p in clips
                if float(p["insert_end"]) > lo and float(p["insert_at"]) < hi]
        out.update(status="measured", overlapping_broll=over,
                   detail=(f"{len(over)} בירולים חופפים לחלון" if over
                           else "אין בירול בחלון — אם ההערה ביקשה בירול, הוא לא שם"))
        return out

    out["detail"] = "אין בדיקת-מכונה לקטגוריה — הפסיקה בעין בלבד"
    return out


def run(workdir, artifact_id=None, reel=False):
    w = Path(workdir).expanduser()
    arts = art_mod.list_artifacts(w)
    if not arts:
        return {"ok": False, "error": "אין גרסאות וידאו בפרויקט"}
    art = None
    if artifact_id:
        art = art_mod.get_artifact(w, artifact_id)
        if not art:
            return {"ok": False, "error": f"גרסה לא נמצאה: {artifact_id}"}
    else:
        art = arts[-1]
    aid = art["artifact_id"]

    integ = art_mod.verify(w, aid)
    doc = cl_mod.build(w, artifact_id=aid)
    if not doc["versions"]:
        return {"ok": False, "error": "אין יומן שינויים לגרסה"}
    ver = doc["versions"][0]

    live_aid = None
    try:
        live_aid = art_mod.artifact_of_live_final(w)
    except Exception:
        pass

    cur_tl = cl_mod.timeline(w, art)
    # הגרסה הקודמת לפי הסדר:
    idx = next((i for i, a in enumerate(arts) if a["artifact_id"] == aid), 0)
    prev = arts[idx - 1] if idx else None
    prev_tl = cl_mod.timeline(w, prev) if prev else None

    outdir = w / "fix_verify" / aid
    outdir.mkdir(parents=True, exist_ok=True)
    video = Path(art["path"])
    video_ok = video.is_file() and integ.get("ok", False)

    items_out = []
    for it in ver.get("items", []):
        rec = {"item_id": it["item_id"], "kind": it["kind"],
               "category": it.get("category"), "title": it.get("title"),
               "t": it.get("t"), "t_end": it.get("t_end"),
               "t_status": it.get("t_status")}
        # ראיה ויזואלית — גיליון מגע מהגרסה עצמה
        if it.get("t") is not None and video_ok:
            s = max(0.0, float(it["t"]) - PAD)
            e = float(it.get("t_end") or it["t"]) + PAD
            sheet = outdir / f"sheet_{it['item_id']}.jpg"
            if extract_sheet(video, s, e, sheet):
                rec["sheet"] = sheet.name
        # ההערה שנכתבה על הגרסה הקודמת — src_t עוזר להשוואת EDL
        rec["src_t"] = it.get("src_t")
        rec["machine"] = machine_checks(w, dict(it, src_t=it.get("src_t")),
                                        art, live_aid, prev_tl, cur_tl)
        rec["eye_required"] = it["kind"] == "comment"
        items_out.append(rec)

    plan = cl_mod.review_plan(ver)
    reel_name = None
    if reel and video_ok and plan["spots"]:
        rp = outdir / "CHECK_REEL.mp4"
        if build_reel(video, plan["spots"], rp, w):
            reel_name = rp.name

    n_cmt = sum(1 for x in items_out if x["kind"] == "comment")
    n_flag = sum(1 for x in items_out
                 if x["machine"]["status"] in ("not_found",))
    result = {
        "ok": True, "artifact_id": aid, "version": art.get("version"),
        "generated_at": now_ts(),
        "video": str(video), "video_verified": video_ok,
        "video_checksum": art.get("checksum"),
        "items": items_out,
        "summary": {"total": len(items_out), "comments": n_cmt,
                    "machine_flags": n_flag,
                    "sheets": sum(1 for x in items_out if x.get("sheet"))},
        "reel": reel_name,
        "next": ("קלאוד: Read על כל sheet_*.jpg ואז fix-verdict פר-פריט. "
                 "אין דיווח 'תוקן ואומת' בלי קריאת הגיליונות (חוק הראייה)"),
    }
    (w / "FIX_VERIFY.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--artifact", default=None)
    ap.add_argument("--reel", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    doc = run(a.workdir, artifact_id=a.artifact, reel=a.reel)
    if a.json or not doc.get("ok"):
        print(json.dumps(doc, ensure_ascii=False, indent=1))
        return 0 if doc.get("ok") else 1
    s = doc["summary"]
    print(f"🤖 FIX_VERIFY — גרסה {doc['version']} · {s['total']} פריטים · "
          f"{s['sheets']} גיליונות · {s['machine_flags']} דגלי מכונה"
          + (f" · reel: {doc['reel']}" if doc.get("reel") else ""))
    for it in doc["items"]:
        m = it["machine"]
        print(f"  [{m['status']}] {it['item_id']}: {m['detail'][:110]}")
    print(f"→ {doc['next']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
