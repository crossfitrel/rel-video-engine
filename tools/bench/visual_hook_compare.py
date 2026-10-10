#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""visual_hook_compare.py — חבילת השוואה להראל (11.9.26). לא תוצר פרסום.

לכל מקרה שהמנוע הציע בו הדגשה ורץ עליו גימור אמיתי פעמיים (off / מאושר) על עותק:
  A_מקור.mp4 · B_הדגשה-עדינה.mp4 — 12 השניות הראשונות מה-FINAL, אותו קידוד, אותו אודיו
  צד-בצד.mp4 — ימין מקור · שמאל הדגשה (כותרת צרובה ב-PIL, Assistant ExtraBold)
  פריים-שיא.jpg — אותו רגע בשני התוצרים, המסגרת מסומנת על המקור
ולכל שבעת סרטוני האפיון + סריקת כל הפרויקטים: ההחלטה והסיבות בעברית.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
SYSDIR = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from relvid.paths import work_root          # noqa: E402
from relvid import visual_hook as VH        # noqa: E402

E2E = work_root() / ".e2e" / "visual-hook"
OUT = SYSDIR / "handoff" / "visual-hook-engine" / "comparisons"
FONT = SYSDIR / "brand-assets" / "Assistant-ExtraBold.ttf"
RED = (135, 29, 31)

REASON_HE = {
    "already_effective": "הפתיחה כבר עובדת כמו שהיא",
    "intentional_entrance": "כניסה מכוונת לפריים בפתיחה — שומרים עליה",
    "fixed_intro_present": "יש פתיח קבוע (פורמט) — לא נוגעים",
    "unsafe_crop": "ידיים/גוף קרובים לשולי הפריים — חיתוך היה מסתיר",
    "semantic_unknown": "לא ניתן לאמת נושא יחיד בפריים",
    "policy_disallowed": "המתכון לא משוחרר",
    "explicit_disabled": "כובה ידנית",
    "auto_cohort_not_approved": "אין קוהורט מאושר להפעלה אוטומטית",
    "stale_transcript": "המילים לא תואמות לגרסת הווידאו",
    "multi_person": "כמה אנשים/פנים בפריים",
    "existing_camera_motion": "כבר יש תנועת מצלמה/פריים בפתיחה",
    "strong_motion": "תנועה חזקה בפתיחה — אין צורך בתנועה נוספת",
    "reservation_conflict": "מתנגש בבירול/שכבה מוגנת",
    "no_verbal_anchor": "אין מילה מדוברת לעגן אליה בשניות 1-5",
    "competing_cut": "יש קאט בתוך חלון ההדגשה",
    "unsupported_timeline": "פורמט/ציר לא נתמך",
    "no_eligible_candidate": "אין מועמד זכאי",
    "shadow_suggestion": "הצעה (לא הוחלה)",
}


def ff(*args, timeout=900):
    r = subprocess.run([VH.ffbin(), "-nostdin", "-y", "-hide_banner", "-loglevel", "error", *map(str, args)],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])


