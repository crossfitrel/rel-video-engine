#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
note_corrections.py — v7.8 · תיקוני כתיב מהערות הראל, אוטומטית
==============================================================
שורש הבעיה (ניתוח 40 ההערות בפועל, 25.7.26): "שגיאות כתיב בכתוביות" היא התלונה
החוזרת ביותר, והראל כבר כותב את התיקון המדויק בהערה — בשלוש תבניות קבועות:

    A. "בקרוספיט* ולא קרוספית"      → קרוספית ⇒ בקרוספיט
    B. "שהריל* הזה"                  → מילה עם כוכבית = הצורה הנכונה; המילה
                                        השגויה מזוהה בהתאמה מטושטשת בתמליל
    C. "אני האבא במקום אני דואגת"    → **מדווח בלבד**, לא מוחל: בעברית
                                        "X במקום Y" דו-משמעי (לפעמים X הנכון,
                                        לפעמים X השגוי) — נמדד 3/4 בכיוון ההפוך

עד היום כל תיקון כזה חזר דרך קלאוד (סבב שלם). הכלי הזה מחיל אותו ישירות על
התמליל לפני reconcile — כך ש"גימור מהיר" מהאפליקציה מתקן כתוביות בלי קלאוד.

בטיחות (עיקרון: לעולם לא להמציא):
  • תבנית C לא מוחלת אוטומטית אף פעם (ambiguous בדוח).
  • תבנית B מוחלת רק כשיש **מועמד יחיד** בתמליל במרחק עריכה 1-2 מהמילה המסומנת.
    שני מועמדים או יותר / אפס → מדווח כ-needs_manual, לא נוגע.
  • מילה שכבר מופיעה בתמליל בצורתה הנכונה — מדולגת (אין מה לתקן).
  • למידה גלובלית (asr-glossary.json) היא **shadow**: זוג נכנס ל-"pending" עם
    מונה; רק אחרי 2+ פרויקטים שונים הוא מקודם ל-"corrections" (--promote).
    אותה פילוסופיה כמו learn_from_edits: ראיות לפני החלה.

שימוש:
  python3 note_corrections.py --workdir "_work/שם" [--apply] [--learn] [--json out.json]
  python3 note_corrections.py --promote            # קידום pending→corrections (2+ פרויקטים)
