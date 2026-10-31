-- Additive hybrid retrieval foundation. Existing keyword RPC remains operational.
begin;
create extension if not exists pgcrypto with schema extensions;
alter table public.finn_research_chunks
  add column if not exists body_hash text generated always as
    (encode(extensions.digest(body, 'sha256'), 'hex')) stored,
  add column if not exists embedding_input_hash text,
  add column if not exists embedding_version text,
  add column if not exists embedded_at timestamptz;

create table if not exists public.finn_embedding_cache (
  model text not null,
  dimensions smallint not null check (dimensions = 768),
  task_type text not null check (task_type in ('RETRIEVAL_DOCUMENT','RETRIEVAL_QUERY')),
  version text not null,
  input_hash text not null,
  embedding extensions.vector(768) not null,
  created_at timestamptz not null default now(),
  primary key (model, dimensions, task_type, version, input_hash)
);
create table if not exists public.finn_embedding_requests (
  id bigint generated always as identity primary key,
  model text not null,
  operation text not null check (operation in ('count','embed')),
  input_count integer not null check (input_count > 0),
  input_tokens integer not null check (input_tokens >= 0),
  reserved_at timestamptz not null default now()
);
create index if not exists finn_embedding_request_time
  on public.finn_embedding_requests(model,reserved_at);
alter table public.finn_embedding_cache enable row level security;
alter table public.finn_embedding_requests enable row level security;
revoke all on public.finn_embedding_cache, public.finn_embedding_requests from public,anon,authenticated;
grant all on public.finn_embedding_cache, public.finn_embedding_requests to service_role;
grant usage, select on sequence public.finn_embedding_requests_id_seq to service_role;

create or replace function public.finn_reserve_embedding_request(
  p_model text, p_operation text, p_input_count integer, p_tokens integer,
  p_rpm integer default 80, p_rpd integer default 800, p_tpm integer default 27000
) returns jsonb language plpgsql security invoker set search_path='' as $$
declare minute_calls integer; day_calls integer; tokens integer; oldest timestamptz; day_start timestamptz;
begin
  if p_input_count < 1 or p_tokens < 0 or p_operation not in ('count','embed') then
    raise exception 'Invalid embedding reservation';
  end if;
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext('finn-embedding-' || p_model));
  day_start := ((now() at time zone 'America/Los_Angeles')::date::timestamp at time zone 'America/Los_Angeles');
  select count(*) filter(where reserved_at > now()-interval '1 minute'), count(*) filter(where reserved_at >= day_start),
    coalesce(sum(input_tokens) filter(where reserved_at > now()-interval '1 minute'),0),
    min(reserved_at) filter(where reserved_at > now()-interval '1 minute')
  into minute_calls,day_calls,tokens,oldest
  from public.finn_embedding_requests where model=p_model and reserved_at >= least(day_start,now()-interval '1 minute');
  if day_calls >= least(greatest(p_rpd,1),800) then
    return jsonb_build_object('allowed',false,'reason','daily_budget','retry_after',86400);
  end if;
  if p_tokens > least(greatest(p_tpm,1),27000) then
    return jsonb_build_object('allowed',false,'reason','batch_too_large','retry_after',0);
  end if;
  if minute_calls >= least(greatest(p_rpm,1),80) or tokens+p_tokens > least(greatest(p_tpm,1),27000) then
    return jsonb_build_object('allowed',false,'reason','minute_budget',
      'retry_after',greatest(1,ceil(extract(epoch from oldest+interval '61 seconds'-now()))));
  end if;
  insert into public.finn_embedding_requests(model,operation,input_count,input_tokens)
    values(p_model,p_operation,p_input_count,p_tokens);
  return jsonb_build_object('allowed',true,'retry_after',0);
end $$;

