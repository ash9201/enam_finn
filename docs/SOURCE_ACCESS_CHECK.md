# Bounded source-access check: Singapore

The current Virginia API can use Supabase and Gemini, including a new uncached answer,
but cannot connect to Screener for unfamiliar-company discovery. The identical TCS
index adapter finds annual reports and transcripts locally. IPv4 did not fix the
deployed failure. A second region is a diagnostic, not a promised solution.

Render cannot change an existing service's region:
[Render regions](https://render.com/docs/regions). Keep the existing frontend/API in
place while testing; Supabase data stays in the existing project.

## Create one temporary Free API

In Render, create a **Web Service** from `ash9201/enam_finn`, branch `main`:

| Setting | Value |
| --- | --- |
| Name | `finn-api-source-test` |
| Region | **Singapore** |
| Runtime | Python |
| Instance | **Free** |
| Root directory | Blank (repository root) |
| Build | `pip install -r requirements.lock && pip install --no-deps -e .` |
| Start | `uvicorn finn.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health/live` |

Copy the **backend** environment variables from the existing Virginia API. The exact
list is in [DEPLOYMENT.md](DEPLOYMENT.md#2-create-the-python-api), including Python
version, server Supabase/Gemini keys, model names and existing frontend CORS origin.
Do not copy secrets into the static frontend or chat. No new database, disk, worker,
cron resource or paid instance is needed.

After Render assigns a URL, add it to the existing local `.env.local`:

```dotenv
FINN_TEST_API_URL=<actual assigned Singapore API URL>
```

Leave `FINN_DEPLOYED_API_URL` and frontend `VITE_API_BASE_URL` pointing at Virginia for
now. We will run the protected fixed-host probes and a genuinely unprepared TCS request
against the test API. TCS has not been pre-ingested locally to disguise the failed
deployed test.

If source discovery and PDF ingestion succeed, verify model answering and citations,
then switch the frontend to the verified API. If the same refusal persists, stop the
regional experiment and retain the existing deployment while investigating another
primary-source discovery route. Do not create more regional copies speculatively.

## GitHub automation is a separate issue

The user reported GitHub's failed-payment/spending-limit banner. Increasing a paid
budget to $1 is not a zero-charge guarantee. FINN's repository variable
`FINN_ENABLE_SCHEDULED_SYNC` has temporarily been set to `false`; no new hosted workflow
will be dispatched by the agent until the free allowance/account restriction is clear.
The automatic `foundation.yml` workflow is also temporarily disabled, so documentation
pushes cannot start a potentially billable private runner. Re-enable it together with
scheduled updates once the free gate is verified. Local tests/build remain available.
Restore paid Actions budgets to $0 with **Stop usage when budget limit is reached**.

Check included compute usage separately from billable-usage filters and inspect any
failed-payment/account restriction. Standard hosted runners in public repositories
are free, while private repositories draw from an included allowance before billable
usage: [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
The private repository has not been made public.
