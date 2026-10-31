# Research experience improvements - 31 October 2026

This release keeps React/FastAPI/Supabase and the existing evidence, retrieval and
job contracts. It improves answer substance, acquisition/caching, financial recovery,
management comparisons and truthful indexing status. No dependencies or paid services
were added. The previous main revision is preserved at
`release/pre-research-improvements-20261031` (`0653dcb`).

## What changed and why

- The old answer schema constrained explanations to short, single-source claims.
  Answers now support headings, up to eight substantive points and multiple exact
  supporting passages per point. Broad questions request connected explanations;
  narrow questions and thin source coverage remain shorter. Missing support withholds
  the whole point. Numbers, metric names and ambiguous financial-table figures retain
  their validation gates. Nonfinancial dates/headcounts are no longer indiscriminately
  rejected merely because they appear in an annual report.
- Prepared answers have a read-only, synchronous cache path before the acquisition
  queue. New questions over prepared documents have a separate bounded answer worker.
  Document acquisition remains serial. A completed cache response includes the result,
  avoiding an unnecessary initial polling delay. Ordinary questions reuse existing
  dated documents; explicit refresh checks originals. Clicking Investigate on a filing
  no longer forces an unrelated full annual-report/transcript refresh.
- Extraction progress writes are throttled, and each saved primary document is exposed
  during preparation and after a subsequent failure. Retrying can reuse those documents.
  Large annual reports use native PDFium text earlier, with a 1,600-page bound instead
  of rejecting LT's report at 700 pages. An unavailable individual source can produce
  explicitly partial coverage; a failed explicit refresh never masquerades as success.
- Jobs record queue/processing time and discovery, download, PDF, database/cache,
  retrieval, embedding, model and validation spans. Nested spans overlap and must not
  be summed. Model generation has a 45-second timeout without a second timeout retry.
  A transient interrupted database read or conflict-key upsert retries once; quota RPCs,
  ordinary inserts and model calls are not replayed by this storage retry.
- Source details are progressive disclosure rather than prominent technical badges.
  Multi-source synthesis, original statement images, source switching, visible context,
  question progress and the investigation trail retain the existing visual system.

## Observed latency and answer substance

These are small local live-source observations, not a statistically controlled load
benchmark. Network/provider latency and source/cache state differ. Source dates and
original generation dates stay intact. No cold-start speedup is claimed.

| Case | Before | After | Interpretation |
| --- | --- | --- | --- |
| CCL prepared broad question | Previous saved answer: 3 points, 46 words; fresh job 49.9 s | 3 points, 127 words; 11.40 s | Same prepared-company workflow, richer supported explanations. |
| HDFCBANK risk question | Historical fresh job 164.5 s; 3 points, 58 words | New generation over prepared sources: 10.39 s; 4 points, 102 words | Historical comparison, not a paired latency experiment. |
| APLAPOLLO first acquisition vs reuse | First acquisition 43.55 s, including 38.43 s corpus preparation; 1 point, 12 words | Prepared new-prompt answer 8.89 s; 2 points, 67 words | Demonstrates warm-source reuse, not a 5x like-for-like speedup. |
| LT first acquisition | Failed the 700-page bound | 62.73 s; 6 points, 274 words | Generic acquisition now works; new-company preparation is still substantial. |
| Cached API answers | Old controlled HDFCBANK pipeline cache path 4.04 s, plus client polling | CCL hybrid HTTP response 2.76 s; INFY keyword 1.90 s, both immediately completed | Different examples; zero generation and no acquisition on the new path. |

LT's first run spent 54.58 s in inclusive corpus preparation, including 15.21 s PDF
processing, 4.62 s downloading and 0.47 s discovery. The remainder includes database
persistence and metadata work; those spans are now recorded for future jobs. Model
generation was 5.22 s.
The prepared CCL run used 3.21 s retrieval and 4.39 s generation. Therefore replacing
the model alone would not address acquisition or queue delays.

The implementer reviewed the INFY/POLYCAB/CCL overview claims against their quoted
primary passages. They contain respectively 3/4/2 points and 125/113/68 words. CCL's
narrow default question remains shorter than its broader business-model question;
unsupported customer/channel details are not padding. This is a small implementer
review, not an independent human evaluation. The previous retrieval study and its
Recall@5/10 results remain unchanged; RRF k=10 and semantic weight=2 stay frozen.

