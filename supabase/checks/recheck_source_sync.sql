-- Run in SQL Editor as project owner. No secrets or configuration changes.
-- One real full-source Cron check at the next minute; self-removes after dispatch.
select cron.schedule('finn-source-check', '* * * * *',
  $$select finn_internal.trigger_source_sync('all');
    select cron.unschedule('finn-source-check');$$);
