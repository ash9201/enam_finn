# Evidence-first company research

Claims and citation chips open the same evidence panel: selected claim, exact stored
source passage, original document, PDF page, dates and original PDF link. It is a right
drawer on desktop and a scrolling bottom sheet on mobile, with a persistent follow-up
action, keyboard dismissal, focus restoration and background-scroll locking. Both
themes use the existing shared tokens.

**Ask about this evidence** carries the company and selected statement into the question
form. Three optional paths investigate repetition, later observations or another
perspective. The active context can be inspected or removed; returning to general
company research preserves completed investigations in a short, in-memory research
trail. This is bounded company research without an elaborate conversational agent.

## Server contract and retrieval

`POST /research` retains the existing job/polling contract and accepts:

```json
{
  "symbol": "CCL",
  "question": "What did later commentary say about this statement?",
  "context": {
    "research_id": "<parent answer UUID>",
    "citation_id": "<selected chunk UUID>",
    "claim_index": 0,
    "intent": "later"
  },
  "include_history": false,
  "refresh": false
}
```

Intents are `question`, `repeated`, `later` and `perspective`. The client sends references,
never an authoritative claim/quote. The server resolves the saved answer, verifies
company and citation membership, and checks the quote against the current stored
chunk. The claim index distinguishes different claims using the same passage; an
ambiguous legacy reference is rejected. Missing or stale evidence produces an explicit error. The read-only
`GET /research/{research_id}/evidence/{citation_id}?symbol=CCL` returns verified passage
metadata without a model call or exposing a full private document.

The selected chunk is pinned as an anchor. Two deterministic searches use the question
plus claim and the claim alone; existing keyword/hybrid retrieval, company/manifest
filters, RRF and diversity limits are reused. Other documents receive space before
additional passages from the anchor document. The existing semantic feature flag and
keyword fallback remain unchanged; production is still keyword-only.

Repetition searches transcripts and excludes known duplicate versions of the same
dated call. The later-evidence path additionally searches strictly later, independently
dated documents in the active manifest. Generated later claims must cite those
documents. If none can be retrieved, the workflow abstains before calling the model.
Unknown chronology is not a disagreement or evidence of target delivery.

The optional **Add earlier documents** acquisition uses the same generic discovery,
hashing, extraction and ingestion pipeline: up to two annual reports and four calls,
instead of the initial one report/two calls. Unchecking the option does not hide
collected history; later refreshes retain this expanded discovery depth. The active
manifest still tracks the latest bounded set, rather than an unlimited archive.
**Check latest sources** runs the existing
refresh. Missing history and failed retrieval stay visible. No broad web research or
new data provider was added.

## Dates, validation and persistence

Index labels are not publication dates. For transcripts, a conservative extractor
accepts one unambiguous English date repeated in call headers on at least two of the
first four PDF pages; a verified publication date is a fallback. Ambiguous/scanned or
other date formats remain unknown. Annual reports without verified publication dates
are excluded from chronological claims, even when an index label names a year.

Context and history options persist in existing job JSON, participate in deduplication,
and reach the worker after polling/restarts. Answer cache identity includes canonical
context, anchor content hash, corpus version, retrieval identity and follow-up prompt
version. Follow-ups stay private and cannot be published through the prepared-answer
flag. Abstentions and runtime semantic failures are not cached as permanent results.
No SQL migration, dependency or access-policy change is required.

Existing exact-quote, number, named-financial-metric and unvalidated-table guards apply
to every new claim. The prompt preserves forecasts/conditions, attributes management
commentary and distinguishes repetition from delivery. Follow-ups additionally withhold
quotes ending mid-sentence, which source review exposed in an early generated result.
Citation existence and chronology
checks do not mechanically prove semantic support; source review remains necessary.
Financial table comparisons remain disabled.

## Verification: 31 October 2026

| Check | Actual result |
| --- | --- |
| CCL July 28 call, PDF p. 6: utilisation and freeze-dried demand → October 16 call | Validated later-source claims; independent October passages, original links and dates. Repeated request reused its private answer cache. No financial-target conclusion. |
| July cost-plus statement → later-document investigation | Insufficient support; no forced corroboration from unrelated October commentary. |
| Focused freeze-dried demand repetition check | October p. 7 supplies an independent supporting statement. This does not establish repetition of July's aggregate utilisation percentage. |
| Pricing perspective follow-up | October pp. 7/13 supply management's pricing explanation and explicitly conditional demand belief; no fabricated disagreement or target verdict. |
| General follow-up from an annual-report business claim without a verified date | Retrieved calls and answered the demand question. Direct deployed-browser testing exposed an overly broad chronological instruction; it now applies only to the later-evidence path. |
| October statement → no independently dated later document | `insufficient_evidence`, no claims and zero model usage. |
| POLYCAB optional history acquisition | Two real annual reports and four transcripts ready through generic ingestion; original source metadata retained. |
| Backend regression | 129 tests passed, including company-bound references, same-passage claim identity, stale quotes, chronology, general questions without dated anchors, complete-quote checks, duplicate-call exclusion, cache isolation, job context and abstention. |
| Browser interaction | Four viewport/theme combinations: 390×844 and 1440×1000, Light and Dark. Exact passage, real API evidence reads and cached follow-up jobs, source ordering, focus, context removal/restoration, company reset and missing-context failure guard passed. |
| Theme regression | 44 existing scenes passed: system preference, persistence, contrast, startup and responsive states. |
| Build/security | TypeScript/Vite production build and privileged-credential bundle scan passed. |

Browser checks replay only the initial private real-source answer to enter the UI;
evidence reads and follow-up jobs hit the actual API. Transport-error checks are
explicit simulations. Real generation and absence-of-later-evidence checks are separate.
No fabricated source or published fixture was introduced. Browser emulation is not a
physical-device test. The bounded CCL case is acceptance evidence, not a broad claim
about comparative answer accuracy.

Reproduce with the existing local API, frontend preview and configured private keys:

```powershell
.\.venv\Scripts\python scripts/verify_evidence_research.py
python scripts/npm.py run build
python scripts/npm.py run test:evidence
python scripts/npm.py run test:theme
```

The opt-in real check uses Gemini if its answer cache is absent; it writes private
research and ignored local artifacts. It requires the actual July/October 2026 CCL
calls in the active corpus and stops rather than substituting another source. Set
`FINN_EVIDENCE_API_URL` for the API under test; the default is localhost port 8000.
Local screenshots/reports are in `artifacts/evidence-browser/` and
`artifacts/release/evidence-*-real.json`; credentials and generated artifacts are ignored.
