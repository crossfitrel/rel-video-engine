"""gen.py — הרצת גנרציה אחת תחת שומר התקציב, עם רישום מלא ב-ledger."""
from __future__ import annotations
import json, time
from pathlib import Path
import hf_client as hf
from budget import Ledger, BudgetExceeded


def run(ledger: Ledger, role: str, shot: str, model: str, body: dict, out: Path,
        retry_risk: float, attempt: int = 1, note: str = "", fallback_usd: float | None = None) -> Path:
    """fallback_usd: מחיר שמרני (מחירון רשמי, לפני הנחה) למודלים ש-/estimate שלהם מחזיר 500/תיאור בלבד
    (נמדד 25.9.26: kling o3/omni video-edit). בלי מחיר ידוע — לא מריצים."""
    try:
        usd = hf.estimate(model, body)["usd"]
    except hf.HFError:
        usd = None
    if usd is None:
        usd = fallback_usd
    if usd is None:
        raise RuntimeError(f"אין estimate מספרי ל-{model} — לא מריצים בלי מחיר ידוע")
    guard = ledger.check(role, usd, retry_risk)          # זורק BudgetExceeded
    t0 = time.time()
    try:
        job = hf.submit(model, body)
    except hf.NoCredits:
        ledger.record(role=role, shot=shot, model=model, attempt=attempt, status="blocked_no_credits",
                      est_usd=usd, charged_usd=0.0, body=body, note="403 not_enough_credits — טעינת יתרה דורשת אישור הראל")
        raise
    rid = job["request_id"]
    ledger.record(role=role, shot=shot, model=model, attempt=attempt, request_id=rid,
                  status="submitted", est_usd=usd, charged_usd=0.0, body=body, note=note,
                  guard=guard)
    res = hf.wait(rid)
    st = res.get("status")
    charged = usd if st == "completed" else 0.0
    entry = ledger.data["entries"][-1]
    entry.update(status=st, charged_usd=charged, secs=round(time.time() - t0, 1))
    if st != "completed":
        entry["error"] = str(res.get("error"))[:300]
        ledger.save()
        raise RuntimeError(f"{shot}: {st} {res.get('error')}")
    url = hf.result_url(res)
    hf.download(url, out)
    entry.update(output=str(out.name), result_url=url)
    ledger.save()
    return out
