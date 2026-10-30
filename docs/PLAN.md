# FINN implementation plan

Status: approved direction with the user's retrieval/extraction amendments incorporated.
Milestone 0 dependency/deployment checks have been verified and the user has authorised
continuation. The first working prototype now includes portfolio Push, primary-source
Pull, three prepared companies, and one conservative narrative/evidence comparison.
One-company acceptance preceded scaling. Semantic search remains deferred pending a
benefit benchmark; keyword retrieval is working. Model timeouts and fallback choices
are preserved in the evidence, not hidden behind fabricated answers.

## Requirements and product

The four-page main brief and three-page glossary remain the source of requirements.
Deliver a mobile-first working prototype, GitHub repository, AI build history, and
covering note. The deadline is Sunday, 1 November 2026; the brief supplies no cutoff
time. Submit to assessment@enam.com with subject `ENAM - IIT screening - 2027`.

- Portfolio: 15–20 NSE/BSE-listed companies; initially 15 across sectors and sizes.
- Push: proactively surface important portfolio changes, preserving access to routine
  filings. Pull: company research grounded in annual reports and call transcripts.
- Integrate EOD price/volume, exchange announcements, and primary company documents.
- Use the same generic NSE ticker discovery and analysis pipeline for prepared and
  unfamiliar companies. Do not introduce a demo-company allowlist.
- The eight research sections, exact announcement categories, professional biographies,
  results comparisons, and four-quarter tracker are examples rather than a checklist.
- Evaluate judgment, creativity, product sense, architecture, reliability, and efficient
  model use. Presentation should make the investor's task easier.

Keep the agreed attention-inbox direction over a research-first or chat-first product.
Use Briefing, Research, and Portfolio navigation; progressive disclosure and concise
cards with source links. Push delivery is in-app only.

Briefing defaults to 24 hours with seven-day/custom windows. Important items come first;
routine items expand on demand. Separate actual results from meeting/publication
notices. Price/volume alerts default to ±4% and 2× the prior 20 complete sessions' mean
volume, excluding the current session. Preferences are browser-local. Show coverage,
failed fetches, completion timestamps, and EOD session dates. Scheduled retrieval is not
instantaneous exchange delivery.

Investigate opens company-scoped research from a card. Provide a business summary,
selected dated financial facts, management commentary, uncertainties, suggested
questions, and free-text questions. Citations reveal excerpts, original links, document
dates, and PDF page numbers. First prove **one company end to end**, then prepare three
companies with a recent annual report and two transcripts each.

Keep narrative versus evidence as the first differentiator after reliable Push/Pull:
earlier statement → later observation → interpretation, with citations on both sides.
Use compatible metrics, periods, currencies, units, and accounting bases. Distinguish
an explicit target from commentary; return `not yet assessable` when appropriate.

## Architecture and retrieval amendment

Retain React + TypeScript + Vite + Tailwind, Python 3.12 + FastAPI/Pydantic, Supabase
Postgres/Storage, Render static frontend/free Python API, and GitHub Actions ingestion.
The frontend reads explicitly public cached outputs; all writes and privileged keys
remain server-side. Keep a visibly dated snapshot fallback, never a silent replacement
for a failed live fetch. Render cold starts and Supabase inactivity are known free-tier
constraints. Do not add another vector database or a RAG orchestration framework.

Design retrieval for PostgreSQL **full-text search + pgvector + metadata filters +
Reciprocal Rank Fusion (RRF)**, all inside Supabase:

1. Implement and verify keyword retrieval first, with company/document-type/date filters.
2. Reserve nullable embeddings with a recorded model, dimensionality, and document hash.
   Never mix incompatible embedding models or dimensions. Keep numerical table evidence
   attached to its table/header context rather than embedding isolated cells.
3. After the core works, test Gemini embedding access/quota, then add cosine retrieval
   under the same metadata filters. Use document/query task types as supported by the
   selected embedding model. Embedding generation is optional and separately budgeted.
4. Fuse independently ranked keyword and semantic candidates using
   `sum(1 / (60 + rank))`, equal initial weights, deterministic ties, then select the
   final evidence set. Do not combine raw ts_rank and cosine scores directly.
5. Missing embeddings, quota errors, or a disabled semantic flag retain functioning
   keyword retrieval and report the actual retrieval mode. Empty keyword evidence must
   abstain, not invite a model-memory answer.
