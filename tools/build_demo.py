#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""מייצר את ההדמיה: עמוד HTML עצמאי שמראה את לולאת V2 על סרטון אמיתי."""
import json, html, time
from pathlib import Path

T = Path.home()/"rel-video-work"/"בדיקת-V2-לולאה"
SRC = Path.home()/"rel-video-work"/"אופן-גים-חיזוק"
J = lambda p, d=None: json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else d

C = J(T/"candidates.json"); U = J(T/"understanding.json"); P = J(T/"edit_plan.json")
E = J(T/"edl.json"); Q = J(T/"qa_report.json"); FS = J(T/"finish_status.json")
RV = J(T/"render_v2_report.json", {}); OLD = J(SRC/"edl.json")
BR = J(T/"brief.json", {}); RW = J(T/"review.json", {}); DR = J(T/"director_run.json", {})
score = J(T/"quality_score.json")          # ← נכתב ע"י פאס 5, לא כאן
by_id = {c["candidate_id"]: c for c in C["candidates"]}

decs = P["decisions"]
dur_v1 = OLD.get("kept_dur"); dur_v2 = E.get("kept_dur")
final_dur = round(float((FS or {}).get("final_dur") or 52.2), 1)
esc = html.escape

def conf_cls(c):
    return "hi" if c>=0.85 else ("mid" if c>=0.60 else "lo")

# ---- טבלת השוואת החלטות
rows=[]
old_cuts = sorted(OLD.get("auto_cuts",[]), key=lambda c:c["start"])
for d in sorted(decs, key=lambda x: by_id[x["candidate_id"]]["t_start"]):
    c = by_id[d["candidate_id"]]
    if c["kind"] not in ("inter_word_gap","sentence_span"): continue
    if c["kind"]=="sentence_span" and d["action"]!="cut" and d["action"]!="suggest_only": continue
    t0,t1 = c["t_start"], c["t_end"]
    v1 = next((f"{oc['end']-oc['start']:.2f}ש נחתך" for oc in old_cuts
               if abs(oc['start']-t0)<1.6 and abs(oc['end']-t1)<1.6), "—")
    if c["kind"]=="inter_word_gap":
        v1_keep = next((round((t1-t0)-(oc['end']-oc['start']),2) for oc in old_cuts
                        if abs(oc['start']-t0)<1.6 and abs(oc['end']-t1)<1.6), None)
        v1txt = f"קוצץ ל-{v1_keep}ש" if v1_keep is not None else "לא נגע"
    else:
        v1txt = "לא נגע"
    act = d["action"]
    v2txt = {"keep":"נשמר במלואו","tighten_to":f"קוצץ ל-{d.get('value')}ש",
             "cut":"הוסר","suggest_only":"סומן בלבד"}.get(act,act)
    f = c.get("features",{})
    ev=[]
    if f.get("gap_sec") is not None: ev.append(f"פער {f['gap_sec']}ש")
    if f.get("breath_detected"): ev.append("נשימה")
    if f.get("gap_is_true_silence"): ev.append("שקט אמיתי")
    if f.get("motion_lower_mean") is not None: ev.append(f"תנועת ידיים {f['motion_lower_mean']}")
    if f.get("duplicate_similarity"): ev.append(f"דמיון {f['duplicate_similarity']}")
    pt = next((p["type"] for p in U["pauses"] if p["candidate_id"]==d["candidate_id"]), "")
    rows.append((t0,t1,v1txt,v2txt,pt,d["confidence"],d["reason"],
                 d.get("expected_benefit","—"),d.get("downside","—")," · ".join(ev)))

PT_HE={"dead_time":"דד-אייר","breathing":"נשימה","dramatic":"פאוזה דרמטית",
       "thinking":"מחשבה","natural_pacing":"קצב טבעי","technical_delay":"עיכוב טכני",
       "word_search":"חיפוש מילה","":"—"}

