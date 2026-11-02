# Build history summary

### Evidence reliability and read-only submission checks (2 November)

- Preserved existing source/claim ownership and quote/page-hash checks. Added typed
  validation versus storage-outage responses, malformed/page/version checks, bounded
  drawer verification and retry, and verification-only follow-up gates. Missing date
  metadata and unavailable financial previews no longer imply passage failure.
- Added `scripts/verify_submission.py`: reuses targeted regressions/build, directory,
  cache, RLS, retrieval and existing secret scanning. Remote checks are read-only;
  no research POST, Gemini call, quota reservation, ingestion or backfill. The policy
  probe uses document pages' composite key rather than a nonexistent `id` column.
- Combined check: 22 PASS / 0 FAIL / 2 SKIP, including 184 targeted regression tests.
  Browser replays cover verification faults and existing evidence/numerical workflows
  at desktop/mobile sizes in both themes. Details and commands: DEPLOYMENT.md and
  EVIDENCE_WORKFLOW.md. No schema, financial calculations or ranking changes.

### Compact evidence controls (2 November)

- Unified Research evidence-opening controls as compact, themed button chips with a
  panel icon, source label and physical page. Existing handlers, drawer, verification
  and external PDF anchors are unchanged, including numerical/quarterly/comparison views.
- Removed the Briefing coverage heading and excess divider/spacing while preserving
  the complete provenance and coverage paragraph.
- Frontend build, credential scan and targeted real-fixture browser replays pass at
  1440px/390px in light/dark themes: multi-source, keyboard/focus return, external
  PDF destination, source switching, financial evidence and contextual follow-up.
  No backend changes, ingestion or model evaluations.

### Credit classification and verified numerical research (2 November)

- Replaced substring rating detection with credit/agency/action context; specific
  downgrade/outlook/upgrade/withdrawal/reaffirmation priorities. Added regression
  negatives for operating, generating, integrating, agency commentary and ESG/equity
  ratings. The idempotent dry-run audit found no retained records requiring repair.
  `python -m finn.filing_reclassification --apply` patches only related classification
  fields and preserves IDs, source links and review state.
- Added a 147-metric registry and deterministic numerical intent recognition; conceptual
  and CFO-person queries retain ordinary Research. Values use existing primary PDFs,
  hybrid/keyword candidates, approved quarterly cells and Decimal calculations.
- Added explicit intent completeness, source/version-aware caching and TMCV/TMPV
  entity safeguards. General unverified LLM ratios remain prohibited. Every calculated
  input has its own evidence interaction; existing quarterly comparisons are intact.
- Verified real TMCV direct ratios and V2RETAIL calculated margin/source cells. Added
  reported/calculated/unavailable cards using shared tokens, and desktop/mobile
  light/dark browser checks. Full backend regression, build and secret scan pass.
- Details, source links, support matrix and limits: QUARTERLY_RESULTS.md. Rating files:
  `backend/finn/briefing.py`, `backend/finn/filing_reclassification.py`, and
  `tests/test_credit_ratings.py`. No schema, dependency or environment changes needed.

### Production hybrid scope and rollout (2 November)

- Verified production flag was disabled and Gemini embedding access worked; owner
  enabled the flag and applied private migration 0011.
- Extended existing indexing/search to quarterly filings, atomic conditional batch
  writes, scope-aware cache invalidation and quota-aware incremental resume.
- Preserved complete-index eligibility, frozen RRF settings, original citations,
  financial validation and the persistent NSE-directory fallback.
- Added focused tests; refreshed primary-page recall/latency without retuning or
  rerunning source ingestion broadly. Live outcomes are in HYBRID_ROLLOUT.md.

### Event-based review and focused workflow controls (2 November)

- Added independent unusual-activity prioritisation plus transparent Portfolio sorts;
  moved Alert thresholds beside them and kept existing calculations/preferences.
- Added stable Briefing company and chronology orders, significance filtering and
  clear Significant/Routine/Unclassified labels with a secondary rules disclosure.
  Compacted summaries, moved publication time beside titles and removed filing-based
  headline counters. Original sources/evidence and event-specific facts remain.
