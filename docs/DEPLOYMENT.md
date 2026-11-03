# Deployment and local development

The deployed frontend is [finn-web](https://finn-web-yb14.onrender.com); the active
Singapore API is [finn-api-source-test](https://finn-api-source-test.onrender.com).
Both follow `main` in [ash9201/enam_finn](https://github.com/ash9201/enam_finn).
The API's historical service name does not mean it is a separate test environment.
The setup uses a Render Static Site, Free Python API, Supabase Free and Gemini free quota.

## Local development

Use Python **3.12** and Node **24**. From the repository root, create `.env.local`
from [`.env.example`](../.env.example) only if it does not already exist; fill in keys
locally. Never overwrite a configured file or commit real credentials.

On Windows x64, the optional bootstrap installs workspace-local tools and verifies
Node's official SHA-256 without changing system PATH or execution policy:

```powershell
py -3.12 scripts/bootstrap.py
.venv\Scripts\python.exe -m uvicorn finn.main:app --host 127.0.0.1 --port 8000
# Second terminal, repository root:
.venv\Scripts\python.exe scripts/npm.py run dev
```

With existing toolchains on Linux/macOS:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install -e '.[dev]'
npm --prefix frontend ci --no-fund --no-audit
.venv/bin/python -m uvicorn finn.main:app --host 127.0.0.1 --port 8000
# Second terminal:
npm --prefix frontend run dev
```

Open `http://localhost:5173`; the API listens on port 8000. Briefing is `/`, Research
`/?view=research`, Portfolio `/?view=portfolio` and secondary System Status `/?view=status`.
The old `/?view=foundation` URL is a compatibility alias with a return path.

## Supabase provisioning and initial data

For a **new project**, run [migrations](../supabase/migrations) `0001` through `0011`
in numeric order, using the current complete files in SQL Editor. Keep RLS enabled.
Application API keys cannot perform SQL schema administration. Existing projects do
not need reseeding or repeated migration setup.

Keep `finn-documents` private. Documents/pages/chunks, vectors, usage, jobs and
unpublished database answers have server-only access. Anonymous reads expose intended
status, watchlist, filings, prices and explicitly published outputs. Do not add public
write policies to fix a frontend connection error.

These commands acquire real data and can consume model quota; they are not unit tests:

```powershell
.venv\Scripts\python -m finn.ingest --portfolio
.venv\Scripts\python -m finn.ingest --symbol INFY --publish
.venv\Scripts\python -m finn.briefing --mode all
```

Verify one company's sources and answer before scaling prepared examples. Publishing
is explicit; unfamiliar tickers use the same generic pipeline. Embedding provisioning,
coverage and rollback are in [hybrid retrieval](HYBRID_RETRIEVAL.md).

## Environment variables

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Project URL; `NEXT_PUBLIC_SUPABASE_URL` is also accepted |
| `SUPABASE_SECRET_KEY` | Server-only secret; legacy `SUPABASE_SERVICE_ROLE_KEY` also accepted |
| `SUPABASE_PUBLISHABLE_KEY` | Intended public key; `SUPABASE_ANON_KEY` / `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` aliases accepted |
| `SUPABASE_STORAGE_BUCKET` | Private PDF bucket, default `finn-documents` |
| `GEMINI_API_KEY` | Server-only generation and embedding credential |
| `GEMINI_LITE_MODEL` | `gemini-3.5-flash-lite`: ordinary generation, current comparisons and financial text/image extraction |
| `GEMINI_REASONING_MODEL` | Retained `gemini-3.8-flash` configuration; not the current comparison runtime |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` |
| `FINN_ENABLE_SEMANTIC_SEARCH` | Active API: `true`; new unprepared database / keyword rollback: `false` |
| `FINN_ALLOWED_ORIGINS` | Exact frontend origins, comma-separated; local default `http://localhost:5173` |
| `VITE_API_BASE_URL` | Public API URL, without trailing slash |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` | Public frontend settings; local Vite can derive them from root Supabase settings |
| `FINN_DEPLOYED_API_URL`, `FINN_DEPLOYED_WEB_URL` | Optional verification targets |

Only public values belong behind `VITE_` or `NEXT_PUBLIC_` prefixes. A Supabase secret
must never use those prefixes. Backend deployed environment values take precedence
over root `.env.local`. Vite variables are compiled at build time; changing them requires
a frontend rebuild.

## Render services

[render.yaml](../render.yaml) supplies Blueprint configuration; `sync: false` values
must be supplied through Render settings. For manual setup:

| Setting | Python Web Service | Static Site |
| --- | --- | --- |
| Region / plan | Singapore / Free | Static hosting |
| Branch | `main` | `main` |
| Root directory | Repository root | `frontend` |
| Build | `pip install -r requirements.lock && pip install --no-deps -e .` | `npm ci --no-fund --no-audit && npm run build` |
| Start / publish | `uvicorn finn.main:app --host 0.0.0.0 --port $PORT` | `dist` |
| Runtime version | `PYTHON_VERSION=3.12.10` | `NODE_VERSION=24.22.2` |
| Health check | `/health/live` | — |

Set `FINN_ENV=production`, backend Supabase/Gemini variables and exact
`FINN_ALLOWED_ORIGINS` on the API. Set only the three `VITE_` variables on the static
site. Use the assigned real URLs, not example hostnames. Add static rewrite `/*` to
`/index.html`, plus `X-Content-Type-Options: nosniff` and
`Referrer-Policy: strict-origin-when-cross-origin` headers.

`/health/live` exposes process availability/revision; `/health/ready` reports configuration,
not successful live dependency tests. Verify actual browser CORS and public-cache reads.
The Free API sleeps after idle time and may need about a minute to wake. Static saved
content remains separate. Do not use artificial keep-alive traffic to disguise this.
For browser-only failures, inspect content blockers and CORS rather than exposing keys.
Supabase inactivity/capacity, free allowances and upstream restrictions can also affect service.

## Source updates and indexing

| Workflow | Configured schedule | Required Actions settings |
| --- | --- | --- |
| [Portfolio source sync](../.github/workflows/portfolio-sync.yml): filings | UTC minutes 17/47, every 30 minutes | Secrets `SUPABASE_URL`, `SUPABASE_SECRET_KEY`; variable `FINN_ENABLE_SCHEDULED_SYNC=true` |
| Same workflow: EOD prices | 12:45 UTC / 18:15 IST weekdays | Same; no Gemini key needed |
| [Resume document indexing](../.github/workflows/embedding-maintenance.yml) | 08:45 UTC / 14:15 IST daily | Same Supabase secrets plus `GEMINI_API_KEY`; variable `FINN_ENABLE_SEMANTIC_BACKFILL=true` |

Standard `ubuntu-latest` runners are used. Manual source dispatch accepts `all`,
`filings` or `prices`. The source job also checks whether the official directory is
due for its bounded daily refresh; failure preserves last-known-good identities.
Filing sync enriches up to six pending official sources without LLM calls. Indexing
resumes collected corpora under the existing budgets, not an NSE-wide crawl.

Schedules are intended cadence, not guaranteed delivery. GitHub can delay or skip starts;
actual stored completion times determine freshness. EOD bars require completed sessions,
21 valid bars for the current/prior-20 baseline, and no backward saved-session update.
NSE daily-file recovery applies to an incomplete latest returned Yahoo bar, not a
complete replacement for absent history. Split-affected comparisons stay suppressed.

Briefing/Portfolio reread saved data on activation and every 60 seconds while visible.
Reload saved updates does not fetch NSE/Yahoo. Research documents refresh on demand;
quarterly answer reuse has a 24-hour window, not a scheduled daily results acquisition.
The labelled bundled snapshot is outage recovery and retains original dates.

### Optional scheduler recovery

Supabase fallback source schedules are installed but **inactive**. GitHub is the active
scheduler. Never enable both automatic engines together.

If GitHub source scheduling becomes unavailable, first set
`FINN_ENABLE_SCHEDULED_SYNC=false` and wait for existing runs to finish. Migration
`0005` provides the private lease/pg_cron/pg_net/Vault functions. Locally run
`scripts/prepare_cron_config.py`, then apply the generated
`artifacts/private/configure-supabase-cron.sql` in SQL Editor. It contains a privileged
credential: keep it local and never commit or share it. This activates the fallback
and a self-removing acceptance invocation.

Cron dispatches `/internal/source-sync`; HTTP acceptance alone does not prove fetch
completion. Inspect persisted source results and actual session dates. The singleton
lease rejects duplicates and contention; interrupted work can wait for lease expiry.
`scripts/verify_cron.py` includes access-denial write probes and is **not** a read-only
check. `supabase/checks/recheck_source_sync.sql` requests a real one-time refresh.

To return to GitHub, apply `supabase/checks/disable_fallback_schedules.sql`, confirm
`finn-filings` and `finn-eod-prices` inactive through the server-only
`finn_source_schedule_status` function, wait for dispatched work, then re-enable the
GitHub variable. Key rotation also requires updating Vault configuration. This recovery
path shares the existing privileged server key; a dedicated sync token is future hardening.

## Verification

[Testing and reliability](EVALUATION.md) distinguishes offline tests, recorded-source
browser checks, read-only deployment checks and quota-consuming integration scripts.
Use `scripts/verify_submission.py --live-only --timeout 75` for bounded read-only checks.
Compare `/health/live` revision and actual frontend assets with the intended source;
a successful push alone does not establish deployment parity.
