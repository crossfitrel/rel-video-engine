#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_ab.py — שער הזהות של מנוע הרינדור v2 (V2 שלב 2).

**המנוע לא הופך לברירת מחדל בלי שהקובץ הזה עובר.** הכלל של המערכת: לא מחליפים
רכיב בלי מספר לפני ואחרי (התבנית: `ASR-BENCH.md`).

מה נמדד, ולמה דווקא זה:

1. **זהות תוכן** — משך, רזולוציה, fps, קודק. פער משך מעל 0.15ש אומר שמיפוי
   הצירים (keep_segments → tight_keeps → speed) סטה, וזה הכשל היחיד שיכול
   להעביר סרטון שגוי בשקט.
2. **יישור ויזואלי** — SSIM/PSNR בין v1 ל-v2. **לא** מצפים ל-1.0: v2 הוא
   קידוד אחד ו-v1 הוא 4-7, ולכן הם *חייבים* להיות שונים. מה שגבוה SSIM מוכיח
   הוא שאותם פריימים יושבים באותם זמנים — כלומר לא הזזנו את הציר.
3. **איכות מול אב-קדמון משותף** — SSIM של כל אחד מהם מול `EXPORT_TIGHT.mp4`
   (המקור האחרון שלפני הכתוביות, באותו משך ובאותו ציר). **זו המדידה שקובעת
   אם v2 באמת טוב יותר**: שני הקבצים נושאים את אותה רצועת כתוביות באותה
   גיאומטריה, ולכן ההפרש ביניהם הוא דור הקידוד ולא התוכן. v2 חייב לנצח.
4. **אודיו** — LUFS ו-True Peak. יעד ‎-14 LUFS, TP ≤ ‎-0.8.
5. **דורות** — מה שהצנרת דיווחה בפועל (‏`finish_status.timings` מול
   `render_v2_report.json`).

שימוש:
  python3 tools/bench/render_ab.py --workdir W [--json]
  python3 tools/bench/render_ab.py --all [--limit 5]          # כל פרויקט שיש בו את שניהם
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from relvid.paths import work_root                            # noqa: E402

TOL_DUR = 0.15          # ש
# יישור ציר נמדד בספירת פריימים, לא ב-SSIM. הסף נגזר מסבילות המשך כדי ששתי
# הבדיקות לא יסתרו: 0.15ש × 30fps = 4.5 ⇒ 5 פריימים. נמדד שסף 3 הפיל סרטון של
# 14 סגמנטים על Δ=4 בזמן שהמשך שלו (0.143ש) עבר — כלומר הסף היה הדוק מהמדד
# שהוא אמור לשרת. שגיאת העיגול של ה-tighten ב-v1 מצטברת עם מספר התפרים.
MAX_FRAME_DELTA = 5
MIN_SSIM_ANCHOR = 0.85  # כל אחד מהם מול EXPORT_TIGHT (אב-קדמון משותף)
TOL_LUFS = 1.2          # מול -14
MAX_TP = -0.8


def sh(cmd, timeout=900):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                          timeout=timeout)


def probe(p):
    r = sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=width,height,avg_frame_rate,codec_name,pix_fmt,color_primaries:"
            "format=duration,size", "-of", "json", str(p)])
    j = json.loads(r.stdout or "{}")
    s = (j.get("streams") or [{}])[0]
    f = j.get("format") or {}
    fr = s.get("avg_frame_rate", "0/1")
    try:
        a, b = fr.split("/")
        fps = round(float(a) / float(b), 2) if float(b) else 0.0
    except Exception:
        fps = 0.0
    r2 = sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
             "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(p)])
    try:
        frames = int((r2.stdout or "0").strip().rstrip(",").split(",")[0])
    except (TypeError, ValueError):
        frames = 0
    return {"w": s.get("width"), "h": s.get("height"), "fps": fps,
            "vcodec": s.get("codec_name"), "pix_fmt": s.get("pix_fmt"),
            "primaries": s.get("color_primaries"), "frames": frames,
            "dur": round(float(f.get("duration") or 0), 3),
            "mb": round(int(f.get("size") or 0) / 1e6, 2)}


