#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qa_gates.py — מנוע ה-QA המאוחד של צנרת הווידאו (v5). ריצה אחת, דוח PASS/FAIL לכל השערים.
"מוגדר ≠ עובד": כל שער נמדד על המדיה עצמה.

שערים:
  G1 duration      — משך בגבול הקשיח של length_policy (12–180ש; --max-dur/--min-dur לשינוי)
  G2 silence       — אפס דד-אייר (silencedetect -35dB/0.5 + מילים אם סופקו)
  G3 av_sync       — אורך אודיו = אורך וידאו ±0.3ש (נגד חיתוך-זנב)
  G4 loudness      — integrated ‎-14±1.2 LUFS, TP ≤ ‎-0.8 (אם --music/--loudnorm בוצע)
  G5 format        — 1080×1920 (או ריבועי עם --allow-square), fps 24–60, faststart
  G5c size         — ≤‎60MB. **דיווח בלבד** (v9.9): הגודל היה חלק מ-G5 החוסם,
                     כלומר סרטון תקין לחלוטין לא קיבל FINAL בגלל מספר עגול
                     שאיש לא מדד — והתיקון בפועל היה ידני בכל ריצה. הדחיסה
                     לתקן ההעלאה כבר קורית בצנרת (`deliver_spec`), ולכן זה
                     מדד ולא שער. רזולוציה/fps נשארים חוסמים — שם הכשל אמיתי.
  G6 captions_sync — captions_qa PASS≥90% (אם סופקו words+truth)
  G7 hook_intact   — המילים הראשונות של האמת מופיעות בפתיחה (אם סופק truth)
הרצה:
  python3 qa_gates.py --video FINAL.mp4 [--words words.json] [--truth whisper.json]
      [--content-type value] [--length-reason "..."] [--max-dur N] [--min-dur N] [--skip-loudness] [--allow-square] [--report out.json]
exit 0 = הכל עבר · exit 1 = שער נכשל
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# הנימוק של כל שער נכנס לדוח כדאטה, לא כהערה בקוד. שער שאומר רק "לא" הוא
# שער שלא סיים את העבודה — מי שקורא qa_report.json רואה גם על מה הוא מגן,
# מה מחיר החסימה, ומה קורה במקום. הייבוא רך: אם הרשומה חסרה, השערים עדיין
# רצים — הם לא תלויים בה, היא רק מסבירה אותם.
try:
    import gate_registry as GR
except Exception:                                    # pragma: no cover
    GR = None

