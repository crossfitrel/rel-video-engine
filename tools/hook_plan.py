#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hook_plan — שלב "בניית הוק" בעריכה (v9.44, 8.10.26)
=====================================================
הרטרו של 8.10.26: אחוז הצופים שנשארים אחרי 3 שניות (VR) מנבא את החשיפה (r=0.83/0.94).
מחקר הגיליונות באותו יום (48 ריילס): פעולה/סצנה אמיתית בפריים 0 = VR חציוני 42.6%,
מדבר-למצלמה בלי פעולה = 30.3% (p=0.00006). ההוק הוא ההחלטה הכי יקרה בריל — ולכן
הבמאי **מצהיר** עליו לפני שהראל רואה, והמבקר-קדם (P22) בודק את ההצהרה ואת מה שנמדד.

  init   — טיוטה: המילים של 0-2ש, הטכניקות המומלצות לסוג התוכן (tools/hook_toolbox.json),
           ודגלים שכבר נראים (פרק X, פנייה גאוגרפית, פתיח קבוע). כותב HOOK_PLAN.draft.json.
  sheet  — HOOK_SHEET.jpg: 6 פריימים 0/0.5/1/1.5/2/2.9ש מהקובץ — נפתח ב-Read (חוק הראייה).
  stamp  — אחרי ה-Read: קושר את ההצהרה לקובץ (גודל+mtime) ולגיליון. קלט שהשתנה מבטל אותה.
  check  — הממצאים (אותם ממצאים ש-preflight_critic מכניס כ-P22_hook_anchor).

HOOK_PLAN.json (הבמאי כותב, מתוך ⟦HOOK⟧ של התסריט כשיש):
  {"version":1, "technique":"<מזהה מהארגז>", "anchor_type":"<scene|action|object|...>",
   "t0":"מה רואים בשנייה 0", "t1":"...", "t2":"...", "first_sentence":"...",
   "amplifier":null|"spotlight"|"kinetic_title"|"telestrator_freeze"|"punch_in"|"stat"|"sfx",
   "source":"⟦HOOK⟧ v2"|"inferred", "sheet":"HOOK_SHEET.jpg", "media":{file,size,mtime}}

שימוש (על המק):
  ~/.rel-whisper/bin/python tools/hook_plan.py init  --workdir W
  ~/.rel-whisper/bin/python tools/hook_plan.py sheet --workdir W [--video W/FINAL.mp4]
  ~/.rel-whisper/bin/python tools/hook_plan.py stamp --workdir W [--video FINAL.mp4]
  ~/.rel-whisper/bin/python tools/hook_plan.py check --workdir W
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLBOX = HERE / "hook_toolbox.json"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
HIGH, MED, LOW = "high", "medium", "low"
CHECK = "P22_hook_anchor"
# הפרויקטים שנפתחו לפני שהשלב נולד — חוסר הצהרה מדווח (medium) ולא חוסם
ENFORCE_FROM = "2026-10-08T18:00:00"
OPEN_WIN = 2.0
BLACK_YAVG = 16.0           # פיזיקלי: פריים שחור/כמעט שחור (טווח luma מוגבל 16-235)
GEO_RE = re.compile(r"^(תושבי|אריאלניקים|אריאלניקיות|ברוכים|סטודנטים|סטודנטיות)$")
EPISODE_RE = re.compile(r"^(פרק|אפיזודה)$")
FULL_GFX = {"forearm", "end_card", "tripod", "outro", "section"}


