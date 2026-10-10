#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
baseline.py — baseline/אימות של כל המערכת בפקודה אחת, בפלט קצר (v9.30-eff, 22.9.26)
================================================================================
כל גל עבודה מתחיל ונגמר בארבע פקודות (unittest · system_doctor · gate_registry
--audit · lesson_registry --audit). נמדד 22.9.26: unittest לבדו 113ש סדרתי, ופלט
של 30KB שרובו ResourceWarning — כל הדבקה שלו לצ'אט עולה אלפי טוקנים בלי מידע.

מה זה עושה:
  • מריץ את קובצי הבדיקה במקביל (מודול לתהליך, --jobs, ברירת מחדל 4) בלי אזהרות.
  • מריץ doctor --json + שני ה-audits + skill_pack check.
  • מדפיס ≤15 שורות: מספרים, שמות מה שנכשל, ו**דיף מול הריצה הקודמת**
    (בדיקה שנשברה/תוקנה, WARN/FAIL חדש) — כך רואים מה *אתה* שברת, לא את החוב הישן.
  • שומר handoff/.baseline/last.json (+ prev.json) — claude_start.py קורא ממנו.

  ~/.rel-whisper/bin/python tools/baseline.py [--jobs 4] [--no-tests] [--json] [--serial]
exit 0 = אין כשל חדש מול הריצה הקודמת (כשל ותיק לא מפיל) · 1 = נשבר משהו חדש.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
TESTS = PROJECT / "tests"
STORE = PROJECT / "handoff" / ".baseline"
PY = str(Path.home() / ".rel-whisper" / "bin" / "python")
if not Path(PY).exists():
    PY = sys.executable

ENV = dict(os.environ, PYTHONWARNINGS="ignore", PYTHONDONTWRITEBYTECODE="1")
FAIL_LINE = re.compile(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)", re.M)
RAN = re.compile(r"^Ran (\d+) tests? in ([\d.]+)s", re.M)


def run(cmd: list[str], timeout: int = 900) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=PROJECT, env=ENV, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT {timeout}s: {' '.join(cmd)}"


def test_module(mod: str) -> dict:
    t0 = time.time()
    code, out = run([PY, "-m", "unittest", "discover", "-s", str(TESTS), "-p", mod])
    m = RAN.search(out)
    fails = [b for _k, _a, b in FAIL_LINE.findall(out)]
    if code != 0 and not fails and "NO TESTS RAN" not in out:   # קריסת import / טיימאאוט — כשל
        #   (מודול בלי בדיקות מחזיר exit 5 ב-3.12 — לא כשל; כך גם ב-discover הסדרתי)
        fails = [f"{mod}:crash"]
    return {"mod": mod, "ran": int(m.group(1)) if m else 0, "fails": fails,
            "secs": round(time.time() - t0, 1), "tail": out[-600:] if fails else ""}


def run_tests(jobs: int, serial: bool) -> dict:
    t0 = time.time()
    if serial:
        code, out = run([PY, "-m", "unittest", "discover", "-s", str(TESTS)], timeout=1800)
        m = RAN.search(out)
        fails = sorted(b for _k, _a, b in FAIL_LINE.findall(out))
        return {"ran": int(m.group(1)) if m else 0, "fails": fails, "secs": round(time.time() - t0, 1),
                "mode": "serial", "slowest": []}
    mods = sorted(p.name for p in TESTS.glob("test_*.py"))
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        res = list(ex.map(test_module, mods))
    return {"ran": sum(r["ran"] for r in res), "fails": sorted(f for r in res for f in r["fails"]),
            "secs": round(time.time() - t0, 1), "mode": f"parallel×{jobs}",
            "slowest": [(r["mod"], r["secs"]) for r in sorted(res, key=lambda r: -r["secs"])[:3]],
            "fail_tails": {r["mod"]: r["tail"] for r in res if r["fails"]}}


def doctor() -> dict:
    _code, out = run([PY, str(HERE / "system_doctor.py"), "--json"], timeout=300)
    try:
        d = json.loads(out[out.index("{"):])
    except Exception:
        return {"error": out[-300:]}
    return {"fail": sorted(c["check"] for c in d["checks"] if c["status"] == "FAIL"),
            "warn": sorted(c["check"] for c in d["checks"] if c["status"] == "WARN"),
            "pass": sum(c["status"] == "PASS" for c in d["checks"]),
            "detail": {c["check"]: c["detail"][:160] for c in d["checks"] if c["status"] != "PASS"}}


