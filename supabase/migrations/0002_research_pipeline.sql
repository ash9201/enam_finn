-- Milestone 1: keyword-first company research. No semantic search runs yet.
begin;

create table if not exists public.finn_companies (
  symbol text primary key,
  name text not null,
  isin text,
  portfolio boolean not null default false,
  sector text,
  manifest uuid[] not null default '{}',
  corpus_fingerprint text,
  source_checked_at timestamptz,
  coverage jsonb not null default '{}'
);
create table if not exists public.finn_documents (
  id uuid primary key,
  symbol text not null references public.finn_companies(symbol),
  kind text not null check (kind in ('annual_report', 'transcript')),
  sha256 text not null,
  source_url text not null,
  final_url text not null,
  discovery_url text not null,
  discovery_label text not null,
  published_at timestamptz,
  reporting_period text,
  fetched_at timestamptz not null,
  extracted_at timestamptz not null,
  page_count integer not null,
  storage_path text not null,
  table_candidates jsonb not null default '[]',
  extraction_notes jsonb not null default '{}',
  state text not null default 'extracting' check (state in ('extracting', 'ready')),
  unique (symbol, kind, sha256)
);
create table if not exists public.finn_document_pages (
  document_id uuid not null references public.finn_documents(id) on delete cascade,
  pdf_page integer not null check (pdf_page > 0),
  layout_text text not null,
  metadata jsonb not null default '{}',
  primary key (document_id, pdf_page)
);
create table if not exists public.finn_research_chunks (
  id uuid primary key,
  document_id uuid not null references public.finn_documents(id) on delete cascade,
  pdf_page integer not null check (pdf_page > 0),
  ordinal integer not null,
  body text not null,
  metadata jsonb not null default '{}',
  fts tsvector generated always as (to_tsvector('english'::regconfig, body)) stored,
  embedding extensions.vector(768),
  embedding_model text,
  embedding_dimensions smallint,
  check ((embedding is null and embedding_model is null and embedding_dimensions is null)
      or (embedding is not null and embedding_model is not null and embedding_dimensions = 768)),
  unique (document_id, pdf_page, ordinal)
);
create index if not exists finn_chunks_fts on public.finn_research_chunks using gin (fts);
create index if not exists finn_chunks_document on public.finn_research_chunks(document_id);
create table if not exists public.finn_research_cache (
  id uuid primary key,
  cache_key text not null unique,
  symbol text not null references public.finn_companies(symbol),
  question text not null,
  corpus_fingerprint text not null,
  model text not null,
  prompt_version text not null,
  result jsonb not null,
  is_public boolean not null default false,
  created_at timestamptz not null default now()
);
create table if not exists public.finn_research_jobs (
  id uuid primary key,
  symbol text not null,
  question text not null,
  state text not null default 'queued' check (state in ('queued', 'running', 'completed', 'failed')),
  stage text not null default 'queued',
  refresh boolean not null default false,
  result jsonb,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table if not exists public.finn_model_calls (
  id bigint generated always as identity primary key,
  model text not null,
  reserved_at timestamptz not null default now()
);
create index if not exists finn_calls_time on public.finn_model_calls(model, reserved_at);

-- Private source text, jobs, custom questions, and model usage are server-only.
do $$
declare t text;
begin
  foreach t in array array['finn_companies','finn_documents','finn_document_pages',
      'finn_research_chunks','finn_research_cache','finn_research_jobs','finn_model_calls']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
    execute format('grant all on public.%I to service_role', t);
  end loop;
end $$;
grant usage, select on sequence public.finn_model_calls_id_seq to service_role;
grant select on public.finn_companies to anon, authenticated;
drop policy if exists "Read company directory" on public.finn_companies;
create policy "Read company directory" on public.finn_companies for select
  to anon, authenticated using (true);
grant select on public.finn_research_cache to anon, authenticated;
drop policy if exists "Read published research only" on public.finn_research_cache;
create policy "Read published research only" on public.finn_research_cache for select
  to anon, authenticated using (is_public);

create or replace function public.finn_keyword_search(
  p_symbol text, p_query text, p_kinds text[] default null,
  p_published_before timestamptz default null, p_limit integer default 12
)
returns table (
  chunk_id uuid, document_id uuid, pdf_page integer, body text,
  kind text, source_url text, discovery_label text, published_at timestamptz,
  reporting_period text, fetched_at timestamptz, metadata jsonb, rank real
)
language sql stable security invoker set search_path = ''
as $$
  select c.id, d.id, c.pdf_page, c.body, d.kind, d.source_url, d.discovery_label,
      d.published_at, d.reporting_period, d.fetched_at, c.metadata,
      pg_catalog.ts_rank_cd(c.fts, pg_catalog.websearch_to_tsquery('english', p_query)) as rank
  from public.finn_research_chunks c
  join public.finn_documents d on d.id = c.document_id
  join public.finn_companies co on co.symbol = d.symbol and d.id = any(co.manifest)
  where d.symbol = p_symbol and d.state = 'ready'
    and (p_kinds is null or d.kind = any(p_kinds))
    -- Unknown publication dates cannot satisfy an explicit historical cutoff.
    and (p_published_before is null or d.published_at <= p_published_before)
    and c.fts @@ pg_catalog.websearch_to_tsquery('english', p_query)
  order by rank desc, d.id, c.pdf_page, c.ordinal
  limit greatest(1, least(p_limit, 30));
$$;
revoke all on function public.finn_keyword_search(text,text,text[],timestamptz,integer) from public, anon, authenticated;
grant execute on function public.finn_keyword_search(text,text,text[],timestamptz,integer) to service_role;

create or replace function public.finn_reserve_model_call(p_model text, p_rpm integer, p_rpd integer)
returns boolean language plpgsql security invoker set search_path = '' as $$
declare minute_count integer; day_count integer;
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext('finn-model-' || p_model));
  select count(*) filter (where reserved_at >= now() - interval '1 minute'), count(*)
    into minute_count, day_count from public.finn_model_calls
    where model = p_model and reserved_at >=
      ((now() at time zone 'America/Los_Angeles')::date::timestamp at time zone 'America/Los_Angeles');
  if minute_count >= least(p_rpm,12) or day_count >= least(p_rpd,400) then return false; end if;
  insert into public.finn_model_calls(model) values(p_model);
  return true;
end;
$$;
revoke all on function public.finn_reserve_model_call(text,integer,integer) from public, anon, authenticated;
grant execute on function public.finn_reserve_model_call(text,integer,integer) to service_role;

commit;
notify pgrst, 'reload schema';
