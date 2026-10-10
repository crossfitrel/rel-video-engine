# rel-social-video-editor · visual-hook
> נגזר מהמאסטר (v9.40 — 2026-10-04) ע"י tools/skill_pack.py — לא לערוך כאן.

## פתיחה חזותית — Visual Hook Engine (v9.22, 11.9.26)

> **Visual Hook Engine:** optional and local-first; `--visual-hook off|shadow|auto`, with old projects defaulting to off. Current recipes are NO_OP and SMART_PUNCH_IN. NO_OP is a successful editorial decision, especially for existing motion, protected entrances, multiple people or uncertain crop safety. The engine changes picture only: never speech, EDL, duration, captions, music or publishing rules. Analysis binds the resolved final-body export and transcript provenance; the same approved plan must render in v1, v2 and fallback. No additional graphic text, generated humans, fake gym footage or automatic opening B-roll is authorized. A later PAYOFF_PREVIEW release requires a separate explicit canon exception. Review uses the existing app approval and immutable artifact checksum. Report preflight's verdict when saying a candidate is ready for Harel; unresolved high findings remain explicit. Every implemented lesson needs a registered enforcer.

**סטטוס:** פיילוט — הראל אישר את שתי דוגמאות ההשוואה (11.9.26: מי-אמר-שמאוחר-מידיי ×1.04, סקאלת-הבריאות ×1.06). ברירת מחדל `off`; `auto_cohorts` ריק ⇒ `auto` נפתר ל-NO_OP. אין הפעלה גורפת בלי קוהורט+מעטפת שהראל אישר במפורש.

**איך משתמשים (פר-פרויקט, רק מהאפליקציה):** חלון האישור ← שורת "🎬 פתיחה חזותית" ← *לאפשר הצעה* (shadow) ← *הכן תצוגה* (job מסוג `hook_preview` תחת אותה נעילה, בלי FINAL ובלי artifact) ← *השוואה* ← אישור. האישור קושר `visual_hook_plan_digest` טרי שנצפה; עריכה אחרי התצוגה ⇒ `HOOK_REVIEW_STALE` והגימור עוצר (הגרסה המאושרת הקודמת נשמרת). אבחון מבודד: `python3 tools/visual_hook.py analyze|plan|preview|validate|prepare-review <workdir>`.

**למה רוב הסרטונים יוצאים NO_OP (סריקה של 38, 11.9.26 — 2 זכאים):** תנועת מצלמה/פריים קיימת, כמה אנשים, כניסה מכוונת, קאט או בירול בחלון, פתיח קבוע, ומסגרת שלא מכילה ראש+מעטפת תנועה. זו התוצאה הנכונה ולא באג. הספים ב-`tools/visual_hook_policy.json` מסומנים `calibrated:false` — משנים אותם רק מדוגמאות כיול שהראל פסק עליהן (`handoff/visual-hook-engine/comparisons/כיול/`), לעולם לא כדי "להגדיל כיסוי".

**אסור:** לגעת ב-EXPORT; להניח ש-v2 משתמש ב-EXPORT מתוקן (v2 מקמפל את התוכנית פר-סגמנט); `-frames:v` ברינדור v1 מלא (קוטע את זנב האודיו — `HOOK_AUDIO_CHANGED`); E2E שלא על עותק עם `REL_BROLL_USAGE_COMMIT=0` (דולף ל-`בירולים/usage.json`). לקחים L56-L58, שערים G8b + VH1-VH8 + P16.
