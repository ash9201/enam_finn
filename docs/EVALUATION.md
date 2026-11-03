# Testing and reliability

FINN uses focused offline tests, pure frontend model tests, recorded-source browser
checks and opt-in real-service verification. These establish different kinds of
confidence; a passing cache read is not proof of a fresh source acquisition or model call.
The separate [retrieval evaluation](HYBRID_EVALUATION.md) reports measured recall,
answer review and latency rather than folding them into a general accuracy claim.

## Routine local checks

From the repository root with the configured toolchain:

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python scripts/npm.py run test:briefing:model
.venv\Scripts\python scripts/npm.py run test:company-search
.venv\Scripts\python scripts/npm.py run test:portfolio:model
.venv\Scripts\python scripts/npm.py run build
.venv\Scripts\python scripts/check_frontend_secrets.py
```

Use relevant test files during development, then the full regression for a completed
behavioral feature. Documentation-only changes need link/reference and whitespace checks,
not model calls or source ingestion. Hosted CI runs the backend regression, frontend
model checks, production build and credential scan on standard Ubuntu runners.

The 3 November 2026 CI checkpoint passed **336 backend tests**, with one existing
Starlette test-client deprecation warning. This is a dated result, not a fixed expected
test count. Build history records why coverage expanded, without repeating every command.

## Important invariants and reviewed cases

| Area | Checks and observed cases |
| --- | --- |
| Identity | Verified symbols/ISINs, aliases/ambiguity, 403 and malformed-directory last-known-good fallback, unknown-company failures, restart reuse |
| Announcement classification | Actual results versus notices/recordings; auditor rotation; credit-rating context instead of incidental word matches; unclassified filings retained |
| Event grouping/reviews | KPIT tenure dates, NTPC results/dividend/debt separation, Reliance recording relationships, all source identities retained, stable ordering, versioned receipts, undo and updated evidence |
| EOD integrity | Bounded Yahoo retry, null latest close, exact-date/EQ/ISIN NSE recovery, prior-20 baseline, split suppression and refusal to overwrite a newer session |
| Retrieval | Matched metadata filters, no cross-company passages, complete-index eligibility, stale-vector rejection, provider/SQL/quota fallback, cache invalidation and restartable indexing |
| Evidence | Exact stored quotes/pages/hashes, same-passage claim identity, typed validation versus outage errors, safe retry, verified-context follow-ups and explicit unknown dates |
| Financial research | Compatible periods/bases/units/entity, native/image disagreement, missing rather than zero, reported EBITDA, PAT attribution, Decimal changes/ratios and every calculation input cited |
| Chronology | CCL cross-document repetition/later investigation, no-later-source abstention without generation, KPIT incomplete-unit/full-year target withheld |

Source-slice validation establishes that an excerpt exists. It does not prove every
paraphrase, causality claim or accounting interpretation. Important examples were
reviewed against source pages; the whole corpus has not been independently audited.

## Browser coverage

Affected interaction suites cover desktop 1440×1000 and mobile 390×844 in light/dark,
with additional 320px and short-landscape checks. Theme checks cover startup before
React, System preference, persistence, cross-tab changes, contrast and visible focus.
Representative cross-page testing follows a Briefing results event into financial
research, opens figure evidence/context, visits Portfolio, filters company Briefing,
and returns to the retained company, draft and accounting basis.

Checks include no root overflow or sticky-navigation obstruction; selectable prose
and dedicated evidence buttons; distinct external PDF links; multiple sources; keyboard
focus; autocomplete; all four one-click actions; basis switching; a single quarterly
section; sorting/expansion; review counts/undo; and local alert preferences. Empty windows,
loading, cached answers, unavailable figures, API errors and recorded fallback are explicit.

```powershell
.venv\Scripts\python scripts/npm.py run test:layout
.venv\Scripts\python scripts/npm.py run test:briefing
.venv\Scripts\python scripts/npm.py run test:research-redesign
.venv\Scripts\python scripts/npm.py run test:portfolio
.venv\Scripts\python scripts/npm.py run test:evidence-reliability
.venv\Scripts\python scripts/npm.py run test:evidence-controls
.venv\Scripts\python scripts/npm.py run test:metrics
.venv\Scripts\python scripts/npm.py run test:theme
```

These require a running frontend preview/API and, for several suites, previously captured
real-source artifacts under ignored `artifacts/`. `FINN_BROWSER_URL` selects another
frontend target where supported. Browser fixtures are not committed; a fresh clone
cannot replay every source-specific scene without preparation. Transport/job failures
are test simulations, not altered production records. Real generation was checked
separately and reused across visual scenes rather than called again per theme.
Chromium device emulation is not physical iOS/Safari coverage. Original PDF targets
are checked without repeatedly downloading every exchange document.

## Read-only deployment checks

The existing script name is retained for compatibility:

```powershell
.venv\Scripts\python scripts/verify_submission.py --local-only
.venv\Scripts\python scripts/verify_submission.py --live-only --timeout 75
# Public checks only, even if local server credentials exist:
.venv\Scripts\python scripts/verify_submission.py --live-only --public-only
```

Default invocation combines local regressions/build with live checks. API selection is
`--api-url`, then `FINN_DEPLOYED_API_URL`, then `VITE_API_BASE_URL`.
`FINN_DEPLOYED_WEB_URL` enables deployed asset scanning. Reports print PASS/FAIL/SKIP
and return nonzero on failure. Missing credentials/cases and deliberately uncalled
model operations stay SKIP; zero failures does not prove skipped functionality.

Live checks use GET endpoints and allowlisted SELECT-only RPCs: liveness, canonical
identities, prepared-cache stability, citation metadata, RLS, private anonymous denial,
financial caches, index counts and injected quota-failure keyword fallback over stored
corpora. They never submit `/research`, reserve model budget, refresh sources or backfill.
An initial 20-second cold API request timed out in the 3 November check; a bounded
75-second retry passed. Live Gemini generation/ranking was intentionally not repeated.

## Opt-in integration work and limits

`scripts/verify_evidence_research.py`, `verify_financial_results.py`,
`verify_portfolio_financials.py`, `verify_hybrid_rollout.py` and retrieval evaluation
commands can write caches, acquire sources or use Gemini when needed. Read their
options before running. Numerical verification reuses stored primary evidence without
generation/embedding calls, but can still write research artifacts/cache state.
`--refresh` and `--publish` are explicit operational actions, not ordinary smoke tests.

Free cold starts, delayed GitHub schedules, source restrictions, incomplete history,
partial embeddings and unsupported accounting layouts remain real limits. RLS protects
private database access, but there is no user authentication or confidential-document
security boundary. Environment files, raw PDFs and diagnostics stay ignored; the
frontend scanner checks for private credentials in emitted assets. See
[architecture](PLAN.md), [financial policy](QUARTERLY_RESULTS.md) and
[deployment](DEPLOYMENT.md) for the corresponding safeguards.
