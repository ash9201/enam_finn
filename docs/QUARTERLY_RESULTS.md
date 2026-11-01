# Quarterly financial results

The [1 November investor QA release](INVESTOR_QA.md) adds concise deterministic
performance observations, directly cited current-quarter note context where verified,
additive preservation of missing native financial pages, and fixes repeated results
rendering and navigation overlap. The original figures and comparison policy remain.

FINN acquires original quarterly filings and compares verified Revenue, explicitly
reported EBITDA, PBT and PAT. Research has a Quarterly results action; actual-results
briefing cards offer Compare quarters. Acquisition is generic for NSE tickers with
suitable primary filings. No company values are hardcoded or drawn from Screener's
financial tables. Source/generation dates remain visible; refresh explicitly checks
new original documents.

The [31 October experience audit](RESEARCH_IMPROVEMENTS.md) records coverage across
all 15 portfolio companies, source recovery, timings and remaining gaps. All 15 now
have some usable results, not complete coverage of every metric. Earlier acceptance
records describing withheld CCL cells refer to the previous native-only release.

## Extraction and preservation

1. Resolve through the live NSE directory and discover original quarterly source links.
2. Download only permitted primary BSE/NSE/company PDFs, preserving original/final URL,
   content hash, source check time and private original PDF.
3. Read native text, identify statement pages and use geometry-aware extraction there.
   The bound is 200 pages / three filings, allowing INFY's 195-page document. Quarter,
   half-year and year columns remain distinct, including merged and wrapped headings.
4. Check company identity, explicit period, basis, currency, scale, row meaning and
   numeric formatting. Unambiguous row mapping is deterministic; bounded LLM selection
   supplies row indices only when needed. It does not supply accepted native amounts.
5. For incomplete eligible statements, read at most two statement pages using two
   separate renders/reads of the same Gemini model. Each agreed cell/definition/header
   is retained independently; disputed cells remain missing. Native validated values
   are preserved, including CCL's separately reported associate share in group PAT.
6. Some native-only cells retain image-verified headers rather than image-verified
   amounts. Evidence distinguishes this method from two-image agreement. Explicit
   whole-company quarterly EBITDA prose has a separate native-plus-image agreement
   path; only an explicitly dated, matching quarter is accepted.

The two image reads are not independent models or accounting audits. Original page
previews make verification inspectable. Source PDFs are never edited or corrected.
Scanned/unfamiliar layouts without reliable metadata can still fail. There is no
unbounded OCR pipeline, guessed decimal insertion, fiscal-label date inference or
YTD subtraction. Same-quarter alternative index locators may be tried; an older
quarter is never silently presented as the latest.

Parser version `quarterly-tables-v4.2`, row-mapping version `quarterly-row-map-v2`,
source cells and evidence hashes participate in cache identity. Document versions are
additive, preserving old citations. Image reads can be reused by original PDF SHA.
Repeated analyses reuse dated results within 24 hours. Explicit refresh checks original
sources and reports failures. Results, jobs and raw documents use existing Supabase
storage; no additional vector store or paid resource was introduced.

## Comparison policy

- Revenue is revenue from operations. Banks may show explicitly identified **total
  income**, clearly labelled in the view; it is not silently called industrial revenue.
- Consolidated PAT is group profit before shareholder/noncontrolling attribution;
  separately reported associate shares are included. Standalone PAT is company profit.
- EBITDA must be explicitly reported, unadjusted and an amount, not a margin or segment
  metric. No PBT/finance-cost/depreciation reconstruction is offered.
- Require matching currency, accounting basis, period kind and metric definition.
  Known units normalize with Decimal; currencies never convert. Cross-basis data and
  incompatible definitions cannot produce changes.
- Prefer same-statement comparative columns and preserve restatements. Conflicting
  cells are withheld. Detected scope/regrouping changes can block cross-filing changes.
- Absolute change = latest minus base. Percent = change / base x 100, using unrounded
  Decimal values and ROUND_HALF_UP. Zero/negative bases retain valid absolute change
  without a misleading percent. Missing is not zero.

