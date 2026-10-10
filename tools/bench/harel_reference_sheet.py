#!/usr/bin/env python3
"""גיליון-ייחוס: איך הראל נראה. נדרש לפני אימות מגדר/מתאמן.

בלי הייחוס הזה, אימות "מתאמן או הראל?" הוא ניחוש — וזו בדיוק הטעות
שהולידה את `verified_member_files` ב-26.7.26.
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
    cat = json.loads(Path(cfg["catalog_path"]).read_text(encoding="utf-8"))["items"]
    harel_named = {d["file"] for d in cfg.get("harel_present_files", [])}
    pool = [i for i in cat
            if G.library_of(i) == "הראל חיון" or i["file"] in harel_named]
    pool.sort(key=lambda i: i["file"])
    pool = pool[:24]

    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf", 46)
    sheet = Image.new("RGB", (G.COLS * G.CELL_W, G.ROWS * G.CELL_H), "black")
    draw = ImageDraw.Draw(sheet)
    for k, it in enumerate(pool):
        f = out / "frames" / f"h{k:02d}.jpg"
        if not G.grab(it, f):
            continue
        x, y = (k % G.COLS) * G.CELL_W, (k // G.COLS) * G.CELL_H
        sheet.paste(Image.open(f).convert("RGB"), (x, y))
        draw.rectangle([x + 6, y + 6, x + 100, y + 60], fill="black")
        draw.text((x + 14, y + 10), str(k + 1), fill="cyan", font=font)
    sheet.save(out / "harel_reference.jpg", quality=85)
    print(f"ייחוס הראל: {len(pool)} קליפים → {out / 'harel_reference.jpg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
