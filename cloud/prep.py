#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prep — שלב 2 של ה-workflow בענן: גלם ממאנדיי → פרויקט עבודה מוכן לבמאי.

  python3 cloud/prep.py --name "<שם-תיקייה>" --item <monday_item_id> --dept "<מחלקה>" \
      --title "<כותרת>" [--content-type value|conversion] RAW1.mov RAW2.mov ...

מה קורה (דטרמיניסטי, אותם כלים כמו במק):
  1. hdr_gate batch  → clip_NN.mp4 (1080×1920@30, crf23) + HDR_GATE.json  [מחליף tonemap.swift]
  2. concat          → INPUT.mp4
  3. align_words     → whisper_raw.json (ivrit-ai turbo + VAD, ct2)
  4. edl_build       → edl.json + sentences.json + intent_card.md (טיוטת מכונה; הבמאי מכריע אחר כך)
  5. edl_cut         → ROUGH.mp4
  6. intake_guard    → orient + density (מדווח, לא חוסם)
  7. project_manifest.json עם monday_item_id/dept/title — הזהות שהגשר והגאנט נשענים עליה
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYS = HERE.parent; TOOLS = SYS / "tools"
sys.path.insert(0, str(TOOLS))
from relvid.paths import work_root          # noqa: E402
from relvid import registry as reg          # noqa: E402
PY = os.environ.get("REL_PY") or sys.executable


def run(cmd, **kw):
    t = time.time()
    r = subprocess.run([str(c) for c in cmd], stdin=subprocess.DEVNULL, capture_output=True, text=True, **kw)
    tail = (r.stdout or "")[-600:] + (r.stderr or "")[-600:]
    print(f"  [{time.time()-t:5.1f}s] {Path(str(cmd[1] if str(cmd[0]).endswith('python') or 'python' in str(cmd[0]) else cmd[0])).name} rc={r.returncode}")
    if r.returncode:
        raise SystemExit(f"נכשל: {' '.join(map(str, cmd))[:200]}\n{tail}")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True); ap.add_argument("--item", required=True)
    ap.add_argument("--dept", default=None); ap.add_argument("--title", default=None)
    ap.add_argument("--content-type", default=None); ap.add_argument("--month", default=None)
    ap.add_argument("raws", nargs="+")
    a = ap.parse_args()
    W = work_root(create=True) / a.name
    W.mkdir(parents=True, exist_ok=True)
    T0 = time.time()
    print(f"[prep] {W}")
    run([PY, TOOLS / "hdr_gate.py", "batch", "--out-dir", W, *a.raws])
    # concat — אותו מבנה כמו במק (concat.txt של קליפים מנורמלים ⇒ stream copy)
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", W / "concat.txt",
         "-c", "copy", "-movflags", "+faststart", W / "INPUT.mp4"])
    run([PY, TOOLS / "align_words.py", W / "INPUT.mp4", W / "whisper_raw.json"])
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(W / "INPUT.mp4")], capture_output=True, text=True).stdout.strip() or 0)
    run([PY, TOOLS / "edl_build.py", "--words", W / "whisper_raw.json", "--out-dir", W, "--video", W / "INPUT.mp4",
         "--end", f"{dur:.3f}"])
    run([PY, TOOLS / "edl_cut.py", "--video", W / "INPUT.mp4", "--edl", W / "edl.json", "--out", W / "ROUGH.mp4",
         "--crf", "23", "--preset", "medium"])
    # שומרי גלם (L69/L70) — מדווחים
    g = subprocess.run([PY, str(TOOLS / "intake_guard.py"), "density", "--workdir", str(W)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    (W / "intake_guard.txt").write_text((g.stdout or "") + (g.stderr or ""), encoding="utf-8")
    m = reg.ensure_manifest(W, probe=True) if hasattr(reg, "ensure_manifest") else {}
    mp = W / "project_manifest.json"
    m = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else (m or {})
    m.update({"monday_item_id": str(a.item), "dept": a.dept or m.get("dept"), "title": a.title or m.get("title"),
              "content_type": a.content_type or m.get("content_type"), "month": a.month or m.get("month"),
              "runtime": "cloud", "prep_secs": round(time.time() - T0, 1),
              "hdr": json.loads((W / "HDR_GATE.json").read_text(encoding="utf-8")).get("hdr_count", 0)})
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[prep] ✓ {a.name} · INPUT {dur:.1f}s · {time.time()-T0:.0f}s · HDR={m['hdr']}")


if __name__ == "__main__":
    main()
