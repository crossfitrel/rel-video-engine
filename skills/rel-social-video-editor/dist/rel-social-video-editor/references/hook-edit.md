# rel-social-video-editor · hook-edit
> נגזר מהמאסטר (v10.0 — 2026-10-10) ע"י tools/skill_pack.py — לא לערוך כאן.

# rel-social-video-editor v6 — מקומי מקצה-לקצה, אפס Descript

**גרסה:** v10.0 — 2026-10-10 ("ענן") · **פרויקט:** Social Video Editing System
**קאנון:** `00_META/VIDEO-CANON.md` (v2.2) גובר על הסקיל הזה. פורמט התסריט ו-`⟦EDIT-LAYER⟧` בבעלות `rel-script-writer`.

## ארגז העריכה של ההוק (v9.46, 8.10.26)

**הבקשה (הראל 8.10.26):** "הרעיון של ארגז הכלים הוא לא ברמת התסריט אלא ברמת העריכה שלנו. אפקטים למיניהם, אנימציה שמשתלבת בתוך ההוק, מעברים ויזואליים, צלילים". ⇒ v9.44 בחר **מה** פותח (עוגן); v9.46 קובע **איך העריכה מגבירה אותו**: תנועת מצלמה, מעבר, צליל ואנימציה על הרגע שצולם, בגימור, תחת שערים.

**הכלי:** `tools/hook_fx.py` (מקומי, cv2+ffmpeg, מישורי YUV מקוריים, בלי המרת צבע) + `tools/hook_toolbox.json` (`edit_moves` · `edit_sfx` · `edit_recipes` · `edit_rules`, ו-`edit_recipes` לכל שורת תוכן) + צלילים `tools/motion/sfx/hook/` (16, Mixkit Free License, יבוא: `hook_sfx_import.py`).

**8 תנועות:** `snap_zoom` (ease-out-expo, החזקה, יציאה/חיתוך חזרה) · `push_in` (מתח עד העוגן) · `shake` (מגע) · `impact_freeze` (עצירה בשיא; punch=1 ⇒ אפשר טלסטרייטור מעליו) · `speed_ramp` (האטה ותפיסה, S(a)=a S(b)=b) · `whip` · `zoom_through` · `flash` (שלושת המעברים רק על חיתוך). מושן-בלר אמיתי, cover() אוטומטי (אין שוליים), focus:"face" מגלאי הפנים של motion_build.
**סאונד:** impact · swish · zoom · riser (מיושר לסוף) · rewind · scratch · shutter — כל צליל ביחס ל-LUFS של הדיבור, וריאציה מסובבת לפי seed; `music_drop` = המצע נעלם עד/בזמן הרגע (`audio_mix.py --mute`); `boost_orig` = סאונד אמיתי בחזית.

**12 מתכונים** (טבלה מלאה: `docs/ארגז-עריכת-הוק-v9.46.md`): reaction_punch · action_ramp_freeze · action_whip · push_tension · dramatic_zoom · scratch_freeze · object_spotlight (MG) · then_now_split (MG) · anatomy_freeze_draw (פריז+טלסטרייטור) · cold_open_flash · number_stat_hit (MG stat) · diegetic_boost.

**כלל הבחירה:** מתכון אחד לריל, רק על העוגן שהוצהר (t0-t2) · לכל היותר 2 תנועות ו-3 צלילים ב-0-4ש · משנה-זמן רק בלי דיבור · מעבר רק על חיתוך · פנים שממלאות פריים: scale עד 1.12 · אין רגע ברמה גבוהה ⇒ `edit:{recipe:"none", why}` (רגע בינוני גרוע מאפס).

**השלב (חלק משלב 2.5):**
```
hook_plan.py init --workdir W            # מציע גם edit_recipes לשורה
# הבמאי מוסיף ל-W/HOOK_PLAN.json: "edit": {"recipe", "moves":[...], "sfx":[...], "music_drop":[[a,b]]}
#   זמנים על ציר EXPORT (= ציר הגימור; השכבה שומרת ציר ⇒ words_final לא משתנים)
hook_fx.py check --workdir W --base W/EXPORT.mp4     # HFX1-HFX6, HFX10 לפני רינדור
hook_fx.py demo --src W/EXPORT.mp4 --plan p.json --out D --secs 6   # לפני/אחרי מהיר + compare.mp4
local_finish_pipeline.py … --hook-fx auto            # ברירת מחדל: רץ כשיש בלוק edit · on = חובה · off
# Read על W/HOOK_FX_SHEET.jpg (לפני/אחרי כל 0.2ש + גל קול + סימוני צליל/תנועה) לפני הצגה
```
**בצנרת:** שלב `hook_fx` (5.55) אחרי בירול/פתיח קבוע ולפני MG ⇒ MG וכתוביות לא זזים עם הזום. מנוע v2 (כתוביות צרובות) ⇒ רק סאונד. Visual Hook (punch-in) שהוחל ⇒ HFX10 חוסם זום נוסף.
**שערים:** HFX1 חלון · HFX2 מינון · HFX3 דיבור · HFX4 תקינות · HFX5 פנים · HFX6 עוגן חיתוך · HFX10 התנגשות MG/punch-in — לפני רינדור (HFX4b טווחי LIM מדווח בלבד עד כיול E16); HFX8 אורך · HFX8b יישור פריימים (L127) · HFX9 צבע — אחרי. חסימה = השכבה לא מוחלת, לא עצירת צינור (ב-auto). **P22** (preflight): edit מוצהר שלא בתוצר / דוח של תוכנית אחרת = high; אין בלוק edit בכלל = medium.
**דמואים (8.10.26):** HSPU (push_tension + snap למאמן) ✅ · משימות (dramatic_zoom על אוריה) ✅ · פודיום (reaction_punch על שיילי) ❌ נפסל ("בסרטון של שיילי זה לא מתאים שם האפקט הזה") — פסיקות ב-`tools/hook_fx_verdicts.json`, P22 חוסם מתכון שנפסל באותו סרטון, reaction_punch לא ראשון באף שורה עד דמו מאושר — `תוצרי-אנימציה/ארגז עריכת הוק/`. לקחים: L126-L127. ניסוי E16.
