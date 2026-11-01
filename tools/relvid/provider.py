#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
relvid.provider — שכבת ספק AI מופשטת (V2).

שלושה backends מאחורי אותו חוזה:
  api     — Anthropic API. דורש ANTHROPIC_API_KEY. מודל: REL_AI_MODEL.
  proxy   — (v11) דרך tools/llm.py → פונקציית video ב-Supabase: Sonnet, לוג עלות ותקרה בצד השרת. ברירת המחדל ב-worker.
  chat    — כותב כרטיס בקשה לדיסק וקורא תשובה שהודבקה חזרה. עובד בלי מפתח,
            כלומר קלוד בצ'אט הוא ה-Director.
  replay  — קורא אך ורק מה-cache. דטרמיניסטי → בדיקות ו-CI.

עקרונות מחייבים:
  * כל תשובה נשמרת ב-<proj>/ai_cache/<role>.<digest>.json.
  * ה-digest נגזר מ-(role, תוכן קובץ הפרומפט, payload קנוני). content-addressed:
    שינוי בפרומפט או בקלט = מפתח אחר = אי אפשר להחזיר תשובה ישנה בטעות.
  * המודל לעולם לא פולט timecodes. הוא בוחר מתוך מרחב מועמדים סופי,
    ו-validate_answer אוכפת שכל מזהה שהוא החזיר קיים במרחב.

CLI:
  python3 -m relvid.provider status <proj>
  python3 -m relvid.provider pending <proj>
"""
import os, sys, json, time, hashlib, pathlib, datetime

HERE = pathlib.Path(__file__).resolve().parent
PROMPT_DIR = HERE / "prompts"

DEFAULT_MODEL = os.environ.get("REL_AI_MODEL", "claude-opus-4-6")
DEFAULT_MAX_TOKENS = int(os.environ.get("REL_AI_MAX_TOKENS", "16000"))
COMPACT_SUFFIX = ("\n\n## פורמט דחוס (ניסיון חוזר אחרי קטיעה)\n"
                  "התשובה הקודמת נקטעה באורך. החזר את אותו JSON בדיוק לפי הסכמה, בלי טקסט מחוצה לו, "
                  "בלי שדות אופציונליים ריקים, וכל שדה נימוק/הסבר עד 8 מילים. אל תחשוב בקול.")

# שם קובץ הפרומפט לכל תפקיד. הגרסה בתוך שם הקובץ — מחייב שינוי שם בכל שינוי חוזה.
ROLE_PROMPTS = {
    "proofreader": "proofreader.v1.0.md",
    "producer":  "producer.brief_v1.0.md",
    "understand": "understand.v1.0.md",
    "director":  "director.plan_v1.4.md",   # v9.13: +harel_lessons (לקחים+דפוסי תיקון)
    "broll":     "broll.pick_v1.3.md",
    "reviewer":  "reviewer.blind_v1.0.md",
    "scorer":    "scorer.rubric_v1.0.md",
}


class ProviderError(RuntimeError):
    """תשובה לא חוקית, מזהה שלא קיים, או backend שנכשל."""


class NeedsHuman(RuntimeError):
    """backend=chat: נכתב כרטיס בקשה וממתינים לתשובה. לא שגיאה — עצירה מכוונת."""
    def __init__(self, role, req_path, resp_path):
        self.role, self.req_path, self.resp_path = role, req_path, resp_path
        super().__init__(f"{role}: ממתין לתשובה. כרטיס: {req_path} → תשובה אל: {resp_path}")


def _canon(obj):
    """JSON קנוני — מפתחות ממוינים, בלי רווחים. בסיס ל-digest יציב."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def prompt_text(role):
    name = ROLE_PROMPTS.get(role)
    if not name:
        raise ProviderError(f"תפקיד לא מוכר: {role}")
    p = PROMPT_DIR / name
    if not p.exists():
        raise ProviderError(f"קובץ פרומפט חסר: {p}")
    return p.read_text(encoding="utf-8")


def prompt_version(role):
    """הגרסה כפי שהיא מופיעה בשם הקובץ — נכנסת לכל תוצר לצורך ראיה."""
    name = ROLE_PROMPTS[role]
    return name.replace(".md", "").replace(".", "/", 1)


def digest(role, payload):
    h = hashlib.sha256()
    h.update(role.encode("utf-8")); h.update(b"\x00")
    h.update(prompt_text(role).encode("utf-8")); h.update(b"\x00")
    h.update(_canon(payload).encode("utf-8"))
    return h.hexdigest()[:16]