- Introduced versioned event receipts with one-time legacy review migration,
  event-level counts/undo and Updated since review for new/changed evidence. Verified
  multi-development references can share a file without sharing review state;
  identical duplicate evidence does not create a false update.
- Left-aligned Investigate beneath the question, preserving behavior and prompts.
  Focused pure-model and four-scene UI tests cover sorting, migration, updates,
  persistence, filters, source identities, both themes and responsive layouts.
  No backend/source/model pipeline changes. See the existing Briefing/Portfolio reports.
### Reliable company identity and focused UI fixes (2 November)

- Replaced the live-on-resolution NSE CSV dependency with a verified persistent
  Supabase reference snapshot, the existing bundled capture and trusted prior company
  identities. Exact symbols and ISIN conflicts remain guarded. Successful live
  refresh: 2,620 listings, 19 existing stored identities checked; anonymous writes denied.
- Added daily bounded official-directory refresh to existing portfolio automation,
  preserving the last good snapshot on 403, malformed/truncated data or storage failure.
  Metadata retains actual source/check dates. No SQL migration or model calls needed.
- Moved Find company beside the selected identity, clarified watchlist labels, kept
  recents and autocomplete, and moved directory provenance to secondary details.
  Removed the generic coverage caption. Moved generic split methodology out of rows;
  actual per-company suppression notes and financial calculations remain intact.
- Focused resolution/pipeline and split-guard tests, company-search/portfolio model
  checks and four themed viewport UI checks plus a reference-store 403 fallback pass.
  See [research reliability](RESEARCH_REDESIGN.md) for actual behavior and limits.
### Final integrated UI acceptance (2 November)

- Reviewed the actual shared layout, Briefing, Research and Portfolio together in
  both themes at desktop/mobile sizes. Found and fixed sticky quarterly-table cells
  escaping the horizontal scroller and widening the mobile page. Local table
  scrolling, figure evidence, all data and financial safeguards are preserved.
- Added a real saved-data event → figures → evidence → Portfolio → company Briefing
  → retained Research journey to the existing layout checks, alongside attempted
  global-pan regression checks. Restored strict page-width auditing in theme tests.
- All targeted UI suites pass, including four theme/viewport matrices, search,
  review/undo, source identities, one-click actions, basis handling, unavailable
  figures, loading/empty/error states and 56 theme scenes. The 27 frontend model
  checks, build and credential scan pass. No ingestion, new model evaluations or
  backend/AI changes. [Scope, evidence and limits](ACCEPTANCE.md).

### Charcoal / blue dark palette (2 November)

- Refreshed shared dark tokens with near-black canvas, charcoal/slate surfaces,
  soft off-white text, muted blue interactions and subtle dividers. Green/red
  remain financial/status colours; warning states retain restrained amber.
- Added a shared elevated-surface token for evidence panels and company options;
  its light value aliases the original surface. All existing light token values
  are unchanged. No application behaviour, layout, backend or AI changes.
- Updated the theme checks for the current Research/Portfolio UI and added real
  published NTPC tables, figure evidence and company-option states. All 56 scenes
  pass across desktop/mobile, both themes, contrast, focus, persistence, OS/cross-tab
  changes and startup before React. Financial cache reads are frozen across scenes;
  simulated progress/errors do not send research/model requests.

### Portfolio watchlist redesign (2 November)

- Replaced oversized cards with a sortable desktop table and mobile rows using
  the shared warm light/dark tokens. Full names, sectors, Last close, signed 1D
  change and primary Research actions are visible, with optional company details.
- Centralized EOD date and source methodology, preserving original per-company
  source URLs and local freshness/error warnings. Membership and calculations
  are unchanged; these are share prices, not invested amounts or returns.
- Shared Briefing's existing threshold predicate and grouped recent events for
  genuine attention indicators, with filtered company Briefing links and retained
  navigation state. No backend or model workflow changes.
