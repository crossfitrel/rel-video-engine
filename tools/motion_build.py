#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
motion_build — שכבת Motion Graphics של מערכת העריכה (v9.37, 4.10.26)
=====================================================================
הראל, 4.10.26: "צריך לבוא לידי ביטוי בכל סרטון שבו יש קטעים שאפשר לשלב את זה ...
ובתנאי שזה יהיה באמת ברמה מאוד גבוהה."  סקיל: rel-motion-graphics · עיצוב: tools/motion/MOTION.md

החלוקה (כמו illustration_gate/illustration_build — החלטה קודם, ציור אחר כך):
  • `propose`   — מועמדים דטרמיניסטיים מהתמליל (הוק, מספרים, אנטומיה, מנייה, CTA, אנשים).
                  זה **לא** ההחלטה — Claude (הבמאי) אוצר אותם ל-W/motion_plan.json.
  • `check`     — לפני רינדור: MG0 סכמה · MG4 נאמנות טקסט (חוסם) · MG3 מינון · MG7 זמן קריאה (מדווחים).
  • `snap`      — PNG בזמנים נבחרים + הרכבה על פריימי הבסיס (`--base`) → MG_SNAPS.jpg ללולאת הביקורת.
  • `all`       — check → הכרעת אזורי 'auto' לפי פנים → קומפוזיציה → מדידה ב-5 זמנים לאירוע
                  (MG1 אזור בטוח · MG5 פונטים · MG6 שגיאות דף · MG2 פנים — חוסמים) → פריימים עם אלפא →
                  ProRes 4444 `MG_LAYER.mov` → **overlay יחיד** + זנב + SFX → MG8 אורך → MG_SHEET.jpg.

תוכנית (W/motion_plan.json):
  {"version":1, "duration": <אורך הבסיס>, "tail": 0, "opaque": false,
   "facts":[{"text":"נבו ינאי","source":"monday:<id>:אחראי"}],
   "events":[{"id":"hook","type":"kinetic_title","start":0,"end":1.8,"text":"...","zone":"auto",
              "suppress_captions":true, "sfx":[{"at":0.02,"kind":"whoosh"}]}, ...]}

שימוש (על המק):
  ~/.rel-whisper/bin/python tools/motion_build.py propose --workdir W
  ~/.rel-whisper/bin/python tools/motion_build.py check   --workdir W
  ~/.rel-whisper/bin/python tools/motion_build.py snap    --workdir W --base W/EXPORT_TIGHT.mp4 --at 1.2,7.5
  ~/.rel-whisper/bin/python tools/motion_build.py all     --workdir W --base <בסיס> --out W/EXPORT+MG.mp4
  בגימור: local_finish_pipeline.py ... --motion auto|on|off (ברירת מחדל auto = רץ כשיש motion_plan.json)
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOT = HERE / "motion"
PROJECT = HERE.parent
BRAND = PROJECT / "brand-assets"
LOGO = HERE / "thumbnail" / "brand" / "logo_rel.png"
LOGO_WHITE = HERE / "thumbnail" / "brand" / "logo_white.png"   # צללית בלבד — מסכה לברק, לא לוגו (L110)
NODE = shutil.which("node") or "/opt/homebrew/bin/node"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

FONTS = [("Assistant", 800, "Assistant-ExtraBold.ttf"), ("Ploni", 900, "PloniBlack.otf"),
         ("Ploni", 800, "PloniUBold.otf"), ("Ploni", 700, "PloniBold.otf"),
         ("Ploni", 600, "PloniDBold.otf"), ("Ploni", 500, "PloniMedium.otf"),
         ("Ploni", 400, "PloniRegular.otf")]
FW, FH = 1080, 1920
# MG1 — אזור בטוח לטקסט. למעלה: UI של אינסטגרם/טיקטוק (Meta 14% = 269px) עם סובלנות.
# למטה: רצועת הכתוביות של הקאנון (0.66H = 1267px, illustration_place.CAPTION_BAND).
SAFE = {"x0": 56, "x1": 1024, "y0": 258, "y1": 1256}
FULL_TYPES = {"forearm", "end_card", "tripod", "outro"}
OVERLAY_TYPES = {"kinetic_title", "chips", "name_reveal", "name_sparkle", "compare", "list_stack", "quote",
                 "poll", "stat", "callout", "angle", "section",
                 # v9.38 — סיפור/תחרות · אימון/טכניקה · הסבר/וויס-אובר (templates/story|coach|explainer.js)
                 "letterbox", "punch", "athlete_card", "podium", "timeline", "quote_card",
                 "tag", "telestrator", "bubbles", "day_split", "alerts", "clock", "crowd",
                 # v9.44 — מגברי הוק (templates/hook.js, tools/hook_toolbox.json)
                 "spotlight", "then_now"}
# מיקום מפורש בתבנית (קואורדינטות/פינה/פסים) — 'auto' לא מוכרע לפי פנים; MG2 עדיין בודק טקסט מול פנים
FIXED_POS_TYPES = {"letterbox", "tag", "telestrator", "spotlight", "then_now"}
# then_now: שני פאנלים 1080×953 (עליון 0, תחתון 967) — כל פאנל מציג פריים קפוא אחר (L124)
THEN_NOW_PANELS = (("a", 0.0), ("b", 967.0))
THEN_NOW_H = 953.0
TYPES = FULL_TYPES | OVERLAY_TYPES
TEXT_KEYS = ("text", "name", "role", "title", "sub", "a", "b", "question", "label", "kicker",
             "promise", "state_a", "state_b", "label_radius", "label_ulna", "stat_unit", "unit",
             "by", "word", "wrong_label", "tri_label", "label_a", "label_b", "value_a", "value_b")
LIST_TEXT_KEYS = ("items", "options", "marks", "labels", "places")     # רשימות של {text} או מחרוזות
DICT_TEXT_KEYS = ("comment", "winner", "chip")                         # {text, at}
NUM_KEYS = ("value", "stat_value", "to_deg")
SFX_KINDS = ("whoosh", "pop", "tick", "hit", "sparkle")   # sparkle = חתימת שם מתאמן (name_sparkle, 8.10.26)
SFX_DB = {"whoosh": -29.5, "pop": -27.5, "tick": -31.0, "hit": -26.5, "sparkle": -26.0}   # v9.39: ‎-2.5dB (הראל: "קצת עמוס בצלילים")
SFX_VARIANTS = {"whoosh": 3, "pop": 3, "tick": 2, "hit": 2}   # מתחלפים לפי סדר — לא אותו צליל שוב ושוב
SFX_MIN_GAP = 0.9        # שני צלילים במרחק קטן מזה ⇒ נשאר אחד (hit גובר)
SFX_REPEAT_WIN, SFX_REPEAT_DB = 3.0, -4.0   # אותו סוג שוב תוך 3ש ⇒ שקט יותר
SFX_CAP_WIN, SFX_CAP_N = 4.0, 2             # לכל היותר 2 צלילים בכל 4ש (העדיפות: hit > whoosh > pop > tick)
SFX_PRIO = {"sparkle": 3, "hit": 3, "whoosh": 2, "pop": 1, "tick": 0}
SFX_WINS = {"hit", "sparkle"}   # צליל חתימה — גובר על צליל קרוב אחר
TEAM_ROLE_WORDS = ("מאמן", "מאמנת", "מנהל", "מנהלת", "בעלים", "צוות", "מטפל", "מטפלת", "נציג", "נציגה")
AUTO_SFX = {"name_sparkle": ("sparkle", 0.0)}   # הקליק על הפלאש, הפעמונים על הקפיצה של השם   # תבנית עם צליל קבוע — נוסף אוטומטית אם לא הוגדר
CPS_MAX = 17.0          # Netflix Hebrew Timed Text: ≤17 תווים לשנייה
HEAD_PAD = 0.035        # = illustration_place.HEAD_PAD
TOP_ZONE_FREE_Y = 760   # 'auto' → top רק אם כל הפנים מתחילות מתחת לקו הזה (300-700 פנוי לטקסט)

# ─────────────────────────── עזר ───────────────────────────

def sh(cmd, timeout=3600):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)


