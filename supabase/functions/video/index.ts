// video — שכבת המצב של מערכת עריכת הסושיאל (v11, 29.10.26).
// מחליף את ה-db של עמוד ה-Artifact. כל הכתיבה עוברת כאן; הטבלאות בסכמת video סגורות ל-anon.
// הרשאות: x-review-token (הראל, עמוד rel.fit/review) · x-video-admin (Claude/Codex/Mac) · x-worker-token (טוקן חד-פעמי לג'וב).
// מפתחות (Anthropic, Monday, GitHub) נשארים כאן ולא יוצאים לעולם ל-runner או לדפדפן.
import postgres from "npm:postgres@3.4.4";
import { createClient } from "npm:@supabase/supabase-js@2";

// 1.11.26: max 3 ⇒ enqueue נתקע עד 504 כשכמה workers קוראים ל-llm במקביל. 8 חיבורים + timeouts כדי שקריאה תיכשל מהר ולא תיתקע.
const sql = postgres(Deno.env.get("SUPABASE_DB_URL")!, { max: 8, prepare: false, idle_timeout: 20, connect_timeout: 10 });
const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
const BUCKET = "video-review";
const REPO = "crossfitrel/rel-video-cloud";
// L159 (1.11.26): קוד שנכתב לריפו ולא נפרס = התיקון לא קיים. ה-worker משווה את המספר הזה לקובץ בריפו ומדליק באנר אם הפונקציה הפרוסה ישנה.
const FN_VERSION = "2026-11-03.1";
const METRICOOL_USER = "4873293";
const WORKFLOW = "video-worker.yml";
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "content-type, x-review-token, x-video-admin, x-worker-token", "Access-Control-Allow-Methods": "POST, GET, OPTIONS" };
const J = (b: unknown, s = 200) => new Response(JSON.stringify(b), { status: s, headers: { ...CORS, "content-type": "application/json; charset=utf-8" } });
const secretCache: Record<string, string | null> = {};
async function secret(name: string): Promise<string | null> {
  if (name in secretCache) return secretCache[name];
  const env = Deno.env.get(name.toUpperCase()); if (env) return (secretCache[name] = env);
  const r = await sql`select decrypted_secret from vault.decrypted_secrets where name=${name} limit 1`;
  return (secretCache[name] = r[0]?.decrypted_secret ?? null);
}
function eq(a: string, b: string) { if (!a || !b || a.length !== b.length) return false; let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i); return d === 0; }
async function sha(s: string) { const h = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)); return [...new Uint8Array(h)].map(x => x.toString(16).padStart(2, "0")).join(""); }
const rnd = () => [...crypto.getRandomValues(new Uint8Array(24))].map(x => x.toString(16).padStart(2, "0")).join("");

type Who = { role: "harel" | "admin" | "worker"; job?: any };
async function auth(req: Request): Promise<Who | null> {
  const rt = req.headers.get("x-review-token") || ""; const ak = req.headers.get("x-video-admin") || ""; const wt = req.headers.get("x-worker-token") || "";
  if (rt && eq(rt, (await secret("video_review_token")) || "")) return { role: "harel" };
  if (ak && eq(ak, (await secret("video_admin_key")) || "")) return { role: "admin" };
  if (wt) {
    const h = await sha(wt);
    const r = await sql`select * from video.jobs where token_hash=${h} and status in ('queued','running') and coalesce((dispatch->>'at')::timestamptz, created_at) > now()-interval '14 hours' limit 1`;
    if (r[0]) return { role: "worker", job: r[0] };
  }
  return null;
}


