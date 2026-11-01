-- L160 (1.11.26): פעם ביום, אחרי איפוס תקרת העלות היומית, מה שנדחה/נתקע/אושר ומחכה חוזר לתור לבד.
-- זו לא "בדיקה יומית" של Claude: קריאת DB אחת לפונקציית video, אפס עלות כשאין מה לעשות. המפתח לא יוצא מה-DB.
select cron.unschedule('video-resume') where exists (select 1 from cron.job where jobname = 'video-resume');
select cron.schedule('video-resume', '10 22 * * *', $$
  select net.http_post(
    url := 'https://xfsvbpqbfmqlwgyusrww.supabase.co/functions/v1/video',
    headers := jsonb_build_object('content-type', 'application/json',
                                  'x-video-admin', (select decrypted_secret from vault.decrypted_secrets where name = 'video_admin_key')),
    body := '{"op":"resume"}'::jsonb, timeout_milliseconds := 60000);
$$);
