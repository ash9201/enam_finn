# Research workspace redesign — 1 November 2026

Research now uses the shared compact layout, with company discovery, a custom
question and four immediate actions together. Backend identity, retrieval,
generation, citation validation and financial calculations are unchanged.

## Company discovery

`frontend/public/company-directory.json` is a dated capture of **2,620** listings
from NSE's equity directory, with connected official name/symbol histories:

- [Equity directory](https://archives.nseindia.com/content/equities/EQUITY_L.csv)
- [Symbol changes](https://archives.nseindia.com/content/equities/symbolchange.csv)
- [Name changes](https://archives.nseindia.com/content/equities/namechange.csv)

The asset loads once per page, then searches locally. It ranks exact symbols and
names, prefixes, historical identities/acronyms and word matches before using
small spelling-distance matches when there are no direct matches. Shorter prefix
names rank before longer ones. There is no external request per keystroke and no
LLM company resolution. Histories connect back to current names; future-dated
changes are excluded. The listing remains authoritative, rather than an old alias.

`Jindal`, `Jindal Steel`, `JINDALSTEEL` and a small typo find **JINDALSTEL**;
other Jindal entities retain separate names and symbols. `JSPL`, `HUL`, `L&T`,
`M&M` and historical `SAWPIPES` are covered by name/acronym/history matching.
Ambiguous matches require explicit selection. Enter commits an active option or
a unique suggestion; it never automatically chooses among ambiguous matches.
Only the canonical symbol is passed into the existing research workflow.

The selected full name/ticker and Change company action remain visible. A compact
watchlist disclosure opens the 15 full-name entries; it is collapsed normally.
Recent choices appear within discovery. The search shows its directory date and
can fall back, visibly, to the existing watchlist if the asset is unavailable.
This is the same equity-directory universe used by the backend resolver; it is
not a new source of company research facts or an assertion of instant listing updates.

Refresh the committed directory deliberately; deployment does not contact NSE:

```powershell
python scripts/update_company_directory.py
```

## Research actions and state

All four actions sit immediately below the question and execute in one click:

| Action | Existing workflow |
|---|---|
| Quarterly results | Exact quarterly-results question and validated financial-cell renderer |
| Management outlook | Demand/growth question through company-grounded research |
| Business risks | Risk question through company-grounded research |
| Track management statements | Existing statement-versus-later-evidence comparison question |

Available saved results/comparisons open immediately with their original dates.
A click waits for an already pending saved-answer read before starting the API,
avoiding an unnecessary cold-start request. Other requests retain normal job
polling and progress. An optional refresh leaves valid research visible and reports
failure without replacing it with an unrelated answer.

A late overview read could previously overwrite a result selected with a quick
action. Selection/request generations now guard the active result independently
from saved specialized metadata. Selecting the same saved result is idempotent,
preserving its accounting-basis selection. Comparisons render only when selected,
inside the single answer panel; their old detached trigger and automatic second
panel are removed.

Canonical selection, per-company question drafts and last standard result mode
persist locally. In-memory per-company workspaces preserve answers, evidence
context and investigation trails across company/view navigation, including deliberate
company links. Updating the company URL also updates navigation's remembered
Research location without remounting the page. Full private answers/trails are not
serialized into localStorage; after reload the last available standard saved view
can be reopened while the custom draft remains editable. No cross-device sync is implied.

## Reading and evidence

Panels use the shared spacing tokens. Answers retain readable 14–15px paragraphs
and claim-level source actions, with smaller gaps and no decorative claim-number
column. Report/transcript counts, indexing/retrieval state, processing notes and
timing are inside existing expandable details. Material missing-data notices and
answer/source dates remain visible. The evidence drawer, source verification,
page links, source-cell inspection, calculations and contextual follow-ups are reused.

Financial figures keep their original units, periods, bases and calculations.
Phone tables scroll horizontally instead of shrinking or breaking financial
numbers. The metric column remains visible. With two supported bases, the selector
updates the table, figures, narrative and evidence indices. With one supported
basis, a plain label and explicit unavailable-basis message replace ineffective tabs.

## Verification and limits

- Five local search tests use the actual directory: canonical identities, names,
  aliases, ambiguity, typos and unknown inputs. CI runs these alongside existing checks.
- Four UI scenes cover desktop/mobile in Light/Dark, including keyboard discovery,
  one directory fetch per page load, full-name watchlist, selection/draft/answer
  retention, reload, all four actions, citations, evidence context, numeric basis
  changes, contrast and 320px overflow.
- The first live CCL scene executed all four actions. Results and the existing
  comparison used saved analyses; outlook and risks completed through the API with
  four and six source-backed claims respectively. Those exact responses were reused
  in subsequent visual scenes to avoid repeat model work.
- Current published **NTPC** and **SUNPHARMA** datasets each have distinct standalone
  and consolidated revenue values and one row per metric. Both are verified in the
  UI. NTPC's current source data did not require a financial/arithmetic correction.
  Each requested result renders one financial section, one reported-figures table
  and one changes table; repeated results clicks preserve the selected basis.
- Additional focused checks delay an overview response, simulate a failed refresh
  while retaining valid figures, and display a genuine archived standalone-only
  NTPC answer. No figures are fabricated for the unavailable-basis case.
- No unrelated research/source ingestion pipeline or backend test suite was rerun
  locally for each theme. Build and emitted-asset credential checks pass.

Capture real fixtures into the ignored artifacts directory, then run targeted checks:

```powershell
python scripts/capture_research_ui_fixtures.py
python scripts/npm.py run test:company-search
python scripts/npm.py run test:research-redesign
python scripts/npm.py run build
python scripts/check_frontend_secrets.py
```

The capture uses the owner's existing server-side project credentials and does not
publish private fixtures. `FINN_VERIFY_LIVE_ACTIONS=1` enables live actions for the
first scene only; subsequent scenes replay the captured real answers. Default runs
require already captured CCL outlook/risk results. Latency/failure simulations are
test-only. API requests during local UI testing use a transparent test relay for
the deployment's CORS boundary. Production continues using its existing API URL.
No new dependency, migration, service or environment variable is required.