// ---------- סודות: כתיבה בלבד מהעמוד (הערך לא חוזר לעולם, גם לא ל-Claude) ----------
const SETTABLE: Record<string, { re: RegExp; health: string; verify: (v: string) => Promise<string | null> }> = {
  anthropic_api_key: { re: /^sk-ant-[A-Za-z0-9_\-]{20,}$/, health: "llm", verify: async (v) => {
    // Anthropic לא תמיד עונה מה-edge בזמן: אחרי 15 שניות שומרים בכל זאת, וקריאת ה-llm הראשונה מאמתת (באנר אם נכשל).
    try { const r = await fetch("https://api.anthropic.com/v1/models?limit=1", { headers: { "x-api-key": v, "anthropic-version": "2023-06-01" }, signal: AbortSignal.timeout(15000) });
      return r.ok ? null : (r.status === 401 ? "המפתח לא תקף" : "Anthropic החזיר " + r.status); } catch { return "__timeout__"; } } },
  github_dispatch_token: { re: /^(github_pat_|ghp_)[A-Za-z0-9_]{20,}$/, health: "dispatch", verify: async (v) => {
    const h = { authorization: "Bearer " + v, accept: "application/vnd.github+json", "user-agent": "rel-video" };
    const r = await fetch("https://api.github.com/repos/crossfitrel/rel-video-cloud", { headers: h, signal: AbortSignal.timeout(15000) });
    if (!r.ok) return r.status === 401 ? "הטוקן לא תקף" : "אין לטוקן גישה לריפו rel-video-cloud";
    const w = await fetch("https://api.github.com/repos/crossfitrel/rel-video-cloud/actions/workflows", { headers: h, signal: AbortSignal.timeout(15000) });
    return w.ok ? null : "חסרה הרשאת Actions (קריאה וכתיבה)"; } },
  // L161: תזמון אוטונומי. הטוקן של Metricool (X-Mc-Auth) נשמר רק כאן; ה-worker מדבר עם Metricool דרך op=metricool.
  metricool_token: { re: /^[A-Za-z0-9_\-\.]{16,}$/, health: "metricool", verify: async (v) => {
    try { const r = await fetch(`https://app.metricool.com/api/v2/scheduler/posts?blogId=6323702&userId=${METRICOOL_USER}&start=2026-01-01T00:00:00&end=2026-01-02T00:00:00&timezone=Asia/Jerusalem`, { headers: { "X-Mc-Auth": v }, signal: AbortSignal.timeout(15000) });
      return r.ok ? null : (r.status === 401 || r.status === 403 ? "הטוקן לא תקף" : "Metricool החזיר " + r.status); } catch { return "__timeout__"; } } },
};
async function secretSet(name: string, value: string) {
  const d = SETTABLE[name]; value = String(value || "").trim();
  if (!d) return { ok: false, error: "שם לא מוכר" };
  if (!d.re.test(value)) return { ok: false, error: "הפורמט לא נראה נכון" };
  const bad = await d.verify(value); const unverified = bad === "__timeout__"; if (bad && !unverified) return { ok: false, error: bad };
  const ex = await sql`select id from vault.secrets where name=${name} limit 1`;
  if (ex[0]) await sql`select vault.update_secret(${ex[0].id}::uuid, ${value})`; else await sql`select vault.create_secret(${value}, ${name})`;
  delete secretCache[name];
  await health(d.health, unverified ? "unverified" : "ok", unverified ? "המפתח נשמר. Anthropic לא ענה בבדיקה, הוא ייבדק בקריאה הראשונה" : "הוגדר מהעמוד " + new Date().toISOString().slice(0, 10));
  return { ok: true, name, verified: !unverified };
}
// ---------- jobs ----------
const KIND_BY_ACTION: Record<string, string> = { send_notes: "notes", approve_publish: "finish", approve_cover_caption: "schedule", request_cover_change: "cover" };
// מה רץ איפה: חישוב דטרמיניסטי + Sonnet ⇒ GitHub Actions. תזמון Metricool ⇒ צעד Claude קצר (MCP) עד שיהיה טוקן Metricool בכספת.
// L160 (1.11.26): judge ו-schedule רצים ב-Actions. Claude נכנס רק כשה-worker עצמו מעביר (runner=claude) אחרי שני סבבים שנכשלו.
const RUNNER_BY_KIND: Record<string, string> = { prep: "actions", notes: "actions", finish: "actions", cover: "actions", refinish: "actions", schedule: "actions", judge: "actions" };
async function enqueue(kind: string, project_id: string | null, payload: any = {}, runner?: string) {
  const open = await sql`select id from video.jobs where kind=${kind} and coalesce(project_id,'')=${project_id || ""} and status in ('queued','running') limit 1`;
  if (open[0]) return { id: open[0].id, deduped: true };
  const run = runner || RUNNER_BY_KIND[kind] || "actions";
  const r = await sql`insert into video.jobs(kind, project_id, payload, runner) values (${kind}, ${project_id}, ${sql.json(payload)}, ${run}) returning id`;
  const id = r[0].id; const d = run === "actions" ? await dispatch(id) : { ok: true, via: "claude-queue" };
  return { id, dispatch: d };
}
async function dispatch(job_id: string) {
  const gh = await secret("github_dispatch_token");
  const token = rnd();
  await sql`update video.jobs set token_hash=${await sha(token)} where id=${job_id}`;
  if (!gh) {
    await health("dispatch", "not_configured", "חסר github_dispatch_token בכספת: הג'וב נשאר בתור ויורץ כשנפתח סשן עם Claude");
    await sql`update video.jobs set dispatch=${sql.json({ ok: false, reason: "no_token" })} where id=${job_id}`;
    return { ok: false, reason: "no_token" };
  }
  const res = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST", headers: { authorization: `Bearer ${gh}`, accept: "application/vnd.github+json", "user-agent": "rel-video" },
    body: JSON.stringify({ ref: "main", inputs: { job_id, job_token: token } }) });
  const ok = res.status === 204; const info = { ok, status: res.status, at: new Date().toISOString(), body: ok ? "" : (await res.text()).slice(0, 300) };
  await sql`update video.jobs set dispatch=${sql.json(info)} where id=${job_id}`;
  await health("dispatch", ok ? "ok" : "failed", ok ? "" : `GitHub החזיר ${res.status}`);
  return info;
}
async function health(key: string, value: string, note = "") {
  await sql`insert into video.system_health(key,value,note,at) values (${key},${value},${note},now()) on conflict (key) do update set value=excluded.value, note=excluded.note, at=now()`;
}

