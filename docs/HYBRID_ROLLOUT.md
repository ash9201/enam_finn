# Production hybrid rollout ? 2 November 2026

The owner applied `0011_production_hybrid_scope.sql` and enabled the active Singapore
Render API with `FINN_ENABLE_SEMANTIC_SEARCH=true` and
`GEMINI_EMBEDDING_MODEL=gemini-embedding-001`. The embedding API was verified live.
The publishable key cannot read the search-document view or invoke the inventory RPC.
A stale-body batch write was rejected without changing a chunk.

## Implementation

- One private scope for both retrieval branches and incremental backfill: current
  annual reports/transcripts plus current quarterly-result PDFs. Original source,
  page/chunk identities and superseded versions are preserved.
- Complete-company eligibility is retained. Incomplete companies use keyword
  retrieval and report actual saved progress/worker state. No partial prefix of an
  annual report is represented as a complete semantic index.
- RRF settings remain 30 candidates per branch, 10 results, k=10, semantic weight 2,
  two chunks per page and adaptive document diversity. Keyword retrieval remains
  PostgreSQL full-text search; metadata filters match the semantic branch.
- 768-dimensional L2-normalized Gemini vectors use RETRIEVAL_DOCUMENT and
  RETRIEVAL_QUERY, with separate task/model/version/hash cache keys.
- Atomic writes persist up to 32 vectors in one RPC; conditional body hashes protect
  against stale writes. Interrupted storage retries reuse the persistent vector cache.
- Budget preflight avoids repeatedly spending count-token calls after exhaustion.
  Small batches use the remaining allowance. Daily bulk accounting is now **850**,
  foreground query accounting **900**, below the confirmed 1,000/day provider limit.
  This retains 50 reserved foreground units and 100 units of provider safety margin;
  token-count calls are conservatively counted too. RPM80 / TPM27000 stay unchanged.
- Daily maintenance prioritizes nearly complete watchlist corpora, then other
  companies already collected on demand. Quarterly-only companies are included;
  it never walks or embeds the whole NSE directory. Existing scheduling is retained.
- A new document-scope fingerprint invalidates stale keyword answers without
  invalidating them after every partial embedding batch. Empty semantic results do
  not get labelled hybrid. Numeric statement claims remain gated through the
  validated financial-results workflow; embeddings do not validate financial cells.

Exact cosine similarity is retained **after company/document filtering**, using
existing chunk/document indexes and a new source-version lookup index. At these
per-company sizes, a global approximate vector index would add storage and risk
losing company matches through post-filtering; no ANN tuning or new service was added.
The inventory RPC reports database size so future index growth can be monitored.

## Verification and current coverage

Measured 2026-11-01T23:11:40.292233+00:00 (2 November IST): **2,488 / 18,698
chunks**, **14 / 70 fully indexed current documents**, across
**20 companies with collected documents**. Three companies have complete eligible
indexes; 17 remain keyword-only. The database measures 160.4 MB.
Counts describe current search scope, not all retained extraction versions.

| Company | Indexed / current chunks | Complete / current documents |
| --- | ---: | ---: |
| CCL | 707 / 707 | 4 / 4 |
| GOKEX | 711 / 711 | 3 / 3 |
| V2RETAIL | 25 / 25 | 1 / 1 |
| INFY | 877 / 1,160 | 2 / 4 |
| POLYCAB | 168 / 2,628 | 4 / 8 |

- Deployed application revision `1154a2d` and its parent `c86fcf9` passed CI,
  including the full unit suite, frontend build/model checks and secret scan.
  Focused retrieval, evidence, financial and directory checks also passed locally.
  No unrelated source ingestion or LLM benchmark sweep was run.
- A new production CCL question returned a cited hybrid answer. Existing CCL/GOKEX
  indexes passed live retrieval, query-vector reuse, answer caching, incomplete-index
  fallback, simulated provider/vector-RPC failures and flag-off rollback checks.
- Previously uncollected **V2RETAIL**, outside the watchlist, was resolved from the
  verified directory, discovered and ingested through the generic quarterly workflow,
  and indexed automatically on Render: one primary filing / 25 chunks. Its evidence
  follow-up returned three cited hybrid claims about group entities, business segment
  and review limitations. All three citations matched original PDF pages 9, 12 and 10.
  The first financial result retained nine verified Revenue/PBT/PAT cells; EBITDA
  remained missing. This is a financial-only collected corpus, not a preloaded annual
  report/transcript corpus; requesting those documents extends its index normally.
- Repeating its financial request completed from cache in 2.18 seconds, with unchanged
  document versions and zero embedding reservations. Repeating its hybrid follow-up
  also reused the answer with zero new embedding reservations.
- **COLPAL** resolved correctly but its public index exposed no primary quarterly
  links. The job reported that specific failure; no substitute data was returned.
