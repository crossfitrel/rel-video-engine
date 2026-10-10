#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hook_sfx_import.py — ספריית צלילי ההוק (v9.46, 8.10.26).

מוריד (או קורא מקומית) צלילים נבחרים מ-Mixkit (Mixkit Free License: שימוש מסחרי ברשתות/מודעות,
בלי קרדיט — https://mixkit.co/license/), חותך לפי onset, מנרמל ל-‎-16 LUFS, מודד איפה השיא,
וכותב tools/motion/sfx/hook/<role>_<n>.wav + catalog.json. hook_fx.py מיישר כל צליל לפי peak_at
(riser — לפי הסוף), ולכן "מכה על הפריים" נוחתת על הפריים ולא 0.3ש אחריו.

שימוש:  ~/.rel-whisper/bin/python tools/hook_sfx_import.py [--src DIR_WITH_MP3S]
"""
import argparse, json, re, subprocess, sys, wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "motion" / "sfx" / "hook"
TARGET_LUFS = -16.0
# role → [(mixkit_id, title, start_pad_or_None, max_dur)] — נבחרו בהאזנה-מדידה (onset/peak/tail) 8.10.26.
# בלי קרטון/אימה/8-bit; קצר ונקי, מתאים לרחבה ולמותג.
PICK = {
    "swish":   [(1492, "Cinematic whoosh fast transition", None, 1.3), (1490, "Fast whoosh transition", None, 0.9),
                (166, "Fast small sweep transition", None, 0.75), (168, "Fast air sweep transition", None, 0.8)],
    "zoom":    [(2608, "Air zoom vacuum", None, 0.9), (772, "Quick zoom impact", None, 1.0)],
    "impact":  [(1143, "Cinematic whoosh deep impact", None, 2.2), (2299, "Short bass hit", None, 1.0),
                (2908, "Movie trailer epic impact", None, 2.6), (2300, "Knocking sub bass", 0.95, 1.6)],
    "riser":   [(790, "Cinematic trailer riser", None, 2.6), (1144, "Short space stutter intro riser", 3.4, 3.2)],
    "rewind":  [(1092, "Fast tape rewind cinematic transition", None, 1.9)],
    "scratch": [(704, "Vinyl stop fast scratch", None, 0.7), (702, "Record player vinyl scratch", None, 1.1)],
    "shutter": [(1430, "Camera shutter hard click", None, 0.5)],
}
ALIGN = {"riser": "end"}          # riser נגמר על הרגע; כל השאר — השיא על הרגע


def sh(cmd):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, stdin=subprocess.DEVNULL)


def lufs(path) -> float:
    r = sh(["ffmpeg", "-nostdin", "-i", path, "-af", "ebur128", "-f", "null", "-"])
    v = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(v[-1]) if v else -70.0


def load(path):
    w = wave.open(str(path))
    n = w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).reshape(-1, 2).astype(np.float64) / 32768.0
    return x


def envelope(x, hop=480):
    m = x.mean(1)
    e = np.sqrt(np.convolve(m ** 2, np.ones(hop) / hop, "same"))
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(Path.home() / "rel-video-work" / "_hook_fx" / "mixkit" / "raw"))
    a = ap.parse_args()
    src = Path(a.src)
    OUT.mkdir(parents=True, exist_ok=True)
    cat = {"_doc": "צלילי ההוק — Mixkit Free License (מסחרי, בלי קרדיט). peak_at = שניות מתחילת הקובץ לשיא "
                   "(riser: align=end). מנורמלים ל-‎-16 LUFS; hook_fx.py קובע עוצמה יחסית לדיבור.",
           "license": "Mixkit Free License — https://mixkit.co/license/ (מאומת 8.10.26 דרך mixkit.co/llm-info)",
           "target_lufs": TARGET_LUFS, "items": []}
    for role, items in PICK.items():
        for n, (mid, title, start_pad, max_dur) in enumerate(items, 1):
            mp3 = src / f"{mid}.mp3"
            if not mp3.exists():
                u = f"https://assets.mixkit.co/active_storage/sfx/{mid}/{mid}-preview.mp3"
                r = sh(["curl", "-sS", "--max-time", "30", "-o", mp3, u])
                if r.returncode != 0 or not mp3.exists():
                    print(f"✗ {role} {mid}: הורדה נכשלה"); continue
            tmp = OUT / f"_tmp_{mid}.wav"
            sh(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", mp3, "-ar", "48000", "-ac", "2", tmp])
            x = load(tmp)
            env = envelope(x)
            on = int(np.argmax(env > 0.08 * env.max()))
            start = max(0, on - int(0.03 * 48000)) if start_pad is None else int(start_pad * 48000)
            end = min(len(x), start + int(max_dur * 48000))
            seg = x[start:end].copy()
            fo = min(len(seg), int(0.06 * 48000))
            seg[-fo:] *= np.linspace(1, 0, fo)[:, None]
            fi = min(len(seg), int(0.004 * 48000))
            seg[:fi] *= np.linspace(0, 1, fi)[:, None]
            key = f"{role}_{n}"
            raw = OUT / f"_raw_{key}.wav"
            with wave.open(str(raw), "wb") as w:
                w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
                w.writeframes((np.clip(seg, -1, 1) * 32767).astype(np.int16).tobytes())
            L = lufs(raw)
            g = TARGET_LUFS - L
            dst = OUT / f"{key}.wav"
            sh(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", raw,
                "-af", f"volume={g:.2f}dB,alimiter=limit=0.89:level=disabled", "-ar", "48000", "-ac", "2", dst])
            y = load(dst)
            e2 = envelope(y)
            pk = int(np.argmax(e2))
            item = {"key": key, "role": role, "file": dst.name, "dur": round(len(y) / 48000, 3),
                    "peak_at": round(pk / 48000, 3), "align": ALIGN.get(role, "peak"),
                    "lufs": round(lufs(dst), 1), "source": f"mixkit:{mid} — {title}"}
            cat["items"].append(item)
            for p in (tmp, raw):
                p.unlink(missing_ok=True)
            print(f"✓ {key:10} {item['dur']:.2f}s peak@{item['peak_at']:.2f} {item['lufs']} LUFS  ← {title}")
    (OUT / "catalog.json").write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"catalog: {len(cat['items'])} צלילים → {OUT / 'catalog.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