def one_line(cmd: list[str]) -> dict:
    code, out = run(cmd, timeout=300)
    last = [ln for ln in out.strip().splitlines() if ln.strip()][-1:] or [""]
    return {"ok": code == 0, "line": last[0][:160]}


def diff(prev: dict, cur: dict) -> list[str]:
    out = []
    pt, ct = set((prev.get("tests") or {}).get("fails", [])), set((cur.get("tests") or {}).get("fails", []))
    if cur.get("tests") and prev.get("tests"):
        for f in sorted(ct - pt):
            out.append(f"🆕❌ בדיקה נשברה: {f}")
        for f in sorted(pt - ct):
            out.append(f"✅ בדיקה תוקנה: {f}")
        dn = cur["tests"]["ran"] - prev["tests"]["ran"]
        if dn:
            out.append(f"Δ בדיקות: {dn:+d}")
    for lvl in ("fail", "warn"):
        p, c = set((prev.get("doctor") or {}).get(lvl, [])), set((cur.get("doctor") or {}).get(lvl, []))
        for x in sorted(c - p):
            out.append(f"🆕{'❌' if lvl == 'fail' else '⚠️'} doctor: {x}")
        for x in sorted(p - c):
            out.append(f"✅ doctor נפתר: {x}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--no-tests", action="store_true")
    ap.add_argument("--serial", action="store_true", help="כמו unittest discover המקורי (להשוואה)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    t0 = time.time()
    cur = {"at": time.strftime("%Y-%m-%d %H:%M"), "tests": None}
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_doc = ex.submit(doctor)
        f_g = ex.submit(one_line, [PY, str(HERE / "gate_registry.py"), "--audit"])
        f_l = ex.submit(one_line, [PY, str(HERE / "lesson_registry.py"), "--audit"])
        f_s = ex.submit(one_line, [PY, str(HERE / "skill_pack.py"), "check"])
        if not a.no_tests:
            cur["tests"] = run_tests(a.jobs, a.serial)
        cur["doctor"], cur["gates"], cur["lessons"], cur["skill_pack"] = (
            f_doc.result(), f_g.result(), f_l.result(), f_s.result())
    cur["secs"] = round(time.time() - t0, 1)

    STORE.mkdir(parents=True, exist_ok=True)
    last = STORE / "last.json"
    prev = json.loads(last.read_text(encoding="utf-8")) if last.exists() else {}
    if prev and (not a.no_tests or prev.get("tests") is None):
        (STORE / "prev.json").write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.no_tests and prev.get("tests"):
        cur["tests_from"] = prev.get("at")
        cur["tests"] = prev["tests"]
    last.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    changes = diff(prev, cur) if prev else ["(ריצה ראשונה — אין השוואה)"]

    if a.json:
        print(json.dumps(dict(cur, changes=changes), ensure_ascii=False, indent=1))
    else:
        t, d = cur["tests"], cur["doctor"]
        if t:
            src = f" (מ-{cur['tests_from']})" if cur.get("tests_from") else f" · {t['secs']}ש {t['mode']}"
            print(f"{'✅' if not t['fails'] else '❌'} unittest: {t['ran']} · {len(t['fails'])} FAIL{src}")
            for f in t["fails"][:6]:
                print(f"   ❌ {f}")
        if "error" in d:
            print(f"❌ doctor לא רץ: {d['error'][:120]}")
        else:
            print(f"{'✅' if not d['fail'] else '❌'} doctor: {len(d['fail'])} FAIL · {len(d['warn'])} WARN · {d['pass']} PASS")
            for x in d["fail"]:
                print(f"   ❌ {x}: {d['detail'].get(x, '')}")
        for k, lbl in (("gates", "gates"), ("lessons", "lessons"), ("skill_pack", "skill pack")):
            print(f"{'✅' if cur[k]['ok'] else '❌'} {lbl}: {cur[k]['line']}")
        print("שינויים מהריצה הקודמת: " + (" | ".join(changes) if changes else "אין"))
        print(f"⏱ {cur['secs']}ש · handoff/.baseline/last.json")
    new_break = any(c.startswith("🆕❌") for c in changes)
    return 1 if new_break else 0


if __name__ == "__main__":
    sys.exit(main())
