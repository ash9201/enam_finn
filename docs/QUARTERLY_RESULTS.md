# Financial extraction and numerical research

FINN separates narrative research from approved financial facts. Finding a number in
retrieval or asking an LLM for a ratio does not make it verified. Quarterly comparisons
and custom numerical questions reuse primary PDFs, native source cells, existing jobs,
caches and the [evidence interaction](PLAN.md#evidence-first-follow-ups).

## Quarterly results pipeline

1. Resolve the issuer through verified persistent NSE identities; discover original
   quarterly-result links generically, without company-specific hardcoded values.
2. Download permitted company/NSE/BSE PDFs, retaining original/final URL, SHA-256,
   source-check time and private original. Inspect up to three filings and a 200-page
   financial-processing bound; prefer actual statement pages before table extraction.
3. Extract native text/cell geometry. Preserve physical page, row/column headers,
   period kind/end, currency/scale, standalone/consolidated basis, actual/guidance
   status and source passage. Quarter, half-year and year columns remain distinct.
4. Validate identity, explicit dates, units, metric meaning and formatting. Deterministic
   mapping handles clear rows; optional schema-bound LLM mapping supplies row indices,
   not accepted native amounts.
5. For eligible damaged statements, bounded recovery reads at most two statement pages
   using separate renders/reads of the same Gemini model. Agreed cells/metadata are
   accepted independently; disagreement remains missing. Some native cells use only
   image-verified headers, a separately labelled method. Explicit whole-company EBITDA
   prose uses native-plus-image agreement for an explicitly matching quarter.

Two image reads are not independent models or financial audits. There is no guessed
decimal insertion, YTD subtraction, fiscal-abbreviation date inference or unbounded
OCR. Original PDFs are never edited. Document/extraction versions are additive, preserving
older citations; image reads can be cached by original PDF hash. Answer reuse has a
24-hour window; explicit refresh checks originals and reports failure rather than
silently presenting an older quarter as latest.

### Comparison policy

- Revenue means revenue from operations. A bank's total income is explicitly labelled;
  it is not silently equated with industrial revenue.
- Consolidated PAT is group profit before shareholder/noncontrolling attribution,
  including separately reported associates. Standalone PAT is company profit.
- EBITDA must be explicitly reported, unadjusted, whole-company and an amount.
  Margins, adjusted EBITDA, segment EBITDA and reconstructed PBT/finance-cost/depreciation
  calculations cannot substitute.
- Currency, basis, period kind, entity scope and metric definition must match. Known
  money scales normalize with Decimal, without FX conversion. Same-statement comparative
  columns are preferred and restatements retained. Conflicting cells and detected
  scope/regrouping changes can block comparisons.
- Absolute change is latest minus base; percentage is change/base × 100. Use unrounded
  Decimal values and round display half up. Zero/negative bases can retain valid absolute
  changes without a misleading percentage. Missing is not zero.

## Custom numerical research

The [metric registry](../backend/finn/metric_registry.py) recognizes **147 canonical
metrics** with aliases, units, sector applicability, dependencies and support status.
Recognition is separate from available extraction/calculation. Definitions such as
“Explain ROE,” business revenue-model questions and the CFO's identity remain ordinary
Research. A generic CAGR request asks for the base metric instead of assuming revenue.

| Support | Implemented boundary |
| --- | --- |
| Reported facts | Explicit native statement cells, dated numerical prose and previously approved quarterly cells with original evidence |
| 19 conditional calculation paths | Total borrowings; net debt/cash; debt/equity and net-debt/equity; current ratio; working capital; EBIT/interest coverage; gross/operating/EBIT/EBITDA/net margins; effective tax; revenue/profit growth; ROE; ROCE; FCF |
| Reported only | EPS, EBITDA and CFO amounts; other turnover/liquidity ratios, DSCR/gearing, ROA/ROIC, CAGR, segment, banking, insurance and industry operating metrics |
| Valuation | Explicitly dated reported P/E, forward P/E, P/B, EV ratios, market cap and related disclosures; no live/forward market-value calculation |

Basic/diluted EPS, operating profit/EBIT, total income/revenue from operations,
RONW/ROE and interest-service/interest coverage remain distinct. Adjusted definitions
do not fall back to standard metrics. Industrial formulas are not applied to financial
firms, and total finance costs cannot replace interest expense.

Candidate search combines existing hybrid/keyword retrieval and deterministic disclosure
labels. Native extraction reuses the same number/date/header validators. Repeated annual
navigation listing both accounting bases cannot establish a cell's basis. New numerical
requests can preserve up to 12 relevant omitted balance-sheet/cash-flow/ratio pages
from the stored hash-checked PDF; up to 18 candidate pages per document are verified.
Existing evidence pages are not replaced. This does not launch fresh annual-ratio OCR.

Calculations require compatible entity, basis, currency, dates and durations. As-at
balances cannot stand in for full-period flows; uncertain YTD/stub periods are rejected.
ROE uses owners' profit and average opening/closing owners' equity. ROCE uses reported
EBIT and average opening/closing assets minus current liabilities. Closing versus
average definitions cannot switch silently. FCF uses CFO plus explicitly signed cash
outflow for combined PPE/intangible purchases, not accrual capex or ambiguous spending.
A clearly reported company ratio takes precedence; conflicting definitions are declined.

Each requested metric returns a verified value with metadata or a specific unavailable
reason, including on cache reuse. Every input is independently inspectable even when
two cells share a page. Cache identity includes ISIN, canonical intent, requested
period/frequency/basis, document hashes/extraction versions, approved quarterly revision,
calculation/validation versions and optional evidence context.

### Entity safeguards

Cover/ISIN mismatches stop extraction. TMCV and TMPV use distinct identities; automatic
use of pre-1-October-2025 Tata figures is declined rather than inventing demerger recasts.
The [official NSE information memorandum](https://nsearchives.nseindia.com/corporates/offerdocument/scheme/IM_TMCV.pdf)
records the underlying scheme dates. This is a conservative guard, not a complete
historical corporate-action engine.

## Reviewed primary-document examples

These dated examples are implementation spot checks, not independently audited coverage
or permanent latest-quarter claims. Amounts are latest / previous quarter / prior-year
quarter, where shown.

| Case | Original physical PDF evidence | Outcome |
| --- | --- | --- |
| POLYCAB, September 2026 | [BSE filing p.4](https://www.bseindia.com/xml-data/corpfiling/AttachHis/4ac93ea0-d4d1-4b85-8849-14a19e0dcceb.pdf#page=4), INR million | Consolidated Revenue 98,989.01 / 82,097.32 / 64,772.11; QoQ +20.58%, YoY +52.83%. Standalone restatement retained. |
| CCL, September 2026 | [BSE filing p.7](https://www.bseindia.com/xml-data/corpfiling/AttachHis/ac6a2647-0f4d-4ccc-8659-4101c055586a.pdf#page=7), INR lakh | Recovered Revenue 121,076.24 / 120,044.62 / 112,672.61; group PAT 13,010.97 / 11,688.05 / 10,085.75 includes associates. |
| SUNPHARMA, September 2026 | Saved original press release p.17, INR million | Explicit current consolidated EBITDA 47,439. Prior fiscal-label EBITDA amounts remain unverified. |
| TMCV, September 2026 | [Quarterly filing p.10](https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=09b74181-7f44-4aed-b9f0-c12d57fa5474.pdf#page=10) | Reported standalone debt/equity 0.13 times. |
| TMCV, March 2026 | [Annual report p.222](https://www.bseindia.com/xml-data/corpfiling/AttachHis/c733587d-fcc8-432d-89fe-1e37630d8896.pdf#page=222) / [p.451](https://www.bseindia.com/xml-data/corpfiling/AttachHis/c733587d-fcc8-432d-89fe-1e37630d8896.pdf#page=451) | Consolidated 0.38 times and standalone 0.22 times remain separate. |
| V2RETAIL, June 2026 | [Quarterly filing p.11](https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=a11441e0-2a87-4072-bc6c-b0cd51475381.pdf#page=11) | Net margin 4.20% calculated from compatible consolidated PAT/revenue; both inputs cited. |
| Unsupported historical request | TMCV ROIC FY2019 | Explicit unavailable result; no old combined-company figure substituted. |

The 31 October portfolio audit found some usable quarterly figures for all 15 companies,
not complete four-metric/basis coverage. M&M lacked usable PAT/QoQ and standalone;
NTPC consolidated PBT remained unverified; Reliance PAT/standalone and Titan eligible
total Revenue remained unavailable. Other files may contain relevant data in unsupported
formats. A dash means unverified/unavailable, not proof a company never disclosed it.

## Evidence and presentation

Quarterly figures open the existing drawer with raw amount, row/column, period, basis,
scale, exact passage/transcription and source page. Hash-verified private PDFs supply
original page previews without exposing Storage secrets. Changes expose their formula
and input references. Accounting-basis controls update figures, commentary and evidence
without duplicating the results section; unavailable bases stay explicit.

“What the figures show” separates deterministic observations from disclosed context.
SUNPHARMA's September 2026 consolidated YoY Revenue +11.88%, PBT −24.19% and PAT −36.16%
is an observation, not a causal explanation. Source-matched acquisition/transaction
costs and litigation notes appear under one Additional disclosures heading with separate
evidence buttons and one incomplete-attribution qualification. Context must match
company, quarter and basis; raw monetary text is not promoted into approved figures.

Ask about this evidence retains the financial anchor while retrieving other company
reports/calls. Other-period commentary cannot prove current-quarter causes. Current
quarterly PDFs are included in the shared search/indexing scope; adding one can make
a formerly complete company index incomplete until backfill catches up. Existing
citations remain intact. General narrative models cannot invent new financial figures.

## Verification and limitations

Targeted tests cover amount parsing, damaged/ambiguous headers, quarter versus YTD,
image disagreement, PAT attribution, reported EBITDA versus adjusted/margin amounts,
units, periods, entity boundaries, Decimal arithmetic and provenance. Browser checks
cover both themes/viewports, basis changes, missing data, formulas, separate input
sources, original page previews and contextual questions.

```powershell
.venv\Scripts\python -m pytest tests/test_financial_results.py tests/test_numerical_metrics.py
# Opt-in stored-source/integration checks; may write caches/artifacts:
.venv\Scripts\python scripts/verify_financial_results.py
.venv\Scripts\python scripts/verify_numerical_research.py
.venv\Scripts\python scripts/verify_portfolio_financials.py
```

The portfolio verifier can acquire sources/use extraction quota; `--refresh` checks
original files and `--publish` publishes reviewed outputs. Numerical verification
reuses stored primary documents without generation/embedding calls. See
[testing](EVALUATION.md) before running integration work.

Difficult layouts, missing units/dates/bases, scans, conflicting definitions and
unsupported sector calculations remain unavailable. Full OCR, live valuations,
historical entity recasts and broad fiscal-label EBITDA inference are outside scope.
