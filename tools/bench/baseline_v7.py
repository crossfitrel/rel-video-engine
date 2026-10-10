#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""baseline_v7.py — מדידת ה-baseline של v7 לפני מיגרציית V2.

למה זה קיים: הכלל של המערכת הוא "לא מייעלים ולא מחליפים בלי מספר לפני ואחרי"
(ASR-BENCH.md). המסמך V2-ARCHITECTURE.md מגדיר 13 KPIs; הקובץ הזה מודד את אלה
שניתן למדוד מהדיסק, פעם אחת, על v7 as-is — ומקבע אותם ב-bench/baseline_v7.json.

עיקר החידוש: K1 (תיקוני גבול לסרטון) נמדד עם coalescing אמיתי. באפליקציה כל
לחיצת ±0.1ש כותבת אירוע adjust_cut נפרד, וכולם נושאים את אותו ts (נצפה: 3
אירועים ב-14:32:54 על אותו cut). ספירה גולמית מנפחת פי כמה. ההגדרה כאן:
"תיקון גבול אחד" = שרשרת מקסימלית של adjust_cut שבה from של אירוע == to של
קודמו (אותו cut, אותו פרויקט), עם דלתא נטו מחושבת מקצה לקצה.

הרצה:  python3 tools/bench/baseline_v7.py [--json] [--work WORK_ROOT]
פלט:   tools/bench/baseline_v7.json  + דוח קריא ל-stdout
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, glob
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

BURST_GAP_SEC = 90.0

# שלבי גימור שכל אחד מהם = קידוד וידאו מלא מקצה לקצה
ENCODE_STAGES = {
    "recut": "crf18 (edl_cut, per-segment)",
    "tighten": "crf18",
    "speed_fit": "crf18 (tighten שני)",
    "broll": "crf20",
    "fixed_intro": "crf18",
    "captions": "crf16",
    "deliver": "crf23",
}
# שלבים שמקודדים אודיו מחדש (דור AAC)
AAC_STAGES = {"recut": "192k", "tighten": "192k", "speed_fit": "192k",
              "fixed_intro": "256k", "music": "256k", "loudness": "256k"}


def _ts(s):
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(s)[:19], f).timestamp()
        except Exception:
            pass
    return None


