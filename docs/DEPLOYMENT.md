# Milestone 0: Render setup

The user has deployed both services, and dependency, browser/CORS and public-cache
checks pass. This guide records how the services are configured. The existing URLs
remain in local configuration; no hostname is invented. See [acceptance](ACCEPTANCE.md).

## 1. Push the source

Verify `git status` and `git check-ignore .env.local` before committing and pushing.
The `.gitignore` excludes credentials, the supplied assessment PDFs, installed tools,
dependency folders, downloaded PDFs, and feasibility artifacts. Never force-add them.

## 2. Create the Python API

Choose Render **New → Web Service**, connect the FINN repository, and set:

| Setting | Value |
| --- | --- |
| Name | `finn-api` (the assigned hostname may differ) |
| Runtime | Python |
| Branch | Your pushed working branch |
| Root directory | Leave blank: repository root |
| Build command | `pip install -r requirements.lock && pip install --no-deps -e .` |
| Start command | `uvicorn finn.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health/live` |
| Instance | **Free** |

Backend environment variables:

| Variable | Value |
| --- | --- |
| `PYTHON_VERSION` | `3.12.10` |
| `FINN_ENV` | `production` |
| `GEMINI_API_KEY` | Existing key from `.env.local` |
| `GEMINI_LITE_MODEL` | `gemini-3.5-flash-lite` |
| `GEMINI_REASONING_MODEL` | `gemini-3.8-flash` |
| `FINN_ENABLE_SEMANTIC_SEARCH` | `false` |
| `SUPABASE_URL` | Project URL, locally named `NEXT_PUBLIC_SUPABASE_URL` |
| `SUPABASE_SECRET_KEY` | Server-only secret; never prefix it `VITE_` or `NEXT_PUBLIC_` |
| `SUPABASE_PUBLISHABLE_KEY` | Publishable key |
| `SUPABASE_STORAGE_BUCKET` | `finn-documents` |
| `FINN_ALLOWED_ORIGINS` | Set to the real frontend origin in step 4 |

Deploy and copy the actual API URL shown by Render. Open `/health/live`; expect
`service: finn-api` and `status: ok`. Readiness deliberately says `configuration_only`.
Before step 4, browser requests from the production frontend will not be allowed.

## 3. Create the frontend

Choose Render **New → Static Site**, connect the same repository, and set:

| Setting | Value |
| --- | --- |
| Name | `finn-web` |
| Branch | Same source branch |
| Root directory | `frontend` |
| Build command | `npm ci --no-fund --no-audit && npm run build` |
| Publish directory | `dist` |

Set only these frontend build variables:

| Variable | Value |
| --- | --- |
| `NODE_VERSION` | `24.22.2` |
| `VITE_API_BASE_URL` | Actual API URL from step 2, without a trailing slash |
| `VITE_SUPABASE_URL` | Public Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Publishable key, **not** the secret |

Do not add Gemini or Supabase secrets to the frontend service. Changing a `VITE_` value
requires a new frontend build. Add a **Rewrite** from `/*` to `/index.html` and the
headers `X-Content-Type-Options: nosniff` and
`Referrer-Policy: strict-origin-when-cross-origin`.

Deploy and copy the assigned frontend URL. The static page should load independently
of whether the Python service is awake.

## 4. Connect and verify

Set the API's `FINN_ALLOWED_ORIGINS` to the actual frontend **origin**: HTTPS scheme
and hostname only, no trailing slash/path/wildcard. Save/redeploy the API. On the
frontend verify both **Check API connection** and **Check public cache**.

The Supabase migration and its access boundaries have already been tested. Keep the
PDF bucket private and do not add anonymous write policies to fix a frontend problem.
The connection view reads `finn_public_status`; the working app also reads portfolio
metadata and explicitly published research through read-only policies.

`render.yaml` supplies equivalent Blueprint configuration. Its `sync: false` values
must be filled by you; actual API URLs and frontend origins still need to be set
after service creation. Do not add a paid database, disk, cron service, or worker.

## 5. Close the deployment gate

Put the actual assigned URLs in `.env.local`:

```dotenv
FINN_DEPLOYED_API_URL=<actual API URL>
FINN_DEPLOYED_WEB_URL=<actual frontend URL>
```

Then run:

```powershell
.\.venv\Scripts\python.exe -m finn.feasibility --symbol INFY
```

