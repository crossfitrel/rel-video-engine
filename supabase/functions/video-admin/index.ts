// video-admin — פעולות מנהל קטנות למערכת העריכה (v11): ביטול ג'וב, ופריט במאגר הפתוחים של קלאוד (hub.claude_item).
// הרשאה: x-video-admin = video_admin_key בכספת. לא מוחק כלום: ביטול = status='cancelled'.
import postgres from "npm:postgres@3.4.4";
const sql = postgres(Deno.env.get("SUPABASE_DB_URL")!, { max: 2, prepare: false });
const J = (b: unknown, s = 200) => new Response(JSON.stringify(b), { status: s, headers: { "content-type": "application/json; charset=utf-8" } });
Deno.serve(async (req) => {
  const key = (await sql`select decrypted_secret from vault.decrypted_secrets where name='video_admin_key'`)[0]?.decrypted_secret || "";
  const got = req.headers.get("x-video-admin") || "";
  if (!key || got.length !== key.length || got !== key) return J({ ok: false, error: "unauthorized" }, 401);
  const b = await req.json().catch(() => ({}));
  try {
    if (b.op === "job_cancel") {
      const r = await sql`update video.jobs set status='cancelled', finished_at=now(), result=coalesce(result,'{}'::jsonb)||${sql.json({ cancelled: b.reason || "" })} where id=${b.job_id} and status in ('queued','running') returning id`;
      return J({ ok: true, n: r.length });
    }
    if (b.op === "claude_item_add") {
      const dup = await sql`select ref from hub.claude_item where title=${b.title} and status not in ('closed') and deleted_at is null limit 1`;
      if (dup[0]) return J({ ok: true, ref: dup[0].ref, deduped: true });
      const r = await sql`insert into hub.claude_item(title,status,due_date,details,source_url,origin,third_party) values (${b.title}, ${b.status || "open"}, ${b.due_date}, ${b.details || ""}, ${b.source_url || null}, 'claude', ${b.third_party || null}) returning ref`;
      return J({ ok: true, ref: r[0].ref });
    }
    if (b.op === "claude_item_update") {
      const r = await sql`update hub.claude_item set status=coalesce(${b.status || null}, status), details=case when ${b.append || null}::text is null then details else details || E'\n\n' || ${b.append || ""} end, evidence=coalesce(${b.evidence || null}, evidence), updated_at=now(), closed_at=case when ${b.status || ""}='closed' then now() else closed_at end where ref=${b.ref} returning ref, status`;
      return J({ ok: true, row: r[0] || null });
    }
    if (b.op === "health") return J({ ok: true, rows: await sql`select * from video.system_health order by at desc` });
    return J({ ok: false, error: "op" }, 400);
  } catch (e) { return J({ ok: false, error: String((e as Error).message).slice(0, 300) }, 500); }
});