- Six model checks and targeted browser verification passed for all 15 real saved
  rows, sorting, expansion, links, preferences, source attribution, contrast and
  failure handling across desktop/mobile and both themes. See
  [Portfolio redesign](PORTFOLIO_REDESIGN.md) for actual data and test boundaries.

### Research workspace redesign (1 November)

- Added a dated official 2,620-company NSE directory with name/symbol histories,
  local autocomplete, aliases/acronyms and typo fallback. Ambiguous names require
  selection; the backend still receives the canonical NSE symbol.
- Replaced the ticker strip with a full-name selected company and collapsed
  watchlist. Company workspaces, drafts and navigation locations are preserved.
- Grouped four one-click workflows above the result. Specialized saved reads are
  reused, late overviews cannot overwrite chosen results, and repeated quarterly
  actions preserve the accounting basis. Removed the detached comparison control.
- Compacted reading/evidence spacing and moved technical coverage into details.
  Financial tables retain readable figures; single-basis answers have an explicit
  unavailable-basis message without ineffective tabs. Financial/retrieval logic
  and the backend architecture are unchanged.
- Verified real NTPC/SUNPHARMA basis values and one financial section, all four
  live CCL actions, source evidence, four theme/viewport scenes and focused
  latency/failure/archived-basis cases. See [the implementation report](RESEARCH_REDESIGN.md).

### Event review, complete descriptions and narrower topics (1 November)

- Replaced source-level review buttons with one event control operating on the
  existing filing IDs. Immediate undo restores a legacy mixed review state;
  saved reviews survive reload. Chronological activity uses the same grouped
  events and sorts by their latest publication, avoiding per-source review controls.
- Found the formatter was dropping the last word of unpunctuated text and adding
  ellipses after 450 characters. Full saved feed statements now recover the missing
  Dividend/year words without downloads. Native excerpts contribute a complete
  sentence; incomplete source text is labelled and never completed speculatively.
- Split NTPC's shared results package into results (two sources), dividend/record
  date (three), and three distinct debt subjects. A dividend requires a verified
  type/record date; debt duplicates require the same subject and document hash.
  Reprocessed eight NTPC filings using one cached PDF and one XML fetch. No model,
  research, financial-calculation or schema changes were needed.
- Targeted checks: 27 filing-detail cases, 16 frontend model cases, and four
  desktop/mobile Light/Dark browser scenes, including legacy review undo/reload,
  full descriptions and the regrouped sources. Build and asset credential scan pass.

### Expanded Briefing event refinement (1 November)

- Kept the collapsed company list and page structure. Expanded events now show one
  explanation, category/date, actions, compact official-source links and one optional
  evidence inspector with a source selector. Removed the per-document cards, nested
  disclosures, repeated summaries and investor-facing exchange metadata.
- Verified the KPIT PDF's additional subsidiary/committee roles and effective date.
  Refreshed only six recording/tenure documents across KPIT, NTPC and Reliance.
  Recording pairs group by explicit call date, recording type and shared recording
  URL; presentation and unrelated operational disclosures stay separate.
- Original filing identities, URLs, timestamps, wording and review states are retained.
  New ingestion extracts the same references generically; no financial/retrieval/model
  changes, dependencies, migration or environment settings are needed.