def ffdur(p) -> float:
    r = sh([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


NIQQUD = re.compile(r"[֑-ׇ]")
PUNCT = re.compile(r"[\"'״׳?!.,:;()\[\]{}…–—\-־/\\]")
PREFIX = "והבכלמש"


def toks(s: str) -> list[str]:
    s = NIQQUD.sub("", str(s))
    s = PUNCT.sub(" ", s)
    return [t for t in s.split() if t]


def _stems(t: str) -> set[str]:
    out, s = {t}, t
    for _ in range(2):           # עד שתי תחיליות: "והאולנה" → "האולנה" → "אולנה"
        if len(s) > 2 and s[0] in PREFIX:
            s = s[1:]
            out.add(s)
    return out


def tok_match(t: str, pool: set[str]) -> bool:
    if t in pool:
        return True
    st = _stems(t)
    return any(st & _stems(p) for p in pool)


def load_words(W: Path) -> list[dict]:
    for n in ("words_final.json", "whisper_export_tight.json", "words.json"):
        p = W / n
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            return d if isinstance(d, list) else (d.get("words") or [])
    return []


def plan_texts(ev: dict) -> list[str]:
    out = [ev[k] for k in TEXT_KEYS if isinstance(ev.get(k), str) and ev[k].strip()]
    for lk in LIST_TEXT_KEYS:
        for it in ev.get(lk) or []:
            if isinstance(it, dict) and it.get("text"):
                out.append(it["text"])
            elif isinstance(it, str) and it.strip():
                out.append(it)
    for dk in DICT_TEXT_KEYS:
        if isinstance(ev.get(dk), dict) and ev[dk].get("text"):
            out.append(ev[dk]["text"])
    return out


def plan_numbers(ev: dict) -> list[str]:
    out = []
    for k in NUM_KEYS:
        if ev.get(k) is not None:
            v = float(ev[k])
            out.append(str(int(v)) if v.is_integer() else str(v))
    return out


def load_plan(W: Path, path: str | None = None) -> dict:
    p = Path(path) if path else W / "motion_plan.json"
    plan = json.loads(p.read_text(encoding="utf-8"))
    plan.setdefault("tail", 0.0)
    plan.setdefault("facts", [])
    plan.setdefault("events", [])
    plan["_path"] = str(p)
    return plan


def gate(name, ok, level, detail, **extra):
    return {"gate": name, "ok": bool(ok), "level": level, "detail": detail, **extra}

# ─────────────────────────── שערים לפני רינדור ───────────────────────────

def gate_schema(plan: dict) -> dict:
    probs, ids = [], set()
    D = float(plan.get("duration") or 0) + float(plan.get("tail") or 0)
    if D <= 0:
        probs.append("duration חסר")
    for ev in plan["events"]:
        i = ev.get("id")
        if not i or i in ids:
            probs.append(f"id חסר/כפול: {i}")
        ids.add(i)
        if ev.get("type") not in TYPES:
            probs.append(f"{i}: תבנית לא מוכרת {ev.get('type')}")
        s, e = float(ev.get("start", -1)), float(ev.get("end", -1))
        if not (0 <= s < e <= D + 1e-3):
            probs.append(f"{i}: חלון לא חוקי {s}-{e} (אורך {D:.2f})")
        for x in ev.get("sfx") or []:
            if x.get("kind") not in SFX_KINDS:
                probs.append(f"{i}: sfx לא מוכר {x.get('kind')}")
    bw = plan.get("base_windows") or []
    if bw and plan.get("opaque"):
        probs.append("base_windows עם opaque:true — השכבה חייבת אלפא כדי שהצילום ייראה בחלונות")
    for w in bw:
        if not (isinstance(w, (list, tuple)) and len(w) == 2 and 0 <= float(w[0]) < float(w[1]) <= D + 1e-3):
            probs.append(f"base_window לא חוקי {w}")
    return gate("MG0_schema", not probs, "blocking", "; ".join(probs) or f"{len(plan['events'])} אירועים תקינים")


def gate_text_fidelity(plan: dict, words: list[dict]) -> dict:
    """MG4 — 'אין המצאות': כל מילה על המסך באה מהתמליל או מ-facts עם מקור.
    מספר חייב להופיע כספרות בתמליל או ב-facts — לא 'בערך'."""
    tr = {t for w in words for t in toks(w.get("word") or w.get("text") or "")}
    facts_ok = [f for f in plan["facts"] if f.get("text") and f.get("source")]
    facts_bad = [f for f in plan["facts"] if not f.get("source")]
    pool = tr | {t for f in facts_ok for t in toks(f["text"])}
    miss = []
    for ev in plan["events"]:
        for s in plan_texts(ev):
            bad = [t for t in toks(s) if not tok_match(t, pool)]
            if bad:
                miss.append(f"{ev['id']}: «{s}» ← {' '.join(bad)}")
        for n in plan_numbers(ev):
            if n not in pool:
                miss.append(f"{ev['id']}: מספר {n} לא בתמליל ולא ב-facts")
    if facts_bad:
        miss.append(f"facts בלי source: {[f.get('text') for f in facts_bad]}")
    return gate("MG4_text_fidelity", not miss, "blocking",
                "; ".join(miss) or "כל הטקסטים מהתמליל/facts", missing=miss)


def gate_dosage(plan: dict) -> dict:
    """MG3 — מינון. **מדווח בלבד**: אין עדיין סרטוני MG מאושרים למדוד מהם סף
    ("אין שער חוסם עם סף לא-מדוד"). הספים כאן — נקודת פתיחה, מכוילים מפסיקות הראל."""
    D = float(plan["duration"])
    evs = [e for e in plan["events"] if e["start"] < D]
    iv = sorted([max(0.0, e["start"]), min(D, e["end"])] for e in evs)
    merged: list[list[float]] = []
    for s0, e0 in iv:
        if merged and s0 <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e0)
        else:
            merged.append([s0, e0])
    cover = sum(e0 - s0 for s0, e0 in merged) / max(D, 1e-6)       # איחוד חלונות, בלי הזנב
    gaps = [b[0] - a[1] for a, b in zip(merged, merged[1:])]        # חפיפה מכוונת אינה "צפיפות"
    tight = [round(g, 2) for g in gaps if g < 0.6]
    per_min = len(evs) / max(D / 60, 1e-6)
    warn = cover > 0.65 or per_min > 12 or bool(tight)
    return gate("MG3_dosage", not warn, "reporting",
                f"{len(evs)} רגעים · כיסוי {cover:.0%} · {per_min:.1f}/דקה"
                + (f" · מרווחים צפופים {tight}" if tight else ""),
                coverage=round(cover, 3), per_min=round(per_min, 1), calibrated=False)


def gate_reading(plan: dict) -> dict:
    """MG7 — זמן קריאה (≤17 תווים/שנייה בעברית). מדווח."""
    bad = []
    for ev in plan["events"]:
        chars = sum(len(s.replace(" ", "")) for s in plan_texts(ev))
        d = ev["end"] - ev["start"]
        if chars and chars / max(d, 1e-6) > CPS_MAX:
            bad.append(f"{ev['id']}: {chars} תווים ב-{d:.1f}ש = {chars / d:.0f}/ש")
    return gate("MG7_reading_time", not bad, "reporting", "; ".join(bad) or "כל האירועים קריאים")


def gate_sfx(plan: dict) -> dict:
    """MG9 — מינון צלילים (מדווח). הראל 4.10.26: "קצת עמוס מידיי בצלילים — לגוון או למתן".
    plan_sfx כבר אוכף מרווח 0.9ש + וריאציות + ‎-4dB לחזרה; כאן רק מדווחים כמה תוכנן וכמה נשאר."""
    raw = sum(len(_ev_sfx(ev)) for ev in plan["events"])
    kept, dropped = plan_sfx(plan)
    D = float(plan["duration"]) + float(plan.get("tail") or 0)
    per10 = len(kept) / max(D / 10, 1e-6)
    return gate("MG9_sfx_density", per10 <= 2.5, "reporting",
                f"{len(kept)}/{raw} צלילים · {per10:.1f} ל-10ש" + (f" · הוסרו {dropped}" if dropped else ""),
                per10=round(per10, 2), calibrated=False)


def gate_base_share(plan: dict) -> dict:
    """MG10 — בסרטון MG מלא (backdrop): כמה מהזמן הראל במצלמה. הראל 4.10.26: "העיקר אנימציות ו-20% זה אני". מדווח."""
    if not plan.get("backdrop"):
        return gate("MG10_base_share", True, "reporting", "לא סרטון MG מלא")
    D = float(plan["duration"])
    share = sum(float(e) - float(s) for s, e in plan.get("base_windows") or []) / max(D, 1e-6)
    return gate("MG10_base_share", 0.12 <= share <= 0.30, "reporting",
                f"הראל במצלמה {share:.0%} מהזמן (יעד ~20%)", share=round(share, 3))


def check(W: Path, plan: dict) -> list[dict]:
    return [gate_schema(plan), gate_text_fidelity(plan, load_words(W)), gate_dosage(plan), gate_reading(plan),
            gate_sfx(plan), gate_base_share(plan)]

# ─────────────────────────── פנים ───────────────────────────

def haar_at(video, t: float):
    """פנים סביב זמן t (3 פריימים, אשכול מתמיד של illustration_place). (None, 'unavailable:…') = לא נמדד."""
    try:
        import cv2
        sys.path.insert(0, str(HERE))
        import illustration_place as ip
    except Exception as e:      # noqa: BLE001
        return None, f"unavailable:{type(e).__name__}"
    hc = getattr(getattr(cv2, "data", None), "haarcascades", "") or ""
    xml = Path(hc) / "haarcascade_frontalface_default.xml"
    if not xml.exists():
        return None, "unavailable:no-cascade"
    casc = cv2.CascadeClassifier(str(xml))
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return None, "unavailable:no-video"
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    per = []
    for dt in (-0.2, 0.0, 0.2):
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int((t + dt) * fps)))
        ok, fr = cap.read()
        if not ok or fr is None:
            continue
        h, w = fr.shape[:2]
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        per.append([[x / w, y / h, (x + fw) / w, (y + fh) / h]
                    for (x, y, fw, fh) in casc.detectMultiScale(g, 1.15, 5, minSize=(60, 60))])
    cap.release()
    return _clean_faces(per), f"haar:{sum(len(p) for p in per)}"


def _clean_faces(per: list[list[list[float]]]) -> list[list[float]]:
    """Haar מחזיר גם "פנים" על חולצה/מכנסיים (L52) — וכאן בגודל פי 9 מהפנים האמיתיות, כך שאשכול
    מדורג-שטח (illustration_place) דווקא *מעדיף* אותו (נמדד בדמו 4.10.26: קופסה 590px על המכנסיים
    ב-1 מ-3 פריימים). שני כללים פשוטים במקום: (1) קופסה שכולה מתחת לקופסה אחרת עם חפיפה אופקית
    באותו פריים — גוף, לא פנים; (2) התמדה לפי **מספר פריימים** (≥2 מ-3), לא לפי שטח."""
    kept = []
    for fr in per:
        fr = [b for b in fr if (b[2] - b[0]) <= 0.5]                    # פנים לא רחבות מחצי פריים
        for b in fr:
            under = any(a is not b and a[3] <= b[1] + 0.01 and min(a[2], b[2]) - max(a[0], b[0]) > 0
                        for a in fr)
            if not under:
                kept.append(b)
    if len(per) < 2:
        return kept
    out = []
    for b in kept:
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        n = sum(1 for o in kept if abs((o[0] + o[2]) / 2 - cx) < 0.12 and abs((o[1] + o[3]) / 2 - cy) < 0.12)
        if n >= 2:
            out.append(b)
    return out