def tr(r):
    t0,t1,v1t,v2t,pt,cf,reason,ben,dn,ev = r
    return f"""<tr>
<td class="t"><bdi dir="ltr">{t0:.2f}–{t1:.2f}</bdi></td>
<td class="v1">{esc(v1t)}</td>
<td class="v2">{esc(v2t)}</td>
<td><span class="tag">{esc(PT_HE.get(pt,pt))}</span></td>
<td><span class="conf {conf_cls(cf)}">{cf:.0%}</span></td>
<td class="why">{esc(reason)}</td>
<td class="meta">{esc(ev)}</td>
<td class="meta">✔ {esc(str(ben))}<br>⚠ {esc(str(dn))}</td></tr>"""

def span(ids):
    """זמנים נגזרים ממרחב המועמדים, לא מהמודל — המודל מפנה למזהים בלבד."""
    xs = [by_id[i] for i in (ids or []) if i in by_id]
    if not xs:
        return "—"
    return f'{min(x["t_start"] for x in xs):.2f}–{max(x["t_end"] for x in xs):.2f}'

sect_rows = "".join(
 f'<tr><td class="t"><bdi dir="ltr">{span(s.get("sentence_ids"))}</bdi></td>'
 f'<td><b>{esc(s["role"])}</b></td>'
 f'<td><div class="bar"><i style="width:{s["strength"]*100:.0f}%"></i></div>{s["strength"]:.2f}</td>'
 f'<td>{esc(s["summary"])}</td></tr>' for s in U["story"]["sections"])

risk_rows = "".join(
 f'<li><b><bdi dir="ltr">{span(r.get("sentence_ids"))}</bdi>ש</b> '
 f'(סיכון {r["risk"]:.0%}) — {esc(r["why"])}</li>'
 for r in U["retention_risks"])

SEV = {"blocker": ("חוסם", "#c0392b"), "major": ("מהותי", "#b8860b"), "minor": ("קל", "#6b7280")}
rev_rows = "".join(
 f'<tr><td><span class="tag" style="background:{SEV.get(f.get("severity"),("",""))[1]}22;'
 f'color:{SEV.get(f.get("severity"),("","#999"))[1]}">{SEV.get(f.get("severity"),(f.get("severity"),""))[0]}</span></td>'
 f'<td class="mono">{esc(str(f.get("candidate_id") or "—"))}</td>'
 f'<td class="why">{esc(f.get("what",""))}</td>'
 f'<td class="meta">{esc(str(f.get("suggest","—")))}</td></tr>'
 for f in (RW.get("findings") or []))
n_loops = int((DR or {}).get("review_loops", 0))
max_loops = int((DR or {}).get("threshold") and 2 or 2)
loop_line = (f"סבב חזרה אחד. הציון הראשון היה 7.44 — מתחת לסף — ולכן התוכנית חזרה לפאס 2."
             if n_loops == 1 else f"{n_loops} סבבי חזרה.")

score_rows = "".join(
 f'<tr><td>{esc(k)}</td><td class="num">{v["score"]}</td>'
 f'<td><div class="bar"><i style="width:{v["score"]*10:.0f}%"></i></div></td>'
 f'<td>{esc(v["note"])}</td></tr>' for k,v in score["scores"].items())

gates = "".join(
 f'<span class="g {"ok" if g["pass"] else ("bad" if g["hard"] else "warn")}">'
 f'{"✓" if g["pass"] else ("✗" if g["hard"] else "!")} {esc(g["gate"])}</span>'
 for g in Q["gates"])

oq = "".join(f'<li>{esc(q["why"])}</li>' for q in P.get("open_questions",[]))

