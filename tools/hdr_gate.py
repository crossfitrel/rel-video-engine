#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hdr_gate — שער טווח דינמי לכל גלם, לפני שהוא נכנס לפרויקט (ענן, v10).

מחליף את tonemap.swift (macOS בלבד). HDR כבוי באייפון מ-10.10.26 ⇒ גלם חדש הוא SDR.
  SDR  (bt709 / smpte170m / לא מתויג)  → עובר כמו שהוא, בלי לגעת בצבע.
  HLG  (arib-std-b67, גלם ישן)          → tonemap ב-ffmpeg בשרשרת המכוילת למטה + דגל בפלט.
  PQ   (smpte2084)                       → אותה שרשרת עם tin=smpte2084 + דגל uncalibrated (מדווח, לא חוסם).
  לא ידוע                                 → נמדד ומדווח, ממשיך כ-SDR (לא חוסם בשקט: הדגל בדוח).

כיול (10.10.26, נגזר ממדידה — לא ניחוש): זוג אמת מהמק — INPUT_HLG_backup.mp4 (HLG) מול INPUT.mp4
שעבר tonemap.swift באותו פרויקט ("טעויות נפוצות strict pull-ups", 86ש). 8 פריימים (בלי פריים שחור 0),
גריד npl∈{100..300} × אופרטור∈{hable,mobius,reinhard,clip,linear,gamma} + zscale ישיר + colorspace:
  npl=160 hable desat=0 → SSIM 0.951 · PSNR 30.0 · ‎Y‎ 101.7 מול 102.6 · SAT 21.3 מול 20.5 (הטוב ביותר)
  passthrough (תיוג בלבד) → SSIM 0.933 · PSNR 21.0 · SAT 13.1 (דהוי — זה הליקוי של L80)
  zscale ישיר בלי tonemap → SSIM 0.775 (גרוע)
הקלט בזוג הוא 8-bit מקודד מחדש, ולכן התקרה נמוכה מ-1.0; מקור 10-bit צפוי להתקרב יותר.

שימוש:
  python3 hdr_gate.py probe RAW.mov [...]               # JSON פר-קובץ, בלי לכתוב כלום
  python3 hdr_gate.py convert RAW.mov OUT.mp4 [--crf 23] # נרמול ל-1080×1920@30 + tonemap רק אם HDR
  python3 hdr_gate.py batch --out-dir W RAW1 RAW2 ...    # clip_NN.mp4 + HDR_GATE.json
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

CALIBRATION = {"date": "2026-10-10", "pair": "strict-pull-ups INPUT_HLG_backup vs tonemap.swift INPUT",
               "frames": 8, "npl": 160, "op": "hable", "ssim": 0.951, "psnr": 30.0,
               "y_mean": [101.7, 102.6], "sat_mean": [21.3, 20.5]}
NPL, OP = CALIBRATION["npl"], CALIBRATION["op"]
SDR_TRC = {"bt709", "smpte170m", "bt470bg", "bt470m", "iec61966-2-1", "gamma22", "gamma28", "unknown", "", None}

def probe(path: str) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,pix_fmt,color_transfer,color_primaries,color_space,r_frame_rate:"
                        "stream_tags=rotate:stream_side_data=rotation:format=duration",
                        "-of", "json", path], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    j = json.loads(r.stdout or "{}"); st = (j.get("streams") or [{}])[0]
    trc = st.get("color_transfer")
    kind = "hlg" if trc == "arib-std-b67" else "pq" if trc == "smpte2084" else "sdr" if trc in SDR_TRC else "unknown"
    return {"file": path, "transfer": trc, "primaries": st.get("color_primaries"), "space": st.get("color_space"),
            "pix_fmt": st.get("pix_fmt"), "w": st.get("width"), "h": st.get("height"),
            "duration": float((j.get("format") or {}).get("duration") or 0), "kind": kind}

def tonemap_chain(tin: str) -> str:
    return (f"zscale=tin={tin}:pin=bt2020:min=bt2020nc:t=linear:npl={NPL},format=gbrpf32le,"
            f"zscale=p=bt709,tonemap={OP}:desat=0,zscale=t=bt709:m=bt709:r=tv")

def convert(src: str, out: str, crf: int = 23) -> dict:
    p = probe(src)
    vf = []
    if p["kind"] == "hlg": vf.append(tonemap_chain("arib-std-b67"))
    elif p["kind"] == "pq": vf.append(tonemap_chain("smpte2084"))
    # יעד 1080×1920 לאורך; landscape נשאר בתוך מסגרת — הרקע המטושטש הוא החלטת עריכה, לא של השער
    vf.append("scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2,"
              "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p")
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", "-i", src, "-vf", ",".join(vf),
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    res = {**p, "out": out, "ok": r.returncode == 0, "err": (r.stderr or "")[-400:] if r.returncode else ""}
    res["action"] = {"sdr": "passthrough", "hlg": "tonemap_ffmpeg_v1", "pq": "tonemap_ffmpeg_v1_uncalibrated",
                     "unknown": "passthrough_unmeasured"}[p["kind"]]
    if p["kind"] in ("hlg", "pq"): res["calibration"] = CALIBRATION
    return res

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("probe"); a.add_argument("files", nargs="+")
    b = sub.add_parser("convert"); b.add_argument("src"); b.add_argument("out"); b.add_argument("--crf", type=int, default=23)
    c = sub.add_parser("batch"); c.add_argument("--out-dir", required=True); c.add_argument("files", nargs="+")
    c.add_argument("--crf", type=int, default=23)
    x = ap.parse_args()
    if x.cmd == "probe":
        print(json.dumps([probe(f) for f in x.files], ensure_ascii=False, indent=1)); return 0
    if x.cmd == "convert":
        r = convert(x.src, x.out, x.crf); print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
    W = Path(x.out_dir); W.mkdir(parents=True, exist_ok=True); rows = []
    for i, f in enumerate(x.files, 1):
        rows.append(convert(f, str(W / f"clip_{i:02d}.mp4"), x.crf))
        print(f"[hdr_gate] clip_{i:02d} ← {Path(f).name}: {rows[-1]['kind']} → {rows[-1]['action']} {'✓' if rows[-1]['ok'] else '✗'}")
    rep = {"clips": rows, "hdr_count": sum(r["kind"] in ("hlg", "pq") for r in rows),
           "unknown_count": sum(r["kind"] == "unknown" for r in rows), "ok": all(r["ok"] for r in rows)}
    (W / "HDR_GATE.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    (W / "concat.txt").write_text("".join(f"file 'clip_{i:02d}.mp4'\n" for i in range(1, len(rows) + 1)), encoding="utf-8")
    if rep["hdr_count"]: print(f"[hdr_gate] ⚑ {rep['hdr_count']} קליפים HDR עברו tonemap (ffmpeg v1) — מסומן בדוח")
    return 0 if rep["ok"] else 1

if __name__ == "__main__":
    sys.exit(main())