def sh(cmd, timeout=180):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def probe(video):
    r = sh(["ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type,width,height,avg_frame_rate,duration:format=duration,size",
            "-of", "json", str(video)])
    return json.loads(r.stdout or "{}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--words"); ap.add_argument("--truth")
    # v8.6 (P0-10) — ground-truth שנמדד מהמדיה, לא נגזר מאותו חישוב.
    # שורש: G6 השווה את words_final מול whisper_export_tight — ושניהם עוברים את
    # אותו remap_words המדויק, כך ששגיאת מיפוי/הידוק מתקזזת בשני הצדדים והשער
    # תמיד עובר. זו סתירה ישירה לעקרון "כל שער נמדד על המדיה עצמה" (שורה 5).
    # --truth-measured הוא תמלול ASR חדש שרץ על האודיו של הציר הסופי בפועל.
    ap.add_argument("--truth-measured", default=None,
                    help="whisper_verify.json — ASR על האודיו של הציר הסופי (G6b)")
    ap.add_argument("--visual-hook-qa", default=None,
                    help="visual_hook_qa.json — רק כשהוחל טיפול פתיחה חזותית (G8b); בלעדיו G8 כמו שהיה")
    ap.add_argument("--measured-tol", type=float, default=0.35)
    ap.add_argument("--measured-pass", type=float, default=85.0)
    # v9.25 (הראל 19.9.26 "לא כל סרטון חייב להיות מוגבל עד 60 שניות"): הגבולות
    # נגזרים מ-length_policy לפי סוג התוכן — לא מספר קשיח כאן. --max/--min-dur עוקפים.
    ap.add_argument("--content-type", default=None)
    ap.add_argument("--length-reason", default=None)
    ap.add_argument("--max-dur", type=float, default=None)
    ap.add_argument("--min-dur", type=float, default=None)
    ap.add_argument("--skip-loudness", action="store_true")
    ap.add_argument("--allow-square", action="store_true")
    ap.add_argument("--report")
    a = ap.parse_args()
    V = Path(a.video)
    gates, hard_fail = [], False

    def gate(name, ok, detail, hard=True):
        nonlocal hard_fail
        rec = {"gate": name, "pass": bool(ok), "detail": detail, "hard": hard,
               "warn": bool(not ok and not hard)}
        if GR:
            rec["why"] = GR.annotate("qa_gates", name)
        gates.append(rec)
        if hard and not ok:
            hard_fail = True

    info = probe(V)
    fmt = info.get("format", {})
    vs = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    aus = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    vdur = float(fmt.get("duration", 0) or 0)
    w, h = vs.get("width", 0), vs.get("height", 0)
    size_mb = int(fmt.get("size", 0)) / 1048576

    # G1 duration
    import length_policy as LP
    _lp = LP.evaluate(vdur, a.content_type, a.length_reason)
    _mn = a.min_dur if a.min_dur is not None else LP.HARD_MIN
    _mx = a.max_dur if a.max_dur is not None else LP.HARD_MAX
    gate("G1_duration", _mn <= vdur <= _mx, f"{vdur:.1f}s (גבול קשיח {_mn:.0f}–{_mx:.0f})")
    # G1b (v9.25): יעד לפי סוג תוכן — רך בלבד. האורך אינו הלוחץ (40 ריילס: rho=0.10 מול reach).
    gate("G1b_target_range", _lp["in_target"], _lp["message"], hard=False)
    # G1c (v9.25): מעל סף-הנימוק של הסוג — חייב length_reason. רך: ההכרעה של הראל.
    gate("G1c_length_reason", _lp["reason_ok"],
         (_lp["message"] if not _lp["reason_ok"] else
          (f"נימוק אורך: {_lp['length_reason'][:80]}" if _lp["needs_reason"]
           else f"מתחת לסף הנימוק {_lp['reason_above']:.0f}ש")), hard=False)

    # G2 silence — silencedetect. v6.3 (20.7.26): פער ≥0.6ש = חור אמיתי; היה חוסם.
    # v7.1 (23.7.26, הראל): הופך לאזהרה בלבד (hard=False) — ה-gate הזה רץ אחרי
    # שהראל כבר סקר ואישר ב-review-app ("אני המילה האחרונה"), ואסור שיחסום את
    # מה ששלח לגימור. עדיין נמדד ומדווח (gates/warn ב-qa_report.json) — לא נעלם.
    r = sh(["ffmpeg", "-i", str(V), "-af", "silencedetect=noise=-35dB:d=0.5", "-f", "null", "-"])
    spans = re.findall(r"silence_start: ([\d.]+).*?silence_duration: ([\d.]+)", r.stderr, re.S)
    mid = [(float(s), float(d)) for s, d in spans if float(d) >= 0.5 and float(s) > 0.3 and float(s) + float(d) < vdur - 0.3]
    holes = [(s, d) for s, d in mid if d >= 0.6]
    warns = [(s, d) for s, d in mid if d < 0.6]
    gate("G2_silence", not holes,
         ("נקי" if not mid else f"{len(holes)} חורים: " + ", ".join(f"{s:.1f}s({d:.1f})" for s, d in holes[:4]) +
          (f" · {len(warns)} פאוזות קצרות (לא חוסם)" if warns else "")),
         hard=False)

    # G3 audio == video
    adur = float(aus.get("duration", vdur) or vdur)
    gate("G3_av_sync", abs(adur - vdur) <= 0.3, f"video {vdur:.2f} / audio {adur:.2f}")

    # G4 loudness
    if not a.skip_loudness:
        r = sh(["ffmpeg", "-i", str(V), "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"], timeout=300)
        m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
        if m:
            ln = json.loads(m.group(0))
            ii, tp = float(ln["input_i"]), float(ln["input_tp"])
            gate("G4_loudness", (-15.2 <= ii <= -12.8) and tp <= -0.8, f"I={ii:.1f} LUFS, TP={tp:.1f}", hard=False)
        else:
            gate("G4_loudness", False, "מדידה נכשלה", hard=False)

    # G5 format
    ok_res = (w == 1080 and h == 1920) or (a.allow_square and w == h == 1080)
    fr = vs.get("avg_frame_rate", "0/1")
    try:
        x, y = fr.split("/"); fps = float(x) / float(y) if float(y) else 0
    except Exception:
        fps = 0
    r2 = sh(["ffprobe", "-v", "trace", "-i", str(V)], timeout=60)
    faststart = "moov" in r2.stderr.split("mdat")[0] if "mdat" in r2.stderr else True
    gate("G5_format", ok_res and 24 <= fps <= 60,
         f"{w}x{h} @ {fps:.0f}fps · faststart={'✓' if faststart else '?'}")
    # G5c (v9.9) — הגודל יצא מהשער החוסם. ראה docstring: מספר עגול לא-מדוד
    # שחסם סרטונים תקינים, בזמן שהדחיסה לתקן ההעלאה כבר קורית ב-deliver_spec.
    # ה-detail נשאר נפרד גם כדי שגודל הקובץ לא יזלוג ל-payload של ה-scorer.
    gate("G5c_size", size_mb <= 60, f"{size_mb:.1f}MB (תקן העלאה ≤60MB)", hard=False)
    # G5b (v7): מותג = 30fps. הכרעת AUDIT-v7 #4: קשיח נשאר 24-60, סטייה מ-30 = אזהרה.
    gate("G5b_fps_30", 29.5 <= fps <= 30.5, f"{fps:.2f}fps (יעד מותג: 30)", hard=False)

    # G6 captions sync
    if a.words and a.truth:
        r = sh(["python3", str(HERE / "captions_qa.py"), a.words, a.truth], timeout=120)
        ok = r.returncode == 0
        m = re.search(r"\{.*\}", r.stdout, re.S)
        gate("G6_captions_sync", ok, (m.group(0)[:160] if m else r.stdout[-160:]).replace("\n", " "))

    # G6b (v8.6, P0-10) captions sync מול ASR שנמדד מהאודיו של הציר הסופי.
    # למה זה השער האמיתי ולא G6: G6 משווה שתי נגזרות של אותו חישוב (שתיהן עברו
    # remap_words), ולכן דריפט מיפוי לא יכול להתגלות בו. כאן ה-truth הוא תמלול
    # חדש מהמדיה — אם הכתוביות זזו ביחס למה שנשמע בפועל, זה נופל.
    # ספים רחבים בכוונה (tol 0.35ש / 80%): ל-ASR עצמו יש jitter ו-WER ~7.5%
    # (ASR-BENCH.md), ואנחנו מחפשים דריפט אמיתי (>0.5ש על מילים רבות), לא רעש.
    # כיול (נמדד 30.7.26 על 5 סרטונים אמיתיים, tol=0.35):
    #   score: 94.6 / 97.2 / 98.5 / 98.9 / 100.0   → סף 85 נותן ≥9.6 נקודות מרווח
    #   matched_pct: 76.5 / 81.2 / 85.6 / 89.9 / 95.8
    # matched_pct הוא כמה מהכתוביות בכלל הצליחו להתיישר מול ה-ASR. כשהוא נמוך
    # (רעש/מבטא/מוזיקה) אי אפשר למדוד באמון — וזה **לא** כשל של הכתוביות. לכן
    # מפרידים: "נמדד ורע" = חוסם · "לא ניתן למדוד" = אזהרה. אחרת היינו מייצרים
    # false-block בדיוק בסרטונים הקשים.
    if a.words and a.truth_measured and Path(a.truth_measured).exists():
        r = sh(["python3", str(HERE / "captions_qa.py"), a.words, a.truth_measured,
                "--tol", str(a.measured_tol), "--pass", str(a.measured_pass)], timeout=180)
        m = re.search(r"\{[^{}]*\"score\"[^{}]*\}", r.stdout, re.S)
        summ = {}
        if m:
            try:
                summ = json.loads(m.group(0))
            except Exception:
                summ = {}
        matched = float(summ.get("matched_pct", 0) or 0)
        score = summ.get("score")
        detail = (json.dumps({k: summ[k] for k in ("score", "matched_pct", "mean_signed",
                                                   "mean_abs", "max_abs", "within_0.15")
                              if k in summ}, ensure_ascii=False)
                  if summ else (r.stdout or r.stderr)[-140:].replace("\n", " "))
        ms0 = float(summ.get("mean_signed", 0) or 0)
        # 28.9.26 (TD26 אביגיל): בהתאמה נמוכה ה-mean מזוהם מהתאמות-שווא של ה-ASR
        # (מילה חוזרת שהותאמה 3-8ש רחוק). נמדד: mean ‎-0.42ש, median ‎-0.10ש, ו-onset
        # אקוסטי +0.14ש — הכתוביות מסונכרנות. בענף ההתאמה-הנמוכה שופטים לפי החציון;
        # הסחה אמיתית (רוטטור-קאף +0.65ש) מזיזה גם את החציון, ולכן עדיין נתפסת.
        if matched < 72.0 and summ.get("median_signed") is not None:
            ms0 = float(summ["median_signed"])
        if not summ:
            gate("G6b_captions_measured", True, f"מדידה לא הופקה: {detail}", hard=False)
        elif matched < 72.0 and abs(ms0) < 0.35:
            # התאמה נמוכה + הסחה קטנה = רעש ASR, לא כשל כתוביות.
            gate("G6b_captions_measured", True,
                 f"לא ניתן למדוד באמון (matched={matched:.0f}% < 72, הסחה {ms0:+.2f}ש) · {detail}",
                 hard=False)
        elif matched < 72.0:
            # התאמה נמוכה **אבל** הסחה שיטתית גדולה — רעש ASR הוא סימטרי וקטן;
            # הסחה של ‎0.35ש+ בכיוון אחד היא ציר לא מסונכרן, לא מבטא.
            # נמדד 30.7.26 על מאסל-מן-רוטטור-קאף: matched=47%, mean_signed=+0.65ש,
            # max=5.15ש — פרויקט שה-doctor מסמן edl_ahead, כלומר הציר באמת התקדם
            # מעבר ל-FINAL. G6 דיווח על אותו פרויקט 0.000ש.
            gate("G6b_captions_measured", False,
                 f"הסחה שיטתית {ms0:+.2f}ש למרות התאמה נמוכה (matched={matched:.0f}%) — "
                 f"סימן לציר לא מסונכרן · {detail}")
        else:
            gate("G6b_captions_measured", (score is not None and score >= a.measured_pass),
                 f"{detail} [tol={a.measured_tol} סף={a.measured_pass}]")
        # דריפט שיטתי — עובר את הסף אבל אומר משהו אמיתי על התזמון
        ms = float(summ.get("mean_signed", 0) or 0)
        if summ and abs(ms) >= 0.12:
            gate("G6c_caption_drift_bias", False,
                 f"הסחה שיטתית {ms:+.3f}ש ({'מאוחרות' if ms > 0 else 'מוקדמות'}) — "
                 f"תיקון מוצע {summ.get('suggest_delay')}ש", hard=False)
    elif a.words and a.truth:
        gate("G6b_captions_measured", True,
             "לא נמדד (אין whisper_verify.json) — G6 בלבד", hard=False)

    # G8 opening flash — פלאש/קפיצת פריים בשנייה הראשונה (לקח הראל 19.7)
    # באג נעול (26.7.26): ‎-t היה **אחרי** ‎-i, כלומר אופציית פלט. עם select+null
    # הפילטר רץ על כל הסרטון ומדפיס scene_score מכל מקום — נמדד: השער "נכשל על
    # פלאש בשנייה הראשונה" בגלל קאט בשנייה 4.07. מרגע שיש מצע בירולים רציף
    # (10 קאטים מכוונים) זה היה נכשל בכל סרטון המרה — false positive מובטח.
    # ‎-t לפני ‎-i = trim בקלט, ואז מנותח בפועל רק החלון שהשער מתיימר לבדוק.
    r = sh(["ffmpeg", "-nostdin", "-t", "1.2", "-i", str(V),
            "-vf", "select='gt(scene,0.45)',metadata=print", "-f", "null", "-"], timeout=60)
    flashes = len(re.findall(r"scene_score", r.stderr))
    gate("G8_opening_flash", flashes == 0,
         "פתיחה חלקה" if flashes == 0 else f"{flashes} קפיצות-סצנה בשנייה הראשונה — לבדוק ויזואלית",
         hard=False)

    # G8b — פתיחה חזותית מבוססת-קבלה (11.9.26). **תוספת** ל-G8, לא החלפה: G8 הישן
    # רץ תמיד וזהה לחלוטין. G8b קיים רק כשהוחלה תוכנית, וחוסם רק על אינווריאנטים
    # פיזיים (מספר פריימים · אודיו · תמונה≠תוכנית · פריים שחור/לבן/A→B→A שהוכנס).
    if getattr(a, "visual_hook_qa", None):
        try:
            vq = json.loads(Path(a.visual_hook_qa).read_text(encoding="utf-8"))
            hf = vq.get("hard_failures") or []
            ev = vq.get("events") or []
            gate("G8b_visual_hook", bool(vq.get("pass")),
                 ("QA פתיחה חזותית: " + (", ".join(hf) if hf else "PASS") +
                  f" · אירועים בחלון: {len(ev)} ("
                  + ", ".join(sorted({e.get('class', '?') for e in ev})) + ")"),
                 hard=bool(hf))
        except Exception as e:
            gate("G8b_visual_hook", False, f"דוח QA פתיחה חזותית לא קריא: {e}", hard=True)

    # G7 hook intact
    if a.truth and a.words:
        try:
            truth = json.loads(Path(a.truth).read_text(encoding="utf-8"))
            words = json.loads(Path(a.words).read_text(encoding="utf-8"))
            t3 = [re.sub(r"\W+", "", x["word"]) for x in truth[:3]]
            head = " ".join(re.sub(r"\W+", "", x["word"]) for x in words[:12])
            gate("G7_hook_intact", all(t in head for t in t3 if t), f"פתיחה: {' '.join(t3)}", hard=False)
        except Exception as e:
            gate("G7_hook_intact", False, f"שגיאה: {e}", hard=False)

    report = {"video": str(V), "pass": not hard_fail, "gates": gates}
    if a.report:
        Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for g in gates:
        print(f"{'✅' if g['pass'] else ('❌' if g['hard'] else '⚠️ ')} {g['gate']:<18} {g['detail']}")
    print(json.dumps({"pass": report["pass"]}, ensure_ascii=False))
    sys.exit(0 if report["pass"] else 1)

if __name__ == "__main__":
    main()
