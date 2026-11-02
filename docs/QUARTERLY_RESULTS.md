# Quarterly financial results

## Verified numerical research - 2 November 2026

Custom numerical questions now use an approved deterministic pathway alongside the
existing four-metric quarterly comparison. The general LLM prompt and its numerical
validation guards are unchanged. No new database migration, dependency, model API,
configuration variable or full embedding rebuild is required.

### Routing and supported scope

`metric_registry.py` contains **147 canonical metrics** across eight categories, with
aliases, units, industry applicability, support status, dependencies, source
requirements and accounting restrictions. Recognition is separate from successful
extraction. `debt/equity`, `D/E`, `ROE`, `P/E`, natural metric requests, explicit
periods/bases and profitability/financial-health questions are recognised. Definitions
such as `Explain what ROE means`, revenue-model questions, employee turnover and the
CFO's identity stay in ordinary Research. Generic CAGR/growth requests ask for the
base metric rather than substituting revenue.

- **Reported figures:** native PDF cells with explicit column dates, basis and units;
  explicitly dated numerical prose; previously server-validated quarterly cells,
  including matching two-image verification and original chunk evidence. Basic and
  diluted EPS remain distinct reported metrics. Operating profit is separate from
  explicitly reported EBIT; total income is separate from revenue from operations.
  RONW is distinct from ROE, interest-service coverage from interest coverage, and
  adjusted EBITDA/forward P/E from their standard counterparts. Unsupported adjusted
  definitions return an explicit missing result rather than the standard metric.
- **19 implemented calculation paths, conditional on compatible verified inputs:**
  current + non-current borrowings; net debt/net cash; debt/equity and net-debt/equity;
  current ratio and working capital; EBIT/interest expense coverage; gross, operating,
  EBIT, EBITDA and net margins; effective tax rate; revenue/profit growth; ROE;
  ROCE; free cash flow. No finance-cost total is silently substituted for interest
  expense, or EBITDA for EBIT. No industrial formulas are applied to financial firms.
- **Reported only:** other turnover/liquidity ratios, DSCR/gearing, ROA/ROIC,
  CAGR, segment indicators, banking, insurance and industry operating metrics.
  The engine attempts an explicit, unambiguous disclosure; no unsupported formula is
  advertised. Recognition does not imply every report format or sector is supported.
- **Dated reported values only for valuation:** P/E, forward P/E, P/B, EV ratios,
  market cap and related metrics. No live-price, forward-earnings, PEG or market-value
  calculation is implemented. Inaccessible or unstated valuation inputs remain missing.

### Verification, calculations and caching

Company identity is resolved first through the existing verified persistent NSE
snapshot. Existing hybrid/keyword retrieval supplies candidate pages; deterministic
label matching also finds actual disclosures beyond qualitative policy paragraphs.
Only primary annual/quarterly PDFs and approved financial cells can supply values.
Similarity, a citation alone, or a model-generated number cannot establish a fact.

Native extraction reuses `grouped_lines`, `parse_number`, `parse_date`, the quarterly
column validator and its date/basis rules. It preserves physical page, exact passage,
source URLs, document hash, row label, column header and cell bounding box. The repeated
annual-report navigation listing both bases is excluded from basis selection. The
existing image-verified quarterly cache is reused through its original source chunks,
not incorrectly checked against an empty scanned native-text page.

The older quarterly extractor deliberately saves P&L pages. New requests may add up to
12 relevant omitted balance-sheet/cash-flow/ratio pages from the already stored PDF,
with deterministic chunk IDs and incremental background indexing. Existing evidence
pages are not replaced. Up to 18 candidate pages per document are verified. This is
bounded page-level verification, not a parallel PDF ingestion pipeline.

Arithmetic uses Decimal and explicit definitions, retaining full precision and rounding
only display values (two decimal places, half up). Money scales are converted without
FX conversion. Every calculation checks entity, basis, currency, date and period kind.
Flow ratios need matching full annual/quarterly durations; as-at balances and uncertain
YTD/stub flows cannot stand in for income/cash-flow periods. Growth requires a positive
comparison base; ratios reject zero/negative denominators where inappropriate.

ROE uses profit attributable to owners and average opening/closing owners' equity,
excluding interchangeable NCI-inclusive totals. ROCE uses reported EBIT divided by
average opening/closing (assets minus current liabilities). Closing and average definitions
are never switched silently. FCF adds an explicitly signed cash outflow for combined
PPE/intangible purchases to CFO; accrual capex and ambiguous positive spending figures
are not substituted. A company's clearly disclosed ratio takes precedence over a
calculated alternative. Conflicting reported values/definitions are declined.