def header_png(path: Path, right: str, left: str, w=1080, h=96):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (w, h), (18, 18, 18))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(FONT), 44)
    for text, cx in ((right, w * 3 // 4), (left, w // 4)):
        try:
            d.text((cx, h // 2), text, font=font, fill=(255, 255, 255), anchor="mm", direction="rtl")
        except Exception:
            d.text((cx, h // 2), text[::-1], font=font, fill=(255, 255, 255), anchor="mm")
    d.rectangle([w // 2 - 2, 10, w // 2 + 1, h - 10], fill=RED)
    img.save(path)


def still_pair(a_mp4: Path, b_mp4: Path, frame: int, rect, out: Path, left_label: str = "הדגשה עדינה"):
    from PIL import Image, ImageDraw
    tmp = out.parent / "_f"
    tmp.mkdir(exist_ok=True)
    for src, name in ((a_mp4, "a.png"), (b_mp4, "b.png")):
        ff("-i", src, "-vf", f"select=eq(n\\,{frame})", "-frames:v", "1", "-fps_mode", "passthrough", tmp / name)
    A = Image.open(tmp / "a.png").convert("RGB").resize((540, 960))
    B = Image.open(tmp / "b.png").convert("RGB").resize((540, 960))
    dr = ImageDraw.Draw(A)
    x, y, w, h = rect
    dr.rectangle([x * 540, y * 960, (x + w) * 540 - 1, (y + h) * 960 - 1], outline=RED, width=5)
    canvas = Image.new("RGB", (1080, 960 + 96), (18, 18, 18))
    # בלי סוגריים: PIL בלי raqm הופך אותם בטקסט RTL ("מקור )המסגרת(")
    header_png(tmp / "h.png", "מקור · המסגרת = השיא", left_label)
    canvas.paste(Image.open(tmp / "h.png"), (0, 0))
    canvas.paste(B, (0, 96))
    canvas.paste(A, (540, 96))
    canvas.save(out, quality=90)
    shutil.rmtree(tmp, ignore_errors=True)


def build_case(idx: int, case: str) -> dict:
    off = E2E / "runs" / f"{case}_off_v1"
    app = E2E / "runs" / f"{case}_approved_v1"
    plan = json.loads((app / "visual_hook_plan.json").read_text(encoding="utf-8"))
    name = json.loads((app / "project_manifest.json").read_text(encoding="utf-8")).get("name") or case
    stem = f"{idx:02d}_{name}"
    d = OUT / stem
    d.mkdir(parents=True, exist_ok=True)
    A, B = d / f"{stem}__A_מקור.mp4", d / f"{stem}__B_הדגשה-עדינה.mp4"
    for src, dst in ((off / "FINAL.mp4", A), (app / "FINAL.mp4", B)):
        ff("-i", src, "-t", "12", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", dst)
    hdr = d / "_hdr.png"
    header_png(hdr, "מקור", "הדגשה עדינה")
    ff("-i", A, "-i", B, "-loop", "1", "-i", hdr, "-filter_complex",
       "[0:v]scale=540:960[a];[1:v]scale=540:960[b];[b][a]hstack=inputs=2[s];[2:v]scale=1080:96,format=yuv420p[h];"
       "[h][s]vstack=inputs=2[v]", "-map", "[v]", "-map", "0:a", "-t", "12", "-c:v", "libx264", "-crf", "20",
       "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
       d / f"{stem}__צד-בצד.mp4")
    hdr.unlink(missing_ok=True)
    cue = plan["cues"][0]
    peak = cue["keyframes"][1]["frame"] + 8
    still_pair(A, B, peak, VH.rect_at(cue, peak), d / f"{stem}__פריים-שיא.jpg")
    rep = json.loads((app / "visual_hook_report.json").read_text(encoding="utf-8"))
    qa = json.loads((app / "visual_hook_qa.json").read_text(encoding="utf-8"))
    pf = json.loads((app / "PREFLIGHT.json").read_text(encoding="utf-8")).get("verdict", {})
    anchor = next((x.split(":", 1)[1] for x in rep.get("why", []) if x.startswith("anchor:")), None)
    return {"idx": idx, "case": case, "name": name, "dir": stem, "recipe": plan["recipe"],
            "scale": round(1 / cue["keyframes"][1]["rect"][2], 3),
            "window_sec": [round(cue["start_frame"] / 30, 2), round(cue["end_frame"] / 30, 2)],
            "anchor": anchor, "plan_digest": plan["plan_digest"], "qa_pass": qa["pass"],
            "preflight": pf.get("summary"), "evidence": plan["evidence"]["grade"]}


def decisions() -> list:
    rows = []
    audit = json.loads((SYSDIR / "handoff/visual-hook-engine/evidence/sample_audit.json").read_text(encoding="utf-8"))
    for i, s in enumerate(audit, start=1):
        rp = E2E / f"case{i:02d}" / "visual_hook_report.json"
        if rp.exists():
            r = json.loads(rp.read_text(encoding="utf-8"))
            crop = next((c for c in r["candidates"] if c["recipe"] == "SMART_PUNCH_IN"), {})
            rows.append({"name": s["project"], "decision": r["suggestion_label_he"],
                         "reasons": [REASON_HE.get(x, x) for x in (crop.get("reason_codes") or [])] or
                                    ["עבר את כל בדיקות הזכאות"]})
    return rows


def calibration_html() -> str:
    """דוגמאות כיול (visual_hook_calibration.py) — אם נבנו. לא תוצר פרסום."""
    import html as H
    p = OUT / "כיול" / "כיול.json"
    if not p.exists():
        return ""
    doc = json.loads(p.read_text(encoding="utf-8"))
    var = [b for b in doc["built"] if b.get("kind") == "variant"]
    cal = [b for b in doc["built"] if b.get("kind") == "calibration"]
    out = []
    for b in var:
        st = b["dir"]
        out.append(f"""
<section class="case">
  <h2>{H.escape(b['project'])} — עוצמה עדינה יותר ×{b['scale']}</h2>
  <p class="meta">מרכז המסגרת: {H.escape(b.get('center') or '')} · {b['window_sec'][0]}–{b['window_sec'][1]}ש · עוגן «{H.escape(b.get('anchor') or '')}» · תצוגת גוף בלי כתוביות/מוזיקה</p>
  <video class="wide" controls playsinline preload="metadata" src="כיול/{st}/{st}__צד-בצד.mp4"></video>
  <img src="כיול/{st}/{st}__פריים-שיא.jpg" alt="רגע השיא">
  <p class="ask">מול הגרסה המאושרת (×1.06): כאן שולי הלוח נשמרים. אם זו עדיפה — ×1.04 הופך לברירת המחדל בסרטוני לוח.</p>
</section>""")
    for b in cal:
        st = b["dir"]
        ov = b.get("overflow") or {}
        out.append(f"""
<section class="case cal">
  <h2>{H.escape(b['name'])} <span class="tag">גבולי · לכיול</span></h2>
  <p class="meta">נפסל כי: {H.escape(' · '.join(REASON_HE.get(r, r) for r in b['rejected_for']))} (מעטפת התנועה חורגת ב-{round(100 * ov.get('motion_over', 0), 1)}% מהפריים, הראש בפנים) ·
     כאן: {H.escape(b['relaxation_he'])} · ×{b['scale']} · {b['window_sec'][0]}–{b['window_sec'][1]}ש · עוגן «{H.escape(b.get('anchor') or '')}»</p>
  <video class="wide" controls playsinline preload="metadata" src="כיול/{st}/{st}__צד-בצד.mp4"></video>
  <img src="כיול/{st}/{st}__פריים-שיא.jpg" alt="רגע השיא">
</section>""")
    return f"""
<h2 class="sec">עוד דוגמאות — כיול הסף (11.9.26)</h2>
<p class="lead">בסריקה רק 2 מתוך 38 סרטונים יצאו זכאים. {len(cal)} נוספים נפסלו <b>רק</b> כי ידיים/גוף מתקרבים לשולי הפריים — כל שאר הבדיקות עברו.
כאן הם עם הרפיה אחת: מגינים רק על הראש. זו לא הצעה לפרסום — זה כדי לקבוע את הסף מהעין שלך ולא מניחוש. תצוגת גוף, 12 שניות, בלי כתוביות.
פסילות מוגנות (כמה אנשים, תנועת מצלמה קיימת, כניסה מכוונת, בירול או קאט בחלון, פתיח) לא הורפו.</p>
<p class="ask">מה לומר לי: אילו מספרים <b>עוברים</b> ואילו <b>לא</b>. רוב "עובר" ⇒ מגינים רק על הראש, ומספר הזכאים בסריקה עולה מ-2 לעד {2 + len(cal)}. רוב "לא" ⇒ הסף הנוכחי נכון.</p>
{''.join(out)}"""


def write_html(doc):
    import html as H
    cards = []
    for b in doc["built"]:
        st = b["dir"]
        cards.append(f"""
<section class="case">
  <h2>{H.escape(b['name'])}</h2>
  <p class="meta">הדגשה עדינה ×{b['scale']} · {b['window_sec'][0]}–{b['window_sec'][1]}ש · עוגן: «{H.escape(b['anchor'] or '')}» ·
     QA {'עבר' if b['qa_pass'] else 'נכשל'} · מבקר-קדם: {H.escape(b['preflight'] or '')}</p>
  <div class="pair">
    <figure><video controls playsinline preload="metadata" src="{st}/{st}__B_הדגשה-עדינה.mp4"></video><figcaption>B · הדגשה עדינה</figcaption></figure>
    <figure><video controls playsinline preload="metadata" src="{st}/{st}__A_מקור.mp4"></video><figcaption>A · מקור</figcaption></figure>
  </div>
  <img src="{st}/{st}__פריים-שיא.jpg" alt="אותו רגע בשני התוצרים">
  <p class="ask">מה לומר לי אחרי הצפייה: <b>מקור / הדגשה / שוויון</b> · האם תומך במשפט הפתיחה · האם מסיח · מה לשנות.</p>
</section>""")
    rows = "".join(f"<tr><td>{H.escape(r['name'])}</td><td>{H.escape(r['decision'] or '')}</td>"
                   f"<td>{H.escape(' · '.join(r['reasons']))}</td></tr>" for r in doc["samples"])
    reasons = "".join(f"<li>{H.escape(k)} — {v}</li>" for k, v in doc["scan"]["reasons"])
    page = f"""<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>פתיחה חזותית — השוואה</title>
<style>
:root{{--red:#871d1f;--ink:#161616;--mut:#666;--bg:#faf8f6}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--ink);font-family:Assistant,'Ploni',system-ui,sans-serif;line-height:1.55}}
main{{max-width:980px;margin:0 auto}} h1{{font-size:30px;margin:0 0 6px}} h1 b{{color:var(--red)}}
.lead{{color:var(--mut);margin:0 0 26px}} .case{{background:#fff;border-radius:14px;padding:18px;margin:0 0 22px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.case h2{{margin:0 0 4px;font-size:22px}} .meta{{color:var(--mut);font-size:14px;margin:0 0 12px}}
.pair{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}} figure{{margin:0}}
video{{width:100%;aspect-ratio:9/16;background:#000;border-radius:10px}} figcaption{{text-align:center;font-weight:700;margin-top:4px}}
img{{width:100%;max-width:100%;border-radius:10px;margin-top:12px}} video.wide{{aspect-ratio:1080/1056;max-width:640px;display:block;margin:0 auto}} .tag{{font-size:14px;background:#871d1f;color:#fff;border-radius:20px;padding:2px 10px;vertical-align:middle}} h2.sec{{margin-top:34px}} .ask{{border-right:4px solid var(--red);padding:6px 12px;background:#fbeeee;border-radius:6px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;font-size:15px}}
td,th{{padding:9px 10px;border-bottom:1px solid #eee;text-align:right;vertical-align:top}} th{{background:#f0e6e6}}
.wrap{{overflow-x:auto}} ul{{columns:2;gap:24px}} @media(max-width:600px){{ul{{columns:1}}}}
</style></head><body><main>
<h1>פתיחה חזותית — <b>השוואה על עותקים</b></h1>
<p class="lead">אותו גימור אמיתי פעמיים: בלי הטיפול (A) ועם הדגשה עדינה אחת בתמונה בלבד (B). הדיבור, הכתוביות, המוזיקה והמשך זהים.
לצפות בטלפון: לפתוח את קבצי ה-B וה-A מתוך התיקייה הזו ב-iCloud. זה לא תוצר פרסום, ואין כאן טענה שהשימור משתפר — ההחלטה היא טעם שלך.</p>
{''.join(cards)}
{calibration_html()}
<h2>שבעת סרטוני האפיון — מה המנוע היה מחליט</h2>
<div class="wrap"><table><tr><th>סרטון</th><th>החלטה</th><th>למה</th></tr>{rows}</table></div>
<h2>סריקת כל הפרויקטים ({doc['scan']['n']})</h2>
<p>הצעת הדגשה רק ב: {H.escape(' · '.join(doc['scan']['eligible']))}. בכל השאר — ללא שינוי, והסיבות (סרטון יכול להופיע בכמה):</p>
<ul>{reasons}</ul>
</main></body></html>"""
    (OUT / "השוואה.html").write_text(page, encoding="utf-8")


def main() -> int:
    cases = sys.argv[1:] or ["case03"]
    OUT.mkdir(parents=True, exist_ok=True)
    built = [build_case(i, c) for i, c in enumerate(cases, start=1)]
    scan = json.loads((E2E / "scan" / "scan_results.json").read_text(encoding="utf-8"))
    from collections import Counter
    cnt = Counter(x for r in scan for x in (r.get("crop_reasons") or []))
    doc = {"built": built, "samples": decisions(),
           "scan": {"n": len(scan), "eligible": [r["project"] for r in scan if r.get("suggestion") == "SMART_PUNCH_IN"],
                    "reasons": [[REASON_HE.get(k, k), v] for k, v in cnt.most_common()]}}
    (OUT / "comparisons.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    write_html(doc)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
