-- L168 (3.11.26): הערות שנשלחו טופלו אבל הג'וב המקורי עבר הסלמה ⇒ consume_action לא קרה ⇒ "הערות נשלחו" לנצח.
create or replace function video.consume_actions_on_review() returns trigger language plpgsql security definer set search_path = video, public as $$
begin
  if new.state in ('review','cover_review') and (old.state is distinct from new.state or old.version is distinct from new.version or old.video_path is distinct from new.video_path) then
    update video.actions set consumed = true, consumed_at = now(), handled_as = 'auto:back_to_harel'
     where project_id = new.id and not consumed and at < now() - interval '1 minute'
       and type in ('send_notes','approve_publish','request_cover_change')
       and not exists (select 1 from video.comments c where c.project_id = new.id and c.status = 'sent');
  end if;
  return new;
end $$;
drop trigger if exists trg_consume_actions_on_review on video.projects;
create trigger trg_consume_actions_on_review after update on video.projects for each row execute function video.consume_actions_on_review();