create or replace function public.finn_embedding_status(p_symbol text, p_model text, p_version text)
returns jsonb language sql stable security invoker set search_path='' as $$
  with active as (
    select c.* from public.finn_research_chunks c
    join public.finn_documents d on d.id=c.document_id
    join public.finn_companies co on co.symbol=d.symbol and d.id=any(co.manifest)
    where d.state='ready' and (p_symbol is null or d.symbol=p_symbol)
  ), checked as (
    select *, embedding is not null and embedding_model=p_model and embedding_dimensions=768
      and embedding_version=p_version and embedding_input_hash=body_hash as valid from active
  ) select jsonb_build_object('total',count(*),'ready',count(*) filter(where valid),
    'fingerprint',encode(extensions.digest(coalesce(string_agg(id::text||body_hash,',' order by id)
      filter(where valid),''),'sha256'),'hex'),
    'secure', (select bool_and(relrowsecurity) from pg_class
      where oid in ('public.finn_embedding_cache'::regclass,'public.finn_embedding_requests'::regclass))
      and not has_table_privilege('anon','public.finn_embedding_cache','SELECT,INSERT,UPDATE,DELETE')
      and not has_table_privilege('authenticated','public.finn_embedding_cache','SELECT,INSERT,UPDATE,DELETE')
      and not has_table_privilege('anon','public.finn_embedding_requests','SELECT,INSERT,UPDATE,DELETE')
      and not has_table_privilege('authenticated','public.finn_embedding_requests','SELECT,INSERT,UPDATE,DELETE'))
  from checked;
$$;

create or replace function public.finn_pending_embeddings(
  p_symbol text, p_model text, p_version text, p_limit integer default 32
) returns table(chunk_id uuid, document_id uuid, body text, body_hash text)
language sql stable security invoker set search_path='' as $$
  select c.id,c.document_id,c.body,c.body_hash from public.finn_research_chunks c
  join public.finn_documents d on d.id=c.document_id
  join public.finn_companies co on co.symbol=d.symbol and d.id=any(co.manifest)
  where d.state='ready' and (p_symbol is null or d.symbol=p_symbol)
    and (c.embedding is null or c.embedding_model is distinct from p_model
      or c.embedding_dimensions is distinct from 768 or c.embedding_version is distinct from p_version
      or c.embedding_input_hash is distinct from c.body_hash)
  order by d.symbol,d.kind desc,c.pdf_page,c.ordinal,c.id
  limit greatest(1,least(p_limit,64));
$$;

create or replace function public.finn_store_chunk_embedding(
  p_chunk_id uuid,p_input_hash text,p_embedding extensions.vector,p_model text,p_version text
) returns boolean language plpgsql security invoker set search_path='' as $$
declare changed integer;
begin
  if extensions.vector_dims(p_embedding) <> 768 then raise exception 'Embedding dimensions must be 768'; end if;
  update public.finn_research_chunks set embedding=p_embedding,embedding_model=p_model,
    embedding_dimensions=768,embedding_input_hash=p_input_hash,embedding_version=p_version,embedded_at=now()
  where id=p_chunk_id and body_hash=p_input_hash;
  get diagnostics changed=row_count;
  return changed=1;
end $$;

create or replace function public.finn_keyword_search_v2(
  p_symbol text,p_query text,p_kinds text[] default null,p_published_before timestamptz default null,
  p_document_ids uuid[] default null,p_published_after timestamptz default null,
  p_reporting_period text default null,p_metadata jsonb default null,p_limit integer default 30
) returns table(chunk_id uuid,document_id uuid,pdf_page integer,body text,kind text,source_url text,
  discovery_label text,published_at timestamptz,reporting_period text,fetched_at timestamptz,metadata jsonb,rank real)