def read_jsonl(p):
    out = []
    try:
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def jload(p, default=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


# ---------------------------------------------------------------- K1
def k1_boundary_adjustments(work: Path):
    """שרשור adjust_cut לתיקונים נפרדים. מחזיר גם גולמי וגם מקואלס."""
    per_project, raw_total, chains_total, noop_total = {}, 0, 0, 0
    deltas = []
    for cdir in sorted(work.glob("*/corrections.jsonl")):
        proj = cdir.parent.name
        evs = [e for e in read_jsonl(cdir) if e.get("type") == "adjust_cut"]
        raw_total += len(evs)
        # open chains: key = (round(to.start,3), round(to.end,3))
        open_chains = {}
        chains = []
        for e in evs:
            f, t = e.get("from") or {}, e.get("to") or {}
            if not f or not t:
                continue
            fk = (round(float(f.get("start", -1)), 3), round(float(f.get("end", -1)), 3))
            tk = (round(float(t.get("start", -1)), 3), round(float(t.get("end", -1)), 3))
            ts = _ts(e.get("ts")) or 0.0
            ch = open_chains.pop(fk, None)
            if ch is not None and (ts - ch["last_ts"]) <= BURST_GAP_SEC:
                ch["n"] += 1
                ch["last"] = t
                ch["last_ts"] = ts
            else:
                ch = {"first": f, "last": t, "n": 1, "first_ts": ts, "last_ts": ts}
                chains.append(ch)
            open_chains[tk] = ch
        n_noop = 0
        for ch in chains:
            ds = abs(float(ch["last"].get("start", 0)) - float(ch["first"].get("start", 0)))
            de = abs(float(ch["last"].get("end", 0)) - float(ch["first"].get("end", 0)))
            net = round(ds + de, 3)
            ch["net_delta"] = net
            if net < 0.02:
                n_noop += 1
            else:
                deltas.append(net)
        per_project[proj] = {"raw_events": len(evs), "distinct_adjustments": len(chains),
                             "noop_roundtrips": n_noop,
                             "effective": len(chains) - n_noop}
        chains_total += len(chains)
        noop_total += n_noop
    n_proj = max(1, len([p for p, v in per_project.items() if v["raw_events"]]))
    eff = chains_total - noop_total
    deltas.sort()
    return {
        "raw_events_total": raw_total,
        "distinct_adjustments_total": chains_total,
        "noop_roundtrips_total": noop_total,
        "effective_adjustments_total": eff,
        "projects_with_adjustments": n_proj,
        "raw_per_project": round(raw_total / n_proj, 1),
        "effective_per_project": round(eff / n_proj, 1),
        "inflation_factor": round(raw_total / max(1, eff), 2),
        "median_net_delta_sec": deltas[len(deltas) // 2] if deltas else None,
        "per_project": per_project,
    }


# ---------------------------------------------------------------- K2
def k2_review_rounds(work: Path):
    per, tot, n = {}, 0, 0
    for d in sorted(work.glob("*/")):
        if d.name.startswith("_"):
            continue
        cm = jload(d / "comments.json", []) or []
        rr = jload(d / "review_rounds.json", {}) or {}
        rounds_v6 = len(rr.get("rounds", [])) if isinstance(rr, dict) else 0
        harel = [c for c in cm if (c.get("actor") or "harel") == "harel"]
        if not harel and not rounds_v6:
            continue
        resolved = len([c for c in harel if c.get("status") == "resolved"])
        per[d.name] = {"harel_comments": len(harel), "resolved": resolved,
                       "open": len(harel) - resolved, "rounds_v6": rounds_v6}
        tot += max(rounds_v6, 1 if harel else 0)
        n += 1
    return {"projects_measured": n, "avg_rounds": round(tot / max(1, n), 2), "per_project": per}


# ---------------------------------------------------------------- K3/K4/K5
def k3_k4_k5_render(work: Path):
    enc, aac, secs, per = [], [], [], {}
    for fs in sorted(work.glob("*/finish_status.json")):
        d = jload(fs, {}) or {}
        tm = d.get("timings") or {}
        if not tm:
            continue
        e = [s for s in ENCODE_STAGES if s in tm]
        a = [s for s in AAC_STAGES if s in tm]
        # recut/tighten קורים גם ב-refinish דרך EXPORT_TIGHT קיים — נמנים רק אם רצו
        if "refinish" in tm:
            e = [s for s in e if s not in ("recut", "tighten", "speed_fit")]
        per[fs.parent.name] = {"encode_stages": e, "n_encodes": len(e),
                               "aac_stages": a, "n_aac_generations": len(a),
                               "refinish": "refinish" in tm}
        enc.append(len(e))
        aac.append(len(a))
    for rf in work.glob("*/runs/run_*.json"):
        d = jload(rf, {}) or {}
        if d.get("status") == "done" and d.get("total_secs"):
            secs.append(float(d["total_secs"]))
    enc.sort(); aac.sort(); secs.sort()
    med = lambda v: v[len(v) // 2] if v else None
    return {
        "K3_full_encodes": {"measured_runs": len(enc), "median": med(enc),
                            "min": min(enc) if enc else None, "max": max(enc) if enc else None,
                            "static_full_path_worst_case": 7,
                            "note": "נמדד ממה שרץ בפועל; מסלול מלא עם broll+fx+speed_fit = 7"},
        "K4_aac_generations": {"median": med(aac), "min": min(aac) if aac else None,
                               "max": max(aac) if aac else None,
                               "note": "מעל INPUT שכבר aac 128k — הדור הראשון לא נמנה כאן"},
        "K5_finish_secs": {"done_runs": len(secs), "median": med(secs),
                           "p25": secs[len(secs) // 4] if secs else None,
                           "max": max(secs) if secs else None},
        "per_project": per,
    }


# ---------------------------------------------------------------- K7
def k7_gates():
    """qa_gates.py קורא ל-gate(name, ok, detail, hard=True) — hard הוא ברירת מחדל.
    לכן שער חוסם = קריאה שאין בה hard=False. הקריאות רב-שורתיות, אז חותכים כל
    קריאה עד תחילת הקריאה הבאה ובודקים בתוך המקטע."""
    qa = (TOOLS / "qa_gates.py").read_text(encoding="utf-8")
    calls = [(m.start(), m.group(1)) for m in re.finditer(r'\bgate\(\s*["\']([A-Za-z0-9_]+)["\']', qa)]
    gates = {}
    for i, (pos, name) in enumerate(calls):
        end = calls[i + 1][0] if i + 1 < len(calls) else len(qa)
        seg = qa[pos:end]
        is_hard = "hard=False" not in seg.replace(" ", "")
        # קריאה חוזרת לאותו שער (ענף else) — hard נקבע לפי החמור מביניהם
        gates[name] = "True" if (gates.get(name) == "True" or is_hard) else "False"
    gates = list(gates.items())
    hard = [g for g, h in gates if h == "True"]
    # כלים חוצי-שער: קיימים? מופעלים בצנרת? ה-exit code נבדק? רצים לפני הקידום?
    pipe = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")
    try:
        promote_at = pipe.index("\n    PENDING.replace(FINAL)")
    except ValueError:
        promote_at = len(pipe)

    def _nocomments(src):
        out = []
        for ln in src.splitlines():
            s = ln.split("#", 1)[0]
            out.append(s)
        return "\n".join(out)

    def tool_state(name, exit_pat):
        src = _nocomments((TOOLS / f"{name}.py").read_text(encoding="utf-8"))
        can_fail = bool(re.search(exit_pat, src))
        wired = f"{name}.py" in pipe
        checked = bool(re.search(rf'blockers\.append\(f?"{name}', pipe))
        before = wired and (pipe.index(f"{name}.py") < promote_at)
        if not wired:
            return {"blocking": False, "why": "לא מחובר לצנרת"}
        if not can_fail:
            return {"blocking": False, "why": "לא מחזיר exit code שנכשל"}
        if not checked:
            return {"blocking": False, "why": "מחובר אך ה-returncode לא נבדק"}
        if not before:
            return {"blocking": False, "why": "רץ אחרי הקידום ל-FINAL"}
        return {"blocking": True, "why": "חוסם לפני הקידום"}

    tools_state = {
        "canon_lint": tool_state("canon_lint", r"sys\.exit\(1 if hard"),
        "cut_qa": tool_state("cut_qa", r"sys\.exit\(1 if blockers"),
        "caption_safety": tool_state("caption_safety", r"sys\.exit\(1 if issues"),
    }
    n_tools_block = sum(1 for v in tools_state.values() if v["blocking"])
    return {"gates_total": len(gates), "hard_blocking": len(hard),
            "hard_gate_ids": hard, "all_gates": dict(gates),
            "tool_gates": tools_state, "tool_gates_blocking": n_tools_block,
            "total_blocking_checks": len(hard) + n_tools_block,
            "gates_before_promote": promote_at < len(pipe)}


# ---------------------------------------------------------------- K9
def k9_classify_coverage(work: Path):
    try:
        import learn_from_edits as L
    except Exception as e:
        return {"error": f"import failed: {e}"}
    total = kept = 0
    dropped_types, kept_codes = {}, {}
    for cj in sorted(work.glob("*/corrections.jsonl")):
        for e in read_jsonl(cj):
            total += 1
            try:
                rc = L.classify(e)
            except Exception:
                rc = None
            if rc:
                kept += 1
                kept_codes[rc] = kept_codes.get(rc, 0) + 1
            else:
                t = e.get("type", "?")
                dropped_types[t] = dropped_types.get(t, 0) + 1
    report_only = set(getattr(L, "REPORT_ONLY", ()) or ())
    calibratable = set((getattr(L, "CAL", {}) or {}).keys())
    n_report = sum(v for k, v in kept_codes.items() if k in report_only)
    n_cal = sum(v for k, v in kept_codes.items() if k in calibratable)
    return {
        "events_total": total, "recognized": kept,
        "dropped": total - kept,
        "dropped_pct": round(100.0 * (total - kept) / max(1, total), 1),
        "recognized_report_only": n_report,
        "recognized_report_only_pct_of_recognized": round(100.0 * n_report / max(1, kept), 1),
        "recognized_calibratable": n_cal,
        "kept_codes": dict(sorted(kept_codes.items(), key=lambda x: -x[1])),
        "dropped_types": dict(sorted(dropped_types.items(), key=lambda x: -x[1])),
        "min_evidence": getattr(L, "MIN_EVIDENCE", None),
        "min_projects": getattr(L, "MIN_PROJECTS", None),
    }


# ---------------------------------------------------------------- K10
RULE_FAMILIES = {
    "silence": ["שקט"],
    "take_duplicate": ["טייק", "כפילות"],
    "filler": ["מילוי", "מילת מילוי"],
    "director_command": ["פקודת בימוי", "בימוי"],
    "fragment": ["פרגמנט", "שבר"],
    "false_start": ["התחלה כושלת", "false"],
    "take_marker": ["מילת אישור", "אישור טייק", "מרקר"],
    "visual_opening": ["פתיח ויזואלי", "פתיחה ארוכה"],
    "format_intro": ["פתיח קבוע", "מנפצים"],
}


def k10_golden_coverage():
    gdir = ROOT / "golden"
    man = jload(gdir / "manifest.json", {}) or {}
    cases = man.get("cases") or man.get("case_names") or []
    if isinstance(cases, dict):
        cases = list(cases.keys())
    fired, n_auto, n_manual = {k: 0 for k in RULE_FAMILIES}, 0, 0
    for exp in gdir.glob("*/expected_edl.json"):
        d = jload(exp, {}) or {}
        for key, cnt in (("auto_cuts", "a"), ("manual_review_cuts", "m")):
            for c in d.get(key, []) or []:
                r = str(c.get("reason") or "")
                if cnt == "a":
                    n_auto += 1
                else:
                    n_manual += 1
                for fam, kws in RULE_FAMILIES.items():
                    if any(k in r for k in kws):
                        fired[fam] += 1
    covered = [f for f, n in fired.items() if n > 0]
    return {"cases": len(list(gdir.glob("*/expected_edl.json"))),
            "policy_at_capture": man.get("policy_at_capture"),
            "auto_cuts": n_auto, "manual_cuts": n_manual,
            "families_total": len(RULE_FAMILIES), "families_fired": len(covered),
            "fired_counts": fired,
            "allow_missed_default": _allow_missed_default()}


def _allow_missed_default():
    try:
        g = (TOOLS / "golden.py").read_text(encoding="utf-8")
        m = re.search(r"allow-missed[^\n]*default\s*=\s*(\d+)", g)
        return int(m.group(1)) if m else None
    except Exception:
        return None


# ---------------------------------------------------------------- K11
MAGIC_FILES = ["edl_build.py", "tighten_finish.py", "broll_pick.py", "story_structure.py"]


def k11_magic_numbers():
    policy = jload(TOOLS / "edl-policy.json", {}) or {}
    known = set()
    for k, v in policy.items():
        if isinstance(v, (int, float)):
            known.add(round(float(v), 4))
    out, total = {}, 0
    for fn in MAGIC_FILES:
        p = TOOLS / fn
        if not p.exists():
            continue
        hits = []
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            s = ln.strip()
            if s.startswith("#") or '"""' in s:
                continue
            for m in re.finditer(r"(?<![\w.])(\d+\.\d+)(?![\w.])", s):
                val = round(float(m.group(1)), 4)
                if val in (0.0, 1.0, 2.0, 100.0) or val in known:
                    continue
                hits.append({"line": i, "value": val, "code": s[:110]})
        out[fn] = {"count": len(hits), "samples": hits[:12]}
        total += len(hits)
    dead = [k for k, v in policy.items() if not k.startswith("_") and _policy_key_dead(k)]
    return {"total_float_literals_outside_policy": total, "per_file": out,
            "policy_keys": len([k for k in policy if not k.startswith("_")]),
            "dead_policy_keys": dead}


def _policy_key_dead(key):
    try:
        r = subprocess.run(["grep", "-rl", "--include=*.py", "--include=*.html", key, str(TOOLS), str(ROOT / "review-app")],
                           capture_output=True, text=True, timeout=30)
        return not r.stdout.strip()
    except Exception:
        return False


# ---------------------------------------------------------------- K13
def k13_doc_drift():
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "consistent": bool(ok), "detail": detail})

    pipe = (TOOLS / "local_finish_pipeline.py").read_text(encoding="utf-8")
    m = re.search(r'--music-lufs["\'][^)]*default\s*=\s*(-?\d+(?:\.\d+)?)', pipe)
    # ‎-44.0 בקוד מול "‎-44" בתיעוד הוא אותו מספר — משווים מספרית, לא כמחרוזת.
    code_lufs = m.group(1) if m else None
    lufs_int = str(abs(int(float(code_lufs)))) if code_lufs else None
    for doc in ("PIPELINE.md", "AUDIO-MIX.md"):
        p = TOOLS / doc
        if p.exists():
            txt = p.read_text(encoding="utf-8")
            add(f"{doc}: music lufs", bool(lufs_int and lufs_int in txt),
                f"code={code_lufs} · מחפש '{lufs_int}' במסמך")
    tf = (TOOLS / "tighten_finish.py").read_text(encoding="utf-8")
    # ‎default יכול להיות מספר או מחרוזת (‎default="-40") — שני המקרים תקפים.
    m2 = re.search(r'--noise["\'][^)]*default\s*=\s*["\']?(-?\d+)', tf)
    noise = m2.group(1) if m2 else None
    add("tighten noise: code vs inline comment", bool(noise and f"{noise}dB" in tf),
        f"code={noise}dB · המסמך/ההערה חייבים לנקוב באותו מספר")
    sk = ROOT / "skills" / "rel-social-video-editor" / "SKILL.md"
    if sk.exists():
        t = sk.read_text(encoding="utf-8")
        add("SKILL: stale 1.5s audio gate string absent", "≥1.5ש" not in t, "gate בפועל 0.6ש")
    am = TOOLS / "AUDIO-MIX.md"
    if am.exists():
        t = am.read_text(encoding="utf-8")
        add("AUDIO-MIX: does not claim Descript owns the mix",
            "Descript" not in t.split("\n\n")[0], "השורה הראשונה טוענת שהמיקס ב-Descript")
    tst = ROOT / "TESTING.md"
    if tst.exists():
        t = tst.read_text(encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                               cwd=str(ROOT), capture_output=True, text=True, timeout=300)
            n = re.search(r"Ran (\d+) tests", (r.stderr or "") + (r.stdout or ""))
            actual = n.group(1) if n else "?"
        except Exception:
            actual = "?"
        add("TESTING.md unit-test count", f"{actual} בדיקות" in t or f"{actual} tests" in t,
            f"actual={actual}")
    bad = [c["check"] for c in checks if not c["consistent"]]
    return {"checks": checks, "inconsistent": len(bad), "inconsistent_list": bad}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=None, help="נתיב _work (ברירת מחדל: מהקונפיג/ROOT/_work)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=str(HERE / "baseline_v7.json"))
    a = ap.parse_args()

    work = Path(a.work) if a.work else None
    if work is None:
        try:
            sys.path.insert(0, str(TOOLS))
            from relvid.paths import work_root  # type: ignore
            work = Path(work_root())
        except Exception:
            work = ROOT / "_work"
    if not work.exists():
        print(f"[!] אין תיקיית עבודה: {work}", file=sys.stderr)
        sys.exit(2)

    res = {
        "measured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "work_root": str(work),
        "system_version": "v7.11",
        "projects_in_work": len([d for d in work.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))]),
        "K1_boundary_adjustments": k1_boundary_adjustments(work),
        "K2_review_rounds": k2_review_rounds(work),
        "K3_K4_K5_render": k3_k4_k5_render(work),
        "K7_gates": k7_gates(),
        "K9_learning_coverage": k9_classify_coverage(work),
        "K10_golden_coverage": k10_golden_coverage(),
        "K11_magic_numbers": k11_magic_numbers(),
        "K13_doc_drift": k13_doc_drift(),
    }
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return

    k1, k3, k7, k9, k10, k11, k13 = (res["K1_boundary_adjustments"], res["K3_K4_K5_render"],
                                     res["K7_gates"], res["K9_learning_coverage"],
                                     res["K10_golden_coverage"], res["K11_magic_numbers"],
                                     res["K13_doc_drift"])
    P = print
    P("=" * 66)
    P(f"BASELINE v7 · {res['measured_at']} · {res['projects_in_work']} פרויקטים")
    P("=" * 66)
    P(f"K1  תיקוני גבול:  גולמי {k1['raw_events_total']} → נפרדים {k1['distinct_adjustments_total']}"
      f" → אפקטיביים {k1['effective_adjustments_total']}  (ניפוח ×{k1['inflation_factor']})")
    P(f"    לסרטון: גולמי {k1['raw_per_project']} · אפקטיבי {k1['effective_per_project']}"
      f" · דלתא חציונית {k1['median_net_delta_sec']}ש · round-trips {k1['noop_roundtrips_total']}")
    P(f"K2  סבבי רוויו:   חציון {res['K2_review_rounds']['avg_rounds']} על {res['K2_review_rounds']['projects_measured']} פרויקטים")
    P(f"K3  קידודים מלאים: חציון {k3['K3_full_encodes']['median']} (טווח {k3['K3_full_encodes']['min']}-{k3['K3_full_encodes']['max']}, worst-case סטטי 7)")
    P(f"K4  דורות AAC:    חציון {k3['K4_aac_generations']['median']} (טווח {k3['K4_aac_generations']['min']}-{k3['K4_aac_generations']['max']})")
    P(f"K5  זמן גימור:    חציון {k3['K5_finish_secs']['median']}ש על {k3['K5_finish_secs']['done_runs']} ריצות")
    P(f"K7  שערים:        qa_gates {k7['hard_blocking']}/{k7['gates_total']} חוסמים"
      f" + כלים {k7['tool_gates_blocking']}/3 = {k7['total_blocking_checks']} בדיקות חוסמות")
    for _n, _v in k7["tool_gates"].items():
        P(f"      · {_n}: {'✅' if _v['blocking'] else '❌'} {_v['why']}")
    P(f"K9  למידה:        {k9.get('events_total')} אירועים · נזרקים {k9.get('dropped_pct')}%"
      f" · report-only {k9.get('recognized_report_only_pct_of_recognized')}% מהמזוהים"
      f" · כיולים {k9.get('recognized_calibratable')} (סף {k9.get('min_evidence')})")
    P(f"K10 Golden:       {k10['cases']} cases · משפחות כללים {k10['families_fired']}/{k10['families_total']}"
      f" · allow-missed default={k10['allow_missed_default']}")
    P(f"K11 מספרי קסם:    {k11['total_float_literals_outside_policy']} מחוץ לפוליסי · מפתחות מתים {k11['dead_policy_keys']}")
    P(f"K13 דריפט תיעוד:  {k13['inconsistent']} אי-התאמות → {k13['inconsistent_list']}")
    P("=" * 66)
    P(f"נשמר: {a.out}")


if __name__ == "__main__":
    main()
