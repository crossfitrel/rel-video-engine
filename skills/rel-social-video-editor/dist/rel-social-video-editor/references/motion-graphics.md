# rel-social-video-editor · motion-graphics
> נגזר מהמאסטר (v11.0 — 2026-10-29) ע"י tools/skill_pack.py — לא לערוך כאן.

## שכבת Motion Graphics (v9.37, 4.10.26)

**הבקשה (הראל 4.10.26):** MG "חלק בלתי נפרד" מהעריכה — בכל סרטון שיש בו קטעים שמרוויחים ממנו, **רק ברמה מאוד גבוהה**: שם מתאמן שקופץ, אנטומיה שמוסברת ויזואלית, בירול גרפי, ועד סרטון שכולו MG עם וויס-אובר של הראל. הסקיל המלא: **`rel-motion-graphics`** · מערכת העיצוב: `tools/motion/MOTION.md`.

**איך זה בנוי:** HTML+GSAP בפורמט HyperFrames (Apache-2.0; Remotion נפסל — רישיון חברה מעל 3 אנשים) → `tools/motion/render.js` (Chrome מקומי, ≤ליבות-1 עובדים, פריים ריק משותף) → `MG_LAYER.mov` ProRes 4444 אלפא → **overlay יחיד** + זנב + SFX פרוצדורליים → `EXPORT+MG.mp4` · `MG_SHEET.jpg` · `MOTION_REPORT.json`. תבניות: kinetic_title · chips · name_reveal · compare · list_stack · quote · poll · stat · callout · angle · section · forearm (מסך מלא) · end_card (מסך מלא, זנב).
**v9.38 — ארבעה סגנונות + 13 תבניות:** סיפור מתאמן קולנועי (letterbox · athlete_card · punch · podium · timeline · quote_card · outro) · פירוק טכני (tag · telestrator עם `freeze_at` = פריים קפוא · tripod) · MG מלא + וויס-אובר (`backdrop:true` · bubbles · day_split · alerts · clock · crowd). `ev.bg:true` הופך כל תבנית לסצנת מסך מלא; `plan.theme:"personal"` = המותג האישי של הראל (#0077B6) — רק עם `--brand personal`. דמואים: `תוצרי-אנימציה/Motion Graphics/` (סוגי אחיזות · איתי עוזרי · HSPU · בעל מועדון).
**v9.39 — פסיקות הראל על הדמואים (חלות מהיום):** השכבה לא נוגעת בצבע (MG11 חוסם — בסיס HLG נשאר HLG) · בלי מלבן סביב משטחים (`REL.CLIP`) · צלילים מגוונים ומדוללים (`plan_sfx`, MG9) · MG מלא = מעברים תופסי עין + ~20% הראל במצלמה (`base_windows`, MG10) · end_card לא בכל סרטון · בסיפור מתאמן לא חותכים לגרפיקה ברגע וידוי. פירוט: סקיל `rel-motion-graphics` + `tools/motion/harel_verdicts.json`.
**v9.49 (17.10.26) — סגנון "על הלוח מונפש" + עוגני מילה:** תוכן חינוכי ⇒ ~80% אנימציה / ~20% הראל. `templates/board.js` (spectrum · board_title · board_list · board_strike · board_steps · board_years · board_poll · source_tag), משטחים דיו/נייר/אדום עם רצפת כתוביות (L141), קשת עוגן חוזרת. כל זמן בתוכנית = **עוגן מילה** `{"w":..}` שנפתר מ-words_final (MG12 חוסם, מדויק-קודם — L140). תיקון ליבה L139: חלון בסיס ב-0 + backdrop הזיז את כל ה-MG ב-1.27ש. התסריט נכתב לפי הסצנות (`◆MG STYLE board`), צילום = וויס-אובר + 3 שוטים. פירוט: `docs/על-הלוח-מונפש.md` · MOTION.md §13 · דמו `_motion_demo/board_scale`.
**v9.40 — הסגנון נבחר בתסריט:** `rel-script-writer` v3.2 כותב `◆MG STYLE` (+`theme`), רגעי `◆MG` ו-`◆BASE` ב-`⟦EDIT-LAYER⟧`, ודרישות הצילום של הסגנון ב-`⟦SHOOT⟧`. במצב B הם הבסיס של `motion_plan.json` (STYLE→סגנון/backdrop · ◆MG→אירועים על המילה · ◆BASE→`base_windows`); צילום שלא עמד בדרישה ⇒ סגנון חלופי + שורה בטבלת הפער.

**הרצה:**
```bash
~/.rel-whisper/bin/python tools/motion_build.py propose --workdir W        # מועמדים מהתמליל (לא החלטה)
#   Claude כותב W/motion_plan.json כבמאי — זמנים מ-words_final, טקסט מהתמליל או facts עם source
~/.rel-whisper/bin/python tools/motion_build.py check --workdir W           # MG0/MG4 חייבים לעבור
~/.rel-whisper/bin/python tools/motion_build.py snap --workdir W --base W/EXPORT_TIGHT.mp4 --at 1.2,7.5,…
#   Read על W/MG_SNAPS.jpg — ציון 1-10 על 7 צירים, מתקנים 3 חלשים, עד ≥8 בכולם
local_finish_pipeline.py … --motion auto   # ברירת מחדל: רץ כשיש motion_plan.json · on = חובה · off = מדלג
```
**בצנרת:** שלב `motion` אחרי בירול/פתיח קבוע ולפני מוזיקה. בחלונות `suppress_captions` המילים לא נצרבות פעמיים (`words_captions_mg.json`), V7 מודד מול מה שנצרב, ובירול מתחת ל-MG נמדד על הבסיס שלפני ה-MG (L111). כשל ב-auto = אזהרה והסרטון יוצא בלי MG; ב-on = עצירה.

**שערים:** MG0 · MG12 עוגני מילה · MG4 נאמנות טקסט · MG1 אזור בטוח [56..1024]×[258..1256] · MG2 פנים (5 דגימות לאירוע, באותו זמן) · MG5 פונטים · MG6 שגיאות דף · MG8 אורך — חוסמים. MG3 מינון + MG7 ≤17 תווים/ש — מדווחים עד כיול מפסיקות הראל.

**אזורים:** בסרטוני הדיבור שלנו הפנים בשליש העליון ⇒ ברירת המחדל `body` (מתחת לראש, עוגן תחתון 1240px). `top` רק כשהפנים מתחילות מתחת ל-760px (שוט תלייה, שוט רחב, בירול). `exit_lead` מצמיד יציאה לחיתוך כשהשוט הבא מוריד את הפנים.

**מינון התחלתי:** ערך 4-8 רגעים לדקה עם אוויר ≥0.6ש · המרה 2-4 (הוק+שם+CTA) · אירוע: שמות + תוצאות · מאסל מן/ההבנה האנטומית: דיאגרמה מסך-מלא אחת + תוויות. המחשה מאיור (v9.20) נשארת המסלול לשרירים על איור; MG הוא הוקטורי/טיפוגרפי.