def jload(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def toolbox() -> dict:
    return jload(TOOLBOX, {}) or {}


def load_words(W: Path) -> list[dict]:
    for n in ("words_final.json", "whisper_export_tight.json", "words.json"):
        d = jload(W / n)
        if d is not None:
            return d if isinstance(d, list) else (d.get("words") or [])
    return []


def manifest(W: Path) -> dict:
    return jload(W / "project_manifest.json", {}) or {}


def intro_offset(W: Path) -> float:
    prov = jload(W / "FINAL_PROVENANCE.json", {}) or {}
    for k in ("intro_offset_sec",):
        if prov.get(k):
            return float(prov[k])
    ex = prov.get("extra") or {}
    return float(ex.get("intro_offset_sec") or 0.0)


def opening_words(W: Path, win: float = OPEN_WIN) -> list[str]:
    """המילים שנשמעות ב-[0, win] של ה-FINAL (ציר הגוף + היסט הפתיח הקבוע)."""
    off = intro_offset(W)
    out = []
    for w in load_words(W):
        s = float(w.get("start", 1e9)) + off
        if s <= win:
            out.append(re.sub(r"[^\w֐-׿]", "", str(w.get("word") or w.get("text") or "")))
    return [x for x in out if x]


def is_paid(W: Path) -> bool:
    m = manifest(W)
    hay = " ".join(str(m.get(k) or "") for k in ("name", "content_type", "topic")) + " " + W.name
    return bool(m.get("paid")) or "ממומן" in hay


def media_stamp(W: Path, name: str) -> dict:
    f = W / name
    if not f.exists():
        return {}
    st = f.stat()
    return {"file": name, "size": st.st_size, "mtime": int(st.st_mtime)}


def first_frame_yavg(video: Path) -> float | None:
    if not video or not Path(video).exists():
        return None
    r = subprocess.run([FFMPEG, "-nostdin", "-hide_banner", "-i", str(video), "-frames:v", "1",
                        "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=60)
    m = re.findall(r"YAVG=([\d.]+)", r.stderr or "")
    return float(m[0]) if m else None


def row_for(W: Path) -> str:
    """שורת הארגז לפרויקט: manifest.hook_row גובר; אחרת מחלקה + content_type + מילות שם."""
    m = manifest(W)
    if m.get("hook_row"):
        return str(m["hook_row"])
    dept, ct = str(m.get("dept") or ""), str(m.get("content_type") or "")
    name = f"{m.get('name') or ''} {W.name} {m.get('topic') or ''}"
    has = lambda *ks: any(k in name for k in ks)
    if has("פודקאסט", "מדברים-כושר", "מדברים כושר", "פרק-") or "podcast" in name.lower():
        return "פודקאסט"
    if "Throwdown" in dept:
        return "Throwdown"
    if "הראל חיון" in dept:
        return "אישי-מערכת שבניתי" if has("אפליקצי", "פרומפט", "מערכת", "בניתי", "קלוד") else "אישי-עיקרון"
    if ct == "conversion" or has("ממומן", "המרה"):
        return "המרה"
    if has("טיפ", "טעויות", "טכניקה"):
        return "טיפ טכני"
    if "שיקום" in dept or has("מאסל", "אנטומ", "מיתוס"):
        return "שיקום/אנטומיה"
    if has("סיפור", "מתאמן", "חזרה", "הכירו"):
        return "סיפור מתאמן"
    if has("הומור", "צוות", "ישיבת", "קהילה"):
        return "קהילה/הומור"
    return "בריאות לחיים"


def suggest(W: Path) -> dict:
    tb = toolbox()
    rows = tb.get("content_types", {})
    key = row_for(W)
    return {"content_type": manifest(W).get("content_type"), "row": key,
            "techniques": (rows.get(key) or {}).get("techniques") or list(tb.get("techniques", {}))[:4],
            "note": (rows.get(key) or {}).get("note"),
            "edit_recipes": (rows.get(key) or {}).get("edit_recipes") or []}


# ─────────────────────────── הממצאים (P22) ───────────────────────────

def evaluate(W: Path, measure_video: bool = True, target: str | None = None) -> list[dict]:
    """ממצאי P22. כל ממצא: {check, severity, detail, fix}. לא חוסם בעצמו — preflight קובע ready_for_harel.

    target (v10.1, 23.10.26): הקובץ שנבדק — FINAL.mp4 (ברירת מחדל) או FINAL_PENDING.mp4.
    עד התיקון ההשוואה הייתה תמיד מול FINAL.mp4, ולכן preflight --target FINAL_PENDING.mp4
    אישר הצהרת הוק שנקשרה ל-FINAL הישן (גרסה אחרת) — מעבר שקרי."""
    W = Path(W)
    target = Path(target).name if target else "FINAL.mp4"
    tb = toolbox()
    f: list[dict] = []
    F = lambda sev, d, fix: f.append({"check": CHECK, "severity": sev, "detail": d, "fix": fix})
    m = manifest(W)
    hp = jload(W / "HOOK_PLAN.json")
    legacy = str(m.get("created_at") or "9999") < ENFORCE_FROM
    if not hp:
        F(MED if legacy else HIGH,
          "אין HOOK_PLAN.json — הבמאי לא הצהיר מה רואים ושומעים ב-0-2ש ואיזה עוגן מוחשי פותח"
          + (" (פרויקט שנפתח לפני v9.44)" if legacy else ""),
          "hook_plan.py init → לבחור טכניקה מהארגז → sheet → Read → לכתוב HOOK_PLAN.json → stamp")
    else:
        tech, anc = hp.get("technique"), hp.get("anchor_type")
        if tech not in (tb.get("techniques") or {}):
            F(MED, f"טכניקה «{tech}» לא בארגז (tools/hook_toolbox.json)", "לבחור מזהה מהארגז או להוסיף טכניקה עם ראיה")
        if anc not in (tb.get("anchor_types") or {}) or not str(hp.get("t0") or "").strip():
            F(HIGH, f"אין עוגן מוחשי מוצהר בשנייה 0 (anchor_type={anc!r}, t0 ריק={not hp.get('t0')})",
              "לבחור פריים פתיחה שהוא סצנה/פעולה/חפץ/אדם/מספר — או לצלם (shot_debt)")
        fin = target if (W / target).exists() else None
        if not hp.get("sheet") or not (W / str(hp.get("sheet"))).exists():
            F(MED, "ההצהרה לא נבדקה על גיליון (HOOK_SHEET.jpg חסר)", "hook_plan.py sheet → Read → stamp")
        elif fin and hp.get("media") and media_stamp(W, fin) != hp.get("media"):
            F(MED, "ה-FINAL השתנה אחרי שההוק נבדק — ההצהרה מתייחסת לגרסה אחרת", "sheet → Read → stamp מחדש")
    if hp:
        for x in evaluate_edit(W, hp, tb, legacy):
            F(*x)
    ow = opening_words(W)
    for i, w in enumerate(ow):
        # "פרק" לבד הוא גם אנטומיה ("פרק כף היד") — רק כשאחריו מספר/סידורי
        nxt = ow[i + 1] if i + 1 < len(ow) else ""
        if EPISODE_RE.match(w) and re.match(r"^(\d+|ראשון|שני|שלישי|רביעי|חמישי|מיוחד)$", nxt):
            F(HIGH, f"'{w}' נשמע ב-2 השניות הראשונות — כרטיס/הכרזת פרק (VR 17.3% פעמיים)",
              "לפתוח ברגע החזק מהפרק; מספר הפרק עובר לקפשן")
            break
    if not is_paid(W):
        geo = [w for w in ow[:4] if GEO_RE.match(w)]
        if geo:
            F(MED, f"פנייה גאוגרפית/ברכה ב-2 השניות הראשונות בריל אורגני («{' '.join(ow[:4])}») — VR חציוני 24%",
              "הגאוגרפיה למשפט השני; לפתוח בבעיה התפקודית המצולמת (hook-writer 0.3)")
    off = intro_offset(W)
    if off > 0.5:
        F(MED, f"פתיח קבוע של {off:.1f}ש לפני ההוק — מאסל מן עם פתיח 30.8-36.8% מול 53.3% בלי",
          "ניסוי E14: הוק קודם, תגית 'מאסל מן' (MG tag) אחרי המשפט הראשון, בלי הפתיח הארוך (--no-full-intro)")
    mp = jload(W / "motion_plan.json", {}) or {}
    if not mp.get("backdrop"):
        early = [e for e in mp.get("events", []) if e.get("type") in FULL_GFX and float(e.get("start", 9)) < 1.5]
        if early:
            F(HIGH, f"מסך גרפי מלא לפני העוגן ({early[0].get('type')} @ {float(early[0]['start']):.1f}ש) — כרטיס כותרת",
              "להזיז אחרי 2ש או להחליף במגבר מעל העוגן (spotlight/kinetic_title)")
    if measure_video and (W / target).exists():
        y = first_frame_yavg(W / target)
        if y is not None and y < BLACK_YAVG:
            F(HIGH, f"הפריים הראשון שחור (YAVG {y:.1f})", "הפריים הראשון = העוגן; לחתוך את השחור")
    return f


def evaluate_edit(W: Path, hp: dict, tb: dict, legacy: bool) -> list[tuple]:
    """v9.46 — ארגז העריכה של ההוק (tools/hook_fx.py). ממצאים כ-(severity, detail, fix).

    - אין בלוק edit בכלל = MED: הבמאי לא החליט (גם 'none' עם why היא החלטה טובה).
    - יש moves/sfx בלי HOOK_FX_REPORT תקין, או שהדוח לתוכנית אחרת (edit_digest) = HIGH: התוכנית לא בתוצר.
    - דוח תקין בלי HOOK_FX_SHEET.jpg = MED (חוק הראייה)."""
    out = []
    ed = hp.get("edit")
    if ed is None:
        if not legacy:
            rec = ", ".join(((tb.get("content_types") or {}).get(row_for(W)) or {}).get("edit_recipes") or [])
            out.append((MED, "HOOK_PLAN בלי בלוק edit — לא הוחלט על שכבת עריכה להוק (תנועה/מעבר/צליל)",
                        f"לבחור מתכון מ-edit_recipes ({rec or 'hook_toolbox.json'}) או edit:{{recipe:'none', why}}"))
        return out
    if str(ed.get("recipe") or "") == "none" or not (ed.get("moves") or ed.get("sfx") or ed.get("music_drop")):
        if not str(ed.get("why") or "").strip() and str(ed.get("recipe") or "") == "none":
            out.append((LOW, "edit:none בלי why", "משפט אחד: למה אין רגע ברמה גבוהה לשכבת העריכה"))
        return out
    vj = jload(Path(__file__).resolve().parent / "hook_fx_verdicts.json", {}) or {}
    for vd in vj.get("verdicts") or []:
        if vd.get("verdict") == "reject" and vd.get("recipe") == ed.get("recipe") and vd.get("project") in (
                W.name, str(manifest(W).get("e2e_copy_of") or "")):
            out.append((HIGH, f"הראל פסל את «{ed.get('recipe')}» בסרטון הזה ({vd.get('date')}): «{vd.get('quote')}»",
                        "מתכון אחר מהשורה, או edit:{recipe:'none', why}"))
    if ed.get("recipe") not in (tb.get("edit_recipes") or {}):
        out.append((MED, f"מתכון עריכה «{ed.get('recipe')}» לא בארגז", "לבחור מ-edit_recipes או להוסיף מתכון עם ראיה"))
    rep = jload(W / "HOOK_FX_REPORT.json")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import hook_fx as HF
        dg = HF.edit_digest(ed)
    except Exception as e:                                   # גלאי שנופל בשקט גרוע מגלאי שאין
        out.append((MED, f"edit_digest לא נמדד: {e}", "להריץ hook_fx.py check"))
        return out
    if not rep or not rep.get("ok"):
        bad = [g.get("gate") for g in (rep or {}).get("gates", []) if g.get("level") == "blocking" and not g.get("ok")]
        out.append((HIGH, "תוכנית עריכת הוק מוצהרת אבל לא הוחלה בתוצר"
                    + (f" (שערים: {', '.join(bad)})" if bad else " (אין HOOK_FX_REPORT.json תקין)"),
                    "גימור עם --hook-fx on (או לתקן את התוכנית לפי השער) → Read על HOOK_FX_SHEET.jpg"))
    elif dg not in (rep.get("edit_digest"), rep.get("orig_edit_digest")):
        out.append((HIGH, "HOOK_FX_REPORT שייך לתוכנית עריכה אחרת (edit_digest לא תואם)",
                    "גימור מחדש — התוכנית השתנתה אחרי הרינדור"))
    elif not (W / str(rep.get("sheet") or "HOOK_FX_SHEET.jpg")).exists():
        out.append((MED, "שכבת העריכה הוחלה בלי גיליון לפני/אחרי", "hook_fx.py sheet → Read"))
    return out


# ─────────────────────────── פקודות ───────────────────────────

def cmd_init(W: Path) -> dict:
    sg = suggest(W)
    tb = toolbox()
    d = {"version": 1, "technique": None, "anchor_type": None, "t0": "", "t1": "", "t2": "",
         "first_sentence": " ".join(opening_words(W, 3.0)), "amplifier": None,
         "source": "inferred", "suggested": sg["techniques"],
         "suggested_row": sg["row"], "flags": [x["detail"] for x in evaluate(W, measure_video=False)
                                               if "HOOK_PLAN" not in x["detail"]],
         "rule": tb.get("selection_rule"),
         "edit": {"recipe": None, "suggested_recipes": sg.get("edit_recipes") or [], "moves": [], "sfx": [],
                  "music_drop": [], "why": "", "rules": tb.get("edit_rules")}}
    (W / "HOOK_PLAN.draft.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def cmd_sheet(W: Path, video: Path | None) -> Path:
    from PIL import Image, ImageDraw
    video = video or next((W / n for n in ("FINAL.mp4", "EXPORT+MG.mp4", "EXPORT_TIGHT.mp4") if (W / n).exists()), None)
    if not video:
        raise SystemExit("אין וידאו לגיליון")
    ts = (0.0, 0.5, 1.0, 1.5, 2.0, 2.9)
    tiles = []
    with tempfile.TemporaryDirectory() as td:
        for t in ts:
            p = Path(td) / f"{t}.png"
            subprocess.run([FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t}", "-i", str(video),
                            "-frames:v", "1", "-vf", "scale=360:640", str(p)])
            tiles.append(Image.open(p).convert("RGB").copy() if p.exists() else Image.new("RGB", (360, 640)))
    sheet = Image.new("RGB", (360 * len(tiles), 640), "black")
    dr = ImageDraw.Draw(sheet)
    for i, im in enumerate(tiles):
        sheet.paste(im, (i * 360, 0))
        dr.rectangle([i * 360, 0, i * 360 + 64, 30], fill="black")
        dr.text((i * 360 + 6, 8), f"{ts[i]:.1f}s", fill="yellow")
    out = W / "HOOK_SHEET.jpg"
    sheet.save(out, quality=85)
    return out


def cmd_stamp(W: Path, video: str) -> dict:
    hp = jload(W / "HOOK_PLAN.json")
    if not hp:
        raise SystemExit("אין HOOK_PLAN.json לקשור")
    if not (W / "HOOK_SHEET.jpg").exists():
        raise SystemExit("אין HOOK_SHEET.jpg — sheet ואז Read קודם")
    hp["sheet"] = "HOOK_SHEET.jpg"
    hp["media"] = media_stamp(W, video)
    hp["stamped_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (W / "HOOK_PLAN.json").write_text(json.dumps(hp, ensure_ascii=False, indent=1), encoding="utf-8")
    return hp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "sheet", "stamp", "check"])
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--video", default=None)
    a = ap.parse_args()
    W = Path(a.workdir).expanduser()
    if a.cmd == "init":
        d = cmd_init(W)
        print(f"HOOK_PLAN.draft.json · שורת ארגז: {d['suggested_row']} · מומלץ: {', '.join(d['suggested'] or [])}")
        print(f"0-3ש: «{d['first_sentence'][:80]}»")
        print(f"מתכוני עריכה: {', '.join(d['edit']['suggested_recipes']) or '—'} (hook_toolbox.json edit_recipes)")
        for x in d["flags"]:
            print(f"  ⚠ {x[:140]}")
    elif a.cmd == "sheet":
        print(cmd_sheet(W, Path(a.video) if a.video else None))
    elif a.cmd == "stamp":
        hp = cmd_stamp(W, a.video or "FINAL.mp4")
        print(f"נקשר ל-{hp['media']}")
    else:
        fs = evaluate(W, target=a.video)
        if not fs:
            print("✅ P22 נקי — עוגן מוצהר, נבדק על הגיליון, אין פתיחה אסורה")
        for x in fs:
            print(f"[{x['severity']}] {x['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
