# FINN

An investor attention inbox with primary-source research. This checkout currently
implements **Milestone 0 only**: live dependency probes and a deployment foundation.
There is no simulated investor feed, research answer fallback, or prepared portfolio.

The approved [plan](docs/PLAN.md) includes the hybrid-search and financial-table
amendments. Later milestones remain gated until external dependencies are verified.

## Local setup (Windows)

```powershell
python scripts/bootstrap.py
Copy-Item .env.example .env.local  # only if the local file does not already exist
```

The bootstrap installs dependencies into `.venv` and a checksum-verified portable
Node 24 runtime into `.tools`; it does not alter system PATH or install Node globally.
Both directories and `.env.local` are ignored. Python 3.12 is required.

Fill `.env.local` with your actual values, never in chat or tracked files:

- `GEMINI_API_KEY`
- `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_PUBLISHABLE_KEY`
- The user's `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
  names are also accepted. **No secret may use `NEXT_PUBLIC_` or `VITE_`.**

Apply [the foundation migration](supabase/migrations/0001_dependency_foundation.sql)
in the Supabase SQL Editor. It enables pgvector and creates only isolated dependency
tables, a public read-only status row, and a private `finn-documents` PDF bucket.
No source corpus or investor-workflow tables are deployed by this migration.

Run in two terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn finn.main:app --host 127.0.0.1 --port 8000
```

```powershell
python scripts/npm.py run dev
```

Open `http://localhost:5173`. The foundation page can check the API and read the public
Supabase status using the publishable key. It does not pretend these checks verify all
external dependencies. Vite loads root `.env.local` and explicitly exposes only the
public Supabase URL/key and API base URL; the build rejects public-prefixed secrets.

## Acceptance checks

```powershell
.\.venv\Scripts\python.exe -m pytest
python scripts/npm.py run build
.\.venv\Scripts\python.exe scripts/check_frontend_secrets.py
.\.venv\Scripts\python.exe -m finn.feasibility --symbol INFY --check-embeddings
```

For repeatable browser checks with the two local servers running:

```powershell
python scripts/npm.py exec -- playwright install chromium
python scripts/npm.py run test:browser
```

This uses real API/public-cache connections. Phone and desktop screenshots/checks go
to the ignored `artifacts/milestone-0/browser` directory.

Live probes use the same generic ticker/document-discovery functions for any NSE
symbol. The initial acceptance company is INFY. A full run makes one request to each
configured generation model; `--check-embeddings` adds one optional embedding request.
Do not use the live suite as a repeated unit test or consume the scarce reasoning quota
unnecessarily. A successful request proves access, not the full daily quota.

The report is `artifacts/milestone-0/feasibility.md` (and JSON). Downloaded primary PDFs,
page text, hashes, original/final URLs, and sampled table candidates are saved alongside
it, all ignored by Git. Missing credentials are `blocked`; failed live requests are
`failed`. The command exits nonzero until all required checks pass. Partial `--only`
runs cannot pass the overall gate. Use a separate `--output` path for partial reruns
so the full live report is preserved.

Table extraction is a bounded financial-page sample, **not a verified financial data
set**. All cells remain unvalidated candidates. Document-index labels are preserved
separately from reporting/publication dates, which stay unknown until verified from
the source. Financial comparisons are disabled. No keyword/semantic investor retrieval
or full research pipeline is enabled in this milestone.

## Deploying the foundation

The user has created the GitHub repository and Render account. No deployed service or
URL is assumed to exist. Follow [the exact Render setup guide](docs/DEPLOYMENT.md).

1. Use the GitHub repository you created and push the source, excluding the supplied PDFs,
   `.env.local`, `.venv`, `.tools`, and `artifacts`. Keep this boundary when exporting
   the repository or build history.
2. Connect that repository to Render and create a Blueprint from `render.yaml`.
   The API has `plan: free`; the frontend uses static hosting. Do not add a paid disk,
   paid database, or paid worker.
3. Fill backend secrets with the canonical server-only names listed in the Blueprint.
   After Render assigns the real API URL, use it as the frontend's `VITE_API_BASE_URL`.
   Frontend Supabase variables are `VITE_SUPABASE_URL` and
   `VITE_SUPABASE_PUBLISHABLE_KEY` only. Never copy the whole `.env.local` into frontend
   settings. Rebuild the frontend after changing its public build variables.
4. Set backend `FINN_ALLOWED_ORIGINS` to the actual frontend origin, with no path or
   wildcard. The API runs with `FINN_ENV=production` and does not allow arbitrary origins.
5. Put the assigned URLs into `FINN_DEPLOYED_API_URL` and `FINN_DEPLOYED_WEB_URL` locally
   and rerun the full feasibility suite when ready. Test a cold start after 15 minutes
   idle and the frontend's public-cache button in a browser.

`/health/live` is process liveness; `/health/ready` reports configuration presence and
explicitly does **not** claim external dependencies have been verified. There is no
public endpoint that runs expensive model calls, reads secrets, or accepts PDF URLs.

The GitHub workflows provide offline foundation tests and a **manual** live feasibility
run. There is no scheduled ingestion yet. The latter needs repository secrets matching
`.env.example` and actual deployment URL variables. Retain no credentials in logs.

Keep a working local copy of downloaded evidence and a redacted feasibility report;
free API/server/storage availability is not guaranteed. Historical evidence must always
keep its original timestamps when reused.

## Handoff and build history

See [Milestone 0 findings](docs/MILESTONE_0.md) and [build log](docs/BUILD_HISTORY.md).
The build log is a summary, not a substitute for the assignment's required coding-agent
conversation exports/share links. Export those separately and redact credentials before
submission. The covering note and investor demo are later milestones.
