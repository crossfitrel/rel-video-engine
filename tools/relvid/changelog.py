#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
changelog — "מה תוקן בגרסה הזו": יומן שינויים פר-גרסת וידאו, עם טיימקוד ממופה.
==============================================================================
הראל 17.8.26: *"תכניס באפליקציית רוויו הערות לכל גרסה שנערכת, שאוכל לבדוק
בדיוק את ההערות שתוקנו במקום לעבור על הסרטון המלא כל פעם שיש תיקונים."*

השורש: `comments.json` יודע **מה** ביקשת ו-`artifacts/` יודע **מה נוצר** —
אבל אף אחד לא ידע *איזה תיקון נכנס לאיזו גרסה*. לכן כל סבב תיקונים חייב
צפייה מלאה מחדש: 60 שניות כפול מספר הסבבים, כדי לאמת 4 נקודות של 3 שניות.

כאן נסגר הפער בשלושה חלקים:

1. **חותמת בזמן היצירה (מדויקת).** `artifacts.create_artifact` קורא ל-
   `stamp_fixes()` ושומר ברשומת הגרסה את ההערות שנפתרו מאז הגרסה הקודמת.
   מכאן והלאה השיוך הוא עובדה שנרשמה, לא ניחוש בדיעבד.
2. **הסקה לגרסאות ישנות (מסומנת ככזו).** לגרסאות שנוצרו לפני v9.15 —
   ובמיוחד ל-71 הגרסאות שנוצרו בבת-אחת במיגרציה של v9.4 ולכן נושאות
   `created_at` זהה — השיוך נגזר משני אותות בלתי-תלויים: סדר ה-revisions
   (`resolved_revision_id`) וחותמות הזמן. **שני האותות מסכימים ⇒ "ודאי";
   אחד בלבד ⇒ "משוער"** — והתווית מוצגת להראל. אף פעם לא מנחשים בשקט.
3. **מיפוי טיימקוד בין צירים.** הערה נכתבה על 0:14 של גרסה 4; בגרסה 5
   נחתכו 3 שניות לפניה, והנקודה הזו כבר לא ב-0:14. המיפוי עובר דרך ציר
   המקור: זמן-פלט → (keep_segments + speed של הגרסה הישנה) → זמן ב-INPUT →
   (keep_segments + speed של הגרסה החדשה) → זמן-פלט חדש. נקודה שנחתכה
   בגרסה החדשה מסומנת `cut_out` ומוצמדת לגבול — ולא מוצגת כאילו היא קיימת.

