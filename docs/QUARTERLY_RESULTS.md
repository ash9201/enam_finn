# Quarterly financial results

FINN can acquire original quarterly filings, validate native statement cells, and
compare Revenue, explicitly reported EBITDA, PBT and PAT. The **Quarterly results**
action is in Research; results announcement cards offer **Compare quarters**. Prepared
POLYCAB and CCL snapshots load directly from the existing public result cache.
Refresh sources explicitly to check for a newer filing; saved results keep their
reporting periods and original check/generation dates. This is on-demand acquisition,
not another background schedule.

## Actual source validation — 31 October 2026

The rendered primary consolidated statements were inspected during implementation.
The following are dated acceptance cases, not a claim of independently audited or
universal financial coverage.

| Case | Original statement | Actual behaviour |
| --- | --- | --- |
| POLYCAB, quarter ended 30 September 2026 | [BSE filing](https://www.bseindia.com/xml-data/corpfiling/AttachHis/4ac93ea0-d4d1-4b85-8849-14a19e0dcceb.pdf), consolidated PDF p. 4; standalone p. 10; INR million | Revenue 98,989.01 / 82,097.32 / 64,772.11 for latest / prior / year-ago. QoQ +16,891.69 (+20.58%); YoY +34,216.90 (+52.83%). PBT and group PAT also compare successfully. |
| CCL, same quarter | [BSE filing](https://www.bseindia.com/xml-data/corpfiling/AttachHis/ac6a2647-0f4d-4ccc-8659-4101c055586a.pdf), consolidated PDF p. 7; standalone p. 3; INR lakh | Three consolidated cells withheld: current/prior Revenue and prior PBT. Native text loses decimals or has malformed grouping. PAT 13,010.97 / 11,688.05 / 10,085.75 supports QoQ +11.32%, YoY +29.00%. PBT YoY works; PBT QoQ remains unavailable. |
| EBITDA in both filings | No eligible explicit unadjusted EBITDA row | Unavailable, not zero. No substitution of operating profit or an invented PBT/finance-cost/depreciation definition. |
| Financial evidence follow-up | Published POLYCAB Revenue cell → company transcripts | Selected company, quarter, basis and claim are preserved. Narrative evidence comes from other documents. Earlier-period commentary is labelled historical context and is not proof of the selected quarter's drivers. A separate broad product-mix request had all candidate claims withheld by existing validation; no answer was fabricated. |

Both bases are available. POLYCAB's standalone year-ago column is marked **Restated**
from its actual header. Consolidated PAT uses total group profit before shareholder/
non-controlling-interest attribution; CCL's separately reported associate share is
included. The precise reported row is visible in evidence. Standalone PAT is the
company's reported profit. No cross-company comparisons are offered.

## Acquisition and extraction

1. Resolve any requested NSE ticker through the existing live company directory.
2. Use only the quarterly **source links** on its Screener page. No Screener financial
   table values or generated commentary enter the evidence.
3. Resolve the source locator to the original BSE/NSE/company PDF through the existing
   safe PDF downloader. Preserve URL, content hash, stored PDF and fetch date.
4. Group native PDF words by geometry and retain the exact reading text, row cells,
   horizontal columns and statement header. Quarter headings are distinguished from
   half-year/year headings, including wrapped/merged headings. Dates must be explicit
   month ends, unambiguous and not in the future.
5. Verify the company name in the statement header, accounting basis, currency and unit.
   The primary statement quarter must agree with its discovery locator; the locator
   never supplies an accepted figure's period.
6. Unambiguous eligible rows map deterministically. If multiple permitted candidates
   remain, bounded Gemini schema output can select row indices. It cannot supply
   figures, dates, units or substitute another metric. Every selected cell still passes
   deterministic validation.

The latest filing commonly contains all three required quarter columns. If required
periods are absent, acquire up to two additional primary quarterly filings through
the same directory/index flow. Missing cells within an otherwise available period
are not silently repaired from an older/restated version. No YTD subtraction creates
an unreported quarter. New companies use these same functions without a ticker list.

Raw financial PDFs/pages/chunks remain private in the existing document store.
Accepted facts, raw cells, headers and figure citations live in the existing versioned
research-result JSON. Published prepared outputs use the existing public read policy;
custom follow-ups stay private. Parser/mapping versions and result-schema versions
participate in caching. Content-identical documents reuse extraction and row mapping;
repeated analyses within 24 hours reuse the result without a model call. Explicit
refresh rereads the index/files and preserves errors rather than presenting stale data
as a successful refresh.

## Comparison policy

- Revenue means **revenue from operations**, not total income including other income.
- EBITDA must be explicitly reported, unadjusted and not a margin. Deriving it would
  require agreeing on treatment of other income, exceptional items and other adjustments.
- Use explicit quarter cells, the immediately previous quarter and the same quarter
  one year earlier. Fiscal-year labels are not guessed.
- Compare the same currency, accounting basis, period kind and metric definition.
  Known lakh/crore/million/billion scales normalize with `Decimal`; currencies never
  convert. Incompatible currency figures are not displayed under another currency.
- Prefer comparative figures in the newest statement, including its restatements.
  Conflicting same-filing cells are withheld. Detected regrouping/scope markers block
  comparisons between separate filings pending review.
- Absolute change = current − base. Percent = change ÷ base × 100. Calculations use
  unrounded values and `ROUND_HALF_UP`; the UI shows two decimals. Zero/negative bases
  retain valid absolute changes but no misleading percentage.

The results view separates figures from changes. Every figure opens the existing
evidence panel with the exact source row plus selected column, raw amount, quarter,
basis, unit, statement header, PDF page and original link. Changes open their formula
and links to both underlying figures. The existing contextual question flow can search
reports, transcripts and selected results filings. A numerical anchor also triggers
question-only transcript retrieval so its numbers do not dominate a qualitative inquiry.

Financial pages use a small private keyword RPC alongside the existing research
retrieval/RRF pipeline; they do not expand the annual-report/transcript manifest or
trigger new embedding backfills. The semantic rollout flag remains unchanged.
Ordinary narrative generation retains its existing quote/number/table guards and
cannot invent new financial comparisons. Chronological investigations still need
independently verified document dates; a quarter end is not a publication date.

## Limits and verification

Native English statements with reliable alignment and consistent decimal formats are
supported, bounded to 60 PDF pages and at most three filings per acquisition. Scans,
damaged text, ambiguous headers/units/bases and unsupported layouts fail or expose
missing cells. No OCR recovery or guessed decimal placement is enabled. Banks and
insurers do not get industrial revenue/EBITDA inferred from total income; specialized
NII/NIM, underwriting and insurance metrics are outside this feature. Acquisition,
company-name matching and table layout are deliberately conservative; not every NSE
company is supported.

Keyword retrieval can return older management commentary. Timing labels and source
dates expose that limitation; a historical demand statement does not establish a
current-quarter cause. Quote existence and native-cell validation do not prove semantic
entailment or every possible accounting comparability issue. The bounded two-company
review is retained as acceptance evidence.

- 25 targeted financial tests cover malformed/negative/Indian-format numbers, merged
  and wrapped quarter/YTD headings, exact periods, source-row substitution, decimal
  damage, unit conversion, unvalidated figures, incompatible definitions/bases,
  nonpositive denominators and avoiding unnecessary LLM calls.
- Full backend regression: **154 passed**. No unrelated backend suite was repeated per theme.
- Production TypeScript/Vite build and privileged-credential asset scan pass.
- Affected results/evidence/calculation views pass Light/Dark checks at 390×844 and
  1440×1000, including contrast and overflow. The live follow-up runs once, not once
  per theme. Real CCL coverage and negative standalone changes are also checked.
- The server-only financial-search RPC accepts privileged calls; anonymous execution
  is denied (401). Existing private-table RLS remains enabled.

Apply `supabase/migrations/0008_quarterly_results.sql` once with RLS enabled (already
applied to this project). Its initial sort-reference error was corrected before the
successful run. It extends the document-kind constraint and adds a restricted search
function; it creates no tables or public grants.

```powershell
.\.venv\Scripts\python -m pytest tests/test_financial_results.py -q
.\.venv\Scripts\python scripts/verify_financial_results.py --followup
# --publish is optional and publishes only the verified prepared financial snapshots.
python scripts/npm.py run build
python scripts/npm.py run test:financial
```

The dated real-source check stops if the quarter or expected source cells change;
review the new original filing before updating it. Browser tests use the real public
snapshots. For a local API, set `FINN_FINANCIAL_API_URL=http://127.0.0.1:8001`; requests
are forwarded there without fabricated responses. Without it the deployed API is
accessed directly. Real follow-up results and two useful UI screenshots are ignored
local artifacts under `artifacts/financial-results/` and `artifacts/financial-browser/`.
