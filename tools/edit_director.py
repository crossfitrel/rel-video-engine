#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edit_director — הצינור העריכתי בחמישה פאסים (V2).

    מפיק (בריף) → הבנה → במאי (תוכנית) → ביצוע דטרמיניסטי → מבקר → ציון
                          ↑______________ לולאה מתחת לסף ______________|

הכל עובר דרך relvid.provider, כלומר אותה ריצה בדיוק ניתנת לשחזור עם
backend=replay. המודל בוחר מתוך מרחב מועמדים סופי ולעולם לא פולט timecodes.

שימוש:
    python3 tools/edit_director.py run --workdir DIR [--backend chat|api|replay]
                                       [--threshold 7.5] [--max-loops 2]
    python3 tools/edit_director.py status --workdir DIR

יציאה: 0 = הושלם · 2 = ממתין לתשובת אדם (backend=chat) · 1 = שגיאה
"""
import argparse, json, sys, time, datetime, hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from relvid.provider import Provider, NeedsHuman, ProviderError, prompt_version  # noqa: E402
import edit_plan as EP  # noqa: E402

WEIGHTS = {"hook": .15, "retention": .15, "story": .15, "flow": .15, "emotion": .10,
           "visual": .10, "educational": .08, "entertainment": .05,
           "platform_readiness": .07}

ACTION_MAP = {"tighten": "tighten_to", "flag": "suggest_only",
              "cut": "cut", "keep": "keep"}


def jload(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def jdump(p, obj):
    p = Path(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ════════════════════════════════════════════════ payloads
def _slim_candidate(c):
    """מה שהמודל צריך כדי לשפוט — בלי שדות שאין לו מה לעשות איתם."""
    f = c.get("features", {})
    keep = (
        # פערים בין מילים
        "gap_sec", "sentence_boundary", "gap_is_true_silence", "breath_detected",
        "rms_in_gap_db", "noise_floor_db", "speech_rate_before_wps",
        "speech_rate_after_wps", "motion_mean", "motion_lower_mean",
        "face_present_pct", "scene_change_in_gap",
        # משפטים שלמים
        "n_words", "dur_sec", "speech_rate_wps", "duplicate_similarity",
        "duplicate_of_sentence", "is_first", "is_last", "in_hook_window",
        "in_cta_window", "rms_mean_db", "all_words_filler", "sentence_index",
        # ⚠️ ארבעת מדדי התמונה. הפרומפט director.plan_v1.4 מקדיש להם סעיף
        # שלם ("התמונה, לא רק הקול") ומורה לבמאי לקבוע לפיהם את אורך הפאוזה
        # — אבל עד 17.8.26 הם לא היו ברשימה הזאת, כלומר **הבמאי קרא הוראה
        # על מספרים שלא הגיעו אליו**. זו בדיוק אותה עיוורון של V3 2.1-2.2,
        # רק דרך המסננת במקום דרך המדידה: candidates.py חישב אותם נאמנה,
        # ו-_slim_candidate זרק אותם בשקט. נמדד על "בריאות-לקום-מכיסא":
        # gap_0001 motion_around_norm=0.57 (תקיעה) ו-gap_0003
        # pose_delta_at_024=0.315 (פי 15 מהחציון) — שני מספרים שהיו משנים
        # את ההחלטה, והבמאי קיבל None.
        "pose_delta_at_024", "pose_range_in_gap",
        "face_low_before", "face_low_after", "motion_around_norm",
    )
    out = {"candidate_id": c["candidate_id"], "kind": c["kind"],
           "t_start": c["t_start"], "t_end": c["t_end"],
           "features": {k: f[k] for k in keep if k in f}}
    for k in ("prev_word", "next_word", "text"):
        if c.get(k) is not None:
            out[k] = c[k]
    # מגבלות קשיחות — מה שהמודל לא רשאי להפר. חייב להגיע אליו במפורש.
    if c.get("hard_constraints"):
        out["hard_constraints"] = c["hard_constraints"]
    return out


def build_payloads(W):
    cands = jload(W / "candidates.json")
    if not cands:
        raise SystemExit("[director] אין candidates.json — הריצו קודם tools/candidates.py")
    slim = [_slim_candidate(c) for c in cands["candidates"]]
    ids = {c["candidate_id"] for c in cands["candidates"]}
    sents = cands.get("sentences") or []
    manifest = jload(W / "project_manifest.json", {}) or {}
    notes = jload(W / "note_corrections.json", {}) or {}
    # ⚠️ בכוונה בלי שם התיקייה. שם תיקייה הוא ארטיפקט של ניהול קבצים, לא תוכן —
    #    ותלות בו הופכת כל העתקה או שינוי שם לפסילת cache. הנושא מגיע מהמניפסט.
    meta = {"total_dur": cands["source"]["total_dur"],
            "profile": manifest.get("profile", "social_vertical"),
            "topic": manifest.get("topic", ""),
            "user_notes": notes.get("comments") or notes.get("notes") or []}
    return cands, slim, ids, sents, meta


# ════════════════════════════════════════════════ פאס 0 — הגהה

def _apply_phrase_corrections(words, phrases):
    """תיקוני רב-מילה→מילה, דטרמיניסטיים, **לפני** ששואלים את המודל.
    שיבוש שאושר פעם אחת לא נשאל שוב לעולם — זה מה שמדייק את המערכת כבר
    מההתחלה בסרטון הבא. (30.7.26: "ועל כל צפוף" → "והמקום צפוף", בהוק.)
    הטווח נשמר מקצה לקצה, ולכן אף כתובית לא זזה."""
    import he_lexicon as LEX
    out, applied = list(words), []
    for src, dst in sorted(phrases.items(), key=lambda kv: -len(kv[0].split())):
        toks = src.split()
        n = len(toks)
        k = 0
        while k + n <= len(out):
            if all(LEX.norm(out[k + j]["word"]) == LEX.norm(toks[j]) for j in range(n)):
                merged = dict(out[k])
                tail = "".join(ch for ch in str(out[k + n - 1]["word"])[::-1]
                               if ch in "?!,.…")[::-1]
                merged["word"] = dst + tail
                merged["end"] = out[k + n - 1]["end"]
                applied.append({"i": k, "from": src, "to": merged["word"],
                                "merged_tokens": n, "source": "asr-glossary"})
                out = out[:k] + [merged] + out[k + n:]
            k += 1
    return out, applied


def pass_proofread(pv, W, sents):
    """מתקן את התמלול **לפני** שמישהו מחליט עריכה. פר-מילה עם אינדקס, כך
    שהתזמונים לא זזים. ראה `he_lexicon.py` להסבר מדוע הלקסיקון הוא הדק ולא שופט."""
    import he_lexicon as LEX
    raw = jload(W / "whisper_raw.json") or []
    words = sorted([w for w in raw if str(w.get("word", "")).strip()],
                   key=lambda w: float(w["start"]))
    if not words:
        return None, words
    gloss = jload(Path(__file__).resolve().parent / "asr-glossary.json", {}) or {}

    # ── תיקוני רב-מילה, דטרמיניסטיים, **לפני** ששואלים את המודל ──
    # שיבוש שאושר פעם אחת לא נשאל שוב לעולם. זה מה שהופך את המערכת למדויקת
    # יותר כבר מההתחלה בסרטון הבא, במקום לשאול את אותה שאלה כל פעם.
    # (30.7.26: "ועל כל צפוף" → "והמקום צפוף" — היה בהוק, אושר ע"י הראל.)
    words, phrase_applied = _apply_phrase_corrections(
        words, gloss.get("phrase_corrections") or {})

    flagged = LEX.unknown([w["word"] for w in words])
    payload = {
        "words": [{"i": i, "t": round(float(w["start"]), 2), "w": str(w["word"])}
                  for i, w in enumerate(words)],
        "flagged": flagged,
        "context": " ".join(str(w["word"]) for w in words),
        "known_confusions": dict(list((gloss.get("corrections") or {}).items())[:60]),
    }
    ans = pv.ask("proofreader", payload,
                 required_keys=("corrections", "approved", "needs_manual"))

    fixed = [dict(w) for w in words]
    applied = []
    for c in ans.get("corrections") or []:
        try:
            i = int(c["i"])
            conf = float(c.get("confidence", 0))
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= i < len(fixed)) or conf < 0.80:
            continue
        # שומרים על הפיסוק המקורי — התיקון נוגע בליבת המילה בלבד
        orig = str(fixed[i]["word"])
        tail = "".join(ch for ch in orig[::-1] if ch in "?!,.…")[::-1]
        if LEX.norm(orig) != LEX.norm(c.get("from", orig)):
            continue                      # האינדקס לא תואם למה שהמודל חשב — לא נוגעים
        fixed[i]["word"] = str(c["to"]) + tail
        applied.append({"i": i, "from": orig, "to": fixed[i]["word"],
                        "confidence": conf, "why": c.get("why", "")})

    # ⚠️ **לא** מעדכנים כאן את הלקסיקון הגלובלי.
    # הלקסיקון מזין את `flagged`, ו-`flagged` נכנס ל-payload של הפאס. עדכון
    # בתוך הפאס היה הופך את הקלט של הפאס לתלוי-מצב: כל ריצה מייצרת digest אחר,
    # ו-`--backend replay` מפסיק לשחזר. זו בדיוק אותה מלכודת של "מטא-דאטה
    # משתנה ב-payload" שכבר יש עליה בדיקת רגרסיה. האישורים נשמרים בפרויקט,
    # והקידום לגלובלי הוא צעד מפורש: `he_lexicon.py promote <project>`
    # (אותה תבנית כמו `note_corrections.py --promote`).
    jdump(W / "words_corrected.json", fixed)
    jdump(W / "transcript_fix.json", {
        "schema_version": 1, "created_at": now(),
        "prompt_version": prompt_version("proofreader"),
        "n_words": len(words), "flagged": flagged,
        "phrase_applied": phrase_applied,
        "applied": applied,
        "approved": ans.get("approved") or [],
        "needs_manual": ans.get("needs_manual") or [],
    })
    # המשפטים שנשלחים הלאה נושאים את הטקסט המתוקן
    # ⚠️ שיוך מילה→משפט לפי **קרבה**, לא לפי הכלה בחלון הזמן.
    # השורש (17.8.26): גבולות המשפטים ב-candidates.json נבנים מזמני מילים
    # שעברו `snap_words_to_audio`, בעוד שכאן קוראים את `whisper_raw` הלא-מוצמד.
    # ההפרש קטן (‏~0.3ש) אבל שיטתי, ותמיד באותו כיוון: **המילה הראשונה של כל
    # משפט נופלת מחוץ לחלון ונעלמת מ-`s["text"]`.** נמדד על "טיפ-אחד-בטן-בר":
    # sent_000 היה "טיפ אחד לטוז טו בר" והפך ל"אחד לטוז טו בר" — כלומר המילה
    # שנותנת לפורמט את שמו נעלמה בדיוק מהטקסט שהמבקר ושכבת הבירול רואים.
    # ל-`s["text"]` שני צרכנים אמיתיים: ה-`edited_transcript` של המבקר,
    # וההתאמה **המילולית** של הבירול (חוק ברזל 6 — הנימוק חייב לצטט את
    # המשפט). שניהם קיבלו משפטים קטומים. הכתוביות עצמן נבנות מהמילים ולכן
    # לא נפגעו — וזה בדיוק מה שהסתיר את זה.
    def _nearest_sentence(t):
        best, best_d = None, 1e9
        for j, s in enumerate(sents):
            if s["start"] <= t <= s["end"]:
                return j
            dist = s["start"] - t if t < s["start"] else t - s["end"]
            if dist < best_d:
                best, best_d = j, dist
        return best if best_d <= 0.60 else None

    buckets = {j: [] for j in range(len(sents))}
    for w in fixed:
        mid = (float(w["start"]) + float(w.get("end", w["start"]))) / 2.0
        j = _nearest_sentence(mid)
        if j is not None:
            buckets[j].append(str(w["word"]))
    for j, s in enumerate(sents):
        if buckets[j]:
            s["text"] = " ".join(buckets[j])
    print(f"  [proofreader] {len(flagged)} מילים נבדקו · {len(applied)} תוקנו · "
          f"{len(ans.get('needs_manual') or [])} להכרעה ידנית")
    return ans, fixed


def edited_transcript(W, plan, cands):
    """מה שהצופה שומע אחרי העריכה — הקלט של המבקר. בלי נימוקים."""
    by_id = {c["candidate_id"]: c for c in cands["candidates"]}
    cuts = EP.plan_to_cuts(plan, by_id)
    keeps = EP.cuts_to_keeps(float(cands["source"]["total_dur"]), cuts)

    def kept(t):
        return any(k["start"] - .001 <= t <= k["end"] + .001 for k in keeps)

    out, prev_end = [], None
    for s in cands.get("sentences") or []:
        mid = (float(s["start"]) + float(s["end"])) / 2.0
        if not kept(mid):
            continue
        if prev_end is not None:
            gap = round(max(0.0, float(s["start"]) - prev_end), 2)
            # הפער בפועל אחרי החיתוכים, לא הפער במקור
            for cs, ce, _ in cuts:
                if prev_end <= cs and ce <= float(s["start"]):
                    gap = round(gap - (ce - cs), 2)
            out.append({"gap_sec": max(0.0, gap)})
        out.append({"text": s["text"], "sec": round(float(s["end"]) - float(s["start"]), 2)})
        prev_end = float(s["end"])
    return out


# ════════════════════════════════════════════════ passes
def pass_producer(pv, sents, meta):
    return pv.ask("producer", {"meta": meta, "sentences": sents},
                  required_keys=("audience", "goal", "single_cta"))


def pass_understand(pv, brief, sents, slim, ids):
    return pv.ask("understand", {"brief": brief, "sentences": sents, "candidates": slim},
                  allowed_ids=ids, required_keys=("story", "pauses"))


def pass_director(pv, brief, understanding, slim, ids, feedback=None, attempt=0,
                  lessons=None):
    payload = {"brief": brief, "understanding": understanding, "candidates": slim}
    # v9.13 — למידה מ-n=1: הלקחים הקבועים + דפוסי התיקון של הראל (cohort).
    # הקובץ נכתב פעם אחת לפרויקט (director_lessons.py) ולכן ה-payload יציב
    # בתוך הפרויקט — לא מפר את "אסור מטא-דאטה משתנה ב-payload של פאס".
    if lessons:
        payload["harel_lessons"] = lessons
    if feedback:
        payload["fix_these"] = feedback
        payload["attempt"] = attempt
    return pv.ask("director", payload, allowed_ids=ids, required_keys=("decisions",))


def normalize_plan(raw, brief):
    """תשובת הבמאי → סכמת edit_plan.json שהצינור הקיים כבר יודע לקרוא."""
    decs = []
    for d in raw.get("decisions") or []:
        act = ACTION_MAP.get(d.get("action"), d.get("action"))
        nd = {"candidate_id": d.get("candidate_id"), "action": act,
              "reason": d.get("reason", ""),
              "confidence": float(d.get("confidence", 0) or 0),
              "expected_benefit": d.get("expected_benefit", "—"),
              "downside": d.get("downside", "—")}
        if d.get("pause_type"):
            nd["pause_type"] = d["pause_type"]
        if d.get("evidence"):
            nd["evidence"] = d["evidence"]
        if act == "tighten_to":
            nd["value"] = round(float(d.get("tighten_to") or d.get("value") or 0), 3)
        for k in ("t_start", "t_end"):
            if d.get(k) is not None:
                nd[k] = float(d[k])
        decs.append(nd)
    return {"schema_version": 1, "pass": "plan", "plan_id": hashlib.sha256(
        json.dumps(decs, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12],
        "prompt_version": prompt_version("director"), "created_at": now(),
        "brief": brief, "decisions": decs}


# ════════════════════════════════════════════════ פאס בירול
def _shortlist(W, manifest, report):
    """‏447 קליפים → בריכה מסוננת. כל שערי הקאנון נשארים ב-broll_pick."""
    import subprocess
    out = W / "broll_shortlist.json"
    ct = manifest.get("content_type") or "conversion"
    cmd = [sys.executable, str(HERE / "broll_pick.py"), "--shortlist",
           "--content-type", ct, "--dept", manifest.get("dept") or "",
           "--audience", manifest.get("audience") or "",
           "--brand", manifest.get("brand") or "rel",
           # v9.7: בלי `--workdir` שער סתירה-לבריף לא רץ — הוא קורא את
           # ההבטחה מ-`brief.json`. זו הייתה הדרך שבה "חימום עם מוט
           # מתאמנת" (שיעור מלא) הגיע לבריכה של סרטון שמבטיח רחבה פנויה.
           "--workdir", str(W),
           "--json", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        report.append(f"shortlist נכשל (exit {r.returncode}): "
                      f"{(r.stderr or r.stdout)[-200:]}")
        return None
    return jload(out)


def pass_broll(pv, W, brief, cands, plan, manifest):
    """מה הצופה **רואה** בזמן שהוא ממשיך לשמוע. רץ אחרי compile_edl, כי חלון
    שהמשפט שלו נחתך אינו חלון. המודל מחזיר (חלון, קליפ, ביטחון, נימוק);
    הזמנים והשערים — בקוד (`broll_director`)."""
    import broll_director as BD
    notes = []
    edl = jload(W / "edl.json", {}) or {}
    keeps = edl.get("keep_segments") or []
    out_dur = float(edl.get("kept_dur") or 0)
    if not keeps or out_dur <= 0:
        return None

    windows = BD.surviving_windows(cands["candidates"], keeps, out_dur)
    sl = _shortlist(W, manifest, notes)
    clips = (sl or {}).get("clips") or []
    paths = (sl or {}).get("_paths") or {}

    # **מי הקהל קובע את המבנה.** נגזר מ-content_type ומהבריף, לא מוזן ידנית.
    ct = manifest.get("content_type") or (sl or {}).get("content_type") or "conversion"
    dtr = BD.doctrine(ct, brief, cands.get("sentences") or [], keeps, out_dur)

    if not windows or not clips:
        doc = BD.write_plan(W, [], {"n_windows": len(windows), "pool_size": len(clips),
                                    "doctrine": dtr,
                                    "why": "אין חלונות ששרדו" if not windows
                                           else "הבריכה ריקה אחרי סינון",
                                    "notes": notes})
        print(f"  [broll] {len(windows)} חלונות · {len(clips)} קליפים · 0 שיבוצים")
        return doc

    ans = pv.ask("broll", {
        "doctrine": dtr,
        "brief": {k: brief.get(k) for k in ("audience", "goal", "single_cta", "tone")},
        "windows": windows, "clips": clips},
        allowed_ids={w["candidate_id"] for w in windows},
        # `bed_sequence` חובה גם ב-anchors_only (שם הוא []). מפתח אופציונלי
        # שהמודל יכול פשוט לא להחזיר הופך את דוקטרינת המצע להמלצה.
        required_keys=("placements", "bed_sequence"))

    accepted, rejected = BD.enforce(ans.get("placements"), windows, clips)
    items, dropped, face_gaps = BD.build_plan(accepted, windows, clips, out_dur,
                                              paths, keeps=keeps)

    # מצע: ממלא את מה שנשאר בין העוגנים. רק ב-continuous_bed.
    bed_items, trust_beats = [], []
    if dtr.get("mode") == "continuous_bed":
        packed, _ = BD.pack_bed(ans.get("bed_sequence") or [], items, dtr, clips, paths)
        # v9.9 — פעימת `trust` היא **החלטה**, לא קליפ: אין לה path ולכן היא
        # לא נכנסת לתוכנית הרינדור. היא כן נשמרת בדוח, וכן נספרת ככיסוי
        # מכוון ב-`face_holes` — אחרת התפקיד היה מדווח כליקוי בכל פעם.
        trust_beats = [p for p in packed if p.get("role") == "trust"]
        bed_items = [p for p in packed if p.get("role") != "trust"]
        items = BD.close_small_holes(items + bed_items, clips, dtr)

    # ── יישור לגבולות החיתוך — אחרון, אחרי שכל הזמנים כבר סופיים ────────────
    # הראל, 1.8.26: קצה בירול שנעצר 0.1ש לפני קאט מייצר שני אירועים ויזואליים
    # בשבריר שנייה. רץ **בשני המצבים** — גם ב-anchors_only, שם `close_small_holes`
    # לא רץ בכלל, ולכן שם הליקוי היה בלתי-נראה למערכת.
    items, cut_slivers = BD.snap_to_cuts(items, keeps, clips, dtr, out_dur)

    # מימוש קבצי הבירול מ-iCloud **לפני** שהרינדור נוגע בהם. בלי זה ffmpeg
    # נחסם על ה-read הראשון ונראה כתקוע (0% CPU, בלי שגיאה ובלי לוג).
    mat = BD.materialize([p["path"] for p in items], log=notes)

    cov = BD.coverage(items, out_dur)
    holes = BD.face_holes(items, dtr, trust_beats)
    target = dtr.get("coverage_target_pct")
    doc = BD.write_plan(W, items, {
        "n_windows": len(windows), "pool_size": len(clips), "doctrine": dtr,
        "prompt_version": prompt_version("broll"), "created_at": now(),
        "n_anchors": sum(1 for p in items if p.get("role") == "anchor"),
        "n_bed": sum(1 for p in items if p.get("role") == "bed"),
        "coverage_pct": cov, "coverage_target_pct": target,
        "coverage": BD.coverage_verdict(cov, dtr),
        "shot_list": BD.shot_list(windows, items, ans.get("skipped"), dtr),
        "n_stalled_windows": sum(1 for w in windows if w["is_stalled"]),
        "n_stalled_covered": sum(1 for p in items if p.get("covers_stall")),
        "rejected": rejected, "dropped": dropped,
        "face_gaps": face_gaps, "bed_face_holes": holes, "materialize": mat,
        "n_cuts": len(BD.cut_boundaries(keeps)),
        "n_snapped": sum(1 for p in items if p.get("snapped_to_cut") is not None),
        "cut_slivers": cut_slivers,
        "trust_beats": trust_beats,
        "model_skipped": ans.get("skipped") or [], "notes": notes})
    tgt = f" (יעד {target}%)" if target else ""
    print(f"  [broll] {dtr['mode']} · {len(windows)} חלונות · {len(clips)} קליפים · "
          f"{doc['n_anchors']} עוגנים + {doc['n_bed']} מצע · כיסוי {cov}%{tgt} · "
          f"{len(rejected)} נדחו · {len(holes)} חורי-פנים במצע · "
          f"{doc['n_snapped']} קצוות יושרו לקאט · {len(cut_slivers)} סליברים נותרו")
    return doc


def pass_review(pv, brief, plan, cands, W):
    return pv.ask("reviewer", {
        "brief": brief,
        "edited_transcript": edited_transcript(W, plan, cands),
        "candidates_used": sorted(d["candidate_id"] for d in plan["decisions"]
                                  if d["action"] != "keep")},
        required_keys=("findings", "verdict"))


def pass_score(pv, brief, plan, cands, review, qa, W, threshold):
    summary = {"n_decisions": len(plan["decisions"]),
               "n_cut": sum(1 for d in plan["decisions"] if d["action"] == "cut"),
               "n_tighten": sum(1 for d in plan["decisions"] if d["action"] == "tighten_to"),
               "n_keep": sum(1 for d in plan["decisions"] if d["action"] == "keep"),
               "n_flag": sum(1 for d in plan["decisions"] if d["action"] == "suggest_only")}
    ans = pv.ask("scorer", {"brief": brief, "threshold": threshold,
                            "edited_transcript": edited_transcript(W, plan, cands),
                            "review": review, "qa": qa, "plan_summary": summary},
                 required_keys=("scores",))
    ans["overall"] = weighted(ans["scores"])
    ans["threshold"] = threshold
    return ans


def weighted(scores):
    """הממוצע מחושב כאן, לא נלקח מהמודל — מספר שאפשר לבדוק."""
    tot = num = 0.0
    for k, w in WEIGHTS.items():
        v = scores.get(k)
        if isinstance(v, dict) and v.get("score") is not None:
            num += float(v["score"]) * w
            tot += w
    return round(num / tot, 2) if tot else 0.0


def qa_snapshot(W, val=None):
    """מה שה-scorer רואה על איכות טכנית.

    ⚠️ **מהוולידטור, לא מ-`qa_report.json`.** זו הייתה טעות מבנית ולא באג
    נקודתי: ה-scorer מדרג **תוכנית עריכה**, ו-`qa_report.json` הוא תוצאה של
    **ריצת גימור קודמת** — קובץ אחר, ציר אחר, לפעמים מנוע רינדור אחר. תיקנתי
    אותו פעמיים (‏31.7.26: קודם הוצאתי את גודל הקובץ מה-detail, ואז ראיתי את
    ה-digest זז שוב כשרשימת השערים עצמה השתנתה בין v1 ל-v2) — וזה הסימן
    שהתיקון היה בשכבה הלא-נכונה. **קלט של פאס חייב להיגזר מהתוכנית בלבד.**
    הוולידטור הוא פונקציה טהורה של התוכנית, ולכן הוא הקלט הנכון.

    `qa_report.json` נשאר מה שהוא: ראיה על **הקובץ**, ל-QA ולדוח — לא ל-scorer.
    """
    if val is not None:
        return {"source": "validator",
                **{k: val[k] for k in ("n_decisions", "n_cuts", "kept_dur",
                                       "n_segments", "auto_applied", "suggest_only")
                   if k in val},
                "hard_failures": list(val.get("hard") or [])}
    return _qa_report_snapshot(W)


def _qa_report_snapshot(W):
    """מצב השערים מהתוצר. לדוחות בלבד — **לא** ל-payload של פאס.

    ⚠️ **בלי `detail`, ובכוונה.** נמדד 31.7.26: `qa_report.json` נכתב מחדש בכל
    ריצת גימור, וה-`detail` נושא מדידות של אותו קידוד — `G5_format` מכיל את
    גודל הקובץ (22.4MB מול 28.1MB באותה תוכנית בדיוק) ו-`G4_loudness` את ה-
    LUFS שנמדד. כלומר אותה תוכנית עריכה ייצרה שני payloads שונים ל-scorer,
    digest אחר, ו-`--backend replay` נכשל עם "אין תשובה ב-cache" בכל ריצה
    שנייה. זו בדיוק המלכודת של "מטא-דאטה משתנה ב-payload של פאס", והפעם היא
    נכנסה דרך **קובץ תוצר** ולא דרך חותמת זמן.
    שם/עבר/חוסם הם פונקציה של התוכנית; גודל הקובץ אינו. ה-scorer צריך לדעת
    אם שער חוסם נפל — לא כמה בייטים יצאו.

    באג שני שנתפס באותה נשימה: הקובץ כותב `gate`/`pass`, והפונקציה קראה
    `name`/`ok` — כלומר ה-scorer קיבל מאז ומתמיד רשימת שערים **בלי שמות**.
    """
    q = jload(W / "qa_report.json", {}) or {}
    gates = q.get("gates") or q.get("results") or []
    if not isinstance(gates, list):
        return {"gates": gates, "pass": q.get("pass", q.get("ok"))}
    return {"gates": [{"name": g.get("gate") or g.get("name"),
                       "ok": g.get("pass") if g.get("pass") is not None else g.get("ok"),
                       "hard": g.get("hard", True)}
                      for g in gates],
            "pass": q.get("pass", q.get("ok"))}


# ════════════════════════════════════════════════ run
def run(workdir, backend=None, threshold=7.5, max_loops=2, force=False):
    W = Path(workdir).resolve()
    cands, slim, ids, sents, meta = build_payloads(W)
    pv = Provider(W, backend=backend)
    print(f"[director] backend={pv.backend} · {len(slim)} מועמדים · סף {threshold}")

    # פאס 0 — הגהה. רץ ראשון כדי שכל שאר הפאסים יראו את הטקסט הנכון,
    # והכתוביות ייצרבו ממנו. ראה `he_lexicon.py`.
    pass_proofread(pv, W, sents)
    # חלונות הבירול נושאים עותק של טקסט המשפט, והתאמת הבירול היא **מילולית**.
    # בלי הסנכרון הזה החלון היה נשאר עם "כל הציעות זמין" בזמן שהכתובית אומרת
    # "כל הציוד זמין" — כלומר המודל מתאים קליפ למילה שלא נאמרה, וגם בדיקת
    # הציטוט הייתה נכשלת על משפט תקין לגמרי.
    _by_idx = {s["i"]: s["text"] for s in sents}
    for c in cands["candidates"]:
        if c.get("kind") == "broll_window":
            i = c.get("features", {}).get("sentence_index")
            if i in _by_idx:
                c["text"] = _by_idx[i]
                c["prev_text"] = _by_idx.get(i - 1)
                c["next_text"] = _by_idx.get(i + 1)

    brief = pass_producer(pv, sents, meta)
    jdump(W / "brief.json", brief)

    und = pass_understand(pv, brief, sents, slim, ids)
    # ⚠️ מה שנשלח הלאה חייב להיות התשובה הגולמית בלבד. כל מטא-דאטה משתנה
    # (built_at, plan_id) שנכנס ל-payload של הפאס הבא הופך את ה-digest ללא יציב
    # ואז ה-cache אף פעם לא נפגע. המטא נכתב לקובץ, לא לשרשרת.
    jdump(W / "understanding.json", dict(und, schema_version=1, **{
        "pass": "understand", "prompt_version": prompt_version("understand"),
        "built_at": now()}))

    # v9.13 — הלקחים ודפוסי-התיקון של הראל (אם הוכנו). קריאה בלבד: הקובץ
    # נבנה פעם אחת לפרויקט ע"י director_lessons.py, ולכן יציב בתוך הפרויקט.
    lessons = jload(W / "lessons_for_director.json") or None

    feedback, loops, plan, val = None, 0, None, None
    while True:
        raw = pass_director(pv, brief, und, slim, ids, feedback, loops,
                            lessons=lessons)
        plan = normalize_plan(raw, brief)
        jdump(W / "edit_plan.json", plan)
        val = EP.validate(W, verbose=True)
        if val["ok"]:
            break
        loops += 1
        if loops > max_loops:
            print("❌ הבמאי לא הפיק תוכנית תקפה בתוך התקציב. לא נגענו במדיה.")
            return 1
        feedback = [{"kind": "validator_hard", "msg": m} for m in val["hard"]]
        print(f"[director] סבב {loops}: {len(val['hard'])} כשלי אימות חוזרים לבמאי")

    EP.compile_edl(W)

    review = pass_review(pv, brief, plan, cands, W)
    jdump(W / "review.json", review)

    score = pass_score(pv, brief, plan, cands, review, qa_snapshot(W, val), W, threshold)
    jdump(W / "quality_score.json", score)

    blockers = [f for f in review.get("findings", []) if f.get("severity") == "blocker"]
    # ── מתי חוזרים לפאס התכנון (30.7.26) ──
    # הלולאה הייתה מונעת אך ורק מ-`overall < threshold`, ולכן היא נסגרה גם על
    # ליקויים ש**אינם במרחב הפעולה של הבמאי** — למשל שגיאת תמלול שנצרבת ככתובית.
    # במקרה כזה כל סבב נוסף מייצר את אותה תוכנית ושורף תקציב. לכן: הציון עדיין
    # קובע, אבל ה-scorer רשאי להצהיר `reloop.needed=false` ולעצור — ורק כשאין
    # blocker. blocker תמיד מחייב חזרה, בלי קשר להצהרה.
    def _needs_reloop(score, blockers):
        if blockers:
            return True
        if score.get("reloop", {}).get("needed") is False:
            return False
        return score["overall"] < threshold

    need = _needs_reloop(score, blockers)
    _why = ("נדרשת חזרה" if need else
            "עבר" if score["overall"] >= threshold else
            "מתחת לסף — אך אין מה לתקן בשכבת העריכה (reloop.needed=false)")
    print(f"[director] ציון {score['overall']} (סף {threshold}) · "
          f"{len(blockers)} blockers · {_why}")

    reloops = 0
    while need and reloops < max_loops:
        reloops += 1
        focus = (score.get("reloop", {}).get("focus") or []) + \
                [f"{f.get('candidate_id') or '-'}: {f.get('what')} → {f.get('suggest')}"
                 for f in review.get("findings", []) if f.get("severity") in ("blocker", "major")]
        print(f"[director] חזרה {reloops}/{max_loops} לפאס 2 — {len(focus)} נקודות")
        raw = pass_director(pv, brief, und, slim, ids,
                            [{"kind": "review", "msg": m} for m in focus], 100 + reloops,
                            lessons=lessons)
        plan = normalize_plan(raw, brief)
        jdump(W / "edit_plan.json", plan)
        val = EP.validate(W, verbose=True)
        if not val["ok"]:
            print("⚠️  התוכנית המתוקנת לא עברה אימות — נשארים עם הקודמת")
            break
        EP.compile_edl(W)
        review = pass_review(pv, brief, plan, cands, W)
        jdump(W / "review.json", review)
        score = pass_score(pv, brief, plan, cands, review, qa_snapshot(W, val), W, threshold)
        score["loop"] = reloops
        jdump(W / "quality_score.json", score)
        blockers = [f for f in review.get("findings", []) if f.get("severity") == "blocker"]
        need = _needs_reloop(score, blockers)

    # ── שכבת הבירול — אחרונה בכוונה ─────────────────────────────────────────
    # רצה על ה-EDL **הסופי**, אחרי שהלולאות התכנסו. חלון שהמשפט שלו נחתך בסבב
    # אחרון אינו חלון, וקליפ שנבחר לרגע שכבר לא קיים נראה כמו החלטה תקינה עד
    # שמסתכלים על התוצר. כשל כאן לא מפיל את הריצה: העריכה עומדת בפני עצמה,
    # והבירול הוא שכבה מעליה.
    bdoc = None
    try:
        bdoc = pass_broll(pv, W, brief, cands, plan,
                          jload(W / "project_manifest.json", {}) or {})
    except NeedsHuman:
        raise
    except Exception as e:
        print(f"⚠️  שכבת הבירול נכשלה — ממשיכים בלי בירול: {e}")

    jdump(W / "director_run.json", {
        "schema_version": 1, "created_at": now(), "threshold": threshold,
        "plan_loops": loops, "review_loops": reloops,
        "broll": ({"n": len(bdoc.get("plan", [])),
                   "windows": bdoc.get("n_windows"),
                   "pool": bdoc.get("pool_size"),
                   "stalled_covered": f"{bdoc.get('n_stalled_covered', 0)}/"
                                      f"{bdoc.get('n_stalled_windows', 0)}",
                   "rejected": len(bdoc.get("rejected") or [])}
                  if bdoc else None),
        "final_score": score["overall"], "passed": not need,
        "validator": {k: val[k] for k in ("n_decisions", "n_cuts", "kept_dur", "n_segments",
                                          "auto_applied", "suggest_only")},
        "provider": pv.report()})
    if need:
        print("⚠️  נשאר מתחת לסף אחרי מיצוי הלולאות — התוצר מסומן, לא מוסתר.")
    return 0


def status(workdir):
    W = Path(workdir).resolve()
    for name in ("brief.json", "understanding.json", "edit_plan.json", "edl.json",
                 "review.json", "quality_score.json", "director_run.json"):
        p = W / name
        print(f"  {'✅' if p.exists() else '·  '} {name}"
              + (f"  {p.stat().st_size}B" if p.exists() else ""))
    pend = sorted((W / "ai_requests").glob("*.md")) if (W / "ai_requests").exists() else []
    pend = [q for q in pend if not (W / "ai_responses" / (q.stem + ".json")).exists()]
    for q in pend:
        print(f"  ⏳ ממתין לתשובה: {q}")
    return 2 if pend else 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); s = sub.add_parser("status")
    for x in (r, s):
        x.add_argument("--workdir", required=True)
    r.add_argument("--backend", default=None, choices=["api", "chat", "replay"])
    r.add_argument("--threshold", type=float, default=7.5)
    r.add_argument("--max-loops", type=int, default=2)
    r.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.cmd == "status":
        return status(a.workdir)
    try:
        return run(a.workdir, a.backend, a.threshold, a.max_loops, a.force)
    except NeedsHuman as e:
        print(f"⏸  {e}")
        return 2
    except ProviderError as e:
        print(f"❌ ספק: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
