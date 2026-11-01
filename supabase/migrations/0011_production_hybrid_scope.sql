-- Current primary documents share one private search/indexing scope.
-- Superseded PDFs remain stored for existing citations, outside new retrieval.
begin;
create index if not exists finn_document_source_versions
  on public.finn_documents(symbol,kind,source_url,extracted_at desc,id);
create or replace view public.finn_search_documents with (security_invoker=true) as
  select d.* from public.finn_documents d
  join public.finn_companies co on co.symbol=d.symbol
  where d.state='ready' and d.id=any(co.manifest)
  union all
  select q.* from (
    select distinct on (symbol,kind,source_url) d.* from public.finn_documents d
    where kind='quarterly_results' and state='ready'
    order by symbol,kind,source_url,extracted_at desc,id desc
  ) q where not exists (
    select 1 from public.finn_companies co where q.id=any(co.manifest)
  );
revoke all on public.finn_search_documents from public,anon,authenticated;
grant select on public.finn_search_documents to service_role;

create or replace function public.finn_embedding_status(p_symbol text, p_model text, p_version text)
returns jsonb language sql stable security invoker set search_path='' as $$
  with active as (
    select c.* from public.finn_research_chunks c
    join public.finn_search_documents d on d.id=c.document_id
    where d.state='ready' and (p_symbol is null or d.symbol=p_symbol)
  ), checked as (
    select *, embedding is not null and embedding_model=p_model and embedding_dimensions=768
      and embedding_version=p_version and embedding_input_hash=body_hash as valid from active
  ) select jsonb_build_object('total',count(*),'ready',count(*) filter(where valid),
    'documents',count(distinct document_id),
    'scope_fingerprint',encode(extensions.digest(coalesce(string_agg(id::text||body_hash,',' order by id),''),'sha256'),'hex'),
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
  join public.finn_search_documents d on d.id=c.document_id
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
  from public.finn_research_chunks c join public.finn_search_documents d on d.id=c.document_id
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
    from public.finn_research_chunks c join public.finn_search_documents d on d.id=c.document_id
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

-- A whole bounded batch commits atomically; stale bodies are never overwritten.
create or replace function public.finn_store_chunk_embeddings(
  p_rows jsonb,p_model text,p_version text
) returns integer language plpgsql security invoker set search_path='' as $$
declare changed integer;
begin
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) not between 1 and 32
    then raise exception 'Use 1 to 32 vectors'; end if;
  if exists(select 1 from jsonb_array_elements(p_rows) r
    where extensions.vector_dims((r->>'embedding')::extensions.vector) <> 768)
    then raise exception 'Embedding dimensions must be 768'; end if;
  update public.finn_research_chunks c set
    embedding=(r->>'embedding')::extensions.vector,embedding_model=p_model,
    embedding_dimensions=768,embedding_input_hash=r->>'body_hash',
    embedding_version=p_version,embedded_at=now()
  from jsonb_array_elements(p_rows) r
  where c.id=(r->>'chunk_id')::uuid and c.body_hash=r->>'body_hash';
  get diagnostics changed=row_count;
  return changed;
end $$;

-- Read-only preflight prevents burning token-count calls after the daily allowance.
-- The reservation RPC remains authoritative under concurrency.
create or replace function public.finn_embedding_budget(p_model text,p_rpd integer)
returns jsonb language sql stable security invoker set search_path='' as $$
  select jsonb_build_object('remaining',greatest(0,least(greatest(p_rpd,1),900)-
    coalesce(sum(case when operation='embed' then input_count else 1 end),0)))
  from public.finn_embedding_requests where model=p_model and reserved_at >=
    ((now() at time zone 'America/Los_Angeles')::date::timestamp at time zone 'America/Los_Angeles');
$$;

-- Server-only inventory, including empty companies and completed-document counts.
create or replace function public.finn_embedding_inventory(p_model text,p_version text)
returns jsonb language sql stable security invoker set search_path='' as $$
  with docs as (
    select d.symbol,d.id,d.kind,count(c.id) as total,
      count(c.id) filter(where c.embedding is not null and c.embedding_model=p_model
        and c.embedding_dimensions=768 and c.embedding_version=p_version
        and c.embedding_input_hash=c.body_hash) as ready
    from public.finn_search_documents d left join public.finn_research_chunks c on c.document_id=d.id
    group by d.symbol,d.id,d.kind
  ), companies as (
    select co.symbol,co.portfolio,count(d.id) as documents,
      count(d.id) filter(where d.total>0 and d.ready=d.total) as indexed_documents,
      coalesce(sum(d.total),0) as total,coalesce(sum(d.ready),0) as ready
    from public.finn_companies co left join docs d on d.symbol=co.symbol
    group by co.symbol,co.portfolio order by co.portfolio desc,co.symbol
  ) select jsonb_build_object('database_bytes',pg_catalog.pg_database_size(pg_catalog.current_database()),
    'companies',coalesce(jsonb_agg(to_jsonb(companies)),'[]'::jsonb)) from companies;
$$;

do $$ declare signature text;
begin
  foreach signature in array array[
    'finn_embedding_status(text,text,text)', 'finn_pending_embeddings(text,text,text,integer)',
    'finn_store_chunk_embedding(uuid,text,extensions.vector,text,text)',
    'finn_store_chunk_embeddings(jsonb,text,text)', 'finn_embedding_budget(text,integer)',
    'finn_embedding_inventory(text,text)',
    'finn_keyword_search_v2(text,text,text[],timestamptz,uuid[],timestamptz,text,jsonb,integer)',
    'finn_semantic_search(text,extensions.vector,text,text,text[],timestamptz,uuid[],timestamptz,text,jsonb,integer)'
  ] loop
    execute 'revoke all on function public.'||signature||' from public,anon,authenticated';
    execute 'grant execute on function public.'||signature||' to service_role';
  end loop;
end $$;
commit;
notify pgrst,'reload schema';
