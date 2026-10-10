"""budget.py — שומר התקציב של שכבת ה-AI (תקרה קשיחה לסרטון).

כלל: לפני כל פעולה בתשלום  actual + next + retry_risk*next  ≤ cap.
אם לא — לא ממשיכים אוטומטית: Re-plan לאופציה זולה, ורק אז (אם מוצדק) בקשת אישור מהראל.
עדיפות תקציבית: Hook ו-CTA קודם (40%/40%), אמצע 20%. יתרה לא מנוצלת עוברת הלאה.
חיוב: Higgsfield מחייב את ה-estimate; failed/nsfw לא מחויבים (docs billing-and-retention).
"""
from __future__ import annotations
import json, time, hashlib
from pathlib import Path

DEFAULTS = {"target_ils": [10, 20], "cap_ils": 20.0, "usd_ils": 3.1,
            "alloc": {"hook": 0.4, "cta": 0.4, "mid": 0.2}}


class BudgetExceeded(RuntimeError):
    pass


class Ledger:
    def __init__(self, path: Path, cfg: dict | None = None):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {
            "budget": dict(DEFAULTS), "entries": []}
        if cfg:
            self.data["budget"].update(cfg)
        self.save()

    # ---- state
    @property
    def b(self):
        return self.data["budget"]

    def spent_usd(self, role: str | None = None) -> float:
        return round(sum(e.get("charged_usd", 0) for e in self.data["entries"]
                         if role is None or e.get("role") == role), 4)

    def spent_ils(self, role=None) -> float:
        return round(self.spent_usd(role) * self.b["usd_ils"], 2)

    def cap_usd(self) -> float:
        return self.b["cap_ils"] / self.b["usd_ils"]

    # ---- guard
    def check(self, role: str, next_usd: float, retry_risk: float) -> dict:
        """retry_risk = הסתברות משוערת שיידרש ניסיון נוסף באותו מחיר."""
        proj = self.spent_usd() + next_usd + retry_risk * next_usd
        ok = proj <= self.cap_usd()
        info = {"spent_ils": self.spent_ils(), "next_ils": round(next_usd * self.b["usd_ils"], 2),
                "projected_ils": round(proj * self.b["usd_ils"], 2), "cap_ils": self.b["cap_ils"],
                "role_spent_ils": self.spent_ils(role),
                "role_alloc_ils": round(self.b["cap_ils"] * self.b["alloc"].get(role, 0.2), 2),
                "ok": ok}
        if not ok:
            raise BudgetExceeded(json.dumps(info, ensure_ascii=False))
        return info

    # ---- record
    def record(self, **e):
        e.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
        if "body" in e:
            e["body_hash"] = hashlib.sha256(json.dumps(e.pop("body"), sort_keys=True).encode()).hexdigest()[:12]
        self.data["entries"].append(e)
        self.save()
        return e

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))
        tmp.replace(self.path)

    def summary(self) -> dict:
        roles = sorted({e.get("role") for e in self.data["entries"]})
        return {"spent_ils": self.spent_ils(), "spent_usd": self.spent_usd(),
                "by_role_ils": {r: self.spent_ils(r) for r in roles},
                "generations": sum(1 for e in self.data["entries"] if e.get("charged_usd")),
                "failed_uncharged": sum(1 for e in self.data["entries"] if e.get("status") in ("failed", "nsfw"))}
