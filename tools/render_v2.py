#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_v2.py — CLI למנוע הרינדור v2 (גרף סגמנטים + מטמון).

בונה את **המאסטר** בלבד: וידאו סופי בפרמטרי המסירה, עם כתוביות ובירולים
צרובים, ואודיו PCM. המוזיקה, ה-loudness והשערים נשארים ב-`local_finish_pipeline`
(‏`--render-engine v2`) — כאן אין שכפול של אף אחד מהם. הכלי הזה קיים כדי
לבדוק, למדוד ולדבג את המנוע בנפרד מהצנרת.

שימוש:
  python3 tools/render_v2.py plan   --workdir W [--json]      # מה ירונדר, בלי לרנדר
  python3 tools/render_v2.py build  --workdir W [--out master_v2.mkv] [--jobs 4] [--force]
  python3 tools/render_v2.py cache  --workdir W [--prune]
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from relvid import render as R                      # noqa: E402


def _pl(tl):
    return {
        "engine": R.ENGINE_VERSION,
        **getattr(tl, "meta", {}),
        "deliver": {k: R.DELIVER[k] for k in ("width", "height", "fps", "crf", "preset",
                                              "pix_fmt", "acodec")},
        "crf": tl.crf,
        "segments": [{"i": s.idx, "src_in": s.t_in, "src_out": s.t_out,
                      "dur": s.dur, "out_start": s.out_start,
                      "cues": len(s.cues), "broll": len(s.broll), "key": s.key}
                     for s in tl.segments],
    }


def cmd_plan(a):
    tl = R.build_timeline(a.workdir, brand=a.brand, crf=a.crf)
    info = _pl(tl)
    cache = Path(a.workdir) / R.CACHE_DIRNAME
    for s in info["segments"]:
        s["cached"] = (cache / f"seg_{s['key']}.mkv").exists()
    info["cache"] = R.cache_stats(a.workdir)
    if a.json:
        print(json.dumps(info, ensure_ascii=False, indent=1))
        return 0
    m = info
    print(f"מנוע {m['engine']} · מקור הציר: {m['source_of_truth']}")
    print(f"{m['n_segments']} סגמנטים · {m['n_cues']} cues · "
          f"{m['n_broll_placements']} השמות בירול · speed {m['speed']} · משך {m['dur']}ש")
    print(f"פרמטרי מסירה: {R.DELIVER['width']}x{R.DELIVER['height']}@{R.DELIVER['fps']} "
          f"crf{tl.crf} {R.DELIVER['preset']} · אודיו ביניים {R.DELIVER['acodec']}")
    n_cached = sum(1 for s in m["segments"] if s["cached"])
    print(f"מטמון: {n_cached}/{m['n_segments']} סגמנטים כבר מרונדרים "
          f"({R.cache_stats(a.workdir).get('bytes', 0)/1e6:.0f}MB)")
    print()
    print(f"{'#':>3} {'מקור':>16} {'משך':>6} {'בציר':>7} {'cues':>5} {'בירול':>6}  מטמון")
    for s in m["segments"]:
        print(f"{s['i']:>3} {s['src_in']:>7.2f}-{s['src_out']:<8.2f} {s['dur']:>6.2f} "
              f"{s['out_start']:>7.2f} {s['cues']:>5} {s['broll']:>6}  "
              f"{'✓' if s['cached'] else '·'}")
    return 0


def cmd_build(a):
    t0 = time.time()
    tl = R.build_timeline(a.workdir, brand=a.brand, crf=a.crf)
    out = Path(a.out) if a.out else (Path(a.workdir) / "master_v2.mkv")

    last = {"n": 0}

    def prog(i, n, res):
        last["n"] = i
        tag = "מטמון" if res.get("cached") else f"{res.get('secs')}ש"
        print(f"  [{i}/{n}] seg {res['key'][:8]} — {tag}", flush=True)

    print(f"▶ רינדור {len(tl.segments)} סגמנטים (crf{tl.crf}) …", flush=True)
    st = R.render(tl, out, jobs=a.jobs, force=a.force, on_progress=prog)
    st["plan"] = _pl(tl)
    st["total_secs"] = round(time.time() - t0, 1)
    (Path(a.workdir) / "render_v2_report.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    if not st.get("ok"):
        print("❌ " + st.get("error", "כשל לא ידוע"), file=sys.stderr)
        return 1
    print(f"✅ מאסטר: {out.name} · {st['n_rendered']} רונדרו / {st['n_cached']} מהמטמון · "
          f"קידוד {st['encode_secs']}ש · wall {st['wall_secs']}ש ({st['jobs']} במקביל)")
    print(f"   דורות וידאו: 1 · דורות AAC עד כה: 0 (המיקס יוסיף אחד)")
    if a.json:
        print(json.dumps(st, ensure_ascii=False, indent=1))
    return 0


def cmd_cache(a):
    if a.prune:
        tl = R.build_timeline(a.workdir, brand=a.brand, crf=a.crf)
        res = R.prune_cache(a.workdir, keep_keys=[s.key for s in tl.segments])
        print(f"נמחקו {res['removed']} סגמנטים לא-בשימוש ({res['bytes']/1e6:.0f}MB)")
    print(json.dumps(R.cache_stats(a.workdir), ensure_ascii=False, indent=1))
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("plan", cmd_plan), ("build", cmd_build), ("cache", cmd_cache)):
        s = sub.add_parser(name)
        s.add_argument("--workdir", required=True)
        s.add_argument("--brand", default="rel")
        s.add_argument("--crf", type=int, default=None)
        s.add_argument("--json", action="store_true")
        if name == "build":
            s.add_argument("--out", default=None)
            s.add_argument("--jobs", type=int, default=None)
            s.add_argument("--force", action="store_true")
        if name == "cache":
            s.add_argument("--prune", action="store_true")
        s.set_defaults(func=fn)
    a = p.parse_args()
    try:
        sys.exit(a.func(a))
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
