#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_finish_pipeline.py — v6: אורקסטרטור הגימור המקומי, אפס Descript.
=====================================================================
רץ על המק. מ-EDL מאושר ועד FINAL.mp4 עם QA — בקריאה אחת:

  1. recut     — edl_cut על INPUT.mp4 לפי edl.json → EXPORT.mp4 (הקאט המאושר, נקי)
  2. whisper   — align_words (venv ‎~/.rel-whisper) על EXPORT → whisper_export.json
  3. reconcile — align_reconcile (טקסט מתוקן: edited.txt > correct_transcript.txt >
                 טקסט whisper) → words_final.json  (כולל de-collide מובנה)
  4. gate      — finish_local gate: אפס דד-אייר. נכשל → עוצרים ומחזירים טיימקודים
                 (התיקון: באפליקציית הרוויו — לא ב-Descript)
  5. broll     — [conversion בלבד] אוטומטי: ‎--broll-plan מפורש > broll_plan.json קיים
                 בתיקיית העבודה > הרצה אוטומטית של broll_pick.py (topic מ-intent_card.md,
                 dept מה-manifest, טיימינג-משפטים ממופה לציר המהודק). ‎--no-broll לדלג במפורש.
                 כשל בירול = לא-חוסם (מדווח, ממשיכים בלי בירול).
  6. music     — בחירת טראק (rotation; רגוע לתוכן לא-מכירתי, מסונן phonk/trap/rock_sport/
                 edm) + audio_mix ‎-38, עם דאקינג אמיתי כברירת מחדל (יורד ל--9 LUFS בזמן
                 דיבור; ‎--no-duck מבטל — 23.7.26 r2)
  7. captions  — צריבת PIL overlay (captions-app/captions_overlay) על MIXED → FINAL
  8. loudness  — יישור ‎-14 LUFS/TP-1 על FINAL (‎-c:v copy — לא נוגע בווידאו)
  9. qa        — qa_gates.py, כל השערים. FAIL ⇒ exit 1.
 10. thumbnail — [אם ‎--title] frame_select על EXPORT נקי → thumbnail_build (band 0.725)

סטטוס חי נכתב ל-{workdir}/finish_status.json (לאפליקציית הרוויו) + FINISH_REPORT.md.

שימוש:
  python3 local_finish_pipeline.py --workdir "_work/{שם}" [--content-type value|conversion]
      [--music auto|/path.mp3] [--music-lufs -38] [--broll-plan broll_plan.json]
      [--broll-audience דוספיט] [--no-broll]
      [--title "כותרת קאבר" [--subtitle "..."]] [--skip-whisper] [--no-recut]
"""
import argparse, json, os, re, shlex, shutil, subprocess, sys, time
from pathlib import Path

HERE   = Path(__file__).resolve().parent          # tools/
sys.path.insert(0, str(HERE))
import length_policy as LP                         # noqa: E402  (v9.25)
SYSDIR = HERE.parent                              # Social Video Editing System
APPDIR = SYSDIR / "captions-app"
MUSIC_DIR = SYSDIR / "brand-assets" / "music"
ROTATION_STATE = HERE / "music-rotation.json"
WHISPER_PY = Path.home() / ".rel-whisper" / "bin" / "python"


def ensure_tool_path():
    """v9.22 (L50b, 10.9.26): הגימור רץ גם מתוך שרת הרוויו, שעולה בלי סביבת login
    (PATH=/usr/bin:/bin:/usr/sbin:/sbin). אז `ffmpeg` לא נמצא ו-`python3` הוא 3.9 של
    המערכת — edl_cut נפל ב-FileNotFoundError אחרי 0.4ש, בדיוק כשהראל לחץ "אשר".
    מקדימים את נתיבי Homebrew לסביבה של התהליך — וכל תת-תהליך יורש אותם."""
    cur = os.environ.get("PATH", "").split(os.pathsep)
    add = [d for d in ("/opt/homebrew/bin", "/usr/local/bin") if Path(d).is_dir() and d not in cur]
    if add:
        os.environ["PATH"] = os.pathsep.join(add + cur)


ensure_tool_path()

def sh(cmd, cwd=None, timeout=1800):
    """v8.6 (P0-4): TimeoutExpired נתפס ומתורגם ל-returncode 124.

    שורש: עד כה אף קורא לא עטף את הקריאה ב-try. ffmpeg תקוע ⇒ החריגה עולה מעל
    fail(), ולכן FINISH_REPORT לא נכתב ו-finish_status.json נשאר state="running"
    לנצח — וזה בדיוק הקובץ שהאפליקציה קוראת כדי להציג מצב. הריצה נראתה "רצה"
    יומיים אחרי שמתה. עכשיו timeout מתנהג כמו כל כשל אחר: rc≠0 → fail() → failed.
    124 הוא הקוד ש-coreutils/timeout מחזיר, כדי שיהיה מזוהה בלוגים."""
    try:
        return subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = (e.stderr or b"") if isinstance(e.stderr, bytes) else (e.stderr or "")
        if isinstance(out, bytes): out = out.decode("utf-8", "replace")
        if isinstance(err, bytes): err = err.decode("utf-8", "replace")
        name = Path(str(cmd[0])).name if cmd else "?"
        return subprocess.CompletedProcess(
            args=[str(c) for c in cmd], returncode=124, stdout=out,
            stderr=(err + f"\n[TIMEOUT] {name} עבר {timeout}ש ונקטע (rc=124)"))

def ffdur(p):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", p])
    try: return float(r.stdout.strip())
    except Exception: return 0.0

class Status:
    """v7.8 — מדידת זמן פר-שלב. בלי זה אי אפשר לדעת איפה הזמן נשרף:
    המדידה הראשונה (25.7.26, סרטון 47ש) הראתה whisper=51ש מתוך 105ש ריצה —
    חצי מהזמן בשלב אחד, מה שהוביל להחלפת המודל. הזמנים נכתבים ל-finish_status.json
    (האפליקציה מציגה), ל-FINISH_REPORT.md ולרשומת הריצה."""
    def __init__(self, workdir):
        self.path = Path(workdir) / "finish_status.json"
        self.t0 = time.time()
        self._step_t = None
        self.data = {"state": "running", "step": "", "steps_done": [], "started": self.t0,
                     "timings": {}}
    def step(self, name):
        self._step_t = time.time()
        self.data["step"] = name; self._w()
        print(f"▶ {name}", flush=True)
    def done_step(self, name, detail=""):
        el = round(time.time() - self._step_t, 1) if self._step_t else None
        if el is not None:
            self.data["timings"][name] = round(self.data["timings"].get(name, 0.0) + el, 1)
        self.data["steps_done"].append({"step": name, "detail": detail, "secs": el}); self._w()
        print(f"✅ {name} [{el}ש] {detail}" if el is not None else f"✅ {name} {detail}", flush=True)
    def finish(self, ok, detail=""):
        self.data["state"] = "done" if ok else "failed"
        self.data["step"] = ""; self.data["detail"] = detail
        self.data["total_secs"] = round(time.time() - self.t0, 1); self._w()
    def timings_md(self):
        rows = sorted(self.data["timings"].items(), key=lambda kv: -kv[1])
        tot = round(time.time() - self.t0, 1)
        body = " · ".join(f"{k} {v}ש" for k, v in rows)
        return f"- ⏱ זמני שלבים (סה\"כ {tot}ש): {body}"
    def _w(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

# ── טון הבריף קובע ז'אנר, לא רק סוג התוכן (v9.9) ──────────────────────────
# השורש: הסינון הכבד הופעל רק כש-`content_type != "conversion"`. סרטון
# האופן-ג'ים **הוא** המרה, והטון שלו "רגוע, בטוח ועובדתי. זו הזמנה לשקט
# ולמרחב אישי, לא דחיפה" — ובכל זאת קיבל phonk. אז זה תוקן פעמיים באותה
# נשימה (ז'אנר **וגם** מפלס), ואחד התיקונים התיישן ונשאר (‏v9.8: -48 שנקבע
# כפיצוי על phonk, כשהז'אנר כבר תוקן). **תיקון בשתי שכבות לאותה בעיה = סימן
# שהשכבה הנכונה לא זוהתה.** השכבה הנכונה היא הטון.
CALM_TONE_WORDS = ("רגוע", "רגועה", "שקט", "שקטה", "שקטות", "עדין", "עדינה",
                   "אינטימי", "כנה", "כן ", "מכבד", "נוגע", "רך", "רכה",
                   "מרגיע", "הזמנה לשקט", "לא דחיפה", "בלי דחיפה",
                   "עובדתי", "מדויק", "צנוע", "calm", "quiet", "gentle")
ENERGETIC_TONE_WORDS = ("אנרגטי", "אנרגטית", "נמרץ", "פיצוץ", "חוגג", "חגיגי",
                        "מתלהב", "דוחף", "מלהיב", "עוצמתי", "hype", "energetic")


def tone_class(tone: str) -> str:
    """`calm` / `energetic` / `neutral`. מחזיר דאטה, לא דעה.

    ‏`energetic` מנצח כשהטון אומר את שניהם — טון שמכיל 'אנרגטי' במפורש
    ביקש את הבס, ואין סיבה לנחש אחרת.
    """
    t = str(tone or "")
    if any(w in t for w in ENERGETIC_TONE_WORDS):
        return "energetic"
    if any(w in t for w in CALM_TONE_WORDS):
        return "calm"
    return "neutral"


def read_brief_tone(W) -> str:
    try:
        return str((json.loads((Path(W) / "brief.json").read_text(encoding="utf-8"))
                    or {}).get("tone") or "")
    except Exception:
        return ""


def pick_music(content_type, explicit, tone="", light=False):
    if explicit and explicit != "auto":
        return Path(explicit)
    tracks = sorted(MUSIC_DIR.glob("*.mp3"))
    if not tracks:
        return None
    # תיוג אנרגיה (הראל 20.7.26: מוזיקה ל"שינה" הרגישה כמו מוזיקת מעליות — ברירת המחדל
    # לרוטציה חייבת להיות קצבית/כיפית, לא רגועה/אמביינטית). music-energy.json הוא המקור
    # לתיוג; "mellow_special" יוצא מהרוטציה האוטומטית לכל content_type (כולל value/personal) —
    # נכנס רק אם התבקש נקודתית דרך --music מפורש.
    tags = {}
    tags_path = HERE / "music-energy.json"
    if tags_path.exists():
        try:
            tags = json.loads(tags_path.read_text(encoding="utf-8")).get("tracks", {})
        except Exception:
            tags = {}
    energetic = [t for t in tracks if tags.get(t.name, "energetic") != "mellow_special"]
    pool = energetic or tracks
    # סינון ז'אנר לפי content_type (23.7.26, פידבק הראל: "המוזיקה רועשת מדי, לא שומעים
    # טוב את הדיבור") — אבחון בפועל על "סקאלת-הבריאות" (content_type=value): נבחר
    # "Phonk Gym" (ז'אנר phonk, אנרגטי) כמצע לתוכן חינוכי-רגוע. הבעיה לא הייתה מתמטיקת
    # LUFS (נבדק — הבדל זניח בין single-pass ל-two-pass על התוכן הזה) אלא **הז'אנר עצמו**:
    # ז'אנרים פרקוסיביים/כבדי-בס (phonk/trap/rock_sport) בולטים ומתחרים עם דיבור גם
    # ב-LUFS נמוך, בגלל crest-factor גבוה (הלמי-בס/טראנזיינטים חדים). music-catalog.json
    # (105 טראקים, genre+energy+source) קיים כבר אבל לא נקרא כאן עד עכשיו. כלל: לתוכן
    # לא-מכירתי (value/personal — לא conversion) מסננים את שלושת הז'אנרים הכבדים ביותר;
    # ל-conversion נשאר המאגר האנרגטי המלא (הבס המכירתי מתאים שם). אם הסינון מרוקן את
    # המאגר — נופלים בחזרה ל-pool המלא (לא חוסמים את הפייפליין).
    #
    # תיקון שורש נוסף (23.7.26, פידבק חוזר: "המוזיקה עדיין רועשת מדי בכל הסרטונים"):
    # מדדתי crest-factor (TP-I) ו-LRA בפועל על כל 105 טראקי הקטלוג (ffmpeg loudnorm
    # measure-pass, ראה crest_measurements.json בסשן האבחון). התוצאה הפריכה את ההנחה
    # ש-crest-factor הוא הסמן הנכון: ל-piano_calm/lofi_calm יש crest **גבוה** יותר
    # מ-phonk/edm/rock_sport (כי יש להם רגעים שקטים אמיתיים בין תווים, לעומת "קיר סאונד"
    # דחוס-דינמית שכבר עבר מאסטרינג לעוצמה קבועה). אין סמן אקוסטי-סטטי נקי אחד שמזהה
    # "טראק שיתנגש עם דיבור" — מדידה אוטומטית לא תחליף כאן שיפוט אנושי.
    # הממצא האמיתי מבדיקת FINISH_REPORT.md על 15 הסרטונים האחרונים: רק 2/15 השתמשו
    # ב---duck בפועל (המפלס יורד בזמן דיבור) — 13 האחרים ניגנו מוזיקה **קבועה** לכל
    # אורך הסרטון (אין ירידה כלל בזמן דיבור), כולל טראקים בז'אנרים "corporate"/"funk"/
    # "edm" שלא נכללו בסינון הישן. זה השורש האמיתי, לא בחירת הטראק: --duck היה אופציונלי
    # (opt-in) ולא הופעל ברוב הריצות. תוקן: ---duck הפך לברירת מחדל (ראה parse_args
    # --no-duck), ו-edm נוסף ל-HEAVY_GENRES (מה שראינו בפועל: "Hard/Acid EDM" נבחרו
    # לתוכן value ולא היו אמורים).
    HEAVY_GENRES = {"phonk", "trap", "rock_sport", "edm"}
    # v9.9 — הטון גובר על סוג התוכן. המרה בטון רגוע מסוננת כמו תוכן ערך;
    # המרה בטון אנרגטי שומרת את המאגר המלא. `neutral` = ההתנהגות הישנה.
    tc = tone_class(tone)
    filter_heavy = (content_type != "conversion") or tc == "calm"
    if tc == "energetic":
        filter_heavy = False
    # v9.36 (28.9.26, הראל: "הכל נשמע די אותו דבר") — הקטלוג נקרא תמיד, לא רק
    # כשמסננים כבדים: הוא נושא עכשיו heavy / energy_level / sound_family
    # (מדודים, tools/_music_harvest/) שקובעים התאמה וגיוון.
    catalog = {}
    catalog_path = HERE / "music-catalog.json"
    if catalog_path.exists():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8")).get("tracks", {})
        except Exception:
            catalog = {}
    meta = lambda t: catalog.get(t.name, {}) or {}
    pool = [t for t in pool if not meta(t).get("banned")] or pool
    if filter_heavy and catalog:
        # ז'אנר כבד = אחד מארבעת הישנים **או** heavy:true (drill/hardstyle/rage/
        # jersey club/brazilian funk/punk… — ז'אנרים חדשים מ-v9.36 מסומנים בדאטה).
        gentle = [t for t in pool if meta(t).get("genre") not in HEAVY_GENRES
                  and not meta(t).get("heavy")]
        pool = gentle or pool
    # v9.36 — התאמת אנרגיה לטון/סוג תוכן. energy_level 1-5 נמדד מהאודיו
    # (bpm+פרקוסיביות+צפיפות אונסטים+RMS). מסנן רק כשנשארים ≥10 מועמדים —
    # לא מרוקן את המאגר (אין שער חוסם עם סף לא-מדוד).
    def _lvl(t):
        try: return int(meta(t).get("energy_level") or 3)
        except Exception: return 3
    if tc == "energetic":
        fit = [t for t in pool if _lvl(t) >= 4]
    elif tc == "calm":
        fit = [t for t in pool if _lvl(t) <= 3]
    elif content_type == "conversion":
        fit = [t for t in pool if _lvl(t) >= 3]
    else:
        # תוכן ערך: בלי vocal chops (מילים מוקלטות מתחרות בדיבור של הראל)
        fit = [t for t in pool if 2 <= _lvl(t) <= 4 and meta(t).get("vocals") != "chops"]
    if len(fit) >= 10:
        pool = fit
    # v9.37 (29.9.26, הראל על תכני Throwdown: "בסגנון יותר מדי דרמטי להרבה תכנים קלילים").
    # פרופיל light = תוכן אירוע/קהילה/ראיונות: funk/afrobeat/hiphop-groove, בלי אפי/רוק/EDM/
    # טראפ/פונק/סינמטי, רמת אנרגיה ≤4. גובר על טון "energetic" מהבריף (שם נפל ה-epic).
    # מופעל ע"י finish_prefs.music.profile="light" או אוטומטית לפרויקט Throwdown (ראה הקריאה).
    if light and catalog:
        # v9.47 (L128, הראל 9.10.26 על 26 ריליז Throwdown): funk/afrobeat/hiphop נפסלו —
        # "מוזיקה על הפנים, המוזיקה לאחרונה לא מתאימה לסגנון הסרטון בכל התכנים",
        # "המוזיקה פה מאוד מוזרה", "צריך משהו יותר קצבי וקליל". הפרופיל הקליל עובר לפופ/
        # דאנס-פופ/אינדי/סינת'-פופ/טרופיקל/נו-דיסקו/האוס: קצבי, מואר, בלי מצב רוח אגרסיבי/
        # אפל/אפי, ונוכחות בפס הטלפון (‎300-5000Hz) — אחרת לא נשמע ברמקול (שורש 27.9).
        LIGHT_GENRES = {"pop", "dance_pop", "reels_pop", "indie_pop", "synthpop", "electropop",
                        "tropical_house", "nu_disco", "disco", "house", "deep_house", "latin_house",
                        "future_bass", "indie_rock", "surf_rock", "ska_reggae"}
        LIGHT_BAD_MOODS = {"aggressive", "dark", "epic"}
        _all = [t for t in energetic or tracks if not meta(t).get("banned")]
        lp = [t for t in _all if meta(t).get("genre") in LIGHT_GENRES and not meta(t).get("heavy")
              and 3 <= _lvl(t) <= 4 and meta(t).get("vocals") in (None, "none")
              and not (set(meta(t).get("moods") or []) & LIGHT_BAD_MOODS)
              and "cinematic" not in t.name and "drill" not in t.name]
        if len(lp) >= 8:
            pool = lp
    # חוק אי-חזרה (הראל 23.7.26): אותה מנגינה לא חוזרת בחלון של 90 יום לפחות.
    # music-rotation.json v2 = היסטוריית שימוש {track: ts}. אם *כל* המאגר שומש
    # ב-90 הימים — נופלים ל-LRU (הישן ביותר), כדי לא לחסום את הפייפליין;
    # זה גם הסימן שצריך להרחיב את הספרייה.
    NO_REPEAT_DAYS = 90
    state = {}
    if ROTATION_STATE.exists():
        try: state = json.loads(ROTATION_STATE.read_text())
        except Exception: state = {}
    history = dict(state.get("history", {}))
    if not history and state.get("last"):            # מיגרציה מפורמט v1
        history[state["last"]] = time.strftime("%Y-%m-%d %H:%M:%S")
    def used_at(t):
        try:
            return time.mktime(time.strptime(history.get(t.name, ""), "%Y-%m-%d %H:%M:%S"))
        except Exception:
            return 0.0
    cutoff = time.time() - NO_REPEAT_DAYS * 86400
    fresh = [t for t in pool if used_at(t) < cutoff]
    if fresh:
        # v9.36 — גיוון צליל: לא אותה "משפחת סאונד" (sound_family, אשכול
        # אקוסטי מדוד — לא תווית ז'אנר) כמו 3 הבחירות האחרונות. זה השורש של
        # "הכל נשמע אותו דבר": טראקים שונים באותו ז'אנר-על נשמעים זהים מתחת לדיבור.
        recent = sorted(history.items(), key=lambda kv: kv[1], reverse=True)[:3]
        recent_fam = {(catalog.get(n, {}) or {}).get("sound_family") for n, _ in recent} - {None}
        varied = [t for t in fresh if meta(t).get("sound_family") not in recent_fam]
        cand = varied or fresh
        choice = cand[int(time.time()) % len(cand)]
    else:
        choice = min(pool, key=used_at)              # LRU — כל המאגר שומש לאחרונה
        print(f"⚠️ כל {len(pool)} הטראקים שומשו ב-{NO_REPEAT_DAYS} הימים — "
              f"נבחר הישן ביותר ({choice.name}). להרחיב את הספרייה.", flush=True)
    history[choice.name] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = ROTATION_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 2, "last": choice.name,
                               "history": history}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(ROTATION_STATE)
    return choice

def extract_broll_topic(W, title=""):
    """טקסט-נושא לניקוד broll_pick (score_item) — קו-הסיפור מ-intent_card.md, עם
    fallback ל-Hook, ועם כותרת הקאבר אם סופקה. best-effort: אם ריק, broll_pick עדיין
    עובד לפי משך/rotation בלבד (לא חוסם)."""
    parts = [title] if title else []
    p = W / "intent_card.md"
    if p.exists():
        try:
            txt = p.read_text(encoding="utf-8")
            m = re.search(r"קו סיפור:?\*\*\s*\n(.*?)(?=\n- \*\*|\Z)", txt, re.DOTALL)
            body = (m.group(1) if m else "").strip()
            if not body:
                hm = re.search(r"Hook[^\n]*:\*\*\s*(.*)", txt)
                body = hm.group(1).strip() if hm else ""
            if body:
                parts.append(" ".join(body.split()[:120]))
        except Exception:
            pass
    return " ".join(parts).strip()

def remap_sentences(sentences_path, remap_fn, out_path):
    """ממפה sentences.json (נכתב ב-edl_build, על ציר ה-EXPORT הגולמי) לציר המהודק
    (אחרי tighten) — כדי ש-broll_pick ימקם overlay ביחס לגבולות משפט נכונים בפלט
    בפועל, לא לפי טיימינג שהוזז ע"י חיתוך שקטים."""
    sents = json.loads(Path(sentences_path).read_text(encoding="utf-8"))
    out = []
    for s in sents:
        ns = dict(s)
        ns["start"] = round(remap_fn(float(s["start"])), 3)
        ns["end"] = round(remap_fn(float(s["end"])), 3)
        out.append(ns)
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out_path

