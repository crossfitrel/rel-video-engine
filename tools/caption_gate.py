#!/usr/bin/env python3
"""caption_gate.py — שער הקפשן האחד של R.E.L (v1, 10.10.26). מקור אחד לכל מי שכותב קפשן.

שתי שכבות:
 1. lint   — קאנון הקפשן (CANON → "קפשנים — קאנון אחיד") + חוקי קול. הועבר מ-
             08/06-מקורות-וסקילז/tools/caption_lint.py (שהפך לעטיפה שמפעילה את הקובץ הזה).
 2. novelty — "הקפשן משלים את הסרטון, לא משכפל אותו" (הראל 10.10.26: "הקפשן תמיד חוזר
             על מה שנאמר בתסריט עצמו"). כל משפט בגוף נמדד מול מה שנשמע בסרטון.

מדידת בסיס (10.10.26, n=88 קפשנים מאושרים ב-~/rel-video-work, מול words_final = מה שנשמע):
  echo כולל: חציון 0.56 · p25 0.41 · p75 0.69 · שורה 1 = הד ב-42/88 · בלי משפט חדש 14/88.
  28/88 מהקפשנים שכבר אושרו היו נכשלים בשער — זה גודל הבעיה שהראל תיאר.
  מכאן הספים: FAIL מעל p75 (הרבע הכי משוכפל בארכיון) או אפס משפטים חדשים;
  ⚠ מעל p25 — היעד הוא שקפשן חדש יהיה פחות משוכפל מ-75% מהארכיון.

שימוש:
  python3 caption_gate.py --type ערך|המרה|קהילה|עדות [--brand club|harel] [--transcript T] < caption.txt
  python3 caption_gate.py --workdir ~/rel-video-work/<proj> --type ערך      # קפשן+תמליל מהפרויקט
  python3 caption_gate.py --sources ~/rel-video-work/<proj>                  # חומר גלם לקפשן (מה לא נאמר)
  python3 caption_gate.py --calibrate ~/rel-video-work                       # מדידת בסיס מחדש
יציאה: 0 = PASS · 1 = FAIL.
"""
import argparse, json, os, re, statistics, sys

# ── ספים (נגזרו ממדידה — ר' למעלה) ─────────────────────────────────────────
ECHO_SENT = 0.60      # משפט שרוב מילות התוכן שלו נשמעו בסרטון = "הד"
NOVEL_SENT = 0.40     # משפט שרובו לא נשמע = "חדש"
ECHO_FAIL = 0.69      # p75 של הארכיון
ECHO_WARN = 0.41      # p25 של הארכיון

# ── קאנון ──────────────────────────────────────────────────────────────────
EMO = re.compile('[\U0001F300-\U0001FAFF☀-➿\U0001F900-\U0001F9FF❤]')
EMO_ANY = re.compile('[\U0001F000-\U0001FAFF☀-➿️‍⁦-⁩❤]')
SIG = re.compile('❤️?\\s*\U0001F5A4')
BRAND_OPENERS = ('ברוכים הבאים', 'תושבי אריאל', 'אריאלניקים', 'בקרוספיט אריאל,', 'אנחנו קרוספיט')
BIO = r'בביו|בלינק שבביו|דרך הביו|הקישור בביו|פרטים בלינק'
# סימני AI בעברית — אזהרה (מחקר 10.10.26: tropes.fyi + הראל 4.10.26)
AI_CLICHES = ('הסוד', 'מסע', 'משנה חיים', 'משנה את החיים', 'בואו נצלול', 'בואו נדבר על',
              'תדמיינו', 'דמיינו', 'הנה הדבר', 'וזה בדיוק', 'בדיוק בשביל זה', 'ברמה אחרת',
              'קחו את זה איתכם', 'זכרו:', 'השורה התחתונה', 'בסופו של יום', 'פשוט ככה')
NEG_PARALLEL = re.compile(r'(זה|זו|זאת|הוא|היא)\s+לא\s+[^.\n,]{1,40}[,.]\s*(זה|זו|זאת|אלא)\s')
NOT_NOT = re.compile(r'(^|\n|[.])\s*לא\s+[^.\n]{1,25}\.\s*לא\s+[^.\n]{1,25}\.')

