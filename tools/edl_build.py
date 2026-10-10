#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edl_build.py — לב מערכת v5: בונה תוכנית עריכה (EDL) דטרמיניסטית מתזמוני-מילים אמיתיים,
לפני Descript. Descript מקבל אחר-כך רק הוראות כירורגיות ספורות — או כלום.

קלט:  whisper words JSON (מ-align_words.py, זמן אמיתי לכל מילה) + תסריט רופף אופציונלי.
פלט:  edl.json (keep/cuts+סיבות+confidence) · sentences.json · intent_card.md · review_suggestions.md

עקרונות (קאנון):
- תמליל = מקור אמת. תסריט רופף = מצפן בלבד. לא מסננים תוכן כי "לא בתסריט".
- Hook קדוש: בחלון הפתיחה (ברירת מחדל 6ש) חותכים רק שקט-הובלה ופקודות בימוי.
- טיפול שקט מדורג: דד-אייר נחתך, פאוזות מכוונות (beat אחרי punch / לפני CTA) נשמרות.
- כפילות → הטייק האחרון. פקודת בימוי ("סטופ", "עוד פעם") → חיתוך הטייק שלפניה.
- אנטי חיתוך-יתר: שאלות רטוריות/פירוט טכני = תוכן. חיתוך אוטומטי = confidence high בלבד.

הרצה:
  python3 edl_build.py --words whisper.json --out-dir _work/{שם}/ [--video in.mp4]
      [--loose-script script.txt] [--policy edl-policy.json] [--end DUR]
