---
name: rel-podcast-descript-editor
description: >-
  **עריכת פרק פודקאסט "מדברים כושר" בדיסקריפט — CrossFit R.E.L**: מערכת לעריכת פרק
  פודקאסט מלא ב-Descript עם משימה אחת בלבד — הסרת Fillers (מילות מילוי/היסוס).
  אסור לגעת בשום דבר אחר בפרק: לא לחתוך משפטים, לא להסיר שתיקות, לא Studio Sound,
  לא כתוביות, לא לסדר מחדש. שומר על הפתיח הקבוע (מחיאת כף + "ברוכים הבאים לפודקאסט
  מדברים כושר"), מטפל בקבצי 4K כבדים (טרנסקוד מקומי לפני העלאה), ומפיק Timestamps
  ליוטיוב מהתמלול. MANDATORY TRIGGERS — "ערוך פרק פודקאסט", "עריכת פודקאסט בדיסקריפט",
  "תוריד fillers מהפרק", "הסר מילות מילוי", "פרק מדברים כושר לעריכה", "timestamps
  לפרק", "edit podcast episode", "remove fillers", "podcast descript edit". להפעיל
  בכל פעם שיש פרק פודקאסט גולמי לעריכה ב-Descript. לא להפעיל על עריכת ריילס/סושיאל
  (→ rel-social-video-editor), כתיבת תסריט (→ medabrim-kosher-scriptwriter), או
  show-notes (→ medabrim-kosher-show-notes).
---

# עריכת פרק פודקאסט "מדברים כושר" בדיסקריפט

## 🎯 מטרה אחת — ואין בלתה

**להסיר Fillers בלבד. שום דבר אחר.** זו עריכה מינימליסטית: הפרק יוצא כמעט זהה
לקלטת הגלם, רק בלי מילות ההיסוס. הראל אומר במפורש: *"אני לא רוצה שהוא ישנה שום דבר
בפרק. צריך אך ורק להוריד Fillers."*

### ⛔ אסור בתכלית האיסור (Hard NO)
- ❌ לא להסיר שתיקות / פאוזות (זה פודקאסט, לא ריל — פאוזות = קצב טבעי)
- ❌ לא לחתוך משפטים, חזרות, "התחלות כושלות", או תוכן כלשהו
- ❌ לא לסדר מחדש / להזיז מקטעים
- ❌ לא Studio Sound / denoise / נרמול אודיו (שורף קרדיטים + משנה את הסאונד)
- ❌ לא כתוביות, לא B-roll, לא טקסט גרפי, לא מוזיקה
- ❌ לא לחתוך את מחיאת הכף בפתיחה ואת "ברוכים הבאים" (ראה למטה)

### ✅ הדבר היחיד שמותר
- ✅ הסרת מילות מילוי לא-לקסיקליות והיסוסים בלבד

---

## 🔒 כלל הפתיחה הקדושה
כל פרק נפתח ב**מחיאת כף חזקה של הראל** (מזוהה לפי peak סאונד חזק בשנייה הראשונה),
ומיד אחריה: **"ברוכים הבאים לפודקאסט מדברים כושר"**.
- **אסור** שהסוכן יחתוך את מחיאת הכף (יכול לטעות ולחשוב שזה רעש/filler)
- **אסור** לגעת במשפט הפתיחה
- בפרומפט לסוכן — להגן על 10 השניות הראשונות במפורש

---

## 📋 רשימת ה-Fillers (שמרני בכוונה)
ברירת מחדל **שמרנית** — מסירים רק היסוסים ברורים, לא מילות תוכן.

**להסיר (היסוסים לא-לקסיקליים + טיקים ברורים):**
`אהה`, `אה`, `אמ`, `אהמ`, `המ`, `אֶה`, `eh`, `um`, `uh`

**להסיר רק כשברור שזה טיק (לא נושא משפט):**
`יעני`, `כאילו` (כשהוא מילת מילוי ולא חלק מהמשמעות)

**אסור להסיר (מילות תוכן — גם אם נשמעות כמו filler):**
`בעצם`, `סוג של`, `אתה יודע`, `טוב`, `אוקיי`, `נכון`, `זאת אומרת` — אלה לרוב נושאים
משמעות בעברית מדוברת. במקרה ספק — **להשאיר**.

> עדיף להחמיץ filler אחד מאשר לחתוך מילת תוכן. הראל מעדיף עריכה שמרנית.

---

## 🛠️ הצינור המלא (Pipeline)

### שלב 0 — קליטת הגלם
- קובצי פודקאסט מצולמים ב-4K HEVC — **כבדים מאוד** (פרק 19 דק' ≈ 4–5GB).
- **אסור להעלות ישירות מהסנדבוקס** (egress ~200KB/s — ייקח שעות).

### שלב 1 — Remux נקי ל-4K (Desktop Commander על המאק) — ⚠️ לא לרדת ל-1080p!
**פודקאסט תמיד נעלה ב-4K** (הראל 29.6). אסור downscale. עושים **remux** שמעתיק את
הזרמים כמו שהם (בלי re-encode, בלי איבוד איכות) ורק מוריד data-tracks בעייתיים
מה-.MOV של האייפון:
```bash
ffmpeg -y -i "<INPUT.MOV>" -map 0:v:0 -map 0:a:0 \
  -c:v copy -c:a copy -movflags +faststart \
  "$HOME/rel-podcast-work/<NAME>_4k.mp4"
```
- מהיר מאוד (העתקה, לא קידוד) — שניות.
- שומר 4K HEVC מקורי + אודיו מקורי. Descript תומך ב-HEVC/4K.
- אם Descript דוחה HEVC — fallback: re-encode 4K ב-`hevc_videotoolbox -b:v 30M`
  (עדיין 4K!), אף פעם לא scale ל-1080p.
- מריצים ברקע עם `nohup ... &` (תהליך רקע על המאק שורד; של הסנדבוקס לא).
- מאמתים `duration` + `width=3840` של הפלט = של המקור.

### שלב 2 — העלאה ל-Descript
- `import_media` עם **direct upload** (`content_type`+`file_size`) → מקבלים `upload_url`.
- מבצעים את ה-PUT **מהמאק** דרך Desktop Commander (`curl` ברקע), לא מהסנדבוקס:
  ```bash
  curl -s -X PUT -H "Content-Type: application/octet-stream" \
    --data-binary @"<FILE>" "<upload_url>"
  ```
- שם פרויקט: `מדברים כושר — פרק NN`.
- `wait_for_job` עד שהייבוא+תמלול מסתיימים. `language: "he"` בייבוא.
- **אם הייבוא נכשל ("Import failed" / media `type:"other"`):** לפני שמאשימים את הקובץ —
  לאבחן אם זו תקלת backend של Descript. בדיקה מהירה: לחתוך קליפ 30ש
  (`ffmpeg -t 30 -c copy test30.mp4`), להעלות ולייבא. אם **גם הקליפ הזעיר נכשל**
  → ה-import של Descript שבור בצד השרת (קרה 29.6, יום שלם) — להמתין שיתאוששו,
  לא לבזבז זמן על re-encode. אם הקליפ עובר אבל הפרק לא → אז זו בעיית גודל/אורך.

### שלב 3 — תמלול בסיס (לפני העריכה)
- `get_project` → לאמת duration + composition_id.
- `export_transcript` (txt) → שומרים כ**baseline** להשוואה אחרי.

### שלב 4 — הסרת Fillers בלבד (`prompt_project_agent`)
פרומפט ממוקד וחד (עברית+אנגלית כדי לא להשאיר מקום לפרשנות):

> Remove ONLY filler words and hesitation sounds from this Hebrew podcast.
> Filler words to remove: אהה, אה, אמ, אהמ, המ, um, uh — and יעני / כאילו ONLY
> when used as a verbal tic. Do NOT remove any meaningful words. Do NOT remove
> silences or pauses. Do NOT cut any complete sentences, repetitions, or content.
> Do NOT rearrange anything. Do NOT add captions, music, or effects. Do NOT apply
> Studio Sound. PROTECT the first 10 seconds completely (opening clap + welcome
> line) — never cut them. This is the only edit: filler removal, nothing else.

- `wait_for_job`.
- **קרדיטים:** פעולת agent אחת בלבד לפרק. אסור Studio Sound / פעולות AI נוספות.

### שלב 5 — אימות (חובה — Descript Agent over-cuts)
הסוכן של Descript נוטה לחתוך יותר מהמבוקש. **חייבים** לאמת:
1. `get_project` → `duration` אחרי. ירידה צפויה: **קטנה מאוד** (שניות בודדות עד
   ~דקה לפרק ארוך). ירידה של דקות רבות = הוא חתך תוכן → לחזור/לתקן.
2. `export_transcript` אחרי → **diff מול baseline**. לוודא שנעלמו רק fillers,
   לא משפטים שלמים.
3. לאמת שהפתיח ("ברוכים הבאים...") שלם.
- אם נחתך תוכן → `conversation_id` + פרומפט מתקן, או undo ידני.

### שלב 6 — Timestamps ליוטיוב
מהתמלול הסופי:
```
export_transcript(format=txt, timecodes={on_paragraphs:true}, include_speaker_labels="changes")
```
- מקבצים פסקאות ל**פרקי נושא** (chapters), לא כל פסקה.
- פורמט יוטיוב — חייב להתחיל ב-`0:00`:
  ```
  0:00 פתיחה — ברוכים הבאים
  X:XX [נושא 1]
  X:XX [נושא 2]
  ...
  ```
- כותרות פרק קצרות וקולעות (3–6 מילים), בקול הפודקאסט.
- מוסרים להראל להדבקה בתיאור היוטיוב / show-notes.

### שלב 7 — ייצוא הפרק
- ייצוא דרך Descript (download_url) או הראל מוריד מהפרויקט.
- **לא** `publish_project` אוטומטי — הראל לוקח לגימור/העלאה ידנית.

---

## 🎬 פתיח / סגיר קבועים (אופציונלי — ברירת מחדל: כבוי)
לכל פרק יש פתיח וסגיר קבועים שכבר נמצאים ב-Media Library של Descript:
`folder = 06695b24-4cd4-421c-96da-cd30873f3bb4`.

- **ברירת מחדל בעריכה הזו: לא להוסיף אותם** (הראל ביקש "רק fillers, שום דבר אחר").
- אם הראל מבקש במפורש להוסיף — לשרשר אותם כקליפ נפרד בתחילת/סוף ה-composition,
  בלי לגעת בגוף הפרק.

---

## ✅ Definition of Done
- [ ] Remux 4K אומת (duration = מקור, width=3840 נשמר — לא 1080p!)
- [ ] הועלה ל-Descript, תמלול הושלם
- [ ] baseline transcript נשמר
- [ ] הוסרו fillers בלבד (agent op אחת)
- [ ] אימות duration + diff transcript → לא נחתך תוכן
- [ ] הפתיח (מחיאת כף + "ברוכים הבאים") שלם
- [ ] Timestamps ליוטיוב הופקו, מתחילים ב-0:00
- [ ] לא הופעל Studio Sound / פעולת AI מיותרת (קרדיטים)

---
*v1 — 2026-06-29. ייווצר אחרי ניסיון פרק 55; לחדד לפי פידבק הראל.*