- Publishable access to the private view/inventory was denied with permission code
  42501 while ordinary public company reads succeeded. A mismatched body-hash batch
  wrote zero rows. CCL/GOKEX source passages/pages and new V2RETAIL pages were checked.
- Current frozen-setting relevance/latency results are in [the evaluation report](HYBRID_EVALUATION.md):
  matched keyword Recall@5/10 **0.5714 / 0.8571** versus hybrid **0.9286 / 0.9286**;
  warm retrieval medians **688 / 1,881 ms** (27 samples per method, no provider calls).
  These are small reference-page checks, not a general answer-quality claim.

## Remaining operational limits and owner actions

**No further migration or Render environment change is required for this rollout.**
Keep the server-side Gemini key, model and enabled flag above. No frontend/GitHub
variable changes are needed; the existing Actions secret/enable variable are configured.
The standard-runner daily backfill remains at 08:45 UTC / 14:15 IST, after Pacific
midnight in both DST seasons. Its latest scheduled run succeeded; the updated
maintenance entry point was also run against production and resumed INFY to 877
chunks before stopping explicitly at the shared daily budget.

The remaining 16,210 chunks cannot fit in one confirmed free daily allowance.
At roughly 800 completed vectors/day after reservation overhead, full current coverage
needs around 20 further daily allowances, subject to research usage, retries and new
filings. Keyword research remains available meanwhile. New companies acquire only
requested documents and join this same resumable pipeline; a large new annual corpus
can therefore remain keyword-only across multiple resets. Missing/scanned/inaccessible
sources retain existing coverage limits. No OCR, model-provider, quota tier or billing
upgrade was introduced.

For rollback, set only `FINN_ENABLE_SEMANTIC_SEARCH=false` on the active API and
redeploy. Existing keyword retrieval/citations continue; vectors remain stored.
Private detailed diagnostics stay in ignored `artifacts/hybrid-rollout` and
`artifacts/retrieval`. Public evaluation summaries contain no credentials.

---

## Historical rollout record (31 October; counts and quota budget superseded above)

# Production hybrid rollout — 31 October 2026

**Later research-experience update:** migrations 0009 and a daily indexing-maintenance
workflow now add private attempt/lease state and truthful status. The owner configured
Actions secret GEMINI_API_KEY and variable FINN_ENABLE_SEMANTIC_BACKFILL=true. The
Render flag/model below remain unchanged. Indexing is eligible after the documented
reset and resumes via requests or the daily 14:15 IST free-runner workflow. Existing
portfolio scheduling and inactive Supabase fallback are unchanged. New LT/APLAPOLLO/
other generic corpora mean the historical aggregate denominator below is no longer
the current total; the four prepared-company counts were rechecked unchanged. See
[current behaviour, quotas and checks](RESEARCH_IMPROVEMENTS.md).

**Enabled and verified on the active Singapore API**
(`https://finn-api-source-test.onrender.com`). The owner deployed the environment
changes; the live configuration reports semantic search enabled. No application
retrieval changes, evaluation retuning, new model, service or migration were needed.

## Render configuration

In the **Singapore API web service**, Environment:

```dotenv
FINN_ENABLE_SEMANTIC_SEARCH=true
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```

Keep the existing server-side `GEMINI_API_KEY` and Supabase credentials. Save and
deploy the API after an environment edit. There are **no frontend/Vite or GitHub
Actions environment changes**, new secrets or dimensions variables. Dimensions remain
768, with `gemini-retrieval-body-v1` input version and task-specific document/query
vectors. Migrations 0006/0007 are already applied and verified; 0008 does not change
the hybrid index policy.