"""
import argparse, difflib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

def load_json(p): return json.loads(Path(p).read_text(encoding="utf-8"))

def norm_w(w):
    w = re.sub(r"[.,!?;:״\"'()\-…]+", "", w)
    return w.strip()

def build_sentences(words, gap_thr):
    sents, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["start"] - w["end"]) if nxt else 999
        if gap >= gap_thr:
            sents.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                          "text": " ".join(x["word"] for x in cur),
                          "wi": [words.index(cur[0]), words.index(cur[-1])]})
            cur = []
    if cur:
        sents.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                      "text": " ".join(x["word"] for x in cur),
                      "wi": [words.index(cur[0]), words.index(cur[-1])]})
    return sents

def sent_sim(a, b):
    na = " ".join(norm_w(w) for w in a.split())
    nb = " ".join(norm_w(w) for w in b.split())
    return difflib.SequenceMatcher(None, na, nb).ratio()


def containment(short, long_):
    """כמה מהמשפט הקצר מוכל בארוך (0-1), ברמת מילים.
    v6.4 — הסימן ל"אמר את המשפט שוב, בגרסה מלאה יותר". `sent_sim` לבדו מפספס את זה
    כי הוא מנרמל מול סכום האורכים ולכן נענש על ההרחבה עצמה."""
    sa = [norm_w(w) for w in short.split() if norm_w(w)]
    sb = [norm_w(w) for w in long_.split() if norm_w(w)]
    if not sa:
        return 0.0
    sm = difflib.SequenceMatcher(None, sa, sb)
    matched = sum(b.size for b in sm.get_matching_blocks())
    return matched / len(sa)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--video")
    ap.add_argument("--loose-script")
    ap.add_argument("--policy", default=str(HERE / "edl-policy.json"))
    ap.add_argument("--end", type=float, default=0.0, help="משך הקובץ (אם ידוע); אחרת סוף מילה אחרונה+trail")
    a = ap.parse_args()

    P = load_json(a.policy)
    words = [w for w in load_json(a.words) if norm_w(w.get("word", ""))]
    if not words:
        sys.exit("אין מילים בקובץ words")
    outd = Path(a.out_dir); outd.mkdir(parents=True, exist_ok=True)
    total = a.end or (words[-1]["end"] + 0.5)

    cuts = []   # {start,end,reason,confidence}
    def add_cut(s, e, reason, conf):
        s, e = max(0.0, round(s, 3)), min(total, round(e, 3))
        if e - s >= 0.06:
            cuts.append({"start": s, "end": e, "reason": reason, "confidence": conf})

    # ── 1. שקט-הובלה וזנב ──
    # לקח הראל 19.7 (shina): פתיחה ארוכה בלי דיבור היא לרוב פתיח ויזואלי (הליכה/התיישבות)
    # — זה Hook, לא שקט. מעל הסף → הצעה (medium) שהראל מכריע באפליקציה, לא חיתוך אוטומטי.
    if words[0]["start"] > 1.0:
        lead_conf = "high" if words[0]["start"] <= P.get("visual_opening_sec", 2.5) else "medium"
        lead_reason = ("שקט פתיחה ריק" if lead_conf == "high"
                       else "פתיחה ארוכה בלי דיבור — פתיח ויזואלי? (Hook) — הכרעה באפליקציה")
        add_cut(0.0, words[0]["start"] - P["lead_silence_keep"], lead_reason, lead_conf)
    if total - words[-1]["end"] > 1.0:
        add_cut(words[-1]["end"] + P["trail_silence_keep"], total, "שקט סיום ריק", "high")

    # ── 2. משפטים ──
    sents = build_sentences(words, P["sentence_gap"])

    # ── 3. פקודות בימוי → הטייק שלפניהן החוצה ──
    director = set(P["director_commands"])
    kill_sent = set()
    for si, s in enumerate(sents):
        toks = [norm_w(t) for t in s["text"].split()]
        joined = " ".join(toks)
        if any(cmd in joined for cmd in director) and len(toks) <= 6:
            # המשפט-פקודה עצמו + המשפט שקדם לו = טייק פסול
            kill_sent.add(si)
            if si > 0:
                kill_sent.add(si - 1)
    # ── 3.5 מילות אישור-טייק של הדובר (v6.4, פידבק הראל 25.7.26: "יש קטע שהוא אומר
    #      סבבה — זה לא חלק מהתסריט"). בניגוד ל-director_commands, מילה כזאת **לא**
    #      פוסלת את הטייק שלפניה — היא רק סימן שהטייק נגמר. שני מצבים:
    #      (א) משפט שכולו מילות-סימון ("סבבה", "יאללה") → נחתך כולו.
    #      (ב) מילת-סימון *חזקה* בסוף משפט תוכן ("...במחלקה השיקומית. סבבה?") →
    #          נחתכת המילה בלבד. הרשימה החזקה מכילה רק מילים שלעולם אינן תוכן אצלנו —
    #          "טוב"/"מעולה"/"בסדר" מודרות ממנה בכוונה ("זה דרך מעולה", "מרגיש טוב").
    markers = set(P.get("take_markers", []))
    markers_strong = set(P.get("take_markers_strong", []))
    # מילות אישור טהורות בלבד — מותר לחתוך אותן גם בתחילת משפט. "יאללה" מודר
    # בכוונה: בעברית הוא פותח-משפט לגיטימי ("יאללה, ספרו לי איך ישנתם" = CTA).
    markers_approval = set(P.get("take_markers_approval", []))
    marker_max = P.get("take_marker_max_words", 3)
    marker_cuts = []
    for si, s in enumerate(sents):
        toks = [norm_w(t) for t in s["text"].split() if norm_w(t)]
        if not toks:
            continue
        if len(toks) <= marker_max and all(t in markers for t in toks):
            kill_sent.add(si)
            continue
        if len(toks) > 1 and toks[-1] in markers_strong:
            w_last = words[s["wi"][1]]
            marker_cuts.append((w_last["start"] - 0.03, w_last["end"] + 0.05,
                                f"מילת אישור-טייק בסוף משפט «{toks[-1]}»"))
        # v6.5 — גם ב**תחילת** משפט: "סבבה. ושלא תבינו לא נכון..." — הדובר אישר
        # את הטייק הקודם ומיד המשיך. נמדד אצל הראל 25.7.26 שזה נשאר בסרטון.
        if len(toks) > 1 and toks[0] in markers_approval:
            w_first = words[s["wi"][0]]
            marker_cuts.append((w_first["start"] - 0.05, w_first["end"] + 0.04,
                                f"מילת אישור-טייק בתחילת משפט «{toks[0]}»"))
        # v6.5 — משפט קצר שנגמר בשלוש נקודות = טייק שנגמר באוויר
        # ("אמרתי כבר באותו איזה...") — Whisper מסמן את זה במפורש.
        raw_txt = s["text"].strip()
        if (raw_txt.endswith("...") or raw_txt.endswith("…")) and len(toks) <= 8:
            kill_sent.add(si)
            continue
        # v6.5 — "פטפוט בין טייקים": משפט קצר עם 2+ סימני-הפקה
        # ("זה היה סבבה? או שוב את המשפט הזה? משהו כאילו.")
        signals = sum(1 for tk in toks if tk in markers or tk in director)
        if any(k in " ".join(toks) for k in ("שוב את המשפט", "משהו כאילו", "עוד פעם")):
            signals += 2
        if signals >= 2 and len(toks) <= 12:
            kill_sent.add(si)

    # ── 3.9 שארית יתומה **צמודה לטייק פסול** (v6.5) — "ואז," שנשאר אחרי ש"יאללה"
    #      שאחריו נחתך. רק בסמיכות: כלל גורף על משפטים קצרים פסל ב-golden מילים
    #      לגיטימיות ("לאוטיפים?", "תקפו") — צמידות היא ההבדל בין שארית לתוכן.
    for si, s in enumerate(sents):
        if si in kill_sent:
            continue
        toks = [norm_w(x) for x in s["text"].split() if norm_w(x)]
        if (len(toks) > P.get("fragment_max_words", 2)
                or (s["end"] - s["start"]) > P.get("fragment_max_sec", 1.5)
                or s["start"] < P["hook_protect_sec"]):
            continue
        near_dead = (si + 1 in kill_sent) or (si - 1 in kill_sent)
        if near_dead:
            kill_sent.add(si)

    # ── 3.8 מילת-אישור טהורה **בכל מקום** (v6.5, הוראת הראל 25.7.26:
    #      "יש קטע שהוא אומר סבבה — זה לא חלק מהתסריט"). "סבבה"/"וואלה"/"אוקיי"
    #      אינן תוכן אצלנו בשום הקשר, גם באמצע משפט ("זה מקל על הגוף עכשיו, זה
    #      סבבה. מוזמנים להגיע...") — שם לא עזרו לא כלל-הקצה ולא כלל-המשפט-השלם.
    #      "יאללה" **לא** ברשימה הזאת (פותח-משפט לגיטימי — ראה golden/שינה-והתאוששות).
    for wi_, w_ in enumerate(words):
        if norm_w(w_["word"]) not in markers_approval:
            continue
        conf = "high" if w_["start"] >= P["hook_protect_sec"] else "medium"
        add_cut(w_["start"] - 0.05, w_["end"] + 0.05,
                f"מילת אישור-טייק «{norm_w(w_['word'])}»", conf)

    # ── 4. כפילויות (טייקים) — שמור את האחרון ──
    n = len(sents)
    for i in range(n):
        if i in kill_sent:
            continue
        for j in range(i + 1, n):
            if j in kill_sent:
                continue
            li, lj = len(sents[i]["text"].split()), len(sents[j]["text"].split())
            if min(li, lj) < P["take_min_words"]:
                continue
            if sent_sim(sents[i]["text"], sents[j]["text"]) >= P["take_similarity"]:
                kill_sent.add(i)  # המוקדם נופל, המאוחר נשאר
                break
            # v6.4 — **הכלה**, לא רק דמיון. difflib מנרמל מול *סכום* האורכים, ולכן
            # טייק חוזר-מורחב חומק: "לבנות תנועה חזקה לאורך זמן" (5 מילים) מול
            # "או לאבחון שיעזור לכם לבנות תנועה חזקה ונכונה לאורך זמן" (9) נותן
            # ratio≈0.65 < 0.72 ⇒ לא נתפס, והטייק הכושל נשאר בסרטון (הראל תפס בפועל
            # 25.7.26). כאן נמדד כמה מהמשפט הקצר מוכל בארוך — הסימן האמיתי ל"אמר
            # את זה שוב, מלא יותר".
            if min(li, lj) >= P.get("take_containment_min_words", 4):
                short, long_ = ((sents[i]["text"], sents[j]["text"]) if li <= lj
                                else (sents[j]["text"], sents[i]["text"]))
                if containment(short, long_) >= P.get("take_containment", 0.82):
                    kill_sent.add(i)
                    break
    # ── 4.5 חזרה **בתוך** משפט (v6.5) — שלוש חזרות של "אל תחכו שזה יעבור לבד"
    #      נבלעו במשפט אחד כי הפער ביניהן <sentence_gap, ולכן זיהוי-הכפילות
    #      ברמת-משפט לא ראה אותן בכלל (הראל 25.7.26). כאן מחפשים n-gram שחוזר
    #      בתוך אותו משפט ומוחקים את כל המופעים חוץ מהאחרון.
    for si, s in enumerate(sents):
        if si in kill_sent:
            continue
        i0, i1 = s["wi"]
        toks = [norm_w(words[k]["word"]) for k in range(i0, i1 + 1)]
        n_min = P.get("intra_repeat_min_words", 4)
        seen = {}
        spans = []
        for L in range(min(10, len(toks)), n_min - 1, -1):
            for k in range(len(toks) - L + 1):
                key = " ".join(toks[k:k + L])
                if not key.strip():
                    continue
                seen.setdefault(key, []).append(k)
            for key, pos in seen.items():
                if len(pos) < 2:
                    continue
                # כל המופעים חוץ מהאחרון יורדים
                for k in pos[:-1]:
                    spans.append((k, k + L - 1))
            if spans:
                break
            seen = {}
        for k0, k1 in spans:
            ws_, we_ = words[i0 + k0], words[i0 + k1]
            add_cut(ws_["start"] - 0.05, we_["end"] + 0.05,
                    f"חזרה בתוך משפט: «{' '.join(toks[k0:k1+1])[:50]}»", "high")

    # ── 5. התחלות כושלות: משפט קצר שהוא רישא של המשפט הבא ──
    for i in range(n - 1):
        if i in kill_sent:
            continue
        cur_toks = sents[i]["text"].split()
        if len(cur_toks) <= P["false_start_max_words"]:
            nxt = sents[i + 1]["text"]
            if sent_sim(sents[i]["text"], " ".join(nxt.split()[: len(cur_toks) + 2])) >= 0.62:
                kill_sent.add(i)

    for si in sorted(kill_sent):
        s = sents[si]
        conf = "high"
        if s["start"] < P["hook_protect_sec"] and si == 0:
            conf = "medium"  # בלוק פתיחה — לא חותכים אוטומטית, רק בהוראה
        add_cut(s["start"] - 0.05, s["end"] + 0.05,
                f"טייק פסול/כפילות: «{s['text'][:60]}»", conf)

    # מילות אישור-טייק בזנב משפט (v6.4) — נחתכת המילה בלבד, לא המשפט
    for ms, me, reason in marker_cuts:
        add_cut(ms, me, reason, "high" if ms >= P["hook_protect_sec"] else "medium")

    # ── 6. מילות מילוי מבודדות ──
    for i, w in enumerate(words):
        t = norm_w(w["word"])
        if t not in set(P["filler_words"]):
            continue
        prev_gap = w["start"] - (words[i - 1]["end"] if i else 0.0)
        next_gap = (words[i + 1]["start"] if i + 1 < len(words) else total) - w["end"]
        if prev_gap >= P["filler_isolated_gap"] and next_gap >= P["filler_isolated_gap"]:
            conf = "medium" if w["start"] < P["hook_protect_sec"] else "high"
            add_cut(w["start"] - 0.04, w["end"] + 0.04, f"מילת מילוי «{t}»", conf)

    # ── 7. שקטים בין מילים (מדורג) ──
    last_sent_start = sents[-1]["start"] if sents else 0.0
    for i in range(len(words) - 1):
        gap = words[i + 1]["start"] - words[i]["end"]
        if gap <= P["silence_in_sentence_keep"]:
            continue
        gs, ge = words[i]["end"], words[i + 1]["start"]
        boundary = gap >= P["sentence_gap"]
        keep = P["silence_between_sentences_keep"] if boundary else P["silence_in_sentence_keep"]
        # פאוזות מכוונות: לפני CTA (המשפט האחרון) שומרים beat
        if boundary and abs(ge - last_sent_start) < 0.3:
            keep = max(keep, P["cta_beat_keep"])
        if gs < P["hook_protect_sec"]:
            if gap < 1.0:
                continue  # בחלון ההוק לא נוגעים בפאוזות קצרות
            keep = max(keep, 0.5)
        if gap > keep + 0.08:
            conf = "high" if gap >= P["silence_in_sentence_cut_above"] or boundary else "medium"
            add_cut(gs + keep, ge, f"שקט {gap:.2f}ש → {keep:.2f}ש", conf)

    # ── מיזוג חיתוכים חופפים ──
    # תיקון 23.7.26 (הראל): סף המיזוג כאן חייב להיות >= הסף שמשמש למטה כדי להחליט אם
    # להשאיר keep segment עצמאי (0.04ש) — אחרת שני cuts שנשארו לא-ממוזגים במרחק
    # 0.03-0.04ש מייצרים sliver שנבלע בשקט (לא מוצג כ-keep, לא באמת ממוזג) → "קאט רפאים"
    # שנראה כקפיצת-פריים/מאית-שנייה בפלט הסופי. שני הספים מתואמים עכשיו יחד (ראה גם
    # relvid/edl_utils.derive_keep, אותו תיקון בדיוק שם).
    MIN_KEEP_GAP = 0.04
    cuts.sort(key=lambda c: c["start"])
    merged = []
    for c in cuts:
        if merged and c["start"] <= merged[-1]["end"] + MIN_KEEP_GAP:
            m = merged[-1]
            if c["end"] > m["end"]:
                m["end"] = c["end"]
                m["reason"] += " + " + c["reason"]
                # v6.5 — עד כאן המיזוג לקח את הביטחון ה**גרוע** ביותר, ולכן חיתוך
                # ודאי של טייק פסול שנגע בטרים-שקט קטן (medium) ירד ל-medium ולא
                # הוחל אוטומטית. כך שרד "ואז, יאללה" בסרטון של הראל (25.7.26).
                # מעכשיו: הטוב ביותר — **חוץ** מקאט "פתיח ויזואלי", ששם ה-medium
                # הוא הגנה מכוונת על Hook ואסור לשדרג אותה.
                order = {"high": 0, "medium": 1, "low": 2}
                protected = "פתיח ויזואלי" in m["reason"] or "פתיח ויזואלי" in c["reason"]
                pick = max if protected else min
                m["confidence"] = pick(m["confidence"], c["confidence"], key=lambda x: order[x])
        else:
            merged.append(dict(c))

    auto = [c for c in merged if c["confidence"] in P["confidence_auto_apply"]]
    manual = [c for c in merged if c["confidence"] not in P["confidence_auto_apply"]]

    # ── keep segments (מהחיתוכים האוטומטיים בלבד) ──
    keep, pos = [], 0.0
    for c in auto:
        if c["start"] > pos + MIN_KEEP_GAP:
            keep.append({"start": round(pos, 3), "end": round(c["start"], 3)})
        pos = max(pos, c["end"])
    if pos < total - MIN_KEEP_GAP:
        keep.append({"start": round(pos, 3), "end": round(total, 3)})
    # ── v6.6 — פתיח-פורמט קבוע למקומו הנכון (הראל 25.7.26) ──
    # "מנפצים לכם מיתוסים" הוא **הפתיח הקבוע של הפינה**, שנבו אומר אחרי הקטע
    # הראשון. בגלם הוא מוקלט איפה שיצא (כאן: באמצע), וב-v7.9 האפקט הורכב במקום
    # שבו הוא נאמר — כלומר בסוף הסרטון. זו לא בעיית אפקט אלא בעיית **סדר**:
    # הקטע עצמו צריך לעבור לאחרי המשפט הראשון, והאפקט הולך איתו.
    FORMAT_INTRO_PHRASES = ["מנפצים לכם מיתוסים", "מנפצים מיתוסים", "מנפץ לכם מיתוסים"]
    format_move = None
    live_idx = [i for i in range(len(sents)) if i not in kill_sent]
    if len(live_idx) >= 3:
        first_i = live_idx[0]
        for si in live_idx[1:]:
            joined = " ".join(norm_w(x) for x in sents[si]["text"].split())
            if not any(" ".join(norm_w(y) for y in ph.split()) in joined
                       for ph in FORMAT_INTRO_PHRASES):
                continue
            if si == live_idx[1]:
                break                      # כבר במקום הנכון
            hs, he = sents[si]["start"] - 0.06, sents[si]["end"] + 0.06
            anchor = sents[first_i]["end"]
            front, rest = [], []
            for k in keep:
                s, e = k["start"], k["end"]
                lo, hi = max(s, hs), min(e, he)
                if lo < hi - 0.04:
                    if s < lo - 0.04:
                        rest.append({"start": s, "end": round(lo, 3)})
                    front.append({"start": round(lo, 3), "end": round(hi, 3)})
                    if e > hi + 0.04:
                        rest.append({"start": round(hi, 3), "end": e})
                else:
                    rest.append(k)
            if front:
                pos_i = 0
                for idx_, k in enumerate(rest):
                    if k["start"] <= anchor <= k["end"] + 0.2:
                        pos_i = idx_ + 1
                        break
                keep = rest[:pos_i] + front + rest[pos_i:]
                format_move = {"phrase": sents[si]["text"][:60],
                               "from": [round(hs, 2), round(he, 2)],
                               "after_sentence_end": round(anchor, 2)}
            break

    # ── v6.7 — "אוויר לפני טייק" (הראל 25.7.26: "בשתי השניות הראשונות של
    #      'מוזמנים להגיע אלינו' נבו ממלמל לעצמו את מה שהוא צריך להגיד").
    #      מלמול-חזרה לפני טייק הוא מעל סף ה-‎-40dB ולכן ה-tighten לא נוגע בו,
    #      ו-Whisper לא מתמלל אותו — כלומר אף שער לא רואה אותו. הסימן הוודאי:
    #      קטע שמתחיל הרבה לפני המילה הראשונה שבתוכו. הקטע הראשון פטור (Hook /
    #      פתיח ויזואלי מוגן).
    air = P.get("pre_take_air_keep", 0.25)
    trimmed_air = 0.0
    for idx_, k in enumerate(keep):
        if idx_ == 0:
            continue
        inside = [w for w in words if w["start"] >= k["start"] - 0.01 and w["end"] <= k["end"] + 0.01]
        if not inside:
            continue
        lead = inside[0]["start"] - k["start"]
        if lead > air + 0.05:
            new_start = round(inside[0]["start"] - air, 3)
            trimmed_air += new_start - k["start"]
            k["start"] = new_start

    kept_dur = sum(k["end"] - k["start"] for k in keep)

    # ── remap: זמן מקורי → זמן אחרי חיתוך (להוראות ב-ROUGH) ──
    def remap(t):
        acc = 0.0
        for k in keep:
            if t < k["start"]:
                return acc
            if t <= k["end"]:
                return acc + (t - k["start"])
            acc += k["end"] - k["start"]
        return acc
    for c in manual:
        c["rough_start"] = round(remap(c["start"]), 2)
        c["rough_end"] = round(remap(c["end"]), 2)

    edl = {"source_words": str(a.words), "video": a.video or "", "total_dur": round(total, 2),
           "kept_dur": round(kept_dur, 2), "removed_dur": round(total - kept_dur, 2),
           "keep_segments": keep, "auto_cuts": auto, "manual_review_cuts": manual,
           "format_intro_move": format_move,
           "pre_take_air_trimmed": round(trimmed_air, 2),
           "policy": str(a.policy)}
    (outd / "edl.json").write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")

    live_sents = [s for i, s in enumerate(sents) if i not in kill_sent]
    (outd / "sentences.json").write_text(json.dumps(
        [{"start": round(remap(s["start"]), 2), "end": round(remap(s["end"]), 2), "text": s["text"]}
         for s in live_sents], ensure_ascii=False, indent=1), encoding="utf-8")

    # ── INTENT CARD ──
    loose = Path(a.loose_script).read_text(encoding="utf-8").strip() if a.loose_script and Path(a.loose_script).exists() else ""
    hook = live_sents[0]["text"] if live_sents else ""
    cta = live_sents[-1]["text"] if live_sents else ""
    beats = "\n".join(f"- {s['text'][:90]}" for s in live_sents[1:-1][:6])
    # v9.25 (הראל 19.9.26): יעד האורך לפי סוג התוכן (length_policy), לא 60ש קבוע.
    sys.path.insert(0, str(HERE))
    import length_policy as LP
    _lp = LP.evaluate(kept_dur, *LP.from_workdir(outd))
    card = (f"# INTENT CARD\n\n- **Hook (נאמר בפועל):** {hook}\n- **CTA (נאמר בפועל):** {cta}\n"
            f"- **קו סיפור:**\n{beats}\n\n- **תסריט רופף (מצפן בלבד):** {loose or '—'}\n"
            f"- **משך אחרי חיתוך אוטומטי:** {kept_dur:.1f}ש (יעד {_lp['target'][0]:.0f}-{_lp['target'][1]:.0f}ש · {_lp['label']})\n")
    (outd / "intent_card.md").write_text(card, encoding="utf-8")

    # ── הצעות רוויו (החלטות פתוחות לאפליקציית הרוויו של הראל) ──
    lines = ["# הצעות רוויו (טיימקודים בציר ה-ROUGH אחרי החיתוך המקומי)", ""]
    if not manual:
        lines.append("✅ אין החלטות פתוחות — אין הצעות לרוויו.")
    for i, c in enumerate(manual, 1):
        lines.append(f"{i}. [{c['confidence']}] {c['rough_start']}–{c['rough_end']}s — {c['reason']} — החלטה: לחתוך רק אם אינו חלק מה-Hook/תוכן.")
    if _lp["level"] in ("hard", "reason"):
        lines.append(f"\n⚠️ {_lp['message']} — לקצר מהאמצע בלבד (לא Hook ולא CTA), "
                     f"או לרשום length_reason אם התוכן מחזיק.")
    (outd / "review_suggestions.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"ok": True, "total": round(total, 2), "kept": round(kept_dur, 2),
                      "auto_cuts": len(auto), "manual_review": len(manual),
                      "sentences": len(live_sents), "out_dir": str(outd)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
