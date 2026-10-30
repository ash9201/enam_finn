# Supabase Cron fallback

GitHub's public standard-runner jobs remain blocked by an account billing lock.
The user approved this fallback on 30 October 2026. It uses the existing Supabase
database and Render API; no paid scheduler or extra backend is created.

## Configure once

1. Run `supabase/migrations/0005_source_sync_cron.sql` in Supabase SQL Editor as
   project owner. Keep RLS enabled. This installs pg_cron/pg_net/Vault, a private
   singleton job/lease, and server-only functions. It does not enable schedules.
2. Run `.venv\Scripts\python scripts/prepare_cron_config.py` locally. Open the generated
   `artifacts/private/configure-supabase-cron.sql` and run it in the same SQL Editor.
   This file contains the existing server credential: keep it local, never commit,
   paste into chat, record on video, or share it with the submission. Rerunning it
   updates the named Vault entries/schedules rather than creating duplicates.
3. Keep GitHub repository variable `FINN_ENABLE_SCHEDULED_SYNC=false`. Both schedulers
   must not operate together. No new Render environment variable is required; the
   endpoint authenticates the existing server secret. It never accepts the public key.
4. The configuration schedules one acceptance run for the next minute. This temporary
   schedule removes itself after dispatch. Allow the API to wake and finish fetching;
   then run `.venv\Scripts\python scripts/verify_cron.py`.

The verifier requires actual Cron dispatch, HTTP acceptance, completed source results,
expected active schedules, and denied anonymous/private access. Merely applying SQL,
seeing a successful Cron SQL run, or receiving HTTP 202 is insufficient.

## Runtime behaviour

- Announcements: minutes 17 and 47 of each UTC hour (30-minute interval).
- EOD prices: 12:45 UTC / **18:15 IST**, Monday–Friday. Holidays preserve the actual
  last completed session date; they do not create imaginary bars.
- Cron invokes a private function which reads URL/key from Vault and uses pg_net to
  POST `/internal/source-sync`. Its 120-second HTTP timeout allows a Render cold start.
  The endpoint responds after queuing; fetch completion is persisted separately.
- One database lease covers all API instances. Duplicate calls return 409. Requests
  while research is active return 409 and wait for the next scheduled invocation;
  this protects the serial worker/free memory. There is no implicit immediate retry.
- Announcement ticks also check whether the latest due weekday EOD refresh is missing
  or incomplete. They retry due prices alongside filings, so a busy daily invocation
  does not leave prices waiting for the next weekday's daily job. This checks refresh
  deadlines, not an exchange holiday calendar; original trading dates stay visible.
- An explicit Yahoo rate-limit exception gets one retry after five seconds. A second
  failure remains a visible failed refresh; there is no fabricated replacement.
- Missing closing price/volume in the latest completed Yahoo row cannot silently drop
  the displayed session backwards. FINN checks NSE's official dated UDiFF archive for
  the same date, EQ symbol and ISIN. Latest close/volume then carry the NSE source link
  and archive hash; previous-20-session history remains explicitly attributed to Yahoo.
  Invalid baseline bars, unavailable archives, identifier/date mismatches or backwards
  session updates fail visibly and preserve the previous dated saved value.
- A restart can interrupt in-process work. An interrupted lease expires after 45 minutes,
  so a tick may be skipped before retry. Failed/incomplete scans retain dated earlier
  data with their failure state; they never appear as an empty successful scan.
- The existing research executor also runs refreshes. No model calls are required.
  Each source is attempted independently, and each completed result records its origin.
- Standard public-runner GitHub workflows remain available for eventual recovery,
  but the source-schedule variable stays off while this fallback is active.

The prototype reuses its existing server key in Vault to avoid another Render secret
configuration step. This remains a privileged, server-only credential; a dedicated
rotatable sync token is a useful subsequent hardening step. After key rotation, regenerate
and rerun the private configuration SQL and update the API secret together.

## Inspect or stop

`scripts/verify_cron.py` saves a credential-free report under `artifacts/release/`.
The Supabase Cron dashboard shows dispatch runs; source status in FINN shows fetch
results. pg_net responses expire after approximately six hours, so a later check may
need a new scheduled invocation to obtain HTTP evidence. Recent response metadata is
project-wide; it must be assessed alongside the FINN job and source results.
For a fresh full-source acceptance run, execute `supabase/checks/recheck_source_sync.sql`
in SQL Editor. It uses the existing Vault entries and removes its own temporary schedule.
The first real check on 31 October IST refreshed filings and 14/15 prices, with one
honestly reported Yahoo rate limit. A separate operator retry refreshed 15/15; this
operator recovery is not relabelled as a successful automatic full-source run.

The subsequent real Cron recheck passed at **03:23 IST on 31 October 2026**: both
sources completed, 15/15 prices refreshed, source freshness passed, private access was
denied, and the temporary check removed itself. The two intended schedules remain
active. Earlier partial results remain in the acceptance/build history.
That early check was subsequently strengthened to validate actual trading sessions.
After a Yahoo null-close issue was caught, the regular **03:47 IST** tick exercised
the NSE adapter on Singapore and recovered all 15 true 30 October sessions with source
links. The final verifier includes session integrity, not just recent fetch timestamps.

To stop only FINN schedules, run in SQL Editor:

```sql
select cron.unschedule(jobid) from cron.job
where jobname in ('finn-filings','finn-eod-prices','finn-source-check');
```

Paused Supabase projects and unavailable Render services cannot execute successful
updates. The UI's actual timestamps remain the source of freshness, regardless of schedule.

References: [Supabase Cron](https://supabase.com/docs/guides/cron),
[Vault-backed scheduled HTTP calls](https://supabase.com/docs/guides/functions/schedule-functions),
[pg_net](https://supabase.com/docs/guides/database/extensions/pg_net).