`render.yaml` now declares the rollout flag as operator-managed (`sync: false`),
instead of pinning it to `false`. Existing Blueprint updates leave such values alone,
preserving the Dashboard's rollout or rollback choice. New Blueprint installations
must supply it during setup; the application still defaults off when unset.
[Render Blueprint reference](https://render.com/docs/blueprint-spec).

The flag means **hybrid when this company's active index is complete**. It does not
force semantic retrieval over partially embedded documents. Rollback is the same API
variable set to `false`, followed by a deploy. Stored vectors survive rollback.

## Current active-manifest coverage

| Company | Ready / total chunks | New research mode |
| --- | ---: | --- |
| CCL | 694 / 694 | Hybrid |
| GOKEX | 711 / 711 | Hybrid |
| INFY | 288 / 1,125 | Keyword; `index_incomplete` |
| POLYCAB | 0 / 2,584 | Keyword; `index_incomplete` |
| BHARTIARTL | 0 / 1,319 | Keyword |
| HINDUNILVR | 0 / 1,079 | Keyword |
| SUNPHARMA | 0 / 864 | Keyword |
| TCS | 0 / 897 | Keyword |

Total: **1,693 / 9,273**, with private index security checks passing. CCL/INFY each
have one annual report/two calls; POLYCAB's expanded history is two reports/four calls.
Its larger denominator is genuine added source coverage. Company indexes cover the
active annual-report/transcript manifest, not every archived version or quarterly
financial-table PDF. Validated quarterly calculations keep their separate source-cell
pipeline; narrative follow-ups can combine hybrid company research with financial
keyword evidence.

Published saved answers retain their original generation dates and retrieval modes.
The fast frontend can therefore initially show a prepared **keyword** answer. Submit
a question to exercise the enabled API; it selects the current company profile and
uses a separate hybrid answer-cache identity. Existing historical answers are not
relabeled to advertise the rollout.

## Backfills and the actual quota boundary

Bounded INFY/POLYCAB resume attempts both ended **pending / daily_budget**, with zero
new vectors and zero provider calls. An initial transient Supabase connection failure
was retried with a fresh connection. A paginated scan of all 1,693 document-cache
entries found **no cached vectors available to restore** for their missing chunks.
No partial index was marked complete and no source manifest was shortened.

The shared ledger was already at its **800-unit daily bulk ceiling** before this
rollout check. Verification consumed six foreground units, leaving the ledger at
806 and about **94 units** below the separate 900-unit query ceiling at that check.
These are FINN reservations, not a claim about the project's entire provider usage.
Batch texts and token-count reservations are included. The owner's stated provider
limits remain 100 RPM / 1,000 RPD / 30k TPM; FINN's conservative budgets stay unchanged.

The next Pacific-day reset is **1 November 2026, 12:30 p.m. IST**. Google documents
midnight Pacific resets; the IST conversion uses `America/Los_Angeles` so DST is
accounted for. [Google rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).
No service is left waiting until the reset.

Prioritize INFY, then POLYCAB after the reset:

```powershell
.\.venv\Scripts\python.exe -m finn.embeddings --symbol INFY --max-batches 100
.\.venv\Scripts\python.exe -m finn.embeddings --symbol INFY --status
.\.venv\Scripts\python.exe -m finn.embeddings --symbol POLYCAB --max-batches 100
.\.venv\Scripts\python.exe -m finn.embeddings --symbol POLYCAB --status
```

The explicit CLI works even if the local rollout flag is off. It resumes missing
text and stops at daily limits; it never redownloads/reduces documents or enables
paid quota. INFY still needs 837 vectors and POLYCAB 2,584, plus accounting overhead:
neither should be promised complete in a single 800-unit day. Avoid `ALL` when
prioritising these companies, since alphabetical unprepared corpora can consume
the allowance first.

With production enabled, normal company ingestion/reuse also schedules bounded
background backfills. This requires a request; there is no midnight scheduler.
Free Render sleep/restarts can interrupt a worker, so the CLI is preferable for a
deliberate bulk pass. No additional backfill is required before using the two ready
companies today. Incomplete companies remain fully usable through keyword research.

## Verification results

- **CCL and GOKEX:** fresh query embeddings, actual PostgreSQL FTS + pgvector + RRF,
  original source citations, three validated claims each, repeated query-vector hits
  with zero provider calls, and repeated answer-cache hits.
- **INFY and POLYCAB:** actual keyword results with `index_incomplete` and zero query
  embedding calls. A complete INFY research answer returned two cited claims.
- **Controlled failures:** injected embedding-provider and semantic-RPC failures each
  retained six real keyword passages. These are deliberate local faults, not claimed
  production outages. Targeted tests also cover avoiding hybrid-key cache pollution.
- **Rollback:** flag off produced keyword retrieval without embedding calls.
- **Live production:** the deployed flag is true; a new CCL question generated a fresh
  hybrid answer with three claims. GOKEX reused its hybrid answer; INFY reused its
  keyword answer with the explicit incomplete-index reason. Production metadata
  confirms `gemini-embedding-001`, k=10 and semantic weight=2.
- **Checks:** all 25 targeted hybrid tests and the live minute/day quota-accounting
  audit pass. No unrelated UI or full local suite was repeated for this configuration
  rollout. Existing quote/metric/financial validation remains active.

Settings are unchanged: **30 candidates per branch, RRF k=10, semantic weight=2,
10 selected passages, page cap 2, adaptive document cap starting at 4**. The two fresh
operator retrievals took approximately 6.1s and 3.8s including uncached provider
work/network round trips. These are smoke-check observations, not a new latency
benchmark or reason to retune the frozen [evaluation](HYBRID_EVALUATION.md).

Reproduce the scoped checks with existing local credentials:

```powershell
.\.venv\Scripts\python.exe scripts/verify_hybrid_rollout.py
```

This enables the flag only in its process, writes private test answers and ignored
artifacts, and can use Gemini query/generation allowance if uncached. Automatic bulk
backfill is suppressed only inside this verifier; explicit operator backfill remains
separate. It never edits `.env.local`, Render or the published prepared answers.
Results and production-response artifacts are in `artifacts/hybrid-rollout/`.
