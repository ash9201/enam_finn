-- Optional cached, source-backed presentation of an existing public exchange filing.
-- No new tables, grants or policies. Existing filing RLS remains enabled.
begin;
alter table public.finn_filings add column if not exists enrichment jsonb;
comment on column public.finn_filings.enrichment is
  'Versioned official-source excerpts, event metadata and extraction status; never inferred financial figures.';
alter table public.finn_filings enable row level security;
commit;
notify pgrst, 'reload schema';
