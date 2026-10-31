# FINN

A mobile-first investor attention inbox and primary-source company research prototype
for the ENAM AI Engineer challenge. The first working release includes **Push and Pull**
with real sources. The original [plan](docs/PLAN.md) records scope and trade-offs.

**Current deployment:** the frontend now uses Singapore and passes deployed phone/desktop
browser checks. Unprepared TCS and HINDUNILVR research completed live. GitHub's account
restriction is resolved: hosted CI and a full 15-company source sync passed on standard
Ubuntu runners. [GitHub Actions scheduling](docs/GITHUB_AUTOMATION.md) is enabled; both
Supabase fallback schedules are verified inactive. The retained
[Supabase Cron fallback](docs/SUPABASE_CRON.md) was also tested successfully and can be
reactivated if needed after turning GitHub scheduling off. Prices preserve actual
session dates, with bounded rate-limit retries and explicit primary-source recovery.
See [acceptance](docs/ACCEPTANCE.md).

## What works

- **Briefing:** real NSE portfolio filings, explainable priority, routine disclosures
  collapsed, 24-hour/seven-day/custom windows, and review state saved in the browser.
- **EOD alerts:** configurable daily-move and volume thresholds, with the volume baseline
  excluding the current session. Split-affected comparisons are suppressed.
  An incomplete latest Yahoo bar is recovered from the exact-date NSE daily file,
  with explicit provenance; older sessions never replace newer saved data.
- **Portfolio:** 15 verified NSE companies, real saved EOD closes, sector labels and
  explicit session/refresh dates. This is a mock watchlist, without trading or P&L.
- **Research:** any valid NSE ticker with accessible primary reports/transcripts uses
  the same generic pipeline. Prepared examples: INFY, POLYCAB and CCL, each with one
  annual report and two transcripts. Answers have page-level source quotes.
- **Narrative/evidence:** one prepared INFY comparison traces earlier guidance against
  later call evidence, without pretending one quarter settles a full-year target.
- **Resilience:** persistent jobs, content-hash document versions, answer caches, limited
  model calls, explicit errors, and a visibly dated recorded-demo snapshot if live
  saved updates cannot be read. Failed live research never becomes a fabricated answer.

No news/broker summaries or model-memory company facts supply Pull answers. Screener
is a primary-link index only. Raw PDFs and full source text are private in Supabase;
only company metadata and explicitly published prepared answers are anonymous-readable.

## Architecture

React/TypeScript/Vite/Tailwind on Render static hosting; Python 3.12/FastAPI on a free
Render web service; Supabase Postgres/Storage; GitHub Actions for scheduled source
ingestion. Supabase Cron is retained as an inactive, tested recovery option.
The frontend reads saved public results without waking Python. On-demand research
uses persisted jobs and polls their progress. No external vector service or RAG framework.

Postgres full-text search is complemented by Gemini embeddings, Supabase pgvector and
Reciprocal Rank Fusion, with company/document/date/metadata filters in both branches.
[Hybrid retrieval](docs/HYBRID_RETRIEVAL.md) is behind the existing feature flag;
production remains keyword-only during controlled rollout. The completed CCL
[evaluation](docs/HYBRID_EVALUATION.md) improves early reference-page recall, with equal
reviewed answer quality and additional latency. Other corpora require additional
quota-bounded backfill. Partial
indexes and semantic failures use the working keyword path with explicit limitations.
Existing citation/table guards remain in force; an added metric-name check withholds
unsupported financial acronyms.

Gemini 3.5 Flash-Lite handles ordinary answers. Gemini 3.8 Flash is preferred for deeper
analysis but was intermittently slow in live testing; a bounded Flash-Lite fallback
records the actual model and keeps the same source/chronology guards. Model reservations
in Postgres cap normal use below the user's stated free-tier limits; provider quotas
can still reject requests. Caches avoid repeating model calls for identical evidence.

PDF processing keeps layout text for tables and reading-order text for narrative.
New documents over 200 pages use the already-installed PDFium native text engine,
while pypdf preserves aligned financial-page text and pdfplumber preserves sampled
table cells/context. Native calls are serialised and handles closed promptly. Existing
verified corpora remain intact. A native decoding failure falls back to pypdf over
the same original PDF and records the warning.
Every document retains original/final URLs, hash, fetch time and page numbers. Unknown
publication/reporting dates stay unknown. Table cells are **candidates**, not approved
facts. Financial table comparisons remain disabled. A quote repaired for PDF whitespace
is replaced with the original source slice; split/ambiguous numbers cannot validate a
new figure. Citation matching does not mechanically prove semantic entailment: prepared
claims are also reviewed against their primary evidence.

## Run locally

```powershell
python scripts/bootstrap.py
# Create .env.local from .env.example only if it does not already exist.
.\.venv\Scripts\python.exe -m uvicorn finn.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
python scripts/npm.py run dev
```