def ensure_broll_plan(W, HERE, dur, content_type, title, audience, n, sentences_tight_path, report,
                      commit=True):
    """מחזיר (path לbroll_plan.json תקין, detail) או (None, סיבה) — לא-חוסם.
    סדר עדיפויות: broll_plan.json קיים בתיקיית העבודה (מוכן מראש/ידני) >
    הרצה אוטומטית של broll_pick.py."""
    existing = W / "broll_plan.json"
    if existing.exists():
        try:
            plan = json.loads(existing.read_text(encoding="utf-8"))
            if plan.get("plan"):
                return existing, f"broll_plan.json קיים ({len(plan['plan'])} פריטים)"
            # v9.4 — תוכנית ריקה של הבמאי היא **החלטה**, לא כישלון: "אין קליפ
            # שעונה על מה שנאמר ⇒ אין בירול". בלי הבדיקה הזאת הצינור היה מריץ
            # מעליה בחירה אוטומטית לפי נושא-על — בדיוק המנגנון שהוחלף.
            if plan.get("source") == "director":
                why = plan.get("why") or "הבמאי לא מצא התאמה שעוברת את סף הביטחון"
                report.append(f"- 🎬 בלי בירול (החלטת הבמאי): {why} "
                              f"({plan.get('n_windows', '?')} חלונות, "
                              f"בריכה {plan.get('pool_size', '?')})")
                return None, "הבמאי החליט בלי בירול"
        except Exception:
            pass
    manifest = {}
    mpath = W / "project_manifest.json"
    if mpath.exists():
        try: manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except Exception: manifest = {}
    dept = manifest.get("dept") or ""
    topic = extract_broll_topic(W, title)
    # v9.7: `--workdir` מפעיל את שער סתירה-לבריף (קורא brief.json).
    cmd = ["python3", HERE / "broll_pick.py", "--workdir", str(W),
           "--content-type", content_type,
           "--topic", topic, "--audience", audience, "--dept", dept,
           "--n", str(n), "--video-dur", f"{dur:.2f}",
           "--json", str(existing)]
    # v9.23 — רישום שימוש (usage.json, רוטציית הבירולים) רק בגימור אמיתי. נמדד 11.9.26:
    # הכנת תצוגת פתיחה ועותקי E2E רשמו שימוש גלובלי בקליפים שלא פורסמו — ומשנים
    # את הבחירה של הריצה הבאה (ולכן גם את הקשר הפתיחה). REL_BROLL_USAGE_COMMIT=0
    # לעותקי בדיקה; בהרצה רגילה ההתנהגות זהה לחלוטין לקודם.
    if commit and os.environ.get("REL_BROLL_USAGE_COMMIT", "1") != "0":
        cmd.append("--commit")
    if sentences_tight_path and Path(sentences_tight_path).exists():
        cmd += ["--sentences", str(sentences_tight_path)]
    r = sh(cmd)
    if r.returncode != 0:
        detail = (r.stdout or r.stderr or "").strip()[-200:]
        report.append(f"- ⚠️ broll_pick.py אוטומטי לא הפיק תוכנית (exit {r.returncode}): {detail}")
        return None, "אוטומטי נכשל"
    try:
        plan = json.loads(existing.read_text(encoding="utf-8"))
    except Exception as e:
        report.append(f"- ⚠️ broll_plan.json שנוצר אוטומטית לא תקין: {e}")
        return None, "JSON לא תקין"
    if not plan.get("plan"):
        why = plan.get("no_match_reason") or "אין התאמות בקטלוג"
        report.append(f"- 🎬 בלי בירול: {why} "
                      f"(נסרקו {plan.get('pool_size', '?')} קליפים, "
                      f"{plan.get('skipped_low_relevance', 0)} מתחת לסף)")
        return None, why
    return existing, f"נוצר אוטומטית ({len(plan['plan'])} פריטים, topic={topic[:40]!r})"

def speech_coverage_gate(video, words_path, st, report, min_gap=1.0):
    """v7.9 — שער כיסוי כתוביות: מאתר דיבור **בלי מילים**.

    v7.10: הסף ירד 1.5→1.0ש כדי לתפוס גם **מלמול לפני טייק** (הראל: "בשתי השניות
    הראשונות של 'מוזמנים להגיע אלינו' נבו ממלמל לעצמו") — קול בלי מילים הוא בדיוק
    החתימה של מלמול-חזרה. לא חוסם: מדווח עם טיימקוד כדי שתחתוך באפליקציה.

    שורש (הראל 25.7.26: "משהו נופל בין הכיסאות בכתוביות, פספס משפט והקדים את הבא"):
    Whisper השמיט משפט שלם, ואף שער לא תפס — כל השערים בדקו תזמון/שקט, אף אחד לא
    בדק *כיסוי*. הבדיקה: כל חלון ≥min_gap שניות בלי אף מילה — האם יש בו דיבור?
    מצליבים מול silencedetect: אם הקטע אינו שקט ⇒ דיבור בלי כתובית ⇒ אזהרה רועשת
    עם טיימקוד. לא חוסם (יכול להיות רעש/צחוק), אבל **חייב להופיע בדוח ובאפליקציה**.
    """
    try:
        words = json.loads(Path(words_path).read_text(encoding="utf-8"))
    except Exception:
        return []
    if not words:
        return []
    dur = ffdur(video)
    r = sh(["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-i", str(video),
            "-af", "silencedetect=n=-35dB:d=0.4", "-f", "null", "-"])
    sil = []
    starts = re.findall(r"silence_start: ([\d.]+)", r.stderr)
    ends = re.findall(r"silence_end: ([\d.]+)", r.stderr)
    for i, s in enumerate(starts):
        e = float(ends[i]) if i < len(ends) else dur
        sil.append((float(s), e))

    def silent_frac(a, b):
        if b <= a:
            return 1.0
        covered = sum(max(0.0, min(b, e) - max(a, s)) for s, e in sil)
        return covered / (b - a)

    gaps = []
    prev_end = 0.0
    for w in words + [{"start": dur, "end": dur}]:
        gap = float(w["start"]) - prev_end
        if gap >= min_gap:
            sf = silent_frac(prev_end, float(w["start"]))
            if sf < 0.6:                     # רוב החלון אינו שקט ⇒ דיבור בלי כתובית
                gaps.append({"start": round(prev_end, 2), "end": round(float(w["start"]), 2),
                             "silent_frac": round(sf, 2)})
        prev_end = max(prev_end, float(w["end"]))
    if gaps:
        txt = " · ".join(f"{g['start']}-{g['end']}ש" for g in gaps[:6])
        report.append(f"- 🚨 **קול בלי כתוביות** ב-{len(gaps)} מקומות: {txt} — "
                      f"תמלול חסר או מלמול-לפני-טייק; לבדוק לפני פרסום")
        st.done_step("coverage", f"⚠️ {len(gaps)} קטעי דיבור בלי כתוביות: {txt}")
    else:
        st.done_step("coverage", "כל הדיבור מכוסה בכתוביות")
    return gaps


CENSOR_LEXICON = HERE / "caption-censor.json"
CENSOR_PREFIXES = ("ו", "ה", "ש", "יא", "יה")


def censor_mask(word: str) -> str:
    """'שרמוטה' → 'שרמ#$%'. חצי מהאותיות (עיגול למעלה) ואז סימנים — מבינים מה נאמר
    בלי לכתוב את זה (הראל 9.10.26, "תחרות-ראשונה-שלי")."""
    core = word.strip(",.?!:;\"'")
    keep = max(1, (len(core) + 1) // 2)
    return word.replace(core, core[:keep] + "#$%")


def censor_caption_words(words_path, W, manifest=None):
    """v9.47 (L129) — מחזיר (נתיב, מספר מילים שצונזרו). הלקסיקון: tools/caption-censor.json
    (מילים חד-משמעיות בלבד) + finish_prefs.captions.censor במניפסט (פר-פרויקט, למילה
    דו-משמעית כמו 'כוס'). מילה מכוסה גם עם תחילית ו/ה/ש. לא נוגע ב-words_final.json —
    רק בעותק שנצרב."""
    try:
        lex = set((json.loads(CENSOR_LEXICON.read_text(encoding="utf-8")) or {}).get("words", []))
    except Exception:
        lex = set()
    extra = (((manifest or {}).get("finish_prefs") or {}).get("captions") or {}).get("censor") or []
    lex |= set(extra)
    if not lex:
        return words_path, 0
    try:
        ws = json.loads(Path(words_path).read_text(encoding="utf-8"))
    except Exception:
        return words_path, 0

    def hit(core):
        if core in lex:
            return True
        return any(core.startswith(p) and core[len(p):] in lex for p in CENSOR_PREFIXES)
    n = 0
    for w in ws:
        txt = str(w.get("word") or w.get("text") or "")
        core = txt.strip(",.?!:;\"'")
        if core and hit(core):
            key = "word" if "word" in w else "text"
            w[key] = censor_mask(txt)
            n += 1
    if not n:
        return words_path, 0
    out = Path(W) / "words_captions_censored.json"
    out.write_text(json.dumps(ws, ensure_ascii=False, indent=1), encoding="utf-8")
    return out, n


def run_notefix(W, st, report, enabled=True):
    """v7.8 — מחיל את תיקוני הכתיב שהראל כתב בהערות ישירות על התמליל, לפני reconcile.

    למה: "שגיאות כתיב בכתוביות" היא ההערה החוזרת ביותר, והראל כבר כותב את התיקון
    המדויק ("בקרוספיט* ולא קרוספית"). עד v7.6 כל תיקון כזה חייב סבב קלאוד שלם;
    מעכשיו "גימור מהיר" מהאפליקציה מתקן אותם לבד. תיקון עמום → needs_manual, לא ניחוש.
    לא-חוסם: כשל כאן לא עוצר גימור."""
    if not enabled:
        return None
    st.step("notefix")
    r = sh(["python3", HERE / "note_corrections.py", "--workdir", W,
            "--apply", "--learn", "--json", W / "note_corrections.json"])
    try:
        rep = json.loads((W / "note_corrections.json").read_text(encoding="utf-8"))
    except Exception:
        st.done_step("notefix", "לא רץ (לא-חוסם)")
        return None
    n = rep.get("applied", 0)
    man = len(rep.get("needs_manual") or [])
    amb = len(rep.get("ambiguous") or [])
    detail = (f"{n} תיקוני כתיב מההערות"
              + (f" · {man} עמומים להכרעתך" if man else "")
              + (f" · {amb} 'במקום' דו-משמעי" if amb else ""))
    st.done_step("notefix", detail)
    if amb:
        for x in rep["ambiguous"]:
            report.append(f"- ❔ \"{x['a']}\" / \"{x['b']}\" — ניסוח \"במקום\" דו-משמעי, לא שונה אוטומטית")
    if n or man:
        fixes = " · ".join(f"{f['from']}→{f['to']}" for f in (rep.get("fixes") or [])[:12])
        report.append(f"- 📝 תיקוני כתיב מההערות: {n} הוחלו{(' — ' + fixes) if fixes else ''}")
        if man:
            report.append(f"  ⚠️ {man} מילים מסומנות לא זוהו חד-משמעית: "
                          + ", ".join(m["word"] for m in rep["needs_manual"]))
    return rep


def measure_lufs(p):
    r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", p,
            "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"])
    blocks = re.findall(r"\{[^{}]*\}", r.stderr, re.DOTALL)
    if not blocks: return None, None
    j = json.loads(blocks[-1])
    return float(j["input_i"]), float(j["input_tp"])