After at least 15 minutes without API traffic, reopen the frontend and check the API.
Record wake-up time; the static page/public cache should remain usable. Do not add
artificial keep-alive traffic to disguise cold starts.

Those Milestone 0 checks have passed. Push/Pull implementation is now present; verify
the current release with the product browser checks and [acceptance notes](ACCEPTANCE.md).

## Current source automation

The production frontend now points to the verified Singapore API at
`https://finn-api-source-test.onrender.com`. Virginia remains available for rollback.
GitHub's account restriction has been resolved. Hosted CI and a full source workflow
passed on standard Ubuntu runners; [GitHub scheduling](GITHUB_AUTOMATION.md) is enabled.
Both [Supabase fallback schedules](SUPABASE_CRON.md) are verified inactive. Retain their
configuration for recovery, but do not reactivate them alongside GitHub scheduling.

## Pre-submission sanity check

From the repository root, with the existing virtual environment/dependencies:

```powershell
# Local regression tests + frontend build/scan, then configured live checks:
.\.venv\Scripts\python.exe scripts/verify_submission.py

# Separate local checks from read-only live checks:
.\.venv\Scripts\python.exe scripts/verify_submission.py --local-only
.\.venv\Scripts\python.exe scripts/verify_submission.py --live-only

# Explicit production API; allow a bounded cold-start wait if needed:
.\.venv\Scripts\python.exe scripts/verify_submission.py --live-only --api-url https://finn-api-source-test.onrender.com --timeout 75

# Omit privileged database/operator checks even when local credentials exist:
.\.venv\Scripts\python.exe scripts/verify_submission.py --live-only --public-only
```

API configuration is `--api-url`, otherwise `FINN_DEPLOYED_API_URL`, then
`VITE_API_BASE_URL`. Existing `.env.local` server/publishable credentials enable the
private checks; never supply keys in command-line arguments or logs.
`FINN_DEPLOYED_WEB_URL` enables the deployed asset scan. `--symbols INFY CCL TMCV`
selects canonical companies (these are the defaults). Request deadlines default to
20 seconds, configurable from 1 to 120; no indefinite retries are performed.

The report prints **PASS / FAIL / SKIP**, followed by totals. Any failed check returns
exit code 1. Missing credentials, absent saved cases and intentionally untested model
calls are explicit SKIPs; a zero exit code does not turn skipped checks into proof.
Unknown/unavailable coverage is never replaced with invented answers.

The default is read-only against deployed services. Local tests/builds create only
ordinary local artifacts. Live API calls are GETs: health, companies, prepared answers,
search coverage, and evidence. Prepared answers are read twice to check stable IDs,
timestamps and source references. **No `POST /research` is used**, since even its
cached fast path writes a job row and may schedule indexing.

Private checks reuse the existing directory, cache, citation and retrieval functions:
canonical symbol/ISIN provenance without contacting NSE; RLS and anonymous read denial;
saved quarterly/numerical metadata; read-only fast-cache repeats; actual index counts;
and keyword fallback against the production corpus. The Supabase client blocks writes
and all unaudited RPCs. Only existing SELECT-only functions are allowed (PostgREST
uses POST for read-only RPCs). No budget reservation, embeddings, background work,
fresh discovery, source refresh or model generation is permitted.

Hybrid **eligibility** is based on actual ready/total counts, not the flag alone.
Complete-index quota failure is deliberately injected in local retrieval code using
the production corpus; the checker does not execute paid/live semantic queries.
The budget check reads the application ledger, not Gemini's current provider quota.
Source verification is against stored source text; external PDF availability and
uncached generation are deliberately outside this lightweight check.

The existing secret scanner is reused for both local and deployed JS/CSS assets.
Local regressions cover evidence, company directory, general Research, quarterly
figures, numerical metrics and hybrid fallback; existing company-search tests cover
name/alias/ambiguity selection. The checker installs no dependencies or migrations.

Observed on 2 November: the combined command passed **22 checks**, failed none, and
skipped two: TMCV has no current public prepared answer (private numerical caches
remain available), and live Gemini generation/semantic ranking is deliberately not
called. Local regressions passed **184 tests**; the frontend build and scans passed.
At that check CCL was 707/707 indexed, INFY 877/1160 and TMCV 811/1208. These are
dated observations; rerun for current coverage, including any further automatic indexing.
