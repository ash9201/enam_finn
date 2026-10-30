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
