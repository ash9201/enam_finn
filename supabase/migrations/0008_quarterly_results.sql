-- Primary quarterly-result documents use the existing private document/evidence store.
begin;
alter table public.finn_documents drop constraint if exists finn_documents_kind_check;
alter table public.finn_documents add constraint finn_documents_kind_check
  check (kind in ('annual_report', 'transcript', 'quarterly_results'));

-- Bounded, explicit-document search for financial evidence, independent of the
-- annual-report/transcript manifest. Never makes raw financial pages public.
create or replace function public.finn_results_keyword_search(
  p_symbol text, p_query text, p_document_ids uuid[], p_limit integer default 10
) returns table (
  chunk_id uuid, document_id uuid, pdf_page integer, body text, kind text,
  source_url text, document_url text, discovery_label text, published_at timestamptz,
  reporting_period text, fetched_at timestamptz, metadata jsonb, rank real
) language sql stable security invoker set search_path = '' as $$
  select c.id, d.id, c.pdf_page, c.body, d.kind, d.source_url, d.final_url,
    d.discovery_label, d.published_at, d.reporting_period, d.fetched_at, c.metadata,
    pg_catalog.ts_rank_cd(c.fts, pg_catalog.websearch_to_tsquery('english', p_query)) as search_rank
  from public.finn_research_chunks c join public.finn_documents d on d.id = c.document_id
  where d.symbol = p_symbol and d.kind = 'quarterly_results' and d.state = 'ready'
    and d.id = any(p_document_ids)
    and c.fts @@ pg_catalog.websearch_to_tsquery('english', p_query)
  order by search_rank desc, c.id limit greatest(1, least(p_limit, 20));
$$;
revoke all on function public.finn_results_keyword_search(text,text,uuid[],integer)
  from public, anon, authenticated;
grant execute on function public.finn_results_keyword_search(text,text,uuid[],integer)
  to service_role;
-- Preserve existing RLS and grants; no new public policy or storage bucket.
alter table public.finn_documents enable row level security;
alter table public.finn_document_pages enable row level security;
alter table public.finn_research_chunks enable row level security;
commit;