STOP = set("""את של על עם זה זו זאת הוא היא הם הן אני אתם אתן אנחנו אתה לא כן גם רק כל
אבל או אם כי כמו יש אין עוד כבר הכי מה מי איך למה כש אז פה שם כאן היה היו להיות יהיה
שלכם שלך שלי שלנו שלו שלה אותו אותה אותם לכם לך לי לנו לו לה בו בה בהם מאוד ממש פשוט
עכשיו אחרי לפני בין תוך עד אחד אחת שני שתי הזה הזאת האלה אלה ואת וזה ולא""".split())
PFX = ('וה', 'שה', 'בה', 'לה', 'מה', 'כש', 'וב', 'ול', 'ומ', 'וש', 'ה', 'ו', 'ב', 'ל', 'מ', 'ש', 'כ')


def norm_tokens(text):
    t = EMO_ANY.sub(' ', text)
    t = re.sub(r'[^\w֐-׿\s]', ' ', t)
    out = []
    for w in t.split():
        w = w.lower()
        if len(w) < 2 or w in STOP:
            continue
        for p in PFX:  # תחילית אחת, רק אם נשאר שורש של 3+ תווים
            if w.startswith(p) and len(w) - len(p) >= 3:
                w = w[len(p):]
                break
        if w not in STOP:
            out.append(w)
    return out


def sentences(text):
    parts = re.split(r'(?<=[.?!])\s+|\n+', text.strip())
    return [p.strip() for p in parts if len(norm_tokens(p)) >= 2]


# ── שכבה 1: lint ───────────────────────────────────────────────────────────
def lint(text, ctype, brand='club'):
    t = text.replace('⁨', '').replace('⁩', '').strip()
    issues, warns = [], []
    if '#' in t: issues.append('האשטג בקפשן (קאנון: אפס האשטגים)')
    if re.search(r'https?://|www\.|\.fit/|\.com', t): issues.append('לינק בקפשן (אינסטגרם: אף פעם לינק)')
    if brand == 'club' and re.search(r'אימון ניסיון|ניסיון חינם|אימון חינם|טריאל', t):
        issues.append('"אימון ניסיון"/"חינם" — אין מוצר כזה; פגישת יעדים')
    if re.search(r'20\s*דק', t) and 'פגישת יעדים' in t:
        issues.append('פגישת יעדים = כ-30 דקות (CANON 1.10.26), לא 20')
    if 'ווטסאפ' in t: issues.append('"ווטסאפ" → "ווצאפ"')
    if re.search(r'\bHERO\b', t): issues.append('HERO → "אימון גיבורים"')
    if 'R.E.L Therapy' in t: issues.append('R.E.L Therapy → "מחלקת שיקום בתנועה"')
    if 'חדר כושר' in t or 'חדר הכושר' in t: issues.append('"חדר כושר" — אנחנו מועדון קרוספיט')
    if '—' in t: issues.append('קו מפריד ארוך (—) — מסגיר AI (הראל 4.10.26). פסיק, נקודה או שורה חדשה')
    if re.search('[؀-ۿ]', t): issues.append('תו ערבי בטקסט עברי')
    if brand == 'club' and re.search('[\U0001FA75\U0001F499]', t):
        issues.append('לב תכלת/כחול בתוכן מועדון — המועדון ❤️🖤 בלבד')
    if brand == 'harel' and SIG.search(t): issues.append('❤️🖤 בתוכן אישי של הראל — אצלו 🩵')
    for line in t.split('\n'):   # "פרטים בביו" כמשפט עומד (rel-cta-psychology §8 כלל 1)
        core = EMO_ANY.sub('', line).strip(' .!')
        if core and re.fullmatch(r'(ה?פרטים|פרטים נוספים|הקישור|לינק)\s*(בביו|בלינק שבביו|בלינק)', core):
            issues.append(f'"{core}" כמשפט עומד — הביו הוא זנב של CTA עם רווח, לא ה-CTA עצמו')
    body = SIG.sub('§', t)
    n_emo = len(EMO.findall(body)) + body.count('§')
    if n_emo > 4: issues.append(f'{n_emo} אימוג\'ים (קאנון: עד 4, ❤️🖤 = חתימה אחת)')
    if re.search(r'(\S)\1\1', ''.join(EMO.findall(t))): warns.append('ערימת אימוג\'י זהה — להחליף במילה')
    blocks = [b.strip() for b in re.split(r'\n\s*\n', t) if b.strip()]
    emo_led = sum(1 for b in blocks[1:] if EMO_ANY.match(b))
    if emo_led >= 2: warns.append(f'{emo_led} פסקאות נפתחות באימוג\'י — אימוג\'י כתבליט מסגיר AI')
    if '!!' in t: warns.append('"!!" — אנרגיה דרך תוכן, לא סימני קריאה')
    for c in AI_CLICHES:
        if c in t: warns.append(f'ביטוי שחוק/AI: "{c}"')
    if NEG_PARALLEL.search(t) or NOT_NOT.search(t):
        warns.append('מבנה "זה לא X, זה Y" / "לא X. לא Y." — סימן AI מובהק; לנסח ישר')
    bio = len(re.findall(BIO, t))
    asks = len(re.findall(r'כתבו|תכתבו|תגיבו|ספרו לנו|תייגו|שמרו|שתפו|שלחו', t))
    if ctype == 'ערך' and bio: warns.append('ערך עם הפניה לביו — ערך מסתיים רך (שמירה/תגובה/תיוג)')
    if ctype == 'המרה' and brand == 'club' and not bio:
        issues.append('המרה בלי "בלינק שבביו 👆" כזנב ה-CTA')
    if ctype == 'המרה' and brand == 'club' and not re.search(r'פגישת יעדים|השאירו פרטים|תשאירו|שלחו לנו הודעה', t):
        warns.append('המרה בלי עוגן "פגישת יעדים"/"השאירו פרטים"')
    if bio + asks > 2: warns.append(f'{bio+asks} קריאות לפעולה — CTA אחד')
    first = t.split('\n')[0]
    if any(first.startswith(o) for o in BRAND_OPENERS):
        warns.append('שורה 1 = הצהרת מותג (VR חציוני 29.7% מול 40.1% לסצנה)')
    words = len(t.split())
    if brand == 'club' and ctype in ('ערך', 'המרה') and not (40 <= words <= 130):
        warns.append(f'{words} מילים (ערך/המרה: 40–130)')
    return issues, warns