def loudness_align(video, target=-14.0):
    """יישור loudness בלי לגעת בווידאו (‎-c:v copy). עד 2 איטרציות.
    oversample 176.4kHz לפני alimiter (כמו ב-audio_mix.py) — בלעדיו alimiter מגביל רק
    sample-peak ב-48kHz, ו-true-peak (מדידת loudnorm, 4x oversampled per EBU R128) יכול
    לחמוק מעל הסף עקב inter-sample peaks — נצפה בפועל עם דאקינג/מדרגת-גיין (לקח 20.7 r4)."""
    # v7: אם אחרי המעבר הראשון TP עדיין חם (הדגימה-מטה מחזירה inter-sample peaks —
    # אותו לקח כמו tp-limit=0.84 ב-audio_mix), המעבר השני מהדק את התקרה ל-‎-1.6dB.
    # v9.38 (30.9.26) — מעבר שלישי ‎-4.4dB/attack 1ms: חומר אירוע עם צעקות קהל רוויות נשאר
    # TP≈+1.8 אחרי ‎-1.6 (overshoot של AAC על חומר קטום). נמדד על מאסטרס-פיין: אחרי ‎-4.4 → I=-15.5 TP=-3.8;
    # מעבר רביעי (גיין פיצוי + ‎-3dB) → I=-14.1 TP=-2.7. כלומר: קודם לרסן, אחר כך להחזיר עוצמה.
    for attempt, limit_db in enumerate((-1.0, -1.6, -4.4, -3.0)):
        limit = 10 ** (limit_db / 20)
        i, tp = measure_lufs(video)
        if i is None: return False, "מדידת loudness נכשלה"
        if abs(i - target) <= 0.5 and tp <= -0.8:
            # v8.8 — מדווח במפורש שלא היה קידוד. הטענה "שני דורות AAC" הופרכה
            # במדידה 30.7: ב-v2 המיקס נוחת בתוך הסבולת והשלב הזה הוא מדידה בלבד.
            # מספר בלי מקור אינו מספר, וגם "עלות" בלי מדידה אינה עלות.
            return True, (f"I={i:.1f} TP={tp:.1f} · "
                          + ("כבר בטווח — אפס קידוד אודיו" if attempt == 0
                             else f"יושר במעבר {attempt}"))
        gain = round(target - i, 2)
        tmp = str(video) + ".loud.mp4"
        r = sh(["ffmpeg", "-y", "-loglevel", "error", "-i", video,
                "-af", f"volume={gain}dB,aresample=176400,"
                       f"alimiter=limit={limit:.3f}:attack={5 if limit_db > -2 else 1}:release=60:level=disabled,aresample=48000",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", tmp])
        if r.returncode != 0: return False, r.stderr[-300:]
        Path(tmp).replace(video)
    i, tp = measure_lufs(video)
    # v9.38 — גיבוי: loudnorm דינמי (limiter TP מובנה). על חומר קטום ה-TP אחרי AAC לא דטרמיניסטי
    # (מאסטרס-פיין: אותו מעבר נתן TP ‎-2.7 ואז 0.0) — מנסים עד 3 תקרות ובודקים כל פעם.
    for tp_t in (-3.0, -3.5, -4.0):
        if abs(i - target) <= 1.2 and tp <= -0.8: break
        tmp = str(video) + ".loud.mp4"
        r = sh(["ffmpeg", "-y", "-loglevel", "error", "-i", video,
                "-af", f"loudnorm=I={target}:TP={tp_t}:LRA=11,aresample=48000",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", tmp])
        if r.returncode != 0: break
        ti, ttp = measure_lufs(tmp)
        if ti is not None and abs(ti - target) <= 1.2 and ttp <= -0.8:
            Path(tmp).replace(video); i, tp = ti, ttp
        else:
            Path(tmp).unlink(missing_ok=True)
    return (abs(i - target) <= 1.2 and tp <= -0.8), f"I={i:.1f} TP={tp:.1f}"

def deliver_spec(video, crf=23, max_mb=60.0):
    """v7.11 (26.7.26) — הבאת התוצר לתקן-העלאה: 1080x1920@30 crf23.

    שורש תקלה חוזרת: צריבת הכתוביות עובדת ב-crf16/veryfast (v7.8 — נמדד מהיר
    פי 2 באיכות זהה), ו-loudness עושה ‎-c:v copy. כלומר אף שלב לא הביא את
    הווידאו לתקן ההעלאה של הקאנון (crf23). בסרטון עם מצע בירולים רציף
    (הרבה תנועה) זה יצא 66-71MB ⇒ שער G5_format נכשל, ותוקן **ידנית** בכל
    ריצה. תיקון ידני חוזר = חוסר במנגנון. מעכשיו זה שלב בצנרת: דוחסים תמיד
    לתקן, וה-QA בודק תוצר שכבר עומד בו. אודיו ‎-c:a copy — ה-loudness שכבר
    יושר לא נוגעים בו שוב.
    """
    before_mb = Path(video).stat().st_size / 1e6
    tmp = str(video) + ".deliver.mp4"
    r = sh(["ffmpeg", "-y", "-loglevel", "error", "-nostdin", "-i", video,
            "-c:v", "libx264", "-crf", str(crf), "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "copy",
            "-movflags", "+faststart", tmp])
    if r.returncode != 0 or not Path(tmp).exists():
        return False, f"דחיסה לתקן העלאה נכשלה: {r.stderr[-200:]}"
    after_mb = Path(tmp).stat().st_size / 1e6
    if after_mb >= before_mb:      # כבר בתקן — לא מוסיפים דור קידוד לחינם
        Path(tmp).unlink(missing_ok=True)
        return True, f"{before_mb:.1f}MB — כבר בתקן, לא קודד מחדש"
    Path(tmp).replace(video)
    warn = "" if after_mb <= max_mb else f" ⚠️ עדיין מעל {max_mb:.0f}MB"
    return True, f"crf{crf}: {before_mb:.1f}MB → {after_mb:.1f}MB{warn}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--content-type", default="value")
    ap.add_argument("--brand", default="rel", choices=["rel", "personal", "oshia"],
                    help="סרטוני המועדון=rel (מתאר #871d1f); סרטוני הראל חיון=personal (מתאר #0077B6)")
    ap.add_argument("--music", default="auto")
    ap.add_argument("--music-lufs", type=float, default=-46.0,
                    help="v9.22 (10.9.26): -44→-46 (דיבור -52→-54). שתי הערות \"טיפה להנמיך\" באותו יום (על-הלוח, טיפ-אחד) + \"חוזר על עצמו, שווה לדייק במנגנון\"; מאז 23.7 — 14 הערות \"חזק מדי\" מול 0 \"חלש מדי\" (מלבד -46/דאקינג 9=-55 שהיה \"מעט נמוך\"). -54 הוא האמצע בין -55 (נמוך) ל--52 (חזק). v7.8 (25.7.26): ברירת המחדל הורדה -38→-46 על סמך ההתנהגות בפועל. "
                         "מתוך 40 הערות של הראל, 12 היו 'המוזיקה חזקה מדי / לא שומעים אותי' "
                         "ו-0 היו 'המוזיקה חלשה מדי'; בשלוש הפעמים שהוא קבע מפלס ידנית "
                         "באפליקציה הוא בחר -50/-46/-45 (ממוצע -47). ‎-38 היה ברירת מחדל "
                         "שכמעט תמיד תוקנה ⇒ ברירת המחדל הייתה שגויה. "
                         "v7.10 (25.7.26): כוילה שוב מ--46 ל--44 אחרי שהראל שמע את "
                         "התוצאה — 'המוזיקה מעט נמוכה מדי, צריך לאזן טיפה יותר שישמעו "
                         "אותה'. יחד עם עומק דאקינג 9→8, מפלס הדיבור עולה מ--55 ל--52 "
                         "(‏+3dB) — בטווח שהוא בחר ידנית בעבר. מכירה אמיתית: להעלות במפורש.")
    ap.add_argument("--no-duck", action="store_true",
                    help="מבטל דאקינג — מוזיקה במפלס קבוע לכל אורך הסרטון (ישן, לא מומלץ). "
                         "תוקן 23.7.26 r2 (פידבק חוזר: '13/15 סרטונים אחרונים ניגנו מוזיקה "
                         "קבועה בלי ירידה בזמן דיבור — זה השורש, לא הז'אנר'): דאקינג הופך "
                         "לברירת מחדל. השתמש בדגל הזה רק אם הראל אישר מפורשות מוזיקה קבועה "
                         "לסרטון הזה.")
    ap.add_argument("--speech-lufs", type=float, default=None,
                    help="מפלס מוזיקה בזמן דיבור (דאקינג); ברירת מחדל music-lufs-9 "
                         "(‏-6→-9 ב-23.7.26; רוכך ל--8 ב-v7.10 אחרי 'המוזיקה מעט נמוכה מדי')")
    ap.add_argument("--tp-limit", type=float, default=0.84,
                    help="ceiling ל-alimiter true-peak ב-audio_mix (0-1, 0.84≈-1.5dB). הורד ל-0.7-0.75 "
                         "אם loudness נכשל על TP חם (לקח 20.7 r4: דאקינג עם מדרגת-גיין קשה עלול "
                         "ליצור inter-sample peak שחומק מ-alimiter הפשוט ב-loudness_align, שאינו "
                         "oversampled כמו זה שב-audio_mix עצמו).")
    ap.add_argument("--audio-block", type=float, default=0.6,
                    help="סף gate לשקט חוסם (ש). כוילה 0.9→0.6 ב-20.7 (דד-אייר חוזר) אך זה יכול "
                         "להכריח cuts שחותכים לתוך מילים (לקח 20.7 r4, הראל תפס בפועל 2 מילים "
                         "חתוכות). אם gate חוסם המון פערים 0.6-0.8ש שהם פאוזות טבעיות ולא דד-אייר "
                         "אמיתי — עדיף להרפות כאן זמנית (0.8-0.9) מאשר להוסיף cuts שמסתכנים בחיתוך "
                         "דיבור. עדיפות: לא-לחתוך-מילה > אפס-שקט-מושלם.")
    ap.add_argument("--broll-plan", help="broll_plan.json מפורש — עוקף את הבחירה האוטומטית")
    ap.add_argument("--broll-audience", default="", help="דוספיט/נשים/גברים — ברירת מחדל: קהל כללי (לא דוספיט)")
    ap.add_argument("--broll-n", type=int, default=2, help="כמה קליפי בירול לתכנן בבחירה האוטומטית")
    ap.add_argument("--no-broll", action="store_true", help="דלג על בירול גם ב-conversion (עקיפה מפורשת)")
    ap.add_argument("--title", help="כותרת קאבר (Ploni Bold) — אם ניתן, --subtitle הוא חובה (brand=rel): "
                    "קאברים תמיד 2 שורות (הראל 23.7.26), לא כותרת בלבד")
    ap.add_argument("--subtitle", default="", help="תת-כותרת קאבר (Studentit) — חובה יחד עם --title ל-brand=rel")
    ap.add_argument("--skip-whisper", action="store_true")
    ap.add_argument("--no-recut", action="store_true")
    ap.add_argument("--refinish", action="store_true",
                    help="גימור מהיר (v7.4, בקשת הראל 24.7): מדלג על recut/whisper/tighten/gate "
                         "ומשתמש בציר המהודק הקיים (EXPORT_TIGHT + whisper_export_tight). "
                         "מריץ מחדש רק reconcile (קולט תיקוני תמליל) → בירול → מוזיקה → "
                         "כתוביות → loudness → QA. דקות במקום עשרות דקות — לתיקוני "
                         "כתוביות/מוזיקה/בירולים מהאפליקציה בלי תלות בקלאוד.")
    ap.add_argument("--intro-keep", type=float, default=0.0,
                    help="הגנה על פתיח ויזואלי: לא להדק שקט ב-N השניות הראשונות")
    ap.add_argument("--xfade", type=float, default=0.0,
                    help="קרוספייד קצר (שניות) בכל גבול חיתוך פנימי ב-edl_cut, נגד 'פלאש' קפיצת-פריים (לקח 19.7)")
    ap.add_argument("--whisper-model", default="auto",
                    help="auto = ivrit-ai/whisper-large-v3-turbo-ct2 + VAD (v7.8, 25.7.26). "
                         "נמדד מול medium על 6 סרטונים עם תמליל מתוקן: פי ~2 מהר וכמחצית "
                         "השגיאות (WER 7.5% מול 15.8% בסרטון הייחוס). small/medium/large-v3 "
                         "עדיין נתמכים בשם מפורש. בנוסף asr-glossary.json לשיבושים חוזרים.")
    ap.add_argument("--no-map-words", action="store_true",
                    help="מבטל את מיפוי המילים מ-whisper_raw ומאלץ תמלול חוזר על הקאט "
                         "(v7.9 — ברירת המחדל היא מיפוי; זה הדגל לחירום/דיבוג בלבד)")
    ap.add_argument("--no-fixed-intro", action="store_true",
                    help="מבטל זיהוי/הרכבה אוטומטית של אפקטי פורמט קבועים "
                         "(ניפוץ מיתוסים וכו') — v7.9")
    ap.add_argument("--no-full-intro", action="store_true",
                    help="לא להדביק פתיח קבוע מלא (מאסל מן) גם אם זוהה — v9.19")
    ap.add_argument("--hook-fx", choices=("auto", "on", "off"), default="auto",
                    help="v9.46 ארגז העריכה של ההוק (tools/hook_fx.py): תנועות מצלמה/מעברים/צלילים ב-0-4ש "
                         "מתוך HOOK_PLAN.json[edit]. auto = רץ כשיש בלוק edit ו-finish_prefs.hook_fx.enabled אינו "
                         "false (כשל = אזהרה, יוצא בלי) · on = חובה · off = מדלג")
    ap.add_argument("--motion", choices=("auto", "on", "off"), default="auto",
                    help="v9.37 שכבת Motion Graphics (tools/motion_build.py). auto = רץ כשיש W/motion_plan.json "
                         "ו-finish_prefs.motion.enabled אינו false (כשל = אזהרה, הסרטון יוצא בלי MG) · "
                         "on = חובה (כשל עוצר את הגימור) · off = מדלג")
    ap.add_argument("--no-notefix", action="store_true",
                    help="מבטל את שלב notefix (החלת תיקוני הכתיב שהראל כתב בהערות ישירות "
                         "על התמליל, v7.8). ברירת מחדל: פועל.")
    ap.add_argument("--tail-keep", type=float, default=0.3,
                    help="כמה שקט-סיום להשאיר אחרי המילה האחרונה לפני חיתוך (tighten). "
                         "כויל 0.5→0.3 ב-20.7.26 (הראל: 'כמה שפחות שקט ככה טוב') — גם נשאר מתחת "
                         "לסף edge_silence-סיום ב-finish_local.py (0.4ש) כך שלא נכשל את הגייט תמיד "
                         "על שארית קבועה. אם עדיין נכשל על שארית קצרה יותר — להנמיך עוד ל-0.2-0.25.")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="speed ramp אחיד על כל הסרטון (tighten_finish --speed) — רק אחרי מיצוי "
                         "חיתוכים, ורק לפי בקשה מפורשת של הראל (לקח 19.7). 1.1-1.15 טווח סביר.")
    # ── V2 שלב 2 — מנוע רינדור ──
    # ברירת המחדל נשארת v1 עד שהשער `tools/bench/render_ab.py` עובר על 5 סרטונים.
    # החלטה מודעת: מנוע רינדור חדש הוא הסיכון ההנדסי הגדול בפרויקט הזה, ולכן הוא
    # נכנס מאחורי דגל ומוכיח זהות לפני שהוא מחליף התנהגות.
    ap.add_argument("--render-engine", choices=("v1", "v2"), default="v1",
                    help="v1 = השרשרת ההיסטורית (4-7 קידודים). v2 = גרף סגמנטים + "
                         "מטמון תוכן (דור וידאו אחד; כתוביות ובירול נצרבים בסגמנט, "
                         "המוזיקה בסוף). ראה relvid/render.py.")
    # ── Visual Hook Engine (11.9.26) — אופציונלי, ברירת מחדל off ─────────────
    # off: המסלול הישן בדיוק (אפס קבצים חדשים, אפס קידוד) · shadow: ניתוח+הצעה
    # בלי לשנות פיקסלים · auto: רק קוהורט מאושר במדיניות (כרגע אין). העדפת
    # האפליקציה (finish_prefs.visual_hook) גוברת על הדגל; כיבוי מפורש גובר על הכול.
    ap.add_argument("--visual-hook", choices=("off", "shadow", "auto"), default=None,
                    help="Visual Hook Engine: off (ברירת מחדל) / shadow / auto")
    ap.add_argument("--visual-hook-plan", default=None,
                    help="visual_hook_plan.json קפוא ומאומת (עוקף בחירה, לא עוקף אימות)")
    ap.add_argument("--prepare-visual-hook-review", action="store_true",
                    help="פנימי: הכנה דטרמיניסטית + מועמד פתיחה חזותית, ועצירה לפני רינדור/מוזיקה/FINAL")
    ap.add_argument("--render-jobs", type=int, default=None,
                    help="כמה סגמנטים לרנדר במקביל (ברירת מחדל: מחצית הליבות, מקס 4)")
    ap.add_argument("--no-verify-asr", action="store_true",
                    help="לא להריץ תמלול אימות ברקע (G6b יהיה אזהרה במקום שער חוסם)")
    # v9.25 (הראל 19.9.26: "לא כל סרטון חייב להיות מוגבל עד 60 שניות"): תקרת ה-60ש
    # בוטלה. הגבול הקשיח הוא length_policy.HARD_MAX (180ש); יעד רך לפי סוג תוכן.
    ap.add_argument("--allow-long", "--allow-over-60", dest="allow_long", action="store_true",
                    help="עוקף את הגבול הקשיח של length_policy (180ש) — רק באישור מפורש של הראל. "
                         "--allow-over-60 נשאר ככינוי לאחור ולא נדרש יותר עד 180ש.")
    ap.add_argument("--length-reason", default=None,
                    help="נימוק אורך (נשמר ל-project_manifest.json.length_reason) — חובה-רכה "
                         "מעל סף-הנימוק של סוג התוכן (המרה 60ש · ערך/סיפור 90ש · פודקאסט 120ש)")
    ap.add_argument("--max-word-dur", type=float, default=1.3,
                    help="סף gate ל-dead_air_spans (משך מילה מוצג לפני שנחשב 'בולע דד-אייר'). "
                         "ברירת מחדל 1.3ש חוסמת תמיד (לא ניתן לעקיפה דרך --audio-block). "
                         "העלה זמנית (למשל 1.4-1.5) רק אחרי אימות ידני שזה false-positive — "
                         "מונח קליני/מילה ארוכה שבאמת לוקחת יותר מ-1.3ש לומר, לא שקט אמיתי "
                         "(21.7, מאסל-מן-רוטטור-קאף: 'אינפרספינטוס' התמזג מ-2 מילות whisper ל-1.32ש).")
    ap.add_argument("--edge-block", type=float, default=0.4,
                    help="סף gate ל-edge_silence (שקט קצה פתיחה/סיום, אחרי tighten+speed). ברירת מחדל 0.4ש "
                         "חוסמת תמיד (לא ניתן לעקיפה דרך --tail-keep/--intro-keep בלבד — לקח 21.7: "
                         "עם --speed, tighten לא תמיד מוצא/מקצץ את כל שארית השקט בקצה). הרפיה זמנית "
                         "(0.6-1.0) בטוחה מעצם ההגדרה — נמדד תמיד אחרי המילה האחרונה שזוהתה.")
    ap.add_argument("--director", action="store_true",
                    help="V2: להריץ את מנוע ההחלטה בחמישה פאסים לפני הגימור — מודד מרחב "
                         "מועמדים, מייצר תוכנית מנומקת עם ביטחון וסיכון, ומקמפל edl.json")
    ap.add_argument("--director-backend", choices=("api", "chat", "replay"), default=None,
                    help="api=מפתח · chat=כרטיסי בקשה לדיסק (בלי מפתח) · replay=מה-cache בלבד")
    ap.add_argument("--director-threshold", type=float, default=7.5,
                    help="סף ציון האיכות. מתחתיו — חזרה אוטומטית לפאס התכנון")
    ap.add_argument("--director-max-loops", type=int, default=2)
    # ── כפיפות ההידוק לשיפוט הבמאי (30.7.26) ──
    # השורש שנמדד: הבמאי הפיק 57.12ש/9 קטעים, ואז `tighten` — מנוע הכללים
    # האקוסטי הישן — גזם עוד 4.92ש ב-11 פערים והפך את התוצר ל-52.40ש/12 קטעים.
    # כלומר הקצב הסופי נקבע ע"י המנוע שהחלפנו, ושיפוט הבמאי לא הגיע למסך.
    # מאז שגבולות המילים מוצמדים לאנרגיה (`candidates.snap_words_to_audio`),
    # כל שקט אקוסטי גלוי לבמאי — ולכן ההידוק מיותר תחת `--director`.
    ap.add_argument("--tighten", choices=("auto", "on", "off"), default="auto",
                    help="auto = כבוי כש---director פעיל (הבמאי קובע כל פער), דלוק אחרת. "
                         "on = לכפות הידוק גם תחת הבמאי (לניפוי בלבד — ידרוס את התוכנית). "
                         "off = לכבות תמיד.")
    # v9.15 (הראל 17.8.26: "רוב הסרטון רץ בלי צורך בחיתוכים" + "מגבירים את קצב
    # הסרטון ל-1.15"). שורש הליקוי: `--speed` נאכף רק במסלול ההידוק, ולכן תוכנית
    # שהבמאי (או הראל באפליקציה) קבע פער-אחר-פער **חייבת** לעבור דרך המנוע
    # האקוסטי כדי לקבל האצה — והוא חתך שם 8 שתיקות נוספות (0.093/ש → 0.259/ש,
    # מעל התקרה). min-sil גבוה הופך את שלב ההידוק ל-speed-only: אותו מסלול,
    # בלי חיתוך שתיקות. [[lesson: speed_without_retightening]]
    # v9.20 (פידבק אלי 21.8.26 — L43). היו מקובעים 0.12/-40 בקריאה ל-tighten_finish.
    # ברירות המחדל כאן זהות לערכים שהיו, כך שבלי דגל מפורש ההתנהגות לא משתנה.
    # למה בכלל: הפערים שאלי סימן (0.25-0.48ש) אינם שקט ב--40dB — יש בהם נשימה ורעש
    # חדר, ולכן המהדק האקוסטי פשוט לא רואה אותם. נמדד על ת1-סטודנטים: min-sil 0.20
    # לבדו הסיר פער אחד מתוך חמישה. הרצפה היא --noise, לא --min-sil.
    # ⚠️ --protect-words + --word-margin 0.15 נשארים דלוקים תמיד — הם ההגנה מחיתוך
    # של תחילת מילה רכה, וזו הסכנה האמיתית בהנמכת הרצפה.
    ap.add_argument("--keep-sil", type=float, default=0.12,
                    help="כמה שקט להשאיר בכל פער שנחתך. 0.08 מהדק יותר; מתחת ל-0.06 "
                         "הדיבור מתחיל להישמע קטוע.")
    ap.add_argument("--noise", type=float, default=-40.0,
                    help="רצפת הרעש (dB) שמתחתיה נחשב שקט. -40 = ברירת המחדל "
                         "ההיסטורית; -32 תופס גם נשימה ורעש חדר (L43).")
    ap.add_argument("--min-sil", type=float, default=0.30,
                    help="סף שקט מינימלי לחיתוך בהידוק. ערך גבוה (99) = הידוק "
                         "speed-only: מחיל --speed בלי לחתוך אף שתיקה — לשימוש "
                         "כשתוכנית הפערים כבר נקבעה (במאי/הראל).")
    a = ap.parse_args()

    W = Path(a.workdir).resolve()
    st = Status(W)
    INPUT, EDL = W / "INPUT.mp4", W / "edl.json"
    EXPORT, MIXED, FINAL = W / "EXPORT.mp4", W / "MIXED.mp4", W / "FINAL.mp4"
    # v7: תוצר חלקי לא מסומן FINAL — עובדים על FINAL_PENDING עד QA PASS
    PENDING = W / "FINAL_PENDING.mp4"
    report = [f"# FINISH REPORT — {W.name} ({time.strftime('%d.%m.%Y %H:%M')})", ""]

    def fail(msg, code=1):
        report.append(f"❌ {msg}")
        (W / "FINISH_REPORT.md").write_text("\n".join(report), encoding="utf-8")
        st.finish(False, msg)
        sys.exit(code)

    # ── V2: מנוע ההחלטה. רץ לפני הגימור ומייצר את edl.json במקום edl_build.
    #    כישלון כאן לא נוגע במדיה — אין edl, אין גימור.
    if a.director:
        if not INPUT.exists():
            fail("חסר INPUT.mp4 — אין מה למדוד")
        if not (W / "whisper_raw.json").exists():
            # מרחב המועמדים נבנה סביב גבולות מילים. בלי תמלול ברמת מילה אין מרחב,
            # ואז המודל היה חוזר לנחש זמנים — בדיוק מה ש-V2 בא למנוע.
            fail("חסר whisper_raw.json — מנוע ההחלטה רץ אחרי התמלול, לא לפניו")
        t_dir = time.time()
        if not (W / "candidates.json").exists():
            r = sh([sys.executable, str(HERE / "candidates.py"), "--workdir", str(W)])
            if r.returncode:
                fail(f"מרחב המועמדים נכשל: {(r.stderr or r.stdout or '')[-400:]}")
        # v9.13 — למידה מ-n=1: הלקחים + דפוסי התיקון של הראל (cohort) נכנסים
        # לפיילוד של הבמאי. best-effort ולא-חוסם: בלי הקובץ הבמאי פשוט רץ
        # כמו קודם. הקובץ נכתב פעם אחת לפרויקט (יציבות digest בתוך הפרויקט).
        r = sh([sys.executable, str(HERE / "director_lessons.py"),
                "--workdir", str(W)], timeout=120)
        if r.returncode == 0:
            report.append(f"- 🧠 לקחים לבמאי: {(r.stdout or '').strip()[:150]}")
        else:
            report.append(f"- ⚠️ הכנת לקחים לבמאי נכשלה (לא חוסם): "
                          f"{(r.stderr or r.stdout or '')[-120:]}")
        cmd = [sys.executable, str(HERE / "edit_director.py"), "run", "--workdir", str(W),
               "--threshold", str(a.director_threshold),
               "--max-loops", str(a.director_max_loops)]
        if a.director_backend:
            cmd += ["--backend", a.director_backend]
        r = sh(cmd)
        print(r.stdout or "", end="")
        if r.returncode == 2:
            # backend=chat — נכתב כרטיס בקשה. עצירה מכוונת, לא כישלון.
            report.append("- ⏸ מנוע ההחלטה ממתין לתשובת מודל (backend=chat). "
                          "ראו ai_requests/ — הריצו שוב אחרי שהתשובה נשמרה ב-ai_responses/.")
            (W / "FINISH_REPORT.md").write_text("\n".join(report), encoding="utf-8")
            st.finish(False, "ממתין לתשובת מנוע ההחלטה")
            sys.exit(2)
        if r.returncode:
            fail(f"מנוע ההחלטה נכשל: {(r.stderr or r.stdout or '')[-400:]}")
        _dr = json.loads((W / "director_run.json").read_text(encoding="utf-8"))
        report.append(
            f"- 🎬 מנוע החלטה V2: {_dr['validator']['n_decisions']} החלטות → "
            f"{_dr['validator']['n_cuts']} חיתוכים · {_dr['validator']['kept_dur']}ש · "
            f"ציון {_dr['final_score']} (סף {_dr['threshold']}) · "
            f"{_dr['review_loops']} סבבי ביקורת · {time.time()-t_dir:.1f}ש")
        if not _dr.get("passed"):
            report.append("- ⚠️ הציון נשאר מתחת לסף — התוצר מסומן ולא מוסתר.")

    if not INPUT.exists() or not EDL.exists():
        fail("חסר INPUT.mp4 או edl.json")

    # v7.4 — העדפות גימור ידניות מהאפליקציה (project_manifest.json → finish_prefs).
    # הראל בחר בעצמו טראק/עוצמה/בירולים ⇒ ההעדפה גוברת על דגלי ה-CLI (הדגלים הם
    # ברירת המחדל שקלאוד/ה-runner מספקים; ההעדפה היא בחירה מפורשת של הראל).
    mpath = W / "project_manifest.json"
    manifest = {}
    if mpath.exists():
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    # v9.25 — נימוק אורך: CLI גובר ונשמר במניפסט; אחרת מהמניפסט.
    if a.length_reason:
        manifest["length_reason"] = a.length_reason
        try:
            mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass
    a.length_reason = a.length_reason or manifest.get("length_reason")
    _prefs = manifest.get("finish_prefs") or {}
    mus_pref = _prefs.get("music") or {}
    br_pref = _prefs.get("broll") or {}
    if mus_pref.get("track"):
        cand = Path(mus_pref["track"])
        if not cand.is_absolute():
            cand = MUSIC_DIR / mus_pref["track"]
        if cand.exists():
            a.music = str(cand)
            report.append(f"- 🎵 טראק נבחר ידנית באפליקציה: {cand.name}")
        else:
            report.append(f"- ⚠️ הטראק שנבחר באפליקציה לא נמצא ({mus_pref['track']}) — נופל לבחירה אוטומטית")
    elif a.refinish:
        # גימור מהיר בלי בחירת טראק מפורשת — שומרים על אותה מנגינה מהריצה הקודמת
        # (אחרת כל refinish היה מחליף מנגינה ושורף את הרוטציה). fallback לפרויקטים
        # מלפני v7.4 (אין track_auto): מחלצים את שם הטראק מ-FINISH_REPORT.md —
        # באג בפועל 24.7 ("עיסוי רפואי"): שינוי ווליום החליף מנגינה כי לא היה עוגן.
        _sticky = mus_pref.get("track_auto")
        if not (_sticky and (MUSIC_DIR / _sticky).exists()):
            _sticky = None
            try:
                _rep_txt = (W / "FINISH_REPORT.md").read_text(encoding="utf-8")
                _mm = re.findall(r"- מוזיקה: (\S+\.mp3)", _rep_txt)
                if _mm and (MUSIC_DIR / _mm[-1]).exists():
                    _sticky = _mm[-1]
            except Exception:
                pass
        if _sticky:
            a.music = str(MUSIC_DIR / _sticky)
            report.append(f"- 🎵 refinish: נשמרת המנגינה הקיימת ({_sticky}) — החלפה רק בבקשה מפורשת")
    if mus_pref.get("music_lufs") is not None:
        try:
            a.music_lufs = float(mus_pref["music_lufs"])
            report.append(f"- 🎚 עוצמת מוזיקה נקבעה ידנית באפליקציה: {a.music_lufs} LUFS")
        except (TypeError, ValueError):
            pass
    if mus_pref.get("duck") is False:
        a.no_duck = True
    elif mus_pref.get("duck") is True:
        a.no_duck = False
    if br_pref.get("mode") == "off":
        a.no_broll = True
    manual_broll_items = (br_pref.get("items") or []) if br_pref.get("mode") == "manual" else []
    vh_pref = _prefs.get("visual_hook") or {}
    vh_mode = vh_pref.get("mode") or a.visual_hook or "off"
    if a.visual_hook_plan or a.prepare_visual_hook_review:
        vh_mode = vh_mode if vh_mode != "off" else "shadow"

    def _save_manifest():
        try:
            manifest["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            tmpm = mpath.with_suffix(".json.tmp")
            tmpm.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
            tmpm.replace(mpath)
        except Exception:
            pass

    # קאברים תמיד ב-2 שורות (הראל 23.7.26): כותרת (Ploni Bold) + תת-כותרת (Studentit) —
    # אף פעם לא קאבר של שורה אחת. אם ניתנה כותרת בלי תת-כותרת, זו טעות בקריאה ל-pipeline
    # (Claude שכח לספק תת-כותרת), לא ברירת מחדל תקינה — נכשל מוקדם וברור במקום להפיק
    # קאבר חד-שורתי בשקט.
    if a.title and a.brand == "rel" and not (a.subtitle or "").strip():
        fail("קאבר דורש גם --title וגם --subtitle (חוק קבוע: קאברים תמיד 2 שורות, "
             "כותרת+תת-כותרת בשני הפונטים השונים שלנו — Ploni Bold + Studentit). "
             "ספק --subtitle או השמט --title כדי לדלג על שלב הקאבר.")

    WORDS = W / "words_final.json"
    KEEPS = W / "tight_keeps.json"
    SENT_TIGHT = None
    # v8.6: _speed הוגדר עד כה רק בענף המסלול-המלא, ולכן כל שימוש בו אחרי ה-if/else
    # היה NameError במסלול --refinish. מאותחל כאן לשני המסלולים.
    _speed = a.speed if (a.speed and a.speed > 0) else 1.0
    if a.refinish:
        # ⚡ v7.4 — גימור מהיר: הקאט המאושר לא השתנה, רק שכבות הגימור (תמליל/מוזיקה/
        # בירול). משתמשים בציר המהודק הקיים ומריצים reconcile מחדש כדי לקלוט תיקוני
        # תמליל טריים מהאפליקציה — בלי recut/whisper/tighten (החלקים הכבדים).
        st.step("refinish")
        TIGHT = W / "EXPORT_TIGHT.mp4"
        WEXP = W / "whisper_export_tight.json"
        if not TIGHT.exists() or not WEXP.exists():
            fail("גימור מהיר (--refinish) דורש ריצת גימור מלאה קודמת — חסר "
                 "EXPORT_TIGHT.mp4 / whisper_export_tight.json")
        _exp_full = W / "EXPORT.mp4"
        if _exp_full.exists() and _exp_full.stat().st_mtime > TIGHT.stat().st_mtime + 2:
            fail("EXPORT_TIGHT.mp4 ישן מ-EXPORT.mp4 — הציר המהודק שייך לריצה קודמת (L131). "
                 "הריצו גימור מלא (בלי --refinish) כדי לבנות אותו מחדש.")
        EXPORT = TIGHT
        dur = ffdur(EXPORT)
        st.done_step("refinish", f"ציר מהודק קיים ({dur:.1f}ש) — recut/whisper/tighten דולגו")
        report.append(f"- ⚡ גימור מהיר: ציר מהודק קיים ({dur:.1f}ש) — recut/whisper/tighten דולגו")
        run_notefix(W, st, report, enabled=not a.no_notefix)
        st.step("reconcile")
        txt = next((p for p in (W / "edited.txt", W / "correct_transcript.txt") if p.exists()), None)
        if txt is None:
            txt = W / "_whisper_text.txt"
            wh = json.loads(WEXP.read_text(encoding="utf-8"))
            txt.write_text(" ".join(x["word"] for x in wh), encoding="utf-8")
            report.append("- ⚠️ אין טקסט מתוקן — כתוביות לפי טקסט whisper גולמי")
        r = sh(["python3", HERE / "align_reconcile.py", WEXP, txt, WORDS, "--end", f"{dur:.2f}"])
        if r.returncode != 0: fail(f"reconcile נכשל: {r.stderr[-300:]}")
        st.done_step("reconcile", (r.stdout.strip().splitlines() or [""])[0][:120])
        _st_path = W / "sentences_tight.json"
        SENT_TIGHT = _st_path if _st_path.exists() else None
    else:
        # 1. recut
        st.step("recut")
        if a.no_recut and EXPORT.exists():
            st.done_step("recut", "(קיים, דולג)")
        else:
            cut_cmd = ["python3", HERE / "edl_cut.py", "--video", INPUT, "--edl", EDL, "--out", EXPORT]
            if a.xfade and a.xfade > 0:
                cut_cmd += ["--xfade", str(a.xfade)]
            r = sh(cut_cmd)
            if r.returncode != 0: fail(f"edl_cut נכשל: {r.stdout[-200:]}{r.stderr[-200:]}")
            st.done_step("recut", r.stdout.strip()[-120:])
        dur = ffdur(EXPORT)
        report.append(f"- קאט מאושר: {dur:.1f}ש")

        # 2. מילים על ציר הקאט (לפני ההידוק — כדי שההידוק ידע איפה יש דיבור)
        # v7.9: **לא מתמללים שוב.** החיתוך הוא טרנספורמציה ידועה, אז ממפים את
        # whisper_raw.json (ציר INPUT) לציר ה-EXPORT דרך keep_segments.
        # שורש: 25.7.26 ריצה שנייה של Whisper על ה-EXPORT השמיטה משפט שלם שהתמלול
        # על ה-INPUT דווקא תפס נכון — הכתוביות איבדו 3.3ש דיבור בלי שאף שער תפס.
        # מיפוי = דטרמיניסטי, מיידי, ואי אפשר "לאבד" בו מילים בלי שזה יופיע בסטטיסטיקה.
        st.step("words")
        WEXP = W / "whisper_export.json"
        # v9.1 — פאס ההגהה (`--director`) כותב `words_corrected.json`: אותם
        # תזמונים בדיוק, טקסט מתוקן. הוא המקור לכתוביות; `whisper_raw.json`
        # נשאר בלתי-נגוע כראיית ASR עבור G6b.
        _corr = W / "words_corrected.json"
        RAW = _corr if _corr.exists() else (W / "whisper_raw.json")
        if _corr.exists():
            _fx = json.loads((W / "transcript_fix.json").read_text(encoding="utf-8")) \
                if (W / "transcript_fix.json").exists() else {}
            report.append(f"- ✍️ הגהה: {len(_fx.get('applied') or [])} תיקוני תמלול הוחלו "
                          f"({len(_fx.get('flagged') or [])} מילים נבדקו מול הלקסיקון)")
        mapped_ok = False
        if not a.no_map_words and RAW.exists():
            try:
                sys.path.insert(0, str(HERE))
                from relvid.edl_utils import map_words_to_keeps
                raw_words = json.loads(RAW.read_text(encoding="utf-8"))
                keeps_edl = json.loads(EDL.read_text(encoding="utf-8"))["keep_segments"]
                mw, stats = map_words_to_keeps(raw_words, keeps_edl)
                # v9.16 — כיול הציר לאורך הקאט **בפועל**. שורש שנמדד 18.8.26:
                # map_words_to_keeps סוכם את משכי ה-keep המתוכננים, בעוד edl_cut
                # מעגל כל מקטע כלפי מעלה לגבול פריים — כחצי פריים לתפר. הפער
                # מצטבר לאורך הסרטון ולכן הכתוביות מקדימות, יותר ויותר, ביחס
                # ישר למספר התפרים: 6 תפרים → ‎-0.13ש · 11 תפרים → ‎-0.25ש
                # (G6c דיווח את זה בכל 4 הסרטונים ואף אחד לא חיבר את הנקודות).
                # מתיחה לינארית לאורך שנמדד מסלקת את ההסחה השיטתית; מה שנשאר
                # הוא רעש של עד פריים אחד. [[lesson: word_map_uses_planned_length]]
                _planned = sum(float(k["end"]) - float(k["start"]) for k in keeps_edl)
                if _planned > 0 and mw and abs(dur / _planned - 1.0) <= 0.02:
                    _sc = dur / _planned
                    for _w in mw:
                        _w["start"] = round(float(_w["start"]) * _sc, 3)
                        _w["end"] = round(float(_w["end"]) * _sc, 3)
                    report.append(f"- 🎯 כיול ציר המילים לאורך הקאט בפועל: ×{_sc:.5f} "
                                  f"({_planned:.2f}ש מתוכננות → {dur:.2f}ש בפועל)")
                if mw and mw[-1]["end"] <= dur + 1.0:
                    WEXP.write_text(json.dumps(mw, ensure_ascii=False, indent=1), encoding="utf-8")
                    st.done_step("words", f"מופו מ-whisper_raw: {stats['out']}/{stats['in']} "
                                          f"(נחתכו {stats['dropped']})")
                    report.append(f"- 🗣 מילים: מיפוי דטרמיניסטי מהתמלול המלא "
                                  f"({stats['out']}/{stats['in']} מילים) — בלי תמלול חוזר")
                    mapped_ok = True
                else:
                    report.append("- ⚠️ מיפוי המילים לא עבר בדיקת שפיות — נופלים לתמלול מחדש")
            except Exception as e:
                report.append(f"- ⚠️ מיפוי המילים נכשל ({e}) — נופלים לתמלול מחדש")
        if not mapped_ok:
            if a.skip_whisper and WEXP.exists():
                st.done_step("words", "(whisper קיים, דולג)")
            else:
                if not WHISPER_PY.exists(): fail("venv whisper לא נמצא במק")
                r = sh([WHISPER_PY, HERE / "align_words.py", EXPORT, WEXP, a.whisper_model, "he"],
                       timeout=3600)
                if r.returncode != 0 or not WEXP.exists():
                    fail(f"whisper נכשל: {r.stderr[-300:]}")
                st.done_step("words", "תמלול מחדש על הקאט")

        # 3. reconcile עם הטקסט המתוקן (על ציר ה-EXPORT)
        run_notefix(W, st, report, enabled=not a.no_notefix)
        st.step("reconcile")
        txt = next((p for p in (W / "edited.txt", W / "correct_transcript.txt") if p.exists()), None)
        if txt is None:
            txt = W / "_whisper_text.txt"
            wh = json.loads(WEXP.read_text(encoding="utf-8"))
            txt.write_text(" ".join(x["word"] for x in wh), encoding="utf-8")
            report.append("- ⚠️ אין טקסט מתוקן — כתוביות לפי טקסט whisper גולמי")
        r = sh(["python3", HERE / "align_reconcile.py", WEXP, txt, WORDS, "--end", f"{dur:.2f}"])
        if r.returncode != 0: fail(f"reconcile נכשל: {r.stderr[-300:]}")
        st.done_step("reconcile", r.stdout.strip().splitlines()[0][:120])

        # 3.5. הידוק אקוסטי מודע-דיבור — תזמוני whisper מרופדים ולא רואים שקט אמיתי,
        #      אבל silencedetect לבדו חותך דיבור שקט (לקח 19.7, ריצה 3). לכן:
        #      protect-words=whisper — שקט שחופף מילה לא נחתך; ותזמוני המילים ממופים
        #      מחדש לציר המהודק (בלי ריצת whisper שנייה).
        # ── האם ההידוק רץ בכלל (30.7.26) ──
        # השורש שנמדד: הבמאי הפיק 57.12ש/9 קטעים, ואז `tighten` — מנוע הכללים
        # האקוסטי הישן — גזם עוד 4.92ש ב-11 פערים (52.40ש/12 קטעים). כלומר הקצב
        # הסופי נקבע ע"י המנוע שהוחלף, ושיפוט הבמאי לא הגיע למסך. מאז שגבולות
        # המילים מוצמדים לאנרגיה (candidates.snap_words_to_audio) כל שקט אקוסטי
        # גלוי לבמאי — ולכן ההידוק מיותר תחת --director.
        _tighten_on = (a.tighten == "on") or (a.tighten == "auto" and not a.director)
        if not _tighten_on:
            st.step("tighten")
            if a.speed and abs(a.speed - 1.0) > 0.001:
                fail("--speed דורש את שלב ההידוק. הריצו --tighten on או קצרו תוכן בתוכנית.")
            if dur > LP.HARD_MAX and not a.allow_long:
                fail(f"התוכנית מייצרת {dur:.1f}ש — מעל הגבול הקשיח {LP.HARD_MAX:.0f}ש "
                     f"(מעל 3 דק׳ אינסטגרם לא מפיץ לקהל חדש). לקצר בתוכנית הבמאי "
                     f"(או --allow-long במודע).")
            # tight_keeps זהותי — שכבת הסנכרון, מנוע הרינדור ו-cut_qa ממשיכים לעבוד;
            # הציר המהודק **הוא** ציר הקאט.
            TIGHT = EXPORT
            # L131 (9.10.26): EXPORT_TIGHT.mp4 על הדיסק חייב להיות הציר הזה — אחרת --refinish הבא
            # ממחזר ציר מהודק ישן מריצה קודמת (מונטאז' TERRA: 40.8ש ישן מול 47.9ש, כתוביות זזו 7ש).
            _tf = W / "EXPORT_TIGHT.mp4"
            if Path(EXPORT).resolve() != _tf.resolve():
                try:
                    _tf.unlink(missing_ok=True)
                    os.link(EXPORT, _tf)
                except OSError:
                    shutil.copy2(EXPORT, _tf)
            KEEPS.write_text(json.dumps([{"start": 0.0, "end": round(dur, 3)}],
                                        ensure_ascii=False, indent=1), encoding="utf-8")
            WORDS_PRE = W / "words_pre_tight.json"
            WORDS_PRE.write_text(WORDS.read_text(encoding="utf-8"), encoding="utf-8")
            WEXP_T = W / "whisper_export_tight.json"
            WEXP_T.write_text(Path(WEXP).read_text(encoding="utf-8"), encoding="utf-8")
            WEXP = WEXP_T
            keeps = [{"start": 0.0, "end": round(dur, 3)}]
            _speed = 1.0

            def remap_t(t):                       # זהות
                return t

            def remap_words(src, dst):
                Path(dst).write_text(Path(src).read_text(encoding="utf-8"), encoding="utf-8")
            _why = "הבמאי קובע כל פער" if a.director else "כובה מפורשות"
            st.done_step("tighten", f"דולג — {_why}")
            report.append(f"- ⏭ הידוק אקוסטי דולג ({_why}) — הציר נשאר {dur:.1f}ש כפי שתוכנן")
        else:
            st.step("tighten")
            TIGHT = W / "EXPORT_TIGHT.mp4"
            tight_cmd = ["python3", HERE / "tighten_finish.py", "--in", EXPORT, "--out", TIGHT,
                    "--keep-sil", str(a.keep_sil), "--noise", str(a.noise), "--min-sil", str(a.min_sil),
                    "--protect-words", WEXP, "--word-margin", "0.15", "--emit-keeps", KEEPS,
                    "--intro-keep", str(a.intro_keep), "--tail-keep", str(a.tail_keep)]
            if (W / "edl.json").exists():      # L105: אין שארית פריימים בגבול קליפ
                tight_cmd += ["--boundaries-edl", W / "edl.json"]
            if a.xfade and a.xfade > 0:
                tight_cmd += ["--xfade", str(a.xfade)]
            if a.speed and abs(a.speed - 1.0) > 0.001:
                tight_cmd += ["--speed", str(a.speed)]
            r = sh(tight_cmd)
            if r.returncode != 0 or not TIGHT.exists():
                fail(f"tighten נכשל: {r.stdout[-200:]}{r.stderr[-300:]}")
            keeps = json.loads(KEEPS.read_text(encoding="utf-8"))
            _speed = a.speed if (a.speed and a.speed > 0) else 1.0
            def remap_t(t):
                # tighten_finish כותב keeps לפני החלת speed (setpts/atempo) — אז ממפים לציר
                # הקדם-מהירות ואז מחלקים ב-speed, אחרת תזמוני מילים/כתוביות ייצאו מסונכרנים
                # (21.7: תוקן לפני שימוש ראשון ב---speed דרך האורקסטרטור).
                acc = 0.0
                for k in keeps:
                    if t < k["start"]: return acc / _speed
                    if t <= k["end"]:  return (acc + (t - k["start"])) / _speed
                    acc += k["end"] - k["start"]
                return acc / _speed
            def remap_words(src, dst):
                ws = json.loads(Path(src).read_text(encoding="utf-8"))
                out = []
                for w in ws:
                    s, e = remap_t(float(w["start"])), remap_t(float(w["end"]))
                    if e - s < 0.06: e = s + 0.12
                    out.append({**w, "start": round(s, 3), "end": round(e, 3)})
                for i in range(1, len(out)):     # מונוטוניות אחרי מיפוי
                    if out[i]["start"] <= out[i-1]["start"]:
                        out[i]["start"] = round(out[i-1]["start"] + 0.02, 3)
                    if out[i]["end"] < out[i]["start"] + 0.1:
                        out[i]["end"] = round(out[i]["start"] + 0.12, 3)
                Path(dst).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            WORDS_PRE = W / "words_pre_tight.json"
            WORDS_PRE.write_text(WORDS.read_text(encoding="utf-8"), encoding="utf-8")
            remap_words(WORDS, WORDS)            # words_final → ציר מהודק
            WEXP_T = W / "whisper_export_tight.json"
            remap_words(WEXP, WEXP_T)            # ground-truth → ציר מהודק
            WEXP = WEXP_T
            EXPORT = TIGHT                       # מכאן והלאה — הקובץ המהודק
            dur = ffdur(EXPORT)
            st.done_step("tighten", r.stdout.strip()[-110:])
            report.append(f"- אחרי הידוק אקוסטי מודע-דיבור: {dur:.1f}ש")

            # תקרה קשיחה 60ש (הראל 23.7.26): "סרטון בשום מקרה לא יכול לחרוג מ-60 שניות אלא אם
            # ציינתי אחרת". אם אחרי חיתוך+הידוק עדיין מעל 60 ולא ניתן --speed מפורש ולא
            # --allow-over-60 — נכשל בכוונה במקום לשלוח FINAL חורג בשקט. הפתרון הרגיל: להריץ
            # שוב עם --speed 1.1 (ראה [[feedback_speed_ramp_over_60s]] — חיתוך תוכן קודם אם אפשר
            # בלי לפגוע, speed-up רק כגיבוי).
            # v7.9 (הראל 25.7.26: "הוא חורג מ-60 שניות וזה חוק שחייבים לעמוד בו — אולי
            # הייתי מגביר קצב ל-1.05 או 1.1"): במקום להיכשל ולבקש ריצה חוזרת, הפייפליין
            # **מחשב בעצמו** את ה-speed המינימלי שמביא מתחת ל-60 ומריץ את tighten שוב.
            # מדורג ועדין: 1.05 → 1.08 → 1.10 → 1.12 → 1.15 (התקרה שהראל אישר). מעבר
            # לזה — כישלון מפורש, כי האצה חזקה יותר נשמעת מוזר ומחייבת חיתוך תוכן.
            # v9.25 (19.9.26): speed_fit כבר לא רץ כדי להיכנס מתחת ל-60 — רק כשהסרטון
            # חורג מהגבול הקשיח של length_policy (180ש). האצה לצורך "60" בוטלה: האורך
            # אינו הלוחץ של ה-reach (40 ריילס: rho=0.10), וקצב מלאכותי פוגע בהוק.
            if dur > LP.HARD_MAX and abs(a.speed - 1.0) <= 0.001 and not a.allow_long:
                ladder = [s for s in (1.05, 1.08, 1.10, 1.12, 1.15) if dur / s <= LP.HARD_MAX]
                if not ladder:
                    fail(f"משך אחרי הידוק ({dur:.1f}ש) חורג מ-{LP.HARD_MAX:.0f}ש גם ב-speed 1.15 "
                         f"(היה יוצא {dur/1.15:.1f}ש). צריך לקצר תוכן באפליקציה — "
                         f"האצה חזקה יותר נשמעת מוזר.")
                chosen = ladder[0]
                st.step("speed_fit")
                tight_cmd2 = [c for c in tight_cmd] + ["--speed", str(chosen)]
                r2 = sh(tight_cmd2)
                if r2.returncode != 0 or not TIGHT.exists():
                    fail(f"האצה אוטומטית נכשלה: {r2.stdout[-200:]}{r2.stderr[-300:]}")
                a.speed = chosen
                _speed = chosen
                keeps = json.loads(KEEPS.read_text(encoding="utf-8"))
                # ⚠️ למפות מהעותק שלפני ההידוק — WORDS כבר מופה פעם אחת, מיפוי כפול
                # היה מכווץ את כל הכתוביות פי-שניים.
                WORDS.write_text(WORDS_PRE.read_text(encoding="utf-8"), encoding="utf-8")
                remap_words(WORDS, WORDS)
                remap_words(W / "whisper_export.json", WEXP_T)
                WEXP = WEXP_T
                dur = ffdur(EXPORT)
                st.done_step("speed_fit", f"קצב {chosen} → {dur:.1f}ש (מתחת ל-{LP.HARD_MAX:.0f})")
                report.append(f"- ⏩ האצה אוטומטית ל-{chosen} כדי לעמוד בגבול הקשיח {LP.HARD_MAX:.0f}ש "
                              f"(היה {dur*chosen:.1f}ש → {dur:.1f}ש)")

        # sentences.json (מ-edl_build, ציר EXPORT הגולמי) → ממופה לציר המהודק, לשימוש
        # ע"י broll_pick.py (מיקום ביחס לגבולות משפט נכונים בפלט בפועל, לא הציר הישן)
        SENT = W / "sentences.json"
        if SENT.exists():
            try:
                SENT_TIGHT = remap_sentences(SENT, remap_t, W / "sentences_tight.json")
            except Exception:
                SENT_TIGHT = None

    # ═══ v8.6 (P0-5) — שערי הציר רצים בשני המסלולים, כולל --refinish ═══
    # שורש: שער הכיסוי, שער השקט ואכיפת 60ש ישבו כולם בתוך ה-else של המסלול המלא.
    # גימור מהיר (--refinish) — שהוא המסלול השכיח כשמתקנים תמליל/מוזיקה/בירול —
    # דילג על שלושתם. סרטון 63ש עבר את כל השערים בגימור מהיר, ותיקון תמליל שהזיז
    # מילים לא נבדק על דד-אייר ולא על "דיבור בלי כתוביות". מעכשיו זה חוץ ל-if/else.
    dur = ffdur(EXPORT)

    # אכיפת 60ש. במסלול המלא כבר טופל עם speed_fit אוטומטי (יש tight_cmd לרוץ שוב);
    # ב-refinish אין ציר לחתוך מחדש, ולכן זה כשל מפורש עם הוראה, לא תיקון שקט.
    # v9.25: הגבול הוא length_policy.HARD_MAX, לא 60.
    if a.refinish and dur > LP.HARD_MAX and abs(a.speed - 1.0) <= 0.001 and not a.allow_long:
        fail(f"גימור מהיר: הציר המהודק הקיים הוא {dur:.1f}ש — חורג מ-{LP.HARD_MAX:.0f}ש. "
             f"לקצר תוכן באפליקציה או --allow-long במודע.")
    _lp = LP.evaluate(dur, a.content_type, a.length_reason)
    report.append(f"- 📏 אורך: {_lp['message']}")

    # שער כיסוי: דיבור בלי כתוביות (תמלול חסר) — לפני שער השקט.
    st.step("coverage")
    speech_coverage_gate(EXPORT, WORDS, st, report)

    # gate אפס-שקט — אזהרה בלבד, לא חוסם (הראל 23.7.26: הריצה הזו קורית אחרי
    # שהוא כבר סקר ואישר ב-review-app — "אני המילה האחרונה" — ולכן ה-gate לא
    # צריך לעצור את מה ששלח לגימור. הפערים עדיין נמדדים ומדווחים (gate_warn.json
    # + FINISH_REPORT.md), רק לא חוסמים יותר. תואם ל-G2_silence שהוא hard=False).
    st.step("gate")
    r = sh(["python3", HERE / "finish_local.py", "gate", "--words", WORDS,
            "--video", EXPORT, "--comp-dur", f"{dur:.2f}", "--intro-keep", str(a.intro_keep),
            "--audio-block", str(a.audio_block), "--max-word-dur", str(a.max_word_dur),
            "--edge-block", str(a.edge_block)])
    if r.returncode == 3:
        (W / "gate_warn.json").write_text(r.stdout, encoding="utf-8")
        try:
            spans = json.loads(r.stdout)
            n = sum(len(v) for k, v in spans.items() if k != "audio_silence_warnings")
        except Exception:
            n = 0
        report.append(f"- ⚠️ gate שקט: {n} פערים שיוריים מתחת לרף החיתוך (לא חוסם — פורט ב-gate_warn.json)")
        st.done_step("gate", f"אזהרה: {n} פערים שיוריים (לא חוסם, אושר בסקירה)")
    else:
        st.done_step("gate", "אפס דד-אייר")

    # ═══════════ Visual Hook Engine (11.9.26) — החלטה אחת, שני מנועים ═══════════
    # רץ רק כש-mode≠off. הקשר = הגוף הנקי הסופי (אחרי recut/tighten/speed/reconcile)
    # + שכבות מוגנות + פתיח מלא (נפתר כאן, לפני הבחירה). התוכנית הקפואה נצרכת גם
    # ע"י v1 (visual_base בכל ענפי הבירול) וגם ע"י v2 (IR בסגמנטים) — ואם v2 נופל
    # ל-v1, אותה תוכנית בדיוק. EXPORT הנקי לא נדרס לעולם (cut_qa/קאבר צורכים אותו).
    VISUAL_BASE = EXPORT
    vh_state = None
    if vh_mode != "off":
        st.step("visual_hook")
        # קבצי ריצה נגזרים מריצה קודמת לא ישרדו לריצה הזו (קבלה/QA מיושנים)
        for _stale in ("visual_hook_render.json", "visual_hook_qa.json", "VISUAL_BASE.mp4"):
            try:
                (W / _stale).unlink()
            except FileNotFoundError:
                pass
        _vh_items = []
        if manual_broll_items:
            _vh_items = [dict(it, insert_end=it.get("insert_end") if it.get("insert_end") is not None
                              else float(it.get("insert_at", 0)) + float(it.get("clip_len", 2.8)))
                         for it in manual_broll_items]
        elif not a.no_broll:
            _bp0 = Path(a.broll_plan) if a.broll_plan else (W / "broll_plan.json")
            if not _bp0.exists():
                try:
                    _r0, _ = ensure_broll_plan(W, HERE, dur, a.content_type, a.title or "",
                                               a.broll_audience, a.broll_n, SENT_TIGHT, report,
                                               commit=not a.prepare_visual_hook_review)
                    _bp0 = _r0 or _bp0
                except Exception as e:
                    report.append(f"- ⚠️ תכנון בירול מוקדם (שמירות לפתיחה) נכשל: {e}")
            try:
                _vh_items = (json.loads(Path(_bp0).read_text(encoding="utf-8")).get("plan") or []) \
                    if Path(_bp0).exists() else []
            except Exception:
                _vh_items = []
        try:
            sys.path.insert(0, str(HERE))
            from relvid import visual_hook as VHOOK
            vh_state = VHOOK.finish_resolve(
                W, mode=vh_mode, pref=vh_pref, body=EXPORT, words_file=WORDS,
                broll_items=_vh_items, brand=a.brand, content_type=a.content_type,
                title=a.title or "", plan_path=a.visual_hook_plan)
        except Exception as e:
            if a.visual_hook_plan or vh_pref.get("approved_plan_digest"):
                fail(f"HOOK_RESOLVE_FAILED: {e} — הגרסה המאושרת האחרונה נשמרת")
            vh_state = None
            report.append(f"- ⚠️ Visual Hook: ניתוח נכשל (לא חוסם במצב {vh_mode}; המסלול הישן ממשיך): {e}")
        if vh_state and vh_state.get("error"):
            _c, _d = vh_state["error"]
            _d = _d[len(_c) + 2:] if _d.startswith(_c + ": ") else _d
            fail(f"{_c}: {_d[:300]} — התצוגה שאושרה אינה תואמת לגוף הנוכחי. "
                 f"יש להכין תצוגת פתיחה מחדש באפליקציה (או לכבות אותה). הגרסה המאושרת האחרונה נשמרת.")
        if vh_state:
            _r = vh_state["report"]
            st.done_step("visual_hook", f"{_r['label_he'] if vh_state['applied'] else _r['suggestion_label_he']}"
                                        f"{'' if vh_state['applied'] else ' (לא הוחל)'} · {', '.join(_r['why'])[:80]}")
            report.append(f"- 🎬 Visual Hook ({vh_mode}): "
                          f"{_r['label_he'] if vh_state['applied'] else 'לא הוחל — הצעה: ' + str(_r['suggestion_label_he'])}"
                          f" · תוכנית {vh_state['plan']['plan_digest'][:19]} · סיבות: {', '.join(_r['why'])}")
        else:
            st.done_step("visual_hook", "לא זמין")
        if a.prepare_visual_hook_review:
            # עצירה מכוונת: אין רינדור, מוזיקה, FINAL, קאבר, artifact או תזמון.
            (W / "FINISH_REPORT.md").write_text("\n".join(report), encoding="utf-8")
            st.finish(True, "הכנת תצוגת פתיחה חזותית הושלמה (לא גימור)")
            print("DONE-VISUAL-HOOK-PREP")
            sys.exit(0)
    elif a.prepare_visual_hook_review:
        fail("‎--prepare-visual-hook-review דורש visual hook פעיל")

    # ═══════════ v8.7 (V2 שלב 2) — מנוע רינדור v2: גרף סגמנטים + מטמון ═══════════
    # מה שמשתנה הוא **סדר**, לא קידוד: כשהכתוביות והבירולים נצרבים בתוך הקידוד של
    # החיתוך עצמו, והמוזיקה (שנוגעת רק באודיו) נשארת לסוף — נשארים עם דור וידאו
    # אחד במקום 4-7. נמדד על סרטון אמיתי מול v1: 935 פריימים בשניהם (Δ משך 0.002ש),
    # SSIM מול האב-הקדמון 0.9453 מול 0.8692 (‎+7.6 נק'), גודל 18.3MB→9.3MB.
    # ראה tools/bench/render_ab.py — השער שחייב לעבור לפני שזה הופך לברירת מחדל.
    captions_burned = False
    render_v2_stats = None

    # ── בחירת מנוע: v2 מנסה, ורק מי שנתקע יורד ל-v1 (v9.7, 31.7.26) ────────
    # עד v9.6 הכלל היה "מצע של ‎≥3 בירולים ⇒ v1". **המדידה הפריכה אותו**:
    # סגמנט עם 6 בירולים מרנדר ב-9.1ש, וסגמנט אחר עם 3 (וגם עם אחד) נתקע.
    # המפעיל הוא הסגמנט, לא הספירה — ולכן ספירה היא גם הגנה חסרה וגם הורדה
    # מיותרת של סרטונים תקינים. במקומה: v2 רץ עם תקציב זמן קצר לכל סגמנט
    # עם overlay, ואם אחד נתקע — נופלים ל-v1 לכל הסרטון ומדווחים. **עדיף
    # דור וידאו נוסף על תוצר שלא נוצר**, אבל רק כשבאמת צריך.
    # ההחלטה נמדדת ומדווחת, לא מנוחשת.

    if getattr(a, "render_engine", "v1") == "v2":
        st.step("render_v2")
        # הבירול נצרב בתוך הסגמנט ⇒ התוכנית חייבת להיות מוכנה **לפני** הרינדור.
        bplan_path = Path(a.broll_plan) if a.broll_plan else (W / "broll_plan.json")
        if not a.no_broll and not manual_broll_items and not bplan_path.exists():
            try:
                bplan_path, _bd = ensure_broll_plan(W, HERE, dur, a.content_type,
                                                    a.title or "", a.broll_audience,
                                                    a.broll_n, SENT_TIGHT, report)
            except Exception as e:
                report.append(f"- ⚠️ תכנון בירול נכשל (ממשיכים בלי): {e}")
        if manual_broll_items:
            # בחירה ידנית של הראל — אותה סמנטיקה כמו v1, רק שהיא נצרבת בסגמנט.
            try:
                atomic = {"plan": [{"id": f"m{i}", "path": it.get("path"),
                                    "file": Path(str(it.get("path"))).name,
                                    "insert_at": float(it.get("insert_at", 0)),
                                    "insert_end": float(it.get("insert_at", 0))
                                    + float(it.get("clip_len", 2.8)),
                                    "clip_len": float(it.get("clip_len", 2.8)),
                                    "src_offset": float(it.get("src_offset", 0) or 0)}
                                   for i, it in enumerate(manual_broll_items)
                                   if it.get("path")]}
                (W / "broll_plan.json").write_text(json.dumps(atomic, ensure_ascii=False,
                                                              indent=1), encoding="utf-8")
                bplan_path = W / "broll_plan.json"
            except Exception as e:
                report.append(f"- ⚠️ המרת בירול ידני נכשלה: {e}")
        # v9.5 — מימוש קבצי בירול מ-iCloud לפני הרינדור. נמדד 31.7.26:
        # ffmpeg נחסם על ה-read הראשון של קובץ שלא ירד, ונראה כתקוע — 0% CPU,
        # בלי שגיאה ובלי לוג. שכבה שנייה מעל זו שב-`edit_director`, כי תוכנית
        # יכולה להגיע גם מהאפליקציה או מ---broll-plan.
        try:
            sys.path.insert(0, str(HERE))
            import broll_director as _BD
            if bplan_path and Path(bplan_path).exists():
                _pl = (json.loads(Path(bplan_path).read_text(encoding="utf-8"))
                       .get("plan") or [])
                _m = _BD.materialize([x.get("path") for x in _pl])
                if _m["cloud_only"]:
                    report.append(f"- ☁️ בירול: {_m['downloaded']}/{_m['cloud_only']} "
                                  f"קבצים הורדו מ-iCloud לפני הרינדור ({_m['secs']}ש)")
        except Exception as e:
            report.append(f"- ⚠️ מימוש קבצי בירול נכשל (ייתכן רינדור איטי): {e}")
        try:
            sys.path.insert(0, str(HERE))
            from relvid import render as RENDER
            tl = RENDER.build_timeline(W, brand=a.brand,
                                       broll_plan_file=str(bplan_path)
                                       if bplan_path and Path(bplan_path).exists() else None,
                                       hook_plan=(vh_state["plan"] if vh_state and vh_state["applied"]
                                                  else None))
            MASTER = W / "master_v2.mkv"
            rs = RENDER.render(tl, MASTER, jobs=a.render_jobs)
            (W / "render_v2_report.json").write_text(
                json.dumps(dict(rs, plan={"speed_source": tl.meta.get("speed_source"),
                                          "n_segments": len(tl.segments)}),
                           ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            fail(f"מנוע רינדור v2 נכשל בתכנון: {e}")
        if not rs.get("ok") and rs.get("stalled"):
            # התקיעה הידועה — לא כישלון גימור. יורדים ל-v1 לכל הסרטון,
            # שם אותו סגמנט מרונדר בלי בעיה, ומדווחים בדיוק על מי נתקע.
            _keys = ", ".join(s["key"][:8] for s in rs.get("stalled_segments", []))
            a.render_engine = "v1"
            captions_burned = False
            report.append(
                f"- 🔀 נפילה ל-v1: v2 נתקע על {len(rs.get('stalled_segments', []))} "
                f"סגמנטים עם בירול ({_keys}). ליקוי פתוח ומתועד ב-"
                f"`relvid/render.py`. עלות: דור וידאו אחד נוסף. "
                f"**ההחלטה נמדדה — לא נגזרה ממספר הבירולים.**")
            st.done_step("render_v2", "נתקע — נפילה ל-v1")
        elif not rs.get("ok"):
            fail(f"מנוע רינדור v2 נכשל: {rs.get('error')}")
    if getattr(a, "render_engine", "v1") == "v2" and rs.get("ok"):
        render_v2_stats = rs
        if vh_state and vh_state["applied"]:
            from relvid import hook_render as HOOKR
            vh_state["receipt"] = HOOKR.v2_receipt(vh_state["plan"], tl.meta, MASTER)
            vh_state["band"] = tl.band or None
            VHOOK.atomic_write_json(W / VHOOK.FILES["render"], vh_state["receipt"])
            report.append(f"- 🎬 Visual Hook ב-v2: סגמנטים מושפעים {vh_state['receipt']['affected_segments']} "
                          f"· שאר הסגמנטים במפתח המטמון הישן")
        base = MASTER
        EXPORT_FOR_QA = MASTER
        captions_burned = True
        # הבירול והכתוביות כבר בתוך הסגמנטים.
        a.no_broll = True
        # v8.8: אפקט הפורמט הקבוע נתמך גם ב-v2. הוא כן עולה דור וידאו אחד נוסף,
        # אבל רק כשהטריגר בפועל נמצא בתמליל (נדיר), והאודיו נשאר PCM כך שאין
        # דור אודיו נוסף. הצעד הבא לאפס-עלות: לצרוב אותו בתוך הסגמנט החופף.
        st.done_step("render_v2",
                     f"{rs['n_segments']} סגמנטים ({rs['n_rendered']} רונדרו / "
                     f"{rs['n_cached']} מטמון) · קידוד {rs['encode_secs']}ש · "
                     f"wall {rs['wall_secs']}ש · דור וידאו אחד")
        report.append(f"- 🧩 מנוע רינדור v2: {rs['n_segments']} סגמנטים · "
                      f"{rs['n_rendered']} רונדרו, {rs['n_cached']} מהמטמון · "
                      f"קידוד {rs['encode_secs']}ש ב-{rs['wall_secs']}ש wall "
                      f"({rs['jobs']} במקביל) · **דור וידאו אחד**")

    # 5. broll (conversion בלבד) — אוטומטי: broll-plan מפורש > קיים בתיקייה > הרצה
    # אוטומטית של broll_pick.py. כשל בירול = לא-חוסם (מדווח, ממשיכים בלי בירול) —
    # broll הוא שכבת-שיפור מעל עריכה כמעט-גמורה, לא תנאי-סף כמו gate/qa.
    # v8.7: ב-v2 ה-base הוא המאסטר שכבר נצרב (כתוביות+בירול בתוכו).
    if not captions_burned and vh_state and vh_state["applied"]:
        # v1 (או נפילה מ-v2): אותה תוכנית קפואה ⇒ visual_base. כשל = עצירת המועמד.
        st.step("visual_hook_render")
        try:
            from relvid import hook_render as HOOKR
            import visual_hook_qa as VHQA
            _pol = VHOOK.load_policy().get("renderer") or {}
            VISUAL_BASE = W / "VISUAL_BASE.mp4"
            vh_state["receipt"] = HOOKR.render_v1(EXPORT, vh_state["plan"], VISUAL_BASE,
                                                  crf=int(_pol.get("v1_crf", 18)),
                                                  preset=str(_pol.get("v1_preset", "medium")))
            VHOOK.atomic_write_json(W / VHOOK.FILES["render"], vh_state["receipt"])
            _q0 = VHQA.check(EXPORT, VISUAL_BASE, vh_state["plan"], vh_state["receipt"],
                             final_stage=False, reservations=vh_state["context"]["reservations"])
            if not _q0["pass"]:
                fail(f"HOOK_QA_BASE: {', '.join(_q0['hard_failures'])} — visual_base נפסל "
                     f"(הגרסה המאושרת האחרונה נשמרת)")
        except VHOOK.HookError as e:
            fail(f"{e.code}: {e.detail[:300]} — הגרסה המאושרת האחרונה נשמרת")
        st.done_step("visual_hook_render", f"visual_base · {vh_state['receipt']['output']['decoded_frames']} פריימים · אודיו זהה")
        report.append("- 🎬 Visual Hook ב-v1: visual_base נבנה מהגוף הנקי (אודיו stream-copy, מספר פריימים זהה); "
                      "כל ענפי הבירול צורכים אותו")
    base = (W / "master_v2.mkv") if captions_burned else VISUAL_BASE
    broll_applied = []
    if captions_burned:
        pass                     # הבירול נצרב בסגמנטים — אין שלב overlay נפרד
    elif manual_broll_items:
        # v7.4 — בירולים ידניים מהאפליקציה: הראל בחר קליפים ומיקומים בעצמו — זו המילה
        # האחרונה, גם בתוכן שאינו conversion (עקיפה מפורשת של כלל-הקאנון ע"י הבעלים).
        # הזמנים בציר הסרטון הסופי (המהודק). סגנון נעול: מסך-מלא, בלי טשטוש/קופסה.
        st.step("broll")
        ov_args = []
        n_ok = 0
        _applied = []
        for it in manual_broll_items:
            p = Path(it.get("path", ""))
            try:
                s0, e0 = float(it["insert_at"]), float(it["insert_end"])
            except (KeyError, TypeError, ValueError):
                report.append(f"- ⚠️ בירול ידני עם זמנים לא תקינים — דולג: {it}")
                continue
            if not p.exists():
                report.append(f"- ⚠️ קובץ בירול לא נמצא — דולג: {it.get('file') or it.get('path')}")
                continue
            if e0 <= s0 or s0 < 0 or e0 > dur + 0.05:
                report.append(f"- ⚠️ בירול ידני מחוץ לטווח הסרטון ({s0}-{e0} מול {dur:.1f}ש) — דולג")
                continue
            ov_args += ["--overlay", str(p), f"{s0:.2f}", f"{min(e0, dur):.2f}",
                        "--src-offset", str(float(it.get("src_offset") or 0.0))]
            n_ok += 1
            _applied.append(it)
        if ov_args:
            BB = W / "EXPORT+BROLL.mp4"
            r = sh(["python3", HERE / "animation_overlay.py", "--base", VISUAL_BASE, "--out", BB,
                    "--width", "1080", "--blur", "0"] + ov_args)
            if r.returncode != 0 or not BB.exists():
                report.append(f"- ⚠️ broll overlay ידני נכשל — ממשיכים בלי בירול: {r.stderr[-300:]}")
                st.done_step("broll", "נכשל (לא-חוסם)")
            else:
                base = BB
                st.done_step("broll", f"ידני מהאפליקציה · {n_ok} קליפים")
                report.append(f"- בירול: ידני מהאפליקציה ({n_ok} קליפים)")
                broll_applied = _applied
        else:
            st.done_step("broll", "תוכנית ידנית ריקה/לא תקינה — דולג")
    elif a.no_broll:
        report.append("- בירול דולג במפורש (‎--no-broll / מצב כבוי באפליקציה)")
    else:
        # v7.6 (הראל 24.7: "אף פעם אין את הבירולים באפליקציה"): שורש — broll_plan.json
        # שקלאוד הכין בצ'אט כובד רק ב-content_type=conversion, ורוב האישורים מהאפליקציה
        # הם value ⇒ הבירול דולג בריצות האפליקציה בעוד הגרסה בצ'אט כללה אותו. הכלל
        # החדש: **תוכנית בירולים קיימת (בתיקייה או ‎--broll-plan) = החלטה מפורשת —
        # מוחלת תמיד**, בכל סוג תוכן. "רק בהמרה" חל רק על הבחירה האוטומטית (broll_pick).
        plan_path = Path(a.broll_plan) if a.broll_plan else None
        detail = "broll-plan מפורש" if plan_path else None
        if plan_path is None:
            existing = W / "broll_plan.json"
            try:
                _pl = json.loads(existing.read_text(encoding="utf-8")) if existing.exists() else {}
            except Exception:
                _pl = {}
            if _pl.get("plan"):
                plan_path = existing
                detail = f"תוכנית קיימת בתיקייה ({len(_pl['plan'])} קליפים)"
        # v7.8 (הראל 25.7): בחירה אוטומטית רצה **בכל סוגי התוכן**, לא רק conversion.
        # ההגבלה הישנה נולדה כשהיה יקר לייצר בירול לכל סרטון; היום הקטלוג גדל והמטרה
        # הפוכה. הבלימה עברה מ"סוג תוכן" ל"רלוונטיות": broll_pick מחזיר תוכנית ריקה
        # כשאין קליפ שקשור לנושא, ואז ממשיכים בלי בירול (לא-חוסם, מדווח).
        if plan_path is None:
            st.step("broll")
            plan_path, detail = ensure_broll_plan(W, HERE, dur, a.content_type, a.title or "",
                                                   a.broll_audience, a.broll_n, SENT_TIGHT, report)
        if plan_path is not None:
            if st.data.get("step") != "broll":     # לא לפתוח שלב פעמיים (v7.8)
                st.step("broll")
            if a.content_type != "conversion":
                report.append("- בירול מוחל בתוכן לא-המרה — תוכנית קיימת/מפורשת = החלטה מודעת (v7.6)")
            try:
                plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
            except Exception as e:
                plan = {}
                report.append(f"- ⚠️ קריאת {plan_path} נכשלה: {e} — דולג")
            args = plan.get("overlay_args") or []
            if isinstance(args, str):        # תאימות-לאחור: broll_plan.json ישן בפורמט מחרוזת-shell
                args = shlex.split(args)
            if args:
                # סגנון נעול (20.7): בירול מסך-מלא, בלי קופסה/טשטוש — אלא אם התוכנית
                # כבר קובעת width משלה
                style = [] if "--width" in args else ["--width", "1080", "--blur", "0"]
                BB = W / "EXPORT+BROLL.mp4"
                r = sh(["python3", HERE / "animation_overlay.py", "--base", VISUAL_BASE, "--out", BB]
                       + style + args)
                if r.returncode != 0 or not BB.exists():
                    report.append(f"- ⚠️ broll overlay נכשל — ממשיכים בלי בירול: {r.stderr[-300:]}")
                    st.done_step("broll", "נכשל (לא-חוסם)")
                else:
                    base = BB
                    st.done_step("broll", f"{detail} · {len(plan.get('plan', []))} קליפים")
                    report.append(f"- בירול: {detail}")
                    broll_applied = plan.get("plan") or []
            else:
                st.done_step("broll", "תוכנית ריקה — דולג")

    # v7.6 — סנכרון לאפליקציה: מה שנצרב בפועל ב-FINAL נרשם במניפסט (items_applied),
    # ולשונית הבירולים מציגה אותו + "ייבא לעריכה". נכתב גם כשריק — מנקה מידע ישן.
    try:
        _fb = manifest.setdefault("finish_prefs", {}).setdefault("broll", {})
        _fb["items_applied"] = [
            {k: it.get(k) for k in ("id", "file", "path", "insert_at", "insert_end", "src_offset")}
            for it in broll_applied]
        _save_manifest()
    except Exception:
        pass

    # 5.5 אפקט פורמט קבוע (v7.9) — "מנפצים לכם מיתוסים" → ניפוץ זכוכית + צליל.
    # הנכסים והמתכון היו בקטלוג מ-21.7 אבל אף שלב לא הרכיב אותם בפועל (הראל 25.7:
    # "זה הפתיח שלנו ... צריך להיות עם האפקט והסאונד של הזכוכית"). לא-חוסם.
    if not a.no_fixed_intro:
        st.step("fixed_intro")
        try:
            sys.path.insert(0, str(HERE))
            import fixed_intro as fx_mod
            hits = fx_mod.detect(json.loads(WORDS.read_text(encoding="utf-8")))
        except Exception as e:
            hits = []
            report.append(f"- ⚠️ זיהוי אפקט-פורמט נכשל: {e}")
        if hits:
            h = hits[0]
            FXO = W / ("EXPORT+FX.mkv" if captions_burned else "EXPORT+FX.mp4")
            ok_fx, msg_fx = fx_mod.apply(str(base), str(FXO), h["end"], h["format_id"],
                                         lossless=captions_burned)
            if ok_fx:
                base = FXO
                st.done_step("fixed_intro", f"«{h['phrase']}» → {msg_fx}")
                report.append(f"- 💥 אפקט פורמט קבוע: «{h['phrase']}» ב-{h['end']:.2f}ש")
            else:
                st.done_step("fixed_intro", f"נכשל (לא-חוסם): {msg_fx[:80]}")
                report.append(f"- ⚠️ אפקט פורמט קבוע נכשל: {msg_fx[:150]}")
        else:
            st.done_step("fixed_intro", "אין טריגר פורמט קבוע בתמליל")

    # 5.55 (v9.46) ארגז העריכה של ההוק — tools/hook_fx.py. תנועות מצלמה (snap/push/shake/freeze/ramp),
    # מעברים (whip/zoom-through/flash) וצלילי עריכה (impact/swish/riser...) בחלון 0-4ש, מתוך
    # HOOK_PLAN.json["edit"] שהבמאי כתב. רץ אחרי בירול/פתיח קבוע (הציר הסופי) ולפני MG — כך שכבת ה-MG
    # והכתוביות לא זזות עם הזום. שומר ציר (S(a)=a, S(b)=b) ⇒ WORDS לא משתנים. הראל 8.10.26:
    # "ארגז הכלים ... ברמת העריכה שלנו. אפקטים, אנימציה שמשתלבת בהוק, מעברים, צלילים".
    hfx_mute = []
    _hp = W / "HOOK_PLAN.json"
    try:
        _hedit = (json.loads(_hp.read_text(encoding="utf-8")).get("edit") or {}) if _hp.exists() else {}
    except Exception:
        _hedit = {}
    _hfx_pref = (_prefs.get("hook_fx") or {}).get("enabled")
    _hfx_on = a.hook_fx == "on" or (a.hook_fx == "auto" and (_hedit.get("moves") or _hedit.get("sfx")
                                                              or _hedit.get("music_drop")) and _hfx_pref is not False)
    if _hfx_on:
        st.step("hook_fx")
        if not (_hedit.get("moves") or _hedit.get("sfx") or _hedit.get("music_drop")):
            fail("--hook-fx on בלי HOOK_PLAN.json[edit] — קודם hook_plan.py init + בלוק edit (ארגז עריכת ההוק)")
        _plan_arg = []
        if captions_burned and _hedit.get("moves"):
            # v2 צורב כתוביות בתוך החיתוך — זום/רעד היו מזיזים גם אותן. נשארים עם הסאונד בלבד.
            _hv2 = dict(_hedit, moves=[])
            try:
                sys.path.insert(0, str(HERE)); import hook_fx as _HF; _odg = _HF.edit_digest(_hedit)
            except Exception:
                _odg = None
            (W / "_hook_edit_v2.json").write_text(json.dumps({"edit": _hv2, "orig_digest": _odg}, ensure_ascii=False),
                                                  encoding="utf-8")
            _plan_arg = ["--plan", W / "_hook_edit_v2.json"]
            report.append("- ⚠️ hook_fx: מנוע v2 צרב כתוביות — תנועות המצלמה דולגו, הסאונד הוחל")
        HFXO = W / ("EXPORT+HFX.mkv" if captions_burned else "EXPORT+HFX.mp4")
        r = sh([WHISPER_PY if WHISPER_PY.exists() else sys.executable, HERE / "hook_fx.py", "render",
                "--workdir", W, "--base", base, "--out", HFXO, "--words", WORDS] + _plan_arg
               + (["--lossless"] if captions_burned else [])
               + (["--vh-applied"] if (vh_state and vh_state.get("applied")) else []), timeout=1800)
        try:
            hrep = json.loads((W / "HOOK_FX_REPORT.json").read_text(encoding="utf-8"))
        except Exception:
            hrep = {"ok": False, "gates": []}
        _hbad = [g["gate"] + ": " + g["detail"][:90] for g in hrep.get("gates", [])
                 if g.get("level") == "blocking" and not g.get("ok")]
        if r.returncode == 0 and hrep.get("ok") and HFXO.exists():
            base = HFXO
            hfx_mute = hrep.get("music_mute") or []
            _mv = ", ".join(f"{m['type']}@{m['start']:.2f}" for m in hrep.get("moves") or [])
            _sx = ", ".join(f"{x['kind']}@{x['at']:.2f}" for x in hrep.get("sfx") or [])
            st.done_step("hook_fx", f"{_mv or 'בלי תנועה'} · {_sx or 'בלי צלילים'} · HOOK_FX_SHEET.jpg")
            report.append(f"- 🎞 ארגז עריכת ההוק ({_hedit.get('recipe', '?')}): תנועות [{_mv}] · צלילים [{_sx}] · "
                          f"השתקת מצע {hfx_mute} · גיליון HOOK_FX_SHEET.jpg (חוק הראייה — לפתוח לפני הצגה)")
        elif a.hook_fx == "on":
            fail("hook_fx נכשל: " + ("; ".join(_hbad) or (r.stderr or r.stdout or "")[-300:]))
        else:
            st.done_step("hook_fx", "נכשל (לא-חוסם) — הסרטון יוצא בלי שכבת עריכת ההוק")
            report.append("- ⚠️ hook_fx לא הוחל: " + ("; ".join(_hbad) or (r.stderr or "")[-200:]))

    # 5.6 (v9.37) Motion Graphics — שכבה אחת באורך מלא, overlay יחיד (tools/motion_build.py,
    # סקיל rel-motion-graphics). רץ על הציר הסופי (אחרי בירול ופתיח קבוע) ולפני מוזיקה וכתוביות:
    # הכתוביות נצרבות מעל ה-MG, ובחלונות שבהם הטקסט על המסך *הוא* הדיבור (suppress_captions)
    # הן יורדות כדי שלא יהיה טקסט כפול. הראל 4.10.26: "חלק בלתי נפרד ... ברמה מאוד גבוהה".
    mg_suppress = []
    mg_pre_base = None          # הבסיס לפני שכבת ה-MG — לשערי בירול שמודדים נחיתת קליפ (ראה broll_vision)
    CAPS_WORDS = WORDS          # מה שנצרב בפועל ככתוביות (V7 מודד מולו)
    _mp = W / "motion_plan.json"
    _mg_pref = (_prefs.get("motion") or {}).get("enabled")
    _mg_on = a.motion == "on" or (a.motion == "auto" and _mp.exists() and _mg_pref is not False)
    if _mg_on:
        st.step("motion")
        if not _mp.exists():
            fail("--motion on בלי motion_plan.json — קודם propose + תוכנית (סקיל rel-motion-graphics)")
        MGO = W / ("EXPORT+MG.mkv" if captions_burned else "EXPORT+MG.mp4")
        r = sh([sys.executable, HERE / "motion_build.py", "all", "--workdir", W, "--base", base, "--out", MGO]
               + (["--lossless"] if captions_burned else []), timeout=7200)
        try:
            mrep = json.loads((W / "MOTION_REPORT.json").read_text(encoding="utf-8"))
        except Exception:
            mrep = {"ok": False, "gates": []}
        _bad = [g["gate"] + ": " + g["detail"][:90] for g in mrep.get("gates", [])
                if g.get("level") == "blocking" and not g.get("ok")]
        if r.returncode == 0 and mrep.get("ok") and MGO.exists():
            mg_pre_base = base
            base = MGO
            mg_suppress = mrep.get("suppress_captions") or []
            if mrep.get("inserts"):
                # name_sparkle insert (8.10.26): הסרטון נעצר לקטע שם — הציר מתארך; כל מה שאחרי (מוזיקה,
                # כתוביות, שערים) עובד מול המילים המוזזות. words_final.json המקורי לא נוגעים (refinish).
                WORDS = W / (mrep.get("words_after") or "words_after_mg.json")
                CAPS_WORDS = WORDS
                # L130 (9.10.26): גם האמת של G6 זזה בקטע השם — אחרת G6 משווה כתוביות מוזזות לתמליל
                # שלא זז ונכשל בהיסט של אורך העצירה (G6b מול האודיו נשאר הבדיקה האמיתית).
                try:
                    _tr = json.loads(Path(WEXP).read_text(encoding="utf-8"))
                    _tr = _tr if isinstance(_tr, list) else (_tr.get("words") or [])
                    for _w in _tr:
                        _add = sum(float(i["dur"]) for i in mrep["inserts"] if float(_w.get("start", 0)) >= float(i["at"]) - 0.01)
                        if _add:
                            _w["start"] = round(float(_w["start"]) + _add, 3)
                            _w["end"] = round(float(_w["end"]) + _add, 3)
                    _wexp_mg = W / "whisper_export_after_mg.json"
                    _wexp_mg.write_text(json.dumps(_tr, ensure_ascii=False, indent=1), encoding="utf-8")
                    WEXP = _wexp_mg
                except Exception as _e:
                    report.append(f"- ⚠️ לא נוצרה אמת מוזזת ל-G6 אחרי קטע השם: {_e}")
                report.append("- ⏸ קטע שם נוסף (הסרטון נעצר): " + ", ".join(
                    f"{i['id']} @{i['at']:.2f}ש +{i['dur']:.1f}ש" for i in mrep["inserts"]))
            _rd = mrep.get("render") or {}
            _warn = [g["gate"] for g in mrep.get("gates", []) if not g.get("ok") or g.get("measured") is False]
            st.done_step("motion", f"{len(mrep.get('events') or [])} רגעים · {_rd.get('rendered', '?')} פריימים "
                                   f"ב-{_rd.get('secs', '?')}ש · MG_SHEET.jpg" + (f" · ⚠ {','.join(_warn)}" if _warn else ""))
            report.append(f"- 🎬 Motion Graphics: {len(mrep.get('events') or [])} רגעים · אזורים {mrep.get('zones')} · "
                          f"כתוביות יורדות ב-{mg_suppress} · גיליון MG_SHEET.jpg (חוק הראייה — לפתוח לפני הצגה)")
        elif a.motion == "on":
            fail("Motion Graphics נכשל: " + ("; ".join(_bad) or (r.stderr or r.stdout or "")[-300:]))
        else:
            st.done_step("motion", "נכשל (לא-חוסם) — הסרטון יוצא בלי MG")
            report.append("- ⚠️ MG לא הורכב (הסרטון יוצא בלי MG): " + ("; ".join(_bad) or (r.stderr or "")[-200:]))

    # ═══ v8.6 (P0-10) — תמלול אימות ברקע, ל-G6b ═══
    # למה: השער היחיד שחוסם על כתוביות (G6) השווה את words_final מול
    # whisper_export_tight — שתי נגזרות שעברו את אותו remap_words, כך שדריפט
    # מיפוי/הידוק מתקזז ולא ניתן לגלות. כאן מודדים מהמדיה: ASR חדש על האודיו
    # של `base` — הציר הסופי בפועל, **לפני** מצע המוזיקה (מוזיקה מקלקלת ASR
    # ואינה חלק ממה שאנחנו בודקים: ההתאמה בין הכתובית לדיבור).
    # למה ברקע: זה ~27ש על סרטון 60ש (ASR-BENCH). music+captions+loudness+deliver
    # אינם תלויים בו, ויש 10 ליבות — ההצטרפות לפני qa_gates עולה כמעט אפס
    # wall-clock. נמדד ב-timings כ-verify_asr_wait (ההמתנה בפועל, לא זמן ה-ASR).
    VERIFY = W / "whisper_verify.json"
    _verify_thread = None
    if not a.no_verify_asr and WHISPER_PY.exists():
        import threading
        _verify_state = {"rc": None, "err": ""}

        def _run_verify(src: str, out: Path, model: str, state: dict):
            try:
                rr = sh([WHISPER_PY, HERE / "align_words.py", src, out, model, "he"], timeout=3600)
                state["rc"] = rr.returncode
                state["err"] = (rr.stderr or "")[-300:]
            except Exception as ex:      # לעולם לא מפיל את הצנרת — G6b יהפוך לאזהרה
                state["rc"] = -1
                state["err"] = str(ex)[:300]

        _verify_thread = threading.Thread(target=_run_verify, daemon=True,
                                          args=(str(base), VERIFY, a.whisper_model, _verify_state))
        _verify_thread.start()
        report.append("- 🔎 תמלול אימות (G6b) הופעל ברקע על הציר הסופי לפני המוזיקה")

    # 6. music
    st.step("music")
    # גייט שפיות: מפלס נמוך מ-44- LUFS (עוד לפני דאקינג) קרוב לבלתי-נשמע בפועל — בדיוק
    # מה שקרה ב-shina 20.7 (הראל תיקן "מוזיקת מעליות" ← המפלס היה חסום מתחת לרף שמיעה, לא
    # בעיית בחירת טראק). אם צריך לרכך פתיח חד — עדיף fade-in (audio_mix.py כבר תומך) מאשר
    # להנמיך את כל המצע עד שהוא נעלם.
    if a.music_lufs < -50.0:
        # הסף הורד -44→-50 ב-24.7 (הראל: "ההכי נמוך עדיין קצת חזק — שיהיה אפשר להנמיך
        # יותר") — טווח הסליידר באפליקציה הורחב עד -52, וזו בחירה מודעת שלו, לא תקלה.
        report.append(f"- ⚠️ music-lufs={a.music_lufs} נמוך מאוד — המוזיקה תהיה בקושי נשמעת (לקח shina 20.7)")
    # v9.9 — הטון מהבריף נכנס לבחירה. ראה `tone_class`: המרה בטון רגוע
    # מסוננת מז'אנרים כבדים בדיוק כמו תוכן ערך.
    _tone = read_brief_tone(W)
    _light = (mus_pref.get("profile") == "light") or (
        mus_pref.get("profile") != "full" and "hrowdown" in json.dumps(manifest, ensure_ascii=False)
        and not any(k in W.name for k in ("מונטאז", "אפטר-מובי")))
    track = pick_music(a.content_type, a.music, tone=_tone, light=_light)
    if _light:
        report.append("- 🎵 פרופיל מוזיקה קליל v2 (תוכן אירוע — פופ/דאנס/אינדי/טרופיקל, קצבי מ-0; בלי funk/afrobeat/hiphop — הראל 9.10.26)")
    # v9.47 (L128) — המצע נכנס בקצב מהשנייה הראשונה: offset מהמניפסט, ואם אין — auto
    # בפרופיל הקליל (הראל 9.10.26: "המוזיקה מתחילה מאוחר מידיי. מהתחלה צריך מוזיקה קצבית").
    _music_offset = mus_pref.get("offset")
    if _music_offset is None and _light:
        _music_offset = "auto"
    if track is None: fail("לא נמצא טראק מוזיקה")
    if _tone:
        report.append(f"- 🎵 טון הבריף: {tone_class(_tone)} "
                      f"({_tone[:60]}{'…' if len(_tone) > 60 else ''})")
    # v7.4 — נעילת הטראק שנבחר במניפסט (track_auto): גימור מהיר עתידי ישתמש באותה
    # מנגינה במקום לשרוף את הרוטציה, והאפליקציה מציגה להראל מה מתנגן בפועל.
    if mpath.exists():
        try:
            manifest.setdefault("finish_prefs", {}).setdefault("music", {})["track_auto"] = track.name
            _save_manifest()
        except Exception:
            pass
    mix_cmd = ["python3", HERE / "audio_mix.py", "mix", "--video", base, "--music", track,
            "--out", MIXED, "--music-lufs", str(a.music_lufs), "--tp-limit", str(a.tp_limit)]
    if _music_offset not in (None, "", 0, 0.0):
        mix_cmd += ["--music-offset", str(_music_offset)]
    music_detail = f"{track.name} @ {a.music_lufs} (בלי דאקינג — --no-duck)"
    if not a.no_duck:
        # דאקינג אמיתי (הראל 20.7 r4, ברירת מחדל מ-23.7.26 r2): פתיח-מוזיקה-בלבד "מחריש
        # אוזניים" בלי דיבור שממסך אותו — מרגע המילה הראשונה יורדים למפלס נמוך יותר.
        # first-word מ-WORDS (כבר בציר TIGHT כאן).
        try:
            ws = json.loads(WORDS.read_text(encoding="utf-8"))
            first_word = min(float(w["start"]) for w in ws) if ws else None
        except Exception:
            first_word = None
        # עומק הדאקינג הורד 9→8 ב-v7.10 יחד עם העלאת המצע (ראה --music-lufs)
        speech_lufs = a.speech_lufs if a.speech_lufs is not None else (a.music_lufs - 8.0)
        if first_word and first_word > 0.3:
            mix_cmd += ["--speech-start", f"{first_word:.3f}", "--speech-lufs", str(speech_lufs)]
            music_detail = f"{track.name} @ פתיח {a.music_lufs} → דיבור {speech_lufs} (מ-{first_word:.2f}ש)"
        else:
            # תיקון שורש 24.7 ("עיסוי רפואי" — 'הנמכתי ולא נשמע שינוי'): כשהדיבור מתחיל
            # מיד (אין פתיח), הדאקינג דולג והמוזיקה נשארה במפלס-הפתיח הגבוה לכל הסרטון —
            # 9dB מעל סרטונים עם דאקינג. אין פתיח ⇒ כל הסרטון הוא "זמן דיבור" ⇒ מפלס
            # קבוע ברמת-הדיבור (music_lufs-9), לא ברמת-הפתיח.
            mix_cmd[mix_cmd.index("--music-lufs") + 1] = str(speech_lufs)
            music_detail = f"{track.name} @ {speech_lufs} (אין פתיח — מפלס-דיבור קבוע לכל האורך)"
    # L135 (11.10.26) — מפלס יחסי לדיבור + רצפה, בכל ריל עם דיבור. מפלס מוחלט (‎-46/-54)
    # נתן gap של 17-28 LU בין ריליז כי הדיבור בקלט נע ב-26dB. בחירה ידנית באפליקציה
    # (music_lufs) נשמרת אבל נחתכת ברצפה; gap_db במניפסט = בחירה ידנית יחסית.
    _has_words = False
    try:
        _has_words = bool(json.loads(WORDS.read_text(encoding="utf-8")))
    except Exception:
        pass
    if _has_words and not a.no_duck:
        _pol = json.loads((HERE / "music-level-policy.json").read_text(encoding="utf-8"))
        _gs = mus_pref.get("gap_db")
        if _gs is None and mus_pref.get("music_lufs") is None:
            _gs = _pol["speech_gap_lu"]
        if _gs is not None:
            mix_cmd += ["--gap-speech", str(float(_gs)), "--gap-intro", str(float(_gs) - (_pol["speech_gap_lu"] - _pol["intro_gap_lu"]))]
        if not mus_pref.get("allow_louder"):
            mix_cmd += ["--min-gap", str(_pol["min_speech_gap_lu"]), "--min-intro-gap", str(_pol["min_intro_gap_lu"]),
                        "--gap-tolerance", str(_pol["gate_tolerance_lu"])]
        music_detail += f" · L135 gap {'ידני ' + str(_gs) if mus_pref.get('gap_db') is not None else (_gs or 'ידני-LUFS')} / רצפה {_pol['min_speech_gap_lu']}"
    if hfx_mute:
        mix_cmd += ["--mute", ";".join(f"{x:.3f}-{y:.3f}" for x, y in hfx_mute)]
        music_detail += f" · דרופ הוק {hfx_mute}"
    r = sh(mix_cmd)
    if r.returncode != 0: fail(f"audio_mix נכשל: {r.stdout[-200:]}{r.stderr[-300:]}")
    try:  # L135 — ה-gap הנמדד בפועל (לא המספר שביקשנו) נכנס לדוח
        _mg = json.loads(Path(f"{MIXED}.musicgap.json").read_text(encoding="utf-8"))
        if _mg.get("measured"):
            music_detail += f" · נמדד: מוזיקה {_mg['measured']['gap_lu']} LU מתחת לדיבור"
    except Exception:
        pass
    st.done_step("music", music_detail)
    report.append(f"- מוזיקה: {music_detail} LUFS")

    # 7. captions (PIL overlay — המק בלי libass)
    if captions_burned:
        # v8.7 — ב-v2 הכתוביות כבר צרובות בתוך הסגמנטים, וה-MIXED הוא כבר הפלט
        # הסופי (audio_mix עשה ‎-c:v copy). המעבר מ-MIXED ל-PENDING הוא **שינוי שם**,
        # כלומר אפס קידוד — וזה בדיוק הקידוד ה-crf16 שנחסך.
        st.step("captions")
        os.replace(MIXED, PENDING)
        st.done_step("captions", "צרובות בסגמנטים (v2) — אפס קידוד נוסף")
        report.append("- כתוביות: נצרבו בתוך הסגמנטים (v2) — נחסך קידוד crf16 מלא")
    else:
        st.step("captions")
        sys.path.insert(0, str(APPDIR)); sys.path.insert(0, str(HERE))
        import captions_overlay
        # 25.9.26 — סרטון בלי דיבור (מונטאז'): אפס מילים → אין מה לצרוב, מעתיקים כמו שהוא.
        try:
            _nw = len(json.loads(Path(WORDS).read_text(encoding="utf-8")))
        except Exception:
            _nw = -1
        # 28.9.26 (TD26) — היסט כתוביות פר-פרויקט מ-finish_prefs.captions.offset (שניות, +=מאחר).
        # נמדד על אודיו אירוע: תזמוני Whisper מרופדים ⇒ כתוביות מוקדמות ‎0.3ש (G6b median,
        # matched≥76%, ואומת בקורלציית אנבלופ). זה תיקון מדוד פר-פרויקט לפי suggest_delay של G6b;
        # תיקון השורש (הצמדת תחילת מילה ל-onset אקוסטי ב-reconcile) — חוב פתוח ב-handoff.
        _cap_off = float(((_prefs.get("captions") or {}).get("offset") or 0.0))
        if _nw > 0 and abs(_cap_off) >= 0.02:
            _ws = json.loads(Path(WORDS).read_text(encoding="utf-8"))
            for _w in _ws:
                _w["start"] = round(max(0.0, float(_w["start"]) + _cap_off), 3)
                _w["end"] = round(max(_w["start"] + 0.05, float(_w["end"]) + _cap_off), 3)
            Path(WORDS).write_text(json.dumps(_ws, ensure_ascii=False, indent=1), encoding="utf-8")
            # G6 משווה כתוביות לתמליל-המקור — ההיסט מכוון, אז גם האמת של G6 מוזזת (G6b נשאר מול האודיו).
            try:
                _tr = json.loads(Path(WEXP).read_text(encoding="utf-8"))
                for _w in _tr:
                    _w["start"] = round(max(0.0, float(_w["start"]) + _cap_off), 3)
                    _w["end"] = round(max(_w["start"] + 0.05, float(_w["end"]) + _cap_off), 3)
                (W / "whisper_export_offset.json").write_text(json.dumps(_tr, ensure_ascii=False, indent=1), encoding="utf-8")
            except Exception as _e:
                report.append(f"- ⚠️ לא נוצרה אמת מוזזת ל-G6: {_e}")
            report.append(f"- ⏱ היסט כתוביות {_cap_off:+.2f}ש (finish_prefs.captions.offset)")
        elif (W / "whisper_export_offset.json").exists():
            (W / "whisper_export_offset.json").unlink()
        if _nw == 0:
            shutil.copyfile(str(MIXED), str(W / "FINAL_PENDING.mp4")); ok, err, n = True, "", 0
        else:
            _caps_words = WORDS
            if mg_suppress:
                # v9.37 — מילים שמוצגות כ-MG (הוק קינטי, ציטוט, אפשרויות סקר) לא נצרבות פעמיים.
                # G6/coverage נשארים מול WORDS המלא; כאן רק מה שנצרב בפועל.
                _all = json.loads(Path(WORDS).read_text(encoding="utf-8"))
                _keep = [w for w in _all if not any(s0 - 0.02 <= (float(w["start"]) + float(w["end"])) / 2 <= e0 + 0.02
                                                    for s0, e0 in mg_suppress)]
                _caps_words = W / "words_captions_mg.json"
                _caps_words.write_text(json.dumps(_keep, ensure_ascii=False, indent=1), encoding="utf-8")
                CAPS_WORDS = _caps_words
                report.append(f"- 🎬 כתוביות: {len(_all) - len(_keep)} מילים מוצגות כ-MG — לא נצרבו פעמיים")
            # v9.47 (L129) — צנזור קללות בכתוביות: חצי מילה + #$% (הראל 9.10.26).
            _cens_path, _cens_n = censor_caption_words(_caps_words, W, manifest)
            if _cens_n:
                _caps_words = _cens_path
                CAPS_WORDS = _cens_path
                report.append(f"- 🤐 כתוביות: {_cens_n} קללות הוצגו כחצי מילה + #$% (L129)")
            ok, err, n = captions_overlay.burn(_caps_words, str(MIXED), "FINAL_PENDING.mp4", W, brand=a.brand)
        if not ok: fail(f"צריבת כתוביות נכשלה: {err}")
        st.done_step("captions", f"{n} cues · מותג {a.brand}")
        report.append(f"- כתוביות: {n} cues (מתאר {a.brand})")

    # 8. loudness ‎-14
    st.step("loudness")
    ok, detail = loudness_align(PENDING, -14.0)
    if not ok: fail(f"loudness נכשל: {detail}")
    st.done_step("loudness", detail)
    report.append(f"- loudness: {detail}")

    # 8.5 (v7.11) תקן העלאה — crf23. חייב לרוץ לפני qa_gates, אחרת G5_format
    # נכשל על גודל ומתוקן ידנית בכל ריצה (ראה deliver_spec).
    st.step("deliver")
    if captions_burned:
        # v8.7 — ב-v2 הסגמנטים מקודדו ישר בפרמטרי המסירה (1080×1920@30, crf23,
        # תיוג צבע), ולכן אין מה "לתקנן". קידוד נוסף היה מוסיף דור בלי סיבה.
        # ‎deliver_spec רץ רק אם משהו בכל זאת חרג מ-60MB — מקרה קצה, לא ברירת מחדל.
        _mb = PENDING.stat().st_size / 1e6 if PENDING.exists() else 0.0
        if _mb > 60.0:
            ok, ddetail = deliver_spec(PENDING, crf=26)
            if not ok: fail(ddetail)
            ddetail = f"חרג ({_mb:.1f}MB) → נדחס: {ddetail}"
        else:
            ddetail = f"כבר בתקן מהסגמנטים ({_mb:.1f}MB) — אפס קידוד נוסף"
        st.done_step("deliver", ddetail)
        report.append(f"- תקן העלאה: {ddetail}")
    else:
        ok, ddetail = deliver_spec(PENDING, crf=23)
        if not ok: fail(ddetail)
        st.done_step("deliver", ddetail)
        report.append(f"- תקן העלאה: {ddetail}")

    # 8.6 (v9.19) — פתיח קבוע מלא. שורש: הראל, 18.8.26, "שכחנו לצרף את הפתיח
    # של מאסל מן". הנכס והכללים ישבו בקטלוג מ-21.7 ו-`full_intro` היה מתועד
    # כ"concat שנעשה בשלב ההכנה" — כלומר תלוי בזיכרון אנושי, ולכן נשכח.
    #
    # למה **כאן** ולא בשלב ההכנה, ולא יחד עם אפקט-המעבר בשלב 5.5:
    #   • לפני המוזיקה — מצע המוזיקה היה נמרח גם על הפתיח, שיש לו פסקול משלו.
    #   • לפני הכתוביות — הכתוביות נצרבות מ-words_final שהוא על ציר הגוף;
    #     הדבקה קודמת הייתה מזיזה כל כתובית ב-10 שניות.
    #   • לפני תמלול האימות — ה-ASR היה מתמלל את דיבור הפתיח, ו-G6b היה נכשל
    #     על "דיבור בלי כתוביות" (לפתיח כתוביות צרובות משלו).
    # אחרי deliver ולפני השערים: qa_gates מודד את המוצר האמיתי, כולל הפתיח.
    intro_sec = 0.0
    if not a.no_full_intro:
        st.step("full_intro")
        fi_mod, fid, ph = None, None, None
        try:
            sys.path.insert(0, str(HERE))
            import fixed_intro as fi_mod
            _mf = W / "project_manifest.json"
            _man = json.loads(_mf.read_text(encoding="utf-8")) if _mf.exists() else {}
            # ההחלטה **נדבקת** למניפסט. שורש (נמדד 18.8.26 בהרצת סמוק שנייה):
            # הפייפליין עצמו דורס את manifest["name"] בשם תיקיית העבודה, ולכן
            # זיהוי שתלוי בשם בלבד עבד בהרצה הראשונה ונכשל בשנייה על אותו
            # פרויקט. פורמט לא מפסיק להיות "מאסל מן" כי שדה התחלף. בונוס:
            # השדה הוא גם עקיפה ידנית לפרויקט ששמו לא מסגיר את הפורמט.
            _pin = (_man.get("full_intro") or {}).get("id")
            if _pin:
                fid, ph = _pin, (_man.get("full_intro") or {}).get("matched") or _pin
            else:
                fid, ph = fi_mod.detect_full_intro(
                    _man.get("name"), _man.get("topic"),
                    getattr(a, "title", "") or "", W.name)
                if fid and _mf.exists():
                    _man["full_intro"] = {"id": fid, "matched": ph,
                                          "detected_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                    _mf.write_text(json.dumps(_man, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        except Exception as e:
            report.append(f"- ⚠️ זיהוי פתיח קבוע נכשל: {e}")
        if fid and fi_mod is not None:
            _WITH = W / "FINAL_PENDING_INTRO.mp4"
            ok_i, msg_i, intro_sec = fi_mod.prepend_full_intro(
                str(PENDING), str(_WITH), fid, workdir=W)
            if ok_i:
                _WITH.replace(PENDING)
                st.done_step("full_intro", msg_i)
                report.append(f"- 🎬 פתיח קבוע «{ph}»: {msg_i}")
            else:
                # לא-חוסם: סרטון בלי הפתיח עדיף על ריצה שנפלה. מדווח בקול.
                intro_sec = 0.0
                st.done_step("full_intro", f"נכשל (לא-חוסם): {msg_i[:80]}")
                report.append(f"- ⚠️ פתיח קבוע נכשל: {msg_i[:150]}")
        else:
            st.done_step("full_intro", "אין פורמט עם פתיח קבוע")

    # ═══════════════ v8.6 — כל השערים לפני הקידום ל-FINAL ═══════════════
    # שורש (P0-1/2/3/7): עד כה cut_qa, canon_lint ו-broll_seam רצו **אחרי**
    # PENDING.replace(FINAL) — כלומר גם אם היו מוצאים הפרה, ה-FINAL כבר היה על
    # הדיסק. במקביל: canon_lint עשה sys.exit(1) על 8 חוקי HARD_FAIL וה-returncode
    # נזרק; cut_qa עשה sys.exit(0) תמיד; ו-caption_safety.py (106 שורות: RTL,
    # חפיפות cues, תווים ערביים, מונוטוניות, קיום פונט) לא היה מחובר בכלל.
    # מעכשיו: כל השערים רצים על FINAL_PENDING, נאספים ל-blockers, ורק אם הרשימה
    # ריקה מתבצע הקידום. בונוס: canon_lint לפני הקידום פותר גם את
    # approve_publish_gate שנכשל תמיד בגימור ידני (הוא בודק רק כש-FINAL קיים).
    pil_py = WHISPER_PY if WHISPER_PY.exists() else sys.executable
    keeps_file = KEEPS if KEEPS.exists() else None
    blockers = []

    # 9-VH. QA פתיחה חזותית על התוצר בפועל (אחרי כתוביות/פתיח) — רק כשהוחל טיפול.
    # מעבר מוצהר לעולם אינו פוטר פריים שחור/לבן, A→B→A או מקור לא נכון.
    VHQA_REPORT = W / "visual_hook_qa.json"
    if vh_state and vh_state["applied"]:
        st.step("visual_hook_qa")
        try:
            import visual_hook_qa as VHQA
            from relvid import hook_render as HOOKR
            _band = vh_state.get("band") or HOOKR.caption_band(WORDS, a.brand)
            _q = VHQA.check(EXPORT, PENDING, vh_state["plan"], vh_state.get("receipt"),
                            intro_frames=int(round(intro_sec * 30)), band=_band,
                            approved_digest=vh_state.get("approved_digest"),
                            reservations=vh_state["context"]["reservations"])
            VHOOK.atomic_write_json(VHQA_REPORT, _q)
            vh_state["report"]["qa"] = {"pass": _q["pass"], "hard_failures": _q["hard_failures"]}
            VHOOK.atomic_write_json(W / VHOOK.FILES["report"], vh_state["report"])
            if not _q["pass"]:
                blockers.append("visual_hook_qa: " + ", ".join(_q["hard_failures"]))
            st.done_step("visual_hook_qa", "PASS" if _q["pass"] else "FAIL " + ",".join(_q["hard_failures"]))
            report.append(f"- 🎬 QA פתיחה חזותית: {'PASS' if _q['pass'] else 'FAIL'} · "
                          f"{_q['frames_checked']} פריימים בחלון · חציון סטייה {_q.get('median_err')}")
        except Exception as e:
            blockers.append(f"visual_hook_qa: שגיאה {e}")
            st.done_step("visual_hook_qa", f"שגיאה: {e}")

    # 9a. תמלול האימות — הצטרפות לתהליך הרקע לפני qa_gates
    if _verify_thread is not None:
        st.step("verify_asr_wait")
        _verify_thread.join(timeout=1800)
        if _verify_thread.is_alive() or _verify_state.get("rc") not in (0,) or not VERIFY.exists():
            st.done_step("verify_asr_wait", f"לא זמין (rc={_verify_state.get('rc')}) — G6b יהיה אזהרה")
            report.append(f"- ⚠️ תמלול אימות לא הושלם: {_verify_state.get('err', '')[:120]}")
        else:
            st.done_step("verify_asr_wait", "תמלול אימות מוכן")

    # 9b. Visual Cut QA — חוסם על פריים שחור / תקיעה בגבול חיתוך
    st.step("cut_qa")
    cq_cmd = [pil_py, HERE / "cut_qa.py", "--video", EXPORT, "--speed", str(_speed),
              "--out", W / "cut_qa_report.json", "--sheet", W / "cut_qa_sheet.jpg"]
    if keeps_file:
        cq_cmd += ["--keeps", keeps_file]
    r = sh(cq_cmd, timeout=600)
    cq_line = (r.stdout.strip().splitlines() or [""])[-1][:160]
    if r.returncode == 1:
        blockers.append(f"cut_qa: {cq_line}")
    st.done_step("cut_qa", cq_line if r.returncode in (0, 1) else f"שגיאה rc={r.returncode} (לא חוסם)")
    report.append(f"- גבולות חיתוך: {cq_line}")

    # 9c. caption_safety — שער בטיחות כתוביות (P0-2: היה קוד מת)
    st.step("caption_safety")
    r = sh(["python3", HERE / "caption_safety.py", "--words", WORDS, "--brand", a.brand,
            "--dur", f"{ffdur(PENDING):.2f}", "--out", W / "caption_safety_report.json"],
           timeout=120)
    cs_line = (r.stdout.strip().splitlines() or [""])[-1][:160]
    if r.returncode != 0:
        blockers.append(f"caption_safety: {cs_line}")
    st.done_step("caption_safety", cs_line)
    report.append(f"- בטיחות כתוביות: {cs_line}")

    # 9c2. G9 — כל מילה שנצרבת היא מילה בעברית מוכרת. חוסם.
    # שורש (הראל 30.7.26): "הכתוביות מלאות בשגיאות כתיב ולא בעברית תקינה".
    # נצרבו "ועל כל צפוף" בהוק, "הציעות", "בשוט הצהריים" — ואף שער לא הסתכל
    # על המילים עצמן. ראה `he_lexicon.py` ו-`caption_lexicon_qa.py`.
    st.step("lexicon")
    r = sh(["python3", HERE / "caption_lexicon_qa.py", "--workdir", W], timeout=120)
    lx_line = (r.stdout.strip().splitlines() or [""])[0][:160]
    if r.returncode != 0:
        blockers.append(f"G9_lexicon: {lx_line}")
    st.done_step("lexicon", lx_line)
    report.append(f"- G9 לקסיקון עברי: {lx_line}")

    # 9c2b. V7 — הכתוביות **כפי שנצרבו**, על הפיקסלים (v9.29, 22.9.26).
    # כל שערי הכתוביות עד כאן בודקים את המילים; זה בודק את הפריים: כל cue
    # מושווה לרינדור הצפוי ולרינדור ההפוך (תקלת raqm+get_display, 24.7.26).
    # חוסם רק על דגלים שהכיול הוכיח (0 חיובי-שגוי על 1,225 cues מאושרים,
    # ≥95% תפיסה בהזרקה, ונבדק על 40 FINAL חיים) — reversed/missing/tofu.
    # השאר מדווח ל-preflight (P20) עם הגיליון.
    st.step("caption_vision")
    # v9.37: V7 מודד מול מה שנצרב בפועל — מילים שמוצגות כ-MG ירדו מהכתוביות בכוונה (לא "missing")
    r = sh([pil_py, HERE / "caption_vision.py", "--workdir", W, "--video", PENDING,
            "--words", CAPS_WORDS, "--brand", a.brand, "--intro-offset", f"{intro_sec:.3f}",
            "--strict"], timeout=600)
    cv_line = (r.stdout.strip().splitlines() or ["ללא פלט"])[0][:170]
    if r.returncode == 1:
        blockers.append(f"V7_captions: {cv_line}")
    st.done_step("caption_vision", cv_line if r.returncode in (0, 1)
                 else f"שגיאה rc={r.returncode} (לא חוסם — לא נמדד)")
    report.append(f"- 👁️ V7 כתוביות על הפיקסלים: {cv_line}")

    # 9c2c. בירולים כפי שנחתו ב-FINAL (v9.30): B1 הקליפ שנצרב באמת על המסך ·
    # B3 בירול של הראל בתוכן מועדון · B4 פסיקת עיגון (אם קיימת ותואמת). חוסם רק
    # דגלים שהכיול הוכיח (broll-vision-calibration.json); השאר ל-preflight P21.
    if broll_applied:
        st.step("broll_vision")
        # v9.37: כששכבת MG מורכבת מעל בירול, B1 (דמיון לפריימי הקליפ) נמדד על הבסיס שלפני ה-MG —
        # הנחיתה נקבעת שם, וה-MG מורכב מעליו ב-overlay יחיד מאומת (MG8). מדווח במפורש, לא בשקט.
        _bv_video = mg_pre_base if mg_pre_base else PENDING
        if mg_pre_base:
            report.append(f"- 👁️ בירולים נמדדו על {Path(mg_pre_base).name} (לפני שכבת ה-MG)")
        r = sh([pil_py, HERE / "broll_vision_qa.py", "check", "--workdir", W,
                "--video", _bv_video, "--intro-offset", f"{intro_sec:.3f}", "--strict"], timeout=600)
        bv_line = (r.stdout.strip().splitlines() or ["ללא פלט"])[0][:170]
        if r.returncode == 1:
            blockers.append(f"broll_vision: {bv_line}")
        st.done_step("broll_vision", bv_line if r.returncode in (0, 1)
                     else f"שגיאה rc={r.returncode} (לא חוסם — לא נמדד)")
        report.append(f"- 👁️ בירולים ב-FINAL: {bv_line}")

    # 9c3. פרופיל התוצר מול המעטפת שנמדדה מסרטונים שהראל אישר.
    # כל שאר השערים מודדים את **התוכנית**; זה מודד את מה שהראל באמת רואה.
    # שלוש פעמים ברצף התוכנית עברה והתוצר היה פגום — ראה bench/output_profile.py.
    # דיווח בלבד: אלה מדדי טעם בתוך טווח, לא חוקי פיזיקה.
    st.step("profile")
    r = sh([pil_py, HERE / "bench" / "output_profile.py", "--workdir", W,
            "--video", PENDING], timeout=900)
    pf_line = (r.stdout.strip().splitlines() or ["ללא פלט"])[0][:170]
    st.done_step("profile", pf_line)
    report.append(f"- 📐 פרופיל מול סרטונים מאושרים: {pf_line}")
    for extra in (r.stdout.strip().splitlines() or [])[1:5]:
        report.append(f"  {extra.strip()}")

    # 9d. תפרי בירול — על PENDING (ולא על FINAL, שעוד לא קיים). דיווח בלבד.
    bplan = W / "broll_plan.json"
    if bplan.exists():
        st.step("broll_seam")
        r = sh([pil_py, HERE / "broll_seam_qa.py", "--video", PENDING,
                "--plan", bplan, "--out", W / "broll_seam_report.json"], timeout=600)
        line = (r.stdout.strip().splitlines() or ["ללא פלט"])[0]
        st.done_step("broll_seam", line[:120])
        report.append(f"- תפרי בירול: {line}")

        # v9.8 — דקדוק חזותי של הרצף. `broll_seam_qa` שואל "התפר חושף את
        # הדובר?"; זה שואל "הרצף נקרא טוב?". נמדד על האופן-ג'ים: **11 שוטים
        # בינוניים ברצף, אפס רחבים** — עבר את כל השערים הקיימים.
        # מדווח ואינו חוסם: הבריכה עצמה 47/56 medium, ולכן שער חוסם היה
        # מכשיל סרטונים תקינים במקום להצביע על חוב צילום.
        st.step("broll_sequence")
        r = sh([pil_py, HERE / "broll_sequence_qa.py", "--workdir", W],
               timeout=600)
        line = (r.stdout.strip().splitlines() or ["ללא פלט"])[0]
        st.done_step("broll_sequence", line[:120])
        report.append(f"- רצף מצע: {line}")

        # v9.9 — **מה המערכת מציעה במקום.** שער שאומר רק "לא" לא סיים את
        # העבודה: שלושה מקורות כבר ידעו מה חסר (משפט בלי עוגן · רצף חוזר ·
        # בריכה חד-גודלית) ואף אחד לא הגיע למי שמצלם. הפלט הוא פריטי צילום
        # מוכנים לבורד הסושיאל. דיווח בלבד — לא כותב ל-Monday מכאן.
        r = sh([pil_py, HERE / "broll_shot_debt.py", "--workdir", W], timeout=300)
        line = (r.stdout.strip().splitlines() or ["ללא פלט"])[0]
        report.append(f"- {line}")

    # 9e. canon_lint — 8 חוקי HARD_FAIL, ועכשיו ה-returncode באמת נבדק
    st.step("canon")
    r = sh(["python3", HERE / "canon_lint.py", "--workdir", W,
            "--content-type", a.content_type, "--brand", a.brand,
            "--out", W / "canon_report.json"], timeout=300)
    if r.returncode != 0:
        hard_lines = [ln for ln in (r.stdout or "").splitlines() if "❌" in ln]
        blockers.append("canon_lint: " + ("; ".join(l.strip() for l in hard_lines[:4]) or "HARD_FAIL"))
    st.done_step("canon", "PASS" if r.returncode == 0 else "HARD_FAIL — ראה canon_report.json")

    # 9f. qa_gates — כולל G6b מול תמלול האימות
    st.step("qa")
    qa_cmd = ["python3", HERE / "qa_gates.py", "--video", PENDING, "--words", WORDS,
              "--truth", (W / "whisper_export_offset.json") if (W / "whisper_export_offset.json").exists() else WEXP,
              "--report", W / "qa_report.json",
              "--content-type", a.content_type]
    if a.length_reason:
        qa_cmd += ["--length-reason", a.length_reason]
    if VERIFY.exists():
        qa_cmd += ["--truth-measured", VERIFY]
    if vh_state and vh_state["applied"] and VHQA_REPORT.exists():
        qa_cmd += ["--visual-hook-qa", VHQA_REPORT]
    r = sh(qa_cmd, timeout=900)
    report.append("\n## QA\n```\n" + r.stdout.strip() + "\n```")
    if r.returncode != 0:
        blockers.append("qa_gates: ראה qa_report.json")
    st.done_step("qa", "PASS" if r.returncode == 0 else "FAIL")

    # 9f2. preflight_critic — "הצפייה של הראל, לפני הראל" (v9.13, הראל 16.8.26:
    # "מספר רב של עריכות מחדש במקום מוצר מוגמר כבר מהתחלה"). מרכז את כל
    # הדוחות + בדיקות-הכאב (קפיצה כפולה בגבול · הבהוב · בירול בלי הקשר ·
    # Hook/CTA) לפסק-דין אחד: ready_for_harel. לא חוסם — הממצאים הקשים כבר
    # חסומים במעלה הזרם; זה קובע מה כתוב בשורה הראשונה של הדיווח להראל,
    # וממצא high פתוח הוא החלטה מודעת שמדווחת, לא תקלה שקטה.
    st.step("preflight")
    r = sh(["python3", HERE / "preflight_critic.py", "--workdir", W,
            "--out-dur", f"{ffdur(PENDING):.2f}"], timeout=300)
    pfc_line = (r.stdout.strip().splitlines() or ["ללא פלט"])[0][:170]
    st.done_step("preflight", pfc_line)
    report.append(f"- 🎭 מבקר-קדם (מה הראל היה מתקן): {pfc_line}")
    for extra in (r.stdout.strip().splitlines() or [])[1:6]:
        report.append(f"  {extra.strip()}")

    # 9g. הכרעה — כל השערים או שאף אחד. התוצר נשאר FINAL_PENDING.
    if blockers:
        (W / "gate_blockers.json").write_text(
            json.dumps({"blockers": blockers, "ts": time.strftime("%Y-%m-%d %H:%M:%S")},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        report.append("\n### ❌ שערים חוסמים\n" + "\n".join(f"- {b}" for b in blockers))
        fail("שערים חוסמים: " + " | ".join(blockers[:3]) +
             " — התוצר נשאר FINAL_PENDING.mp4 (לא FINAL). ראה gate_blockers.json")

    # 9h. קידום ל-FINAL — רק אחרי שכל השערים עברו. FINAL קודם מגובה.
    if FINAL.exists():
        prev = W / f"FINAL_prev_{time.strftime('%Y%m%d-%H%M%S')}.mp4"
        FINAL.replace(prev)
        report.append(f"- FINAL קודם גובה: {prev.name}")
    PENDING.replace(FINAL)

    # 10. קאבר — v9.12 (2.8.26): שער כניסה אחד, לשני המותגים.
    # שורש התיקון: עד כאן הפייפליין **דילג** על הקאבר בכל מותג שאינו rel
    # ("→ oshia-cover-creator"), ולכן כל קאבר אישי נבנה ידנית — ושם בדיוק
    # אבדה המשמעת (פריים עם כתוביות צרובות, שורה אחת). עכשיו שני המותגים
    # נבנים באותו מסלול, מ-EXPORT הנקי, עם שערי G-COVER1/2/3.
    if a.title and not (a.subtitle or "").strip():
        report.append("- ⚠️ קאבר לא נבנה: יש --title בלי --subtitle. "
                      "קאבר הוא תמיד 2 שורות (G-COVER2) — ספק גם תת-כותרת.")
    elif a.title:
        st.step("thumbnail")
        tdir = W / "thumb"; tdir.mkdir(exist_ok=True)
        pybin = WHISPER_PY if WHISPER_PY.exists() else sys.executable  # numpy+PIL+cv2
        brand = "personal" if a.brand != "rel" else "rel"
        r2 = sh([pybin, HERE / "thumbnail" / "cover_make.py",
                 "--video", EXPORT,                     # תמיד המקור הנקי
                 "--title", a.title, "--subtitle", a.subtitle,
                 "--brand", brand, "--out", W / "thumbnail.png",
                 "--band-center", "0.725"])
        st.done_step("thumbnail", "✓" if r2.returncode == 0 else "נכשל (ידני)")
        report.append(f"- קאבר ({brand}): "
                      + ("נבנה מ-EXPORT נקי · 2 שורות · Studentit"
                         if r2.returncode == 0 else "נכשל — ראה cover_report.json"))

    # 11. (v7.7, הראל 25.7) רשומת מקור ל-FINAL — בדיוק ממה הוא נבנה: revision,
    # edl_hash, keep_segments, הידוק (tight_keeps) ו-speed. זה מה שמאפשר
    # לאפליקציה לדעת אם הציר שמוצג בה הוא הציר של ה-FINAL או גרסה אחרת.
    # נכתב אחרון — אחרי שאף שלב לא נוגע יותר ב-FINAL.mp4.
    try:
        sys.path.insert(0, str(HERE))
        from relvid import sync as _sync
        # v9.19 — הפתיח מזיז את כל ציר ה-FINAL ב-intro_sec מול ה-EDL. בלי
        # הרשומה הזו, הערה באפליקציה על 00:12 מצביעה על 00:02 בציר העריכה.
        # v9.30: נרשם תמיד, גם 0 — "לא רשום" נאמד מהפיקסלים (caption_vision) ומסומן
        # estimated; היעדר השדה לא אמור להיות המקרה הנפוץ (מאסל-מן 1.8.26: 10.1ש לא נרשם).
        _extra = {"intro_offset_sec": round(intro_sec, 3)}
        if vh_state:
            # מה שנקשר ל-FINAL הזה בלבד — ה-artifact מקפיא את קבצי הלוואי רק כשה-digest תואם
            _extra["visual_hook"] = {
                "mode": vh_state["mode"], "applied": bool(vh_state["applied"]),
                "recipe": vh_state["plan"]["recipe"], "plan_digest": vh_state["plan"]["plan_digest"],
                "input_digest": vh_state["context"]["input_digest"],
                "approved_digest": vh_state.get("approved_digest"),
                "sidecars": {n: VHOOK.file_sha256(W / n) for n in
                             (VHOOK.FILES["plan"], VHOOK.FILES["report"], VHOOK.FILES["render"],
                              VHOOK.FILES["qa"]) if (W / n).exists() and
                             (vh_state["applied"] or n in (VHOOK.FILES["plan"], VHOOK.FILES["report"]))}}
        prov = _sync.write_provenance(
            W, run_id=os.environ.get("REL_RUN_ID"), extra=_extra or None)
        trimmed = _sync.keeps_dur(prov.get("tighten_trims_source"))
        report.append(f"- מקור FINAL נרשם: revision {prov.get('revision_id')} · "
                      f"הידוק הוריד {trimmed}ש (FINAL_PROVENANCE.json)")
    except Exception as e:
        report.append(f"- ⚠️ רשומת מקור ל-FINAL נכשלה (לא חוסם): {e}")

    # v9.4 — שימור הגרסה גם בהרצה ידנית בלי run_finish.py (שם זה כבר קורה).
    try:
        from relvid import artifacts as _art
        _a = _art.create_artifact(W, run_id=os.environ.get("REL_RUN_ID"),
                                  summary="גימור מקומי")
        report.append(f"- גרסה נשמרה לצמיתות: {_a['artifact_id']} (v{_a['version']})")
    except Exception as e:
        report.append(f"- ⚠️ שמירת הגרסה הקבועה נכשלה (לא חוסם): {e}")

    report.append("")
    report.append(st.timings_md())
    report.append(f"\n✅ FINAL.mp4 מוכן ({ffdur(FINAL):.1f}ש) — אפס Descript.")
    (W / "FINISH_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    st.finish(True, "FINAL.mp4 מוכן")
    print("DONE")

if __name__ == "__main__":
    main()