עקרון: **התווית משקרת, הפריים לא** — ולכן כל פריט נושא את מקור המידע
(`source`), את רמת הוודאות (`confidence`) ואת מצב המיפוי (`t_status`).
פריט שאי אפשר למקם בזמן מוצג בלי כפתור ניגון, לא עם טיימקוד שקרי.
"""
from __future__ import annotations

from pathlib import Path

from . import atomic_write_json, now_ts, read_json
from . import revisions as rev_mod
from . import tasks as tasks_mod
from .edl_utils import derive_keep, edl_change_summary

CHECKS_FILE = "changelog_checks.json"
PAD_BEFORE = 2.5          # שניות לפני נקודת התיקון בסבב הבדיקה
PAD_AFTER = 2.5           # ואחריה
MAX_CUT_ITEMS = 8         # חיתוכים בודדים שמוצגים כפריטים נפרדים (השאר מסוכם)
CHECK_STATES = ("pending", "ok", "not_fixed")
CLAUDE_STATES = ("pending", "verified", "not_fixed", "needs_eye")   # v9.18


# ═══════════════════════════════════════════════════════════ צירי זמן
def _edl_of(workdir, art):
    """ה-EDL שממנו נבנתה הגרסה. מקור ראשון: ה-snapshot של ה-revision."""
    rid = (art or {}).get("revision_id")
    if rid:
        rev = rev_mod.get_revision(workdir, rid)
        if rev and rev.get("edl"):
            return rev["edl"], "revision"
    return None, None


def timeline(workdir, art):
    """הציר של גרסה: keep_segments + speed + total. אין revision ⇒ None.

    לא נופלים ל-edl.json הנוכחי: הוא הציר של **עכשיו**, לא של הגרסה הזו,
    ומיפוי לפיו היה מייצר טיימקוד שנראה מדויק ומצביע למקום אחר.
    """
    edl, src = _edl_of(workdir, art)
    if not edl:
        return None
    review = edl.get("review") or {}
    keeps = edl.get("keep_segments")
    if not keeps:
        keeps = derive_keep(float(edl.get("total_dur") or 0),
                            review.get("cuts") or [], review.get("hook_move"))
    try:
        speed = float(review.get("speed") or 1.0) or 1.0
    except (TypeError, ValueError):
        speed = 1.0
    return {"keeps": [{"start": float(k["start"]), "end": float(k["end"])} for k in keeps],
            "speed": speed,
            "total": float(edl.get("total_dur") or 0),
            "source": src}


def _offsets(tl):
    acc, offs = 0.0, []
    for k in tl["keeps"]:
        offs.append(acc)
        acc += max(0.0, k["end"] - k["start"])
    return offs, acc


def out_to_src(t, tl):
    """זמן בציר הפלט של הגרסה → זמן ב-INPUT. מחוץ לטווח ⇒ הקצה הקרוב."""
    if tl is None or t is None:
        return None
    tt = max(0.0, float(t)) * float(tl["speed"])      # setpts: הפלט מכווץ במהירות
    offs, tot = _offsets(tl)
    if not tl["keeps"]:
        return tt
    if tt >= tot:
        return tl["keeps"][-1]["end"]
    for k, off in zip(tl["keeps"], offs):
        span = k["end"] - k["start"]
        if tt <= off + span:
            return round(k["start"] + (tt - off), 3)
    return tl["keeps"][-1]["end"]


def src_to_out(t, tl):
    """זמן ב-INPUT → זמן בציר הפלט. מחזיר (t_out, status).

    status: exact — הנקודה שרדה בגרסה הזו · cut_out — נחתכה, והוחזר הגבול
    הקרוב ביותר שנשמר (מה שהראל יראה אם יקפוץ לשם).
    """
    if tl is None or t is None:
        return None, "unknown"
    tt = float(t)
    offs, tot = _offsets(tl)
    best, best_d = None, None
    for k, off in zip(tl["keeps"], offs):
        if k["start"] - 1e-6 <= tt <= k["end"] + 1e-6:
            return round((off + (tt - k["start"])) / tl["speed"], 2), "exact"
        d = min(abs(tt - k["start"]), abs(tt - k["end"]))
        if best_d is None or d < best_d:
            best_d = d
            best = off if tt < k["start"] else off + (k["end"] - k["start"])
    if best is None:
        return None, "unknown"
    return round(max(0.0, min(best, tot)) / tl["speed"], 2), "cut_out"


def map_time(t, tl_from, tl_to, on_final=True):
    """טיימקוד של הערה → הזמן שלו בגרסה שמוצגת עכשיו.

    on_final=False ⇒ ההערה נכתבה על ציר ה-INPUT (בזמן עריכה), ולכן אין
    שלב ראשון להמרה.
    """
    if t is None:
        return {"t": None, "status": "none"}
    src = float(t) if not on_final else out_to_src(t, tl_from)
    if src is None:
        return {"t": None, "status": "unknown"}
    if tl_to is None:
        return {"t": None, "status": "unknown"}
    out, st = src_to_out(src, tl_to)
    return {"t": out, "status": st, "src_t": round(src, 2)}


# ═══════════════════════════════════════════════════ חותמת בזמן היצירה
def _resolved_at(c):
    return c.get("updated_at") or c.get("created_at") or ""


def stamp_fixes(workdir, since_ts=None):
    """ההערות שנפתרו מאז הגרסה הקודמת — נרשם **בתוך** רשומת הגרסה.

    נקרא מ-`artifacts.create_artifact` ברגע היצירה, כשחותמות הזמן עוד
    אומרות את האמת. `since_ts` = created_at של הגרסה הקודמת (None ⇒ הכל).
    """
    out = []
    for c in tasks_mod.list_comments(workdir):
        if c.get("status") != "resolved":
            continue
        ts = _resolved_at(c)
        if since_ts and ts <= since_ts:
            continue
        out.append({
            "comment_id": c["comment_id"], "text": c.get("text"),
            "category": c.get("category"), "priority": c.get("priority"),
            "time_start": c.get("time_start"), "time_end": c.get("time_end"),
            "on_final": bool(c.get("on_final")),
            "origin_artifact_id": c.get("artifact_id"),
            "origin_version": c.get("artifact_version"),
            "resolution": c.get("resolution"),
            "resolved_revision_id": c.get("resolved_revision_id"),
            "resolved_at": ts,
        })
    return out


# ═══════════════════════════════════════════════════ הסקה לגרסאות ישנות
def _rev_index(workdir):
    idx = read_json(Path(workdir) / "revisions" / "index.json", {}) or {}
    return {rid: i for i, rid in enumerate(idx.get("order") or [])}


def _bulk_created(arts):
    """created_at שחוזר על עצמו בשלוש גרסאות או יותר = חותמת מיגרציה, לא זמן
    יצירה אמיתי. אסור להסיק ממנה כלום."""
    seen = {}
    for a in arts:
        seen[a.get("created_at")] = seen.get(a.get("created_at"), 0) + 1
    return {ts for ts, n in seen.items() if ts and n >= 3}


def _infer_assignment(workdir, arts, all_arts=None):
    """{artifact_id: [fix,...]} + ההערות שלא נתלו על אף גרסה.

    שני אותות בלתי-תלויים; ההסכמה ביניהם היא רמת הוודאות שמוצגת להראל.
    `arts` = הגרסאות שמותר לשייך אליהן (אלה שאינן חתומות); `all_arts` משמש
    רק לזיהוי חותמת-מיגרציה גורפת.
    """
    revi = _rev_index(workdir)
    bulk = _bulk_created(all_arts or arts)
    ordered = sorted(arts, key=lambda a: (a.get("version") or 0))
    by_art, pending = {a["artifact_id"]: [] for a in ordered}, []

    for c in tasks_mod.list_comments(workdir):
        if c.get("status") != "resolved":
            continue
        ts = _resolved_at(c)
        rid = c.get("resolved_revision_id")

        by_rev = None
        if rid in revi:
            for a in ordered:
                ar = a.get("revision_id")
                if ar in revi and revi[ar] >= revi[rid]:
                    by_rev = a["artifact_id"]
                    break
        by_time = None
        for a in ordered:
            if a.get("created_at") in bulk or a.get("migrated"):
                continue
            if (a.get("created_at") or "") >= ts:
                by_time = a["artifact_id"]
                break

        target = by_rev or by_time
        if not target:
            pending.append(c)
            continue
        conf = "ודאי" if (by_rev and by_time and by_rev == by_time) else "משוער"
        fix = {
            "comment_id": c["comment_id"], "text": c.get("text"),
            "category": c.get("category"), "priority": c.get("priority"),
            "time_start": c.get("time_start"), "time_end": c.get("time_end"),
            "on_final": bool(c.get("on_final")),
            "origin_artifact_id": c.get("artifact_id"),
            "origin_version": c.get("artifact_version"),
            "resolution": c.get("resolution"),
            "resolved_revision_id": rid, "resolved_at": ts,
            "_confidence": conf,
        }
        by_art.setdefault(target, []).append(fix)
    return by_art, pending


# ═══════════════════════════════════════════════════════ שינויים מכניים
def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _mech_items(workdir, prev, cur, tl_prev, tl_cur):
    """מה השתנה בין שתי גרסאות מעבר להערות — נמדד מהרשומות ומה-EDL."""
    items = []
    if not prev:
        return items

    dp, dc = _num(prev.get("duration")), _num(cur.get("duration"))
    if dp and dc and abs(dc - dp) >= 0.2:
        items.append({"item_id": "mech_duration", "kind": "mechanical",
                      "icon": "⏱", "title":
                      f"אורך הסרטון: {dp:.1f}ש ← {dc:.1f}ש ({dc - dp:+.1f}ש)",
                      "t": None, "t_status": "none"})

    if (prev.get("music") or None) != (cur.get("music") or None):
        items.append({"item_id": "mech_music", "kind": "mechanical", "icon": "🎵",
                      "title": f"מוזיקה: {prev.get('music') or '—'} ← {cur.get('music') or '—'}",
                      "t": None, "t_status": "none"})

    bp, bc = prev.get("broll_items") or 0, cur.get("broll_items") or 0
    if bp != bc:
        items.append({"item_id": "mech_broll", "kind": "mechanical", "icon": "🎞",
                      "title": f"בירולים: {bp} ← {bc}", "t": None, "t_status": "none"})

    sp = tl_prev["speed"] if tl_prev else None
    sc = tl_cur["speed"] if tl_cur else None
    if sp and sc and abs(sp - sc) > 0.001:
        items.append({"item_id": "mech_speed", "kind": "mechanical", "icon": "⏩",
                      "title": f"קצב נגינה: {sp}x ← {sc}x", "t": None, "t_status": "none"})

    qp = (prev.get("qa") or {}).get("pass")
    qc = (cur.get("qa") or {}).get("pass")
    if qp is not None and qc is not None and qp != qc:
        items.append({"item_id": "mech_qa", "kind": "mechanical", "icon": "🧪",
                      "title": f"QA: {'עבר' if qp else 'נכשל'} ← {'עבר' if qc else 'נכשל'}",
                      "t": None, "t_status": "none"})

    # שינויי חיתוך — אלה **כן** ממוקמים בזמן, ולכן ניתנים לבדיקה בקליק
    ep, _ = _edl_of(workdir, prev)
    ec, _ = _edl_of(workdir, cur)
    if ep and ec and ep is not ec:
        summ = edl_change_summary(ep, ec)
        det = summ.get("detail") or {}
        events = ([("added", x) for x in det.get("added", [])] +
                  [("removed", x) for x in det.get("removed", [])] +
                  [("changed", x) for x in det.get("changed", [])])
        for i, (kind, ev) in enumerate(events[:MAX_CUT_ITEMS]):
            src_t = (ev.get("start") if kind != "changed"
                     else (ev.get("to") or {}).get("start"))
            out, st = src_to_out(src_t, tl_cur) if tl_cur else (None, "unknown")
            label = {"added": "✂ נוסף חיתוך", "removed": "↩ בוטל חיתוך",
                     "changed": "↔ גבול חיתוך הוזז"}[kind]
            items.append({"item_id": f"mech_cut_{kind}_{i}", "kind": "mechanical",
                          "icon": "✂", "title": f"{label} (מקור {src_t:.1f}ש)",
                          "t": out, "t_status": st})
        if len(events) > MAX_CUT_ITEMS:
            items.append({"item_id": "mech_cut_more", "kind": "mechanical", "icon": "✂",
                          "title": f"ועוד {len(events) - MAX_CUT_ITEMS} שינויי חיתוך "
                                   f"שלא פורטו כאן (מוצגים בלשונית גרסאות עריכה)",
                          "t": None, "t_status": "none"})
    return items


# ═══════════════════════════════════════════════════════════ מצב בדיקה
def _checks_path(workdir):
    return Path(workdir) / CHECKS_FILE


def load_checks(workdir):
    return read_json(_checks_path(workdir), {}) or {}


def set_check(workdir, artifact_id, item_id, state, note=None, actor="harel"):
    """סימון של הראל על פריט: נבדק ותקין / עדיין לא תוקן.

    v9.18 — merge ולא replace: פסיקת קלאוד (`claude`) שכבר יושבת על הפריט
    נשמרת. שני השחקנים כותבים על אותה רשומה, אף אחד לא דורס את השני.
    """
    if state not in CHECK_STATES:
        raise ValueError(f"מצב בדיקה לא מוכר: {state}")
    ch = load_checks(workdir)
    entry = ch.setdefault(artifact_id, {}).setdefault(item_id, {})
    entry.update({"state": state, "note": note or None,
                  "ts": now_ts(), "actor": actor})
    atomic_write_json(_checks_path(workdir), ch)
    return entry


def set_claude_verdict(workdir, artifact_id, item_id, state,
                       evidence=None, note=None):
    """פסיקת קלאוד על תיקון (v9.18) — אחרי מדידה + קריאת גיליון-המגע.

    verified — נבדק בראיות ותקין · not_fixed — התיקון לא נכנס (ההערה חוזרת
    לתור דרך review_cli) · needs_eye — אין דרך לאמת במכונה, נשאר להראל.
    הפסיקה נשמרת לצד הסימון של הראל, לא במקומו.
    """
    if state not in CLAUDE_STATES:
        raise ValueError(f"פסיקת קלאוד לא מוכרת: {state}")
    ch = load_checks(workdir)
    entry = ch.setdefault(artifact_id, {}).setdefault(item_id, {})
    entry["claude"] = {"state": state, "evidence": evidence or None,
                       "note": note or None, "ts": now_ts()}
    atomic_write_json(_checks_path(workdir), ch)
    return entry["claude"]


# ═══════════════════════════════════════════════════════════════ בנייה
def _item_from_fix(workdir, fix, tl_from, tl_cur, source):
    m = map_time(fix.get("time_start"), tl_from, tl_cur, on_final=fix.get("on_final", True))
    me = (map_time(fix.get("time_end"), tl_from, tl_cur, on_final=fix.get("on_final", True))
          if fix.get("time_end") is not None else {"t": None})
    return {
        "item_id": "cmt_" + fix["comment_id"],
        "kind": "comment",
        "comment_id": fix["comment_id"],
        "icon": {"edit": "✂", "transcript": "📝", "hook": "🎯", "pacing": "⏱",
                 "audio": "🔊", "captions": "💬", "broll": "🎞", "cover": "🖼",
                 "qa": "🧪", "general": "💭"}.get(fix.get("category"), "💭"),
        "title": fix.get("text") or "",
        "category": fix.get("category"), "priority": fix.get("priority"),
        "resolution": fix.get("resolution"),
        "origin_version": fix.get("origin_version"),
        "origin_time": fix.get("time_start"),
        "resolved_at": fix.get("resolved_at"),
        "t": m["t"], "t_end": me.get("t"), "t_status": m["status"],
        "src_t": m.get("src_t"),            # v9.18 — ציר המקור, להשוואת EDL
        "source": source,
        "confidence": fix.get("_confidence", "ודאי"),
    }


def build(workdir, artifact_id=None):
    """יומן השינויים של כל גרסאות הווידאו בפרויקט (או של גרסה אחת)."""
    from . import artifacts as art_mod       # מיובא כאן כדי למנוע מעגל
    w = Path(workdir)
    arts = art_mod.list_artifacts(w)
    if not arts:
        return {"versions": [], "pending_render": [], "total": 0}

    # `fixes == []` = "נרשם, ולא תוקנה אף הערה" (למשל החלפת מוזיקה בלבד);
    # `fixes` חסר לגמרי = גרסה שנוצרה לפני v9.15 ⇒ הסקה בדיעבד. ההבחנה הזו
    # היא ההבדל בין "אין תיקונים" ל"לא ידוע", ואסור לאחד אותם.
    inferred, unplaced = _infer_assignment(
        w, [a for a in arts if a.get("fixes") is None], all_arts=arts)
    checks = load_checks(w)
    by_id = {a["artifact_id"]: a for a in arts}
    tls = {a["artifact_id"]: timeline(w, a) for a in arts}

    versions = []
    for i, a in enumerate(arts):
        prev = arts[i - 1] if i else None
        tl_cur = tls[a["artifact_id"]]
        stamped = a.get("fixes")
        fixes = stamped if stamped is not None else inferred.get(a["artifact_id"], [])
        src = "רשום בזמן היצירה" if stamped is not None else "הוסק בדיעבד"
        for f in fixes:
            f.setdefault("_confidence", "ודאי" if stamped is not None else "משוער")

        items = []
        for f in fixes:
            origin = by_id.get(f.get("origin_artifact_id")) or prev
            tl_from = tls.get((origin or {}).get("artifact_id")) if origin else None
            items.append(_item_from_fix(w, f, tl_from, tl_cur, src))
        items += _mech_items(w, prev, a, tls.get((prev or {}).get("artifact_id")), tl_cur)

        acur = checks.get(a["artifact_id"], {})
        for it in items:
            rec = acur.get(it["item_id"]) or {}
            it["check"] = ({"state": rec.get("state", "pending"),
                            "note": rec.get("note"), "ts": rec.get("ts")}
                           if rec.get("state") else {"state": "pending"})
            # v9.18 — פסיקת קלאוד מוצגת לצד הסימון של הראל
            it["claude"] = rec.get("claude") or {"state": "pending"}
        n_notes = sum(1 for it in items if it["kind"] == "comment")
        n_done = sum(1 for it in items if it["check"]["state"] == "ok")
        n_bad = sum(1 for it in items if it["check"]["state"] == "not_fixed")
        n_cl_ok = sum(1 for it in items if it["claude"]["state"] == "verified")
        n_cl_bad = sum(1 for it in items if it["claude"]["state"] == "not_fixed")
        versions.append({
            "artifact_id": a["artifact_id"], "version": a.get("version"),
            "created_at": a.get("created_at"), "duration": a.get("duration"),
            "prev_version": (prev or {}).get("version"),
            "timeline_known": tl_cur is not None,
            "items": items,
            "counts": {"total": len(items), "notes": n_notes,
                       "checked": n_done, "not_fixed": n_bad,
                       "claude_verified": n_cl_ok, "claude_flagged": n_cl_bad,
                       "playable": sum(1 for it in items if it.get("t") is not None)},
        })

    # תיקון שנעשה **אחרי** הגרסה האחרונה עדיין לא נראה בשום וידאו. זה לא
    # "חסר מידע" אלא מצב אמיתי וחשוב: יש מה לרנדר. כל השאר — הערה שנפתרה
    # ולא הצלחנו לתלות על גרסה — מדווח בנפרד ובמפורש, ולא נבלע.
    claimed = {i["comment_id"] for v in versions for i in v["items"]
               if i["kind"] == "comment"}
    last = arts[-1]
    revi, bulk = _rev_index(w), _bulk_created(arts)
    pending, unassigned = [], []
    for c in unplaced:
        if c["comment_id"] in claimed:
            continue
        ts, rid = _resolved_at(c), c.get("resolved_revision_id")
        after_last = ((last.get("created_at") not in bulk and not last.get("migrated")
                       and ts > (last.get("created_at") or ""))
                      or (rid in revi and revi.get(last.get("revision_id"), -1) < revi[rid]))
        row = {"comment_id": c["comment_id"], "text": c.get("text"),
               "category": c.get("category"), "resolved_at": ts}
        (pending if after_last else unassigned).append(row)

    if artifact_id:
        versions = [v for v in versions if v["artifact_id"] == artifact_id]
    return {
        "versions": versions,
        "pending_render": pending,       # תוקן — אבל טרם נוצרה גרסה שמכילה את זה
        "unassigned": unassigned,        # תוקן — ולא ידוע לאיזו גרסה זה נכנס
        "total": len(versions),
    }


def review_plan(version, pad_before=PAD_BEFORE, pad_after=PAD_AFTER,
                focus=False):
    """סבב בדיקה: רק הקטעים שהשתנו, לפי סדר הזמן — במקום הסרטון המלא.

    שני פריטים שהקטעים שלהם נוגעים זה בזה מתמזגים, כדי שלא ייווצר ריצוד
    של קפיצה-ניגון-קפיצה על אותה שנייה.

    focus=True (v9.18) — רק מה שעדיין דורש את העין של הראל: פריט שקלאוד
    כבר אימת בראיות, או שקלאוד סימן not_fixed (חוזר לתור ממילא), או שהראל
    כבר סימן — יוצא מהסבב. תיקון מאומת נשאר זמין לדגימה, לא לחובה.
    """
    spots = []
    for it in version.get("items", []):
        if it.get("t") is None:
            continue
        if focus:
            if ((it.get("check") or {}).get("state", "pending") != "pending"
                    or (it.get("claude") or {}).get("state") in
                    ("verified", "not_fixed")):
                continue
        s = max(0.0, float(it["t"]) - pad_before)
        e = float(it.get("t_end") or it["t"]) + pad_after
        spots.append({"start": round(s, 2), "end": round(e, 2),
                      "item_ids": [it["item_id"]]})
    spots.sort(key=lambda x: x["start"])
    merged = []
    for s in spots:
        if merged and s["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], s["end"])
            merged[-1]["item_ids"] += s["item_ids"]
        else:
            merged.append(dict(s))
    covered = sum(x["end"] - x["start"] for x in merged)
    return {"spots": merged, "covered_secs": round(covered, 1)}