def _face_px(f):
    return ((f[0] - HEAD_PAD) * FW, (f[1] - HEAD_PAD) * FH, (f[2] + HEAD_PAD) * FW, (f[3] + HEAD_PAD) * FH)


def resolve_zones(video, plan: dict, detect=None, dur: float | None = None) -> list[str]:
    """'auto' (או בלי zone) → 'top' רק אם בכל החלון הפנים מתחילות מתחת ל-760px; אחרת 'body'.
    בסרטוני הדיבור שלנו הפנים בשליש העליון ⇒ ברוב השוטים זה body (L108)."""
    detect = detect or haar_at
    D = dur if dur is not None else ffdur(video)
    notes = []
    for ev in plan["events"]:
        in_base = any(ev["start"] >= s0 - 0.01 and ev["end"] <= e0 + 0.01 for s0, e0 in plan.get("base_windows") or [])
        if (ev["type"] in FULL_TYPES or ev["type"] in FIXED_POS_TYPES or ev.get("bg")
                or (plan.get("backdrop") and not in_base)
                or ev.get("zone") not in (None, "auto") or ev["start"] >= D):
            continue
        tops, measured = [], True
        for f in (0.15, 0.5, 0.85):
            t = min(D - 0.05, ev["start"] + (ev["end"] - ev["start"]) * f)
            boxes, _m = detect(video, t)
            if boxes is None:
                measured = False
                continue
            tops += [_face_px(b)[1] for b in boxes]
        ev["zone"] = "top" if (measured and all(y >= TOP_ZONE_FREE_Y for y in tops)) else "body"
        notes.append(f"{ev['id']}→{ev['zone']}{'' if measured else '(לא נמדד)'}")
    return notes


def gate_faces(video, plan: dict, m: dict, detect=None, dur: float | None = None) -> dict:
    """MG2 — טקסט שכבה אסור על פנים. משווים קופסאות ופנים **באותו זמן** (5 דגימות לאירוע).
    לא נמדד ⇒ 'reporting' + measured:false — לעולם לא PASS שקט (L51)."""
    detect = detect or haar_at
    D = dur if dur is not None else ffdur(video)
    hits, unmeasured = set(), []
    types = {e["id"]: e["type"] for e in plan["events"]}
    freeze = {e["id"]: float(e["freeze_at"]) for e in plan["events"] if isinstance(e.get("freeze_at"), (int, float))}
    evs = {e["id"]: e for e in plan["events"]}
    for me in m.get("events", []):
        if types.get(me["id"]) == "then_now":
            # v9.44 (L124) — מסך מלא, אבל כל פאנל הוא פריים קפוא אחר: פנים נמדדות בפריים של הפאנל,
            # ממופות לציר הפאנל (object-fit:cover ברוחב מלא ⇒ סקאלה 1, היסט אנכי לפי focal), ומושוות לתוויות שבו
            ev = evs.get(me["id"]) or {}
            for k, top in THEN_NOW_PANELS:
                t = ev.get(f"freeze_{k}_at")
                if t is None:
                    continue
                faces, method = detect(video, min(float(t), D - 0.05))
                if faces is None:
                    unmeasured.append(f"{me['id']}/{k}:{method}")
                    continue
                fy = float(str(ev.get(f"focal_{k}") or "50% 30%").split()[-1].rstrip("%")) / 100.0
                shift = top - (FH - THEN_NOW_H) * fy
                for smp in me.get("samples") or []:
                    for b in [b for b in smp["boxes"] if b.get("text") and top <= b["y0"] < top + THEN_NOW_H]:
                        for f in faces:
                            fx0, fy0, fx1, fy1 = _face_px(f)
                            fy0, fy1 = fy0 + shift, fy1 + shift
                            if min(fx1, b["x1"]) - max(fx0, b["x0"]) > 0 and min(fy1, b["y1"]) - max(fy0, b["y0"]) > 0:
                                hits.add(f"{me['id']}/{k}: «{b['text'][:20]}» על פנים בפאנל")
            continue
        if types.get(me["id"]) in FULL_TYPES or me.get("full"):
            continue
        for smp in me.get("samples") or [{"t": me.get("hero", me["start"]), "boxes": me.get("boxes", [])}]:
            tb = [b for b in smp["boxes"] if b.get("text")]
            if not tb or smp["t"] >= D:
                continue
            # פריים קפוא (telestrator freeze_at): מה שמתחת לטקסט הוא הפריים הקפוא — בודקים פנים בו
            faces, method = detect(video, min(freeze.get(me["id"], smp["t"]), D - 0.05))
            if faces is None:
                unmeasured.append(f"{me['id']}@{smp['t']:.1f}:{method}")
                continue
            for f in faces:
                fx0, fy0, fx1, fy1 = _face_px(f)
                for b in tb:
                    if min(fx1, b["x1"]) - max(fx0, b["x0"]) > 0 and min(fy1, b["y1"]) - max(fy0, b["y0"]) > 0:
                        hits.add(f"{me['id']}@{smp['t']:.1f}: «{b['text'][:20]}» על פנים")
    if hits:
        return gate("MG2_face_occlusion", False, "blocking", "; ".join(sorted(hits)), measured=True)
    if unmeasured:
        return gate("MG2_face_occlusion", True, "reporting", f"לא נמדד: {unmeasured[:4]}", measured=False)
    return gate("MG2_face_occlusion", True, "blocking", "אין טקסט על פנים (5 דגימות לאירוע)", measured=True)

# ─────────────────────────── קומפוזיציה ───────────────────────────

def b64(p: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(Path(p).read_bytes()).decode()


def font_faces() -> list[str]:
    spec = json.loads(os.environ["MG_FONTS_JSON"]) if os.environ.get("MG_FONTS_JSON") else \
        [(f, w, str(BRAND / n)) for f, w, n in FONTS]
    out = []
    for fam, wt, fp in spec:
        fp = Path(fp)
        if fp.exists():
            mime = {".otf": "font/otf", ".woff2": "font/woff2", ".woff": "font/woff"}.get(fp.suffix, "font/ttf")
            out.append(f"@font-face{{font-family:'{fam}';font-weight:{wt};font-style:normal;"
                       f"src:url({b64(fp, mime)});font-display:block}}")
    return out


def compose(plan: dict, out: Path) -> Path:
    js = "".join((MOT / "vendor" / n).read_text(encoding="utf-8") + "\n" for n in
                 ("gsap.min.js", "CustomEase.min.js", "DrawSVGPlugin.min.js"))
    js += (MOT / "lib" / "rel-motion.js").read_text(encoding="utf-8")
    for t in sorted((MOT / "templates").glob("*.js")):
        js += "\n" + t.read_text(encoding="utf-8")
    pub = {k: v for k, v in plan.items() if not k.startswith("_")}
    pub["duration"] = float(plan["duration"]) + float(plan.get("tail") or 0)
    pub["assets"] = {}
    if LOGO.exists():
        pub["assets"]["logo"] = b64(LOGO, "image/png")
    if LOGO_WHITE.exists():
        pub["assets"]["logo_mask"] = b64(LOGO_WHITE, "image/png")
    css = (MOT / "lib" / "rel-motion.css").read_text(encoding="utf-8")
    bg = "#000" if plan.get("opaque") else "transparent"
    html = f"""<!doctype html><html dir="rtl" lang="he"><head><meta charset="utf-8">
<style>{''.join(font_faces())}</style><style>{css} body{{background:{bg}}}</style></head>
<body><div id="stage" data-composition-id="main" data-width="{FW}" data-height="{FH}"
 data-duration="{pub['duration']:.3f}" data-fps="30"></div>
<script>{js}</script>
<script>window.__PLAN={json.dumps(pub, ensure_ascii=False)};REL.build(window.__PLAN);</script>
</body></html>"""
    out.write_text(html, encoding="utf-8")
    return out


_MP_MODEL = MOT / "models" / "face_landmarker.task"


def _mp_landmarker():
    """MediaPipe FaceLandmarker עם blendshapes (חיוך/פה פתוח/מצמוץ) — None אם לא מותקן/אין מודל."""
    try:
        from mediapipe.tasks.python import vision, BaseOptions
    except Exception:       # noqa: BLE001
        try:
            from mediapipe.tasks.python import vision
            from mediapipe.tasks.python.core.base_options import BaseOptions
        except Exception:   # noqa: BLE001
            return None
    if not _MP_MODEL.exists():
        return None
    try:
        opts = vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(_MP_MODEL)),
                                            output_face_blendshapes=True, num_faces=3)
        return vision.FaceLandmarker.create_from_options(opts)
    except Exception:       # noqa: BLE001
        return None


