-- Additive: old documents/citations remain intact when a financial parser changes.
begin;
alter table public.finn_documents add column if not exists extraction_version text not null default 'legacy';
alter table public.finn_documents drop constraint if exists finn_documents_symbol_kind_sha256_key;
create unique index if not exists finn_documents_content_version
  on public.finn_documents(symbol,kind,sha256,extraction_version);

-- Operational state only; no new queue service or public grants.
create table if not exists public.finn_embedding_jobs (
  symbol text not null references public.finn_companies(symbol),
  model text not null,
  version text not null,
  state text not null check (state in ('queued','running','paused_quota','pending','failed','complete')),
  reason text,
  ready integer not null default 0,
  total integer not null default 0,
  retry_at timestamptz,
  updated_at timestamptz not null default now(),
  lease_owner uuid,
  lease_until timestamptz,
  primary key (symbol,model,version)
);
alter table public.finn_embedding_jobs enable row level security;
revoke all on public.finn_embedding_jobs from public,anon,authenticated;
grant all on public.finn_embedding_jobs to service_role;
alter table public.finn_embedding_jobs add column if not exists lease_owner uuid;
alter table public.finn_embedding_jobs add column if not exists lease_until timestamptz;
create or replace function public.finn_claim_embedding_job(p_symbol text,p_model text,p_version text,p_owner uuid)
returns boolean language plpgsql security definer set search_path=public,pg_temp as $$
begin
  insert into public.finn_embedding_jobs(symbol,model,version,state,lease_owner,lease_until)
    values(p_symbol,p_model,p_version,'running',p_owner,now()+interval '5 minutes')
  on conflict(symbol,model,version) do update
    set state='running',reason=null,retry_at=null,lease_owner=p_owner,
        lease_until=now()+interval '5 minutes',updated_at=now()
    where finn_embedding_jobs.lease_until is null or finn_embedding_jobs.lease_until<now();
  return found;
end $$;
revoke all on function public.finn_claim_embedding_job(text,text,text,uuid) from public,anon,authenticated;
grant execute on function public.finn_claim_embedding_job(text,text,text,uuid) to service_role;
commit;
