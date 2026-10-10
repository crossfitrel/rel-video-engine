#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
claude_start.py — פתיחת סשן זולה: כל מה שקלאוד צריך לדעת בכ-30 שורות (v9.30-eff)
==========================================================================
נמדד 22.9.26: פתיחת סשן על המערכת טענה את הסקיל המותקן (112KB) + את המאסטר מהדיסק
(147KB) + CHANGELOG (179KB, לפעמים) + handoffs — עשרות אלפי טוקנים לפני שנעשה משהו.
הכלי הזה מחליף את הקריאה הזו בתמונת מצב אחת:

  • גרסה נוכחית (הכותרת העליונה של CHANGELOG — בלי לקרוא את הקובץ)
  • בריאות: מ-handoff/.baseline/last.json אם טרי (<12ש), אחרת doctor מהיר
  • תור "מה עכשיו" מאפליקציית הרוויו (/api/next) + כמה ממתין לקלאוד
  • צ'אטים מקבילים: תביעות + קבצים/גיבויים שנערכו ב-45 הדק' האחרונות
  • חבילת הסקיל: dist תואם למאסטר? העותק המותקן במק תואם?
  • handoffs פתוחים מהשבוע האחרון (שם + כותרת)

  ~/.rel-whisper/bin/python tools/claude_start.py [--json]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(HERE))
PY = str(Path.home() / ".rel-whisper" / "bin" / "python")
if not Path(PY).exists():
    PY = sys.executable


def version() -> str:
    try:
        with open(PROJECT / "CHANGELOG.md", encoding="utf-8") as f:
            for line in f:
                if line.startswith("## v"):
                    return line[3:].strip()[:110]
    except OSError:
        pass
    return "?"


def health() -> list[str]:
    last = PROJECT / "handoff" / ".baseline" / "last.json"
    if last.exists() and time.time() - last.stat().st_mtime < 12 * 3600:
        b = json.loads(last.read_text(encoding="utf-8"))
        t, d = b.get("tests") or {}, b.get("doctor") or {}
        age = int((time.time() - last.stat().st_mtime) / 60)
        s = [f"בריאות (baseline לפני {age} דק'): unittest {t.get('ran', '?')}/{len(t.get('fails', []))} FAIL · "
             f"doctor {len(d.get('fail', []))} FAIL/{len(d.get('warn', []))} WARN · {b.get('gates', {}).get('line', '')[:60]}"]
        s += [f"   ❌ {x}: {d.get('detail', {}).get(x, '')[:110]}" for x in d.get("fail", [])]
        return s
    try:
        p = subprocess.run([PY, str(HERE / "system_doctor.py"), "--json"], cwd=PROJECT,
                           capture_output=True, text=True, timeout=120)
        d = json.loads(p.stdout[p.stdout.index("{"):])
        fails = [c for c in d["checks"] if c["status"] == "FAIL"]
        s = [f"בריאות (doctor עכשיו; אין baseline טרי): {d['fails']} FAIL · {d['warns']} WARN"]
        s += [f"   ❌ {c['check']}: {c['detail'][:110]}" for c in fails]
        return s
    except Exception as e:
        return [f"בריאות: doctor לא רץ ({e})"]


def queue() -> list[str]:
    try:
        with urllib.request.urlopen("http://127.0.0.1:5112/api/next", timeout=4) as r:
            rows = json.loads(r.read().decode("utf-8"))
    except Exception:
        return ["תור: אפליקציית הרוויו לא עונה (launchctl kickstart -k gui/$(id -u)/com.rel.review-app)"]
    mine = [r for r in rows if r.get("owner") == "claude"]
    s = [f"תור 'מה עכשיו': {len(rows)} פריטים · {len(mine)} ממתינים לקלאוד"]
    for r in (mine + [r for r in rows if r.get("owner") != "claude"])[:8]:
        who = "🤖" if r.get("owner") == "claude" else "👤"
        s.append(f"   {who} {r.get('planned_date') or '—':10} {r['project'][:34]:34} {r.get('action', '')[:40]}")
    return s


def parallel() -> list[str]:
    try:
        import work_claim as WC
        with WC.locked() as data:
            claims = list(data["claims"])
        act = WC.active(45)
    except Exception as e:
        return [f"צ'אטים מקבילים: לא נבדק ({e})"]
    s = []
    for c in claims:
        s.append(f"   ⛔ «{c['by']}» תובע {c['file']}")
    for t, fs in act["backup_tags"].items():
        s.append(f"   ⚠️ גיבויי .bak-{t} נוצרו עכשיו: {', '.join(sorted(set(fs))[:5])}")
    return (["צ'אטים מקבילים — לתאם לפני עריכה של הקבצים האלה:"] + s) if s else \
        ["צ'אטים מקבילים: אין תביעות ואין גיבויים טריים"]


def skill() -> list[str]:
    out = []
    for args in (["check"], ["installed"]):
        try:
            p = subprocess.run([PY, str(HERE / "skill_pack.py"), *args], cwd=PROJECT,
                               capture_output=True, text=True, timeout=60)
            first = (p.stdout.strip().splitlines() or ["?"])[0]
            out.append(first[:150])
        except Exception as e:
            out.append(f"{args[0]}: {e}")
    return ["חבילת הסקיל: " + " · ".join(out)]


def handoffs() -> list[str]:
    d = PROJECT / "handoff"
    fresh = sorted((p for p in d.glob("*.md") if time.time() - p.stat().st_mtime < 7 * 86400),
                   key=lambda p: -p.stat().st_mtime)
    s = []
    for p in fresh[:5]:
        head = next((ln.strip("# ").strip() for ln in p.read_text(encoding="utf-8").splitlines()
                     if ln.startswith("#")), "")
        s.append(f"   handoff/{p.name} — {head[:70]}")
    return (["handoffs מהשבוע (לקרוא רק את הרלוונטי):"] + s) if s else []


def main() -> int:
    parts = [[f"מערכת עריכת הסושיאל · {version()}"], health(), queue(), parallel(), skill(), handoffs()]
    if "--json" in sys.argv:
        print(json.dumps({"lines": [ln for p in parts for ln in p]}, ensure_ascii=False, indent=1))
    else:
        print("\n".join(ln for p in parts for ln in p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