def pick_smile_frame(video, lo: float, hi: float, step: float = 1 / 15, anchor: float | None = None,
                     debug: bool = False, words: list | None = None) -> dict | None:
    """name_sparkle (הראל 8.10.26): "להקפיא את הפריים ברגע שהוא מחייך" — ובפריים **מחמיא**,
    "לא עם פה פתוח כזה כי זה מצחיק". סורק את [lo,hi] ב-15fps.
    מנוע ראשי: MediaPipe FaceLandmarker blendshapes — smile=mouthSmileL/R, jaw=jawOpen, blink=eyeBlinkL/R.
      ציון = (0.15+smile) × קנס פה-פתוח (jaw מעל 0.10+0.35·smile — צחוק אמיתי עם שיניים מותר, פה פעור בדיבור לא)
             × עיניים פתוחות × יציבות (שינוי jaw מול השכנים = באמצע מילה) × הפסקת דיבור (words_final) × חדות × גודל.
    גיבוי: Haar פנים+חיוך (ללא מודל). שוט: חיתוך = קורלציית היסטוגרמה < 0.6; עדיפות לשוט של anchor.
    בלי פנים ⇒ None (התבנית רצה בלי הקפאה). freeze_at מספרי בתוכנית גובר תמיד."""
    try:
        import cv2
        import numpy as np
    except Exception:       # noqa: BLE001
        return None
    hc = Path(getattr(getattr(cv2, "data", None), "haarcascades", "") or "")
    fc = cv2.CascadeClassifier(str(hc / "haarcascade_frontalface_default.xml"))
    scas = cv2.CascadeClassifier(str(hc / "haarcascade_smile.xml"))
    lm = _mp_landmarker()
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    anchor = lo if anchor is None else anchor
    cands, t, shot, prev_hist, anchor_shot = [], max(0.0, lo), 0, None, None
    while t <= hi:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * fps)))
        ok, fr = cap.read()
        if not ok or fr is None:
            break
        h, w = fr.shape[:2]
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        hist = cv2.normalize(cv2.calcHist([cv2.resize(g, (160, 284))], [0], None, [64], [0, 256]), None).flatten()
        if prev_hist is not None and cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL) < 0.6:
            shot += 1
        prev_hist = hist
        if anchor_shot is None and t >= anchor - 1e-6:
            anchor_shot = shot
        speaking = any(float(wd.get("start", 0)) - 0.03 <= t <= float(wd.get("end", 0)) + 0.03 for wd in (words or []))
        c = None
        if lm is not None:
            import mediapipe as mp
            rgb = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)
            res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            ox, oy, sx_, sy_ = 0.0, 0.0, 1.0, 1.0
            if not res.face_landmarks and not fc.empty():
                # פנים קטנות בשוט רחב — הגלאי של MediaPipe קצר-טווח: Haar מאתר, חותכים פי 2.6 סביב, ומריצים שוב
                hf = [f for f in fc.detectMultiScale(g, 1.1, 5, minSize=(int(w * 0.05), int(w * 0.05))) if f[2] <= w * 0.6]
                if len(hf):
                    x, y, fw_, fh_ = max(hf, key=lambda f: f[2] * f[3])
                    cx, cy, half = x + fw_ / 2, y + fh_ / 2, int(max(fw_, fh_) * 1.3)
                    X0, Y0 = int(max(0, cx - half)), int(max(0, cy - half))
                    X1, Y1 = int(min(w, cx + half)), int(min(h, cy + half))
                    crop = np.ascontiguousarray(rgb[Y0:Y1, X0:X1])
                    res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=crop))
                    ox, oy, sx_, sy_ = X0 / w, Y0 / h, (X1 - X0) / w, (Y1 - Y0) / h
            best_i, best_area = None, 0.0
            for k, pts in enumerate(res.face_landmarks or []):
                xs, ys = [ox + p.x * sx_ for p in pts], [oy + p.y * sy_ for p in pts]
                area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                if area > best_area:
                    best_i, best_area, box = k, area, (min(xs), min(ys), max(xs), max(ys))
                    # yaw: האף מול אמצע זוויות העיניים החיצוניות (1 / 33 / 263) — פנים מסובבות לצד = לא מחמיא
                    ex0, ex1, nx = xs[33], xs[263], xs[1]
                    yaw = abs(nx - (ex0 + ex1) / 2) / max(1e-6, abs(ex1 - ex0))
            if best_i is not None and (box[2] - box[0]) >= 0.04:
                bs = {b.category_name: b.score for b in res.face_blendshapes[best_i]}
                smile = (bs.get("mouthSmileLeft", 0) + bs.get("mouthSmileRight", 0)) / 2
                jaw = bs.get("jawOpen", 0)
                blink = (bs.get("eyeBlinkLeft", 0) + bs.get("eyeBlinkRight", 0)) / 2
                x0, y0, x1, y1 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
                sharp = cv2.Laplacian(g[max(0, y0):y1, max(0, x0):x1], cv2.CV_64F).var()
                c = {"t": round(t, 3), "engine": "mediapipe", "smile_bs": round(smile, 3), "jaw": round(jaw, 3), "yaw": round(yaw, 3),
                     "blink": round(blink, 3), "smile": int(round(smile * 46)), "speaking": speaking, "shot": shot,
                     "sharp": round(float(sharp), 1), "fw": box[2] - box[0],
                     "zoom_origin": f"{(box[0] + box[2]) / 2 * 100:.1f}% {(box[1] + box[3]) / 2 * 100:.1f}%"}
        elif not fc.empty():
            faces = [f for f in fc.detectMultiScale(g, 1.12, 6, minSize=(int(w * 0.12), int(w * 0.12))) if f[2] <= w * 0.6]
            if len(faces):
                x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                roi = cv2.equalizeHist(g[y + fh // 2: y + fh, x: x + fw])
                smile = 0
                for nb in (12, 20, 28, 36, 46):
                    if len(scas.detectMultiScale(roi, 1.6, nb, minSize=(fw // 4, fh // 10))):
                        smile = nb
                sharp = cv2.Laplacian(g[y: y + fh, x: x + fw], cv2.CV_64F).var()
                c = {"t": round(t, 3), "engine": "haar", "smile_bs": smile / 46, "jaw": 0.0, "blink": 0.0, "yaw": 0.0,
                     "smile": smile, "speaking": speaking, "shot": shot, "sharp": round(float(sharp), 1), "fw": fw / w,
                     "zoom_origin": f"{(x + fw / 2) / w * 100:.1f}% {(y + fh / 2) / h * 100:.1f}%"}
        if c:
            cands.append(c)
        t += step
    cap.release()
    if lm is not None:
        try:
            lm.close()
        except Exception:   # noqa: BLE001
            pass
    if not cands:
        return None
    for i, c in enumerate(cands):
        nb = [o["jaw"] for o in (cands[i - 1] if i else None, cands[i + 1] if i + 1 < len(cands) else None)
              if o is not None and o["shot"] == c["shot"] and abs(o["t"] - c["t"]) < 3 * step]
        c["mouth_motion"] = round(sum(abs(c["jaw"] - j) for j in nb) / len(nb), 3) if nb else 0.05
        open_pen = max(0.1, 1 - 3 * max(0.0, c["jaw"] - 0.10 - 0.35 * c["smile_bs"]))
        c["score"] = ((0.15 + c["smile_bs"]) * open_pen * max(0.15, 1 - 0.9 * c["blink"])
                      * max(0.3, 1 - 4 * c["mouth_motion"]) * (0.6 if c["speaking"] else 1.0)
                      * max(0.2, 1 - 3 * max(0.0, c["yaw"] - 0.08))
                      * math.log1p(c["sharp"]) * c["fw"])
    good = lambda c: (c["smile_bs"] >= 0.45 and c["jaw"] <= 0.08 + 0.32 * c["smile_bs"]      # noqa: E731
                      and c["blink"] <= 0.5 and c["yaw"] <= 0.18)
    top = lambda xs: max(xs, key=lambda c: c["score"]) if xs else None      # noqa: E731
    same = [c for c in cands if c["shot"] == anchor_shot]
    best = top([c for c in same if good(c)]) or top([c for c in cands if good(c)]) or top(same) or top(cands)
    best = dict(best)
    best["flattering"] = bool(good(best))
    best["same_shot"] = best["shot"] == anchor_shot
    best["method"] = ("smile" if good(best) else "best-face") + ("" if best["same_shot"] else "+other-shot") \
        + f"/{best['engine']}"
    if debug:
        best = dict(best, cands=cands, anchor_shot=anchor_shot)
    return best


def attach_freezes(plan: dict, base: Path | None, words: list | None = None) -> list[str]:
    """v9.38 — telestrator עם freeze_at: הפריים מהבסיס (אותו ציר) מוזרק כ-JPEG ל-freeze_src.
    v9.42 — name_sparkle: freeze_at חסר/"smile" ⇒ pick_smile_frame בחלון האירוע (‎-1ש לפני עד הסוף);
    freeze:false ⇒ בלי הקפאה. בלי בסיס ⇒ חי (בלי הקפאה) ומדווח."""
    notes = []
    for ev in plan.get("events", []):
        if (ev.get("type") == "name_sparkle" and base and ev.get("freeze", True) is not False
                and (ev.get("freeze_at") in (None, "smile"))):
            _hi = float(ev["start"]) + 3.0 if ev.get("insert", True) else float(ev["end"]) - 0.3
            pk = pick_smile_frame(base, float(ev["start"]) - 1.0, _hi, anchor=float(ev["start"]), words=words)
            if pk and not pk.get("flattering") and not ev.get("freeze_any"):
                # הראל 8.10.26: פריים לא מחמיא ("פה פתוח ... מצחיק") גרוע מבלי הקפאה ⇒ השם על הווידאו החי
                ev["freeze_at"], ev["freeze_pick"] = None, pk
                notes.append(f"{ev['id']}: אין חיוך מחמיא בחלון (הכי טוב @{pk['t']:.2f}: חיוך {pk['smile_bs']:.2f} פה {pk['jaw']:.2f}"
                             f" yaw {pk.get('yaw', 0):.2f}) — בלי הקפאה; להזיז את האירוע לרגע חיוך או לקבוע freeze_at")
            elif pk:
                ev["freeze_at"], ev["freeze_pick"] = pk["t"], pk
                ev.setdefault("zoom_origin", pk["zoom_origin"])
                notes.append(f"{ev['id']}: חיוך @{pk['t']:.2f} ({pk['method']}, חיוך {pk['smile_bs']:.2f} פה {pk['jaw']:.2f})")
            else:
                ev["freeze_at"] = None
                notes.append(f"{ev['id']}: לא נמצאו פנים — בלי הקפאה")
        if ev.get("type") == "then_now":
            # v9.44 — שני פריימים מהבסיס (אז/היום). בלי בסיס או בלי אחד מהם — האירוע לא מוצג (פאנל שחור גרוע מאפס)
            for k in ("a", "b"):
                t = ev.get(f"freeze_{k}_at")
                if t is None or not base:
                    notes.append(f"{ev['id']}: freeze_{k}_at חסר/אין בסיס — then_now לא יוצג")
                    ev["_drop"] = True
                    continue
                with tempfile.TemporaryDirectory() as td:
                    fp = Path(td) / f"fz{k}.jpg"
                    sh([FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-ss", f"{float(t):.3f}", "-i", base,
                        "-frames:v", "1", "-vf", f"scale={FW}:{FH}", "-q:v", "2", fp])
                    if fp.exists():
                        ev[f"freeze_{k}_src"] = b64(fp, "image/jpeg")
                        notes.append(f"{ev['id']}: פאנל {k} @{float(t):.2f}")
                    else:
                        ev["_drop"] = True
                        notes.append(f"{ev['id']}: חילוץ פאנל {k} נכשל")
            continue
        if ev.get("freeze_at") is None:
            continue
        if not base:
            notes.append(f"{ev['id']}: אין בסיס — בלי הקפאה")
            continue
        with tempfile.TemporaryDirectory() as td:
            fp = Path(td) / "fz.jpg"
            sh([FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-ss", f"{float(ev['freeze_at']):.3f}", "-i", base,
                "-frames:v", "1", "-vf", f"scale={FW}:{FH}", "-q:v", "2", fp])
            if fp.exists():
                ev["freeze_src"] = b64(fp, "image/jpeg")
                notes.append(f"{ev['id']}: פריים קפוא @{float(ev['freeze_at']):.2f}")
            else:
                notes.append(f"{ev['id']}: חילוץ פריים נכשל")
    plan["events"] = [e for e in plan.get("events", []) if not e.get("_drop")]
    return notes


def node(*args, timeout=3600):
    return sh([NODE, MOT / "render.js", *args], timeout=timeout)

# ─────────────────────────── מדידה (MG1/MG5/MG6) ───────────────────────────

def gates_from_measure(m: dict) -> list[dict]:
    outside = []
    for ev in m.get("events", []):
        for smp in ev.get("samples") or [{"t": ev.get("hero"), "boxes": ev.get("boxes", [])}]:
            for b in smp["boxes"]:
                if not b.get("text"):
                    continue        # קופסה בלי טקסט (דיאגרמה) — מותר על כל הפריים
                if b["x0"] < SAFE["x0"] or b["x1"] > SAFE["x1"] or b["y0"] < SAFE["y0"] or b["y1"] > SAFE["y1"]:
                    outside.append(f"{ev['id']}: «{b['text'][:24]}» [{b['x0']:.0f},{b['y0']:.0f},{b['x1']:.0f},{b['y1']:.0f}]")
    outside = sorted(set(outside))
    gs = [gate("MG1_safe_zone", not outside, "blocking",
               "; ".join(outside[:6]) or "כל הטקסט באזור הבטוח (מתחת ל-UI, מעל הכתוביות)")]
    fonts = m.get("fonts", [])
    bad = [f"{f['family']} {f['weight']}:{f['status']}" for f in fonts if f.get("status") == "error"]
    fams = {f["family"] for f in fonts if f.get("status") == "loaded"}
    if not {"Assistant", "Ploni"} <= fams:
        bad.append(f"חסרים פונטי מותג (נטענו: {sorted(fams)})")
    gs.append(gate("MG5_brand_fonts", not bad, "blocking", "; ".join(bad) or "Assistant + Ploni נטענו"))
    errs = m.get("errors") or []
    gs.append(gate("MG6_page_errors", not errs, "blocking", "; ".join(errs[:4]) or "אין שגיאות דף"))
    return gs


def measure(html: Path, out: Path) -> tuple[dict, list[dict]]:
    r = node("measure", html, out, timeout=900)
    if r.returncode != 0:
        return {}, [gate("MG6_page_errors", False, "blocking", (r.stderr or r.stdout)[-400:])]
    m = json.loads(out.read_text(encoding="utf-8"))
    return m, gates_from_measure(m)

# ─────────────────────────── רינדור ───────────────────────────

def render_layer(W: Path, plan: dict, workers: int = 6, html: Path | None = None) -> tuple[Path, dict]:
    html = html or compose(plan, W / "motion_comp.html")
    frames = W / "_mg_frames"
    shutil.rmtree(frames, ignore_errors=True)
    r = node("frames", html, frames, "--workers", str(workers), timeout=7200)
    if r.returncode != 0:
        raise RuntimeError("render.js frames: " + (r.stderr or r.stdout)[-600:])
    info = json.loads(r.stdout.strip().splitlines()[-1])
    out = W / "MG_LAYER.mov"
    pix = ["-pix_fmt", "yuv444p10le"] if plan.get("opaque") else ["-pix_fmt", "yuva444p10le"]
    r = sh([FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-framerate", "30", "-i", frames / "%05d.png",
            "-c:v", "prores_ks", "-profile:v", "4444", *pix, "-vendor", "apl0", out])
    if r.returncode != 0:
        raise RuntimeError("prores encode: " + r.stderr[-400:])
    shutil.rmtree(frames, ignore_errors=True)
    info["layer"], info["layer_sha"] = out.name, sha(out)
    return out, info

# ─────────────────────────── SFX ───────────────────────────

def ensure_sfx() -> dict:
    """SFX פרוצדורליים (אפס רישוי, דטרמיניסטיים, seed קבוע). עדינים בכוונה — מתחת לדיבור."""
    d = MOT / "sfx"
    d.mkdir(exist_ok=True)
    want = {k: d / f"{k}.wav" for k in SFX_KINDS}
    want.update({f"{k}_{v}": d / f"{k}_{v}.wav" for k, n in SFX_VARIANTS.items() for v in range(1, n)})
    if not want["sparkle"].exists():
        _sparkle_wav(want["sparkle"])
    if all(p.exists() for p in want.values()):
        return want
    import numpy as np
    sr = 48000
    rng = np.random.default_rng(7)

    def save(p, x):
        x = np.clip(x / (np.abs(x).max() + 1e-9) * 0.9, -1, 1)
        st = (np.stack([x, x], 1) * 32767).astype("<i2")
        with wave.open(str(p), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(st.tobytes())

    def sweep_noise(dur, f0, f1, q=0.9):
        n = int(sr * dur)
        x = rng.standard_normal(n)
        out = np.zeros(n)
        x1 = x2 = y1 = y2 = 0.0
        for i in range(n):           # ביקוואד band-pass עם תדר זז (RBJ)
            f = f0 * (f1 / f0) ** (i / n)
            w0 = 2 * math.pi * f / sr
            al = math.sin(w0) / (2 * q)
            a0, a1, a2 = 1 + al, -2 * math.cos(w0), 1 - al
            v = (al * x[i] - al * x2 - a1 * y1 - a2 * y2) / a0
            x2, x1, y2, y1 = x1, x[i], y1, v
            out[i] = v
        return out

    n = int(sr * 0.42); t = np.arange(n) / sr
    save(want["whoosh"], sweep_noise(0.42, 350, 2600) * np.sin(np.pi * np.clip(t / 0.42, 0, 1)) ** 1.6)
    n = int(sr * 0.14); t = np.arange(n) / sr
    save(want["pop"], np.sin(2 * np.pi * (900 * t - 1600 * t * t)) * np.exp(-t * 38))
    n = int(sr * 0.05); t = np.arange(n) / sr
    save(want["tick"], np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 140))
    n = int(sr * 0.5); t = np.arange(n) / sr
    save(want["hit"], np.sin(2 * np.pi * (95 * t - 40 * t * t)) * np.exp(-t * 9)
         + 0.25 * rng.standard_normal(n) * np.exp(-t * 40))
    # v9.39 — וריאציות (אותו אופי, צבע אחר): הראל — "לגוון או למתן"
    n = int(sr * 0.55); t = np.arange(n) / sr
    save(want["whoosh_1"], sweep_noise(0.55, 250, 1700, 0.7) * np.sin(np.pi * np.clip(t / 0.55, 0, 1)) ** 2.2)
    n = int(sr * 0.30); t = np.arange(n) / sr
    save(want["whoosh_2"], sweep_noise(0.30, 700, 3600, 1.1) * np.sin(np.pi * np.clip(t / 0.30, 0, 1)) ** 1.3)
    n = int(sr * 0.12); t = np.arange(n) / sr
    save(want["pop_1"], np.sin(2 * np.pi * (700 * t - 1100 * t * t)) * np.exp(-t * 34))
    n = int(sr * 0.10); t = np.arange(n) / sr
    save(want["pop_2"], np.sin(2 * np.pi * (1150 * t - 2200 * t * t)) * np.exp(-t * 46))
    n = int(sr * 0.05); t = np.arange(n) / sr
    save(want["tick_1"], np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 120))
    n = int(sr * 0.5); t = np.arange(n) / sr
    save(want["hit_1"], np.sin(2 * np.pi * (70 * t - 25 * t * t)) * np.exp(-t * 7)
         + 0.12 * rng.standard_normal(n) * np.exp(-t * 55))
    return want


def _sparkle_wav(p: Path, sr: int = 48000) -> Path:
    """צליל "חמוד" לשם מתאמן: ארפג'ו פעמונים עולה (E6-G#6-B6-E7, צלילי פעמון עם חלקיים לא-הרמוניים)
    + נצנוץ דק של פינגים גבוהים. דטרמיניסטי (seed 11), ‎~1ש, סטריאו קל — פינגים מתפזרים בין הערוצים."""
    import numpy as np
    rng = np.random.default_rng(11)
    n = int(sr * 1.35); t = np.arange(n) / sr
    L = np.zeros(n); R = np.zeros(n)

    def bell(f, at, amp, dec, pan=0.0):
        i0 = int(at * sr); tt = t[: n - i0]
        x = (np.sin(2 * np.pi * f * tt) + 0.42 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * dec * 1.8)
             + 0.18 * np.sin(2 * np.pi * f * 5.40 * tt) * np.exp(-tt * dec * 3.2))
        x *= amp * np.exp(-tt * dec) * np.clip(tt / 0.003, 0, 1)
        L[i0:] += x * (1 - pan) ; R[i0:] += x * (1 + pan)

    # קליק תריס רך (name_sparkle = "הפריים הופך לתמונה"): שני פרצי רעש קצרים מסוננים, ואז הפעמונים
    for at, dur, amp in ((0.0, 0.006, 0.55), (0.032, 0.010, 0.40)):
        i0, m = int(at * sr), int(dur * sr)
        burst = rng.standard_normal(m) * np.exp(-np.arange(m) / (m / 3)) * amp
        burst = np.diff(np.concatenate([[0.0], burst]))          # הטיה לגבוהים
        L[i0:i0 + m] += burst; R[i0:i0 + m] += burst
    for k, f in enumerate((1318.5, 1661.2, 1975.5, 2637.0)):
        bell(f, 0.28 + k * 0.065, 1.0 - k * 0.08, 7.5 - k * 0.6, pan=(-0.25, 0.1, -0.1, 0.25)[k])
    for _ in range(11):
        bell(float(rng.uniform(3200, 6400)), float(rng.uniform(0.44, 1.0)), float(rng.uniform(0.10, 0.22)),
             float(rng.uniform(18, 30)), pan=float(rng.uniform(-0.6, 0.6)))
    fade = np.clip((1.35 - t) / 0.12, 0, 1)
    st = np.stack([L * fade, R * fade], 1)
    st = st / (np.abs(st).max() + 1e-9) * 0.9
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes((st * 32767).astype("<i2").tobytes())
    return p


def _ev_sfx(ev: dict) -> list[dict]:
    """ה-SFX של אירוע + צליל קבוע של התבנית (AUTO_SFX) אם התוכנית לא הגדירה אותו."""
    xs = list(ev.get("sfx") or [])
    auto = AUTO_SFX.get(ev.get("type"))
    if auto and not any(x.get("kind") == auto[0] for x in xs) and not ev.get("no_auto_sfx"):
        xs = [x for x in xs if abs(float(x["at"]) - float(ev["start"])) > SFX_MIN_GAP]   # הצליל הקבוע מחליף צליל כניסה
        xs.append({"at": round(float(ev["start"]) + auto[1], 3), "kind": auto[0]})
    return xs


def plan_sfx(plan: dict) -> tuple[list[tuple[float, str, float]], list[str]]:
    """v9.39 — מינון ומגוון: מרווח מינימלי SFX_MIN_GAP (hit גובר), וריאציה מתחלפת לכל סוג,
    ואותו סוג שוב תוך SFX_REPEAT_WIN ⇒ ‎-4dB. מחזיר [(at, file_key, db)] + מה שהוסר."""
    raw = sorted((float(x["at"]), x["kind"]) for ev in plan["events"] for x in _ev_sfx(ev))
    kept, dropped = [], []
    for at, k in raw:
        if kept and at - kept[-1][0] < SFX_MIN_GAP:
            if k in SFX_WINS and kept[-1][1] not in SFX_WINS:
                dropped.append(f"{kept[-1][1]}@{kept[-1][0]:.2f}"); kept[-1] = (at, k)
            else:
                dropped.append(f"{k}@{at:.2f}")
            continue
        kept.append((at, k))
    capped = []
    for at, k in kept:
        win = [x for x in capped if at - x[0] < SFX_CAP_WIN]
        if len(win) >= SFX_CAP_N:
            low = min(win, key=lambda x: SFX_PRIO.get(x[1], 0))
            if SFX_PRIO.get(k, 0) > SFX_PRIO.get(low[1], 0):
                capped.remove(low); dropped.append(f"{low[1]}@{low[0]:.2f}")
            else:
                dropped.append(f"{k}@{at:.2f}")
                continue
        capped.append((at, k))
    kept = capped
    out, count, last = [], {}, {}
    for at, k in kept:
        i = count.get(k, 0); count[k] = i + 1
        v = i % SFX_VARIANTS.get(k, 1)
        db = SFX_DB[k] + (SFX_REPEAT_DB if k in last and at - last[k] < SFX_REPEAT_WIN else 0.0)
        last[k] = at
        out.append((at, k if v == 0 else f"{k}_{v}", db))
    return out, dropped


def base_color(video) -> dict:
    """תגיות הצבע של הבסיס — ההרכבה חייבת לשמור אותן כמות שהן (L116)."""
    r = sh([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=pix_fmt,color_range,color_space,color_transfer,color_primaries", "-of", "json", video])
    try:
        st = (json.loads(r.stdout).get("streams") or [{}])[0]
    except Exception:
        st = {}
    return {k: st.get(k) for k in ("pix_fmt", "color_range", "color_space", "color_transfer", "color_primaries")}


def gate_color(base, out) -> dict:
    """MG11 — ההרכבה לא נוגעת בצבע: תגיות הצבע של הפלט = של הבסיס (אין סף — שוויון).
    דמו HSPU 4.10.26: בסיס HLG/bt2020nc יצא מתויג bt709 ⇒ הצבע "מוזר" (הראל)."""
    b, o = base_color(base), base_color(out)
    keys = ("color_space", "color_transfer", "color_primaries", "color_range")
    diff = [f"{k}: {b.get(k)}→{o.get(k)}" for k in keys if (b.get(k) or "unknown") != (o.get(k) or "unknown")]
    return gate("MG11_color_preserved", not diff, "blocking", "; ".join(diff) or f"תגיות צבע זהות לבסיס ({b.get('color_space')})",
                base=b, out=o)

# ─────────────────────────── הרכבה ───────────────────────────

def composite(base: Path, layer: Path, out: Path, plan: dict, lossless=False) -> dict:
    tail = float(plan.get("tail") or 0.0)
    sfx, sfx_dropped = plan_sfx(plan)
    files = ensure_sfx() if sfx else {}
    inputs = ["-i", base, "-i", layer]
    for _, k, _db in sfx:
        inputs += ["-i", files[k]]
    # v9.39 (L116) — הצבע של הבסיס נשמר: השכבה (RGBA) מומרת ל-YUV במטריצה *של הבסיס*, וההרכבה ב-yuv420
    # בלי המרה אוטומטית של הבסיס; הפלט מתויג בדיוק כמו הבסיס (HLG/bt2020 נשאר HLG/bt2020).
    bc = base_color(base)
    _cs = bc.get("color_space") or "bt709"
    mtx = "bt2020" if _cs.startswith("bt2020") else ("bt709" if _cs == "bt709" else "bt601")
    vf = "[0:v]" + (f"tpad=stop_mode=clone:stop_duration={tail:.3f}," if tail > 0 else "") + "format=yuv420p[b];"
    vf += f"[1:v]scale=out_color_matrix={mtx}:out_range=tv,format=yuva420p[o];"
    # overlay יחיד, בלי seek על אף קלט (FFMPEG-STALL / v9.10)
    vf += "[b][o]overlay=0:0:format=yuv420:eof_action=pass,format=yuv420p[v]"
    af = "[0:a]aresample=48000," + (f"apad=pad_dur={tail:.3f}" if tail > 0 else "anull") + "[a0]"
    labels = ["[a0]"]
    for i, (at, k, db) in enumerate(sfx):
        ms = max(0, int(round(at * 1000)))
        af += f";[{i + 2}:a]aresample=48000,volume={db:.1f}dB,adelay={ms}|{ms}[s{i}]"
        labels.append(f"[s{i}]")
    af += (f";{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first[a]"
           if len(labels) > 1 else ";[a0]anull[a]")
    tags = []
    for opt, key in (("-colorspace", "color_space"), ("-color_trc", "color_transfer"),
                     ("-color_primaries", "color_primaries"), ("-color_range", "color_range")):
        if bc.get(key) and bc[key] != "unknown":
            tags += [opt, bc[key]]
    venc = (["-c:v", "ffv1", "-level", "3"] if lossless else
            ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p"]) + tags
    cmd = [FFMPEG, "-nostdin", "-y", "-loglevel", "error", *inputs, "-filter_complex", vf + ";" + af,
           "-map", "[v]", "-map", "[a]", *venc, "-c:a", "aac", "-b:a", "256k", "-ar", "48000", out]
    t0 = time.time()
    r = sh(cmd, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError("composite: " + r.stderr[-600:])
    exp, got = ffdur(base) + tail, ffdur(out)
    return {"out": Path(out).name, "secs": round(time.time() - t0, 1), "sfx": len(sfx), "sfx_dropped": sfx_dropped,
            "dur_expected": round(exp, 3), "dur_out": round(got, 3), "dur_ok": abs(got - exp) < 0.1}

# ─────────────────────────── גיליונות ───────────────────────────

def _tile(images, labels, out: Path, cols=6, w=360, h=640) -> Path:
    from PIL import Image, ImageDraw
    rows = max(1, math.ceil(len(images) / cols))
    canvas = Image.new("RGB", (cols * w, rows * h), (20, 20, 20))
    for i, (im, lab) in enumerate(zip(images, labels)):
        im = im.convert("RGB").resize((w, h))
        dr = ImageDraw.Draw(im)
        dr.rectangle([0, 0, w, 26], fill=(0, 0, 0))
        dr.text((8, 6), lab, fill=(255, 255, 255))
        canvas.paste(im, ((i % cols) * w, (i // cols) * h))
    canvas.save(out, quality=88)
    return out


def frame_at(video, t: float):
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "f.png"
        sh([FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", p])
        return Image.open(p).copy() if p.exists() else None


def sheet(video: Path, plan: dict, out: Path) -> Path:
    """גיליון אחרי הרכבה: שני פריימים לכל אירוע (30% ו-75% מהחלון). חוק הראייה: נפתח בסשן."""
    ims, labs = [], []
    for ev in plan["events"]:
        d = ev["end"] - ev["start"]
        for frac in (0.3, 0.75):
            t = ev["start"] + d * frac
            im = frame_at(video, t)
            if im is not None:
                ims.append(im); labs.append(f"{ev['id']} @ {t:.2f}s")
    return _tile(ims, labs, out)


def snaps(W: Path, plan: dict, ts: list[float], base: Path | None) -> Path:
    """לולאת הביקורת: שכבת MG בזמנים נבחרים, מורכבת על פריים הבסיס (אם ניתן) → MG_SNAPS.jpg."""
    from PIL import Image
    attach_freezes(plan, base, load_words(W))
    if base:
        base, _ins = apply_inserts(W, plan, base)      # הגיליון על הציר שאחרי ההכנסה — כמו הגימור
    html = compose(plan, W / "motion_comp.html")
    d = W / "_mg_snaps"
    shutil.rmtree(d, ignore_errors=True)
    r = node("snap", html, d, "--at", ",".join(f"{t:.2f}" for t in ts))
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-400:])
    ims, labs = [], []
    D = ffdur(base) if base else 0
    for t in ts:
        fg = Image.open(d / f"snap_{t:.2f}.png").convert("RGBA")
        bg = frame_at(base, min(t, D - 0.05)) if base and D else None
        bg = (bg.convert("RGBA").resize(fg.size) if bg is not None else Image.new("RGBA", fg.size, (60, 60, 60, 255)))
        bg.alpha_composite(fg)
        ims.append(bg); labs.append(f"{t:.2f}s")
    return _tile(ims, labs, W / "MG_SNAPS.jpg")


def suppress_windows(plan: dict) -> list[list[float]]:
    """חלונות שבהם הטקסט על המסך הוא הדיבור עצמו — הכתוביות יורדות כדי שלא יהיה טקסט כפול.
    true ⇒ כל חלון האירוע · [s,e] ⇒ חלון מפורש (למשל רק השאלה בתוך אירוע הסקר)."""
    out = []
    for e in plan.get("events", []):
        v = e.get("suppress_captions")
        if isinstance(v, (list, tuple)) and len(v) == 2:
            out.append([float(v[0]), float(v[1])])
        elif v:
            out.append([float(e["start"]), float(e["end"])])
    return out

# ─────────────────────────── מועמדים ───────────────────────────

ANATOMY = ("רדיוס", "אולנה", "פרונציה", "סופינציה", "אמה", "שכמה", "רוטטור", "דלתא", "טרפז", "לטיסימוס",
           "ארבע ראשי", "ירך אחורי", "המסטרינג", "עכוז", "גלוטאוס", "סרעפת", "עמוד שדרה", "חוליות",
           "מרפק", "ברך", "קרסול", "אגן", "כתף", "גיד", "רצועה", "סחוס", "שריר")
UNITS = ("ק\"ג", "קילו", "שנה", "שנים", "אחוז", "%", "דקות", "דקה", "חזרות", "סטים", "מעלות", "ימים", "שבועות", "חודשים")
CTA = ("תכתבו לנו בתגובות", "פגישת יעדים", "בלינק", "תשלחו", "תייגו")


def propose(W: Path) -> dict:
    words = load_words(W)
    txt = [(w.get("word") or "", float(w["start"]), float(w["end"])) for w in words]
    cands = []
    end_i = next((i for i, (w, *_x) in enumerate(txt) if re.search(r"[?.!]$", w)), None)
    if end_i is not None and end_i <= 8 and txt[end_i][2] <= 3.6:
        cands.append({"type": "kinetic_title", "start": txt[0][1], "end": txt[end_i][2] + 1.2,
                      "text": " ".join(w for w, *_x in txt[:end_i + 1]),
                      "word_times": [s for _w, s, _e in txt[:end_i + 1]], "suppress_captions": True,
                      "why": "משפט פתיחה קצר — הוק קינטי"})
    for i, (w, s, e) in enumerate(txt):
        if re.search(r"\d", w):
            nxt = txt[i + 1][0] if i + 1 < len(txt) else ""
            if any(u in nxt or u in w for u in UNITS):
                cands.append({"type": "stat", "start": round(s - 0.1, 2), "end": round(e + 2.0, 2),
                              "value": re.sub(r"\D", "", w), "unit": nxt.strip(",."), "why": "מספר עם יחידה"})
        for a in ANATOMY:
            if a in w:
                cands.append({"type": "anatomy", "at": s, "term": a,
                              "why": "מונח אנטומי — forearm/angle/callout או מסלול illustration_build"})
                break
    flat = " ".join(w for w, *_x in txt)
    for cta in CTA:
        if cta in flat:
            k = len(flat[:flat.index(cta)].split())
            if k < len(txt):
                cands.append({"type": "poll", "at": txt[k][1], "why": f"CTA: {cta}"})
    run = []
    for w, s, e in txt + [("", 1e9, 1e9)]:
        if w.endswith(","):
            run.append((w, s))
            continue
        if len(run) >= 2 and run[-1][1] - run[0][1] < 6:
            items = [x.strip(",") for x, _ in run] + ([w.strip(".?!")] if w else [])
            cands.append({"type": "chips|list_stack", "start": run[0][1], "items": items, "why": "מנייה"})
        run = []
    man = W / "project_manifest.json"
    if man.exists():
        m = json.loads(man.read_text(encoding="utf-8"))
        for p in (((m.get("finish_prefs") or {}).get("motion") or {}).get("people")) or []:
            # 8.10.26 הראל: האפקט רק בתוכן שמציג מתאמנים — לא לצוות ("גם ככה מכירים אותנו")
            if p.get("team") or any(k in str(p.get("role") or "") for k in TEAM_ROLE_WORDS):
                continue
            # 8.10.26 — האפקט הקבוע לשם מתאמן: קשת + נצנצים + צליל (name_reveal נשאר למונח/כותרת מקצועית)
            cands.append({"type": "name_sparkle", "name": p.get("name"), "role": p.get("role"),
                          "why": "אדם מוצהר במניפסט — שם על המסך בכניסה הראשונה (facts עם source); צליל sparkle אוטומטי"})
    out = {"candidates": cands, "n_words": len(words)}
    (W / "motion_candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out

# ─────────────────────────── הכל ───────────────────────────

# ─────────────────────────── הכנסת קטע (name_sparkle insert) ───────────────────────────
# הראל 8.10.26: "חשוב שהפריים עומד במקום שהוא לא יפסיק לדבר. זה אמור לא להיות בתור בירול לסרטון
# אלא כמין קטע נוסף כזה בין הקטעים". ⇒ הסרטון *עוצר*: בנקודה T נכנס קטע של `hold` שניות (ברירת מחדל
# 2.6) — הפריים המחייך קפוא, אודיו שקט (+ צליל sparkle; המוזיקה נכנסת אחר כך מעל הכל), ואז הסרטון
# ממשיך בדיוק מ-T. כל מה שאחרי T זז ב-hold: אירועי MG, מילים (words_after_mg.json לכתוביות/שערים).
INSERT_HOLD = 2.6
TIME_KEYS = {"start", "end", "at", "freeze_at", "rise_at", "kicker_at", "title_at"}


def _shift(obj, T: float, D: float):
    """מזיז כל זמן ≥T ב-D, רקורסיבית באירוע (at/start/end/*_times/sfx/suppress_captions/...)."""
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k in ("freeze_src", "freeze_pick", "zoom_origin"):
                continue
            if k in TIME_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool):
                obj[k] = round(v + D, 3) if v >= T - 1e-6 else v
            elif (k.endswith("_times") or k == "suppress_captions") and isinstance(v, list):
                obj[k] = [round(x + D, 3) if isinstance(x, (int, float)) and x >= T - 1e-6 else x for x in v]
            elif isinstance(v, (dict, list)):
                _shift(v, T, D)
    elif isinstance(obj, list):
        for x in obj:
            _shift(x, T, D)


def plan_inserts(plan: dict) -> list[dict]:
    """אירועי name_sparkle עם פריים קפוא ו-insert (ברירת מחדל) ⇒ [{id, at, dur, frame}] לפי סדר."""
    out = []
    for ev in plan["events"]:
        if ev.get("type") == "name_sparkle" and ev.get("insert", True) and ev.get("freeze_src") \
                and isinstance(ev.get("freeze_at"), (int, float)):
            out.append({"id": ev["id"], "at": float(ev["start"]), "dur": float(ev.get("hold") or INSERT_HOLD),
                        "frame": float(ev["freeze_at"])})
    return sorted(out, key=lambda x: x["at"])


def remap_for_inserts(plan: dict, inserts: list[dict]) -> None:
    """מעדכן את התוכנית לציר שאחרי ההכנסות (מהאחרונה לראשונה כדי שהזמנים המקוריים יישארו נכונים)."""
    by_id = {e["id"]: e for e in plan["events"]}
    for ins in sorted(inserts, key=lambda x: -x["at"]):
        T, D = ins["at"], ins["dur"]
        for ev in plan["events"]:
            if ev["id"] != ins["id"]:
                _shift(ev, T, D)
        _shift(plan.get("base_windows") or [], T, D)
        ev = by_id[ins["id"]]
        ev["end"] = round(T + D, 3)
        ev["freeze_at"] = round(T + D / 2, 3)         # בבסיס החדש הפריים הקפוא יושב בתוך הקטע
        for x in ev.get("sfx") or []:
            x["at"] = round(T + max(0.0, float(x["at"]) - T), 3)
    plan["duration"] = round(float(plan["duration"]) + sum(i["dur"] for i in inserts), 3)
    # ins["at"] מתייחס לציר המקורי; בציר החדש הקטע ה-k מתחיל ב-at + סכום הקודמים
    acc = 0.0
    for ins in inserts:
        ins["at_new"] = round(ins["at"] + acc, 3)
        acc += ins["dur"]


def shift_words(words: list[dict], inserts: list[dict]) -> list[dict]:
    out = []
    for w in words:
        w = dict(w)
        add = sum(i["dur"] for i in inserts if float(w.get("start", 0)) >= i["at"] - 0.01)
        if add:
            w["start"] = round(float(w["start"]) + add, 3)
            w["end"] = round(float(w["end"]) + add, 3)
        out.append(w)
    return out


def build_insert_base(base: Path, inserts: list[dict], out: Path, lossless=False) -> Path:
    """בסיס חדש: הסרטון נעצר ב-T, הפריים המחייך מוחזק dur שניות (באותו YUV — בלי סבב RGB), אודיו
    שקט בקטע, וממשיך מ-T. graph אחד, בלי seek על קלטים (FFMPEG-STALL)."""
    r = sh([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
            "-of", "csv=p=0", base])
    _fr = ((r.stdout.strip().splitlines() or ["30/1"])[0]).strip().strip(",") or "30/1"
    num, _, den = _fr.partition("/")
    try:
        fps = float(num) / float(den or 1)
    except ValueError:
        fps = 30.0
    if not (1 < fps < 241):
        fps = 30.0
    cuts = [0.0] + [i["at"] for i in inserts] + [None]
    n = len(inserts)
    vf = f"[0:v]split={2 * n + 1}" + "".join(f"[s{k}]" for k in range(2 * n + 1)) + ";"
    af = f"[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit={n + 1}" + "".join(f"[q{k}]" for k in range(n + 1)) + ";"
    vparts, aparts = [], []
    for k in range(n + 1):
        a0, a1 = cuts[k], cuts[k + 1]
        tr = f"start={a0:.4f}" + (f":end={a1:.4f}" if a1 is not None else "")
        vf += f"[s{2 * k}]trim={tr},setpts=PTS-STARTPTS[v{k}];"
        af += f"[q{k}]atrim={tr},asetpts=PTS-STARTPTS[a{k}];"
        vparts.append(f"[v{k}]"); aparts.append(f"[a{k}]")
        if k < n:
            ins = inserts[k]
            nfr = max(1, int(round(ins["dur"] * fps)))
            # לפי זמן ולא לפי מספר פריים: בסיס VFR (איתי 3620/121) ⇒ אינדקס פריים ≠ זמן, והפריים בבסיס
            # היה שונה מה-freeze_src של השכבה (נראה פריים אחד לפני החיתוך). trim=start תואם ל-ffmpeg -ss.
            vf += (f"[s{2 * k + 1}]trim=start={ins['frame']:.4f},setpts=PTS-STARTPTS,trim=end_frame=1,"
                   f"loop=loop={nfr - 1}:size=1:start=0,setpts=N/({fps:.6f}*TB)[f{k}];")
            af += f"anullsrc=r=48000:cl=stereo,atrim=duration={ins['dur']:.4f}[z{k}];"
            vparts.append(f"[f{k}]"); aparts.append(f"[z{k}]")
    segs = "".join(v + a for v, a in zip(vparts, aparts))
    fc = vf + af + f"{segs}concat=n={len(vparts)}:v=1:a=1[v][a]"
    bc = base_color(base)
    tags = []
    for opt, key in (("-colorspace", "color_space"), ("-color_trc", "color_transfer"),
                     ("-color_primaries", "color_primaries"), ("-color_range", "color_range")):
        if bc.get(key) and bc[key] != "unknown":
            tags += [opt, bc[key]]
    venc = (["-c:v", "ffv1", "-level", "3"] if lossless else
            ["-c:v", "libx264", "-crf", "12", "-preset", "medium", "-pix_fmt", "yuv420p"]) + tags
    cmd = [FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-i", base, "-filter_complex", fc,
           "-map", "[v]", "-map", "[a]", "-r", f"{fps:.6f}", *venc, "-c:a", "pcm_s16le" if lossless else "aac",
           *([] if lossless else ["-b:a", "320k"]), out]
    rr = sh(cmd, timeout=3600)
    if rr.returncode != 0:
        raise RuntimeError("insert base: " + rr.stderr[-600:])
    return out


def apply_inserts(W: Path, plan: dict, base: Path, lossless=False) -> tuple[Path, list[dict]]:
    inserts = plan_inserts(plan)
    if not inserts:
        return base, []
    nb = build_insert_base(base, inserts, W / ("_insert_base.mkv" if lossless else "_insert_base.mp4"), lossless)
    remap_for_inserts(plan, inserts)
    (W / "words_after_mg.json").write_text(json.dumps(shift_words(load_words(W), inserts), ensure_ascii=False,
                                                      indent=1), encoding="utf-8")
    return nb, inserts


def run_all(W: Path, base: Path, out: Path, plan_path=None, workers=6, lossless=False) -> dict:
    plan = load_plan(W, plan_path)
    rep = {"plan": plan["_path"], "plan_sha": sha(Path(plan["_path"])), "base": str(base), "gates": []}
    rep["gates"] += check(W, plan)
    blocking = lambda: [g for g in rep["gates"] if g["level"] == "blocking" and not g["ok"]]  # noqa: E731

    def done(ok):
        rep["ok"] = ok
        (W / "MOTION_REPORT.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        return rep
    if blocking():
        return done(False)
    D = ffdur(base)
    rep["zones"] = resolve_zones(base, plan, dur=D)
    rep["freezes"] = attach_freezes(plan, base, load_words(W))
    orig_base = base
    base, inserts = apply_inserts(W, plan, base, lossless)
    if inserts:
        D = ffdur(base)
        rep["inserts"] = [{k: i[k] for k in ("id", "at", "at_new", "dur", "frame")} for i in inserts]
        rep["words_after"] = "words_after_mg.json"
    html = compose(plan, W / "motion_comp.html")
    m, gs = measure(html, W / "motion_measure.json")
    rep["gates"] += gs
    if not blocking():
        rep["gates"].append(gate_faces(base, plan, m, dur=D))
    if blocking():
        return done(False)
    layer, info = render_layer(W, plan, workers, html=html)
    rep["render"] = info
    rep["composite"] = composite(base, layer, out, plan, lossless=lossless)
    rep["gates"].append(gate("MG8_duration", rep["composite"]["dur_ok"], "blocking",
                             f"{rep['composite']['dur_out']}ש מול צפוי {rep['composite']['dur_expected']}ש"))
    rep["gates"].append(gate_color(orig_base, out))
    rep["sheet"] = sheet(out, plan, W / "MG_SHEET.jpg").name
    rep["suppress_captions"] = suppress_windows(plan)
    rep["events"] = [{"id": e["id"], "type": e["type"], "start": e["start"], "end": e["end"], "zone": e.get("zone")}
                     for e in plan["events"]]
    return done(not blocking())


def main() -> int:
    ap = argparse.ArgumentParser(description="שכבת Motion Graphics — R.E.L")
    ap.add_argument("cmd", choices=("propose", "check", "compose", "measure", "snap", "render", "composite", "sheet", "all"))
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--plan")
    ap.add_argument("--base")
    ap.add_argument("--out")
    ap.add_argument("--at", help="snap: זמנים מופרדים בפסיק")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--lossless", action="store_true")
    a = ap.parse_args()
    W = Path(a.workdir).expanduser()
    mark = lambda g: ("⚠" if g.get("measured") is False else "✓") if g["ok"] else ("✗" if g["level"] == "blocking" else "⚠")  # noqa: E731
    if a.cmd == "propose":
        print(json.dumps(propose(W), ensure_ascii=False, indent=1)); return 0
    plan = load_plan(W, a.plan)
    if a.cmd == "check":
        gs = check(W, plan)
        for g in gs:
            print(mark(g), g["gate"], "—", g["detail"])
        return 0 if all(g["ok"] or g["level"] != "blocking" for g in gs) else 1
    if a.base:
        resolve_zones(Path(a.base), plan)
    if a.cmd == "compose":
        print(compose(plan, W / "motion_comp.html")); return 0
    if a.cmd == "measure":
        m, gs = measure(compose(plan, W / "motion_comp.html"), W / "motion_measure.json")
        if a.base:
            gs.append(gate_faces(Path(a.base), plan, m))
        for g in gs:
            print(mark(g), g["gate"], "—", g["detail"][:300])
        return 0 if all(g["ok"] or g["level"] != "blocking" for g in gs) else 1
    if a.cmd == "snap":
        ts = [float(x) for x in (a.at or "1").split(",")]
        print(snaps(W, plan, ts, Path(a.base) if a.base else None)); return 0
    if a.cmd == "render":
        _, info = render_layer(W, plan, a.workers); print(json.dumps(info, ensure_ascii=False)); return 0
    if a.cmd == "composite":
        print(json.dumps(composite(Path(a.base), W / "MG_LAYER.mov", Path(a.out), plan, a.lossless), ensure_ascii=False)); return 0
    if a.cmd == "sheet":
        print(sheet(Path(a.base), plan, W / "MG_SHEET.jpg")); return 0
    if not a.base or not a.out:
        ap.error("all דורש --base ו---out")
    rep = run_all(W, Path(a.base), Path(a.out), a.plan, a.workers, a.lossless)
    for g in rep["gates"]:
        print(mark(g), g["gate"], "—", g["detail"][:200])
    if rep.get("zones"):
        print("zones:", " · ".join(rep["zones"]))
    if rep.get("render"):
        print("render:", {k: rep["render"][k] for k in ("frames", "rendered", "secs")}, "· composite:", rep["composite"])
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