- Targeted verification: 21 filing-detail tests, 15 frontend model tests, four
  desktop/mobile Light/Dark browser scenes, build and privileged-credential scan.
  See [the refinement report](BRIEFING_REDESIGN.md#expanded-event-refinement).

### Briefing redesign (1 November)

- Added compact company/event groups, chronological activity, combined filing filters
  and explicit browser-local review/undo/counts. Full names and contextual actions
  replace raw-label cards and repeated template advice. EOD settings sit with signals.
- Owner applied 0010 with RLS enabled. Cached native-PDF/XML/feed extraction retains
  source excerpts, pages/fields and hashes; no new model calls or financial-table
  comparisons. Scheduled sync incrementally prepares six pending records per run.
- Reviewed all 37 captured records. Verified NTPC's related results package, neutral
  KPIT tenure completion, Reliance's enabling debt authorisation, and conservative
  headline-only handling of ambiguous debt tables. Raw IDs/dates/text/URLs are preserved.
- Final regression: 209 backend and 12 frontend model tests pass; four targeted
  viewport/theme scenes and a labelled fallback check pass. [Detailed report](BRIEFING_REDESIGN.md).

### Shared layout redesign - phase 1 (1 November)

- Unified page chrome with compact desktop header navigation and a mobile bottom row
  outside the scroll area. Replaced promotional introductions with functional titles,
  removed the large summary strip and added shared spacing tokens.
- Retained visited section state/history, drafts, results, evidence context and scroll;
  deliberate company links still open the chosen research entry. Paused inactive
  portfolio polling and kept shared alert preferences consistent.
- Replaced the obsolete setup page with live connection-only System Status and a
  return action. Page-specific contents, backend and calculation logic are unchanged.
  See [scope and targeted verification](SHARED_LAYOUT.md).

### Investor QA fixes (1 November)

- Reproduced cached-result reopening accumulating NTPC financial sections; fixed
  answer identity reuse and generation boundaries. Both NTPC bases and the working
  SUNPHARMA reference pass repeated-view tests. Research navigation has reserved space.
- Added bounded intent-aware evidence selection and a required response section per
  requested aspect. Real owner questions verify better INFY commercial focus and CCL
  demand/capacity/profitability/growth coverage. M&M numeric contribution limitations
  are explicit; unapproved segment tables never become figures.
- Kept the working CCL management comparison intact. KPIT now repeats the actual
  primary-source figures while explicitly preserving unit/period uncertainty.
- Added deterministic quarterly observations and preserved missing financial notes
  additively. SUNPHARMA's current-quarter disclosures are cited without inventing a
  complete earnings bridge. Final regression: 190 pass; build/bundle checks and four
  targeted viewport/theme scenes pass. [Detailed report](INVESTOR_QA.md).

### Research experience improvements (31 October, latest)

- Preserved main at release/pre-research-improvements-20261031 before development.
  Investigated real job/source/cache records and timed first acquisition, prepared
  generation and cache hits separately. Recorded actual measurements and limitations
  in [the release report](RESEARCH_IMPROVEMENTS.md).
- Expanded grounded answer synthesis with independently resolved supporting passages;
  isolated prepared answering from acquisition, removed automatic aged-corpus refresh
  and excessive progress writes, and exposed saved source documents during preparation.
- Audited all 15 original quarterly filings. Added bounded native/image recovery,
  reliable partial outputs and versioned evidence; recovered CCL cells, bank total
  income/group PAT and one explicitly reported quarterly EBITDA amount. No inferred
  EBITDA, YTD subtraction or guessed decimals. Two image reads use the same model;
  original pages and actual verification method remain inspectable.
- Replaced the poor KPIT comparison with complete, verified management speech and
  primary call dates. CCL reaffirmation is distinguished from delivered guidance.
  Assessment sees only selected quotes and never adds uncited candidate-page facts.
- Owner applied 0009 with RLS, added the embedding Actions secret/opt-in variable.
  Implemented leased, truthful indexing status and daily bounded maintenance without
  changing evaluated RRF settings or portfolio scheduling. Incomplete indexes still
  answer via keyword. Public access to the private operational objects is denied.
- Used targeted tests throughout, then full regression: 173 pass. The final suite
  exposed an obsolete all-or-nothing source-discovery assertion; it now verifies that
  partial original-source coverage never substitutes a generated summary. Build,
  credential scan and four affected viewport/theme checks pass with one live follow-up.

### Selective production hybrid rollout (31 October)

- Audited all active manifests: CCL 694/694 and GOKEX 711/711 complete; INFY 288/1,125
  and expanded POLYCAB 0/2,584 incomplete. Resumed both important backfills with bounded
  attempts; the already-consumed 800-unit bulk budget stopped them without provider
  calls. Paginated cache checks found no unused vectors to restore.
- Verified fresh and cached hybrid retrieval/answers, actual incomplete-index keyword
  answers, controlled provider/semantic-SQL failures and rollback. All 25 targeted
  hybrid tests and shared minute/day accounting audit pass, with frozen settings.
- The owner set the two documented Render variables and deployed the Singapore API.
  Verified its enabled flag, a fresh CCL hybrid answer, cached GOKEX hybrid answer
  and explicit INFY keyword fallback. Existing prepared answer history remains intact.
- No application retrieval, chunking, quota, scheduler, dependency or evaluation-setting
  changes. Added a repeatable opt-in verifier and [rollout report](HYBRID_ROLLOUT.md).
- Removed the Blueprint's pinned-false rollout value in favour of operator-managed
  `sync: false`, preserving the owner's Dashboard choice on future Blueprint updates.

### Quarterly financial results (31 October)

- Added generic primary quarterly-filing discovery, geometry-preserving native cell
  extraction, schema-bound optional row mapping and deterministic comparison policy.
  Shared storage/jobs/caches/evidence remain in use; no new paid service/dependency.
- Applied 0008 with RLS preserved. Fixed an initial incorrect SQL ORDER BY ordinal
  after the owner's error report; the revised private RPC passes access checks.
- Validated original POLYCAB/CCL PDFs before coverage expansion. Fixed merged/wrapped
  quarter headers so six-month columns cannot enter quarterly comparisons. CCL's
  decimal-damaged native text is withheld, not repaired. EBITDA is not fabricated.
- Added a compact two-table view, explicit accounting basis, restatement labels,
  formula/source inspection and financial-context research. A numerical anchor had
  overwhelmed a qualitative question: added question-only transcript retrieval and
  labelled other-period commentary; retained validation abstentions.
- Used targeted tests while building; final backend regression 154 passed. Affected
  components pass four viewport/theme combinations, build, contrast/overflow and
  credential scanning. Verified the follow-up once; other theme checks reuse source data without model calls.
- See [QUARTERLY_RESULTS.md](QUARTERLY_RESULTS.md) for real figures, policies and limits.
- Final deployment checks passed all four affected UI combinations with direct API
  access, a cached financial job and a live primary-source refresh from Render.
  Added two targeted EBITDA policy cases using rendered synthetic statements:
  explicit EBITDA is accepted, while adjusted EBITDA, margins and operating profit
  cannot substitute. This brings coverage to 156 tests without another local full-suite
  or unrelated browser replay.

### Evidence-first research interaction (31 October)

- Made claims and citation chips open a responsive evidence panel with exact quote,
  original PDF/page/link and separately verified dates. Added contextual follow-ups,
  three investigation paths, removable context and a short research trail.
- Reused persisted jobs, generic ingestion, keyword/hybrid retrieval and answer caches.
  Context references are resolved server-side; private answers cannot publish through
  the prepared-answer flag. Added optional two-report/four-call history acquisition.
- Later investigations require primary chronology and independently cited later sources;
  absent support abstains without a model call. Source review caught forecast wording
  becoming an observation; tightened the versioned follow-up prompt and rechecked it.
- Verified real CCL July/October documents and generic POLYCAB history. Browser testing
  caught and fixed modal focus restoration. Also guarded partial-sentence quotes and
  disambiguated individual claims sharing a chunk. Direct deployed-browser testing
  exposed an overly broad chronological instruction for general follow-ups; restricted
  that rule to the later-evidence intent and verified a date-unknown annual-report anchor.
  129 backend tests, four evidence interaction
  combinations, 44 theme scenes, build and credential scan pass. No new migration,
  dependency, paid service, scheduler change or semantic flag change.
- Details and reproducible opt-in checks: [EVIDENCE_WORKFLOW.md](EVIDENCE_WORKFLOW.md).

This record does not replace the assignment's required coding-agent conversation
exports/share links. Export those separately, redact credentials, and never bundle
`.env.local` into build history.

## 30 October 2026 — Milestone 0 only

- Read both PDFs and discussed product, architecture, costs, scope, and acceptance
  gates with the user. Added the requested hybrid retrieval/table-extraction amendments.
- Installed a local Python environment and SHA-256-verified official portable Node
  24.22.2. Did not change system PATH or PowerShell execution policy.
- Built the limited React foundation page and FastAPI liveness/configuration endpoints.
  No portfolio, investor feed, full research endpoint, or fake market data was added.
- Accepted public Supabase variable aliases; renamed the secret locally to a
  server-only variable and checked production assets for credential exposure.
- Added generic live source probes, page-aware extraction, conservative table
  candidates, metadata preservation, and credential-safe dependency reporting.
- Verified both requested Gemini models with one minimal request each and tested
  optional embedding access with one request. Semantic retrieval stays disabled.
- Initial Supabase checks correctly failed before SQL existed. The user applied the
  migration; DB/FTS/pgvector/storage and access-policy rechecks then passed.
- Inspected a real consolidated financial statement, improved table sampling/anchors,
  and kept all financial comparisons blocked pending validated facts.
- Passed offline and phone/desktop Chromium checks, including real cache/API access
  and explicit failed-request behaviour. Scanned emitted assets for actual secrets.
- Prepared Render free-tier configuration, CI/manual feasibility workflows, and setup
  instructions. No public URL or successful deployment has been invented.
- Stopped at the Milestone 0 deployment gate; later milestones remain unstarted.

## 30 October 2026 — first Push/Pull prototype

- The user deployed the foundation and authorised continuation. Verified real frontend,
  API, CORS, public-cache reads and a later idle-request latency; preserved model timeout
  and retry evidence instead of erasing failures.
- Added keyword-first company research with page/chunk provenance, content-hash PDFs,
  private storage, persisted jobs, restart recovery, source-filtered retrieval and
  validated citations. Applied the same engine to INFY before expanding to POLYCAB/CCL.
- Fixed narrative column interleaving without weakening table guards. Source-quote
  alignment returns original source characters; tests reject merged ambiguous numbers.
- Added RLS migrations and server-only policy audit. The user applied them with RLS on;
  live anonymous access tests verified the intended boundaries.
- Built real portfolio sync, explainable filing categories, EOD alerts, a watchlist,
  windows, routine expansion, settings and source-to-research navigation.
- Handled observed NSE timestamp variants and incomplete RSS, exposing incomplete
  coverage rather than substituting a fake feed. All 15 price snapshots were retrieved.
- Added a statement/evidence comparison with exact quotes and conservative period
  handling. Stronger-model latency led to a bounded, recorded smaller-model fallback.
- Added a public-only recorded snapshot with a visible historical-data notice, automated
  source workflow gated by repository configuration, browser acceptance and submission
  notes. Conversation exports/share links are still a separate submission artifact.

### Deployment verification findings

- Pushed the working prototype and verified actual Render phone/desktop flows. A fresh
  deployed question returned five exact-quote-backed claims; the model path works.
- An unprepared TCS request failed during source discovery on Render. Fixed-host,
  operator-only diagnostics isolated source connectivity failures; IPv4 did not fix
  them. Kept the failed job and did not replace it with a local seeded answer.
- Added bounded source GET retries, source-specific failures and safe status-poll
  recovery after a real disconnected response. Browser testing deliberately interrupts
  one status read to verify recovery.
- GitHub configuration is present, but both CI and dispatched sync stop before any
  jobs start. Requested the error banner; no paid spending or account settings changed.
- Recorded a phone walkthrough. Updated acceptance and README to expose the remaining
  deployment issues instead of declaring full completion.

### Public-runner retry and first live Singapore corpus

- Verified that the user made the repository public and restored the paid budget to $0.
  Retried CI/source jobs on standard Ubuntu only. Both remain blocked before runner
  assignment by an explicit account billing lock; no code ran and no larger runner
  was requested. Prepared a support draft without contacting anyone.
- The Singapore API reached the document index and completed uncached TCS research
  with one annual report/two calls and three page-backed claims. No local TCS corpus
  was seeded to conceal the earlier deployment failure.
- Profiled a slow 361-page first load. Reused the existing PDFium dependency for the
  large-document text pass, preserving pypdf financial-page layout and pdfplumber
  cells/geometry. Added native-handle cleanup, serialisation, source-preserving decode
  fallback, and real page/table/saving progress. Local full extraction fell from
  about 60 seconds to 7 seconds; deployed cold performance still needs checking.

### Singapore frontend verified; Supabase Cron fallback

- Confirmed that the user switched the production frontend and local canonical API
  URL to Singapore. Deployed product browser checks passed at phone/desktop sizes.
- User explicitly approved Supabase Cron after public standard-runner GitHub jobs
  remained blocked by the account billing lock. Paid budgets remain zero; GitHub
  source scheduling remains off to avoid duplicate automatic runs.
- Added a server-authenticated sync endpoint, private singleton lease/job, shared
  serial executor, per-source completion/error reporting, Vault-backed pg_net dispatch,
  and local-only credential SQL generation. No new service or model calls are needed.
- Added five failure/security/worker tests; 69 tests pass locally. Real Cron execution,
  cloud NSE/Yahoo fetching and deployed policy checks await the owner's SQL setup.

### Cron executes; transient provider failure and recovery (31 October IST)

- Verified the owner's SQL setup: two active schedules, successful self-removing
  Cron dispatch, HTTP 202 after API wake-up, private-table RLS and denied anonymous
  read/write/function access. Actual results were partial: filings and 14/15 prices.
- One Yahoo rate limit retained the original dated APLAPOLLO bar with an explicit
  error. A bounded operator rerun recovered 15/15. Saved both reports separately;
  did not relabel operator activity as scheduled activity.
- Added one rate-limit retry and late EOD recovery on subsequent announcement ticks,
  protecting the once-daily refresh against research contention or transient failures.
  78 tests pass. Prepared a credential-free self-removing full-source Cron recheck.

### Full scheduled refresh accepted (31 October IST)

- Confirmed the user's recheck as an actual Cron job: full-source work completed at
  03:23:18 IST, with all 15 prices and the announcement scan successful. Verified
  both active schedules, current source dates, private job RLS and anonymous denials.
  The one-time check removed itself; regular half-hour runs also succeeded.
- Preserved the original partial run and operator recovery separately. Only the new
  genuine scheduled run closes the full-source acceptance gate. GitHub source jobs
  remain off; no paid runner or service was enabled.
- Refreshed the public-only dated fallback snapshot and prepared the release checklist,
  demo script and updated covering draft. Actual conversation export and physical-phone
  review remain manual; no submission email has been sent.

### Stronger session integrity and primary-source recovery

- The release export caught an error missed by the initial freshness check: recent
  fetch timestamps accompanied older sessions because Yahoo returned a null latest
  close. Corrected the acceptance interpretation instead of shipping a false claim.
- Restored only strictly newer, previously verified saved records, retaining original
  dates with explicit failed-refresh markers; kept before/after evidence. The source
  is marked failed for genuine automatic overdue-EOD recovery.
- Added bounded NSE daily-archive recovery with exact date/EQ symbol/ISIN/hash checks,
  visible latest/history provider labels, no backwards session updates and no silently
  skipped baseline sessions. All 15 official records verified locally; none seeded
  as a fake cloud source success. Eighty-seven tests now pass.
- Reviewed real filing descriptions and corrected an earnings-discussion notice's
  availability claim; retained its original ID, source and publication time.
- The ordinary 03:47 IST Cron tick automatically recovered the failed EOD status through
  the new NSE adapter on Singapore: 15/15 records, actual 30 October sessions and source
  links, no errors. The strengthened read-only verification passes price integrity as
  well as dispatch, completion, freshness and access. No extra user SQL or local quote
  seeding was used. Exported the public fallback only after that result.

### GitHub account recovery (31 October IST)

- The user resolved the billing restriction and requested a return to GitHub scheduling.
  Both workflows then ran successfully on standard `ubuntu-latest`: 87 hosted tests,
  build/secret scan, and a full filing plus 15-company EOD sync. Actual stored sessions
  are 30 October, with no errors and `github_actions` provenance.
- Prepared a scoped, reversible SQL script to deactivate only FINN's fallback jobs.
  Application API keys cannot administer Cron. GitHub automatic scheduling remains
  off until owner SQL execution and inactive-schedule verification, avoiding duplicates.
- The owner then ran the scoped deactivation script. Confirmed both fallback jobs
  inactive and no in-flight source worker, enabled GitHub's repository source variable,
  and read it back as true. The scheduler switch is complete; the fallback remains
  installed but inactive. No paid runner or spending setting was changed.


### Hybrid retrieval implementation and measured limits (31 October IST)

- Added private pgvector embedding/cache/quota RPCs in migration 0006; the owner
  applied it successfully. Live tests confirmed anonymous denials, identical company/
  document/date/metadata filtering, and rejection of stale-content embedding writes.
- Implemented direct Gemini embedding REST calls, 768-dimensional normalisation,
  content/task/model-version caches, resumable batch indexing, RRF and explicit keyword
  fallback. Generic corpus activation/reuse schedules the same indexing path for any
  company. No dependencies or separate vector service were added.
- CCL reached 694/694 chunks. A real database disconnect preserved its checkpoint;
  the resumed run completed. INFY reached 264/1,125 before Google rejected a batch
  on the 1,000-individual-text daily quota. Stopped bulk work. Migration 0007 corrects
  shared accounting from HTTP batch envelopes to input units and reserves foreground
  headroom; it is an owner SQL step. Daily QuotaFailure/RetryInfo now stops retries.
- Froze primary-page labels, compared actual rankings and generated answers, and
  inspected citations. Found and fixed the old single-document four-passage cap,
  then compared hybrid against the corrected keyword baseline. Twelve bounded RRF
  settings were evaluated on development questions only. The completed five-case
  CCL run and seven unexecuted cases are distinguished in the committed report.
- Recall@5/@10 improves from 0.500/0.875 to 1.000/1.000 on four positive CCL questions.
  Reviewed validated-answer quality is equal at 1.75/2; warmed retrieval adds about
  0.94 seconds. A hybrid draft's unsupported EBITDA addition was caught in review
  and is now withheld by a conservative named-metric guard, including cached answers.
  Management-observation attribution remains a documented limitation.
- Tested local persisted API jobs with real primary evidence and hybrid retrieval.
  Production rollout stays off pending broader evaluation/allowance; private vectors
  remain useful cached state. No paid resources, scheduler changes or fabricated
  coverage were introduced. See HYBRID_RETRIEVAL.md and HYBRID_EVALUATION.md.


### Input-quota migration verified (31 October, 13:02 IST)

- The owner applied 0007. Both live minute/day tests now pass using individual
  batch inputs; isolated audit reservations are removed. Anonymous quota-RPC access
  is denied and embedding security status remains true.
- Cached CCL hybrid retrieval succeeds without provider calls. The deployed keyword
  workflow returns its valid cached answer; the production semantic flag stays off.
- A bounded resume after the allowance reset indexed 24 more INFY chunks, reaching
  288/1,125. The verification run has ended; it did not launch a continuous backfill.
  The earlier evaluation snapshot and its limitations remain unchanged.


### Generic new-company hybrid validation

- Used the remaining reset allowance for previously unprepared GOKEX. The same generic
  pipeline discovered an annual report and two transcripts, produced a keyword answer
  during indexing and automatically embedded all 711 chunks. Repeating the question
  then produced a hybrid answer, proving completion invalidates the partial-index cache.
  New research stays private; the watchlist and production flag are unchanged.
- Added three held-out positive questions and a negative before collecting their
  rankings. A frozen-settings scoring command reuses CCL's chosen parameters without
  tuning on the new company; it reproduces the original CCL scores unchanged.
- New-company Recall@5 improves from 0.667 to 0.833; @10 is equal at 0.833. Observed
  validated-answer quality is 1.33 versus 1.67/2, with both negative answers abstaining.
  Recorded generation/withholding effects and excerpt/date-label limitations explicitly.
  The earlier CCL report is retained; aggregate results span seven positives and two
  negatives across two complete indexes. Seven other labelled cases remain pending.
