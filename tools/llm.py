#!/usr/bin/env python3
"""llm — שכבה אחת לכל קריאת מודל במערכת העריכה (v11, 29.10.26).

למה: כל צעד שיפוט רץ היום בסשן Claude ושורף מכסה. מכאן — קריאה ממוקדת אחת ל-Anthropic API,
עם מודל לפי משימה, לוג טוקנים ועלות לכל פרויקט, ותקרת עלות לריל וליום.

ניתוב (video.config.routes, ברירת מחדל למטה):
  Haiku  — classify · transcript_sanity (הגיון לשוני של תמלול) · broll_label (התאמת בירול לתווית) · quick_check
  Sonnet — director (--director) · hook · caption (מנוע v4 + rel-cta-psychology + caption_gate) · vision (קריאת גיליונות) · note_map · mg_critic
  Opus   — escalate בלבד: שער שנכשל פעמיים, או הערה שלא ממופה לפעולה. תקרה: 2 קריאות לריל.

איך: ברירת המחדל עוברת דרך פונקציית ה-edge `video` (op=llm). המפתח יושב בכספת של Supabase ולא מגיע ל-runner;
התקרה והלוג נאכפים בצד השרת ולכן אי אפשר לעקוף אותם מהקוד. מסלול ישיר (ANTHROPIC_API_KEY בסביבה, למשל במק)
נשען על אותו ניתוב ורושם עלות דרך op=cost_log — אם אין חיבור, הקריאה נכשלת סגור.

  from llm import ask
  r = ask("caption", system=..., user=..., project_id="p-123")      # -> {"ok", "text", "model", "usd", "usage"}
  python3 tools/llm.py route caption           # מה ייבחר
  python3 tools/llm.py ask quick_check "שלום"   # קריאה אמיתית (דורש הרשאה)
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

ROUTES = {"classify": "haiku", "transcript_sanity": "haiku", "broll_label": "haiku", "quick_check": "haiku",
          "director": "sonnet", "hook": "sonnet", "caption": "sonnet", "vision": "sonnet", "note_map": "sonnet",
          "mg_critic": "sonnet", "escalate": "opus"}
MODELS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"}
ESCALATION_REASONS = {"gate_failed_twice", "note_unmapped"}

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cloud"))


class LLMError(RuntimeError):
    pass


def route(task: str) -> str:
    return ROUTES.get(task, "sonnet")


def ask(task: str, user: str | list, system: str | None = None, project_id: str | None = None,
        max_tokens: int = 2000, escalate_reason: str | None = None, images: list | None = None) -> dict:
    """קריאה אחת. user = טקסט, או רשימת content blocks (לגיליונות vision)."""
    tier = route(task)
    if tier == "opus" and escalate_reason not in ESCALATION_REASONS:
        raise LLMError(f"Opus רק להסלמה ({sorted(ESCALATION_REASONS)}), התקבל {escalate_reason!r}")
    content = user if isinstance(user, list) else [{"type": "text", "text": user}]
    for img in images or []:
        import base64
        b = Path(img).read_bytes()
        mt = "image/png" if str(img).endswith(".png") else "image/jpeg"
        content = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": base64.b64encode(b).decode()}}] + content
    messages = [{"role": "user", "content": content}]
    import video_api as V
    r = V.call("llm", task=task, tier=tier, system=system, messages=messages, max_tokens=max_tokens,
               project_id=project_id, timeout=300)
    if not r.get("ok"):
        raise LLMError(f"llm {task}: {r.get('error')} {r.get('detail') or ''}".strip())
    return r


def ask_json(task: str, user, **kw) -> dict:
    r = ask(task, user, **kw)
    t = r["text"].strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0]
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < i:
        raise LLMError(f"{task}: אין JSON בתשובה")
    try:
        r["json"] = json.loads(t[i:j + 1])
    except json.JSONDecodeError:  # L152: JSON ואחריו טקסט נוסף
        r["json"] = json.JSONDecoder().raw_decode(t[i:])[0]
    return r


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "route":
        print(route(sys.argv[2]), MODELS[route(sys.argv[2])]); return 0
    if len(sys.argv) >= 4 and sys.argv[1] == "ask":
        r = ask(sys.argv[2], sys.argv[3]); print(json.dumps({k: r.get(k) for k in ("model", "usd", "usage", "text")}, ensure_ascii=False)); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
