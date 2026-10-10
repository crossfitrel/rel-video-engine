# v9.36 — ספריית מוזיקה מגוונת (28.9.26)
לצ'אט המקביל «TD26 שתיקות+מוזיקה 28.9» ולכל מי שנוגע במוזיקה:
- `tools/local_finish_pipeline.py` — שונה **רק** `pick_music()` (קטלוג נקרא תמיד; banned; heavy:true; התאמת energy_level לטון/סוג; value בלי vocals=chops; גיוון sound_family מול 3 בחירות אחרונות). גיבוי: `tools/local_finish_pipeline.py.bak-v936-music-20260928`. לא נגעתי במפלסים/דאקינג/מיקס.
- `tools/music-catalog.json` → v2 (336 רשומות; genre/energy הישנים נשמרו). גיבוי v1: `tools/_music_harvest/music-catalog.v1-backup.json`.
- `tools/music-energy.json`, `tools/music-intro-dip.json` — נוספו 230 טראקים.
- `brand-assets/music` — +230 טראקים (sha256 ב-`tools/_music_harvest/download_manifest.json`).
- לקח L107 + `tests/test_music_variety_v936.py`. baseline: unittest 0 FAIL; doctor FAIL יחיד = sync ציר↔חיתוך ב-«למה-אני-מתחרה-חלק-ג» (לא שלי, לא נגעתי).
- פסולת לא ניתנת למחיקה מהסנדבוקס: `tools/_music_harvest/_to_delete/`.
