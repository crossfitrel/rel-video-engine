#!/usr/bin/env python3
"""אימות ברזולוציה גבוהה לקליפים שנבחרו — 6 בגיליון, 3 פריימים לקליפ.

פריים בודד אינו מספיק כדי להכריע "מתאמן או הראל" ולא "יחיד או שיעור מלא".
שלושה פריימים לאורך הקליפ (25%/50%/75%) מראים גם מי בפריים וגם מה קורה בו.

  python3 tools/bench/verify_picks_sheet.py OUT 27,28,31,...
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gender_audit_sheets as G  # noqa: E402

W, H = 320, 569          # פריים בודד
COLS, ROWS = 3, 2        # 6 קליפים בגיליון, 3 פריימים כל אחד


def strip(item: dict, n: int, out: Path) -> Path | None:
    """רצועה אופקית של 3 פריימים מהקליפ."""
    from PIL import Image
    dur = float(item.get("dur") or 3.0)
    frames = []
    for k, frac in enumerate((0.25, 0.5, 0.75)):
        f = out / "frames" / f"v{n:03d}_{k}.jpg"
        if not f.exists():
            cmd = ["ffmpeg", "-nostdin", "-loglevel", "error",
                   "-ss", f"{max(0.1, dur * frac):.2f}", "-i", item["path"],
                   "-frames:v", "1",
                   "-vf", f"scale={W - 4}:{H - 4}:force_original_aspect_ratio=decrease,"
                          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black",
                   "-y", str(f)]
            if subprocess.run(cmd, capture_output=True).returncode:
                return None
        frames.append(f)
    band = Image.new("RGB", (W * 3, H), "black")
    for k, f in enumerate(frames):
        band.paste(Image.open(f).convert("RGB"), (k * W, 0))
    return band


def main() -> int:
    out = Path(sys.argv[1]).expanduser()
    nums = [int(x) for x in sys.argv[2].split(",")]
    (out / "frames").mkdir(parents=True, exist_ok=True)

    idx = {i["n"]: i for i in json.loads(
        (Path("~/rel-video-work/.gender-audit/index.json").expanduser())
        .read_text(encoding="utf-8"))}
    cfg = json.loads(G.CFG.read_text(encoding="utf-8"))
    cat = {i["file"]: i for i in
           json.loads(Path(cfg["catalog_path"]).read_text(encoding="utf-8"))["items"]}

    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf", 44)

    per = COLS * ROWS
    for s in range(0, len(nums), per):
        chunk = nums[s:s + per]
        sheet = Image.new("RGB", (COLS * W * 3, ROWS * H), "black")
        draw = ImageDraw.Draw(sheet)
        for k, n in enumerate(chunk):
            band = strip(cat[idx[n]["file"]], n, out)
            if band is None:
                continue
            x, y = (k % COLS) * W * 3, (k // COLS) * H
            sheet.paste(band, (x, y))
            draw.rectangle([x + 6, y + 6, x + 110, y + 62], fill="black")
            draw.text((x + 14, y + 10), str(n), fill="yellow", font=font)
        sheet.save(out / f"verify_{s // per + 1:02d}.jpg", quality=88)
    print(f"אימות: {len(nums)} קליפים → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
