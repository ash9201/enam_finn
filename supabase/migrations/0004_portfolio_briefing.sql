-- Public read-only market/filing metadata for the fixed mock portfolio.
begin;
create table if not exists public.finn_filings (
  id text primary key,
  symbol text not null references public.finn_companies(symbol),
  company_name text not null,
  title text not null,
  description text not null,
  source_url text not null,
  published_at timestamptz not null,
  category text not null,
  priority smallint not null check (priority between 0 and 3),
  review_reason text not null,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);
create index if not exists finn_filings_time on public.finn_filings(published_at desc);
create table if not exists public.finn_price_snapshots (
  symbol text primary key references public.finn_companies(symbol),
  data jsonb,
  error text,
  last_attempt_at timestamptz not null,
  last_success_at timestamptz
);
create table if not exists public.finn_sync_status (
  id text primary key check (id in ('filings','prices')),
  state text not null check (state in ('running','completed','partial','failed')),
  started_at timestamptz not null,
  finished_at timestamptz,
  last_success_at timestamptz,
  captured_since timestamptz,
  error text,
  details jsonb not null default '{}'
);
do $$
declare t text;
begin
  foreach t in array array['finn_filings','finn_price_snapshots','finn_sync_status'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
    execute format('grant select on public.%I to anon, authenticated', t);
    execute format('grant all on public.%I to service_role', t);
    execute format('drop policy if exists "Read portfolio data" on public.%I', t);
    execute format('create policy "Read portfolio data" on public.%I for select to anon, authenticated using (true)', t);
  end loop;
end $$;
commit;
notify pgrst, 'reload schema';