Open `http://localhost:5173`. `/` is Briefing, `/?view=research` is Research,
`/?view=portfolio` is Portfolio, and `/?view=foundation` retains connection diagnostics.
The bootstrap uses a SHA-256-verified workspace-local Node 24 and `.venv`; it does not
change system PATH or PowerShell execution policy. On other platforms use Node 24 and
Python 3.12 directly with the same package manifests.

Local `.env.local` supports `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
`SUPABASE_PUBLISHABLE_KEY`, and `GEMINI_API_KEY`. Existing public aliases
`NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` also work. Secrets must
never have `VITE_` or `NEXT_PUBLIC_` prefixes. Vite explicitly exposes only public values.

Apply the SQL migrations in numeric order through the Supabase SQL Editor. **Keep RLS
on.** Migrations preserve private source/jobs/usage tables and grant public read-only
access to the intended mock portfolio and prepared outputs. They create no paid resources.

For a new database, first prepare one company end to end before scaling:

```powershell
.\.venv\Scripts\python.exe -m finn.ingest --symbol INFY --publish
.\.venv\Scripts\python.exe -m finn.ingest --portfolio
.\.venv\Scripts\python.exe -m finn.ingest --symbol POLYCAB --publish
.\.venv\Scripts\python.exe -m finn.ingest --symbol CCL --publish
.\.venv\Scripts\python.exe -m finn.briefing --mode all
```

Re-ingestion of unchanged PDFs reuses extraction and preserves content integrity.
Do not run corpus refreshes repeatedly as a unit test. A full source/model feasibility
check is available via `python -m finn.feasibility --symbol INFY`.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest
python scripts/npm.py run build
.\.venv\Scripts\python.exe scripts/check_frontend_secrets.py
python scripts/npm.py exec -- playwright install chromium
python scripts/npm.py run test:product
python scripts/npm.py run test:browser
```

Browser checks use real local API/cache connections; run both local servers first.
They cover phone/desktop layout, source drawers, windows/settings, 15-company data,
persisted research jobs, and an unknown ticker. Screenshots/results are in ignored
`artifacts/`. `test:browser` checks the separate connection-diagnostics view.
`python scripts/npm.py run record:demo` records a short phone walkthrough as a local
WebM file. Set `FINN_BROWSER_URL` to record or test the deployed frontend.

`python scripts/export_snapshot.py` exports only anonymously readable public data into
`frontend/public/recorded-snapshot.json`. This is a recorded demo, not live data; the UI
must show the recorded-data banner when using it. Preserve original dates when updating it.

## Deployment and automation

Use [Render setup](docs/DEPLOYMENT.md) and `render.yaml`. Existing deployed origins and
API URLs remain valid. Backend CORS permits GET and POST from the configured frontend
origin; it does not permit arbitrary origins. `/health/live` is process liveness,
while `/health/ready` reports configuration presence, not a blanket dependency guarantee.

Automatic updates use the verified [GitHub workflow](docs/GITHUB_AUTOMATION.md) with
these repository settings:

- Secrets: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`.
- Repository variable: `FINN_ENABLE_SCHEDULED_SYNC=true`.

`portfolio-sync.yml` checks announcements at minutes 17/47 and EOD prices at **18:15 IST**
on weekdays. GitHub scheduling can be delayed; actual sync state and timestamps are
shown. It needs no Gemini key and runs independently of a sleeping Render API.
Both [Supabase fallback schedules](docs/SUPABASE_CRON.md) are inactive. If switching
back to the fallback, turn the GitHub source variable off first. Do not run two
automatic schedulers together.

If an API request is blocked in the browser, check site-specific content-blocking rules
and the configured CORS origin. Do not put server secrets in frontend settings or
make private tables/buckets public to resolve a connection issue.

## Known limits and deliberate omissions

- NSE RSS offers a recent window; captured history builds over time and is not a full
  historical archive. Incomplete XML is retried, then only complete valid items are
  processed with a partial-coverage warning. Bad timestamps are not invented.
- Free API hosting can sleep; model calls can time out or hit quotas. The public saved
  briefing/research and labelled recorded snapshot keep the first screen useful.
- No comprehensive OCR, trading, broker integration, real-time prices, P&L, authentication,
  voice, external notification delivery, or complete financial dashboard.
- Large PDFs above the prototype's 50 MB/700-page processing bounds are rejected with
  an explicit coverage error. Password-protected or image-only documents are unsupported.
- No automatic financial comparisons from ambiguous tables. The narrative example is
  statement-level evidence review, not a company-wide management score.
- Exact-quote checks are necessary but not sufficient; review financial interpretations.

See [acceptance notes](docs/ACCEPTANCE.md), [build history](docs/BUILD_HISTORY.md), and
[submission draft](docs/SUBMISSION.md). The build log does not replace the assignment's
required coding-agent conversation exports/share links; export and redact those separately.
The [demo script](docs/DEMO_SCRIPT.md) and [release checklist](docs/RELEASE_CHECKLIST.md)
cover the final walkthrough and remaining manual submission items.
