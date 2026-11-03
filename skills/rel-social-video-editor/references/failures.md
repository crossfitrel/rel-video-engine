# rel-social-video-editor · failures
> נגזר מהמאסטר (v9.40 — 2026-10-04) ע"י tools/skill_pack.py — לא לערוך כאן.

## טיפול בכשלים
| כשל | פעולה |
|---|---|
| אין גלם matched | `[INTAKE MISSING]` + דלג |
| whisper נכשל במק | model=base; שוב → `transcript_to_words.py` fallback מסומן |
| edl_cut נכשל | בדיקת edl.json (keep_segments ריק?) + תיקון; אין fallback ל-Descript אוטומטי |
| gate שקט נכשל | חזרה לאפליקציית הרוויו עם הטיימקודים (gate_fail.json). לא Descript |
| pipeline נכשל פעמיים על אותו פריט | דיווח להראל + הצעת `[DESCRIPT FALLBACK]` באישורו בלבד |
| שרת הרוויו לא רץ | מ-18.8.26 LaunchAgent `com.rel.review-app` מרים אותו בהדלקה ואחרי קריסה. בדיקה: `launchctl list \| grep rel.review`; החייאה: `launchctl kickstart -k gui/$(id -u)/com.rel.review-app`. לוג: `~/Library/Logs/rel-review-app.log` |
| מייל (כשנדרש בכלל — כשל שדורש את הראל) נכשל | `[EMAIL FAILED]` + דיווח בצ'אט; לא חוסם עדכון Monday |
| Metricool נכשל | `[SCHEDULE FAILED] {error}`, בלי עדכון סטטוס, בלי כפילות |
| artifact_id לא עובר verify ברגע התזמון (v7.2/v9.4) | לא לתזמן. `[STALE-FINAL — יש לאשר קאבר+קפשן מחדש]`; להראל: הגרסה המאושרת נעלמה/נפגמה |
| אימות אחרי תזמון נכשל (v9.31 — `getScheduledPosts` לא מחזיר את הפוסט/השדות) | `[SCHEDULE VERIFY FAILED]`; לא לסמן "תוזמן!" ב-Monday; מייל להראל רק אם התיקון דורש אותו (`rel-email-design`) |
| אין `⟦SCRIPT` על הפריט (v9.21) | לא לעצור — לעבוד ב-`[INFERRED-INTENT]`, לסמן זאת ב-`⟦EDITPLAN⟧` ובדיווח, ולבחור ⬛COVER⬛ בצינור |
| ⟦SHOOT⟧ תוכנן ולא צולם (v9.21) | `shot_debt` + שורה בטבלת הפער + הודעה מפורשת להראל. **אסור** לפצות בהעלאת צפיפות חיתוכים |

## ערוץ ידני
"ערוך את הסרטון של X" → פריט בודד מלא · "תרוץ על מה שמוכן" → batch≤3 · "dry run על X" → שלבים 0-3 (edl+intent כ-Update) · "תזמן את X" → שלב 7 בלבד · "מה הראל תיקן" → learn_from_edits + דוח.

## L166 (3.11.26) — ג'ובים "בתור" שלא זזים אף פעם
- `dispatch.ok=true` (204) **לא** אומר שהריצה התחילה. GitHub מחזיר 204 גם כשהחשבון חסום, והריצה מתה ב-3-5 שניות בלי לוג ("recent account payments have failed or your spending limit needs to be increased").
- בדיקה: `gh run list -R crossfitrel/rel-video-cloud -L 5` + `gh run view <id>` (ה-annotation). ב-1-2.11.26 נשרפו 1,984 דקות (מכסת 2,000 החינמית של החודש) ב-77 ריצות.
- תיקון קבוע: אמצעי תשלום + budget ל-Actions בחשבון crossfitrel (github.com/settings/billing). בקוד: `selfHeal()` בפונקציית video (באנר `actions:blocked` + שליחה חוזרת אוטומטית בטעינת העמוד), ובאנר `cost_cap` שמתאפס ביום חדש.

## L167-L169 (3.11.26) — נפילות בין הכיסאות
- L167: ריל שסומן "מוכן לעריכה" לא הופיע בעמוד עד שה-prep רץ ⇒ טריגר `trg_prep_placeholder` יוצר שורת "בהכנה" עם יצירת הג'וב. גלם חסר = כשל גלוי (קודם skipped שנדרס ל-done בשקט).
- L168: notes שהוסלם ⇒ ה-action לא נצרך ⇒ "הערות נשלחו" לנצח ⇒ טריגר `trg_consume_actions_on_review` סוגר לחיצות ישנות כשהפרויקט חוזר ל-review.
- L169 (פתוח): שתי טעינות עמוד במקביל ⇒ dispatch כפול ⇒ הריצה הראשונה נופלת על unauthorized אחרי ~6 דק'. התיקון (UPDATE אטומי ב-selfHeal) מחכה לפריסת הפונקציה. נפתר לבד (הריצה השנייה לוקחת), רק מבזבז דקות.
- ג'וב שתקוע בתור בלי סשן: `update video.jobs set status='deferred' where id=…` ואז אותה קריאת `resume` שה-cron `video-resume` מריץ (net.http_post) ⇒ נשלח מחדש.
- L170: הסלמות לא נותבו מאז L165 (טוקן ה-worker פג ב-job_done לפני ה-enqueue) ⇒ ריל "אצל הקלאוד" לנצח. הניתוב עבר לטריגר `trg_route_escalation` (redispatch דרך pg_net). 3 סבבים אוטומטיים, אחר כך runner=claude.
- L171: 6 קליפים בקטלוג בלי קובץ בענף libs ⇒ canon `broll_files_exist` HARD_FAIL אחרי גימור מלא. `broll_pick` מסנן קליפים שאין להם קובץ.
- L172: אחרי 3 סבבים שנפלו רק על preflight_not_ready ויש סרטון ⇒ חוזר להראל (state=review, extra.preflight_open_after_rounds). כשל אמיתי ⇒ runner=claude. הממצאים שחוזרים בלולאה (G1b אורך מחוץ ליעד, "FINAL השתנה אחרי שההוק נבדק", "עיגון בירול: אין פסיקה") הם ממצאי צנרת ולא איכות, ומועמדים להורדה ל-MED.
- L173: redispatch מתוך טריגר נכשל לפעמים על timeout של pg_net ⇒ dispatch=null ⇒ אבוד. ג'וב שנוצר בטריגר מסומן מראש dispatch.ok/at-31דק', כך ש-selfHeal בטעינת עמוד תופס אותו. cron רשת-ביטחון (video-kick כל 10 דק') נחסם בשכבת ההרשאות ולא הוקם.
