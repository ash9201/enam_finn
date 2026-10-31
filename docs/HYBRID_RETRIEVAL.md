# Hybrid retrieval

The implementation stays in FastAPI and Supabase. Gemini `gemini-embedding-001`
embeds text; PostgreSQL full-text search and pgvector cosine search retrieve primary
passages. Python combines **ranks**, not incompatible raw scores, with Reciprocal
Rank Fusion (RRF). No embedding SDK, additional database, or RAG framework was added.

## Evidence and filtering

Both branches restrict results to the requested NSE company, its active document
manifest, and ready documents. Optional filters cover document kind, explicit document
IDs, verified publication-date bounds, reporting period, and JSON metadata containment.
Unknown publication dates cannot satisfy date filters. Discovery labels remain separate
from verified dates. Metadata does not become more trustworthy because a passage has
an embedding.

Search returns the original chunk body, PDF page and source metadata. Final PDF URLs
are resolved from server-owned document records. Existing exact-quote, numeric support,
and financial-table guards remain in force after generation. Evaluation also added a
conservative named-metric check: a margin quote cannot validate added EBITDA/EBIT/EPS/
PAT/PBT claims. Cached answers with that mismatch are regenerated. Financial table
comparisons remain disabled. The specialised narrative/evidence comparison keeps its
conservative statement selector and chronology/metric checks; it is not relabelled hybrid.

Cosine search is exact **after** company/document filtering. Current per-company corpora
are small enough to avoid an approximate global index and its post-filter recall risks.
Measure before adding HNSW or changing chunking.

## Embeddings and resumable indexing

- 768 dimensions; `RETRIEVAL_DOCUMENT` for passages, `RETRIEVAL_QUERY` for questions.
  Shortened `embedding-001` vectors are normalised in Python. Invalid dimensions,
  non-finite values, zero vectors and incomplete batches are rejected.
- Cache namespace: model, dimensions, task, input version, SHA-256 of exact input text.
  Query text is not stored in this cache. Raw documents stay in the existing private
  tables/bucket; private vectors and quota accounting have RLS and no public grants.
- Each chunk has a database-generated body hash. A conditional write rejects embedding
  results if its text changed during the provider request. Retrieval requires the
  current model/version/dimensions/hash; incompatible vector spaces are never mixed.
- Batches start at 24 inputs, with actual token counting, conservative token reservation,
  smaller batches when needed, and no silent input truncation. Completed embeddings
  are cached before chunk updates. Retries reuse those vectors after a connection loss.
- Shared database reservations count **individual embedded texts**, including those in
  batches: 80 input units/minute, 800/day for bulk backfill, up to 900/day for foreground
  questions, and 27,000 reserved tokens/minute. These are below the owner's stated
  100/1,000/30,000 limits. Token-count HTTP calls conservatively reserve one unit too;
  token counts are reused within
  a worker. Daily accounting follows the provider's Pacific date. Other applications
  using the project can still consume its allowance.
- Minute/provider throttling waits are bounded and interruptible. Daily exhaustion or
  unsupported input stops the run with explicit pending status. Google `QuotaFailure`
  and `RetryInfo` distinguish a daily stop from a short throttle. Cached query vectors
  remain usable during a provider cooldown. No paid capacity is enabled.

Activate a complete primary-document manifest first; then the generic ingestion path
schedules indexing for that company. Reused corpora also resume missing embeddings.
One background I/O worker per API process handles these tasks. Completed chunk state
survives restarts; another company request or the CLI resumes unfinished work. A free
Render instance can sleep before a large backfill finishes. Use the CLI for the initial
bulk pass; research remains usable through keyword retrieval while indexing proceeds.

```powershell
.venv\Scripts\python -m finn.embeddings --symbol CCL --status
.venv\Scripts\python -m finn.embeddings --symbol CCL --max-batches 100
.venv\Scripts\python -m finn.embeddings --symbol ALL --max-batches 400
# --no-wait returns pending immediately on a quota/storage interruption.
```

