#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
revisions — מנוע גרסאות לא-הרסני ל-EDL + תמליל (v7).
=====================================================
כל שינוי מהותי יוצר revision חדש: snapshot מלא של edl.json + הטקסט המתוקן,
עם parent, actor, summary, policy_version ו-hashes. שום revision לא נמחק;
revision שאושר (approved) מסומן ולעולם לא נדרס.

מבנה בדיסק (בתוך _work/{שם}/):
  revisions/rev_0001_ab12cd34ef56.json   — snapshot מלא
  revisions/index.json                   — {"head": id, "order": [...], "redo": [...]}
"""
import re
from pathlib import Path

from . import (atomic_write_json, atomic_write_text, new_id, now_ts,
               read_json, sha256_file, sha256_json, policy_version)
from .edl_utils import edl_change_summary

REV_DIR = "revisions"


def _rdir(workdir):
    d = Path(workdir) / REV_DIR
    d.mkdir(exist_ok=True)
    return d


def _index(workdir):
    return read_json(_rdir(workdir) / "index.json",
                     {"head": None, "order": [], "redo": []})


def _save_index(workdir, idx):
    atomic_write_json(_rdir(workdir) / "index.json", idx)


def _rev_path(workdir, rev_id):
    # rev_id הוא בפורמט rev_<hex>; שם הקובץ rev_<seq>_<hex>.json
    d = _rdir(workdir)
    hexpart = rev_id.replace("rev_", "")
    hits = sorted(d.glob(f"rev_*_{hexpart}.json"))
    return hits[0] if hits else None


def get_revision(workdir, rev_id):
    p = _rev_path(workdir, rev_id)
    return read_json(p) if p else None


def list_revisions(workdir):
    idx = _index(workdir)
    out = []
    for rid in idx["order"]:
        r = get_revision(workdir, rid)
        if r:
            out.append({k: r.get(k) for k in
                        ("revision_id", "parent_revision_id", "ts", "actor",
                         "summary", "approved", "policy_version", "edl_hash",
                         "kept_dur")})
    return {"head": idx["head"], "revisions": out}


def _read_transcript(workdir):
    w = Path(workdir)
    for cand in ("edited.txt", "correct_transcript.txt"):
        if (w / cand).exists():
            return cand, (w / cand).read_text(encoding="utf-8")
    return None, ""


def head(workdir):
    return _index(workdir)["head"]


def head_edl_hash(workdir):
    h = head(workdir)
    if not h:
        edl = read_json(Path(workdir) / "edl.json")
        return sha256_json(edl) if edl else None
    r = get_revision(workdir, h)
    return r.get("edl_hash") if r else None


def create_revision(workdir, actor, summary, actions=None, approved=False):
    """יוצר revision מהמצב הנוכחי על הדיסק (אחרי שהקבצים כבר נכתבו)."""
    w = Path(workdir)
    edl = read_json(w / "edl.json")
    if edl is None:
        raise FileNotFoundError("אין edl.json — אי אפשר ליצור revision")
    t_src, t_text = _read_transcript(w)
    idx = _index(w)
    seq = len(idx["order"]) + 1
    rid = new_id("rev")
    rev = {
        "revision_id": rid,
        "parent_revision_id": idx["head"],
        "seq": seq,
        "ts": now_ts(),
        "actor": actor,
        "summary": summary or "",
        "approved": bool(approved),
        "policy_version": policy_version(),
        "input_hash": sha256_file(w / "INPUT.mp4"),
        "edl_hash": sha256_json(edl),
        "kept_dur": edl.get("kept_dur"),
        "edl": edl,
        "transcript_source": t_src,
        "transcript": t_text,
        "transcript_hash": sha256_json(t_text),
        "actions": actions or [],
        "output_hash": sha256_file(w / "PREVIEW.mp4"),
    }
    hexpart = rid.replace("rev_", "")
    atomic_write_json(_rdir(w) / f"rev_{seq:04d}_{hexpart}.json", rev)
    idx["order"].append(rid)
    idx["head"] = rid
    idx["redo"] = []          # שינוי חדש מוחק את מסלול ה-redo
    _save_index(w, idx)
    return rid


def ensure_baseline(workdir):
    """אם אין אף revision — יוצר revision-בסיס מהמצב הנוכחי (גרסת המכונה)."""
    w = Path(workdir)
    if _index(w)["order"]:
        return None
    if not (w / "edl.json").exists():
        return None
    return create_revision(w, actor="machine", summary="baseline (גרסת המכונה)")


def _restore_files(workdir, rev):
    """כותב את ה-snapshot חזרה ל-edl.json + טקסט. לא נוגע במדיה."""
    w = Path(workdir)
    atomic_write_json(w / "edl.json", rev["edl"])
    if rev.get("transcript_source"):
        atomic_write_text(w / rev["transcript_source"], rev.get("transcript") or "")


def undo(workdir):
    """מחזיר את ה-head ל-parent ומשחזר קבצים. ה-revision עצמו לא נמחק."""
    w = Path(workdir)
    idx = _index(w)
    if not idx["head"]:
        return {"ok": False, "error": "אין revisions"}
    cur = get_revision(w, idx["head"])
    parent = cur.get("parent_revision_id")
    if not parent:
        return {"ok": False, "error": "כבר בגרסת הבסיס"}
    prev = get_revision(w, parent)
    if not prev:
        return {"ok": False, "error": f"revision הורה חסר: {parent}"}
    _restore_files(w, prev)
    idx["redo"].append(idx["head"])
    idx["head"] = parent
    _save_index(w, idx)
    return {"ok": True, "head": parent, "summary": prev.get("summary")}


def redo(workdir):
    w = Path(workdir)
    idx = _index(w)
    if not idx["redo"]:
        return {"ok": False, "error": "אין מה לבצע מחדש"}
    rid = idx["redo"].pop()
    rev = get_revision(w, rid)
    if not rev:
        return {"ok": False, "error": f"revision חסר: {rid}"}
    _restore_files(w, rev)
    idx["head"] = rid
    _save_index(w, idx)
    return {"ok": True, "head": rid, "summary": rev.get("summary")}


def restore(workdir, rev_id, actor="harel"):
    """שחזור לא-הרסני: משחזר snapshot ישן ויוצר עליו revision חדש."""
    w = Path(workdir)
    rev = get_revision(w, rev_id)
    if not rev:
        return {"ok": False, "error": f"revision לא נמצא: {rev_id}"}
    _restore_files(w, rev)
    new_rid = create_revision(w, actor=actor,
                              summary=f"שחזור של {rev_id} ({rev.get('summary', '')[:60]})")
    return {"ok": True, "head": new_rid, "restored_from": rev_id}


def compare(workdir, rev_a, rev_b):
    a, b = get_revision(workdir, rev_a), get_revision(workdir, rev_b)
    if not a or not b:
        return {"ok": False, "error": "revision חסר"}
    summ = edl_change_summary(a["edl"], b["edl"])
    ta = (a.get("transcript") or "").split()
    tb = (b.get("transcript") or "").split()
    changed_words = sum(1 for x, y in zip(ta, tb) if x != y) + abs(len(ta) - len(tb))
    summ["transcript_words_changed"] = changed_words
    return {"ok": True, "from": rev_a, "to": rev_b, "summary": summ}


def mark_approved(workdir, rev_id=None):
    """מסמן revision (ברירת מחדל: head) כמאושר — לא יידרס ולא יימחק."""
    w = Path(workdir)
    rid = rev_id or head(w)
    if not rid:
        return None
    p = _rev_path(w, rid)
    rev = read_json(p)
    if rev is None:
        return None
    rev["approved"] = True
    rev["approved_at"] = now_ts()
    atomic_write_json(p, rev)
    return rid
