-- L167 (3.11.26): ריל שסומן "מוכן לעריכה" לא הופיע בעמוד עד שה-prep רץ. ג'וב prep חדש יוצר מיד שורת פרויקט "בהכנה".
create or replace function video.prep_placeholder() returns trigger language plpgsql security definer set search_path = video, public as $$
begin
  if new.kind = 'prep' and new.project_id is not null then
    insert into video.projects(id, monday_item_id, title, state, updated_at)
    values (new.project_id, coalesce(new.payload->>'item_id', regexp_replace(new.project_id, '^p-', '')), coalesce(new.payload->>'title', 'ריל חדש, נכנס לעריכה'), 'draft', now())
    on conflict (id) do nothing;
  end if;
  return new;
end $$;
drop trigger if exists trg_prep_placeholder on video.jobs;
create trigger trg_prep_placeholder after insert on video.jobs for each row execute function video.prep_placeholder();
