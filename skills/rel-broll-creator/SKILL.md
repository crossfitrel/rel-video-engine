---
name: rel-broll-creator
description: >-
  **מפעל הבירולים + הקטלוג — CrossFit R.E.L (v2)**: מייצר בירולים מחומר גלם ומנהל את
  ספריית הבירולים המקוטלגת (catalog.json — תגים, קהלים, משכים, תמונות-מגע, rotation).
  ארבעה מצבים: (א) סרטון ארוך → scene-detect + contact sheet + חיתוך; (ב) קטעים קצרים →
  פורמט/צירוף לבירול; (ג) גלם מצלם מקצועי (ZIP) → גריידינג-רפרנס + מיון + חיתוך 2.5-3ש;
  (ד) קטלוג — סריקה, תיוג, בחירה דטרמיניסטית (broll_pick) ושיבוץ. כל הבירולים: אנכי
  1080×1920, מושתק, "בירול" בשם. TRIGGERS — "תייצר בירולים", "בירולים מהסרטון", "תחתוך
  בירולים", "עוד בירולים", "ספריית בירולים", "קטלוג בירולים", "תבחר בירול", "רענן קטלוג",
  "חומר גלם ממצלם", "create b-rolls", "broll catalog". לא להפעיל על שילוב בירול בעריכת
  סרטון — לזה rel-social-video-editor (שקורא ל-broll_pick מכאן).
metadata:
  project: Social Video Editing System
  version: v2.0
  updated: 2026-07-16
---

# rel-broll-creator v2 — מפעל + קטלוג


## ⚠️ גבול מול המחשה ויזואלית (v9.20, 21.8.26)

בירול = **צילום אמיתי מהקטלוג**. המחשה ויזואלית = **איור של משהו שאי אפשר
לצלם** (מבנה פנימי, מנגנון, יחס מספרי, תהליך). שני דברים שונים, שני צינורות.

**רעיון ויזואלי אחד בכל רגע:** המחשה שחופפת לשיבוץ בירול נענשת ומדווחת (IL6).
ההחלטה מי גובר היא של `illustration_gate.py`, לא של הבחירה כאן.

## תפיסת על
בירול = קליפ 2-6ש, אנכי, **מושתק**, של רגע אמיתי מהמועדון. v2 מוסיף את **הקטלוג**: כל בירול מוכן
נרשם ב-`catalog.json` עם תגים/קהל/משך/תמונת-מגע, והבחירה לעריכות הופכת לחיפוש דטרמיניסטי
(`broll_pick.py`) עם rotation — לא ניחוש לפי שם קובץ.

## מקורות אמת
- **ספרייה קנונית (מוכנים):** `{CONTENT_ROOT}/בירולים/` (כולל `Throwdown 2025/`) + `Social Video Editing System/בירולים - מיכאל לוי 28.5/` (סבב 3 מורחב + דוספיט; סבבים 1-2 = גרסאות ישנות, מוחרגות בקונפיג).
- **קטלוג:** `{CONTENT_ROOT}/בירולים/catalog.json` + `catalog.html` (צפייה) + `_catalog_thumbs/`. קונפיג: `tools/broll-catalog-config.json` (roots, החרגות, topic_tag_map, usage_path).
- **Backlog גלם (לא בקטלוג):** ‎~60 קליפי `IMG_*.mov` ב-`בירולים/` המקומית + Drive "בירולים" (1P-Sh66yR46zFVF8emCYhXwhtd0G5L6oD, כולל תת-תיקיית "שיקום בתנועה") + תיקיות הצלם (hayonhq). **Drive "בירולים מוכנים" (1udy2p...) ריקה — הספרייה האמיתית מקומית** (אומת 16.7.26).
- Descript Media Library "בירולים" — נוחות בלבד; הקנוני הוא הדיסק.

## ברירות מחדל מותגיות (הראל 22.6 — לא לשנות בלי בקשה)
אנכי 1080×1920 **blur-fill** (לא מאבד פריים) · אודיו `-an` תמיד · libx264 crf 20 veryfast +faststart ·
שם: `בירול {אירוע} - {NN} {תיאור}.mp4` · מספור רציף בין באצ'ים · `--mode crop` רק לשוט אקשן ממורכז ·
`--mode horizontal` רק לפי בקשה · **אסור לגעת בצבע** (חוק ברזל) אלא בגלם HLG/מצלם עם רפרנס מדוד.

## הכלים
| כלי | תפקיד |
|---|---|
| `tools/broll_catalog.py scan` | סריקת roots → catalog.json + thumbs + catalog.html; מדווח כפילויות-שם |
| `tools/broll_catalog.py list --tag X --audience Y` | שאילתת קטלוג מהירה |
| `tools/broll_pick.py` | בחירה+שיבוץ דטרמיניסטיים → broll_plan.json (+`--commit` ל-usage) |
| `scripts/broll_scan.py` | מצב A: scene-detect + contact sheet + candidates.json |
| `scripts/broll_make.py cut/format/stitch` | יצירת הבירולים |
| `scripts/broll_sheet.py` | contact sheet של תוצרים — אימות ויזואלי |

