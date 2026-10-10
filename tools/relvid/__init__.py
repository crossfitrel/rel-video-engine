#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
relvid — ספריית הליבה של מערכת עריכת הסושיאל v7 (CrossFit R.E.L).
=================================================================
stdlib בלבד. כל כתיבה מהותית אטומית. כל מודול כאן נצרך גם ע"י review-app
וגם ע"י ה-CLI (review_cli / project_registry / run_finish / system_doctor).
"""
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent          # tools/relvid
TOOLS = PKG_DIR.parent                             # tools/
SYSDIR = TOOLS.parent                              # Social Video Editing System
# v8.6 (P0-11): נתיב תיקיית העבודה נפתר דרך relvid.paths (env → tools/paths.json →
# ברירת מחדל היסטורית SYSDIR/_work). WORK נשאר קיים לתאימות עם כל הקוראים, אבל
# מחושב ולא מקובע — בלי paths.json ההתנהגות זהה לחלוטין לקודם.
from .paths import work_root as _work_root          # noqa: E402
WORK = _work_root()
INDEX_DIR = WORK / ".index"
POLICY_PATH = TOOLS / "edl-policy.json"

SCHEMA_VERSION = 1
PIPELINE_VERSION = "v7.0"


def now_ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path, data):
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=1))


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def sha256_file(path, quick=True):
    """hash לקובץ. quick=True לקבצי מדיה גדולים: גודל + 1MB ראשון + 1MB אחרון
    (מספיק לזיהוי החלפת-מקור, בלי לקרוא ג'יגות)."""
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    size = p.stat().st_size
    if not quick or size <= 4 * 1024 * 1024:
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return "sha256:" + h.hexdigest()
    h.update(str(size).encode())
    with open(p, "rb") as f:
        h.update(f.read(1024 * 1024))
        f.seek(-1024 * 1024, os.SEEK_END)
        h.update(f.read(1024 * 1024))
    return "quick:" + h.hexdigest()


def sha256_json(obj):
    """hash קנוני לאובייקט JSON (sorted keys)."""
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def policy_version():
    pol = read_json(POLICY_PATH, {}) or {}
    return str(pol.get("version", "unversioned"))


def append_jsonl(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False