## Quarterly coverage actually exercised

All 15 companies ran through generic discovery, original PDF acquisition, validated
extraction and deterministic comparisons. This is **15 with some usable figures**, not
15 fully complete results sets. The baseline database had usable saved financial
outputs for POLYCAB/CCL; two portfolio companies had no prior financial attempt. It
would be misleading to call that a fresh 2/15 baseline benchmark.

The parser now handles integer and fractional layouts, ordinal dates, split quarter/
half-year headers and 195-page filings. It selects statement pages before table
extraction. Native unambiguous cells are preserved. Bounded recovery uses two separate
reads of differently rendered original page images, agreeing on each accepted cell
and metadata. These are two reads of the **same model**, not independent models or
independent financial audits. Some native cells use image-verified headers only;
these are labelled separately. No decimal placement, EBITDA formula or YTD subtraction
is guessed. Versioned document IDs preserve older citations.

| Company | Latest sourced quarter end | Consolidated coverage | Remaining limits |
| --- | --- | --- | --- |
| APLAPOLLO | 2026-09-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 3 quarters | Both bases available. |
| BHARTIARTL | 2026-06-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 3 quarters | Both bases available. |
| CCL | 2026-09-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 3 quarters | Both bases available. |
| HDFCBANK | 2026-09-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 3 quarters | Revenue label explicitly identifies bank total income. |
| INFY | 2026-09-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 3 quarters | Both bases available. |
| ITC | 2026-06-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 3 quarters | Both bases available. |
| KPITTECH | 2026-09-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 3 quarters | Both bases available. |
| LT | 2026-09-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 3 quarters | Both bases available. |
| M&M | 2026-06-30 | Revenue: 2 quarters, PBT: 2 quarters, PAT: 0 quarters | No QoQ/PAT; standalone unverified. |
| NTPC | 2026-09-30 | Revenue: 3 quarters, PBT: 0 quarters, PAT: 3 quarters | Consolidated PBT withheld; standalone has all three metrics. |
| POLYCAB | 2026-09-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 3 quarters | Both bases available. |
| RELIANCE | 2026-09-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 0 quarters | PAT and standalone remain unverified. |
| SUNPHARMA | 2026-09-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 3 quarters | Also current consolidated EBITDA; prior EBITDA amounts remain unverified. |
| TATASTEEL | 2026-06-30 | Revenue: 3 quarters, PBT: 3 quarters, PAT: 3 quarters | Both bases available. |
| TITAN | 2026-06-30 | Revenue: 0 quarters, PBT: 3 quarters, PAT: 3 quarters | No explicit eligible total Revenue; components are not summed. |

CCL Revenue/PBT cells previously damaged in native text are recovered. Its group PAT
includes the separately reported associate share. HDFCBANK's group PAT is before
noncontrolling-interest attribution, and its Revenue display is explicitly bank total
income. Original CCL, POLYCAB, HDFCBANK and SUNPHARMA pages were spot-checked, not every
cell of all 15 independently audited. INFY has additional corroborating source cells;
the view still selects one compatible figure for each period/basis/metric.

SUNPHARMA's original press release (PDF p.17) explicitly reports consolidated quarterly
EBITDA INR 47,439 million for 30 September 2026. Native prose and a separate image
read must agree. Earlier EBITDA amounts using only fiscal abbreviations are not
converted to dates or inferred. Segment EBITDA, adjusted EBITDA and margins do not
substitute for whole-company amounts. Other filings may contain relevant data in
formats not yet supported; a dash means unverified/unavailable, not absent everywhere.

## Narrative versus evidence

The former KPIT pair was an empty FY27 fragment and an analyst question. Selection
now operates on complete verified management speech, using a roster/role from the
original introduction, actual call dates and immutable page citations. An analyst's
question cannot become management evidence. A second source-grounded pass sees only
the chosen quotes, so unrelated candidate-page details cannot leak into the assessment.
If summaries fail validation, complete verified quotations remain visible instead of
fabricating a conclusion. No meaningful pair produces an explanatory empty state and
useful investigation suggestions.

