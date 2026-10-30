# Build history summary

This record does not replace the assignment's required coding-agent conversation
exports/share links. Export those separately, redact credentials, and never bundle
`.env.local` into build history.

## 30 October 2026 — Milestone 0 only

- Read both PDFs and discussed product, architecture, costs, scope, and acceptance
  gates with the user. Added the requested hybrid retrieval/table-extraction amendments.
- Installed a local Python environment and SHA-256-verified official portable Node
  24.22.2. Did not change system PATH or PowerShell execution policy.
- Built the limited React foundation page and FastAPI liveness/configuration endpoints.
  No portfolio, investor feed, full research endpoint, or fake market data was added.
- Accepted public Supabase variable aliases; renamed the secret locally to a
  server-only variable and checked production assets for credential exposure.
- Added generic live source probes, page-aware extraction, conservative table
  candidates, metadata preservation, and credential-safe dependency reporting.
- Verified both requested Gemini models with one minimal request each and tested
  optional embedding access with one request. Semantic retrieval stays disabled.
- Initial Supabase checks correctly failed before SQL existed. The user applied the
  migration; DB/FTS/pgvector/storage and access-policy rechecks then passed.
- Inspected a real consolidated financial statement, improved table sampling/anchors,
  and kept all financial comparisons blocked pending validated facts.
- Passed offline and phone/desktop Chromium checks, including real cache/API access
  and explicit failed-request behaviour. Scanned emitted assets for actual secrets.
- Prepared Render free-tier configuration, CI/manual feasibility workflows, and setup
  instructions. No public URL or successful deployment has been invented.
- Stopped at the Milestone 0 deployment gate; later milestones remain unstarted.

## 30 October 2026 — first Push/Pull prototype

- The user deployed the foundation and authorised continuation. Verified real frontend,
  API, CORS, public-cache reads and a later idle-request latency; preserved model timeout
  and retry evidence instead of erasing failures.
- Added keyword-first company research with page/chunk provenance, content-hash PDFs,
  private storage, persisted jobs, restart recovery, source-filtered retrieval and
  validated citations. Applied the same engine to INFY before expanding to POLYCAB/CCL.
- Fixed narrative column interleaving without weakening table guards. Source-quote
  alignment returns original source characters; tests reject merged ambiguous numbers.
- Added RLS migrations and server-only policy audit. The user applied them with RLS on;
  live anonymous access tests verified the intended boundaries.
- Built real portfolio sync, explainable filing categories, EOD alerts, a watchlist,
  windows, routine expansion, settings and source-to-research navigation.
- Handled observed NSE timestamp variants and incomplete RSS, exposing incomplete
  coverage rather than substituting a fake feed. All 15 price snapshots were retrieved.
- Added a statement/evidence comparison with exact quotes and conservative period
  handling. Stronger-model latency led to a bounded, recorded smaller-model fallback.
- Added a public-only recorded snapshot with a visible historical-data notice, automated
  source workflow gated by repository configuration, browser acceptance and submission
  notes. Conversation exports/share links are still a separate submission artifact.

### Deployment verification findings

- Pushed the working prototype and verified actual Render phone/desktop flows. A fresh
  deployed question returned five exact-quote-backed claims; the model path works.
- An unprepared TCS request failed during source discovery on Render. Fixed-host,
  operator-only diagnostics isolated source connectivity failures; IPv4 did not fix
  them. Kept the failed job and did not replace it with a local seeded answer.
- Added bounded source GET retries, source-specific failures and safe status-poll
  recovery after a real disconnected response. Browser testing deliberately interrupts
  one status read to verify recovery.
- GitHub configuration is present, but both CI and dispatched sync stop before any
  jobs start. Requested the error banner; no paid spending or account settings changed.
- Recorded a phone walkthrough. Updated acceptance and README to expose the remaining
  deployment issues instead of declaring full completion.

### Public-runner retry and first live Singapore corpus

- Verified that the user made the repository public and restored the paid budget to $0.
  Retried CI/source jobs on standard Ubuntu only. Both remain blocked before runner
  assignment by an explicit account billing lock; no code ran and no larger runner
  was requested. Prepared a support draft without contacting anyone.
