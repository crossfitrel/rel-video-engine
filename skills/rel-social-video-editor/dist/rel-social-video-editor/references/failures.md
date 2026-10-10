# rel-social-video-editor · failures
> נגזר מהמאסטר (v10.0 — 2026-10-10) ע"י tools/skill_pack.py — לא לערוך כאן.

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
