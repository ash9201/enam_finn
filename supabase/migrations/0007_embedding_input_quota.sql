-- Live Gemini quota counts individual texts in a batch, not batch envelopes.
-- Count-token HTTP calls are also reserved conservatively as one unit each.
-- Backfill uses 800/day; foreground queries may use the remaining headroom up to 900.
begin;
create or replace function public.finn_reserve_embedding_request(
  p_model text, p_operation text, p_input_count integer, p_tokens integer,
  p_rpm integer default 80, p_rpd integer default 800, p_tpm integer default 27000
) returns jsonb language plpgsql security invoker set search_path='' as $$
declare minute_calls bigint; day_calls bigint; tokens integer; oldest timestamptz; day_start timestamptz;
begin
  if p_input_count < 1 or p_tokens < 0 or p_operation not in ('count','embed') then
    raise exception 'Invalid embedding reservation';
  end if;
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext('finn-embedding-' || p_model));
  day_start := ((now() at time zone 'America/Los_Angeles')::date::timestamp at time zone 'America/Los_Angeles');
  select coalesce(sum(case when operation='embed' then input_count else 1 end) filter(where reserved_at > now()-interval '1 minute'),0),
    coalesce(sum(case when operation='embed' then input_count else 1 end) filter(where reserved_at >= day_start),0),
    coalesce(sum(input_tokens) filter(where reserved_at > now()-interval '1 minute'),0),
    min(reserved_at) filter(where reserved_at > now()-interval '1 minute')
  into minute_calls,day_calls,tokens,oldest
  from public.finn_embedding_requests where model=p_model and reserved_at >= least(day_start,now()-interval '1 minute');
  if day_calls + (case when p_operation='embed' then p_input_count else 1 end) > least(greatest(p_rpd,1),900) then
    return jsonb_build_object('allowed',false,'reason','daily_budget','retry_after',86400);
  end if;
  if p_tokens > least(greatest(p_tpm,1),27000) then
    return jsonb_build_object('allowed',false,'reason','batch_too_large','retry_after',0);
  end if;
  if minute_calls + (case when p_operation='embed' then p_input_count else 1 end) > least(greatest(p_rpm,1),80) or tokens+p_tokens > least(greatest(p_tpm,1),27000) then
    return jsonb_build_object('allowed',false,'reason','minute_budget',
      'retry_after',greatest(1,ceil(extract(epoch from oldest+interval '61 seconds'-now()))));
  end if;
  insert into public.finn_embedding_requests(model,operation,input_count,input_tokens)
    values(p_model,p_operation,p_input_count,p_tokens);
  return jsonb_build_object('allowed',true,'retry_after',0);
end $$;
revoke all on function public.finn_reserve_embedding_request(text,text,integer,integer,integer,integer,integer) from public,anon,authenticated;
grant execute on function public.finn_reserve_embedding_request(text,text,integer,integer,integer,integer,integer) to service_role;
commit;
notify pgrst,'reload schema';
