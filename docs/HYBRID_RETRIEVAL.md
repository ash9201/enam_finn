# Hybrid retrieval

FINN uses PostgreSQL full-text search and pgvector cosine similarity inside Supabase.
Gemini embeds text; Python combines independently ranked candidates using Reciprocal
Rank Fusion (RRF). There is no separate vector database, embedding SDK or RAG framework.
See [evaluation](HYBRID_EVALUATION.md) for the evidence behind the settings.

## Search scope and ranking

Both branches use the private `finn_search_documents` scope: active annual-report and
transcript manifest documents plus the latest ready extraction per quarterly source URL.
Superseded versions remain available for existing citations, but are not mixed into
current search. Filters include company, document kind/IDs, verified publication-date
bounds, reporting period and JSON metadata. Unknown dates cannot satisfy date filters.
Discovery labels remain separate from verified dates.

Cosine search is exact after company/document filtering. These per-company corpora
do not yet justify a global approximate index and its possible post-filter recall loss.
Measure storage, latency and recall before adding HNSW or changing chunking.

| Setting | Value |
| --- | --- |
| Candidates per retrieval branch | 30 |
| Final evidence budget | 10 passages |
| RRF constant | 10 |
| Keyword / semantic weights | 1 / 2 |
| Page diversity | At most two passages per page |
| Document diversity | Adaptive cap; a single eligible document can fill the budget |

For each candidate, fusion sums `weight / (k + rank)` across branches. Raw keyword
and cosine scores are not directly comparable. Shared diversity selection follows
fusion. Investor-aspect supplements and contextual follow-ups reuse the same company
and source restrictions; the separate management-comparison selector retains its
conservative speaker/chronology rules rather than claiming to be hybrid retrieval.

Returned passages retain original chunk bodies, PDF pages and server-owned source URLs.
Existing quote, named-metric and unvalidated-financial-table guards still apply after
generation. Embeddings do not validate a figure or make uncertain metadata authoritative.
Approved financial comparisons use the [financial pipeline](QUARTERLY_RESULTS.md).

## Embedding lifecycle

- Model: `gemini-embedding-001`, 768 dimensions, L2-normalized in Python.
  Documents use `RETRIEVAL_DOCUMENT`; questions use `RETRIEVAL_QUERY`.
  Invalid dimensions, non-finite/zero vectors and incomplete batches are rejected.
- Cache identity includes model, dimensions, task, input version and exact-input SHA-256.
  Query text is not stored in this vector cache. Vectors/cache/quota tables are private
  under RLS, with no public grants.
- Database-generated body hashes guard writes and reads. Conditional atomic writes
  accept up to 32 vectors; changed text cannot receive a stale result. Retrieval never
  mixes incompatible model/version/dimension/hash combinations.
- Provider batches start at 24 inputs, count tokens, shrink when needed and never silently
  truncate oversized input. Completed vectors are cached before chunk updates, so a
  storage interruption can resume without buying the same embeddings again.
- Generic document activation/reuse and quarterly research schedule missing embeddings.
  Per-company leases prevent duplicate workers. Expired leases do not remain running.
  Checkpoints survive restarts; another request, maintenance job or CLI can resume them.

Shared reservations count individual texts inside a batch, not just HTTP envelopes.
Application ceilings are 80 input units/minute, 27,000 reserved tokens/minute, 850 daily
bulk units and 900 daily foreground units. The configured project allowance is
100 RPM / 30,000 TPM / 1,000 daily inputs; other applications can consume it too.
Token-count calls conservatively reserve units. Daily accounting follows the provider's
Pacific date. Minute waits are bounded; daily exhaustion stops with resumable pending
status rather than repeatedly retrying. Cached query vectors can survive provider cooldowns.

Daily GitHub maintenance prioritizes nearly complete watchlist corpora, then other
already collected companies, including quarterly-only companies. It does not crawl the
NSE universe. A sleeping API may interrupt a long backfill; independent maintenance
and persistent checkpoints avoid depending on an always-awake web process.

```powershell
.venv\Scripts\python -m finn.embeddings --symbol CCL --status
.venv\Scripts\python -m finn.embeddings --symbol CCL --max-batches 100
.venv\Scripts\python -m finn.embeddings --symbol ALL --max-batches 400
```

Status is inspection; backfill commands consume available embedding quota and write
private index state. `ALL` selects current ready corpora, not archived versions.
`--no-wait` returns pending immediately on quota/storage interruptions.

## Selective rollout and rollback

Production enables `FINN_ENABLE_SEMANTIC_SEARCH=true` and
`GEMINI_EMBEDDING_MODEL=gemini-embedding-001`. New databases should apply the migrations
and review a complete-index evaluation before enabling the flag. Rollback sets the
flag to `false` and redeploys the API; keyword retrieval then avoids embedding/status calls.
No frontend setting is required. [Deployment](DEPLOYMENT.md) covers configuration.

A company needs complete current embedding coverage before semantic search is eligible.
Incomplete coverage, missing credentials, quota denial, malformed vectors, provider
failure, semantic SQL failure or unusable semantic results preserve the keyword path
with actual mode/limitations. An empty eligible scope is distinct from a semantic error.
A PostgreSQL outage cannot be repaired by keyword fallback because both branches share it.

Cache identity includes document scope, embedding/input versions, retrieval settings
and completed-index fingerprint. Adding a current PDF invalidates stale source-scope
answers before its embeddings finish. Partial batch progress does not invalidate every
keyword answer; index completion does. Semantic failure is not cached under a hybrid
identity. Existing published answers keep their actual generation dates and retrieval modes.

## Coverage and verification

A dated read-only inventory on **3 November 2026** counted **3,299 / 20,028 current
chunks** and **17 / 75 fully indexed documents**, across 21 companies with documents.
CCL, GOKEX and V2RETAIL had complete indexes; INFY, TMCV, POLYCAB and other incomplete
companies retained keyword retrieval. These are a checkpoint, not permanent production
counts or a claim that the entire watchlist/NSE is semantically indexed.

Rollout checks exercised a fresh CCL answer, cached GOKEX answer and partial-index
keyword fallback. Later V2RETAIL acquisition used the generic quarterly path, indexed
25/25 chunks and produced a three-claim hybrid evidence follow-up with original PDF
pages 9/10/12. Controlled provider/SQL failures, stale-body writes and flag rollback
were checked without weakening source or financial validation.

The opt-in `scripts/verify_hybrid_rollout.py` exercises live behavior and can generate
answers/use quota; it is not a read-only smoke test. Evaluation commands and their
limits are documented separately in [retrieval evaluation](HYBRID_EVALUATION.md).
For lightweight checks use [testing and reliability](EVALUATION.md).

References: [Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings),
[REST API](https://ai.google.dev/api/embeddings),
[Supabase hybrid search](https://supabase.com/docs/guides/ai/hybrid-search).
