#!/usr/bin/env python3
"""גיליון של הבריכה המאומתת עצמה (verified_member_files פחות disabled).

הטענה "34 מתוך 34 נשים" נגזרה מאותה היוריסטיקת-שם שהולידה את ההטיה.
לפני שמסיקים ממנה מסקנה — מסתכלים.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gender_audit_sheets as G  # noqa: E402


def main() -> int:
    out = Path(sys.argv[1]).expanduser()
    (out / "frames").mkdir(parents=True, exist_ok=True)
    cfg = json.loads(G.CFG.read_text(encoding="utf-8"))
    cat = {i["file"]: i for i in
           json.loads(Path(cfg["catalog_path"]).read_text(encoding="utf-8"))["items"]}
    dis = {d.get("file") for d in cfg.get("disabled_files", [])}
    pool = [cat[f] for f in cfg["verified_member_files"]
            if f in cat and f not in dis]

    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf", 46)
    per = G.COLS * G.ROWS
    index = []
    for s in range(0, len(pool), per):
        chunk = pool[s:s + per]
        sheet = Image.new("RGB", (G.COLS * G.CELL_W, G.ROWS * G.CELL_H), "black")
        draw = ImageDraw.Draw(sheet)
        for k, it in enumerate(chunk):
            n = s + k + 1
            index.append({"n": n, "file": it["file"]})
            f = out / "frames" / f"p{n:03d}.jpg"
            if not G.grab(it, f):
                continue
            x, y = (k % G.COLS) * G.CELL_W, (k // G.COLS) * G.CELL_H
            sheet.paste(Image.open(f).convert("RGB"), (x, y))
            draw.rectangle([x + 6, y + 6, x + 106, y + 62], fill="black")
            draw.text((x + 14, y + 10), str(n), fill="lime", font=font)
        sheet.save(out / f"pool_{s // per + 1:02d}.jpg", quality=85)
    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"בריכה מאומתת: {len(pool)} קליפים → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
