"""אחרי התיקון: cover_vision.from_workdir (קוד+כיול חדשים) על כל הקאברים — קריאה בלבד.
כמה קאברים בלי ייחוס מילה (title_words ריק) ולמה; האם דגל garbled_word_title עולה על קאבר אמיתי."""
import sys, json
from pathlib import Path
S = Path(sys.argv[1]); sys.path.insert(0, str(S / "tools" / "thumbnail"))
import cover_vision as V
rows = []
for line in (S / "_opus55_wave6" / "cover_workdirs.txt").read_text(encoding="utf-8").splitlines():
    W = Path(line)
    if not (W / "cover_report.json").exists():
        continue
    r = V.from_workdir(W)
    o = (r.get("checks") or {}).get("CV5_order") or {}
    rep = json.loads((W / "cover_report.json").read_text(encoding="utf-8"))
    rows.append({"w": W.name, "title": rep.get("title"), "ok": r.get("ok"), "flags": r.get("flags"),
                 "title_words": o.get("title_words")})
empty = [x for x in rows if not x["title_words"]]
print("covers", len(rows), "blocked", [(x["w"], x["flags"]) for x in rows if x["ok"] is False])
print("garbled_word_title", [x["w"] for x in rows if "garbled_word_title" in (x["flags"] or [])])
print("no word attribution", [(x["w"], x["title"]) for x in empty])
(S / "_opus55_wave6" / "cover_verify.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
