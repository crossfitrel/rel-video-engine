# צנרת עריכת סושיאל v5 — Runbook (R.E.L)

**נכון ל-16.7.2026 | מקור אמת לפעולות: `skills/rel-social-video-editor/SKILL.md` (v5.0)**
**עיקרון: מקומי-קודם. Descript = כירורגי + רוויו. התמליל מוביל, התסריט הרופף מכוון.**

```
Monday "מוכן לעריכה"
   │  match_intake (שיוך גלם מקומי)
   ▼
[מק] דחיסה crf23 → INPUT.mp4 → Whisper (align_words) → edl_build → edl_cut → ROUGH.mp4 (נקי-שקטים)
   │  intent_card.md + descript_instructions.md (החלטות פתוחות בלבד)
   ▼
[Descript] import ROUGH (קובץ אחד) → agent כירורגי (0-1 קריאות; אין פתוחות → דילוג = אפס קרדיט)
   │  Update [AUTO-EDIT v2 DRAFT] → הראל בודק/מתקן ב-Descript → [APPROVE-PUBLISH]
   ▼  (diff תיקוני הראל → לקח)
[ייצוא] publish → download EXPORT.mp4 (נקי — נשמר תמיד!)
   ▼
[גימור מקומי] gate שקט → B-roll overlay (conversion; broll_pick מהקטלוג) → מוזיקה -38 (תמיד)
   → קאבר (מ-EXPORT נקי, band 0.725) → כתוביות (מילה אחת, forced alignment, PASS≥90)
   → qa_gates.py (כל השערים) → תיוק {מחלקה}/{חודש}/{סרטון}/ → העלאה ל"סרטון מוכן"
   ▼
[Metricool] "מוכן לתזמון!" → מייל אישור (קאבר מוטמע) → [APPROVE-SCHEDULE] → createScheduledPost
   (פוסט אחד, כל הרשתות, titles×3, firstComment) → API קודם, ידני-קומפוזר אחרון → "תוזמן!" + "קפשן סופי:"
```

## פקודות — העתק-הרץ (בתוך `_work/{שם}/`)

```bash
# 2. הכנה מקומית (מק)
ffmpeg -y -i RAW.mov -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -ar 48000 -ac 2 -movflags +faststart clip1_1080.mp4     # לכל גלם; HLG? tonemap קודם
# כמה קליפים: printf "file 'clipN_1080.mp4'\n" ... > list.txt && ffmpeg -f concat -safe 0 -i list.txt -c copy INPUT.mp4
/Users/hayon/.rel-whisper/bin/python ../../tools/align_words.py INPUT.mp4 whisper_raw.json small he
python3 ../../tools/edl_build.py --words whisper_raw.json --out-dir . --video INPUT.mp4 --end {DUR} [--loose-script brief.txt]
python3 ../../tools/edl_cut.py --video INPUT.mp4 --edl edl.json --out ROUGH.mp4

# 7. גימור (אחרי EXPORT מ-Descript)
python3 ../../tools/finish_local.py gate --words words.json --video EXPORT.mp4          # חוסם
python3 ../../tools/broll_pick.py --topic "…" --content-type conversion --sentences sentences.json \
  --video-dur {D} --json broll_plan.json --commit                                       # conversion בלבד
python3 ../../tools/animation_overlay.py --base EXPORT.mp4 --out EXPORT+BROLL.mp4 {overlay_args}
python3 ../../tools/audio_mix.py mix --video EXPORT+BROLL.mp4 --music {TRACK} --out MIXED.mp4   # -38 קבוע
python3 ../../tools/thumbnail/frame_select.py EXPORT.mp4 --out thumb/ && \
python3 ../../tools/thumbnail/thumbnail_build.py --frame thumb/best.png --title "…" --out thumbnail.png
# כתוביות: align_words על MIXED → align_reconcile → captions_qa (PASS≥90) → captions_build burn (סנדבוקס)
python3 ../../tools/qa_gates.py --video FINAL.mp4 --words words.json --truth whisper_export.json
python3 ../../tools/resolve_output_path.py --dept "{מחלקה}" --name "{פריט}" --month "{חודש שנה}"   # → DC move
```

## חוקי ברזל (תמצית — המלא בסקיל)
- Hook קדוש · אנטי חיתוך-יתר (55-60ש) · אפס דד-אייר נמדד · פאוזות מכוונות נשמרות.
- כתוביות מקומיות בלבד: מילה אחת, בלי `.` `,` `…`, Assistant ExtraBold + ‎#871d1f, סטטיות, de-collide, RTL-wrap.
- בלי טקסטים גרפיים / לוגו / פתיחים (חריג מאסל-מן) · B-roll = conversion בלבד, mute, מהקטלוג, overlay מקומי.
- מוזיקה תמיד: מצע ‎-38 LUFS מקומי, בלי ducking, אורך מלא; מכירה אמיתית ‎-32 מותר; אסור שיר מסחרי.
- 1080×1920 · crf23 להעלאות, crf18 לביניים · אסור ultrafast · אסור לגעת בצבע ·
  אסור re-encode למדיה מתוזמנת · קאבר תואם-יחס · band-center 0.725 נעול.
- העלאות כבדות: nohup על המק, בדיקה אחת, בלי ניטור תכוף · כל כתיבה אטומית (tmp→replace).
- Gate-ים של הראל: [APPROVE-PUBLISH] על הטיוטה · מייל אישור לפני כל תזמון. תמיד.

## כלים
| כלי | תפקיד |
|---|---|
| edl_build / edl_cut | עריכה דטרמיניסטית מקומית לפני Descript (+ הוראות כירורגיות) |
| broll_catalog / broll_pick | קטלוג בירולים + בחירה/שיבוץ (rotation, קהלים) |
| qa_gates | כל שערי ה-QA בריצה אחת (G1-G7) |
| finish_local / captions_build / captions_qa | גייט שקט, צריבת כתוביות, מדידת סנכרון |
| audio_mix | מיקס מוזיקה LUFS + measure |
| animation_overlay | overlay בירולים/אנימציות מקומי (mute) |
| thumbnail/* | קאבר ממותג (frame_select → thumbnail_build; cover_inpaint לחירום) |
| match_intake / resolve_output_path | שיוך גלם ↔ בורד · ניתוב תוצרים לתיקיות |
| descript_put.sh | PUT ישיר ל-Descript עם retry |

*היסטוריה: גרסת v2.9 של runbook זה — בגיט/ארכיון. השינוי המרכזי ב-v5: ההחלטות עברו מקומית (EDL), Descript ירד לכירורגיה ורוויו.*