The CLI is an explicit indexing operation and can run while the rollout flag is off.
It does not rediscover/download documents or change source dates. `ALL` selects active
ready corpora, not archived document versions.

## Rollout and rollback

1. Apply `supabase/migrations/0006_hybrid_retrieval.sql` with RLS enabled. The owner
   applied it successfully. Also apply `0007_embedding_input_quota.sql`, which corrects
   quota accounting after the observed live daily limit. Original keyword RPCs remain available.
   Run `python scripts/verify_embedding_quota.py` to verify input accounting with isolated,
   promptly removed audit reservations; it never calls Gemini.
2. Backfill and inspect status, then run the evaluation below. Keep
   `FINN_ENABLE_SEMANTIC_SEARCH=false` until reviewed results justify rollout.
3. In the **Singapore API** Render environment, set `GEMINI_EMBEDDING_MODEL` to
   `gemini-embedding-001` and `FINN_ENABLE_SEMANTIC_SEARCH=true`; redeploy. No frontend
   secret or Gemini key belongs in Vite. No new GitHub Actions secret is required.
4. Ask a new question about a fully indexed company and inspect `retrieval_mode`,
   actual citations and limitations. Prepared historical answers retain their actual
   search mode and original dates.
5. Roll back with `FINN_ENABLE_SEMANTIC_SEARCH=false` and redeploy. New retrieval uses
   keyword search without any embedding/status calls. Previously generated answers
   remain valid cached records; toggling the flag does not rewrite their history.

Full-company embedding coverage is required for semantic search. An incomplete index
uses keyword search with an explicit note. Missing credentials, quota denial, malformed
vectors, provider/network failures or semantic-RPC failure also fall back to keywords.
The keyword branch still needs PostgreSQL; a database outage cannot be repaired by
semantic fallback. Failed semantic attempts are never cached under a hybrid answer key.

Hybrid answer-cache identity includes model, embedding/input version, retrieval settings
and the completed index fingerprint. Index completion invalidates a preparing-state
keyword answer. Flag-off requests retain compatibility with the original keyword cache.

## Reproducible evaluation

`evals/retrieval_cases.json` contains ten answerable questions (five development, five
parameter hold-out) and two unsupported questions, with primary-source PDF page links
and support notes. Source pages were inspected before selecting retrieval settings.

Recall@5/@10 uses **curated reference pages**, not exhaustive relevance annotation of
thousands of pages: retrieved chunks occupy ranking slots; duplicate reference pages
count once. A different valid page may support a good answer without increasing this
reference-page recall. Review answer support separately. This is a small engineering
check, not an independently human-rated or statistically representative benchmark.

```powershell
.venv\Scripts\python scripts/evaluate_retrieval.py collect
.venv\Scripts\python scripts/evaluate_retrieval.py tune
.venv\Scripts\python scripts/evaluate_retrieval.py answers
```

Use `--symbols CCL` for the completed evaluation; the full-set run remains pending
available free-tier quota. These commands opt into semantic search **only in their process**, never change Render
or `.env.local`, and require live credentials/complete indexes. Raw candidates, generated
drafts and timings stay under ignored `artifacts/retrieval/`. Collection refuses a keyword
substitution when hybrid is unavailable, and resumes completed cases. The original
keyword baseline is frozen explicitly. Twelve bounded RRF configurations are selected
using development queries only; hold-out scores do not select settings. A matched
keyword ablation separates candidate-budget changes from semantic gains. Generation
uses the same existing model, prompt and validators for both methods. Ratings must be
reviewed against the actual excerpts, including alternative supporting pages and abstention.

Latency includes client-to-Supabase/model round trips on the operator's connection,
not just SQL execution. First-use and warmed query-cache latency are measured separately;
document ingestion/backfill is excluded. See the actual [evaluation and limitations](HYBRID_EVALUATION.md).

References: [Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings),
[REST API](https://ai.google.dev/api/embeddings),
[Supabase hybrid search](https://supabase.com/docs/guides/ai/hybrid-search).