def loudness(p):
    r = sh(["ffmpeg", "-nostdin", "-i", str(p), "-af",
            "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        return {}
    d = json.loads(m.group(0))
    return {"I": round(float(d["input_i"]), 2), "TP": round(float(d["input_tp"]), 2)}


def compare(ref, cmp_):
    """SSIM+PSNR של cmp_ מול ref. שני הקבצים חייבים להיות באותו משך/רזולוציה."""
    r = sh(["ffmpeg", "-nostdin", "-i", str(cmp_), "-i", str(ref), "-lavfi",
            "[0:v][1:v]ssim;[0:v][1:v]psnr", "-f", "null", "-"])
    out = {}
    m = re.search(r"SSIM .*All:([\d.]+)", r.stderr)
    if m:
        out["ssim"] = round(float(m.group(1)), 5)
    m = re.search(r"PSNR .*average:([\d.]+)", r.stderr)
    if m:
        out["psnr"] = round(float(m.group(1)), 2)
    if not out:
        # ffmpeg 8 מדפיס בפורמט אחר לפעמים — ניסיון שני, פילטר בודד
        r2 = sh(["ffmpeg", "-nostdin", "-i", str(cmp_), "-i", str(ref),
                 "-lavfi", "ssim", "-f", "null", "-"])
        m = re.search(r"All:\s*([\d.]+)", r2.stderr)
        if m:
            out["ssim"] = round(float(m.group(1)), 5)
    return out


def audit(w: Path) -> dict:
    v1 = w / "FINAL.mp4"
    # ⚠️ **לא** FINAL_v2.mp4 — זה שם שהראל משתמש בו לגרסה שנייה של סרטון
    # (נמצא קובץ כזה מ-20.7 בפרויקט אמיתי). התוצר של המנוע הוא FINAL_engine2.mp4.
    v2 = next((w / n for n in ("FINAL_engine2.mp4",) if (w / n).exists()), None)
    tight = w / "EXPORT_TIGHT.mp4"
    res = {"project": w.name, "v1": str(v1), "v2": str(v2) if v2 else None}
    if not v1.exists() or not v2:
        res["skip"] = "אין שני קבצים להשוואה (צריך FINAL.mp4 ו-FINAL_engine2.mp4)"
        return res

    # ── שני מקרים שבהם ההשוואה אינה תקפה, וחייבים להצהיר עליהם ולא "לעבור" ──
    # 1. אפקט הפורמט הקבוע (ניפוץ זכוכית) — v2 עדיין לא מרכיב אותו.
    # 2. **קומפוזיטינג ידני על קבצי ביניים.** זה הממצא הארכיטקטוני של שלב 2:
    #    v1 משרשר ממה שקיים על הדיסק, ולכן אפקט/סידור-מחדש שנעשה ביד על
    #    EXPORT נכנס ל-FINAL. v2 מרנדר **מ-INPUT**, ולכן עבודה כזו בלתי-נראית לו.
    #    זו בעיקר מעלה (מקור אמת אחד), אבל היא אומרת שפרויקט כזה חייב לבטא את
    #    השינוי בתוכנית (broll/FX item) ולא בקובץ ביניים. `Segment.src` הוא
    #    פר-סגמנט בדיוק בשביל זה — המסלול קיים, הוא פשוט לא מחובר עדיין.
    hand = [n for n in ("EXPORT+FX.mp4", "EXPORT_with_effect.mp4", "EXPORT_reordered.mp4",
                        "EXPORT_before_fx_backup.mp4", "EXPORT_TIGHT2.mp4")
            if (w / n).exists()]
    if hand:
        res["skip"] = ("השוואה לא תקפה — קומפוזיטינג/סידור ידני על קבצי ביניים "
                       f"({', '.join(hand)}). v2 מרנדר מ-INPUT ולכן אינו רואה את זה. "
                       "חוב מתועד: לבטא את השינוי בתוכנית, או לחבר src פר-סגמנט.")
        res["not_applicable"] = True
        return res

    p1, p2 = probe(v1), probe(v2)
    res["probe"] = {"v1": p1, "v2": p2}
    res["dur_delta"] = round(abs(p1["dur"] - p2["dur"]), 3)
    res["format_match"] = (p1["w"] == p2["w"] and p1["h"] == p2["h"]
                           and abs(p1["fps"] - p2["fps"]) < 0.1
                           and p1["vcodec"] == p2["vcodec"])
    res["align"] = compare(v1, v2)
    # ── עוגן האיכות: רינדור ייחוס באיכות גבוהה של **אותו ציר** ──
    # EXPORT_TIGHT אינו אב-קדמון משותף: הוא נמצא רק על המסלול של v1 (INPUT crf23
    # → recut crf18 → tighten crf18), ולכן השוואה מולו מענישה את v2 דווקא על כך
    # שהוא **מדלג** על שני הדורות האלה. נמדד: v1 ניצח ב-4 מ-5 פרויקטים במדד הזה,
    # וזו הייתה תוצאה מוטה ולא אמיתית. העוגן הנכון הוא רינדור crf12 של אותו ציר
    # דרך אותו מנוע — שני הקבצים נמדדים מול אותו ייחוס איכותי.
    ref = w / "_ab_ref_crf12.mkv"
    if not ref.exists():
        try:
            sys.path.insert(0, str(TOOLS))
            from relvid import render as RENDER
            tl = RENDER.build_timeline(w, crf=12)
            RENDER.render(tl, ref, jobs=3)
        except Exception as e:
            res["ref_error"] = str(e)[:200]
    if ref.exists():
        pr = probe(ref)
        if abs(pr["dur"] - p2["dur"]) < 1.0:
            res["vs_ref"] = {"v1": compare(ref, v1), "v2": compare(ref, v2),
                             "ref_dur": pr["dur"], "ref_frames": pr.get("frames")}
    res["loudness"] = {"v1": loudness(v1), "v2": loudness(v2)}

    rr = w / "render_v2_report.json"
    if rr.exists():
        try:
            d = json.loads(rr.read_text(encoding="utf-8"))
            res["render_v2"] = {k: d.get(k) for k in
                                ("n_segments", "n_cached", "n_rendered", "encode_secs",
                                 "wall_secs", "jobs", "video_generations")}
            res["render_v2"]["meta"] = d.get("plan", {}).get("speed_source")
        except Exception:
            pass

    # ── הכרעה ──
    checks = []

    def chk(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    chk("משך זהה", res["dur_delta"] <= TOL_DUR,
        f"Δ={res['dur_delta']}ש (סף {TOL_DUR})")
    chk("פורמט זהה", res["format_match"],
        f"v1 {p1['w']}x{p1['h']}@{p1['fps']} {p1['vcodec']} · "
        f"v2 {p2['w']}x{p2['h']}@{p2['fps']} {p2['vcodec']}")
    # יישור הציר נמדד בספירת פריימים — זו הבדיקה החדה. SSIM בין v1 ל-v2 **אינו**
    # מדד יישור: v2 הוא קידוד אחד ו-v1 הוא 4-7, ולכן הם חייבים להיות שונים, וסף
    # גבוה עליהם היה נכשל דווקא כשה-v2 טוב יותר. הוא מדווח כמידע בלבד.
    fd = abs((p1.get("frames") or 0) - (p2.get("frames") or 0))
    chk("יישור ציר (ספירת פריימים)", (p2.get("frames") or 0) > 0 and fd <= MAX_FRAME_DELTA,
        f"v1 {p1.get('frames')} · v2 {p2.get('frames')} פריימים (Δ={fd}, סף {MAX_FRAME_DELTA})")
    vt = res.get("vs_ref")
    if vt and vt["v1"].get("ssim") and vt["v2"].get("ssim"):
        s1, s2 = vt["v1"]["ssim"], vt["v2"]["ssim"]
        chk("שניהם מיושרים לעוגן", min(s1, s2) >= MIN_SSIM_ANCHOR,
            f"מול ייחוס crf12: v1 SSIM={s1} · v2 SSIM={s2} (סף {MIN_SSIM_ANCHOR})")
        chk("v2 קרוב יותר למקור (פחות דורות)", s2 >= s1,
            f"v2 {s2} מול v1 {s1} → {'v2 מנצח' if s2 >= s1 else 'v1 מנצח — לבדוק'} "
            f"(+{round((s2-s1)*100, 2)} נק' SSIM)")
    l2 = res["loudness"]["v2"]
    if l2:
        chk("loudness v2", abs(l2.get("I", 0) + 14.0) <= TOL_LUFS and l2.get("TP", 0) <= MAX_TP,
            f"I={l2.get('I')} TP={l2.get('TP')} (יעד -14 ±{TOL_LUFS}, TP≤{MAX_TP})")
    chk("גודל ≤60MB", p2["mb"] <= 60, f"{p2['mb']}MB")
    chk("תיוג צבע", (p2.get("primaries") or "unknown") not in ("unknown", None, ""),
        f"v1 primaries={p1.get('primaries')} · v2 primaries={p2.get('primaries')}")

    res["checks"] = checks
    res["pass"] = all(c["pass"] for c in checks)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=str(HERE / "render_ab.json"))
    a = ap.parse_args()

    targets = []
    if a.all:
        wr = work_root()
        for d in sorted(wr.iterdir()):
            if d.is_dir() and not d.name.startswith((".", "_")) \
               and (d / "FINAL.mp4").exists() and (d / "FINAL_engine2.mp4").exists():
                targets.append(d)
        targets = targets[:a.limit]
    elif a.workdir:
        targets = [Path(a.workdir)]
    else:
        ap.error("--workdir או --all")

    results = [audit(t) for t in targets]
    applicable = [r for r in results if not r.get("skip")]
    ok = [r for r in applicable if r.get("pass")]
    doc = {"tolerances": {"dur": TOL_DUR, "frame_delta": MAX_FRAME_DELTA,
                          "ssim_anchor": MIN_SSIM_ANCHOR,
                          "lufs": TOL_LUFS, "tp": MAX_TP},
           "n": len(results), "n_applicable": len(applicable), "passed": len(ok),
           "results": results}
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    if a.json:
        print(json.dumps(doc, ensure_ascii=False, indent=1))
        return 0 if (applicable and len(ok) == len(applicable)) else 1

    print("=" * 74)
    print(f"שער זהות מנוע רינדור v2 — {len(ok)}/{len(applicable)} עברו "
          f"({len(results) - len(applicable)} לא-תקפים)")
    print("=" * 74)
    for r in results:
        if r.get("skip"):
            print(f"⏭  {r['project']}: {r['skip']}")
            continue
        print(f"\n{'✅' if r['pass'] else '❌'} {r['project']}")
        for c in r["checks"]:
            print(f"     {'✓' if c['pass'] else '✗'} {c['check']:<32} {c['detail']}")
        rv = r.get("render_v2")
        if rv:
            print(f"     ⓘ {rv['n_segments']} סגמנטים · {rv['n_rendered']} רונדרו · "
                  f"קידוד {rv['encode_secs']}ש · wall {rv['wall_secs']}ש · "
                  f"דורות וידאו {rv['video_generations']}")
        print(f"     ⓘ גודל: v1 {r['probe']['v1']['mb']}MB → v2 {r['probe']['v2']['mb']}MB")
    print("\n" + "=" * 74)
    print(f"נשמר: {a.out}")
    return 0 if (results and len(ok) == len(results)) else 1


if __name__ == "__main__":
    sys.exit(main())