## Reviewed original-source cases, 31 October 2026

| Case | Original evidence | Verified behaviour |
| --- | --- | --- |
| POLYCAB | [BSE PDF](https://www.bseindia.com/xml-data/corpfiling/AttachHis/4ac93ea0-d4d1-4b85-8849-14a19e0dcceb.pdf), consolidated p.4, standalone p.10, INR million | Consolidated Revenue 98,989.01 / 82,097.32 / 64,772.11; QoQ +20.58%, YoY +52.83%. Revenue/PBT/PAT compare on both bases; standalone restatement preserved. |
| CCL | [BSE PDF](https://www.bseindia.com/xml-data/corpfiling/AttachHis/ac6a2647-0f4d-4ccc-8659-4101c055586a.pdf), consolidated p.7, standalone p.3, INR lakh | Recovered consolidated Revenue 121,076.24 / 120,044.62 / 112,672.61 and PBT 15,086.29 / 12,901.75 / 12,709.25. Group PAT 13,010.97 / 11,688.05 / 10,085.75 includes associates. Both bases now support all three periods for these metrics. |
| HDFCBANK | Original consolidated statement p.9, INR crore | Bank total income 129,358.69 / 133,110.36 / 118,560.63; group PAT 21,537.09 / 20,382.69 / 20,363.77 before NCI. Native damaged digits are not substituted for image-verified values. |
| SUNPHARMA | Original press release p.17, INR million | Current consolidated EBITDA 47,439, native prose plus separate image verification. Prior EBITDA fiscal abbreviations are not inferred into dates; QoQ/YoY remain missing. |
| Remaining partial cases | Original filings in the same generic pipeline | M&M has consolidated Revenue/PBT YoY only; Reliance PAT/standalone, NTPC consolidated PBT and Titan Revenue remain withheld. See the full coverage table. |

These are implementation spot checks, not an audit of every cell. All 15 pipeline
runs passed their available-data comparison path. Source layouts and dates can change;
acceptance scripts deliberately stop if the dated reviewed values change.

## Evidence, research and UI

Figures open the existing evidence drawer with row, column, raw amount, quarter,
basis, scale, PDF page, source URL and exact source passage/transcription. Original
statement-page previews are generated server-side from hash-verified private PDFs;
no storage secret reaches the browser. A calculation opens its formula and both
figure references. Partial coverage has an explicit note and usable values remain.

Ask about this evidence retains the numerical anchor and retrieves other company
reports/calls through the existing retrieval pipeline. Historical commentary is
labelled as context; it cannot prove the selected quarter's causes. Financial keyword
retrieval remains separate from the annual-report/transcript embedding manifest, so
quarterly ingestion does not invalidate completed semantic indexes. Narrative models
cannot invent new financial comparisons.

## Operations and tests

Migrations 0008 and 0009 were applied by the owner with RLS enabled. Private source
search, documents, pages and image-verification data remain server-only. Only explicitly
published prepared results are anonymously readable. Anonymous image requests require
a valid canonical published/private result reference; no arbitrary path is accepted.

`python scripts/verify_financial_results.py` checks the reviewed POLYCAB/CCL values,
periods and cache reuse. `python scripts/verify_portfolio_financials.py` audits all 15;
`--refresh` checks original files and `--publish` explicitly publishes reviewed results.
Targeted tests cover amounts, metadata, units, ambiguous periods, image disagreement,
PAT attribution, reported EBITDA versus margins/adjusted/YTD, provenance and arithmetic.
The consolidated research browser matrix covers both themes/viewports, financial
partial data, figure evidence, original pages and one real follow-up. See
[acceptance](ACCEPTANCE.md) for final regression/build checks.

Broader accounting review, fiscal-label EBITDA tables, insurance metrics, NII/NIM and
full OCR remain outside this release. A successful generic discovery does not guarantee
that a company's figures will be supported.