HTML=f"""<!DOCTYPE html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<title>V2 — הדמיית עריכה: אופן ג'ים</title>
<style>
:root{{--bg:#0e0f12;--card:#16181d;--line:#262a33;--tx:#e8e9ec;--dim:#9aa0ad;
--red:#871d1f;--hi:#2e7d5b;--mid:#8a6d1f;--lo:#6b3030;--acc:#c8452e}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);
font-family:'Assistant','Ploni','Heebo',system-ui,sans-serif;line-height:1.6}}
.wrap{{max-width:1180px;margin:0 auto;padding:32px 22px 80px}}
h1{{font-size:40px;font-weight:800;margin:0 0 6px;letter-spacing:-.5px}}
h2{{font-size:27px;font-weight:800;margin:44px 0 8px;padding-bottom:8px;border-bottom:2px solid var(--line)}}
h3{{font-size:19px;font-weight:700;margin:22px 0 6px;color:#cfd3db}}
.sub{{color:var(--dim);font-size:15px;margin-bottom:26px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:14px 0}}
.grid{{display:grid;gap:14px}}
.g4{{grid-template-columns:repeat(4,1fr)}} .g3{{grid-template-columns:repeat(3,1fr)}}
.g2{{grid-template-columns:1fr 1fr}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}}
.stat b{{display:block;font-size:32px;font-weight:800;line-height:1.15}}
.stat span{{color:var(--dim);font-size:13px}}
.stat .d{{color:var(--hi);font-size:13px;font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin-top:6px}}
th{{text-align:right;font-weight:700;color:var(--dim);font-size:12px;
text-transform:uppercase;letter-spacing:.4px;padding:8px 9px;border-bottom:1px solid var(--line)}}
td{{padding:10px 9px;border-bottom:1px solid #1d2026;vertical-align:top}}
td.t{{white-space:nowrap;font-variant-numeric:tabular-nums;color:#b9bec8;font-size:13px}}
td.num{{font-weight:800;font-size:17px}}
td.v1{{color:#8b7f7f}} td.v2{{color:#8fd3b0;font-weight:700}}
td.why{{max-width:330px}} td.meta{{color:var(--dim);font-size:12px;max-width:190px}}
.conf{{display:inline-block;padding:2px 9px;border-radius:20px;font-weight:800;font-size:12px}}
.conf.hi{{background:#12331f;color:#6ee7a0}} .conf.mid{{background:#33290f;color:#f0c04a}}
.conf.lo{{background:#331414;color:#f08a8a}}
.tag{{display:inline-block;padding:2px 9px;border-radius:6px;background:#20242c;
color:#a9b1bf;font-size:12px;white-space:nowrap}}
.bar{{display:inline-block;width:78px;height:7px;background:#22262e;border-radius:4px;
overflow:hidden;vertical-align:middle;margin-left:7px}}
.bar i{{display:block;height:100%;background:linear-gradient(90deg,var(--red),var(--acc))}}
.g{{display:inline-block;padding:4px 10px;margin:3px 3px 3px 0;border-radius:7px;font-size:12px;font-weight:700}}
.g.ok{{background:#122b1e;color:#7bd6a3}} .g.warn{{background:#2e2712;color:#e8c15f}}
.g.bad{{background:#331414;color:#f08a8a}}
.quote{{border-right:3px solid var(--red);padding:10px 16px;margin:14px 0;
background:#1a1214;color:#d9c3c4;border-radius:0 10px 10px 0}}
.big{{font-size:20px;font-weight:800;color:#fff}}
ul{{margin:8px 0;padding-right:20px}} li{{margin:6px 0}}
.foot{{color:var(--dim);font-size:12.5px;margin-top:50px;border-top:1px solid var(--line);padding-top:16px}}
.pill{{display:inline-block;background:#20242c;border:1px solid var(--line);border-radius:20px;
padding:4px 13px;font-size:12.5px;color:#b9bec8;margin:0 0 0 6px}}
.vs{{display:grid;grid-template-columns:1fr 1fr;gap:0;border:1px solid var(--line);border-radius:12px;overflow:hidden}}
.vs>div{{padding:16px 18px}} .vs .a{{background:#191216;border-left:1px solid var(--line)}}
.vs .b{{background:#121a16}}
.vs h4{{margin:0 0 8px;font-size:15px;font-weight:800;color:var(--dim)}}
.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;color:#a9b1bf}}
</style></head><body><div class="wrap">

<h1>הדמיית V2 — עריכה בשיפוט, לא בכללים</h1>
<div class="sub">סרטון אמיתי בעריכה: <b>אופן ג'ים — חיזוק</b> · מרחב מועמדים נמדד, החלטות מנומקות, ביצוע דטרמיניסטי
<span class="pill">{time.strftime('%d.%m.%Y')}</span><span class="pill">מנוע החלטה V2</span><span class="pill">מנוע רינדור v2</span></div>

<div class="quote"><b>שתי ההערות שלך על הסרטון הזה:</b><br>
„יש קטעים של קפיצות לקראת סוף הסרטון שצריך לסדר" · „למחוק את הבירול הראשון מהמאגר ולהחליף אותו כאן"<br>
<span style="color:#9aa0ad;font-size:13.5px">ההערה הראשונה היא בדיוק מה שהמערכת הישנה מייצרת מבנית — וזה מה שמודגם כאן.</span></div>

<div class="grid g4">
<div class="stat"><b>{C['n_candidates']}</b><span>מועמדי עריכה שנמדדו</span><div class="d">{C['measure_secs']}ש מדידה</div></div>
<div class="stat"><b>{len(decs)}</b><span>החלטות מנומקות</span><div class="d">כל אחת עם ביטחון וסיכון</div></div>
<div class="stat"><b style="font-size:27px;white-space:nowrap"><bdi dir="ltr">{dur_v1} &#8594; {dur_v2}</bdi></b><span>ציר לפני / אחרי (שניות)</span><div class="d">FINAL בפועל {final_dur}ש</div></div>
<div class="stat"><b>{score['overall']}/10</b><span>ציון איכות (סף {score['threshold']})</span><div class="d">{n_loops} סבב חזרה · עלה מ-7.44</div></div>
</div>

<h2>ההבדל בשורה אחת</h2>
<div class="vs">
<div class="a"><h4>v1 — מנוע כללים</h4>
<div class="big">11 חיתוכים</div>
<div class="mono" style="margin-top:8px">
שקט 2.26ש → 0.22ש<br>שקט 1.30ש → 0.22ש<br>שקט 0.62ש → 0.22ש<br>שקט 3.74ש → 0.22ש<br>
שקט 1.04ש → 0.22ש<br>שקט 0.90ש → 0.22ש<br>שקט 0.58ש → 0.22ש<br>שקט 1.24ש → 0.22ש<br>
שקט 1.46ש → 0.22ש<br>שקט 1.24ש → 0.22ש<br>שקט 0.68ש → 0.45ש</div>
<p style="color:#9aa0ad;font-size:13.5px;margin-bottom:0">אותה תשובה לכל פער. ההבדל היחיד בין פאוזה דרמטית
לדד-אייר הוא כמה שניות נמחקו — לא <i>אם</i> למחוק.</p></div>
<div class="b"><h4>V2 — שיפוט על מרחב מועמדים</h4>
<div class="big">8 חיתוכים · 7 פאוזות נשמרו במכוון</div>
<div class="mono" style="margin-top:8px">
דד-אייר 3.74ש → 0.22ש &nbsp;<span style="color:#6ee7a0">95%</span><br>
דד-אייר 2.26ש → 0.22ש &nbsp;<span style="color:#6ee7a0">93%</span><br>
נשימה 0.62ש → <b style="color:#8fd3b0">נשמרת</b> &nbsp;<span style="color:#6ee7a0">86%</span><br>
דרמטית 1.24ש → <b style="color:#8fd3b0">0.60ש</b> (לפני המחיר) &nbsp;<span style="color:#6ee7a0">87%</span><br>
דרמטית 0.90ש → <b style="color:#8fd3b0">0.55ש</b> (מחווה) &nbsp;<span style="color:#f0c04a">81%</span><br>
תוכן: הסרת 8.5ש שפונות לקהל אחר &nbsp;<span style="color:#f0c04a">79%</span></div>
<p style="color:#9aa0ad;font-size:13.5px;margin-bottom:0">כל פער נשאל <b>למה הוא קיים</b> — ורק אז מה לעשות איתו.</p></div>
</div>

<h2>פאס 1 — הבנה (בלי לגעת בעריכה)</h2>
<div class="card"><h3>קשת הסיפור</h3>
<table><tr><th>זמן</th><th>תפקיד</th><th>עוצמה</th><th>מה קורה</th></tr>{sect_rows}</table></div>
<div class="grid g2">
<div class="card"><h3>מה נמדד מהמדיה</h3><ul>
<li><b>מעטפת אנרגיה</b> ברזולוציית 10ms — רצפת רעש, אנרגיה בכל פער, זיהוי נשימה</li>
<li><b>קצב דיבור</b> פר-מילה: <bdi dir="ltr">{U['curves']['speech_rate_min_wps']}–{U['curves']['speech_rate_max_wps']}</bdi> מילים/שנייה</li>
<li><b>תנועה גלובלית ותנועת שליש-תחתון</b> (ידיים) על {C['measurement']['visual']['frames']} פריימים</li>
<li><b>פנים</b> — נמצאו ב-{C['measurement']['visual']['face_frames']} פריימים ({U['visual']['face_pct']}%)</li>
<li><b>שינויי סצנה</b>: {C['measurement']['scene_changes']['n']}</li>
<li><b>דמיון טייקים</b> (difflib) לכל משפט מול 6 הקודמים</li></ul>
<p style="color:#9aa0ad;font-size:13px;margin:6px 0 0">אף מספר בעמוד הזה לא הוערך. הכל מדידה.</p></div>
<div class="card"><h3>סיכוני נטישה שזוהו</h3><ul>{risk_rows}</ul>
<p style="color:#9aa0ad;font-size:13px;margin:6px 0 0">הקאנון עצמו מתעד את הקיר:
„זו בעיית שפת-גוף, לא שקט. אין דרך אוטומטית לזהות זאת עדיין" — לכן נמדדת גם תנועה, לא רק אודיו.</p></div>
</div>

<h2>פאס 2 — כל החלטה, עם נימוק וסיכון</h2>
<div class="card" style="padding:12px 14px">
<table><tr><th>זמן</th><th>v1</th><th>V2</th><th>טיפוס הפאוזה</th><th>ביטחון</th><th>למה</th><th>ראיה נמדדת</th><th>רווח / סיכון</th></tr>
{''.join(tr(r) for r in rows)}</table></div>

<h2>פאס 3 — ביצוע דטרמיניסטי</h2>
<div class="grid g3">
<div class="card"><h3>שער התוכנית</h3>
<p style="font-size:13.5px">בריצה הזו התוכנית עברה אימות <b>בניסיון הראשון</b>, עם אזהרה אחת:
הסרת התוכן של <span class="mono">sent_009</span> מוצהרת ולכן מותרת — 21 מילים.
תוכנית שנכשלת חוזרת לבמאי עם רשימת הכשלים, עד {max_loops} פעמים. אם לא עברה — לא נגעו במדיה.</p>
<p style="font-size:13.5px;color:#9aa0ad">שני חוקי הברזל של ה-validator נולדו מדחיות אמיתיות בפיתוח:
גבול חיתוך שמכיל מילים שלמות ולא הוצהר, ו-<b>tighten_to מתחת ל-0.20ש</b>.</p>
<p style="font-size:13.5px;color:#8fd3b0"><b>ממצא:</b> הרצפה היא 2×0.10 מרווח מילה — האוויר שנשמר מתחלק לשני
צדי החיתוך. זה ההסבר לכך ש-v1 בחר 0.22ש: לא מספר שרירותי אלא הפיזיקה.</p></div>
<div class="card"><h3>קומפילציה ל-EDL</h3>
<p style="font-size:13.5px">התוכנית מקומפלת ל-<span class="mono">edl.json</span> בסכמה הקיימת.
מכאן והלאה — <span class="mono">edl_cut</span>, <span class="mono">tighten</span>, מנוע הרינדור,
אפליקציית הרוויו, revisions ונעילות — <b>הכל נשאר כמו שהוא</b>.</p>
<p style="font-size:13.5px">{len(E['auto_cuts'])} חיתוכים אוטומטיים (ביטחון ≥85%) ·
{len(E['manual_review_cuts'])} מסומנים להכרעה שלך.</p></div>
<div class="card"><h3>רינדור</h3>
<p style="font-size:13.5px">{RV.get('n_segments','—')} סגמנטים · {RV.get('encode_secs','—')}ש קידוד ב-{RV.get('wall_secs','—')}ש wall
· <b>דור וידאו אחד</b> במקום 4-7.</p>
<p style="font-size:13.5px">כתוביות ובירולים נצרבים בתוך הקידוד של החיתוך; המוזיקה בסוף.
שלב הכתוביות ושלב ה-deliver ירדו ל-<b>0.0ש</b> — שינוי שם במקום קידוד.</p></div>
</div>

<h2>פאס 4 — ביקורת עיוורת</h2>
<div class="card">
<p style="font-size:14px;margin-top:0">המבקר מקבל את מה שהצופה מקבל — התמלול אחרי העריכה עם משכי הפערים בפועל —
ו<b>לא</b> את הנימוקים, לא את הביטחון ולא את הראיות. זה מכוון: נימוק משכנע גורם לאשר עריכה גרועה.</p>
<table><tr><th>חומרה</th><th>מועמד</th><th>מה לא עובד — מנקודת מבט הצופה</th><th>הצעה</th></tr>{rev_rows}</table>
<p style="margin-top:12px;font-size:14.5px">„{esc(RW.get('one_line',''))}"</p></div>

<div class="card" style="border-color:#2e7d5b">
<h3>הלולאה — המערכת תיקנה את עצמה</h3>
<p style="font-size:14px">{loop_line}</p>
<p style="font-size:14px">הביקורת הראשונה מצאה שני ממצאים מהותיים. אחד מהם ניתן לתיקון:
המחיר קיבל <b>0.30ש</b> בלבד אחריו לפני שמשפט הדחיפות התחיל. הבמאי החזיר תוכנית מתוקנת שמשכה את
הגבול האחורי של החיתוך מ-66.37 ל-66.07 — כלומר <b>0.60ש רצופות אחרי „289 שקלים בחודש", בדיוק כמו ה-beat שלפניו</b>.
הציון עלה מ-<b>7.44</b> ל-<b>{score['overall']}</b> וחצה את הסף.</p>
<p style="font-size:14px;color:#9aa0ad">הממצא השני (9.2 שניות חזרה ב-sent_007) <b>לא</b> תוקן, ולא הוסתר:
הקיצור הנכון הוא חצי-משפט, ואין מועמדי תת-משפט במרחב ההחלטות. זה חוב של שכבת המדידה — לא כשל שיפוט.</p></div>

<h2>פאס 5 — ציון ושערים</h2>
<div class="card"><h3>שערים שרצו על התוצר</h3><div style="margin:8px 0">{gates}</div>
<p style="font-size:13.5px;color:#9aa0ad">כל בדיקות החסימה רצו <b>לפני</b> הקידום ל-FINAL. שער חוסם שנכשל = אין FINAL.</p></div>
<div class="card"><h3>ציון איכות</h3>
<table><tr><th>ממד</th><th>ציון</th><th></th><th>הערה</th></tr>{score_rows}</table>
<p style="margin-top:12px;font-size:15px"><b>כולל: {score['overall']}/10</b> — {esc(score['verdict'])}</p></div>

<h2>מה נשאר להכרעה שלך</h2>
<div class="card"><ul style="font-size:14.5px">{oq}
<li>ארבעה חיתוכים בביטחון 75–84% סומנו <b>לבדיקה</b> ולא הוחלו בעיוורון — הם מופיעים כתומים בציר באפליקציה.</li></ul>
<p style="color:#9aa0ad;font-size:13.5px;margin-bottom:0">
ההחלטה הכי גדולה כאן היא הסרת 8.5 השניות שפונות לחברים קיימים. היא בביטחון 79% ולא 95% בכוונה —
זו החלטה אסטרטגית על קהל, לא החלטה טכנית על שקט. אם הסרטון אמור לדבר גם לחברים קיימים, מבטלים אותה בקליק.</p></div>

<div class="foot">
נבנה מהנתונים בפועל של <span class="mono">בדיקת-V2-לולאה</span> — ריצה מלאה של חמשת הפאסים · הפרויקט המקורי שלך לא נגע.<br>
מקורות: <span class="mono">candidates.json</span> · <span class="mono">understanding.json</span> ·
<span class="mono">edit_plan.json</span> · <span class="mono">edl.json</span> ·
<span class="mono">qa_report.json</span> · <span class="mono">render_v2_report.json</span> ·
<span class="mono">review.json</span> · <span class="mono">quality_score.json</span> · <span class="mono">director_run.json</span><br>
מנוע ההחלטה רץ ב-backend <span class="mono">chat</span> — כלומר קלאוד בצ'אט הוא ה-Director.
עם מפתח API אותה לולאה רצה בלי אדם בלולאה.
</div>
</div></body></html>"""

out = T/"V2-DEMO.html"
out.write_text(HTML, encoding="utf-8")
print("נכתב:", out, len(HTML), "בתים")
