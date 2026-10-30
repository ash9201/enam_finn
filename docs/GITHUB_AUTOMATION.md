# GitHub Actions recovery and scheduler switch

On **31 October 2026 (IST)**, after the user resolved the account restriction, both
workflows were dispatched on `main` and completed successfully using only standard
`ubuntu-latest` runners:

- [Foundation checks](https://github.com/ash9201/enam_finn/actions/runs/41141473616):
  87 tests, frontend production build and emitted-secret scan passed.
- [Portfolio source sync](https://github.com/ash9201/enam_finn/actions/runs/41141475816):
  both sources completed, 15/15 prices, no failed symbols, actual 30 October sessions.
  Supabase records identify `github_actions` as the execution origin.

These were real `workflow_dispatch` runs, not claims that a timed schedule already fired.
The credential-free operational report is `artifacts/release/github-actions-recovery.json`.

**Switch complete:** the owner deactivated both fallback schedules. Server-side checks
confirmed both `active=false` and no in-flight fallback work. Only then was repository
variable `FINN_ENABLE_SCHEDULED_SYNC` set to `true` and read back successfully. Both
GitHub workflows are active; the schedules below now belong to GitHub Actions.

## Complete the switch without overlapping schedules

1. Run `supabase/checks/disable_fallback_schedules.sql` as project owner in SQL Editor.
   It sets `active=false` for only `finn-filings`, `finn-eod-prices` and any temporary
   `finn-source-check`. It preserves jobs, Vault settings, tables and unrelated schedules.
2. Verify both regular fallback schedules are inactive through the server-only
   `finn_source_schedule_status` function. Wait for any already-running fallback work
   to finish; disabling a schedule does not cancel an HTTP request already dispatched.
3. Set GitHub repository variable `FINN_ENABLE_SCHEDULED_SYNC=true`. Keep the required
   secrets `SUPABASE_URL` and `SUPABASE_SECRET_KEY`. No Gemini secret is needed.
4. Verify the variable and active workflow state. The cadence is minutes 17/47 for
   filings and **18:15 IST weekdays** for EOD. Show actual completion times; GitHub
   scheduled starts can be delayed.

SQL Editor is required for step 1 because the available application credentials do
not grant SQL/Cron administration. Keep the source variable false until step 2 is
confirmed. This ordering keeps two automatic ingestion engines from operating together.

## Fallback recovery

Keep the [Supabase Cron instructions](SUPABASE_CRON.md) for recovery. Before reactivating
them, set the GitHub source variable to false. Re-running the private Vault configuration
script enables fallback schedules, so do not run it while GitHub scheduling is active.

The original billing failures remain in build/acceptance history; they no longer
describe current CI execution. This switch does not change runner types, paid budgets,
research quotas, source-date validation or access policies.

Reference: [pg_cron job deactivation](https://github.com/citusdata/pg_cron#altering-a-cron-job).