def _collect_ids(obj, out):
    """אוסף כל ערך תחת מפתח שנגמר ב-candidate_id / candidate_ids."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("candidate_id", "candidate_ids"):
                if isinstance(v, list):
                    out.update(str(x) for x in v)
                elif v is not None:
                    out.add(str(v))
            else:
                _collect_ids(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_ids(v, out)
    return out


def validate_answer(ans, allowed_ids=None, required_keys=()):
    """
    האכיפה המבנית: המודל בוחר מתוך מרחב סופי ולא ממציא.
    כל מזהה מועמד שהוחזר חייב להיות במרחב שנשלח אליו.
    """
    if not isinstance(ans, dict):
        raise ProviderError("התשובה אינה אובייקט JSON")
    miss = [k for k in required_keys if k not in ans]
    if miss:
        raise ProviderError(f"חסרים מפתחות בתשובה: {miss}")
    if allowed_ids is not None:
        allowed = set(map(str, allowed_ids))
        used = _collect_ids(ans, set())
        bad = sorted(used - allowed)
        if bad:
            # L154 (1.11.26): מזהה מומצא בודד הפיל ריל שלם (2 פעמים ביום אחד). העיקרון נשמר — המודל לא ממציא —
            # אבל האכיפה היא גיזום: החלטה שמפנה למזהה לא-קיים נזרקת (= לא חותכים שם), השאר נשאר. רוב מומצא = כשל.
            dropped = _prune_ids(ans, allowed)
            ans.setdefault("_pruned", []).extend(bad)
            if used and len(bad) > max(2, len(used) // 4):
                raise ProviderError(
                    f"התשובה מפנה ל-{len(bad)} מזהי מועמד שאינם קיימים במרחב: {bad[:8]}"
                )
            print(f"  [provider] נגזמו {dropped} החלטות עם מזהה לא-קיים: {bad[:8]}")
    return ans


def _prune_ids(obj, allowed):
    """מסיר החלטות (אובייקטים ברשימה) שמפנות למזהה לא-קיים, ומנקה מזהים לא-קיימים מרשימות candidate_ids."""
    n = 0
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "candidate_ids" and isinstance(v, list):
                keep = [x for x in v if str(x) in allowed]
                n += len(v) - len(keep); obj[k] = keep
            elif isinstance(v, (dict, list)):
                n += _prune_ids(v, allowed)
    elif isinstance(obj, list):
        i = 0
        while i < len(obj):
            x = obj[i]
            if isinstance(x, dict) and x.get("candidate_id") is not None and str(x["candidate_id"]) not in allowed:
                obj.pop(i); n += 1; continue
            n += _prune_ids(x, allowed); i += 1
    return n


def _extract_json(text):
    """מוציא את אובייקט ה-JSON הראשון מטקסט חופשי (עוטף ```json או פרוזה)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    t = t.strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        raise ProviderError("לא נמצא JSON בתשובה")
    try:
        return json.loads(t[i:j + 1])
    except json.JSONDecodeError:
        # L152 (1.11.26): אובייקט JSON תקין ואחריו טקסט/אובייקט נוסף ⇒ "Extra data". מפענחים את האובייקט השלם הראשון.
        return json.JSONDecoder().raw_decode(t[i:])[0]


class Provider:
    def __init__(self, proj, backend=None, model=None, verbose=True):
        self.proj = pathlib.Path(proj)
        self.backend = backend or os.environ.get("REL_AI_BACKEND") or (
            "api" if os.environ.get("ANTHROPIC_API_KEY") else "chat")
        self.model = model or DEFAULT_MODEL
        self.verbose = verbose
        self.cache_dir = self.proj / "ai_cache"
        self.req_dir = self.proj / "ai_requests"
        self.resp_dir = self.proj / "ai_responses"
        for d in (self.cache_dir, self.req_dir, self.resp_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.calls = []

    # ---------- cache ----------
    def _cache_path(self, role, dg):
        return self.cache_dir / f"{role}.{dg}.json"

    def _read_cache(self, role, dg):
        p = self._cache_path(role, dg)
        if not p.exists():
            return None
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            return rec.get("response")
        except Exception:
            return None

    def _write_cache(self, role, dg, payload, response, source):
        rec = {
            "schema_version": 1,
            "role": role,
            "prompt_version": prompt_version(role),
            "digest": dg,
            "source": source,
            "model": self.model if source == "api" else source,
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "input_digest": hashlib.sha256(_canon(payload).encode()).hexdigest()[:16],
            "response": response,
        }
        tmp = self._cache_path(role, dg).with_suffix(".tmp")
        tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self._cache_path(role, dg))

    # ---------- backends ----------
    def _ask_api(self, role, payload):
        try:
            import anthropic
        except ImportError:
            raise ProviderError("backend=api אבל חבילת anthropic לא מותקנת")
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ProviderError("backend=api אבל ANTHROPIC_API_KEY לא מוגדר")
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=prompt_text(role),
            messages=[{"role": "user", "content": _canon(payload)}],
        )
        return _extract_json("".join(b.text for b in msg.content if b.type == "text"))

    def _ask_proxy(self, role, payload):
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        import llm
        task = "director" if role.startswith("director") or role == "edit_director" else role
        r = llm.ask(task, user=_canon(payload), system=prompt_text(role),
                    project_id=os.environ.get("REL_PROJECT_ID"), max_tokens=DEFAULT_MAX_TOKENS)
        if r.get("stop_reason") == "max_tokens":
            # L147 (1.11.26): בריל עם 40-60 מועמדים התשובה המלאה עוברת את תקרת השרת (14000) ⇒ prep נפל.
            # ניסיון אחד נוסף בפורמט דחוס, ורק אז כשל.
            r = llm.ask(task, user=_canon(payload), system=prompt_text(role) + COMPACT_SUFFIX,
                        project_id=os.environ.get("REL_PROJECT_ID"), max_tokens=DEFAULT_MAX_TOKENS)
        self.last_usage = {"model": r.get("model"), "usd": r.get("usd"), "usage": r.get("usage")}
        if r.get("stop_reason") == "max_tokens":
            raise ProviderError(f"התשובה של {role} נקטעה בתקרת הטוקנים ({(r.get('usage') or {}).get('output_tokens')})")
        return _extract_json(r["text"])

    def _ask_chat(self, role, payload, dg):
        resp = self.resp_dir / f"{role}.{dg}.json"
        if resp.exists():
            return json.loads(resp.read_text(encoding="utf-8")), "chat"
        req = self.req_dir / f"{role}.{dg}.md"
        req.write_text(
            f"# כרטיס בקשה — {role} ({prompt_version(role)})\n\n"
            f"מזהה: `{dg}`\n\n"
            f"## הוראות התפקיד\n\n{prompt_text(role)}\n\n"
            f"## קלט\n\n```json\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=1)}\n```\n\n"
            f"## איך להשיב\n\n"
            f"להחזיר JSON בלבד, ולשמור אותו בדיוק אל:\n\n"
            f"    {resp}\n\n"
            f"ואז להריץ את אותה פקודה שוב — הצינור ימשיך מאותה נקודה.\n",
            encoding="utf-8")
        raise NeedsHuman(role, str(req), str(resp))

    # ---------- API ציבורי ----------
    def ask(self, role, payload, allowed_ids=None, required_keys=(), force=False):
        dg = digest(role, payload)
        t0 = time.time()
        cached = None if force else self._read_cache(role, dg)
        if cached is not None:
            self.calls.append({"role": role, "digest": dg, "source": "cache", "sec": 0.0})
            return validate_answer(cached, allowed_ids, required_keys)

        if self.backend == "replay":
            raise ProviderError(
                f"backend=replay ואין תשובה ב-cache עבור {role}.{dg}. "
                f"הריצו קודם עם backend=api או chat.")
        if self.backend == "proxy":
            ans, src = self._ask_proxy(role, payload), "proxy"
        elif self.backend == "api":
            ans, src = self._ask_api(role, payload), "api"
        elif self.backend == "chat":
            ans, src = self._ask_chat(role, payload, dg)
        else:
            raise ProviderError(f"backend לא מוכר: {self.backend}")

        ans = validate_answer(ans, allowed_ids, required_keys)
        self._write_cache(role, dg, payload, ans, src)
        self.calls.append({"role": role, "digest": dg, "source": src,
                           "sec": round(time.time() - t0, 2)})
        if self.verbose:
            print(f"  [{role}] {src} · {dg} · {time.time()-t0:.1f}ש", flush=True)
        return ans

    def report(self):
        return {"backend": self.backend, "model": self.model, "calls": self.calls}


def _cli():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    cmd, proj = sys.argv[1], sys.argv[2]
    p = Provider(proj, verbose=False)
    if cmd == "status":
        rows = sorted(p.cache_dir.glob("*.json"))
        print(f"backend={p.backend} model={p.model} cache={len(rows)}")
        for r in rows:
            try:
                d = json.loads(r.read_text(encoding="utf-8"))
                print(f"  {d['role']:<11} {d['digest']}  {d['prompt_version']:<22} {d['source']}")
            except Exception as e:
                print(f"  {r.name}: פגום ({e})")
        return 0
    if cmd == "pending":
        pend = [q for q in sorted(p.req_dir.glob("*.md"))
                if not (p.resp_dir / (q.stem + ".json")).exists()]
        for q in pend:
            print(q)
        return 1 if pend else 0
    print(f"פקודה לא מוכרת: {cmd}"); return 2


if __name__ == "__main__":
    sys.exit(_cli())
