#!/usr/bin/env python3
"""anchor_cohort.py — קוהורט עוגני-משפט לפסיקה של הראל (v9.32, 23.9.26).

B4 (האם הבירול מאייר את המילים שנאמרות מתחתיו) הוא שיפוט מודלי; עקרון 1 אוסר
לסמוך עליו בלי מדידה מול פסיקת הראל. הכלי:
  build   PROJECT...  → לכל פרויקט: anchor_request (גיליון + sha של ה-FINAL) ו-3 פריימים
                        קטנים לכל חלון ⇒ bench/anchor_cohort.json (קלט לדף הפסיקה)
  import  LABELS.json → פסיקות הראל (מדף הפסיקה) ⇒ bench/anchor_labels_harel.json,
                        נפסלות אם ה-FINAL השתנה מאז (sha) — עקרון 15
  agree               → הסכמה בין פסיקת Claude (BROLL_ANCHOR_VERDICT.json) לפסיקת הראל
                        ⇒ bench/anchor_agreement.json. B4 עובר ל-MEASURED רק עם ≥20 פסיקות
                        והסכמה ≥90% על 'לא מעוגן' (מה שהשער היה חוסם).
"""
import argparse
import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import broll_vision_qa as B          # noqa: E402

BENCH = HERE / "bench"
COHORT = BENCH / "anchor_cohort.json"
LABELS = BENCH / "anchor_labels_harel.json"
AGREE = BENCH / "anchor_agreement.json"
MIN_LABELS = 20
MIN_AGREE = 0.90


def _work_root():
    try:
        from relvid.paths import work_root
        return Path(work_root())
    except Exception:
        return Path.home() / "rel-video-work"


def _thumb(video, t, w=216):
    import cv2
    fr = B._frame(video, t)
    if fr is None:
        return None
    h = int(fr.shape[0] * w / fr.shape[1])
    ok, buf = cv2.imencode(".jpg", cv2.resize(fr, (w, h)), [cv2.IMWRITE_JPEG_QUALITY, 70])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode() if ok else None


def build(projects):
    WR = _work_root()
    out = []
    for name in projects:
        W = WR / name
        video = W / "FINAL.mp4"
        if not video.exists():
            print(f"⚠️ {name}: אין FINAL — דולג")
            continue
        req = B.anchor_request(W)
        if not req:
            print(f"⚠️ {name}: אין בירולים — דולג")
            continue
        intro, _ = B._intro(W)
        brand = B._brand(W)
        for r in req["windows"]:
            s, e = r["window"]
            shots = [_thumb(video, intro + s + (e - s) * f) for f in (0.2, 0.5, 0.8)]
            out.append({"id": f"{name}::{r['ref']}", "project": name, "ref": r["ref"],
                        "brand": brand, "file": r.get("file"), "window": [round(s, 2), round(e, 2)],
                        "sentence": r.get("sentence") or "", "final_sha": req["final_sha"],
                        "shots": [x for x in shots if x]})
        print(f"✓ {name}: {len(req['windows'])} חלונות")
    BENCH.mkdir(exist_ok=True)
    COHORT.write_text(json.dumps({"windows": out}, ensure_ascii=False), encoding="utf-8")
    print(f"קוהורט: {len(out)} חלונות מ-{len({o['project'] for o in out})} סרטונים → {COHORT}")
    return out


def import_labels(path):
    """labels: [{"id": "PROJECT::wNN", "anchored": bool, "burned_text": bool,
    "harel_in_frame": bool, "final_sha": "..."}] — מה שדף הפסיקה שומר."""
    WR = _work_root()
    got = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = got.get("labels", got) if isinstance(got, dict) else got
    keep, stale = [], []
    for r in rows:
        proj = r["id"].split("::")[0]
        if B._sha(WR / proj / "FINAL.mp4") != r.get("final_sha"):
            stale.append(r["id"])
            continue
        if not isinstance(r.get("anchored"), bool):
            continue
        keep.append(r)
    old = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.exists() else {"labels": []}
    by = {x["id"]: x for x in old.get("labels", [])}
    by.update({x["id"]: x for x in keep})
    LABELS.write_text(json.dumps({"labels": list(by.values()), "stale_rejected": stale},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"פסיקות הראל: {len(keep)} נקלטו · {len(stale)} נפסלו (FINAL השתנה) · סה\"כ {len(by)}")
    return by


def agree():
    WR = _work_root()
    labels = json.loads(LABELS.read_text(encoding="utf-8"))["labels"] if LABELS.exists() else []
    pairs = []
    for lab in labels:
        proj, ref = lab["id"].split("::")
        vf = WR / proj / "BROLL_ANCHOR_VERDICT.json"
        if not vf.exists():
            continue
        v = json.loads(vf.read_text(encoding="utf-8"))
        if v.get("final_sha") != lab.get("final_sha"):
            continue
        m = {w["ref"]: w for w in v.get("windows", [])}.get(ref)
        if m is not None:
            pairs.append((bool(m.get("anchored")), bool(lab["anchored"]), lab["id"]))
    n = len(pairs)
    agree_all = sum(1 for c, h, _ in pairs if c == h) / n if n else None
    neg = [(c, h) for c, h, _ in pairs if not c]          # מה ש-Claude היה חוסם
    prec_neg = sum(1 for c, h in neg if not h) / len(neg) if neg else None
    measured = bool(n >= MIN_LABELS and prec_neg is not None and prec_neg >= MIN_AGREE)
    rep = {"n": n, "agreement": agree_all, "not_anchored_precision": prec_neg,
           "n_claude_not_anchored": len(neg), "measured": measured,
           "disagreements": [i for c, h, i in pairs if c != h],
           "rule": f"B4 עובר ל-MEASURED רק עם ≥{MIN_LABELS} פסיקות והסכמה ≥{MIN_AGREE:.0%} על 'לא מעוגן'"}
    AGREE.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False))
    return rep


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("projects", nargs="+")
    i = sub.add_parser("import"); i.add_argument("labels")
    sub.add_parser("agree")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.projects)
    elif a.cmd == "import":
        import_labels(a.labels)
    else:
        agree()


if __name__ == "__main__":
    main()
