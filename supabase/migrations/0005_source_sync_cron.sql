-- Run as the project owner in SQL Editor. Schedules remain OFF until the local
-- configuration script stores the API URL/credential in Vault and enables them.
begin;
create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;
create extension if not exists supabase_vault with schema vault;
create schema if not exists finn_internal;
revoke all on schema finn_internal from public, anon, authenticated;

create table if not exists public.finn_source_sync_job (
  id smallint primary key check (id = 1),
  token uuid not null,
  mode text not null check (mode in ('all','filings','prices')),
  origin text not null,
  state text not null check (state in ('queued','running','completed','partial','failed')),
  started_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  finished_at timestamptz,
  result jsonb not null default '{}',
  error text
);
alter table public.finn_source_sync_job enable row level security;
revoke all on public.finn_source_sync_job from public, anon, authenticated;
grant all on public.finn_source_sync_job to service_role;

create or replace function public.finn_acquire_source_sync(p_token uuid, p_mode text, p_origin text)
returns boolean language plpgsql security definer set search_path = '' as $$
declare acquired boolean;
begin
  if p_mode not in ('all','filings','prices') or p_origin not in ('supabase_cron','cloud_operator') then
    raise exception 'Invalid sync request';
  end if;
  -- One lease across both API services. An interrupted lease can be replaced
  -- after 45 minutes; this may skip a tick, never report a failed run as fresh.
  insert into public.finn_source_sync_job(id,token,mode,origin,state)
    values (1,p_token,p_mode,p_origin,'queued')
  on conflict (id) do update set token=excluded.token,mode=excluded.mode,
    origin=excluded.origin,state='queued',started_at=now(),updated_at=now(),
    finished_at=null,result='{}',error=null
  where public.finn_source_sync_job.state not in ('queued','running')
     or public.finn_source_sync_job.started_at < now() - interval '45 minutes'
  returning true into acquired;
  if coalesce(acquired,false) then
    update public.finn_sync_status set state='failed',finished_at=now(),
      error='A previous source refresh was interrupted. Retrying; earlier data retains its original dates.'
    where state='running' and started_at < now() - interval '45 minutes';
  end if;
  return coalesce(acquired,false);
end $$;
revoke all on function public.finn_acquire_source_sync(uuid,text,text) from public, anon, authenticated;
grant execute on function public.finn_acquire_source_sync(uuid,text,text) to service_role;

create or replace function finn_internal.trigger_source_sync(p_mode text)
returns bigint language plpgsql security definer set search_path = '' as $$
declare api_url text; api_key text; request_id bigint;
begin
  if p_mode not in ('all','filings','prices') then raise exception 'Invalid source mode'; end if;
  select decrypted_secret into api_url from vault.decrypted_secrets where name='finn_sync_api_url';
  select decrypted_secret into api_key from vault.decrypted_secrets where name='finn_sync_api_key';
  if api_url is null or api_key is null then raise exception 'FINN Cron Vault configuration missing'; end if;
  if api_url !~ '^https://[a-z0-9-]+[.]onrender[.]com$' then raise exception 'Expected the deployed Render API origin'; end if;
  select net.http_post(
    url := api_url || '/internal/source-sync',
    headers := jsonb_build_object('Content-Type','application/json','X-Finn-Sync-Key',api_key),
    body := jsonb_build_object('mode',p_mode,'trigger','cron'),
    timeout_milliseconds := 120000
  ) into request_id;
  return request_id;
end $$;
revoke all on function finn_internal.trigger_source_sync(text) from public, anon, authenticated;

-- Operator-only diagnostics: never return Vault values or request headers.
create or replace function public.finn_source_schedule_status()
returns jsonb language sql security definer set search_path = '' as $$
  select jsonb_build_object(
    'job_table_rls', (select relrowsecurity from pg_class where oid='public.finn_source_sync_job'::regclass),
    'schedules', coalesce((select jsonb_agg(jsonb_build_object('name',jobname,'schedule',schedule,'active',active))
      from cron.job where jobname in ('finn-filings','finn-eod-prices')), '[]'::jsonb),
    'recent_runs', coalesce((select jsonb_agg(x) from (
      select d.jobid,d.status,d.start_time,d.end_time from cron.job_run_details d
      where d.command like '%finn_internal.trigger_source_sync%'
      order by d.start_time desc limit 8) x), '[]'::jsonb),
    'http_responses', coalesce((select jsonb_agg(x) from (
      select id,status_code,timed_out,created from net._http_response
      order by created desc limit 8) x), '[]'::jsonb)
  );
$$;
revoke all on function public.finn_source_schedule_status() from public, anon, authenticated;
grant execute on function public.finn_source_schedule_status() to service_role;
commit;
notify pgrst, 'reload schema';