Every requested metric must return a verified numerical value with its metadata or an
explicit missing-data reason. This completeness check also applies to cached answers.
Missing values are not zero. Separate claims preserve each calculation input, including
two different cells on the same PDF page; source inspection and contextual follow-up
reuse the existing evidence panel and source validation.

The existing private research-cache table is keyed by verified ISIN, canonical intent,
requested dates/years/frequency/basis, document IDs/hashes/extraction versions, approved
quarterly-cache revision, parser/validation/calculation versions and optional evidence
context. Alias repeats reuse the answer without PDF verification, generation or
embedding work. Source timestamps retain their original dates.

### Entity safeguards and remaining limits

Cover identity/ISIN mismatches stop extraction. TMCV and TMPV have separate verified
ISIN policies; the new-company/changed-name cover must match the current issuer.
Automatic use of pre-1-October-2025 Tata figures is declined, with no inferred demerger
recast. The appointed/effective dates are documented in the
[official NSE information memorandum](https://nsearchives.nseindia.com/corporates/offerdocument/scheme/IM_TMCV.pdf).
This is a conservative guard, not a complete historical corporate-action engine.

Native headers must establish dates, units and basis; fiscal-year-only or damaged
headers, unreadable currency glyphs, ambiguous sections, unsupported scanned tables and
conflicting definitions can produce an unavailable result. Existing approved quarterly
image cells remain usable; this new route does not launch fresh ratio/annual-table OCR
or vision generation. Broad sector calculations, current valuations, historical entity
recasts and mixed-basis comparisons are not implemented. Ask for one basis per custom
numerical question; existing quarterly basis controls remain available.

### Actual primary-document checks

No financial value is hardcoded in application code.

| Request | Verified outcome | Original physical PDF page |
| --- | --- | --- |
| TMCV `debt to equity ratio` | 0.13 times, standalone, 30 September 2026 | [Quarterly filing, p.10](https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=09b74181-7f44-4aed-b9f0-c12d57fa5474.pdf#page=10) |
| TMCV FY2026 consolidated | 0.38 times, 31 March 2026 | [Annual report, p.222](https://www.bseindia.com/xml-data/corpfiling/AttachHis/c733587d-fcc8-432d-89fe-1e37630d8896.pdf#page=222) |
| TMCV FY2026 standalone | 0.22 times, 31 March 2026 | [Annual report, p.451](https://www.bseindia.com/xml-data/corpfiling/AttachHis/c733587d-fcc8-432d-89fe-1e37630d8896.pdf#page=451) |
| V2RETAIL quarterly net margin | 4.20% from compatible consolidated PAT and revenue, 30 June 2026 | [Quarterly filing, p.11](https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=a11441e0-2a87-4072-bc6c-b0cd51475381.pdf#page=11) |
| TMCV ROIC FY2019 | Explicit unavailable result | No old combined-company figure substituted |

Each observation retains its own entity, basis and period; compatible inputs are
required for calculations. Both V2RETAIL input sources were resolved independently
through the existing evidence validator. Browser checks use these actual verified
results, not invented financial numbers.

Reproducible checks (configured server credentials, existing prepared documents):

```powershell
.venv/Scripts/python scripts/verify_numerical_research.py
.venv/Scripts/python scripts/npm.py run build
.venv/Scripts/python scripts/npm.py run test:metrics
```

The opt-in verification script uses process-local keyword candidate search and cached
primary documents, with zero generation/embedding calls. It writes ignored snapshots
and source contexts for the browser check. Browser checks cover desktop 1440px/mobile
390px, both themes, reported/calculated/unavailable states, formula inputs, separate
source cells, contextual follow-up and horizontal overflow. Existing quarterly,
general Research and evidence regression checks pass. No unrelated ingestion or LLM
evaluation sweep was run.

Changed implementation: `backend/finn/metric_registry.py`, `metric_evidence.py`,
`metric_calculations.py`, `metric_research.py`; integration in `research.py`,
`evidence.py`, and an additive column-boundary field in `financial_tables.py`.
Frontend: `frontend/src/financial-metrics.tsx`, `financial-metrics.css`, `research.tsx`,
`frontend/package.json`, `frontend/scripts/verify-numerical-metrics.mjs`.
Tests: `tests/test_numerical_metrics.py`; live check: `scripts/verify_numerical_research.py`.


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
