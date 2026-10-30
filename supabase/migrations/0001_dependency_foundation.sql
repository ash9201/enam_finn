-- Milestone 0 only: no investor data or full retrieval implementation.
-- Run once in the project's SQL editor; rerunning is safe for these new objects.
begin;

create schema if not exists extensions;
create extension if not exists vector with schema extensions;

create table if not exists public.finn_dependency_probes (
  run_id uuid primary key,
  marker text not null,
  created_at timestamptz not null default now()
);
alter table public.finn_dependency_probes enable row level security;
revoke all on public.finn_dependency_probes from anon, authenticated;
grant all on public.finn_dependency_probes to service_role;
-- No public policies: privileged probe data must not be visible in the browser.

create table if not exists public.finn_public_status (
  id text primary key check (id = 'foundation'),
  milestone smallint not null default 0 check (milestone = 0),
  state text not null default 'foundation_only' check (state = 'foundation_only'),
  note text not null default 'Dependency verification is in progress. No financial data is published.'
);
alter table public.finn_public_status enable row level security;
revoke all on public.finn_public_status from anon, authenticated;
grant select on public.finn_public_status to anon, authenticated;
grant all on public.finn_public_status to service_role;
drop policy if exists "Public can read foundation status" on public.finn_public_status;
create policy "Public can read foundation status" on public.finn_public_status
  for select to anon, authenticated using (id = 'foundation');
insert into public.finn_public_status (id) values ('foundation') on conflict (id) do nothing;

create or replace function public.finn_dependency_capabilities()
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  vector_schema text;
  distance double precision;
begin
  select n.nspname into vector_schema
  from pg_catalog.pg_extension e
  join pg_catalog.pg_namespace n on n.oid = e.extnamespace
  where e.extname = 'vector';
  if vector_schema is null then raise exception 'pgvector is not installed'; end if;
  execute pg_catalog.format(
    'select ''[1,0,0]''::%I.vector OPERATOR(%I.<=>) ''[1,0,0]''::%I.vector',
    vector_schema, vector_schema, vector_schema
  ) into distance;
  return pg_catalog.jsonb_build_object(
    'full_text', pg_catalog.to_tsvector('english', 'operating cash flow')
      @@ pg_catalog.plainto_tsquery('english', 'cash flow'),
    'vector_cosine_distance', distance,
    'private_probe_rls', (select relrowsecurity from pg_catalog.pg_class where oid = 'public.finn_dependency_probes'::regclass),
    'public_cache_rls', (select relrowsecurity from pg_catalog.pg_class where oid = 'public.finn_public_status'::regclass)
  );
end;
$$;
revoke all on function public.finn_dependency_capabilities() from public, anon, authenticated;
grant execute on function public.finn_dependency_capabilities() to service_role;

-- Private, small PDF bucket. There are deliberately no anon storage.objects policies.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('finn-documents', 'finn-documents', false, 52428800, array['application/pdf'])
on conflict (id) do nothing;

commit;
notify pgrst, 'reload schema';
