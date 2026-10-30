# Bounded source-access check: Singapore

**Update:** the Singapore test succeeded for unprepared TCS and HINDUNILVR, including
live documents and cited answers. The frontend now uses Singapore and passed deployed
browser checks. Supabase Cron subsequently passed a full scheduled filing/15-price
refresh. The GitHub account restriction was later resolved: CI/source runs pass,
GitHub scheduling is enabled and both Supabase fallback schedules are inactive. The
setup recipe below is historical and records the single regional test already
performed; do not create another copy or switch back to Virginia.

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

The user made the repository public and restored paid Actions budgets to $0 with
**Stop usage when budget limit is reached**. CI is re-enabled. Both workflows were
retried on standard `ubuntu-latest` runners; GitHub still reports an account billing
lock before runner assignment. Public visibility did not clear that account lock.

`FINN_ENABLE_SCHEDULED_SYNC` remains `false` until a real automated source run succeeds.
Local tests/build and manual source updates work; the latest manual run is explicitly
labelled in public sync metadata and the app. A Supabase Cron fallback in the existing
project has been proposed while the user resolves GitHub's restriction. Standard
public runners are free: [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
The support draft is local at `artifacts/support/github-actions-account-lock.md` and
has not been sent.
