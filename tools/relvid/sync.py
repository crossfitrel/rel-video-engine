#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync — שכבת הסנכרון בין שני מסלולי העריכה (v7.7, בקשת הראל 25.7).
==================================================================
הבעיה שנפתרת כאן (מדווח: "הגרסה FINAL טובה, אבל כשאני רוצה לערוך קטע ידנית
האפליקציה מראה לי את הגרסה הקודמת ולא את ה-FINAL"):

ל-edl.json יש שתי שכבות שאף אחת לא סנכרנה את השנייה:
  * `review.cuts`    — מה שהאפליקציה מציירת על הציר (מסלול עריכה של הראל).
  * `keep_segments`  — מה ש-edl_cut חותך בפועל → EXPORT → FINAL (מסלול הגימור).
האפליקציה כותבת את שתיהן יחד (save → derive_keep), אבל עריכה בצ'אט נגעה
בפועל ב-`keep_segments` בלבד. התוצאה: FINAL נכון, ציר האפליקציה ישן.

בנוסף יש פער מבני קטן וקבוע: `tighten_finish` מקצץ עוד שקט *אחרי* החיתוך
(tight_keeps.json, בציר EXPORT) ואף פעם לא חזר ל-edl.json — לכן גם בפרויקט
"מסונכרן" משך הציר באפליקציה גדול ממשך ה-FINAL בפועל.

מה המודול הזה עושה:
  1. `reconcile_edl`  — ריפוי-עצמי: אם keep_segments ≠ derive_keep(review),
     בונה מחדש את review.cuts מ-keep_segments (הגימור מנצח — זה מה שבאמת נחתך),
     שומר את hook_move/speed, ומאמת round-trip לפני כתיבה. יוצר revision.
  2. `write_provenance` — בסוף גימור מוצלח: FINAL_PROVENANCE.json = בדיוק ממה
     ה-FINAL הזה נבנה (revision, edl_hash, keep_segments, הידוק, speed, stat).
  3. `sync_status`   — מצב הסנכרון להצגה: in_sync / edl_ahead / final_ahead /
     drift (עם המשפט בעברית שהאפליקציה מציגה).
"""
from pathlib import Path

from . import (atomic_write_json, now_ts, read_json, sha256_file, sha256_json)
from .edl_utils import MIN_KEEP_GAP, derive_keep

PROVENANCE = "FINAL_PROVENANCE.json"
EPS = 0.03            # סובלנות השוואת גבולות (מתחת לחצי-פריים ב-30fps)


# ---------------------------------------------------------------- עזרי EDL
def keeps_dur(keeps):
    return round(sum(float(k["end"]) - float(k["start"]) for k in (keeps or [])), 2)


def keeps_equal(a, b, eps=EPS):
    a, b = a or [], b or []
    if len(a) != len(b):
        return False
    sa = sorted(a, key=lambda k: float(k["start"]))
    sb = sorted(b, key=lambda k: float(k["start"]))
    return all(abs(float(x["start"]) - float(y["start"])) <= eps
               and abs(float(x["end"]) - float(y["end"])) <= eps
               for x, y in zip(sa, sb))


def cuts_from_keeps(total, keeps, source="claude", reason="עריכה מחוץ לאפליקציה"):
    """הפוך ל-derive_keep: keep_segments → רשימת cuts פעילים (המשלים ב-[0,total]).

    ההשוואה נעשית על keeps ממוינים לפי start — hook_move (אם קיים) מוחל שוב
    בהמשך ע"י derive_keep, ולכן סדר ההצגה נשמר.
    """
    total = float(total)
    ks = sorted([{"start": max(0.0, float(k["start"])), "end": min(total, float(k["end"]))}
                 for k in (keeps or [])], key=lambda k: k["start"])
    cuts, pos = [], 0.0
    for k in ks:
        if k["start"] > pos + MIN_KEEP_GAP:
            cuts.append({"start": round(pos, 3), "end": round(k["start"], 3),
                         "active": True, "source": source, "reason": reason})
        pos = max(pos, k["end"])
    if pos < total - MIN_KEEP_GAP:
        cuts.append({"start": round(pos, 3), "end": round(total, 3),
                     "active": True, "source": source, "reason": reason})
    return cuts


def edl_drift(edl):
    """האם הציר שהאפליקציה מציגה (review.cuts) תואם למה שנחתך (keep_segments)?"""
    total = float(edl.get("total_dur") or 0)
    rv = edl.get("review") or {}
    disk = edl.get("keep_segments") or []
    from_review = derive_keep(total, rv.get("cuts") or [], rv.get("hook_move"))
    same = keeps_equal(disk, from_review)
    return {"consistent": same,
            "kept_dur_disk": keeps_dur(disk),
            "kept_dur_from_review": keeps_dur(from_review),
            "segments_disk": len(disk),
            "segments_from_review": len(from_review),
            "delta": round(keeps_dur(from_review) - keeps_dur(disk), 2)}


def reconcile_edl(workdir, actor="system", summary=None, dry_run=False):
    """מיישר את review.cuts לפי keep_segments (מה שבאמת נחתך). לא-הרסני.

    מחזיר {"ok", "changed", "reason", "drift", "revision_id"}.
    לא כותב אם: אין דריפט, או שה-round-trip לא מאמת (עדיף לדווח מאשר לשבור ציר).
    """
    from . import revisions as rev_mod        # import מקומי — מניעת מעגליות

    w = Path(workdir)
    p = w / "edl.json"
    edl = read_json(p)
    if edl is None:
        return {"ok": False, "changed": False, "reason": "אין edl.json"}
    drift = edl_drift(edl)
    if drift["consistent"]:
        return {"ok": True, "changed": False, "reason": "מסונכרן", "drift": drift}

    total = float(edl.get("total_dur") or 0)
    rv = dict(edl.get("review") or {})
    keeps = edl.get("keep_segments") or []
    if not keeps or not total:
        return {"ok": False, "changed": False,
                "reason": "אין keep_segments/total_dur לשחזור הציר", "drift": drift}

    new_cuts = cuts_from_keeps(total, keeps)
    # אימות round-trip לפני כתיבה — derive_keep על ה-cuts החדשים חייב להחזיר
    # בדיוק את keep_segments שעל הדיסק, אחרת לא נוגעים.
    back = derive_keep(total, new_cuts, rv.get("hook_move"))
    if not keeps_equal(back, keeps):
        return {"ok": False, "changed": False,
                "reason": ("round-trip נכשל — הציר לא שוחזר מ-keep_segments "
                           f"({keeps_dur(back)}ש מול {keeps_dur(keeps)}ש). לא נכתב."),
                "drift": drift}
    if dry_run:
        return {"ok": True, "changed": False, "reason": "dry-run", "drift": drift,
                "would_write_cuts": len(new_cuts)}

    rev_mod.ensure_baseline(w)
    rv["cuts"] = new_cuts
    rv.setdefault("speed", 1.0)
    rv["synced_from"] = "keep_segments"
    rv["synced_at"] = now_ts()
    edl["review"] = rv
    edl["kept_dur"] = keeps_dur(keeps)
    try:
        edl["kept_dur_at_speed"] = round(edl["kept_dur"] / float(rv.get("speed") or 1.0), 2)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    atomic_write_json(p, edl)
    rid = rev_mod.create_revision(
        w, actor=actor,
        summary=summary or (f"סנכרון ציר לאפליקציה מ-keep_segments "
                            f"({drift['kept_dur_from_review']}ש → {drift['kept_dur_disk']}ש)"),
        actions=[{"type": "sync_review_from_keeps",
                  "cuts": len(new_cuts), "delta": drift["delta"]}])
    return {"ok": True, "changed": True, "reason": "review.cuts נבנה מחדש מ-keep_segments",
            "drift": drift, "revision_id": rid, "cuts": len(new_cuts)}


# --------------------------------------------------- מיפוי הידוק לציר המקור
def tight_keeps_in_source(edl, tight_keeps):
    """tight_keeps (ציר EXPORT, אחרי החיתוך) → טווחים בציר המקור.

    edl_cut משרשר את keep_segments לציר רציף; tighten מקצץ בתוכו. הפונקציה
    ממפה כל keep מהודק חזרה לציר המקורי, כדי שהאפליקציה תוכל לצייר את מה
    שההידוק *הוריד* (השארית = "הידוק גימור").
    """
    keeps = edl.get("keep_segments") or []
    if not keeps or not tight_keeps:
        return []
    # ציר EXPORT: לכל keep מקור טווח [acc, acc+len)
    spans, acc = [], 0.0
    for k in keeps:
        ln = float(k["end"]) - float(k["start"])
        spans.append((acc, acc + ln, float(k["start"])))
        acc += ln
    out = []
    for t in tight_keeps:
        ts, te = float(t["start"]), float(t["end"])
        for a, b, src0 in spans:
            lo, hi = max(ts, a), min(te, b)
            if hi - lo > MIN_KEEP_GAP:
                out.append({"start": round(src0 + (lo - a), 3),
                            "end": round(src0 + (hi - a), 3)})
    return sorted(out, key=lambda k: k["start"])


def tighten_trims_in_source(edl, tight_keeps):
    """מה שההידוק הוריד, בציר המקור (להצגה בלבד — לא נכתב ל-review.cuts)."""
    kept_after = tight_keeps_in_source(edl, tight_keeps)
    if not kept_after:
        return []
    trims = []
    for k in (edl.get("keep_segments") or []):
        s, e = float(k["start"]), float(k["end"])
        pos = s
        for t in kept_after:
            if t["end"] <= s or t["start"] >= e:
                continue
            if t["start"] > pos + MIN_KEEP_GAP:
                trims.append({"start": round(pos, 3), "end": round(t["start"], 3),
                              "source": "tighten"})
            pos = max(pos, t["end"])
        if pos < e - MIN_KEEP_GAP:
            trims.append({"start": round(pos, 3), "end": round(e, 3), "source": "tighten"})
    return trims


# ------------------------------------------------------------- provenance
def _probe_dur(path):
    """משך מדיה (ffprobe). None אם אין קובץ/ffprobe."""
    import subprocess
    p = Path(path)
    if not p.exists():
        return None
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(p)], capture_output=True, text=True, timeout=30)
        return round(float(r.stdout.strip()), 2)
    except Exception:
        return None


def _final_stat(w):
    f = Path(w) / "FINAL.mp4"
    if not f.exists():
        return None
    st = f.stat()
    return {"file": "FINAL.mp4", "size": st.st_size, "mtime": round(st.st_mtime, 3),
            "checksum": sha256_file(f)}


def write_provenance(workdir, run_id=None, extra=None):
    """נכתב בסוף גימור מוצלח: בדיוק ממה ה-FINAL הזה נבנה."""
    from . import revisions as rev_mod

    w = Path(workdir)
    edl = read_json(w / "edl.json", {}) or {}
    tight = read_json(w / "tight_keeps.json", []) or []
    rec = {
        "built_at": now_ts(),
        "run_id": run_id,
        "revision_id": rev_mod.head(w),
        "edl_hash": sha256_json(edl),
        "keep_segments": edl.get("keep_segments") or [],
        "kept_dur": edl.get("kept_dur"),
        "speed": (edl.get("review") or {}).get("speed", 1.0),
        "tight_keeps": tight,
        "tighten_trims_source": tighten_trims_in_source(edl, tight),
        "final": _final_stat(w),
        "input_hash": sha256_file(w / "INPUT.mp4"),
    }
    if extra:
        rec.update(extra)
    atomic_write_json(w / PROVENANCE, rec)
    return rec


def provenance(workdir):
    return read_json(Path(workdir) / PROVENANCE)


def sync_badge(workdir):
    """גרסה קלה ל-badge ברשימת הפרויקטים — בלי hashing של מדיה.
    מחזירה state בלבד: drift / edl_ahead / in_sync / no_final / no_provenance."""
    w = Path(workdir)
    edl = read_json(w / "edl.json", {}) or {}
    if not edl:
        return "no_final"
    if not edl_drift(edl)["consistent"]:
        return "drift"
    if not (w / "FINAL.mp4").exists():
        return "no_final"
    prov = provenance(w)
    if not prov:
        return "no_provenance"
    return "in_sync" if prov.get("edl_hash") == sha256_json(edl) else "edl_ahead"


def sync_status(workdir):
    """מצב הסנכרון בין הציר שבאפליקציה לבין ה-FINAL שעל הדיסק.

    state:
      no_final        — עוד לא נבנה FINAL.
      no_provenance   — יש FINAL אבל נבנה לפני v7.7 (אין רשומת מקור).
      in_sync         — הציר באפליקציה = הציר שממנו נבנה ה-FINAL.
      edl_ahead       — הציר נערך אחרי הגימור → ה-FINAL ישן, צריך גימור מחדש.
      final_ahead     — ה-FINAL נבנה מציר אחר מזה שמוצג → צריך סנכרון ציר.
      drift           — review.cuts ≠ keep_segments (דריפט פנימי, ניתן לריפוי).
    """
    w = Path(workdir)
    edl = read_json(w / "edl.json", {}) or {}
    drift = edl_drift(edl) if edl else {"consistent": True}
    cur_hash = sha256_json(edl) if edl else None
    prov = provenance(w)
    final = w / "FINAL.mp4"
    tight = read_json(w / "tight_keeps.json", []) or []
    trims = tighten_trims_in_source(edl, tight)
    trimmed = keeps_dur(trims)
    base = {"edl_hash": cur_hash, "drift": drift,
            "tighten_trimmed": trimmed,
            "tighten_trims": trims,
            "kept_dur": edl.get("kept_dur"),
            "final_expected_dur": (round((keeps_dur(edl.get("keep_segments")) - trimmed)
                                         / float((edl.get("review") or {}).get("speed") or 1.0), 2)
                                   if edl.get("keep_segments") else None)}

    if not drift["consistent"]:
        return dict(base, state="drift", ok=False,
                    message=(f"הציר שמוצג כאן אינו הציר שנחתך בפועל "
                             f"({drift['kept_dur_from_review']}ש מול {drift['kept_dur_disk']}ש) — "
                             f"עריכה שנעשתה מחוץ לאפליקציה. לחץ 'סנכרן ציר' כדי ליישר."))
    if not final.exists():
        return dict(base, state="no_final", ok=True, message="עוד אין FINAL.")
    if not prov:
        # אין רשומת מקור (FINAL מלפני v7.7). בדיקת שפיות זולה: משך ה-FINAL בפועל מול
        # התחזית מהציר (keeps פחות הידוק, חלקי speed). פער גדול = ה-FINAL לא נבנה מהציר הזה.
        act = _probe_dur(final)
        exp = base["final_expected_dur"]
        if act is not None and exp is not None and abs(act - exp) > 0.75:
            return dict(base, state="final_mismatch", ok=False, final_dur=act,
                        message=(f"ה-FINAL על הדיסק ({act}ש) לא תואם לציר שמוצג כאן "
                                 f"(צפוי ~{exp}ש) — כלומר הוא נבנה מגרסה אחרת. "
                                 f"הרץ גימור מחדש כדי שה-FINAL יתאים לציר."))
        return dict(base, state="no_provenance", ok=True, final_dur=act,
                    message="ה-FINAL נבנה לפני מעקב-המקור — הגימור הבא יסמן אותו.")
    fstat = _final_stat(w)
    final_changed = bool(prov.get("final")) and (
        fstat["size"] != prov["final"].get("size")
        or abs(fstat["mtime"] - float(prov["final"].get("mtime") or 0)) > 1.0)
    if final_changed:
        return dict(base, state="final_ahead", ok=False, provenance=prov,
                    message="ה-FINAL על הדיסק השתנה מחוץ לגימור — רשומת המקור לא תקפה.")
    if prov.get("edl_hash") != cur_hash:
        return dict(base, state="edl_ahead", ok=False, provenance=prov,
                    message=("הציר נערך אחרי בניית ה-FINAL — מה שמוצג כאן חדש מה-FINAL. "
                             "הרץ גימור מחדש כדי שה-FINAL יתאים."))
    return dict(base, state="in_sync", ok=True, provenance=prov,
                message=(f"מסונכרן: ה-FINAL נבנה בדיוק מהציר הזה"
                         + (f" (הידוק הגימור הוריד עוד {trimmed}ש)." if trimmed else ".")))