6. Compare keyword and hybrid search on the same small, manually labelled company-scoped
   question set. Cap initial semantic work at about 90 minutes; retain it only if it
   improves evidence recall/support without unacceptable latency or quota use.

The minimum later interfaces remain company search, time-filtered cached briefing,
`POST /research`, persisted job status, and results with claims/citations/coverage/as-of.
Job stages are discovery, extraction, analysis, completed, and failed. Use polling.

## Extraction, source integrity, and AI

Use pypdf for page-aware text and pdfplumber for table candidates. Preserve raw PDF
hash, original and final URL, fetch time, source publication date (nullable), document
type, company, PDF page, table bounding box, cell matrix, row/column headers, nearby
caption/footnotes, period labels, currency/unit labels, and accounting-basis evidence.
Unknown metadata remains unknown; the fetch date is not the reporting/publication date.

Financial facts require evidence locating the value, metric, reporting period, unit,
currency, standalone/consolidated basis, and actual/guidance status. Extraction produces
candidates, not approved financial facts. Ambiguous headers, broken rows, conflicting
periods, or unresolved units block numerical comparison. Preserve negative signs,
parentheses, nil versus missing, percentages versus percentage points, and restatements.
No financial-comparison generation from unvalidated table cells. Initially mark scans
requiring OCR unsupported and expose that limitation.

Use Screener only to discover original report/transcript links, not its AI commentary
or standardised tables as substitutes for primary evidence. Fetch NSE RSS/dated filings
and accessible BSE/company-IR documents. Deduplicate identical documents and preserve
revisions. Fetch/capture errors remain errors; cached/historical results carry their
original dates and explicit labels. Do not bypass access controls.

Gemini 3.5 Flash-Lite handles bulk classification/extraction and ordinary grounded
answers. Gemini 3.8 Flash is preferred for the deeper comparison, with a bounded,
explicit Flash-Lite fallback when unavailable. Actual model identity is recorded and
the same source checks apply. The user reports 15 RPM/500
RPD and 5 RPM/20 RPD respectively; verify real access without claiming a probe proves
full daily capacity. Use structured output, bounded inputs/concurrency, retry delays,
and document/task/prompt/model-aware caching. Respect zero budget and do not enable
billing. Check exact-quote citation support; manually review semantic entailment.

Programming handles identities, financial arithmetic, units, time windows, alerts,
sorting, deduplication, source allowlisting, and schema validation. Treat source content
as untrusted input; unsupported answers abstain. No fabricated figures or model-memory
company facts.

## Milestones and acceptance gates

| Milestone | Work | Acceptance |
| --- | --- | --- |
| 0 (verified) | Feasibility and deployment foundation | Public price/feed/document access; one annual report and transcript discovered generically for one ticker; page/table extraction inspected; minimal model calls; Supabase DB/vector/FTS/storage probes; health endpoints/static frontend; deployed checks. Record pass/fail/blocked per dependency. |
| 1 (working) | One-company research pipeline, then data scaling | Prove discovery → extraction → metadata-filtered keyword retrieval → grounded cited answer and repeatability for one company before expanding to 15 portfolio/three research companies. |
| 2 (working) | Push | Windows, collapsed routine filings, hand-checked alert arithmetic, visible missing/stale data, idempotent ingestion. |
| 3 (working; semantic deferred) | Pull and optional hybrid retrieval | Same generic pipeline for two previously unprepared tickers; invalid/missing sources abstain; compare retrieval quality before extra tuning. |
| 4 (conservative example working) | Narrative versus evidence | One manually verified statement pair; delivery remains not assessable without a compatible completed-period outcome. |
| 5 (verification and packaging) | Harden and package | Phone QA; throttling, unavailable/malformed documents, empty/weekend windows, restart/retry and cached-data labels; documentation, recording, build history, covering note. |

Milestone 0 requires actual dependency evidence, not just scaffold code or documented
API capabilities. Missing credentials/deployment access leave the gate open. Do not
declare the milestone complete or start later work to disguise a blocker.

Keep native apps, accounts, broker integration, P&L, trading, real-time ticks, voice,
external notifications, comprehensive OCR, autonomous frameworks, and comprehensive
research coverage out of the first prototype. Extend to four quarters/results analysis
only after the core works. Preserve AI build history and redact secrets before sharing.
