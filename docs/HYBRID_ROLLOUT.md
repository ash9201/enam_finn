# Production hybrid rollout — 31 October 2026

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