- The Singapore API reached the document index and completed uncached TCS research
  with one annual report/two calls and three page-backed claims. No local TCS corpus
  was seeded to conceal the earlier deployment failure.
- Profiled a slow 361-page first load. Reused the existing PDFium dependency for the
  large-document text pass, preserving pypdf financial-page layout and pdfplumber
  cells/geometry. Added native-handle cleanup, serialisation, source-preserving decode
  fallback, and real page/table/saving progress. Local full extraction fell from
  about 60 seconds to 7 seconds; deployed cold performance still needs checking.

### Singapore frontend verified; Supabase Cron fallback

- Confirmed that the user switched the production frontend and local canonical API
  URL to Singapore. Deployed product browser checks passed at phone/desktop sizes.
- User explicitly approved Supabase Cron after public standard-runner GitHub jobs
  remained blocked by the account billing lock. Paid budgets remain zero; GitHub
  source scheduling remains off to avoid duplicate automatic runs.
- Added a server-authenticated sync endpoint, private singleton lease/job, shared
  serial executor, per-source completion/error reporting, Vault-backed pg_net dispatch,
  and local-only credential SQL generation. No new service or model calls are needed.
- Added five failure/security/worker tests; 69 tests pass locally. Real Cron execution,
  cloud NSE/Yahoo fetching and deployed policy checks await the owner's SQL setup.

### Cron executes; transient provider failure and recovery (31 October IST)

- Verified the owner's SQL setup: two active schedules, successful self-removing
  Cron dispatch, HTTP 202 after API wake-up, private-table RLS and denied anonymous
  read/write/function access. Actual results were partial: filings and 14/15 prices.
- One Yahoo rate limit retained the original dated APLAPOLLO bar with an explicit
  error. A bounded operator rerun recovered 15/15. Saved both reports separately;
  did not relabel operator activity as scheduled activity.
- Added one rate-limit retry and late EOD recovery on subsequent announcement ticks,
  protecting the once-daily refresh against research contention or transient failures.
  78 tests pass. Prepared a credential-free self-removing full-source Cron recheck.

### Full scheduled refresh accepted (31 October IST)

- Confirmed the user's recheck as an actual Cron job: full-source work completed at
  03:23:18 IST, with all 15 prices and the announcement scan successful. Verified
  both active schedules, current source dates, private job RLS and anonymous denials.
  The one-time check removed itself; regular half-hour runs also succeeded.
- Preserved the original partial run and operator recovery separately. Only the new
  genuine scheduled run closes the full-source acceptance gate. GitHub source jobs
  remain off; no paid runner or service was enabled.
- Refreshed the public-only dated fallback snapshot and prepared the release checklist,
  demo script and updated covering draft. Actual conversation export and physical-phone
  review remain manual; no submission email has been sent.

### Stronger session integrity and primary-source recovery

- The release export caught an error missed by the initial freshness check: recent
  fetch timestamps accompanied older sessions because Yahoo returned a null latest
  close. Corrected the acceptance interpretation instead of shipping a false claim.
- Restored only strictly newer, previously verified saved records, retaining original
  dates with explicit failed-refresh markers; kept before/after evidence. The source
  is marked failed for genuine automatic overdue-EOD recovery.
- Added bounded NSE daily-archive recovery with exact date/EQ symbol/ISIN/hash checks,
  visible latest/history provider labels, no backwards session updates and no silently
  skipped baseline sessions. All 15 official records verified locally; none seeded
  as a fake cloud source success. Eighty-seven tests now pass.
- Reviewed real filing descriptions and corrected an earnings-discussion notice's
  availability claim; retained its original ID, source and publication time.
- The ordinary 03:47 IST Cron tick automatically recovered the failed EOD status through
  the new NSE adapter on Singapore: 15/15 records, actual 30 October sessions and source
  links, no errors. The strengthened read-only verification passes price integrity as
  well as dispatch, completion, freshness and access. No extra user SQL or local quote
  seeding was used. Exported the public fallback only after that result.