# ── שכבה 2: novelty ────────────────────────────────────────────────────────
def novelty(caption, transcript):
    tvocab = set(norm_tokens(transcript))
    sents = sentences(caption)
    body = sents[:-1] if len(sents) > 1 else sents   # המשפט האחרון = CTA, מותר שיחזור
    rows, hit_all, n_all = [], 0, 0
    for s in body:
        toks = norm_tokens(s)
        hit = sum(1 for w in toks if w in tvocab)
        e = hit / len(toks) if toks else 0.0
        hit_all += hit; n_all += len(toks)
        rows.append({'sentence': s, 'echo': round(e, 2),
                     'kind': 'הד' if e >= ECHO_SENT else ('חדש' if e < NOVEL_SENT else 'מעורב')})
    total = hit_all / n_all if n_all else 0.0
    novel = sum(1 for r in rows if r['kind'] == 'חדש')
    issues, warns = [], []
    if not tvocab:
        warns.append('אין תמליל — שער הכפילות לא נמדד (לבדוק בעין: מה הקפשן מוסיף על הסרטון?)')
    else:
        if novel == 0:
            issues.append('אין אף משפט בגוף שמוסיף משהו שלא נשמע בסרטון — הקפשן משכפל את התסריט')
        if total >= ECHO_FAIL:
            issues.append(f'{total:.0%} מהגוף כבר נשמע בסרטון (סף {ECHO_FAIL:.0%} = הרבע הכי משוכפל בארכיון)')
        elif total >= ECHO_WARN:
            warns.append(f'{total:.0%} מהגוף כבר נשמע בסרטון — היעד מתחת ל-{ECHO_WARN:.0%}')
        if rows and rows[0]['kind'] == 'הד':
            warns.append('שורה 1 חוזרת על ההוק של הסרטון — שורה 1 היא הוק שני, מזווית אחרת')
    return {'echo_total': round(total, 2), 'novel_sentences': novel, 'body_sentences': len(rows),
            'rows': rows, 'issues': issues, 'warns': warns}


# ── קלט מפרויקט ────────────────────────────────────────────────────────────
def heard_text(wd):
    """מה שהצופה שומע בפועל: words_final.json (אחרי עריכה), אחרת _whisper_text.txt."""
    p = os.path.join(wd, 'words_final.json')
    if os.path.exists(p):
        try:
            return ' '.join(w.get('word', '') for w in json.load(open(p, encoding='utf-8')))
        except Exception:
            pass
    for name in ('_whisper_text.txt', 'transcript.txt'):
        p = os.path.join(wd, name)
        if os.path.exists(p):
            return open(p, encoding='utf-8').read()
    return ''


