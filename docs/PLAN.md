# Architecture and technical design

FINN combines an investor attention inbox with primary-source company research.
Briefing answers what deserves investigation; Research keeps the investor close to
the underlying documents; Portfolio compares activity across a 15-company mock watchlist.
The [README](../README.md) introduces the product and deployment.

## Application boundaries

The React/TypeScript frontend is a Render Static Site. It reads intended public
Supabase content directly so Briefing, Portfolio and published research can remain
useful while the Python API wakes. FastAPI handles acquisition, research jobs,
evidence verification and privileged writes. Supabase stores company identities,
filings, EOD bars, document versions, pages/chunks, answers, jobs, vectors and usage.
Private PDFs live in Supabase Storage rather than Render's ephemeral filesystem.

Persisted jobs and polling avoid a separate queue service or WebSocket layer.
Acquisition is serial and answer/indexing workers are bounded to respect free-instance
memory and provider quotas. Restart recovery can reuse saved documents; this is not
a distributed worker system that guarantees every in-process task completes.

The watchlist is APLAPOLLO, BHARTIARTL, CCL, HDFCBANK, INFY, ITC, KPITTECH, LT,
M&M, NTPC, POLYCAB, RELIANCE, SUNPHARMA, TATASTEEL and TITAN. Research is not restricted
to that list. Prepared and unfamiliar companies use the same resolution, discovery,
ingestion and answering code.

## Company identity and source acquisition

Resolution uses a verified persistent NSE directory snapshot, bundled official capture
and trusted previously resolved identities. Symbol/ISIN conflicts are guarded; matching
names alone cannot authorize another issuer's evidence. Browser autocomplete supports
names, symbols, aliases, histories and minor typos; ambiguous matches require selection.

The source workflow attempts an official directory refresh at most daily when due.
Malformed responses, HTTP 403 and storage failures preserve the last-known-good snapshot.
Backend snapshot memory has a 15-minute TTL; the browser memoizes its loaded directory
for the page lifetime. Source/check dates remain available in secondary details.
Previously verified companies do not need a successful live directory request per question.
Unknown listings can remain unresolved until verified data is available.

Screener is used only as an index of annual-report and earnings-call links. FINN
downloads original company/exchange PDFs; broker reports, news, Screener-generated
summaries/tables and model-memory company facts are excluded from Pull evidence.
Initial acquisition targets one annual report and two calls; optional earlier-history
acquisition requests two reports and four calls where available. This is a bounded
active manifest, not an unlimited archive or scheduled whole-market document crawl.

Documents retain original/final URLs, hashes, fetch times, source dates and physical
PDF pages. Discovery labels and fetch dates are not verified publication dates.
Annual-report/transcript extraction is bounded to 50 MB and 1,600 pages. PDFium speeds
large narrative extraction; pypdf layout and pdfplumber preserve financial-page/table
candidates. Native handles are closed and serialized where required. Candidates are
not approved financial facts. Quarterly statement processing has its own tighter bounds
and [financial validation pathway](QUARTERLY_RESULTS.md).

## Research, generation and evidence

`POST /research` resolves a company, reuses or acquires its corpus, retrieves evidence,
generates structured claims and validates them. It returns a completed cached answer
or a persisted job identifier for polling. Prepared-answer GETs provide a read-only
published path; even a cached Research POST may create a job and schedule indexing.

Keyword and optional hybrid search share company/document filters. Investor-aspect
detection can supplement the main query with up to four focused keyword searches
within the ten-passage budget. Requested aspects remain explicit in the answer plan;
one bounded repair can address missing coverage from the same evidence. Missing
support becomes a coverage limitation rather than a guessed numerical contribution.
Business-model answers distinguish commercial mechanics from accounting policies.
See [retrieval implementation](HYBRID_RETRIEVAL.md).

Current ordinary generation, quarterly text/image extraction and management comparisons
use `gemini-3.5-flash-lite`. `gemini-3.8-flash` remains a reasoning-model configuration
option, not the current comparison runtime. Embeddings use `gemini-embedding-001`.
Programming handles identity, dates, arithmetic, deduplication, thresholds, cache keys
and schema/source validation. Downloaded text is untrusted input, not instructions.

Each accepted claim binds to stored company-owned evidence. Quote normalization returns
an original source slice; it cannot introduce new digits. Named-metric checks prevent,
for example, a margin quotation from supporting an added EBITDA claim. General narrative
generation cannot turn ambiguous table text into approved financial comparisons.
Exact quotation presence does not prove semantic entailment; reviewed examples and
conservative abstention supplement automated checks.

