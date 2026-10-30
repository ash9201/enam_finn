# Milestone 0 findings

Verified on **30 October 2026** against real public sources and the user's Gemini and
Supabase project. No credentials are recorded here.

**The dependency/deployment gate has since passed and the user authorised continuation.**
The original findings below preserve the first checkpoint; current results are in
[working-prototype acceptance](ACCEPTANCE.md). A later idle API request took 43.19 seconds.

| Check | Result | Evidence |
| --- | --- | --- |
| NSE company directory | Pass | INFY resolved from the live equity directory; no demo-symbol shortcut. |
| NSE announcements | Pass | Live RSS parsed; its recent window is not a complete historical archive. |
| EOD prices/volume | Pass | yfinance history, incomplete current-day data excluded, prior-20-session baseline. |
| Generic discovery | Pass | Raw primary links from Screener's report/concall sections; no summaries ingested. |
| Annual report | Pass | Latest linked 2026 report from BSE: 8,985,010 bytes, 383 PDF pages, page-aware text. |
| Transcript | Pass | October 2026 original transcript from BSE's wrapper target: 3,742,339 bytes, 48 PDF pages. |
| Gemini 3.5 Flash-Lite | Pass | Structured JSON and source-quote check; reported 215 total tokens. |
| Gemini 3.8 Flash | Pass | Minimal structured-output check; reported 141 total tokens, including thinking. |
| Embedding access | Optional pass | `gemini-embedding-001` returned 768 finite dimensions. Semantic retrieval remains disabled; corpus-scale quota not proven. |
| Supabase DB/FTS/vector | Pass | Private insert/read/delete, keyword search capability, cosine distance 0 for identical vectors. |
| Supabase permissions | Pass | Publishable key allowed public status reads, denied private reads/writes and status writes. |
| Private PDF storage | Pass | Upload/download hashes match; anonymous read/public URL/upload denied; probe objects cleaned up. |
| Frontend build/secrets | Pass | TypeScript/Vite build; public values available; configured Gemini/Supabase secrets absent from emitted assets. |
| Browser checks | Pass | Chromium at phone/desktop sizes: real API/cache reads, no horizontal overflow or uncaught page errors, explicit API failure state. |
| Offline tests | Pass | 15 tests: source grounding, metadata/comparison guards, generic discovery, configuration, CORS, deployment secret boundaries, safe failures, reports. |
| Render deployment | Pending | No deployed URL assumed. |
| Deployed CORS/cold start | Pending | Requires real services and an idle-period check. |

## Financial extraction review

Generic alignment initially split narrative columns and row labels. The extractor now
prioritises statement headings and uses explicit header anchors when available. One
actual consolidated P&L page was rendered and visually reviewed: **PDF page 288,
printed page 318**. The original source identifies consolidated accounts, rupees in
crore with per-share exceptions, and years ended March 31, 2026 and 2025. Extraction
preserves the revenue label, note reference, and both raw year values.

This is a bounded extraction acceptance sample, not an enabled financial-comparison
feature. Eight annual-report pages were sampled. All tables remain unvalidated
candidates; comparisons are disabled. Whole-document tables, complex footnotes,
normalised/approved financial facts, and investor research answers are later work.
Unknown document publication/reporting dates remain null, separate from discovery labels.

BSE's general announcement page returned 403 during planning, but actual attachment
URLs worked at runtime. Access must be evaluated per endpoint/deployment environment.

## Reproducible local evidence

- `artifacts/milestone-0/feasibility.json` / `.md`: initial full live run; includes the
  initial missing-schema failure before the user applied SQL.
- `artifacts/milestone-0/infrastructure/feasibility.json` / `.md`: passing Supabase
  recheck after SQL, superseding the earlier database/storage failures.
- `artifacts/milestone-0/INFY-annual_report.json` / `.pdf`: primary-source evidence,
  metadata and table candidates; re-extraction preserves the original fetch time.
- `artifacts/milestone-0/INFY-transcript.json` / `.pdf`: transcript evidence.
- `artifacts/milestone-0/annual-report-p288.png`: inspected financial page.
- `artifacts/milestone-0/browser/`: phone/desktop screenshots and browser check JSON.

Artifacts/PDFs are ignored by Git. See [Render setup](DEPLOYMENT.md) for remaining work.
