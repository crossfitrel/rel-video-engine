#!/usr/bin/env python3
"""video_api — לקוח אחד לשכבת המצב ב-Supabase (פונקציית edge `video`).

כל מי שמדבר עם המצב (worker ב-GitHub Actions, Mac worker, Codex/ChatGPT, סשן Claude) עובר דרך הקובץ הזה.
אין כאן מפתחות: הרשאה = VIDEO_WORKER_TOKEN (טוקן חד-פעמי לג'וב) או VIDEO_ADMIN_KEY (סביבה בלבד).

  python3 cloud/video_api.py <op> '<json>'          # קריאה גולמית, למשל: jobs '{}' · state '{}' (עם VIDEO_REVIEW_TOKEN)
"""
from __future__ import annotations
import hashlib, json, os, sys, time, urllib.request, urllib.error

API = os.environ.get("VIDEO_API", "https://xfsvbpqbfmqlwgyusrww.supabase.co/functions/v1/video")
STORAGE_BASE = os.environ.get("VIDEO_STORAGE", "https://xfsvbpqbfmqlwgyusrww.supabase.co/storage/v1")


class ApiError(RuntimeError):
    pass


def _headers():
    h = {"content-type": "application/json"}
    if os.environ.get("VIDEO_WORKER_TOKEN"):
        h["x-worker-token"] = os.environ["VIDEO_WORKER_TOKEN"]
    elif os.environ.get("VIDEO_ADMIN_KEY"):
        h["x-video-admin"] = os.environ["VIDEO_ADMIN_KEY"]
    elif os.environ.get("VIDEO_REVIEW_TOKEN"):
        h["x-review-token"] = os.environ["VIDEO_REVIEW_TOKEN"]
    return h


def call(op: str, retries: int = 3, timeout: int = 120, **body):
    body["op"] = op
    data = json.dumps(body, ensure_ascii=False, default=str).encode()
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(API, data=data, headers=_headers(), method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")[:400]
            if e.code in (400, 401, 403, 404, 409):          # שגיאת לוגיקה: לא מנסים שוב
                try:
                    return json.loads(txt)
                except Exception:
                    raise ApiError(f"{op} HTTP {e.code}: {txt}")
            last = f"HTTP {e.code}: {txt}"
        except Exception as e:  # רשת
            last = str(e)
        time.sleep(2 * (i + 1))
    raise ApiError(f"{op} נכשל אחרי {retries} ניסיונות: {last}")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def upload(local: str, path: str, content_type: str) -> str:
    """מעלה ל-bucket video-review ומאמת: מוריד חזרה ומשווה sha256. מחזיר את ה-path. בלי אימות אין 'בוצע'."""
    r = call("upload_url", path=path)
    if not r.get("ok"):
        raise ApiError(f"upload_url: {r}")
    url = r["signedUrl"]
    with open(local, "rb") as f:
        data = f.read()
    req = urllib.request.Request(url, data=data, method="PUT", headers={"content-type": content_type, "x-upsert": "true"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        if resp.status not in (200, 201):
            raise ApiError(f"PUT {resp.status}")
    s = call("signed_url", path=path, ttl=600)
    with urllib.request.urlopen(s["url"], timeout=600) as resp:
        got = hashlib.sha256(resp.read()).hexdigest()
    want = hashlib.sha256(data).hexdigest()
    if got != want:
        raise ApiError(f"אימות העלאה נכשל {path}: {got[:12]} != {want[:12]}")
    return path


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    body = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(call(sys.argv[1], **body), ensure_ascii=False, indent=1, default=str)[:20000])


if __name__ == "__main__":
    sys.exit(main())
