-- Keep RLS ON. Safe to rerun: this preserves all data and existing intended policies.
begin;
do $$
declare t text;
begin
  foreach t in array array['finn_companies','finn_documents','finn_document_pages',
      'finn_research_chunks','finn_research_cache','finn_research_jobs','finn_model_calls']
  loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;

create or replace function public.finn_research_security_status()
returns jsonb language sql stable security invoker set search_path = '' as $$
  select pg_catalog.jsonb_build_object(
    'rls', (select pg_catalog.jsonb_object_agg(c.relname, c.relrowsecurity)
      from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace
      where n.nspname='public' and c.relname in ('finn_companies','finn_documents',
        'finn_document_pages','finn_research_chunks','finn_research_cache',
        'finn_research_jobs','finn_model_calls')),
    'anon_bypasses_rls', (select rolbypassrls from pg_catalog.pg_roles where rolname='anon'),
    'anon_private_select', pg_catalog.has_table_privilege('anon','public.finn_research_jobs','SELECT'),
    'anon_cache_write', pg_catalog.has_table_privilege('anon','public.finn_research_cache','INSERT'),
    'anon_cache_read', pg_catalog.has_table_privilege('anon','public.finn_research_cache','SELECT')
  );
$$;
revoke all on function public.finn_research_security_status() from public, anon, authenticated;
grant execute on function public.finn_research_security_status() to service_role;
commit;
notify pgrst, 'reload schema';