language sql stable security invoker set search_path='' as $$
  select c.id,d.id,c.pdf_page,c.body,d.kind,d.source_url,d.discovery_label,d.published_at,
    d.reporting_period,d.fetched_at,c.metadata,
    pg_catalog.ts_rank_cd(c.fts,pg_catalog.websearch_to_tsquery('english',p_query)) as rank
  from public.finn_research_chunks c join public.finn_documents d on d.id=c.document_id
  join public.finn_companies co on co.symbol=d.symbol and d.id=any(co.manifest)
  where d.symbol=p_symbol and d.state='ready'
    and (p_kinds is null or d.kind=any(p_kinds))
    and (p_document_ids is null or d.id=any(p_document_ids))
    and (p_published_before is null or d.published_at<=p_published_before)
    and (p_published_after is null or d.published_at>=p_published_after)
    and (p_reporting_period is null or d.reporting_period=p_reporting_period)
    and (p_metadata is null or c.metadata @> p_metadata)
    and c.fts @@ pg_catalog.websearch_to_tsquery('english',p_query)
  order by rank desc,d.id,c.pdf_page,c.ordinal,c.id limit greatest(1,least(p_limit,100));
$$;

create or replace function public.finn_semantic_search(
  p_symbol text,p_embedding extensions.vector,p_model text,p_version text,
  p_kinds text[] default null,p_published_before timestamptz default null,
  p_document_ids uuid[] default null,p_published_after timestamptz default null,
  p_reporting_period text default null,p_metadata jsonb default null,p_limit integer default 30
) returns table(chunk_id uuid,document_id uuid,pdf_page integer,body text,kind text,source_url text,
  discovery_label text,published_at timestamptz,reporting_period text,fetched_at timestamptz,metadata jsonb,rank real)
language sql stable security invoker set search_path='' as $$
  -- Exact cosine after filtering: small per-company corpus, deterministic recall.
  -- No global ANN index whose post-filters could silently remove company evidence.
  with eligible as materialized (
    select c.id,d.id as document_id,c.pdf_page,c.ordinal,c.body,d.kind,d.source_url,d.discovery_label,
      d.published_at,d.reporting_period,d.fetched_at,c.metadata,c.embedding
    from public.finn_research_chunks c join public.finn_documents d on d.id=c.document_id
    join public.finn_companies co on co.symbol=d.symbol and d.id=any(co.manifest)
    where d.symbol=p_symbol and d.state='ready'
      and c.embedding is not null and c.embedding_model=p_model and c.embedding_dimensions=768
      and c.embedding_version=p_version and c.embedding_input_hash=c.body_hash
      and (p_kinds is null or d.kind=any(p_kinds))
      and (p_document_ids is null or d.id=any(p_document_ids))
      and (p_published_before is null or d.published_at<=p_published_before)
      and (p_published_after is null or d.published_at>=p_published_after)
      and (p_reporting_period is null or d.reporting_period=p_reporting_period)
      and (p_metadata is null or c.metadata @> p_metadata)
  ) select id,document_id,pdf_page,body,kind,source_url,discovery_label,published_at,
    reporting_period,fetched_at,metadata,(1-(embedding operator(extensions.<=>) p_embedding))::real as rank
  from eligible order by embedding operator(extensions.<=>) p_embedding,document_id,pdf_page,ordinal,id
  limit greatest(1,least(p_limit,100));
$$;

-- All source text, vectors, query hashes and quota accounting stay server-only.
do $$ declare signature text;
begin
  foreach signature in array array[
    'finn_reserve_embedding_request(text,text,integer,integer,integer,integer,integer)',
    'finn_embedding_status(text,text,text)', 'finn_pending_embeddings(text,text,text,integer)',
    'finn_store_chunk_embedding(uuid,text,extensions.vector,text,text)',
    'finn_keyword_search_v2(text,text,text[],timestamptz,uuid[],timestamptz,text,jsonb,integer)',
    'finn_semantic_search(text,extensions.vector,text,text,text[],timestamptz,uuid[],timestamptz,text,jsonb,integer)'
  ] loop
    execute 'revoke all on function public.'||signature||' from public,anon,authenticated';
    execute 'grant execute on function public.'||signature||' to service_role';
  end loop;
end $$;
commit;
notify pgrst,'reload schema';
