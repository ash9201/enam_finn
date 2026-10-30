-- GitHub CI and full source sync passed. Run as project owner in SQL Editor.
-- Disable only FINN's fallback/temporary schedules; preserve jobs for easy rollback.
begin;
select cron.alter_job(jobid, active := false)
from cron.job
where jobname in ('finn-filings', 'finn-eod-prices', 'finn-source-check')
  and active;

select jobid, jobname, schedule, active
from cron.job
where jobname in ('finn-filings', 'finn-eod-prices', 'finn-source-check')
order by jobname;
commit;