// ---------- storage ----------
async function signed(path: string | null, ttl = 6 * 3600) {
  if (!path) return null; if (/^https?:/.test(path)) return path;
  const { data } = await sb.storage.from(BUCKET).createSignedUrl(path, ttl); return data?.signedUrl ?? null;
}

// ---------- Monday ----------
async function monday(query: string, variables: any = {}) {
  const t = await secret("monday_token"); if (!t) throw new Error("monday_token missing");
  const r = await fetch("https://api.monday.com/v2", { method: "POST", headers: { authorization: t, "content-type": "application/json", "API-Version": "2024-10" }, body: JSON.stringify({ query, variables }) });
  const j = await r.json(); if (j.errors) throw new Error(JSON.stringify(j.errors).slice(0, 300)); return j.data;
}

// ---------- LLM (Anthropic) ----------
async function cfg(key: string) { const r = await sql`select value from video.config where key=${key}`; return r[0]?.value ?? {}; }
async function llm(b: any, who: Who) {
  const routes = await cfg("routes"), models = await cfg("models"), prices = await cfg("prices_usd_per_mtok"), caps = await cfg("caps");
  const tier = b.tier || routes[b.task] || "sonnet"; const model = models[tier] || tier;
  const project_id = b.project_id || who.job?.project_id || null; const job_id = who.job?.id || null;
  if (project_id) {
    const s = await sql`select coalesce(sum(usd),0)::float usd, coalesce(sum(usd) filter (where job_id is not distinct from ${job_id}),0)::float job_usd,
      count(*) filter (where model=${models.opus}) opus from video.costs where project_id=${project_id}`;
    // L155 (1.11.26): התקרה לריל נספרת לכל ניסיון (ג'וב), לא לכל חיי הריל — ריצות שנפלו על באגים תשתית לא חונקות את הניסיון הבא.
    // תקרת חיים = פי 3 (ברירת מחדל) כדי שריל לא יסתובב בלי סוף.
    const perReel = caps.usd_per_reel ?? 1.5; const lifetime = caps.usd_per_reel_lifetime ?? perReel * 4;
    const attempt = job_id ? s[0].job_usd : s[0].usd;
    if (attempt >= perReel || s[0].usd >= lifetime) { await health("cost_cap", "hit", `תקרת עלות לריל ${project_id} (ניסיון $${attempt.toFixed(2)} · חיים $${s[0].usd.toFixed(2)})`); return { ok: false, error: "cap_reel", spent: s[0].usd, attempt }; }
    if (tier === "opus" && s[0].opus >= (caps.opus_calls_per_reel ?? 2)) return { ok: false, error: "cap_opus" };
  }
  const day = await sql`select coalesce(sum(usd),0)::float usd from video.costs where at > date_trunc('day', now() at time zone 'Asia/Jerusalem') at time zone 'Asia/Jerusalem'`;
  if (day[0].usd >= (caps.usd_per_day ?? 5)) { await health("cost_cap", "hit", "תקרת עלות יומית"); return { ok: false, error: "cap_day", spent: day[0].usd }; }
  const key = await secret("anthropic_api_key");
  if (!key) { await health("llm", "not_configured", "חסר מפתח Anthropic (anthropic_api_key)"); return { ok: false, error: "no_key" }; }
  const body: any = { model, max_tokens: Math.min(b.max_tokens || 2000, 14000) /* 30.10.26: 8000 קטע את understand (8000/8000) ⇒ JSON שבור ⇒ finish rc=1 שקט. 8000 טוקנים ≈ 62ש, לכן 14000 + timeout 145ש */, messages: b.messages };
  if (b.system) body.system = b.system;
  // 30.10.26: ל-Sonnet 5.5 חשיבה פעילה כברירת מחדל, והיא אכלה את תקרת הטוקנים (understand: 14000 מתוכם ~7600 תווי תשובה). השיפוט כאן לא צריך חשיבה.
  if (b.thinking) body.thinking = b.thinking; else if (tier === "sonnet") body.thinking = { type: "between_tools" };
  const r = await fetch("https://api.anthropic.com/v1/messages", { method: "POST", headers: { "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json" }, body: JSON.stringify(body), signal: AbortSignal.timeout(145000) });
  const j = await r.json();
  if (!r.ok) { await health("llm", "error", `Anthropic ${r.status}: ${(j?.error?.message || "").slice(0, 120)}`); return { ok: false, error: "api", status: r.status, detail: j?.error?.message }; }
  const u = j.usage || {}; const p = prices[tier] || { in: 3, out: 15, cache_read: 0.3 };
  const usd = ((u.input_tokens || 0) * p.in + (u.output_tokens || 0) * p.out + (u.cache_read_input_tokens || 0) * (p.cache_read ?? p.in / 10) + (u.cache_creation_input_tokens || 0) * p.in * 1.25) / 1e6;
  await sql`insert into video.costs(project_id, job_id, task, model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, usd) values (${project_id}, ${job_id}, ${b.task || "?"}, ${j.model || model}, ${u.input_tokens || 0}, ${u.output_tokens || 0}, ${u.cache_read_input_tokens || 0}, ${u.cache_creation_input_tokens || 0}, ${usd})`;
  await health("llm", "ok", "");
  return { ok: true, model: j.model || model, tier, text: (j.content || []).filter((c: any) => c.type === "text").map((c: any) => c.text).join("\n"), usage: u, usd, stop_reason: j.stop_reason };
}

