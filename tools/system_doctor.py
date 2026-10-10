#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
system_doctor.py — בדיקת בריאות המערכת (v7). פלט אנושי + JSON (--json).
כל בדיקה: PASS / WARN / FAIL + פירוט. exit 0 אם אין FAIL.
"""
import argparse
import importlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
sys.path.insert(0, str(HERE))

WHISPER_PY = Path.home() / ".rel-whisper" / "bin" / "python"
BRAND_ASSETS_CANDIDATES = [SYSDIR / "brand-assets", SYSDIR / "descript-brand-assets"]

try:
    import gate_registry as GR      # הנימוק נכנס לדוח כדאטה (ראה gate_registry)
except Exception:                   # pragma: no cover
    GR = None

checks = []


def add(name, status, detail=""):
    rec = {"check": name, "status": status, "detail": str(detail)[:300]}
    if GR:
        rec["why"] = GR.annotate("system_doctor", name)
    checks.append(rec)


def clip_gender(item):
    """מי נראה בפריים: 'm' / 'w' / '?' (לא נספר).

    `people` נקבע באימות ויזואלי ולכן גובר תמיד. הנפילה-אחורה ל-
    `audience`/`tags` היא היוריסטיקת-שם-קובץ — היא זו שיצרה את ההטיה
    שהראל זיהה ב-31.7.26, ולכן היא אחרונה ולא ראשונה. קליפ ללא `people`
    וללא רמז בשם נספר '?' — השער מעדיף "לא יודע" על ניחוש.
    """
    people = set(item.get("people") or [])
    if people:
        if "גברים" in people:
            return "m"
        if "נשים" in people:
            return "w"
        return "?"          # ילדים / מעורב — לא נספרים לאיזון
    hint = set(item.get("audience") or []) | set(item.get("tags") or [])
    if {"נשים", "women"} & hint:
        return "w"
    if {"גברים", "men"} & hint:
        return "m"
    return "?"


def run(cmd, timeout=30):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        class R:
            returncode, stdout, stderr = 1, "", str(e)
        return R()



# ═══════════════════════════════════════════════════════════════════════
# v9.26 — אפליקציית הרוויו רצה על הפייתון הנכון, ו-launchd הוא הבעלים שלה.
# ל-python3 המערכתי אין flask. ב-19.9.26 נמצא שרת יתום (nohup ידני) שתופס את
# 5112, ו-launchd בלולאת קריסה של 1,243 הפעלות ("Address already in use").
# ═══════════════════════════════════════════════════════════════════════
REVIEW_PY = str(Path.home() / ".rel-whisper" / "bin" / "python")
REVIEW_PLIST = Path.home() / "Library" / "LaunchAgents" / "com.rel.review-app.plist"


def review_app_verdict(plist_python, has_flask, listener_pid, listener_venv, launchd_pid):
    """הכרעה טהורה (נבדקת בהזרקת-כשל). מחזיר (status, detail)."""
    if not plist_python:
        return "FAIL", "אין LaunchAgent com.rel.review-app — השרת לא יעלה אחרי הפעלה מחדש"
    if plist_python != REVIEW_PY:
        return "FAIL", f"ה-LaunchAgent מריץ {plist_python} ולא {REVIEW_PY} (אין שם flask)"
    if not has_flask:
        return "FAIL", f"{REVIEW_PY} בלי flask — pip install flask"
    if not listener_pid:
        return "WARN", "אין שרת על 5112 — launchctl kickstart -k gui/$UID/com.rel.review-app"
    if not listener_venv:
        return "FAIL", f"השרת על 5112 (pid {listener_pid}) לא רץ מ-.rel-whisper"
    if launchd_pid and str(listener_pid) != str(launchd_pid):
        return "WARN", (f"שרת יתום על 5112 (pid {listener_pid}) ו-launchd בלולאת קריסה "
                        f"(pid {launchd_pid}) — kill {listener_pid} && launchctl kickstart")
    if not launchd_pid:
        return "WARN", f"השרת (pid {listener_pid}) לא בבעלות launchd — לא יחזור אחרי קריסה"
    return "PASS", f"launchd pid {listener_pid} · {REVIEW_PY} · flask"


def _review_app_probe():
    import plistlib
    import subprocess as sp
    plist_py = None
    if REVIEW_PLIST.exists():
        try:
            plist_py = (plistlib.loads(REVIEW_PLIST.read_bytes()).get("ProgramArguments") or [None])[0]
        except Exception:
            plist_py = None
    has_flask = sp.run([REVIEW_PY, "-c", "import flask"], capture_output=True).returncode == 0 \
        if Path(REVIEW_PY).exists() else False
    lp = sp.run(["lsof", "-ti", ":5112", "-sTCP:LISTEN"], capture_output=True, text=True).stdout.split()
    listener = lp[0] if lp else None
    venv = False
    if listener:
        venv = ".rel-whisper" in sp.run(["lsof", "-p", listener], capture_output=True, text=True).stdout
    ld = None
    out = sp.run(["launchctl", "list", "com.rel.review-app"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if '"PID"' in line:
            ld = line.split("=")[1].strip(" ;")
    return review_app_verdict(plist_py, has_flask, listener, venv, ld)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    # Python
    v = sys.version_info
    add("python", "PASS" if v >= (3, 9) else "FAIL", f"{sys.version.split()[0]}")

    # ffmpeg/ffprobe + פילטרים
    for tool in ("ffmpeg", "ffprobe"):
        p = shutil.which(tool)
        add(tool, "PASS" if p else "FAIL", p or "לא נמצא ב-PATH")
    if shutil.which("ffmpeg"):
        r = run(["ffmpeg", "-hide_banner", "-filters"])
        for filt in ("silencedetect", "loudnorm", "alimiter", "gblur", "xfade"):
            add(f"ffmpeg filter {filt}",
                "PASS" if filt in r.stdout else "FAIL")

    # venv whisper
    if WHISPER_PY.exists():
        r = run([str(WHISPER_PY), "-c",
                 "import faster_whisper, PIL, bidi; import numpy; print('ok')"])
        add("rel-whisper venv (faster_whisper+PIL+bidi+numpy)",
            "PASS" if "ok" in r.stdout else "FAIL", r.stderr[-200:])
        r2 = run([str(WHISPER_PY), "-c",
                  "from faster_whisper.utils import download_model; print('ok')"])
        add("faster-whisper importable", "PASS" if "ok" in r2.stdout else "WARN")
    else:
        add("rel-whisper venv", "FAIL", f"לא נמצא: {WHISPER_PY}")

    # flask — השרת רץ עם venv rel-whisper (fallback: python3 מערכתי)
    try:
        importlib.import_module("flask")
        add("flask", "PASS", "python3 מערכתי")
    except ImportError:
        r = run([str(WHISPER_PY), "-c", "import flask; print('ok')"])
        add("flask", "PASS" if "ok" in r.stdout else "FAIL",
            "ב-venv rel-whisper (השרת רץ איתו)" if "ok" in r.stdout
            else "לא נמצא לא ב-python3 ולא ב-venv")

    # פונט מותג
    font_hits = []
    for base in BRAND_ASSETS_CANDIDATES:
        font_hits += list(base.glob("**/Assistant-ExtraBold*")) if base.exists() else []
    add("font Assistant ExtraBold", "PASS" if font_hits else "FAIL",
        str(font_hits[0]) if font_hits else "לא נמצא ב-brand assets")

    # תיקיות + הרשאות כתיבה
    from relvid.paths import work_root as _wr, describe as _pdesc   # v8.6 (P0-11)
    _WORK = _wr()
    for d in (_WORK, SYSDIR / "tools", SYSDIR / "review-app"):
        ok = d.exists() and os.access(d, os.W_OK)
        add(f"dir {d.name} writable", "PASS" if ok else "FAIL", str(d))

    # v8.6 (P0-11) — תיקיית העבודה לא צריכה לשבת ב-iCloud. eviction באמצע גימור
    # הוא כשל שאי אפשר להתגונן ממנו בקוד (אפל מחליטה), והוא נראה כשגיאת ffmpeg
    # אקראית. cleanup_work.py מזהיר על זה במפורש. FAIL כדי שזה לא יישאר "אזהרה
    # שהתרגלנו אליה".
    _pd = _pdesc()
    add("work root off iCloud", "FAIL" if _pd["on_icloud"] else "PASS",
        f"{_pd['work_root']} (מקור: {_pd['source']})"
        + (" · הרץ tools/migrate_work_root.py" if _pd["on_icloud"] else ""))
    if _pd["legacy_still_present"]:
        add("legacy _work leftover", "WARN",
            f"{_pd['legacy']} עדיין קיימת — למחוק אחרי אימות שהמיגרציה תקינה")

    # פורט 5112 (רץ = PASS-info; תפוס ע"י אחר אי אפשר להבחין — בודקים health)
    s = socket.socket()
    s.settimeout(1)
    port_open = s.connect_ex(("127.0.0.1", 5112)) == 0
    s.close()
    if port_open:
        r = run(["curl", "-s", "-m", "2", "http://127.0.0.1:5112/health"])
        add("review-app :5112", "PASS" if '"ok"' in r.stdout else "WARN",
            "רץ ועונה" if '"ok"' in r.stdout else "הפורט תפוס אבל /health לא עונה")
    else:
        add("review-app :5112", "WARN", "לא רץ (הראל מפעיל עם ▶ הפעל רוויו)")

    # SQLite schema
    try:
        from relvid import registry as reg
        n = reg.rebuild()
        con = sqlite3.connect(reg.DB_PATH)
        cnt = con.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        con.close()
        add("sqlite registry", "PASS", f"{cnt} פרויקטים באינדקס (rebuild הצליח)")
    except Exception as e:
        add("sqlite registry", "FAIL", e)

    # v7.7: דריפט סנכרון — ציר האפליקציה מול מה שנחתך בפועל / מול ה-FINAL
    try:
        from relvid import registry as reg2
        from relvid import sync as sync_mod
        drifted, ahead = [], []
        for d in reg2.iter_workdirs():
            st = sync_mod.sync_badge(d)
            if st == "drift":
                drifted.append(d.name)
            elif st == "edl_ahead":
                ahead.append(d.name)
        if drifted:
            add("sync ציר↔חיתוך", "FAIL",
                f"{len(drifted)} פרויקטים עם ציר לא מסונכרן: {', '.join(drifted[:4])} "
                f"— תיקון: review_cli.py sync-all")
        else:
            add("sync ציר↔חיתוך", "PASS", "כל הפרויקטים מסונכרנים")
        add("sync ציר↔FINAL", "WARN" if ahead else "PASS",
            f"{len(ahead)} פרויקטים שהציר בהם חדש מה-FINAL: {', '.join(ahead[:4])}"
            if ahead else "אין FINAL מיושן")
    except Exception as e:
        add("sync ציר↔חיתוך", "FAIL", e)

    # brand assets + מוזיקה
    music = None
    for base in BRAND_ASSETS_CANDIDATES:
        if (base / "music").exists():
            music = base / "music"
            break
    if music:
        tracks = list(music.glob("*.mp3"))
        add("music catalog", "PASS" if tracks else "FAIL", f"{len(tracks)} טראקים")
    else:
        add("music catalog", "FAIL", "אין תיקיית music ב-brand assets")

    # B-roll catalog
    cfg = json.loads((HERE / "broll-catalog-config.json").read_text(encoding="utf-8")) \
        if (HERE / "broll-catalog-config.json").exists() else {}
    cat_path = cfg.get("catalog_path")
    if cat_path and Path(cat_path).expanduser().exists():
        try:
            cat = json.loads(Path(cat_path).expanduser().read_text(encoding="utf-8"))
            n_clips = len(cat.get("items") or cat.get("clips") or
                          (cat if isinstance(cat, list) else []))
            add("broll catalog", "PASS" if n_clips else "WARN", f"{n_clips} קליפים")
        except Exception as e:
            add("broll catalog", "WARN", f"קיים אך לא נקרא: {e}")
    else:
        add("broll catalog", "WARN", f"catalog_path לא נמצא: {cat_path}")

    # דיסק פנוי
    du = shutil.disk_usage(str(SYSDIR))
    free_gb = du.free / 1e9
    add("free disk", "PASS" if free_gb > 20 else ("WARN" if free_gb > 5 else "FAIL"),
        f"{free_gb:.0f}GB פנויים")

    # iCloud — קבצים לא-מקומיים בפרויקטים פעילים
    evicted = list(_WORK.glob("*/.*.icloud")) + list(_WORK.glob("*/*.icloud"))
    add("iCloud eviction in work root", "PASS" if not evicted else "WARN",
        f"{len(evicted)} קבצים בענן בלבד" if evicted else "הכל מקומי")

    # ── V3: המעטפת הנמדדת קיימת, והספים בקוד נגזרים ממנה ──
    # הכלל: כל סף שנוגע לקצב/שקט/תפרים חייב להיות ניתן לגזירה מחדש ממדידה,
    # לא מניחוש. אם הקובץ נעלם — הספים הופכים למספרי קסם.
    try:
        ref = SYSDIR / "tools" / "reference_profile.json"
        if not ref.exists():
            add("V3 reference profile", "FAIL",
                "אין reference_profile.json — הריצו bench/output_profile.py --build-reference")
        else:
            rd = json.loads(ref.read_text(encoding="utf-8"))
            env = rd.get("envelope", {})
            n = rd.get("n_projects", 0)
            sys.path.insert(0, str(SYSDIR / "tools"))
            import edit_plan as _EP
            cps_hi = env.get("cuts_per_sec", {}).get("max", 0)
            ok = n >= 8 and _EP.CUTS_PER_SEC_HARD >= cps_hi * 0.8
            add("V3 reference profile", "PASS" if ok else "WARN",
                f"{n} סרטונים · תפרים/ש {env.get('cuts_per_sec', {}).get('min')}–{cps_hi} · "
                f"שקט {env.get('silence_pct', {}).get('min')}–{env.get('silence_pct', {}).get('max')}%")
    except Exception as e:
        add("V3 reference profile", "FAIL", f"שגיאה: {e}")

    # ── v9.4: שכבת הבירול של הבמאי ─────────────────────────────────────────
    # שלוש טענות שנשברו בפועל ב-30.7.26 ולכן נבדקות ולא מונחות:
    #   1. הפרומפט קיים ורשום — בלי זה הפאס נופל בזמן ריצה ולא בזמן בדיקה.
    #   2. הבריכה המסוננת אינה ריקה — `topic=""` נתן 0 בירולים בלי שאף שער צעק.
    #   3. אף קליף דיבור-למצלמה לא שורד את הסינון — "ראיון עם מתאמנת" נבחר
    #      פעם אחת לסרטון על שעות ומחיר.
    try:
        sys.path.insert(0, str(SYSDIR / "tools"))
        from relvid.provider import prompt_text as _pt
        _pt("broll")
        import subprocess as _sp, tempfile as _tf
        with _tf.TemporaryDirectory() as _d:
            _o = Path(_d) / "sl.json"
            _r = _sp.run([sys.executable, str(SYSDIR / "tools" / "broll_pick.py"),
                          "--shortlist", "--content-type", "conversion",
                          "--json", str(_o)], capture_output=True, text=True)
            if _r.returncode != 0 or not _o.exists():
                add("V3 broll shortlist", "FAIL",
                    f"broll_pick --shortlist נכשל: {(_r.stderr or _r.stdout)[-120:]}")
            else:
                _sl = json.loads(_o.read_text(encoding="utf-8"))
                _n = _sl.get("pool_size", 0)
                _bad = [c["label"] for c in _sl.get("clips", [])
                        if any(t in c["label"] for t in ("ראיון", "עדות"))]
                add("V3 broll shortlist",
                    "PASS" if _n >= 5 and not _bad else "FAIL",
                    (f"בריכה {_n} קליפים · אפס דיבור-למצלמה" if not _bad
                     else f"קליפי ראיון עברו את הסינון: {_bad[:3]}")
                    if _n >= 5 else f"בריכה {_n} — קטנה מדי, בירול לא יתוכנן")
    except Exception as e:
        add("V3 broll shortlist", "FAIL", f"שגיאה: {e}")

    # ── v9.6: איזון מגדרי בבריכת הבירול (הראל 31.7.26) ─────────────────────
    # "יש בירולים רק של נשים? מה עם קצת גברים."
    # נמדד: **35 מתוך 35** בבריכה המאומתת מתויגים 'נשים', אפס גברים — כלומר
    # כל מצע בירולים שהמערכת תבנה, בכל סרטון המרה, יראה רק מתאמנות. זה לא
    # באג בקוד אלא **הטיה בקוריישן** שאף אחד לא ראה כי אף אחד לא ספר.
    # שער מונע שזה יחזור בשקט אחרי שהבריכה תורחב.
    try:
        _cfg = json.loads((SYSDIR / "tools" / "broll-catalog-config.json")
                          .read_text(encoding="utf-8"))
        _cat = json.loads(Path(_cfg["catalog_path"]).read_text(encoding="utf-8"))["items"]
        _ver = set(_cfg.get("verified_member_files", []))
        _dis = {d.get("file") for d in _cfg.get("disabled_files", []) if d.get("file")}
        _pool = [i for i in _cat if i["file"] in _ver and i["file"] not in _dis]

        # v9.7: `people` (מי נראה בפריים, נקבע באימות ויזואלי) גובר על
        # ההיוריסטיקה הישנה שקראה `audience`/`tags` — שני שדות שנגזרים משם
        # הקובץ, וש-`audience` מהם בכלל אומר "למי הקליפ מיועד". הנפילה-אחורה
        # נשארת כדי שקליפ חדש שטרם אומת ייספר כ-"?" ולא ישקר לשער.
        _g = [clip_gender(i) for i in _pool]
        _w, _m = _g.count("w"), _g.count("m")
        _tot = max(1, _w + _m)
        _minority = min(_w, _m) / _tot
        _unver = sum(1 for i in _pool if not i.get("people"))
        add("B-roll pool gender balance",
            "PASS" if _minority >= 0.15 else "WARN",
            f"{_w} נשים · {_m} גברים · {_g.count('?')} לא נספר · "
            f"{_unver} ללא אימות ויזואלי "
            + (f"(מאוזן — מיעוט {_minority:.0%})" if _minority >= 0.15
               else "— **המצע יראה מגדר אחד בלבד.** להוסיף קליפים "
                    "ל-verified_member_files"))
        # v9.7: שער סתירה-לבריף נכשל-סגור — קליפ בלי ראיה ויזואלית פשוט לא
        # נכנס למצע בתוכן המרה. לכן חוסר כיסוי אינו "פחות מידע", הוא בריכה
        # שמצטמצמת בשקט. השער הזה הופך את זה לגלוי.
        try:
            sys.path.insert(0, str(SYSDIR / "tools"))
            import broll_vision_model as _VM
            _no_vision = []
            for _it in _pool:
                try:
                    if _VM.lookup(_it["path"]) is None:
                        _no_vision.append(_it["file"])
                except OSError:
                    _no_vision.append(_it["file"])
            add("B-roll vision coverage",
                "PASS" if not _no_vision else "WARN",
                f"{len(_pool) - len(_no_vision)}/{len(_pool)} קליפים עם ראיה "
                + ("(מלא)" if not _no_vision
                   else f"— **{len(_no_vision)} לא ייכנסו למצע בהמרה.** "
                        f"להריץ broll_vision_model.py request: {_no_vision[:2]}"))
        except Exception as e:
            add("B-roll vision coverage", "WARN", f"לא נמדד: {e}")
    except Exception as e:
        add("B-roll pool gender balance", "WARN", f"לא נמדד: {e}")

    # policy עקביות: SKILL/PIPELINE מול edl-policy + qa_gates
    pol = json.loads((HERE / "edl-policy.json").read_text(encoding="utf-8"))
    add("edl-policy version", "PASS" if pol.get("version") else "WARN",
        f"version={pol.get('version', 'חסר')}")
    skill = SYSDIR / "skills" / "rel-social-video-editor" / "SKILL.md"
    if skill.exists():
        txt = skill.read_text(encoding="utf-8")
        stale = "≥1.5ש" in txt or "חור ≥1.5" in txt
        add("SKILL↔code consistency (audio gate)",
            "PASS" if not stale else "WARN",
            "SKILL עדיין מתעד gate 1.5ש בעוד הקוד 0.6" if stale else "תואם")
        # v7.8 — מפלס המוזיקה הוא מספר שמופיע גם בקוד וגם בשלושה מסמכים. בדיוק סוג
        # הערך שנסחף בשקט (קרה עם gate 1.5→0.6). כאן משווים ישירות לברירת המחדל בקוד.
        import re as _re
        m = _re.search(r'--music-lufs", type=float, default=(-?\d+(?:\.\d+)?)',
                       (HERE / "local_finish_pipeline.py").read_text(encoding="utf-8"))
        if m:
            code_lufs = float(m.group(1))
            doc_ok = f"{code_lufs:g}" in txt or f"{abs(code_lufs):g}" in txt
            add("SKILL↔code consistency (music LUFS)",
                "PASS" if doc_ok else "WARN",
                f"קוד={code_lufs:g}" + ("" if doc_ok else " — לא מופיע ב-SKILL.md"))
    # consumers של relvid
    try:
        from relvid import revisions, tasks, runner  # noqa: F401
        add("relvid package importable", "PASS")
    except Exception as e:
        add("relvid package importable", "FAIL", e)

    # ── חשיפת דובר בגבול חיתוך (v9.11) ─────────────────────────────────────
    # למה זה כאן ולא רק כבדיקת יחידה: הלקח הזה כבר **נסוג פעם אחת בשקט** —
    # v8.3 כיבה fade בתפר ב-v1, ו-v2 נבנה בלעדיו. בדיקת יחידה על הדגלים לא
    # הייתה תופסת את זה, כי הדגלים פשוט לא היו קיימים. הבדיקה כאן מודדת
    # **פיקסלים בפלט של מנוע הרינדור האמיתי**, ולכן היא נכשלת גם על שינוי
    # התנהגות של ffmpeg שאיש לא צפה. ‏~1ש.
    probe = SYSDIR / "tools" / "bench" / "ov_seam_probe.py"
    try:
        r = subprocess.run([sys.executable, str(probe)], capture_output=True,
                           text=True, timeout=180)
        d = json.loads((r.stdout or "{}").strip().splitlines()[-1])
        add("בירול חוצה קאט בלי חשיפת דובר",
            "PASS" if d.get("ok") else "FAIL",
            d.get("why", "") + (f" · {d.get('speaker_exposed_at')}"
                                if not d.get("ok") else ""))
    except Exception as e:
        add("בירול חוצה קאט בלי חשיפת דובר", "WARN", f"הבדיקה לא רצה: {e}")

    # ── פונט תת-כותרת (הראל 26.7.26: "שלא ייפול בין הכיסאות") ──────────────
    # ההערה "התת-כותרת בפונט הלא-נכון" חזרה 3+ פעמים. שלושה כשלים אפשריים,
    # כל אחד מהם שקט: (א) קובץ הפונט חסר/הוחלף, (ב) הפונט לא מכסה תווים
    # נפוצים (גרש/ספרות) ולכן נופלים לפונט אחר, (ג) בונה-קאבר אחר במערכת
    # מצייר תת-כותרת בפונט אחר. שלושתם נבדקים כאן אוטומטית.
    SUB_MUST_COVER = "אבגדץ0123456789'\"׳״?!,.:-₪"
    font_path = SYSDIR / "tools" / "thumbnail" / "fonts" / "Studentit-Full.ttf"
    if not font_path.exists():
        add("פונט תת-כותרת קיים", "FAIL", f"חסר {font_path.name} — יש עותק ב-brand-assets/fonts")
    else:
        add("פונט תת-כותרת קיים", "PASS", font_path.name)
        try:
            r = run([str(WHISPER_PY if WHISPER_PY.exists() else sys.executable), "-c",
                     f"from fontTools.ttLib import TTFont;"
                     f"t=TTFont(r'{font_path}',lazy=True);"
                     f"c=set();"
                     f"[c.update(tb.cmap.keys()) for tb in t['cmap'].tables];"
                     f"m=[x for x in {SUB_MUST_COVER!r} if ord(x) not in c];"
                     f"print('MISSING:'+''.join(m) if m else 'OK:'+str(len(c)))"], timeout=60)
            out = (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else ""
            if out.startswith("OK:"):
                add("פונט תת-כותרת מכסה תווים נדרשים", "PASS", f"{out[3:]} תווים")
            else:
                add("פונט תת-כותרת מכסה תווים נדרשים", "FAIL", out or "בדיקה נכשלה")
        except Exception as e:
            add("פונט תת-כותרת מכסה תווים נדרשים", "WARN", e)

    bad_builders = []
    for py in (SYSDIR / "tools").rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        try:
            txt = py.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line in txt.splitlines():
            s = line.strip()
            # רק ההשמה למשתנה **SUB_FONT עצמו** — לא SUB_FONT_TIER2/FALLBACK,
            # שהם פונטי-גיבוי לתו בודד וזה תקין שהם לא Studentit.
            var = s.split("=")[0].strip() if "=" in s else ""
            if var == "SUB_FONT" and "os.path.join" in s and "Studentit" not in s:
                bad_builders.append(f"{py.name}: {s[:70]}")
    if bad_builders:
        add("כל בוני-הקאבר משתמשים ב-Studentit", "FAIL", " | ".join(bad_builders))
    else:
        add("כל בוני-הקאבר משתמשים ב-Studentit", "PASS", "אין בונה שמצייר תת-כותרת בפונט אחר")

    # ── v9.12 (2.8.26) — שערי הקאבר, אחרי הקאבר עם "אז מה" מבצבץ ──────────
    # שלוש בדיקות שמונעות את החזרה של אותה תקלה בדיוק:
    _th = SYSDIR / "tools" / "thumbnail"
    _calib = _th / "cover-guard-calibration.json"
    try:
        _c = json.loads(_calib.read_text(encoding="utf-8"))
        _ev = _c.get("evidence", {})
        _sep = _ev.get("separation")
        add("סף גלאי-הכתובית בקאבר נמדד", "PASS" if _sep else "FAIL",
            f"‏{_ev.get('projects_with_pairs')} פרויקטים · "
            f"נקי p98={_ev.get('clean_p98')} < צרוב p05={_ev.get('captioned_p05')} · "
            f"חסימת-שווא {_ev.get('false_block_rate')}"
            if _sep else "אין הפרדה בין נקי לצרוב — הסף אינו שמיש")
    except Exception as e:
        add("סף גלאי-הכתובית בקאבר נמדד", "FAIL",
            f"אין כיול מדוד ({e}) — הרץ cover_guard.py --calibrate")

    # שער הכניסה היחיד: אף בונה אחר לא פתוח לקריאה ישירה.
    _open_builders = []
    for _p in (_th / "cover_build.py", _th / "thumbnail_build.py"):
        try:
            _t = _p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if _p.name == "cover_build.py" and "סגור לקריאה ישירה" not in _t:
            _open_builders.append(_p.name)
        if _p.name == "thumbnail_build.py" and "G-COVER2" not in _t:
            _open_builders.append(_p.name)
    add("שער כניסה אחד לקאבר", "FAIL" if _open_builders else "PASS",
        (" | ".join(_open_builders) + " — בונה פתוח שעוקף את G-COVER1/2")
        if _open_builders else "cover_make.py הוא המסלול היחיד; השערים בתוך הבונה")

    # הפייפליין לא מדלג על מותג אישי (שם אבדה המשמעת).
    try:
        _lfp = (SYSDIR / "tools" / "local_finish_pipeline.py").read_text(encoding="utf-8")
        # הבדיקה היא על מה שהפייפליין **קורא לו**, לא על מחרוזת שיכולה לשרוד
        # אחרי התיקון (הגרסה הראשונה של הבדיקה נכשלה בדיוק ככה — היא חיפשה
        # `a.brand != "rel"` שנשאר בשורת בחירת המותג התקינה).
        _uses_entry = "cover_make.py" in _lfp
        _legacy = "frame_select.py" in _lfp or "thumbnail_build.py" in _lfp
        add("קאבר נבנה גם למותג אישי", "PASS" if (_uses_entry and not _legacy) else "FAIL",
            "שני המותגים עוברים ב-cover_make מ-EXPORT הנקי" if _uses_entry and not _legacy
            else ("הפייפליין עדיין קורא לבונה ישן (עוקף את G-COVER1/2)" if _legacy
                  else "הפייפליין לא קורא ל-cover_make.py"))
    except Exception as e:
        add("קאבר נבנה גם למותג אישי", "WARN", str(e))

    # רשומת השערים — הבדיקה ש"לא ייפול בין הכסאות". שער חדש בקוד שאיש לא
    # רשם, או רשומה שממציאה שער שנעלם, נתפסים כאן ולא בסרטון הבא.
    if GR:
        try:
            _ok, _probs = GR.audit()
            _hard = [p for p in _probs if p.startswith("❌")]
            add("gate registry audit", "PASS" if _ok else "FAIL",
                f"{len(GR.GATES)} שערים ברשומה" if _ok
                else " | ".join(_hard[:3]))
        except Exception as e:
            add("gate registry audit", "FAIL", f"האודיט עצמו נכשל: {e}")
    else:
        add("gate registry audit", "FAIL", "gate_registry לא נטען")

    # רשומת הלקחים — "טעויות שחוזרות" (הראל 16.8.26). לקח בלי אוכף חי (סימבול/
    # בדיקה/שער) הוא נוהל, ונוהל נסוג בשקט בהחלפת המנוע הבאה — בדיוק מה שקרה
    # ל-fade-בתפר ול-eof_action. האודיט נכשל לפני שהטעות חוזרת למסך, לא אחרי.
    try:
        import lesson_registry as LSR
        _ok, _probs = LSR.audit()
        add("lesson registry audit", "PASS" if _ok else "FAIL",
            f"{len(LSR.LESSONS)} לקחים, כולם אכופים" if _ok
            else " | ".join(_probs[:3]))
    except Exception as e:
        add("lesson registry audit", "FAIL", f"lesson_registry לא נטען: {e}")

    # גלאי הפנים — L51. שלושה כלים (candidates · broll_vision ·
    # illustration_place) עוטפים את טעינת ה-haarcascade ב-try/except ונופלים
    # בשקט ל"אין פנים". OpenCV 5 הפסיק לארוז את הקבצים, ולכן זה קורה בלי
    # שגיאה ובלי סימן. גלאי שמפסיק לעבוד בשקט גרוע מגלאי שאין.
    try:
        import cv2
        _hc = getattr(getattr(cv2, "data", None), "haarcascades", "") or ""
        _xml = Path(_hc) / "haarcascade_frontalface_default.xml"
        add("face cascade available", "PASS" if _xml.exists() else "WARN",
            f"cv2 {cv2.__version__} · haarcascade קיים" if _xml.exists() else
            f"cv2 {cv2.__version__} — אין haarcascade. זיהוי פנים מושבת בשקט "
            f"ב-candidates/broll_vision/illustration_place; IL8 יעבור למצב "
            f"'לא נמדד'. תיקון: pip install 'opencv-python-headless==4.10.0.84'")
    except Exception as e:
        add("face cascade available", "WARN", f"cv2 לא נטען: {e}")

    # המבקר האחרון לפני הראל — בדיקת חיווט: הקובץ קיים, נטען, ומחובר לצנרת.
    try:
        import preflight_critic as _PFC  # noqa: F401
        _pipe = (HERE / "local_finish_pipeline.py").read_text(encoding="utf-8")
        add("preflight critic wired",
            "PASS" if "preflight_critic.py" in _pipe else "FAIL",
            "רץ בצנרת אחרי qa_gates" if "preflight_critic.py" in _pipe
            else "preflight_critic.py לא נקרא מהצנרת")
    except Exception as e:
        add("preflight critic wired", "FAIL", str(e))

    # v9.29 — שערי הראייה (V7 כתוביות / G-COVER5 קאבר) חוסמים רק מתוך קובץ
    # כיול. קובץ שנמחק = כל הדגלים חוזרים למדווח **בשקט** (עקרון 11) — לכן נבדק.
    try:
        _bad = []
        for _cf in (HERE / "caption-vision-calibration.json",
                    HERE / "thumbnail" / "cover-vision-calibration.json",
                    HERE / "broll-vision-calibration.json"):
            if not _cf.exists():
                _bad.append(f"{_cf.name} חסר")
                continue
            _pp = json.loads(_cf.read_text(encoding="utf-8")).get("params", {})
            if _pp.get("source") != "measured":
                _bad.append(f"{_cf.name}: source={_pp.get('source')}")
        _pipe = (HERE / "local_finish_pipeline.py").read_text(encoding="utf-8")
        if "caption_vision.py" not in _pipe:
            _bad.append("caption_vision לא מחובר לצנרת")
        add("vision gates calibrated", "WARN" if _bad else "PASS",
            " · ".join(_bad) if _bad else
            "V7 כתוביות + G-COVER5 קאבר: ספים נמדדים, דגלים חוסמים, מחובר לצנרת")
    except Exception as e:
        add("vision gates calibrated", "WARN", f"לא נבדק: {e}")

    # v9.30 — קנון הלקחים: כל feedback בזיכרון ממופה לאוכף.
    try:
        import lessons_canon as _LC
        _ok, _pr = _LC.audit()
        _bad = [p for p in _pr if p.startswith("❌")]
        add("lessons canon audit", "PASS" if _ok else "WARN",
            f"{len(_LC.D.C)} קבצי feedback ממופים · 0 בעיות" if _ok else " · ".join(_bad[:3]))
    except Exception as e:
        add("lessons canon audit", "WARN", f"לא נבדק: {e}")

    # v9.30-eff — מנוע התמלול: MLX (Metal) עם נסיגה ל-ct2. נסיגה שקטה = איטי פי ~3
    # בלי שאף אחד יודע (עקרון 11) — לכן זה נבדק כאן ולא רק ב-stderr של align_words.
    _mlx_py = Path.home() / ".rel-mlx" / "bin" / "python"
    _mlx_model = (Path.home() / ".cache" / "huggingface" / "hub" /
                  "models--mlx-community--ivrit-ai-whisper-large-v3-turbo-mlx")
    if os.environ.get("REL_ASR_BACKEND", "mlx") != "mlx":
        add("asr backend", "PASS", f"ct2 (REL_ASR_BACKEND={os.environ.get('REL_ASR_BACKEND')})")
    elif not _mlx_py.exists():
        add("asr backend", "WARN", "~/.rel-mlx חסר — התמלול נופל ל-ct2 (פי ~3 איטי). "
            "התקנה: python3.12 -m venv ~/.rel-mlx && ~/.rel-mlx/bin/pip install mlx-whisper faster-whisper==1.2.1")
    else:
        _r = run([str(_mlx_py), "-c", "import mlx_whisper, faster_whisper.vad"], timeout=60)
        _ok = getattr(_r, "returncode", 1) == 0 if not isinstance(_r, tuple) else _r[0] == 0
        if not _ok:
            add("asr backend", "WARN", "~/.rel-mlx קיים אבל mlx_whisper לא נטען — נסיגה ל-ct2")
        elif not _mlx_model.exists():
            add("asr backend", "WARN", "מודל MLX לא במטמון — הריצה הראשונה תוריד ~1.6GB")
        else:
            add("asr backend", "PASS", "mlx (ivrit-ai turbo על Metal) · נסיגה ל-ct2 בכשל")

    # v9.30-eff — הסקיל המותקן נגזר מהמאסטר (tools/skill_pack.py). dist ישן = הצ'אט הבא
    # טוען הוראות מיושנות (נמדד 22.9.26: המותקן היה v9.22 כשהמאסטר v9.29).
    try:
        import skill_pack as _SP
        import io, contextlib
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _st = _SP.check()
        add("skill pack sync", "PASS" if _st == 0 else "WARN", _buf.getvalue().strip()[:200])
    except Exception as e:
        add("skill pack sync", "WARN", f"לא נבדק: {e}")

    if sys.platform == "darwin":
        try:
            add("review-app python", *_review_app_probe())
        except Exception as e:
            add("review-app python", "WARN", f"לא נבדק: {e}")
    else:
        add("review-app python", "WARN", "לא מק — לא נבדק")

    fails = [c for c in checks if c["status"] == "FAIL"]
    warns = [c for c in checks if c["status"] == "WARN"]
    result = {"ok": not fails, "fails": len(fails), "warns": len(warns),
              "checks": checks}
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        icons = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}
        for c in checks:
            print(f"{icons[c['status']]} {c['check']}: {c['detail']}")
        print(f"\n{'❌' if fails else '✅'} סיכום: {len(fails)} FAIL, {len(warns)} WARN, "
              f"{len(checks) - len(fails) - len(warns)} PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
