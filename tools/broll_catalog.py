#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll_catalog.py — קטלוג ספריית הבירולים של R.E.L (מקור אמת: broll-catalog-config.json)

סורק את כל ה-roots, מוצא קבצי וידאו עם "בירול" בשם, מחלץ מטא-דאטה (ffprobe),
מפיק תגים אוטומטית משם הקובץ + התיקייה, וכותב catalog.json + תמונות-מגע.

הרצה (על המק או בסנדבוקס — הנתיבים בקונפיג הם נתיבי מק):
    python3 broll_catalog.py scan  [--config broll-catalog-config.json] [--no-thumbs]
    python3 broll_catalog.py list  [--tag כוח] [--audience דוספיט]
"""
import argparse, hashlib, json, os, re, subprocess, sys, time, unicodedata
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}
HERE = Path(__file__).resolve().parent

def load_config(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def norm(s):
    s = unicodedata.normalize("NFC", s)
    return s

def ffprobe(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,avg_frame_rate:format=duration,size",
           "-of", "json", str(path)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        d = json.loads(out.stdout or "{}")
        st = (d.get("streams") or [{}])[0]
        fmt = d.get("format") or {}
        fr = st.get("avg_frame_rate", "0/1")
        try:
            a, b = fr.split("/"); fps = round(float(a) / float(b), 2) if float(b) else 0.0
        except Exception:
            fps = 0.0
        return {
            "dur": round(float(fmt.get("duration", 0.0)), 2),
            "w": st.get("width", 0), "h": st.get("height", 0),
            "fps": fps, "size_mb": round(int(fmt.get("size", 0)) / 1048576, 1),
        }
    except Exception as e:
        return {"dur": 0.0, "w": 0, "h": 0, "fps": 0.0, "size_mb": 0.0, "probe_error": str(e)[:120]}

NAME_RE = re.compile(r"בירול\s+(?P<event>.+?)\s*-\s*(?P<num>\d+)?\s*(?P<desc>.*?)\.(mp4|mov|m4v|webm)$", re.IGNORECASE)

def parse_name(fname):
    m = NAME_RE.search(fname)
    if m:
        return (m.group("event") or "").strip(), (m.group("num") or "").strip(), (m.group("desc") or "").strip()
    base = re.sub(r"\.(mp4|mov|m4v|webm)$", "", fname, flags=re.I)
    base = re.sub(r"^בירול\s*", "", base)
    return base.strip(), "", base.strip()

def derive_tags(rel_path, event, desc):
    tags, audience = set(), set()
    text = f"{rel_path} {event} {desc}"
    # תגים = מילות התיאור (ללא מילות קישור)
    for w in re.split(r"[\s\-_()]+", desc):
        w = w.strip(".,'\"")
        if len(w) >= 2 and not w.isdigit():
            tags.add(w)
    if "Throwdown" in text or "תחרות" in text:
        tags.add("Throwdown"); tags.add("תחרות")
    if "דוספיט" in text:
        audience.add("דוספיט")
    if re.search(r"נשים בלבד|נשים-בלבד", text):
        audience.add("נשים")
    if re.search(r"גברים בלבד|גברים-בלבד", text):
        audience.add("גברים")
    if "נשים-בהריון" in text or "נשים בהריון" in text or "הריון" in text:
        tags.add("נשים-בהריון"); audience.add("נשים")
    if "ילדים" in text:
        tags.add("ילדים")
    if "שיקום" in text or "אבחון" in text:
        tags.add("שיקום")
    return sorted(tags), sorted(audience)

def clip_id(path_str):
    return hashlib.sha1(norm(path_str).encode("utf-8")).hexdigest()[:12]

def scan(cfg, thumbs=True):
    roots = [Path(r) for r in cfg["roots"]]
    excludes = cfg.get("exclude_dir_substrings", [])
    items, seen_names = [], {}
    for root in roots:
        if not root.exists():
            print(f"WARN: root לא קיים: {root}", file=sys.stderr); continue
        for p in sorted(root.rglob("*")):
            if p.suffix.lower() not in VIDEO_EXT or not p.is_file():
                continue
            name = norm(p.name)
            # רק נכסים מוכנים: "בירול" חייב להיות בשם *הקובץ* (raw כמו IMG_*.mov = backlog, לא קטלוג)
            if "בירול" not in name:
                continue
            if name.startswith("._"):
                continue
            rel = str(p)
            if any(x in rel for x in excludes):
                continue
            meta = ffprobe(p)
            event, num, desc = parse_name(name)
            tags, audience = derive_tags(rel, event, desc)
            cid = clip_id(rel)
            item = {
                "id": cid, "path": rel, "file": name,
                "event": event, "num": num, "desc": desc,
                "tags": tags, "audience": audience,
                "category": norm(p.parent.name),
                **meta,
                "vertical": bool(meta["h"] and meta["h"] > meta["w"]),
                "mtime": int(p.stat().st_mtime),
            }
            items.append(item)
            seen_names.setdefault(name, []).append(rel)
    # כפילויות שם (גרסאות ישנות בסבבים שונים)
    dups = {k: v for k, v in seen_names.items() if len(v) > 1}
    # overrides ידניים
    ov_path = HERE / "broll-tags-override.json"
    if ov_path.exists():
        ov = json.loads(ov_path.read_text(encoding="utf-8"))
        for it in items:
            extra = ov.get(it["id"]) or ov.get(it["file"])
            if extra:
                it["tags"] = sorted(set(it["tags"]) | set(extra.get("tags", [])))
                it["audience"] = sorted(set(it["audience"]) | set(extra.get("audience", [])))
                # v9.7: `people` = **מי נראה בפריים**, לעומת `audience` = **למי הקליפ
                # מיועד** (קבוצה מגדרית נפרדת / דוספיט), שהוא פילטר בחירה קשיח
                # ב-broll_pick. שני מושגים שונים — שדה אחד לשניהם היה יוצר באג
                # שקט: קליף משיעור מעורב שבו מופיע גבר היה מסומן כתוכן
                # "גברים בלבד" ונחסם מסרטון שמכוון לנשים. `people` נקבע רק
                # באימות ויזואלי, לעולם לא נגזר משם הקובץ.
                if extra.get("people"):
                    it["people"] = sorted(set(it.get("people") or [])
                                          | set(extra["people"]))
    catalog = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(items),
        "duplicates": dups,
        "items": sorted(items, key=lambda x: (x["event"], x.get("num") or "", x["file"])),
    }
    out = Path(cfg["catalog_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, out)
    print(f"CATALOG OK: {len(items)} בירולים → {out}")
    if dups:
        print(f"⚠️  {len(dups)} שמות כפולים (גרסאות ישנות?) — ראה catalog.duplicates")
    if thumbs:
        make_thumbs(cfg, items)
    return catalog

def make_thumbs(cfg, items):
    tdir = Path(cfg["thumbs_dir"]); tdir.mkdir(parents=True, exist_ok=True)
    made = 0
    for it in items:
        tp = tdir / f"{it['id']}.jpg"
        if tp.exists():
            continue
        ts = max(0.5, it["dur"] * 0.4)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{ts:.2f}", "-i", it["path"],
               "-frames:v", "1", "-vf", "scale=270:-2", str(tp)]
        try:
            subprocess.run(cmd, capture_output=True, timeout=60); made += 1
        except Exception:
            pass
    # index.html פשוט לצפייה
    rows = []
    for it in items:
        rows.append(
            f"<div style='display:inline-block;width:280px;margin:6px;text-align:center;font-family:sans-serif'>"
            f"<img src='_catalog_thumbs/{it['id']}.jpg' width='270' style='border-radius:8px'><br>"
            f"<b>{it['file']}</b><br><small>{it['dur']}s · {it['category']} · {', '.join(it['tags'][:5])}</small></div>")
    idx = Path(cfg["catalog_path"]).parent / "catalog.html"
    idx.write_text("<html dir='rtl'><body style='background:#111;color:#eee'>" + "\n".join(rows) + "</body></html>", encoding="utf-8")
    print(f"THUMBS: {made} חדשות · אינדקס: {idx}")

def list_items(cfg, tag=None, audience=None):
    cat = json.loads(Path(cfg["catalog_path"]).read_text(encoding="utf-8"))
    for it in cat["items"]:
        if tag and tag not in it["tags"] and tag not in it["event"]:
            continue
        if audience and audience not in it["audience"]:
            continue
        print(f"{it['id']}  {it['dur']:5.1f}s  {it['file']}  [{', '.join(it['tags'][:6])}]")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["scan", "list"])
    ap.add_argument("--config", default=str(HERE / "broll-catalog-config.json"))
    ap.add_argument("--no-thumbs", action="store_true")
    ap.add_argument("--tag"); ap.add_argument("--audience")
    a = ap.parse_args()
    cfg = load_config(a.config)
    if a.cmd == "scan":
        scan(cfg, thumbs=not a.no_thumbs)
    else:
        list_items(cfg, a.tag, a.audience)

if __name__ == "__main__":
    main()