// ---------- review state ----------
// L166 (3.11.26): הריפוי העצמי רץ בכל טעינת עמוד (אין cron ואין polling).
// 1) באנר "תקרה יומית" מאתמול לא נשאר תקוע — מתאפס כשמתחיל יום חדש בישראל.
// 2) dispatch שהחזיר 204 לא אומר שהריצה התחילה: GitHub מחזיר 204 גם כשהחשבון חסום (חיוב/מכסת דקות) והריצה מתה ב-3 שניות.
//    ג'וב actions בתור שנשלח לפני 15+ דקות ולא התחיל ⇒ באנר actions:blocked + שליחה חוזרת (פעם ב-30 דקות לג'וב, עד 8 ג'ובים בטעינה).
//    כשהחסימה משתחררת, טעינת העמוד הבאה מתניעה את כל התור לבד.
async function selfHeal() {
  await sql`update video.system_health set value='ok', note='' where key='cost_cap' and value='hit' and at < (date_trunc('day', now() at time zone 'Asia/Jerusalem') at time zone 'Asia/Jerusalem')`;
  const stuck = await sql`select id from video.jobs where status='queued' and runner='actions' and (dispatch->>'ok')::boolean is true
    and started_at is null and created_at < now()-interval '15 minutes' order by created_at limit 8`;
  if (!stuck.length) { await sql`update video.system_health set value='ok', note='' where key='actions' and value='blocked'`; return; }
  await health("actions", "blocked", `${stuck.length} ג'ובים בתור לא התחילו לרוץ ב-GitHub Actions`);
  for (const j of await sql`select id from video.jobs where id = any(${stuck.map((x: any) => x.id)}) and (dispatch->>'at')::timestamptz < now()-interval '30 minutes'`) await dispatch(j.id);
}
async function state() {
  try { await selfHeal(); } catch (_) { /* הריפוי לא מפיל את העמוד */ }
  const projects = await sql`select * from video.projects where not hidden order by publish_date nulls last, updated_at desc`;
  const ids = projects.map((p: any) => p.id);
  const comments = ids.length ? await sql`select * from video.comments where project_id = any(${ids}) order by t` : [];
  const actions = ids.length ? await sql`select id, project_id, type, version, at from video.actions where not consumed and project_id = any(${ids})` : [];
  const hh = await sql`select key, value, note, at from video.system_health where value not in ('ok','') and key <> 'dispatch_info'`;
  for (const p of projects as any[]) { p.video_url = await signed(p.video_path); p.cover_url = await signed(p.cover_path); }
  // הג'וב האחרון לכל סרטון + משך חציוני לכל סוג ג'וב (מהריצות שהצליחו), כדי שהעמוד יראה שלב, צפי וסיבת תקיעה
  const jobs = ids.length ? await sql`select distinct on (project_id) project_id, kind, status, runner, created_at, started_at, finished_at, left(coalesce(result->>'error',''),200) as error
    from video.jobs where project_id = any(${ids}) order by project_id, created_at desc` : [];
  const durations = await sql`select kind, count(*)::int as n,
    round(percentile_cont(0.5) within group (order by extract(epoch from (started_at - created_at))))::int as queue_sec,
    round(percentile_cont(0.5) within group (order by extract(epoch from (finished_at - started_at))))::int as run_sec
    from video.jobs where status='done' and started_at is not null and finished_at is not null group by kind`;
  return { projects, comments, actions, health: hh, jobs, durations, at: new Date().toISOString() };
}
const REVIEWABLE = ["review", "fixing", "blocked"];

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  const url = new URL(req.url);
  // Monday webhook: סטטוס "מוכן לעריכה" בגאנט הסושיאל ⇒ ג'וב prep. הכתובת כוללת ?k=<video_admin_key>.
  if (url.searchParams.get("src") === "monday") {
    const b = await req.json().catch(() => ({}));
    if (b.challenge) return J({ challenge: b.challenge });
    if (!eq(url.searchParams.get("k") || "", (await secret("video_admin_key")) || "")) return J({ ok: false }, 401);
    const e = b.event || {}; const label = e.value?.label?.text || "";
    if (String(e.boardId) === "18395578529" && e.columnId === "color_mkrp4sgm" && label === "מוכן לעריכה")
      return J({ ok: true, job: await enqueue("prep", `p-${e.pulseId}`, { item_id: String(e.pulseId) }) });
    // L160: תאריך פרסום נקבע בגאנט ⇒ פרויקט שאושר ומחכה לתאריך מתוזמן לבד. שינוי שם ⇒ הכותרת בעמוד מתעדכנת.
    if (String(e.boardId) === "18395578529" && e.columnId === "date_mkrpvw3n") {
      const p = (await sql`select id, state from video.projects where id=${"p-" + e.pulseId}`)[0];
      if (p?.state === "ready_to_schedule") return J({ ok: true, job: await enqueue("schedule", p.id, { trigger: "date_set" }) });
      return J({ ok: true, ignored: "not_ready" });
    }
    if (String(e.boardId) === "18395578529" && e.type === "update_name" && e.value?.name) {
      await sql`update video.projects set title=${e.value.name}, updated_at=now() where id=${"p-" + e.pulseId}`; return J({ ok: true });
    }
    return J({ ok: true, ignored: true });
  }
  const who = await auth(req); if (!who) return J({ ok: false, error: "unauthorized" }, 401);
  const b = await req.json().catch(() => ({})); const op = b.op;
  const isW = who.role !== "harel";
  try {
    switch (op) {
      // ----- הראל -----
      case "state": return J({ ok: true, ...(await state()) });
      case "secret_set": { if (who.role === "worker") break; return J(await secretSet(b.name, b.value)); }
      case "secrets_status": { if (who.role === "worker") break; const r = await sql`select name from vault.secrets where name = any(${Object.keys(SETTABLE)})`; return J({ ok: true, set: Object.fromEntries(Object.keys(SETTABLE).map(k => [k, r.some((x: any) => x.name === k)])) }); }
      case "comment_add": {
        const r = await sql`insert into video.comments(project_id, version, t, text, category, status, by_user) values (${b.project_id}, ${b.version ?? null}, ${b.t ?? 0}, ${String(b.text || "").slice(0, 2000)}, ${b.category || "other"}, 'open', ${who.role}) returning id`;
        return J({ ok: true, id: r[0].id });
      }
      case "send_notes": case "approve_publish": case "approve_cover_caption": case "request_cover_change": case "hide": {
        const p = (await sql`select * from video.projects where id=${b.project_id}`)[0]; if (!p) return J({ ok: false, error: "no_project" }, 404);
        if (op === "approve_publish" && (!REVIEWABLE.includes(p.state) || !p.video_path)) return J({ ok: false, error: "not_reviewable" }, 409);
        if ((op === "approve_cover_caption" || op === "request_cover_change") && p.state !== "cover_review") return J({ ok: false, error: "not_cover_review" }, 409);
        let count = 0;
        if (op === "send_notes") { const r = await sql`update video.comments set status='sent', updated_at=now() where project_id=${p.id} and status='open' returning id`; count = r.length; if (!count) return J({ ok: false, error: "no_open_notes" }, 409); }
        if (op === "hide") await sql`update video.projects set hidden=true, updated_at=now() where id=${p.id}`;
        // L160: אישור קאבר+קפשן מוציא מיד מ"דורש אותך" (קודם נשאר cover_review עד שסשן Claude תזמן ⇒ נראה כאילו האישור לא נקלט)
        if (op === "approve_cover_caption") await sql`update video.projects set state='ready_to_schedule', caption=coalesce(${b.caption ?? null}, caption), updated_at=now() where id=${p.id}`;
        const payload = { caption: b.caption ?? null, note: b.note ?? null, count };
        const a = await sql`insert into video.actions(project_id, type, version, payload, by_user, consumed) values (${p.id}, ${op === "hide" ? "remove" : op}, ${p.version}, ${sql.json(payload)}, ${who.role}, ${op === "hide"}) returning id`;
        const job = KIND_BY_ACTION[op] ? await enqueue(KIND_BY_ACTION[op], p.id, { action_id: a[0].id, ...payload }) : null;
        return J({ ok: true, action_id: a[0].id, job });
      }
      // ----- worker / admin -----
      case "job_claim": { if (!isW) break; const id = b.job_id || who.job?.id;
        const r = await sql`update video.jobs set status='running', started_at=now(), attempts=attempts+1, runner=coalesce(${b.runner || null}, runner) where id=${id} and status in ('queued','running') returning *`;
        if (!r[0]) return J({ ok: false, error: "not_claimable" }, 409);
        const p = r[0].project_id ? (await sql`select * from video.projects where id=${r[0].project_id}`)[0] : null;
        const comments = r[0].project_id ? await sql`select * from video.comments where project_id=${r[0].project_id} and status in ('sent','not_fixed')` : [];
        return J({ ok: true, job: r[0], project: p, comments }); }
      case "job_done": { if (!isW) break; const id = b.job_id || who.job?.id;
        await sql`update video.jobs set status=${b.status || "done"}, finished_at=now(), result=${sql.json(b.result || {})} where id=${id}`;
        if (b.status === "done" && b.consume_action) await sql`update video.actions set consumed=true, consumed_at=now(), handled_as=${b.handled_as || "worker"} where id=${b.consume_action}`;
        return J({ ok: true }); }
      case "run_log": { if (!isW) break;
        const r = await sql`insert into video.runs(job_id, project_id, stage, runner, started_at, ended_at, seconds, runner_minutes, exit_code, state_saved, state_sha, preflight_ready, log_tail, extra)
          values (${b.job_id || who.job?.id || null}, ${b.project_id || who.job?.project_id || null}, ${b.stage}, ${b.runner || "?"}, ${b.started_at || new Date().toISOString()}, now(), ${b.seconds ?? null}, ${b.runner_minutes ?? null}, ${b.exit_code ?? null}, ${!!b.state_saved}, ${b.state_sha || null}, ${b.preflight_ready ?? null}, ${String(b.log_tail || "").slice(-4000)}, ${sql.json(b.extra || {})}) returning id`;
        return J({ ok: true, id: r[0].id }); }
      case "project_upsert": { if (!isW) break; const p = b.project || {}; if (!p.id) return J({ ok: false, error: "id" }, 400);
        const cols = ["monday_item_id","title","dept","workdir","state","raw_state","version","duration","publish_date","video_path","cover_path","caption","preflight","fixed","hidden","test","extra","source"].filter(k => k in p);
        const row: any = { id: p.id, updated_at: new Date() }; for (const k of cols) row[k] = (k === "preflight" || k === "fixed" || k === "extra") ? sql.json(p[k]) : p[k];
        await sql`insert into video.projects ${sql(row)} on conflict (id) do update set ${sql(row, ...cols, "updated_at")}`;
        return J({ ok: true }); }
      case "comment_update": { if (!isW) break;
        await sql`update video.comments set status=coalesce(${b.status || null}, status), reply=coalesce(${b.reply || null}, reply), updated_at=now() where id=${b.id}`; return J({ ok: true }); }
      case "comment_import": { if (!isW) break; const c = b.comment;
        await sql`insert into video.comments ${sql({ id: c.id, project_id: c.project_id, version: c.version ?? null, t: c.t ?? 0, text: c.text, category: c.category || "other", status: c.status || "open", reply: c.reply || null, by_user: c.by_user || "harel", at: c.at || new Date(), extra: sql.json(c.extra || {}) })} on conflict (id) do nothing`;
        return J({ ok: true }); }
      case "action_import": { if (!isW) break; const a = b.action;
        await sql`insert into video.actions ${sql({ id: a.id, project_id: a.project_id, type: a.type, version: a.version ?? null, payload: sql.json(a.payload || {}), consumed: !!a.consumed, consumed_at: a.consumed_at || null, handled_as: a.handled_as || null, by_user: a.by_user || "harel", at: a.at || new Date() })} on conflict (id) do nothing`;
        return J({ ok: true }); }
      case "action_consume": { if (!isW) break; await sql`update video.actions set consumed=true, consumed_at=now(), handled_as=${b.handled_as || "worker"} where id=${b.id}`; return J({ ok: true }); }
      case "health_set": { if (!isW) break; await health(b.key, b.value, b.note || ""); return J({ ok: true }); }
      case "upload_url": { if (!isW) break; const { data, error } = await sb.storage.from(BUCKET).createSignedUploadUrl(b.path, { upsert: true }); if (error) return J({ ok: false, error: error.message }, 400); return J({ ok: true, ...data }); }
      case "signed_url": { if (!isW) break; return J({ ok: true, url: await signed(b.path, b.ttl || 3600) }); }
      case "monday_item": { if (!isW) break; const d = await monday(`query($id:[ID!]){items(ids:$id){id name column_values{id text value} assets{id name public_url file_extension}}}`, { id: [String(b.item_id)] }); return J({ ok: true, item: d.items?.[0] }); }
      case "monday_status": { if (!isW) break;
        await monday(`mutation($b:ID!,$i:ID!,$v:JSON!){change_column_value(board_id:$b,item_id:$i,column_id:"color_mkrp4sgm",value:$v){id}}`, { b: "18395578529", i: String(b.item_id), v: JSON.stringify({ label: b.label }) });
        if (b.update) await monday(`mutation($i:ID!,$t:String!){create_update(item_id:$i,body:$t){id}}`, { i: String(b.item_id), t: b.update });
        return J({ ok: true }); }
      case "llm": { if (!isW) break; return J(await llm(b, who)); }
      case "enqueue": { if (!isW) break; return J({ ok: true, ...(await enqueue(b.kind, b.project_id || null, b.payload || {}, b.runner)) }); }
      case "version": return J({ ok: true, version: FN_VERSION });
      case "metricool": { if (!isW) break;
        // רק ה-scheduler של Metricool, רק המותגים שלנו. הטוקן לא יוצא מכאן.
        const tok = await secret("metricool_token"); if (!tok) return J({ ok: false, error: "not_configured" });
        const path = String(b.path || ""); if (!/^\/api\/v2\/scheduler\/posts(\/[0-9]+)?$/.test(path)) return J({ ok: false, error: "path" }, 400);
        const q = new URLSearchParams({ ...(b.query || {}), userId: METRICOOL_USER }); if (!["6323702", "6436350", "6519658"].includes(q.get("blogId") || "")) return J({ ok: false, error: "blog" }, 400);
        const r = await fetch(`https://app.metricool.com${path}?${q}`, { method: b.method || "GET", headers: { "X-Mc-Auth": tok, "content-type": "application/json" }, body: b.body ? JSON.stringify(b.body) : undefined, signal: AbortSignal.timeout(120000) });
        const txt = await r.text(); let data: any = null; try { data = JSON.parse(txt); } catch { data = txt.slice(0, 500); }
        if (r.status === 401 || r.status === 403) await health("metricool", "failed", "טוקן Metricool לא תקף. להדביק מחדש בעמוד (מפתחות)");
        return J({ ok: r.ok, status: r.status, data }); }
      case "monday_date": { if (!isW) break;
        const d = await monday(`query($id:[ID!]){items(ids:$id){name column_values(ids:["date_mkrpvw3n"]){value}}}`, { id: [String(b.item_id)] });
        const it = d.items?.[0]; return J({ ok: true, name: it?.name, date: it?.column_values?.[0]?.value ? JSON.parse(it.column_values[0].value) : null }); }
      // L162: תאריכי פרסום נקבעים בשלב ההפקה. קריאת כל התאריכים בגאנט + כתיבת תאריך לפריט (UTC).
      case "board_dates": { if (!isW) break;
        const out: any[] = []; let cursor: string | null = null;
        do {
          const d: any = cursor ? await monday(`query($c:String!){next_items_page(cursor:$c,limit:500){cursor items{id name column_values(ids:["date_mkrpvw3n"]){value}}}}`, { c: cursor })
            : await monday(`query{boards(ids:[18395578529]){items_page(limit:500){cursor items{id name column_values(ids:["date_mkrpvw3n"]){value}}}}}`);
          const pg = cursor ? d.next_items_page : d.boards[0].items_page; cursor = pg.cursor;
          for (const it of pg.items) { const v = it.column_values?.[0]?.value; if (v) { const j = JSON.parse(v); if (j?.date) out.push({ id: it.id, name: it.name, date: j.date, time: j.time || null }); } }
        } while (cursor);
        return J({ ok: true, items: out }); }
      case "monday_set_date": { if (!isW) break;
        await monday(`mutation($b:ID!,$i:ID!,$v:JSON!){change_column_value(board_id:$b,item_id:$i,column_id:"date_mkrpvw3n",value:$v){id}}`, { b: "18395578529", i: String(b.item_id), v: JSON.stringify({ date: b.date, time: b.time }) });
        if (b.update) await monday(`mutation($i:ID!,$t:String!){create_update(item_id:$i,body:$t){id}}`, { i: String(b.item_id), t: b.update });
        return J({ ok: true }); }
      case "monday_file": { if (!isW) break;
        // העלאת קובץ מה-Storage לעמודת קובץ במאנדיי (סרטון מוכן). הטוקן נשאר כאן.
        const t = await secret("monday_token"); const { data: blob, error } = await sb.storage.from(BUCKET).download(b.path); if (error || !blob) return J({ ok: false, error: error?.message || "download" });
        const fd = new FormData(); fd.append("query", `mutation($f:File!){add_file_to_column(item_id:${Number(b.item_id)},column_id:"${b.column_id || "file_mm402fp7"}",file:$f){id}}`); fd.append("variables[file]", blob, b.name || "file");
        const r = await fetch("https://api.monday.com/v2/file", { method: "POST", headers: { authorization: t! }, body: fd }); const j = await r.json().catch(() => ({}));
        return J({ ok: !!j?.data?.add_file_to_column?.id, id: j?.data?.add_file_to_column?.id, error: j?.errors ? JSON.stringify(j.errors).slice(0, 200) : undefined }); }
      case "resume": { if (who.role !== "admin") break;
        // L160: מה שנדחה (תקרה יומית), נתקע (runner מת) או אושר ומחכה לתאריך — חוזר לתור לבד. בלי Claude ובלי מייל.
        const out: any = { deferred: 0, stale: 0, retried: 0, schedule: 0 };
        for (const j of await sql`update video.jobs set status='queued' where status='deferred' and created_at > now()-interval '10 days' returning id`) { await dispatch(j.id); out.deferred++; }
        for (const j of await sql`update video.jobs set status='failed', finished_at=now(), result=coalesce(result,'{}'::jsonb)||'{"error":"stale: runner died"}'::jsonb where status='running' and runner='actions' and started_at < now()-interval '3 hours' returning kind, project_id, payload`) { await enqueue(j.kind, j.project_id, j.payload); out.stale++; }
        // ג'וב שנכשל ואין אחריו ג'וב חדש לאותו פרויקט: ניסיון חוזר אחד ביום, עד 3 כשלים ב-72 שעות
        for (const j of await sql`select distinct on (project_id) id, kind, project_id, payload, status from video.jobs where project_id is not null and kind in ('prep','notes','finish','refinish','cover','judge','schedule') order by project_id, created_at desc`) {
          if (j.status !== "failed") continue;
          const n = (await sql`select count(*)::int n from video.jobs where project_id=${j.project_id} and kind=${j.kind} and status='failed' and created_at > now()-interval '72 hours'`)[0].n;
          const pr = (await sql`select hidden, state from video.projects where id=${j.project_id}`)[0];
          if (n <= 3 && pr && !pr.hidden && !["scheduled", "published"].includes(pr.state)) { await enqueue(j.kind, j.project_id, j.payload); out.retried++; }
        }
        for (const p of await sql`select id from video.projects where state='ready_to_schedule' and not hidden and not exists (select 1 from video.jobs j where j.project_id=video.projects.id and j.kind='schedule' and j.status in ('queued','running'))`) { await enqueue("schedule", p.id, { trigger: "resume" }); out.schedule++; }
        await health("resume", "ok", ""); return J({ ok: true, ...out }); }
      case "redispatch": { if (who.role !== "admin") break; return J({ ok: true, dispatch: await dispatch(b.job_id) }); }
      case "jobs": { if (!isW) break; return J({ ok: true, jobs: await sql`select id, project_id, kind, status, runner, attempts, dispatch, created_at, finished_at from video.jobs where status = any(${b.status || ["queued", "running"]}) order by created_at limit 50` }); }
      case "costs": { if (!isW) break; return J({ ok: true, per_project: await sql`select project_id, round(sum(usd),4)::float usd, count(*) calls, sum(input_tokens) tin, sum(output_tokens) tout from video.costs group by 1`, per_day: await sql`select * from video.v_cost_per_day order by d desc limit 30` }); }
    }
    return J({ ok: false, error: `op not allowed: ${op}` }, 403);
  } catch (e) { return J({ ok: false, error: String((e as Error).message || e).slice(0, 400) }, 500); }
});