## מצב ד — קטלוג ובחירה (החדש ב-v2)
```
רענון:   python3 tools/broll_catalog.py scan            # אחרי כל הוספה; וגם שבועית (scheduled task)
בחירה:   python3 tools/broll_pick.py --topic "{נושא}" --content-type conversion \
           --audience "{דוספיט/נשים/…}" --dept "{מחלקה}" --n 2 \
           --sentences sentences.json --video-dur {dur} --json broll_plan.json --commit
```
הכלי אוכף לבד: conversion בלבד (חריג Throwdown-ערך: `--content-type throwdown_value --allow-throwdown-value`) ·
דוספיט→בירולי דוספיט בלבד + מגדר · התחלה אחרי סוף המשפט הראשון (ברירת מחדל 6ש) · 8ש אחרונות נקיות (CTA-guard) ·
mute · חיתוך אמצע-הקליפ כשארוך · גיוון תיאורים (לא שני "הרמה מול קהל") · קנס שימוש-אחרון (usage.json).
**תיוג ידני:** `tools/broll-tags-override.json` — `{"<id או שם קובץ>": {"tags": [...], "audience": [...]}}`.
**נושא חדש?** להרחיב את `topic_tag_map` בקונפיג — לא לקודד בסקריפט.
**שילוב בעריכה (אוטומטי מ-23.7.26):** `local_finish_pipeline.py` מריץ בעצמו את `broll_pick.py` ואת `animation_overlay.py` על ה-EXPORT הנקי כשה-content_type הוא conversion — אין יותר צורך להריץ את שני הכלים האלה ידנית לפני הגימור. `broll_plan.json` שנוצר כאן ידנית (למשל שיבוץ מותאם-אישית לפי הערת הראל) פשוט מונח בתיקיית `_work/{שם}/` והפייפליין יזהה וישתמש בו אוטומטית (עדיפות ראשונה, לפני ההרצה האוטומטית). `overlay_args` בפלט הוא **רשימת argv**, לא מחרוזת shell — `animation_overlay.py --base EXPORT.mp4` מקבל אותה ישירות כ-subprocess args (לא דרך shell, לא דרך ה-agent של Descript). תמיד לשמור EXPORT טרום-בירול.

## מצב א — סרטון ארוך → בירולים
```
1. python3 scripts/broll_scan.py --video "{גלם}" --out "{OUTDIR}" --min-dur 2.0 [--exclude {starts שכבר נוצלו}]
2. בחירה ויזואלית (חובה): קרא את contact_NN.jpg בנתיב host. אריחים row-major = #0,#1,...
   ✅ אקשן/הרמות/ריג, אינטנסיביות, קהל/קהילה, ספורטאים מגוונים · ❌ לוגו/מעברים מרוחים/חשוך/כפילויות. פיזור על פני הסרטון.
3. plan.json: [{"num":15,"start":29.7,"dur":2.3,"desc":"הרמה מעל הראש"}, ...]  (טיפ: start+0.1, dur-0.2 נגד פריימים של חתך)
   python3 scripts/broll_make.py cut --video "{גלם}" --plan plan.json --dest "{CONTENT_ROOT}/בירולים/{אירוע}" --event "{אירוע}"
4. python3 scripts/broll_sheet.py --dir "{DEST}" --out verify.jpg  → לקרוא ולאשר ויזואלית.
   תיאורים בשמות = best-guess מהפריים האמצעי — תיאור שגוי מתקנים/מדווחים. עדיף מעורפל-נכון מספציפי-שגוי.
5. python3 tools/broll_catalog.py scan   ← חובה בסוף כל מצב!
```

## מצב ב — קטעים קצרים → בירולים
`broll_make.py format --clips a.mov b.mov --dest ... --event ... --start-num {N}` (או `stitch --num {N} --desc "רצף"`).
אימות sheet + `broll_catalog.py scan` בסוף.

## מצב ג — גלם מצלם מקצועי (ZIP)
לפי לקחי סבב מיכאל לוי (28.5): unzip **לדיסק** (לא לזיכרון) → גריידינג מותאם-רפרנס **מדוד מספרית**
(לא ניחוש; אישור צבע על קליפ אחד מול הראל לפני כל הסבב) → סריקה ומיון לקטגוריות (נושא+קהל+שירות) →
חיתוך "אמצע-הקליפ" 2.5-3ש (offset ‎-1ש) → שם עם קטגוריה → sheet → scan. לא דוחפים קליפים חלשים
כדי להגיע למכסה — מדווחים פער תוכן. בירולי-סטילס (Ken Burns): לרנדר 2160×3840 ואז scale ל-1080×1920
(supersample נגד רעד), `-framerate 30 -loop 1` בקלט.

## סביבת ריצה
- **סנדבוקס מועדף** ליצירה (ffmpeg מלא). באצ' גדול חורג מ-45ש → פצל ~7, או חתוך ל-`/tmp` ואז `cp` ליעד.
- iCloud מהסנדבוקס: יצירה/העתקה ✓, מחיקה/שינוי-שם ✗ → Desktop Commander על נתיב המק.
- **קטלוג scan רץ על המק** (roots מחוץ ל-mount). ריצה ראשונה אחרי הוספת קבצי ענן איטית (הורדת iCloud) — ריצות המשך מהירות.
- contact sheets נקראים בנתיב host (Read רץ על ה-host, לא `/sessions/...`). ffmpeg של Homebrew חסר drawtext — מיפוי position→index, לא תוויות צרובות.

## צ'קליסט סיום
```
[ ] בחירה ויזואלית מה-sheet (לא עיוור) · [ ] אנכי 1080×1920 מושתק · [ ] "בירול"+אירוע+מספר בשם
[ ] נשמר לספרייה הקנונית · [ ] verify.jpg אושר · [ ] גיוון תוכן · [ ] catalog scan רץ והקליפים בפנים
[ ] כפילויות-שם שהודפסו טופלו
```

## גרסה
v2.0 — 16.7.2026 (קטלוג + בחירה דטרמיניסטית + rotation + מצב מצלם). קודמת: `SKILL-v1.0-archive.md`.