def workdir_caption(wd):
    mp = os.path.join(wd, 'project_manifest.json')
    if not os.path.exists(mp):
        return ''
    sa = json.load(open(mp, encoding='utf-8')).get('schedule_approval') or {}
    return sa.get('caption_approved') or sa.get('caption_draft') or ''


def sources(wd):
    """חומר אמיתי שהקפשן יכול להוסיף — כל מה שלא נשמע בסרטון הסופי."""
    heard_txt = heard_text(wd)
    heard = set(norm_tokens(heard_txt))
    hs = sentences(heard_txt)
    out = {'heard_hook': hs[0] if hs else '', 'outtakes': [], 'brief': {}, 'intent': ''}
    raw_p = os.path.join(wd, '_whisper_text.txt')
    if os.path.exists(raw_p) and os.path.exists(os.path.join(wd, 'words_final.json')):
        for s in sentences(open(raw_p, encoding='utf-8').read()):
            toks = norm_tokens(s)
            if toks and sum(1 for w in toks if w in heard) / len(toks) < 0.5:
                out['outtakes'].append(s)
    bp = os.path.join(wd, 'brief.json')
    if os.path.exists(bp):
        b = json.load(open(bp, encoding='utf-8'))
        out['brief'] = {k: b[k] for k in ('audience', 'goal', 'single_cta', 'tone', 'content_type',
                                         'persona', 'department') if k in b}
    ip = os.path.join(wd, 'intent_card.md')
    if os.path.exists(ip):
        out['intent'] = open(ip, encoding='utf-8').read()[:1200]
    return out


def gate(caption, ctype, brand='club', transcript=''):
    li, lw = lint(caption, ctype, brand)
    nv = novelty(caption, transcript)
    issues = li + nv['issues']
    return {'status': 'FAIL' if issues else 'PASS', 'issues': issues,
            'warns': lw + nv['warns'], 'novelty': nv}


def calibrate(root):
    res = []
    for d in sorted(os.listdir(root)):
        wd = os.path.join(root, d)
        if not os.path.isdir(wd) or d.startswith('_'):
            continue
        cap, tr = workdir_caption(wd), heard_text(wd)
        if cap and tr:
            res.append((d, novelty(cap, tr)))
    if len(res) < 4:
        print('מעט מדי פרויקטים לכיול'); return
    tots = [a['echo_total'] for _, a in res]
    q = statistics.quantiles(tots, n=4)
    print(f'n={len(res)} · echo: חציון {statistics.median(tots):.2f} · p25 {q[0]:.2f} · p75 {q[2]:.2f}')
    print(f"בלי משפט חדש: {sum(1 for _, a in res if a['novel_sentences'] == 0)}/{len(res)} · "
          f"שורה 1 הד: {sum(1 for _, a in res if a['rows'] and a['rows'][0]['kind'] == 'הד')}/{len(res)} · "
          f"היו נכשלים בשער: {sum(1 for _, a in res if a['issues'])}/{len(res)}")
    for d, a in res:
        print(f"{'FAIL' if a['issues'] else 'PASS':4} echo={a['echo_total']:.2f} "
              f"חדש={a['novel_sentences']}/{a['body_sentences']}  {d}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--type', default='ערך')
    ap.add_argument('--brand', default='club', choices=('club', 'harel', 'throwdown', 'podcast'))
    ap.add_argument('--transcript'); ap.add_argument('--workdir')
    ap.add_argument('--sources'); ap.add_argument('--calibrate')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    if a.calibrate:
        calibrate(os.path.expanduser(a.calibrate)); return 0
    if a.sources:
        print(json.dumps(sources(os.path.expanduser(a.sources)), ensure_ascii=False, indent=1)); return 0
    if a.workdir:
        wd = os.path.expanduser(a.workdir)
        cap, tr = workdir_caption(wd), heard_text(wd)
    else:
        cap = sys.stdin.read()
        tr = open(os.path.expanduser(a.transcript), encoding='utf-8').read() if a.transcript else ''
    r = gate(cap, a.type, 'club' if a.brand in ('club', 'throwdown') else a.brand, tr)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        nv = r['novelty']
        extra = (f" · הד {nv['echo_total']:.0%} · משפטים חדשים {nv['novel_sentences']}/{nv['body_sentences']}"
                 if tr else '')
        print(r['status'] + extra)
        for row in (nv['rows'] if tr else []):
            print(f"  [{row['kind']} {row['echo']:.0%}] {row['sentence'][:90]}")
        for x in r['issues']: print('✗', x)
        for x in r['warns']: print('⚠', x)
    return 0 if r['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
