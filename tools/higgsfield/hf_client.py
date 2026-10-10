"""hf_client.py — לקוח Higgsfield API ישיר (לא דרך MCP/קרדיטים של מנוי).

קריאת מפתחות (לפי סדר): env HF_KEY="id:secret" → env HF_API_KEY_ID+HF_API_KEY_SECRET
→ קובץ HF_ENV_FILE → ~/rel-video-work/.secrets/higgsfield.env → ~/.config/rel/higgsfield.env
הסוד לעולם לא מודפס, לא נכתב ללוג ולא נכנס ל-ledger.

פעולות: upload(path) → public_url · estimate(model, body) → {usd, credits} (חינם)
submit(model, body) → request_id · wait(request_id) → result · download(url, out)
מסמכי API: https://docs.higgsfield.ai/docs/quickstart.md (נבדק 25.9.26)
"""
from __future__ import annotations
import os, time, random, json, mimetypes
from pathlib import Path

import urllib.request, urllib.error


class HFError(RuntimeError):
    def __init__(self, code, body):
        super().__init__(f"HTTP {code}: {body[:300]}")
        self.code, self.body = code, body


def _req(method: str, url: str, headers: dict | None = None, data: bytes | None = None,
         timeout: int = 60) -> dict | bytes:
    """stdlib בלבד (עקרון המערכת: אפס תלויות חדשות)."""
    headers = dict(headers or {})
    headers.setdefault("User-Agent", UA)   # Cloudflare חוסם את ה-UA של urllib (error 1010)
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raise HFError(e.code, e.read().decode("utf-8", "replace")) from None
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _post(path, body, timeout=60):
    return _req("POST", f"{API}{path}", _h(), json.dumps(body).encode(), timeout)

API = "https://api.higgsfield.ai"
UA = "rel-video-system/1.0 (+higgsfield-ai-enhancement)"
TERMINAL = {"completed", "failed", "nsfw", "canceled"}
_ENV_CANDIDATES = [
    os.environ.get("HF_ENV_FILE", ""),
    str(Path.home() / "rel-video-work/.secrets/higgsfield.env"),
    "/Users/hayon/rel-video-work/.secrets/higgsfield.env",
    str(Path.home() / ".config/rel/higgsfield.env"),
]


class NoCredits(RuntimeError):
    """403 not_enough_credits — יתרת ה-API ריקה. טעינה = פעולה כספית ⇒ עצירה ואישור הראל."""


def _key() -> str:
    if os.environ.get("HF_KEY"):
        return os.environ["HF_KEY"]
    if os.environ.get("HF_API_KEY_ID") and os.environ.get("HF_API_KEY_SECRET"):
        return f"{os.environ['HF_API_KEY_ID']}:{os.environ['HF_API_KEY_SECRET']}"
    for p in _ENV_CANDIDATES:
        if p and Path(p).is_file():
            kv = dict(l.strip().split("=", 1) for l in Path(p).read_text().splitlines()
                      if "=" in l and not l.startswith("#"))
            if kv.get("HF_KEY"):
                return kv["HF_KEY"]
            if kv.get("HF_API_KEY_ID") and kv.get("HF_API_KEY_SECRET"):
                return f"{kv['HF_API_KEY_ID']}:{kv['HF_API_KEY_SECRET']}"
    raise SystemExit("חסרים מפתחות Higgsfield — ראו SKILL.md › 'הגדרת מפתח'")


def _h() -> dict:
    return {"Authorization": f"Key {_key()}", "Content-Type": "application/json"}


def upload(path: str | Path) -> str:
    """presigned upload — מחזיר public_url לשימוש כ-image_url. ה-PUT בלי מפתחות."""
    path = Path(path)
    ct = mimetypes.guess_type(str(path))[0] or "image/png"
    u = _post("/files/generate-upload-url", {"content_type": ct}, 30)
    _req("PUT", u["upload_url"], dict(u["upload_headers"]), path.read_bytes(), 180)
    return u["public_url"]


def estimate(model: str, body: dict) -> dict:
    """עלות לפני הרצה (לא מחייב). מחזיר {'usd': float, 'credits': float, 'raw': ...}."""
    j = _post(f"/estimate/{model}", body, 30)
    if j.get("type") == "estimate":
        return {"usd": float(j["usd"]), "credits": float(j["credits"]), "raw": j}
    return {"usd": None, "credits": None, "raw": j}   # מודל שמחזיר רק תיאור מחיר


def submit(model: str, body: dict) -> dict:
    """POST אחד בלבד — אין idempotency key בצד שלהם, לכן לעולם לא retry אוטומטי ל-POST."""
    try:
        return _post(f"/{model}", body, 60)   # {status, request_id, status_url, cancel_url}
    except HFError as e:
        if e.code == 403:
            raise NoCredits(e.body) from None
        raise


def status(request_id: str) -> dict:
    return _req("GET", f"{API}/requests/{request_id}/status", _h(), None, 30)


def wait(request_id: str, max_wait: int = 900) -> dict:
    delay, t0 = 2.0, time.time()
    while True:
        try:
            res = status(request_id)
        except HFError as e:
            if e.code >= 500:
                time.sleep(delay); continue
            raise
        if res.get("status") in TERMINAL:
            return res
        if time.time() - t0 > max_wait:
            raise TimeoutError(request_id)
        time.sleep(delay + random.uniform(0, .5))
        delay = min(delay * 1.5, 10)


def result_url(res: dict) -> str:
    if res.get("video"):
        return res["video"]["url"]
    if res.get("images"):
        return res["images"][0]["url"]
    raise RuntimeError(f"אין URL בתוצאה: {json.dumps(res)[:300]}")


def download(url: str, out: str | Path) -> Path:
    out = Path(out)
    rq = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(rq, timeout=300) as r, open(out, "wb") as f:
        while True:
            ch = r.read(1 << 20)
            if not ch:
                break
            f.write(ch)
    return out


def credits_available() -> bool:
    """בדיקת יתרה בלי לחייב: אין endpoint יתרה ציבורי. מריצים estimate (חינם) —
    ואז submit לא נעשה. לכן הדרך היחידה לדעת = 403 not_enough_credits ב-submit.
    הפונקציה מחזירה None (לא ידוע) — נשמרת כתזכורת מכוונת."""
    return None
