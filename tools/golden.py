#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
golden.py — Golden Set + Regression (v7): מקבע התנהגות edl_build ובודק כל שינוי policy.
=====================================================================================
build: לוכד fixtures מפרויקטים אמיתיים (words + loose script + expected edl) —
       בלי מדיה כבדה, רק JSON קטן. expected = פלט edl_build עם ה-policy הנוכחי
       ברגע הלכידה.
run:   מריץ edl_build על כל fixture עם policy נתון (ברירת מחדל: הנוכחי) ומשווה
       ל-expected: false cuts (חדשים), restored/missed (נעלמו), שינוי משך.
       exit 0 = PASS (אין סטייה מעבר לטולרנס) · 1 = FAIL.

שימוש:
  python3 golden.py build --projects "שינה-והתאוששות" "טיפ-אחד-HSPU" ...
  python3 golden.py run [--policy candidate.json] [--json]
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSDIR = HERE.parent
from relvid.paths import work_root as _work_root   # v8.6 (P0-11)
WORK = _work_root()
GOLDEN = SYSDIR / "golden"

EPS = 0.25            # טולרנס גבולות (ש)
MAX_DUR_DELTA = 1.5   # סטיית kept_dur מותרת (ש)


def sh(cmd, timeout=300):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                          timeout=timeout)


def active_cuts(edl):
    cuts = edl.get("auto_cuts", [])
    return sorted([(round(c["start"], 2), round(c["end"], 2)) for c in cuts])


def run_edl_build(words, out_dir, end, policy, loose=None):
    cmd = ["python3", HERE / "edl_build.py", "--words", words, "--out-dir", out_dir,
           "--end", f"{end:.2f}", "--policy", policy]
    if loose:
        cmd += ["--loose-script", loose]
    return sh(cmd)


def cmd_build(a):
    GOLDEN.mkdir(exist_ok=True)
    manifest = {"created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "policy_at_capture": json.loads((HERE / "edl-policy.json").read_text(encoding="utf-8")).get("version"),
                "cases": []}
    for name in a.projects:
        d = WORK / name
        wsrc = next((d / c for c in ("whisper_raw.json",) if (d / c).exists()), None)
        edl = d / "edl.json"
        if not wsrc or not edl.exists():
            print(f"⚠️ מדלג על {name} — חסר whisper_raw/edl")
            continue
        case_dir = GOLDEN / name
        case_dir.mkdir(exist_ok=True)
        shutil.copy2(wsrc, case_dir / "words.json")
        e = json.loads(edl.read_text(encoding="utf-8"))
        end = float(e.get("total_dur") or 0)
        loose = None
        for c in ("loose_script.txt", "script.txt"):
            if (d / c).exists():
                shutil.copy2(d / c, case_dir / c)
                loose = c
                break
        # expected: ריצה טרייה עם ה-policy הנוכחי (לא ה-edl הערוך של הראל —
        # הרגרסיה בודקת את *המכונה*, לא את העריכה הידנית)
        with tempfile.TemporaryDirectory() as td:
            r = run_edl_build(case_dir / "words.json", td, end,
                              HERE / "edl-policy.json",
                              (case_dir / loose) if loose else None)
            if r.returncode != 0:
                print(f"❌ edl_build נכשל על {name}: {r.stderr[-200:]}")
                continue
            shutil.copy2(Path(td) / "edl.json", case_dir / "expected_edl.json")
        manifest["cases"].append({"name": name, "end": end, "loose": loose,
                                  "content_type": (json.loads((d / "APPROVAL.json").read_text(encoding="utf-8")).get("content_type")
                                                   if (d / "APPROVAL.json").exists() else None)})
        print(f"✅ נלכד: {name} ({end:.1f}ש)")
    (GOLDEN / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Golden Set: {len(manifest['cases'])} cases → {GOLDEN}")


def compare(expected, got):
    ea, ga = active_cuts(expected), active_cuts(got)
    def match(c, pool):
        return any(abs(c[0] - p[0]) <= EPS and abs(c[1] - p[1]) <= EPS for p in pool)
    false_cuts = [c for c in ga if not match(c, ea)]
    missed = [c for c in ea if not match(c, ga)]
    d_kept = abs(float(got.get("kept_dur") or 0) - float(expected.get("kept_dur") or 0))
    return {"false_cuts": false_cuts, "missed_cuts": missed,
            "kept_dur_delta": round(d_kept, 2),
            "pass": not false_cuts and not missed and d_kept <= MAX_DUR_DELTA}


def cmd_run(a):
    manifest = json.loads((GOLDEN / "manifest.json").read_text(encoding="utf-8"))
    policy = a.policy or str(HERE / "edl-policy.json")
    results, ok = [], True
    for case in manifest["cases"]:
        cd = GOLDEN / case["name"]
        expected = json.loads((cd / "expected_edl.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            r = run_edl_build(cd / "words.json", td, case["end"], policy,
                              (cd / case["loose"]) if case.get("loose") else None)
            if r.returncode != 0:
                results.append({"case": case["name"], "pass": False,
                                "error": r.stderr[-200:]})
                ok = False
                continue
            got = json.loads((Path(td) / "edl.json").read_text(encoding="utf-8"))
        cmp = compare(expected, got)
        # שינוי policy *מרכך* (פחות חיתוכים) הוא צפוי — missed_cuts קטן מותר
        # כשבודקים candidate שונה מה-policy המקורי; false cuts לעולם לא.
        if a.policy and not cmp["pass"] and not cmp["false_cuts"] \
                and len(cmp["missed_cuts"]) <= a.allow_missed \
                and cmp["kept_dur_delta"] <= MAX_DUR_DELTA + a.allow_missed * 1.0:
            cmp["pass"] = True
            cmp["note"] = f"ריכוך צפוי: {len(cmp['missed_cuts'])} cuts ירדו"
        results.append({"case": case["name"], **cmp})
        ok = ok and cmp["pass"]
    out = {"ok": ok, "policy": policy, "cases": results}
    if not a.json:
        for r in results:
            print(f"{'✅' if r['pass'] else '❌'} {r['case']}: "
                  f"false={len(r.get('false_cuts', []))} missed={len(r.get('missed_cuts', []))} "
                  f"Δkept={r.get('kept_dur_delta')} {r.get('note', '')}")
    print(json.dumps(out if a.json else {"ok": ok}, ensure_ascii=False))
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--projects", nargs="+", required=True)
    r = sub.add_parser("run")
    r.add_argument("--policy")
    r.add_argument("--json", action="store_true")
    r.add_argument("--allow-missed", type=int, default=3,
                   help="כמה cuts שירדו מותר ל-candidate מרכך (false cuts לעולם 0)")
    a = ap.parse_args()
    if a.cmd == "build":
        cmd_build(a)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