### Evidence-first follow-ups

Answer prose is selectable text. Dedicated evidence chips open a desktop drawer or
mobile bottom sheet with the exact passage, PDF page, date and distinct external PDF
link. Source switching, keyboard dismissal, focus restoration and scroll locking keep
inspection usable. Typed validation errors are distinct from temporary storage outages;
unverified saved context cannot authorize a follow-up.

The drawer makes one bounded 15-second verification request, cancelled on source
changes or close. A temporary outage retains labelled saved evidence and a retry;
invalid ownership/page/hash references fail validation. Missing date metadata and a
failed page preview do not independently invalidate a verified stored passage.
Verification rechecks stored source evidence, not external PDF availability or model output.

The client passes references rather than an authoritative quote:

```json
{
  "symbol": "CCL",
  "question": "What did later commentary say about this statement?",
  "context": {
    "research_id": "<answer UUID>",
    "citation_id": "<citation UUID>",
    "claim_index": 0,
    "intent": "later"
  },
  "include_history": false,
  "refresh": false
}
```

The server resolves the saved claim, company and citation membership, then verifies
the source quote/page version. A read-only evidence endpoint exposes the selected
passage without returning the entire private document. Intent can be `question`,
`repeated`, `later` or `perspective`. The anchor stays available while retrieval gives
other documents space. Repetition excludes known duplicate calls. Later-evidence
investigation requires independently verified chronology and abstains before generation
if no suitable later source exists. A general follow-up does not require a dated anchor.
Context can be removed to return to general company research.

Management tracking selects complete management speech with primary-document speaker
roles, not analyst questions. CCL's reviewed example distinguishes reaffirmation from
delivery. KPIT's incomplete units/full-year outcome prevent a numerical target verdict.
This is statement-level analysis, not a comprehensive management score or guidance ledger.

## Briefing and Portfolio semantics

NSE RSS supplies recent announcements; accumulated capture is not a complete archive.
Deterministic enrichment reads bounded native PDF/XML/feed details, preserving source
hashes, pages and individual filing identities. Grouping needs explicit relationships:
results period; director/effective date; dividend type/record date; or call date and
recording URL. A common PDF packet, headline or publication day is insufficient.
NTPC's results, dividend and debt disclosures therefore remain distinct developments.

Enrichment limits PDFs to 30 MB/the first eight pages and XML to 2 MB, rejecting
declared entities. Unchanged successful source fingerprints reuse saved details;
failed attempts wait six hours before retry. This is bounded native extraction,
not exhaustive OCR or detection of every unannounced same-URL replacement.

Review receipts are event-level and browser-local. They record meaningful source
versions; new or changed evidence becomes Updated since review, while identical
duplicates/rescan times do not. Undo restores prior state. Legacy filing reviews are
imported where possible but cannot reconstruct old content versions. Review never
reshuffles the selected chronological/company ordering.

Filing windows and review/category/significance filters apply to events, retaining
their related sources. EOD alerts are separate watchlist-wide calculations: default
±4% daily move and 2× previous-20-completed-session average volume. Split-affected
comparisons are suppressed. Prices are unadjusted individual share prices. Portfolio
recent-event indicators reuse actual captured events, not speculative financial signals.

## Caching, failure handling and security

Cache identity incorporates relevant document hashes/scope, prompt/model/extraction
versions, financial calculation versions and evidence context. Superseded documents
remain for existing citations. Failed refreshes retain dated data with errors; labelled
recorded snapshots are recovery content, never silent substitutes for successful live work.

RLS keeps documents, chunks, vectors, usage and unpublished database records private;
only intended public outputs have anonymous read policies. Privileged keys stay on
the server. The prototype has no user authentication: possession of research/job
identifiers enables associated API reads. It is suitable for this public-document
demo, not confidential uploads or multi-user authorization.

Shared spacing/theme tokens, compact desktop navigation and safe-area-aware mobile
navigation serve all three views. Session-mounted views preserve drafts, filters,
workspaces and scroll; deliberate company links open the requested company. Inactive
views pause polling and are inert. System Status is secondary, has a return action,
and checks connectivity rather than claiming model/source freshness.

See [deployment and refresh schedules](DEPLOYMENT.md), [testing and known gaps](EVALUATION.md),
and [chronological decisions](BUILD_HISTORY.md).
