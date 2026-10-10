#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gallery_cut.py — שלב 4: הורדת מקור מ-iCloud, שער איכות שני על הווידאו האמיתי, וחיתוך בירול.

למה שער שני: שלבים 1-3 שפטו *פריים אחד* (התצוגה המקדימה). סרטון שלם יכול להיות
רעוע, מטושטש ברובו, או קפוא — בלי שהפריים הבודד יסגיר את זה. כאן, ורק כאן,
נמדד הווידאו עצמו מול אותה מעטפת שנגזרה מ-447 הבירולים המאושרים.

    python3 gallery_cut.py fetch --limit 30
    python3 gallery_cut.py cut   --limit 30

התוצר: בירולים/גלריה-אוטומטי/{קטגוריה}/בירול גלריה - NNN {תיאור}.mp4
        1080x1920 · מושתק · ~2.8ש · מוכן לסריקת broll_catalog.py
"""
import argparse, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gallery_metrics import frame_metrics
from gallery_harvest import load_ledger, save_ledger, now, LIB

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
STAGING = HERE / "_gallery_work" / "originals"
OUTROOT = PROJ / "בירולים" / "גלריה-אוטומטי"
REFERENCE = HERE / "gallery_reference.json"
OSXPHOTOS = Path.home() / "Library" / "Python" / "3.12" / "bin" / "osxphotos"

CLIP_LEN = 2.8      # אורך בירול יעד
SAMPLE_EVERY = 0.4  # צפיפות דגימת פריימים לניתוח


# ------------------------------------------------------------------ fetch
def cmd_fetch(a):
    led = load_ledger()
    todo = [u for u, r in led["assets"].items()
            if r.get("stage") == "accepted" and not r.get("original")]
    if a.limit:
        todo = todo[:a.limit]
    if not todo:
        print("אין מה להוריד — כל המאושרים כבר על הדיסק")
        return
    STAGING.mkdir(parents=True, exist_ok=True)
    print(f"מוריד {len(todo)} מקורות מ-iCloud...")

    # קריאה מרוכזת אחת: osxphotos מנתח ספריית 2GB בכל הפעלה,
    # ולכן קריאה-לכל-נכס היא הבזבוז הגדול. --uuid-from-file פותר.
    uf = STAGING / "_uuids.txt"
    uf.write_text("\n".join(todo), encoding="utf-8")
    cmd = [str(OSXPHOTOS), "export", str(STAGING),
           "--uuid-from-file", str(uf),
           "--filename", "{uuid}",
           "--download-missing", "--use-photokit",
           "--skip-original-if-edited", "--retry", "2",
           # 4.9.26: osxphotos 0.76.1 עוצר ב-click.confirm כשקיים
           # .osxphotos_export.db בתיקיית היעד ואין --update. בריצה מתוזמנת
           # אין מי שיאשר ⇒ Abort והורדה של 0. --update גם מונע כפילויות.
           "--update"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        print("osxphotos נכשל:", out[-500:], file=sys.stderr)
    else:
        print(out[-300:])

    ok = fail = 0
    for u in todo:
        vids = [p for p in STAGING.glob(f"{u}*")
                if p.suffix.lower() in (".mov", ".mp4", ".m4v")]
        if vids:
            v = max(vids, key=lambda p: p.stat().st_size)
            led["assets"][u]["original"] = str(v)
            led["assets"][u]["fetched_at"] = now()
            ok += 1
        else:
            led["assets"][u]["fetch_error"] = "not_exported"
            fail += 1
    save_ledger(led)
    print(f"FETCH OK: {ok} הורדו · {fail} נכשלו · {_dirsize(STAGING)}")


def _dirsize(p):
    tot = sum(f.stat().st_size for f in Path(p).rglob("*") if f.is_file())
    return f"{tot/1e9:.2f}GB בהמתנה"


# ------------------------------------------------------------------ analyse
def probe(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,avg_frame_rate,duration:format=duration",
           "-of", "json", str(path)]
    d = json.loads(subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout or "{}")
    st = (d.get("streams") or [{}])[0]
    dur = float(st.get("duration") or (d.get("format") or {}).get("duration") or 0)
    return {"w": st.get("width", 0), "h": st.get("height", 0), "dur": dur}


def sample_frames(path, dur, tmpdir):
    """דוגם פריימים לאורך הסרטון ומחזיר [(t, metrics, gray_small)]."""
    out = []
    t = 0.3
    while t < max(0.4, dur - 0.3):
        f = Path(tmpdir) / f"s_{int(t*1000)}.jpg"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path),
                        "-frames:v", "1", "-vf", "scale=-2:512", "-y", str(f)],
                       capture_output=True, timeout=90)
        if f.exists() and f.stat().st_size > 0:
            try:
                with Image.open(f) as im:
                    im.load()
                    m = frame_metrics(im)
                    g = np.asarray(im.convert("L").resize((64, 114)), dtype=np.float32)
                out.append((round(t, 2), m, g))
            except Exception:
                pass
            f.unlink(missing_ok=True)
        t += SAMPLE_EVERY
    return out


def best_window(samples, dur, env):
    """בוחר את החלון הרציף הטוב ביותר: חדות מינימלית מקסימלית, עם תנועה קיימת."""
    if not samples:
        return None
    n_in = max(2, int(round(CLIP_LEN / SAMPLE_EVERY)))
    best = None
    for i in range(0, max(1, len(samples) - n_in + 1)):
        win = samples[i:i + n_in]
        if len(win) < 2:
            continue
        sh = [w[1]["sharp"] for w in win]
        motion = float(np.mean([np.abs(win[k + 1][2] - win[k][2]).mean()
                                for k in range(len(win) - 1)]))
        score = min(sh) + 0.15 * float(np.median(sh))
        cand = {
            "start": win[0][0],
            "sharp_min": round(min(sh), 2),
            "sharp_med": round(float(np.median(sh)), 2),
            "bright_med": round(float(np.median([w[1]["bright"] for w in win])), 2),
            "contrast_med": round(float(np.median([w[1]["contrast"] for w in win])), 2),
            "entropy_med": round(float(np.median([w[1]["entropy"] for w in win])), 3),
            "motion": round(motion, 3),
            "score": round(score, 2),
        }
        if best is None or cand["score"] > best["score"]:
            best = cand
    return best


# ------------------------------------------------------------------ cut
def cmd_cut(a):
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    env = ref["envelope"]
    led = load_ledger()
    todo = [u for u, r in led["assets"].items()
            if r.get("stage") == "accepted" and r.get("original") and not r.get("broll_path")]
    if a.limit:
        todo = todo[:a.limit]
    if not todo:
        print("אין מה לחתוך — להריץ fetch קודם")
        return

    # שערים — אותה מעטפת בדיוק כמו בשלב הסינון, עכשיו על פריימים אמיתיים מהווידאו
    G = {"sharp_min": env["sharp"]["p05"], "contrast_med": env["contrast"]["p05"],
         "entropy_med": env["entropy"]["p05"], "bright_lo": env["bright"]["p01"], "bright_hi": 235.0}
    print("שער איכות שני (נגזר מ-%d בירולים מאושרים):" % ref["n_clips_measured"])
    print(f"  sharp_min ≥ {G['sharp_min']}  ·  contrast ≥ {G['contrast_med']}  ·  entropy ≥ {G['entropy_med']}")

    OUTROOT.mkdir(parents=True, exist_ok=True)
    made = 0
    rejected = {}
    below_p25 = 0
    seq = _next_seq()

    with tempfile.TemporaryDirectory() as td:
        for i, u in enumerate(todo, 1):
            r = led["assets"][u]
            src = Path(r["original"])
            if not src.exists():
                r["stage"] = "rejected"; r["stage_reason"] = "original_missing"
                rejected["original_missing"] = rejected.get("original_missing", 0) + 1
                continue
            info = probe(src)
            if info["dur"] < CLIP_LEN + 0.4:
                r["stage"] = "rejected"; r["stage_reason"] = "video_too_short"
                rejected["video_too_short"] = rejected.get("video_too_short", 0) + 1
                continue
            samples = sample_frames(src, info["dur"], td)
            win = best_window(samples, info["dur"], env)
            if not win:
                r["stage"] = "rejected"; r["stage_reason"] = "unreadable_video"
                rejected["unreadable_video"] = rejected.get("unreadable_video", 0) + 1
                continue
            r["window"] = win
            fail = None
            if win["sharp_min"] < G["sharp_min"]:
                fail = "video_sharp_low"
            elif win["contrast_med"] < G["contrast_med"]:
                fail = "video_contrast_low"
            elif win["entropy_med"] < G["entropy_med"]:
                fail = "video_entropy_low"
            elif not (G["bright_lo"] <= win["bright_med"] <= G["bright_hi"]):
                fail = "video_bright_out"
            if fail:
                r["stage"] = "rejected"; r["stage_reason"] = fail
                rejected[fail] = rejected.get(fail, 0) + 1
                continue

            if win["sharp_med"] < env["sharp"]["p25"]:
                below_p25 += 1
                r["quality_tier"] = "below_p25"
            else:
                r["quality_tier"] = "normal"

            cat = r.get("category", "כלליים")
            desc = (r.get("desc") or "בירול").strip().replace("/", "-")
            outdir = OUTROOT / cat
            outdir.mkdir(parents=True, exist_ok=True)
            name = f"בירול גלריה - {seq:03d} {desc}.mp4"
            dest = outdir / name
            vf = ("scale=1080:1920:force_original_aspect_ratio=increase,"
                  "crop=1080:1920,fps=30")
            cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{win['start']:.2f}",
                   "-i", str(src), "-t", f"{CLIP_LEN}", "-an",
                   "-vf", vf, "-c:v", "libx264", "-crf", "19", "-preset", "medium",
                   "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", str(dest)]
            rr = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if rr.returncode != 0 or not dest.exists() or dest.stat().st_size < 20000:
                r["stage"] = "rejected"; r["stage_reason"] = "encode_failed"
                r["encode_error"] = (rr.stderr or "")[-200:]
                rejected["encode_failed"] = rejected.get("encode_failed", 0) + 1
                continue
            r["stage"] = "adopted"
            r["broll_path"] = str(dest)
            r["adopted_at"] = now()
            if not a.keep_originals:
                try:
                    src.unlink()          # המקור כבר לא נחוץ — הבירול נחתך
                    r["original_purged"] = True
                except Exception:
                    pass
            seq += 1
            made += 1
            if i % 10 == 0:
                save_ledger(led)
                print(f"  ...{i}/{len(todo)} (נוצרו {made})", flush=True)

    save_ledger(led)
    print(f"CUT OK: {made} בירולים נוצרו מתוך {len(todo)} · {below_p25} מהם מתחת ל-p25 (חוב איכות)")
    for k, v in sorted(rejected.items(), key=lambda x: -x[1]):
        print(f"  נפסל בשער השני · {k}: {v}")
    print(f"תיקיית יעד: {OUTROOT}")


def _next_seq():
    n = 0
    if OUTROOT.exists():
        for p in OUTROOT.rglob("בירול גלריה - *.mp4"):
            try:
                n = max(n, int(p.name.split(" - ")[1].split()[0]))
            except Exception:
                pass
    return n + 1


REJECT_DIR = OUTROOT / "_נפסל"


def cmd_reject(a):
    """ניקוי של הראל: מעביר בירול שנוצר אוטומטית לתיקיית _נפסל ומסמן בפנקס.
    לא מוחק — הפסילה הפיכה, והנכס לא ייבחר שוב בריצה הבאה."""
    led = load_ledger()
    REJECT_DIR.mkdir(parents=True, exist_ok=True)
    moved = 0
    for pat in a.name:
        hits = [p for p in OUTROOT.rglob("*.mp4")
                if pat in p.name and "_נפסל" not in str(p)]
        if not hits:
            print(f"  לא נמצא: {pat}")
            continue
        for p in hits:
            dest = REJECT_DIR / p.name
            shutil.move(str(p), str(dest))
            for u, r in led["assets"].items():
                if r.get("broll_path") == str(p):
                    r["stage"] = "rejected"
                    r["stage_reason"] = "harel_" + (a.why or "rejected")
                    r["rejected_at"] = now()
                    r["broll_path"] = str(dest)
            moved += 1
            print(f"  הועבר ל-_נפסל: {p.name}")
    save_ledger(led)
    print(f"REJECT OK: {moved} הועברו · סיבה: {a.why or 'rejected'}")
    print("להריץ אחר כך: python3 tools/broll_catalog.py scan")


def cmd_recat(a):
    """תיקון קטגוריה/תיאור של בירול שנוצר אוטומטית."""
    led = load_ledger()
    hits = [p for p in OUTROOT.rglob("*.mp4") if a.name in p.name and "_נפסל" not in str(p)]
    if not hits:
        print("לא נמצא"); return
    for p in hits:
        newdir = OUTROOT / a.category
        newdir.mkdir(parents=True, exist_ok=True)
        stem = p.stem
        if a.desc:
            head = " ".join(stem.split(" ")[:4])   # "בירול גלריה - NNN"
            stem = f"{head} {a.desc}"
        dest = newdir / (stem + p.suffix)
        shutil.move(str(p), str(dest))
        for u, r in led["assets"].items():
            if r.get("broll_path") == str(p):
                r["category"] = a.category
                if a.desc:
                    r["desc"] = a.desc
                r["broll_path"] = str(dest)
                r["recat_at"] = now()
        print(f"  {p.name} → {a.category}/{dest.name}")
    save_ledger(led)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("reject")
    s.add_argument("name", nargs="+", help="חלק משם הקובץ, למשל '001' או 'רגע קהילתי'")
    s.add_argument("--why", default="")
    s.set_defaults(fn=cmd_reject)
    s = sub.add_parser("recat")
    s.add_argument("name")
    s.add_argument("--category", required=True)
    s.add_argument("--desc", default="")
    s.set_defaults(fn=cmd_recat)
    s = sub.add_parser("fetch")
    s.add_argument("--limit", type=int, default=0)
    s.add_argument("--timeout", type=int, default=3600)
    s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("cut")
    s.add_argument("--limit", type=int, default=0)
    s.add_argument("--keep-originals", action="store_true",
                   help="בלי זה — המקור נמחק אחרי חיתוך מוצלח כדי לא לנפח את הדיסק")
    s.set_defaults(fn=cmd_cut)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
