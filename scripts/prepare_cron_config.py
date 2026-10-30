"""Create local-only SQL for Vault configuration. Never print credentials."""

import os
import re

from finn.config import ROOT, load_local_env, supabase_configuration

load_local_env()
api = os.environ.get("FINN_DEPLOYED_API_URL", "").rstrip("/")
_, secret, _ = supabase_configuration()
if not secret or not re.fullmatch(r"https://[a-z0-9-]+\.onrender\.com", api):
    raise SystemExit("Configure the deployed Render API URL and server Supabase key first.")


def literal(value):
    return "'" + value.replace("'", "''") + "'"


statements = []
for name, value in [("finn_sync_api_url", api), ("finn_sync_api_key", secret)]:
    statements.append(f"""do $config$
declare existing uuid;
begin
  select id into existing from vault.secrets where name={literal(name)};
  if existing is null then
    perform vault.create_secret({literal(value)}, {literal(name)});
  else
    perform vault.update_secret(existing, {literal(value)}, {literal(name)});
  end if;
end $config$;""")

statements.append("""
-- UTC schedules: filings twice per hour; EOD at 18:15 IST on weekdays.
select cron.schedule('finn-filings', '17,47 * * * *',
  $$select finn_internal.trigger_source_sync('filings');$$);
select cron.schedule('finn-eod-prices', '45 12 * * 1-5',
  $$select finn_internal.trigger_source_sync('prices');$$);
-- One real scheduler acceptance run at the next minute; removes its own schedule.
select cron.schedule('finn-source-check', '* * * * *',
  $$select finn_internal.trigger_source_sync('all');
    select cron.unschedule('finn-source-check');$$);
""")
destination = ROOT / "artifacts" / "private" / "configure-supabase-cron.sql"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(
    "-- PRIVATE: contains a server credential. Do not commit or share.\nbegin;\n"
    + "\n".join(statements)
    + "\ncommit;\n",
    encoding="utf-8",
)
print(f"Private SQL prepared at {destination.relative_to(ROOT)}. Contents were not printed.")
