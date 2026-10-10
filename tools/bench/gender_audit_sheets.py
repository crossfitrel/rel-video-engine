#!/usr/bin/env python3
"""בונה גיליונות-מגע לאימות ויזואלי של מגדר בבריכת הבירולים (v9.7).

הרקע: 34/34 בבריכה המאומתת מתויגים 'נשים'. הבעיה אינה בקוד אלא בקוריישן.
הכלי הזה מוציא פריימים מכל מועמד בספריית המועדון ומרכיב גיליונות ממוספרים,
כדי שהאימות ייעשה על **מה שרואים בפריים** ולא על שם הקובץ.

  python3 tools/bench/gender_audit_sheets.py --out _work/.gender-audit
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
sys.path.insert(0, str(TOOLS))

CFG = TOOLS / "broll-catalog-config.json"
CLUB_LIBS = {"קרוספיט אריאל", "כללי-ומגוון", "כלליים", ""}
COLS, ROWS = 6, 4
CELL_W, CELL_H = 300, 533


def library_of(item: dict) -> str:
    tail = item["path"].split("/בירולים/")[-1]
    return tail.split("/")[0] if "/" in tail else ""


def candidates(cfg: dict) -> list[dict]:
    cat = json.loads(Path(cfg["catalog_path"]).read_text(encoding="utf-8"))["items"]
    dis = {d.get("file") for d in cfg.get("disabled_files", []) if d.get("file")}
    harel = {d.get("file") for d in cfg.get("harel_present_files", []) if d.get("file")}
    out = []
    for i in cat:
        if library_of(i) not in CLUB_LIBS:
            continue
        if i["file"] in dis or i["file"] in harel:
            continue
        if "הראל-חיון" in (i.get("tags") or []):
            continue
        out.append(i)
    out.sort(key=lambda i: (i.get("category") or "", i["file"]))
    return out


def grab(item: dict, dest: Path) -> bool:
    """פריים מאמצע הקליפ — לא מהפריים הראשון, שלרוב עוד בתנועה/מטושטש."""
    if dest.exists():
        return True
    at = max(0.2, float(item.get("dur") or 2.0) * 0.45)
    cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{at:.2f}",
           "-i", item["path"], "-frames:v", "1",
           # שוליים של 4px סופגים את עיגול ה-scale — בלעדיהם pad נכשל על
           # "Padded dimensions cannot be smaller than input dimensions"
           "-vf", f"scale={CELL_W - 4}:{CELL_H - 4}:force_original_aspect_ratio=decrease,"
                  f"pad={CELL_W}:{CELL_H}:(ow-iw)/2:(oh-ih)/2:black",
           "-y", str(dest)]
    return subprocess.run(cmd, capture_output=True).returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    items = candidates(cfg)
    out = Path(args.out).expanduser()
    frames = out / "frames"
    frames.mkdir(parents=True, exist_ok=True)

    index = []
    ok = []
    for n, it in enumerate(items, 1):
        f = frames / f"{n:03d}.jpg"
        if grab(it, f):
            ok.append((n, it, f))
        index.append({"n": n, "file": it["file"], "id": it["id"],
                      "category": it.get("category"), "dur": it.get("dur"),
                      "tags": it.get("tags"), "audience": it.get("audience")})
    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    # הרכבה ב-PIL ולא ב-ffmpeg: ה-build המקומי של ffmpeg נבנה בלי drawtext,
    # ובלי מספר צרוב על הפריים אי אפשר לקשר תשובה חזרה לקובץ.
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf", 46)
    except OSError:
        font = ImageFont.load_default()

    per = COLS * ROWS
    sheets = 0
    for s in range(0, len(ok), per):
        chunk = ok[s:s + per]
        sheets += 1
        sheet = Image.new("RGB", (COLS * CELL_W, ROWS * CELL_H), "black")
        draw = ImageDraw.Draw(sheet)
        for k, (n, _it, f) in enumerate(chunk):
            x, y = (k % COLS) * CELL_W, (k // COLS) * CELL_H
            sheet.paste(Image.open(f).convert("RGB"), (x, y))
            draw.rectangle([x + 6, y + 6, x + 6 + 96, y + 6 + 56], fill="black")
            draw.text((x + 14, y + 10), str(n), fill="yellow", font=font)
        sheet.save(out / f"sheet_{sheets:02d}.jpg", quality=85)

    print(f"מועמדים: {len(items)} · פריימים: {len(ok)} · גיליונות: {sheets}")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