"""
import argparse, json, re, sys, time, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
GLOSSARY = HERE / "asr-glossary.json"

NIQQUD = re.compile(r"[֑-ׇ]")
HEBWORD = r"[֐-׿'\"׳״A-Za-z0-9-]+"
# מילה + כוכבית (הצורה הנכונה לפי הראל)
RE_STAR = re.compile(rf"({HEBWORD})\s*\*")
# "X* ולא Y"  /  "X ולא Y"
RE_NOT = re.compile(rf"({HEBWORD})\s*\*?\s*ולא\s+({HEBWORD})")
# "X במקום Y"  (יכול להיות ביטוי של 1-3 מילים בכל צד)
RE_INSTEAD = re.compile(rf"((?:{HEBWORD}\s+){{0,2}}{HEBWORD})\s+במקום\s+((?:{HEBWORD}\s+){{0,2}}{HEBWORD})")


def core(w):
    """ליבת מילה: בלי ניקוד, בלי פיסוק קצה — להשוואה בלבד."""
    w = NIQQUD.sub("", unicodedata.normalize("NFC", w))
    return w.strip(" \t\n.,;:!?()[]{}\"'׳״…-*")


def lev(a, b):
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 3:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def parse_notes(texts):
    """מחזיר (pairs, stars, ambiguous) — pairs=[(wrong, right, rule)],
    stars=[(right, before, after)], ambiguous=[{...}] (מדווח, לא מוחל)."""
    pairs, stars, ambiguous = [], [], []
    for t in texts:
        for line in (t or "").splitlines():
            used = False
            for m in RE_NOT.finditer(line):
                right, wrong = core(m.group(1)), core(m.group(2))
                if right and wrong and right != wrong:
                    pairs.append((wrong, right, "A_not"))
                    used = True
            # "X במקום Y" — **לא מוחל אוטומטית**. בעברית הכיוון דו-משמעי:
            # "אני האבא במקום אני דואגת" = X הנכון; אבל "לקחת את הקטע שהוא עושה
            # טעות במקום את הקטע הנכון" = X השגוי. נמדד בפועל על ההערות הקיימות:
            # מתוך 4 התאמות, 3 היו בכיוון ההפוך או שטות ("חצי"→"שניות").
            # לכן: מדווח בלבד (ambiguous), הכרעה אנושית. עדיף לא לתקן מאשר לשבש.
            for m in RE_INSTEAD.finditer(line):
                a_, b_ = core(m.group(1)), core(m.group(2))
                if a_ and b_ and a_ != b_:
                    ambiguous.append({"pattern": "X במקום Y", "a": a_, "b": b_,
                                      "line": line.strip()[:120]})
            if used:
                continue
            for m in RE_STAR.finditer(line):
                c = core(m.group(1))
                if not c:
                    continue
                # הקשר: המילה שאחרי הכוכבית ולפני המילה המסומנת (בהערה) — משמש
                # לעיגון ההתאמה בתמליל ("רחוקות* מהאוזניים" → עוגן=מהאוזניים)
                after = core((line[m.end():].split() or [""])[0])
                before_toks = [core(x) for x in line[:m.start()].split()]
                before = before_toks[-1] if before_toks else ""
                stars.append((c, before, after))
    # דדופ תוך שמירת סדר
    seen = set(); p2 = []
    for w, r, rule in pairs:
        if (w, r) not in seen:
            seen.add((w, r)); p2.append((w, r, rule))
    seen_s = set(); s2 = []
    for s in stars:
        if s[0] not in seen_s:
            seen_s.add(s[0]); s2.append(s)
    return p2, s2, ambiguous


# מילות תפקוד נפוצות — לעולם לא "המילה השגויה" בהתאמה מטושטשת. בלי זה נצפה בפועל
# (25.7.26, "אופן-גים-השקה") תיקון שגוי לנו→לפני שהיה משבש תמליל תקין.
STOP = set("""אני אתה את אנחנו אתם הם היא הוא זה זו זאת אלה כל לא כן גם רק עוד אבל או אם כי
לי לך לו לה לנו לכם להם שלי שלך שלו שלה שלנו שלכם שלהם מה מי איך למה כמה יש אין היה היו
על אל עם בלי אחרי לפני בין תוך כמו אז שם פה כאן ככה יותר פחות מאוד ממש כבר עכשיו היום""".split())


def resolve_stars(stars, transcript_words, known_pairs):
    """מילה מסומנת → (wrong, right) רק בביטחון גבוה.

    שתי דרגות:
      1. **עוגן הקשר** (מועדף) — ההערה נותנת שכנה ("רחוקות* מהאוזניים"); מחפשים
         בתמליל את השכנה ובודקים את המילה הצמודה לה. התאמה יחידה = ודאות גבוהה.
      2. **התאמה גלובלית יחידה** — רק למילים באורך ≥5, מרחק עריכה ≤2, כשהמועמד
         אינו מילת-תפקוד. קצר/עמום → needs_manual (הראל מכריע באפליקציה).
    """
    resolved, manual = [], []
    cores = [core(w) for w in transcript_words]
    idx = {c: i for i, c in enumerate(cores)}
    already = {r for _, r, _ in known_pairs}

    def plausible(cand, target):
        if not cand or cand in STOP or len(cand) < 3:
            return False
        d = lev(cand, target)
        if d == 0 or d > 2:
            return False
        if len(target) <= 4 and d > 1:      # מילים קצרות — רק מרחק 1
            return False
        return abs(len(cand) - len(target)) <= 2

    for s, before, after in stars:
        if s in already or s in cores:      # כבר תקין / כבר מכוסה
            continue
        hit = None
        for anchor, side in ((after, +1), (before, -1)):
            if not anchor or anchor in STOP or anchor not in idx:
                continue
            positions = [i for i, c in enumerate(cores) if c == anchor]
            neigh = {cores[i - side] for i in positions
                     if 0 <= i - side < len(cores)}
            cands = [c for c in neigh if plausible(c, s)]
            if len(cands) == 1:
                hit = cands[0]
                break
        if hit:
            resolved.append((hit, s, "B_star_anchored"))
            continue
        cands = sorted({c for c in cores if plausible(c, s)})
        if len(cands) == 1 and len(s) >= 5:
            resolved.append((cands[0], s, "B_star_unique"))
        else:
            manual.append({"word": s, "candidates": cands})
    return resolved, manual


def apply_pairs(text, pairs):
    """החלפה על ליבת-מילה שלמה בלבד (לא substring), פיסוק נשמר."""
    n = 0
    fixes = []
    out_lines = []
    mapping = {w: r for w, r, _ in pairs}
    for line in text.splitlines():
        toks = re.split(r"(\s+)", line)
        for i, tok in enumerate(toks):
            c = core(tok)
            if c and c in mapping:
                toks[i] = tok.replace(c, mapping[c], 1)
                n += 1
                fixes.append({"from": c, "to": mapping[c]})
        out_lines.append("".join(toks))
    return "\n".join(out_lines), n, fixes


def load_glossary():
    try:
        return json.loads(GLOSSARY.read_text(encoding="utf-8"))
    except Exception:
        return {"corrections": {}}


def save_glossary(g):
    tmp = GLOSSARY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(GLOSSARY)


def learn(pairs, project):
    """shadow: כותב ל-pending עם רשימת פרויקטים. לא מחיל גלובלית."""
    g = load_glossary()
    pend = g.setdefault("pending", {})
    added = 0
    for wrong, right, _ in pairs:
        if wrong in g.get("corrections", {}):
            continue
        e = pend.setdefault(wrong, {"to": right, "projects": [], "first_seen": time.strftime("%Y-%m-%d")})
        if e.get("to") != right:            # סתירה — לא לומדים
            e["conflict"] = True
            continue
        if project not in e["projects"]:
            e["projects"].append(project); added += 1
    save_glossary(g)
    return added


def promote(min_projects=2):
    g = load_glossary()
    pend = g.get("pending", {})
    moved = []
    for wrong, e in list(pend.items()):
        if e.get("conflict"):
            continue
        if len(e.get("projects", [])) >= min_projects:
            g.setdefault("corrections", {})[wrong] = e["to"]
            moved.append({"from": wrong, "to": e["to"], "projects": e["projects"]})
            del pend[wrong]
    save_glossary(g)
    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir")
    ap.add_argument("--apply", action="store_true", help="כתוב את התמליל המתוקן לדיסק")
    ap.add_argument("--learn", action="store_true", help="הוסף זוגות ל-pending במילון הגלובלי")
    ap.add_argument("--promote", action="store_true", help="קדם pending→corrections (2+ פרויקטים)")
    ap.add_argument("--min-projects", type=int, default=2)
    ap.add_argument("--json", help="קובץ דוח")
    ap.add_argument("--only-open", action="store_true",
                    help="רק הערות שעדיין לא נסגרו (status != resolved)")
    a = ap.parse_args()

    if a.promote:
        moved = promote(a.min_projects)
        print(json.dumps({"promoted": moved}, ensure_ascii=False))
        return

    if not a.workdir:
        sys.exit("--workdir חובה (או --promote)")
    W = Path(a.workdir).resolve()
    cpath = W / "comments.json"
    comments = []
    if cpath.exists():
        try:
            raw = json.loads(cpath.read_text(encoding="utf-8"))
            comments = raw if isinstance(raw, list) else raw.get("comments", [])
        except Exception:
            comments = []
    if a.only_open:
        comments = [c for c in comments if c.get("status") != "resolved"]
    texts = [c.get("text", "") for c in comments if (c.get("actor") or "harel") != "claude"]

    tpath = next((W / c for c in ("edited.txt", "correct_transcript.txt") if (W / c).exists()), None)
    transcript = tpath.read_text(encoding="utf-8") if tpath else ""
    if not transcript:
        wf = W / "words_final.json"
        if wf.exists():
            transcript = " ".join(x["word"] for x in json.loads(wf.read_text(encoding="utf-8")))

    pairs, stars, ambiguous = parse_notes(texts)
    resolved, manual = resolve_stars(stars, transcript.split(), pairs)
    all_pairs = pairs + resolved
    new_text, n, fixes = apply_pairs(transcript, all_pairs)

    report = {
        "project": W.name,
        "comments_scanned": len(texts),
        "pairs_explicit": [{"from": w, "to": r, "rule": k} for w, r, k in pairs],
        "pairs_from_stars": [{"from": w, "to": r, "rule": k} for w, r, k in resolved],
        "needs_manual": manual,
        "ambiguous": ambiguous,
        "applied": n,
        "fixes": fixes,
        "transcript_file": tpath.name if tpath else None,
        "written": False,
    }
    if a.apply and n and tpath:
        tmp = tpath.with_suffix(tpath.suffix + ".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        tmp.replace(tpath)
        report["written"] = True
    if a.learn and all_pairs:
        report["learned_pending"] = learn(all_pairs, W.name)
    out = json.dumps(report, ensure_ascii=False, indent=1)
    if a.json:
        Path(a.json).write_text(out, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
