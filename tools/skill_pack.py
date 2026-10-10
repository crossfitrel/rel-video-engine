#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_pack.py — בונה את חבילת הסקיל המותקנת מתוך המאסטר (v9.30-eff, 22.9.26)
==========================================================================
הבעיה שנמדדה: המאסטר `skills/rel-social-video-editor/SKILL.md` גדל ל-~100K תווים
(1,196 שורות) והמותקן בקלאוד היה v9.22 (112KB) — כל הפעלה של הסקיל טענה ~50K
טוקנים, ובנוסף הסוכן קרא את המאסטר מהדיסק (הוראות הפרויקט הפנו אליו) = טעינה
כפולה. ב-8.7.26 הסקיל כבר פוצל ל-117 שורות + references — ונסוג, כי העריכות
המשיכו במונוליט.

הפתרון: **המאסטר נשאר משטח העריכה היחיד** (כל צ'אט ממשיך להוסיף לו), והחבילה
המותקנת *נגזרת* ממנו — ליבה רזה (`CORE.md` ידני + מפת references אוטומטית) וכל
סעיף H2 של המאסטר מילה-במילה בקובץ reference. כך הפיצול לא יכול להיסוג: אין
מה לסנכרן ידנית.

שימוש (על המק, ~/.rel-whisper/bin/python או python3):
  skill_pack.py build   [--out DIR]     # dist/rel-social-video-editor/ + .skill (zip) + BUILD.json
  skill_pack.py check                   # exit 1 אם ה-dist לא תואם למאסטר/CORE (צריך build)
  skill_pack.py installed [PATH ...]    # משווה את העותק המותקן של Claude מול ה-dist
  skill_pack.py stats                   # גדלים (תווים/שורות) — מאסטר מול ליבה

אפס אובדן: `build` נכשל אם שורה לא-ריקה כלשהי מגוף המאסטר לא נמצאת באחד מקובצי
ה-reference (נבדק גם ב-tests/test_skill_pack.py).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
SKILL_NAME = "rel-social-video-editor"
SKILL_DIR = PROJECT / "skills" / SKILL_NAME
MASTER = SKILL_DIR / "SKILL.md"
CORE = SKILL_DIR / "CORE.md"
CONFIG = SKILL_DIR / "pack.json"
DIST = SKILL_DIR / "dist"
# קרוספיט אריאל/00 - REL-OS/03_SKILLS
REL_OS_SKILLS = PROJECT.parents[2] / "00 - REL-OS" / "03_SKILLS"
VIDEO_CANON = REL_OS_SKILLS / "00_META" / "VIDEO-CANON.md"
CANON_SNAPSHOT = REL_OS_SKILLS / "anthropic-skills" / SKILL_NAME / "CANON-snapshot.md"
# v10 ענן: בלי REL-OS (סשן ענן) — עותקים בריפו, מתעדכנים מהמק בכל build שרואה את המקור
if not VIDEO_CANON.exists():
    VIDEO_CANON = SKILL_DIR / "canon" / "VIDEO-CANON.md"
if not CANON_SNAPSHOT.exists():
    CANON_SNAPSHOT = SKILL_DIR / "canon" / "CANON-snapshot.md"
INSTALLED_GLOB = ("Library/Application Support/Claude/local-agent-mode-sessions/"
                  "skills-plugin/*/*/skills/" + SKILL_NAME + "/SKILL.md")

CORE_MAX_CHARS = 30000      # ≈ פחות משליש מהמאסטר; Anthropic: גוף SKILL.md < 500 שורות
CORE_MAX_LINES = 500
DESC_MAX = 1024             # מגבלת ה-frontmatter של Claude
TOC_MIN_LINES = 100         # Anthropic: קובץ reference מעל 100 שורות — תוכן עניינים בראשו


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def split_front(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        end = text.index("\n---", 4)
        return text[4:end], text[end + 4:].lstrip("\n")
    return "", text


def sections(body: str) -> list[tuple[str, str]]:
    """[(heading, text)] לפי H2 מחוץ לבלוקי קוד. מה שלפני ה-H2 הראשון = ('', …)."""
    out, cur_head, cur = [], "", []
    fence = False
    for line in body.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            out.append((cur_head, "\n".join(cur)))
            cur_head, cur = line[3:].strip(), [line]
            continue
        cur.append(line)
    out.append((cur_head, "\n".join(cur)))
    return [(h, t) for h, t in out if t.strip()]


def route(heading: str, rules: list[dict]) -> str:
    for r in rules:
        if re.search(r["match"], heading):
            return r["file"]
    return "misc.md"


def toc(text: str) -> str:
    heads = []
    fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence and re.match(r"^#{2,3} ", line):
            lvl = len(line) - len(line.lstrip("#"))
            heads.append(("  " if lvl == 3 else "") + "- " + line.lstrip("#").strip())
    if len(heads) < 2:     # בלי כותרות (היסטוריית גרסאות) — שורות הפתיחה של כל גרסה
        heads = ["- " + ln.split("**")[0].strip() for ln in text.split("\n")
                 if re.match(r"^v\d+\.\d+ — ", ln)]
    if len(heads) < 2:     # בלוק קבועים — שמות המפתחות
        keys = re.findall(r"^([A-Z][A-Z0-9_]{2,})\s+=", text, re.M)
        if len(keys) >= 2:
            heads = ["- " + " · ".join(keys)]
    if not heads:
        return ""
    return "## תוכן\n" + "\n".join(heads) + "\n\n"


def master_version(body: str) -> str:
    m = re.search(r"\*\*גרסה:\*\*\s*(v[\d.]+)\s*—\s*([\d-]+)", body)
    return f"{m.group(1)} — {m.group(2)}" if m else "unknown"


def build(out: Path = DIST, write_zip: bool = True) -> dict:
    cfg = load_config()
    master = MASTER.read_text(encoding="utf-8")
    core = CORE.read_text(encoding="utf-8")
    _front, body = split_front(master)
    version = master_version(body)
    rules = cfg["routes"]
    desc = cfg["description"].strip()
    if len(desc) > DESC_MAX:
        raise SystemExit(f"description {len(desc)} > {DESC_MAX}")

    files: dict[str, list[str]] = {}
    headings: dict[str, list[str]] = {}
    for head, text in sections(body):
        f = route(head, rules) if head else rules[0]["file"]
        files.setdefault(f, []).append(text.strip("\n"))
        headings.setdefault(f, []).append(head or "(פתיח)")

    pack = out / SKILL_NAME
    refs = pack / "references"
    if pack.exists():
        for p in sorted(pack.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
    refs.mkdir(parents=True, exist_ok=True)

    when = {r["file"]: r["when"] for r in rules}
    ref_rows, ref_text_all = [], []
    for f, parts in files.items():
        text = "\n\n".join(parts) + "\n"
        title = f"# {SKILL_NAME} · {f[:-3]}\n> נגזר מהמאסטר ({version}) ע\"י tools/skill_pack.py — לא לערוך כאן.\n\n"
        t = toc(text) if text.count("\n") > TOC_MIN_LINES else ""
        (refs / f).write_text(title + t + text, encoding="utf-8")
        ref_text_all.append(text)
        ref_rows.append((f, " · ".join(headings[f])[:120], len(text), when.get(f, "סעיף שלא מופה ב-pack.json")))

    extra = []
    if VIDEO_CANON.exists():
        (refs / "video-canon.md").write_text(VIDEO_CANON.read_text(encoding="utf-8"), encoding="utf-8")
        extra.append(("video-canon.md", "VIDEO-CANON (עותק מ-00_META)", VIDEO_CANON.stat().st_size,
                      "מחלוקת על חוק עריכה — הקאנון גובר"))
    if CANON_SNAPSHOT.exists():
        (pack / "CANON-snapshot.md").write_text(CANON_SNAPSHOT.read_text(encoding="utf-8"), encoding="utf-8")

    # אפס אובדן — כל שורה לא-ריקה מגוף המאסטר חייבת להופיע ב-references
    blob = "\n".join(ref_text_all)
    lost = [ln for ln in body.split("\n") if ln.strip() and ln not in blob]
    if lost:
        raise SystemExit(f"אובדן תוכן: {len(lost)} שורות לא נכנסו ל-references, למשל: {lost[0][:80]}")

    rows = "\n".join(f"| `references/{f}` | {w} | {h} | {n // 1000}K |"
                     for f, h, n, w in ref_rows + extra)
    stamp = (f"\n\n## מפת references (נטענים לפי צורך — אפס טוקנים עד שקוראים)\n"
             f"| קובץ | לקרוא כש… | סעיפי המאסטר | גודל |\n|---|---|---|---|\n{rows}\n\n"
             f"---\n*גרסת מערכת {version} · נבנה {time.strftime('%Y-%m-%d %H:%M')} · "
             f"master sha {sha(master)[:12]} · core sha {sha(core)[:12]}*\n")
    front = (f"---\nname: {SKILL_NAME}\ndescription: {json.dumps(desc, ensure_ascii=False)}\n---\n\n")
    skill_md = front + core.strip() + stamp
    (pack / "SKILL.md").write_text(skill_md, encoding="utf-8")

    core_body = core.strip() + stamp
    info = {
        "version": version,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "master_sha256": sha(master),
        "core_sha256": sha(core),
        "config_sha256": sha(CONFIG.read_text(encoding="utf-8")),
        "skill_md_sha256": sha(skill_md),
        "master_chars": len(master), "master_lines": master.count("\n"),
        "core_chars": len(core_body), "core_lines": core_body.count("\n"),
        "description_chars": len(desc),
        "references": {f: n for f, _h, n, _w in ref_rows + extra},
        "unmapped": headings.get("misc.md", []),
    }
    if info["core_chars"] > CORE_MAX_CHARS or info["core_lines"] > CORE_MAX_LINES:
        raise SystemExit(f"ליבה גדולה מהתקציב: {info['core_chars']} תווים / {info['core_lines']} שורות")
    (out / "BUILD.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    if write_zip:
        z = out / f"{SKILL_NAME}.skill"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(pack.rglob("*")):
                if p.is_file():
                    zf.write(p, f"{SKILL_NAME}/{p.relative_to(pack)}")
        info["zip"] = str(z)
    return info


def check() -> int:
    b = DIST / "BUILD.json"
    if not b.exists():
        print("STALE: אין dist — להריץ skill_pack.py build")
        return 1
    info = json.loads(b.read_text(encoding="utf-8"))
    stale = []
    if info["master_sha256"] != sha(MASTER.read_text(encoding="utf-8")):
        stale.append("המאסטר השתנה")
    if info["core_sha256"] != sha(CORE.read_text(encoding="utf-8")):
        stale.append("CORE.md השתנה")
    if info.get("config_sha256") != sha(CONFIG.read_text(encoding="utf-8")):
        stale.append("pack.json השתנה")
    if stale:
        print("STALE: " + " · ".join(stale) + " — להריץ skill_pack.py build ולהתקין מחדש")
        return 1
    print(f"OK: dist תואם ({info['version']}, ליבה {info['core_chars']} תווים)")
    return 0


def installed(paths: list[str]) -> int:
    b = DIST / "BUILD.json"
    if not b.exists():
        print("אין dist")
        return 1
    want = json.loads(b.read_text(encoding="utf-8"))["skill_md_sha256"]
    cands = [Path(p) for p in paths] or sorted(Path.home().glob(INSTALLED_GLOB))
    if not cands:
        print("UNKNOWN: לא נמצא עותק מותקן במק")
        return 2
    # 23.9.26: המטמון של אפליקציית הדסקטופ מתעדכן לבד ובאיחור — חבילה רזה מבנייה קודמת
    # היא LAG (לא תקלה); תקלה אמיתית = MONOLITH: מישהו התקין את המאסטר עצמו (147KB).
    bad = 0
    for p in cands:
        txt = p.read_text(encoding="utf-8")
        if sha(txt) == want:
            print(f"OK  {p.stat().st_size} bytes — זהה ל-dist")
            continue
        m = re.search(r"\*גרסת מערכת (v[\d.]+)[^·]*· נבנה ([\d-]+ [\d:]+)", txt)
        if m:
            print(f"LAG מטמון הדסקטופ על {m.group(1)} (נבנה {m.group(2)}) — מתעדכן לבד; "
                  f"המקור הקובע הוא claude.ai → Customize → Skills")
        else:
            bad += 1
            print(f"MONOLITH {p} ({p.stat().st_size} bytes) — הותקן המאסטר ולא החבילה: "
                  f"skill_pack.py build והתקנת dist/rel-social-video-editor.skill")
    return 1 if bad else 0


def stats() -> None:
    info = build(Path("/tmp") / "skill_pack_stats", write_zip=False)
    print(json.dumps({k: info[k] for k in ("version", "master_chars", "master_lines", "core_chars",
                                           "core_lines", "description_chars", "references", "unmapped")},
                     ensure_ascii=False, indent=1))


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "build":
        out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else DIST
        info = build(out)
        print(f"OK build {info['version']}: ליבה {info['core_chars']} תווים/{info['core_lines']} שורות "
              f"(מאסטר {info['master_chars']}/{info['master_lines']}) · {len(info['references'])} references"
              + (f" · ⚠️ לא ממופים: {info['unmapped']}" if info['unmapped'] else "") + f"\n→ {info.get('zip')}")
        return 0
    if cmd == "check":
        return check()
    if cmd == "installed":
        return installed(argv[2:])
    if cmd == "stats":
        stats()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