Reviewed examples:

- CCL: July 28 -> October 16 management guidance on volume and EBITDA, with later robust
  orders and reaffirmation. The verdict is **Outlook reaffirmed**, not target delivered.
- KPIT: May 7 -> July 29 (the index says August). The earlier FY27 EBITDA range/investment
  statement is paired with an actual quarterly management account. The earlier quote
  does not explicitly print a unit for its range. Qualitative summaries and an explicit
  **not yet assessable** limitation replace a fabricated percentage comparison. One
  quarter does not settle a full-year target.

Each side and synthesis is interactive. Page-scope IDs bind to the stored page hash;
server resolution verifies source/claim membership before follow-ups. This does not
add retrieval chunks or invalidate existing complete semantic indexes. A compatible
reported metric can link its existing financial evidence as context, using the original
financial answer's ID; it never supplies an automatic delivery verdict. No such
optional context is forced into these two examples where eligible EBITDA is missing.

## Indexing and deployment operations

`0009_research_experience.sql` was applied by the owner with RLS kept enabled. The new
embedding-job table/claim function are private; live public-key probes returned 401
for both. Per-company leases prevent duplicate background workers. Running, paused
allowance, pending/no worker, failed, unavailable, disabled and ready states are distinct.
Expired leases do not remain 'running'. Source details show the search mode actually
used for the saved answer separately from a timestamped current index check. Reopening
or refreshing status rechecks it without regenerating an answer.

At verification CCL 694/694 and GOKEX 711/711 remain hybrid-ready; INFY 288/1,125 and
POLYCAB 0/2,584 remain incomplete. Bounded resumes recorded a genuine daily-budget pause
with zero provider calls. The next eligible reset is 1 November 12:30 IST; eligibility
is not a guarantee that another project user has not consumed provider allowance.

The owner added Actions secret `GEMINI_API_KEY` and variable
`FINN_ENABLE_SEMANTIC_BACKFILL=true`. New `Resume document indexing` uses standard free
`ubuntu-latest` runners daily at 14:15 IST, existing Supabase secrets and the existing
embedding budgets. It prioritises INFY then POLYCAB, skips completed indexes, resumes
saved progress and stops at the daily ceiling. Runs may be delayed by GitHub. It is
separate from the unchanged portfolio schedule; Supabase fallback schedules stay off.
No Render variables change. The existing semantic flag remains the rollout/rollback
switch. Disable the Actions variable to stop scheduled backfills independently.

## Verification and reproduction

Use targeted tests during development and a full regression at completion. Local
commands and results are recorded in ACCEPTANCE.md. Browser verification covers one
390x844 / 1440x1000 x Light/Dark matrix, readable figures, source switching, original
page previews, active/removable context, a real cross-document follow-up, partial
financial data, paused indexing, contrast and overflow. It uses real private pipeline
outputs as review fixtures before public publication; API evidence/images/jobs/status
remain live. No market data was fabricated. The live follow-up runs once across the
matrix rather than invoking the model per theme. Browser artifacts and raw diagnostics
are ignored, without credentials.

```powershell
.\.venv\Scripts\python.exe scripts/audit_research_experience.py --sources
.\.venv\Scripts\python.exe scripts/verify_portfolio_financials.py
.\.venv\Scripts\python.exe scripts/verify_financial_results.py
.\.venv\Scripts\python.exe -m finn.embedding_maintenance --max-batches 1
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/npm.py run build
.\.venv\Scripts\python.exe scripts/check_frontend_secrets.py
```

`--refresh` explicitly checks current original financial files. `--publish` explicitly
publishes reviewed financial outputs; ordinary audits are private. For the consolidated
browser check, set FINN_EXPERIENCE_API_URL to a current local API and
FINN_USE_REVIEW_SNAPSHOTS=true only when using the ignored review artifacts. The default
browser path reads genuinely public snapshots and does not substitute failed responses.

Remaining work includes broader independently reviewed accounting coverage, fiscal-label
EBITDA tables, difficult M&M/Reliance/Titan layouts, and a larger answer-quality study.
Free API cold starts, source restrictions and provider quotas remain observable limits.
