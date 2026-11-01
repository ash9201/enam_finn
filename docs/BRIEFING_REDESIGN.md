# Briefing redesign - 1 November 2026

## Event review and ordering follow-up — 2 November

The current UI uses **Grouped by company / Chronological**, secondary company
ordering (most recent update, A–Z, most events) and newest/oldest chronology.
Review state is not part of either comparator. Equal dates/counts use full company
name/ticker or a stable event key, so marking reviewed cannot reshuffle the list.

Review counts, company indicators, filters and notifications now count **distinct
events**, regardless of supporting filings. File identities, original URLs and
page evidence are unchanged. Company headers show event count and a small outstanding
event indicator; source counts and exchange metadata do not occupy collapsed summaries.
The publication timestamp sits to the right of the title, wrapping on small screens.

`finn-event-reviews-v2` stores event receipts keyed by the existing stable relationship
key and the meaningful source content/version seen at review. Legacy `finn-read-v1`
is left intact and imported once for currently captured events: complete source reviews
remain reviewed; partial reviews with unseen evidence become **Updated since review**.
Review/Undo operates on a whole event and can restore a prior partial/updated receipt.
Unreviewed filters include updated events, with a separate updated-only option.
Identical duplicate evidence and rescan times do not invalidate a review; new or
changed supporting content does. Removed duplicate sources alone do not create new
information. Legacy flags cannot reconstruct source versions from before migration.
If browser storage fails, an explicit session-only warning is shown.

Date/category/company/significance/review filters operate on complete events.
An event matches the date window when one of its original filings matches; all its
associated sources remain available and the review applies to the complete event.
Explicit verified results and dividend references in the same filing can create
separate developments sharing the original file, each with an independent receipt.
Unstructured mixed headings are not speculatively split or merged.

**Significant** uses the existing priority 2/3 source classification; **Routine**
covers priority 0/1 informational, scheduled and administrative records;
**Unclassified** remains explicit regardless of its provisional priority. Categories
remain separate. A collapsed Review & significance disclosure explains the rules,
local persistence, date behavior and independent EOD thresholds. These labels do not
assert regulatory materiality or supply investment recommendations. Existing verified
event-specific summaries/additional details remain the explanation; no generic
"why it matters" paragraphs or new unsupported interpretations were generated.

Focused model/UI checks cover legacy migration, partial undo, stable order, all-source
retention, changed/new/duplicate evidence, combined filters, both chronology directions,
company sorts, empty windows and unchanged EOD rules across four viewport/theme scenes.
New-evidence transport replays are explicitly test-only and never write source records.
No backend, ingestion, retrieval, price calculations or model settings changed.

## Original phase record (historical)

The filing-based review model and ordering described below were superseded by the
follow-up above. The earlier NTPC grouping was also split into eight distinct events
in later source-review work; original dated observations are retained as history.

Briefing now monitors company developments rather than rendering a large card for
every exchange record. The shared header/navigation, Research, Portfolio, financial
calculations and hybrid-retrieval settings remain in use.

## Interaction and information hierarchy

- **By company** is the default. Each matching company appears once, including a
  company with only routine filings. Its collapsed row shows the full name, secondary
  NSE symbol, event previews, filing count and outstanding review count.
- Company groups and individual events expand independently. Routine sources sit in
  an expandable subsection within their company. Expand/collapse companies is also
  available. Company priority considers unreviewed events; it does not treat every
  captured filing as unread or every update as material.
- **Latest activity** lists individual announcements in publication-time order across
  companies. A nearby checkbox can include routine filings in the same chronology.
- Company/category/review filters combine with 24-hour, seven-day and custom IST
  windows. The custom end includes its displayed minute. Invalid ranges and empty
  matches are explicit. Counts describe the active filters. Related sources outside
  those filters are not silently added back.
- Review remains `finn-read-v1` browser-local state. Individual sources and entire
  events can be reviewed/unreviewed. Checkmarks, reduced emphasis and outstanding
  counts are visible; an inline undo restores the last change. No cross-device sync
  is implied, and original filing IDs remain stable.
- Unusual activity has a separate section, with discoverable expandable thresholds,
  full company names, completed-session dates and the existing price/volume maths.
  Desktop places it beside company updates; phone layouts place it below, with a
  jump link. Filing filters do not alter these whole-watchlist EOD signals. Controls
  remain available when no signal meets the thresholds.

## Source-backed details and conservative grouping

Migration `0010_briefing_enrichment.sql` adds one nullable JSON column to the existing
filing table. The owner applied it with RLS enabled. It adds no grants, new tables or
paid resources. The publishable key can read enrichment and cannot update filings.

`finn.filing_details` uses substantive NSE announcement text, native PDF narrative
passages and selected exchange XML narrative fields. It does not infer P&L figures
from tables or call an LLM. It keeps an original-source URL, page/field references,
quoted passages, source SHA-256, extraction status and original fetch/check times.
Director DINs remain inspectable in supporting/original text but are removed from
the main summary. Descriptions do not render the old category-advice templates.

Grouping requires explicit source-backed references, such as a financial-results
reporting period or a single director's identity and effective date. A common company,
publication day or filename is insufficient. Different business developments stay
separate. Every original filing remains separately accessible and reviewable.

Primary actions use explicit relevance: verified results offer Compare financials;
research-worthy updates offer Investigate; routine/scheduling records keep their
original source. A results-related meeting notice, recording or presentation does
not by itself establish an actual results statement. Primary-link styling uses a
named class, never whichever link happens to be first. Compare financials opens the
company's latest verified results; Research displays its actual reporting period.

Cached summaries use a version plus the original URL/title/description fingerprint.
PDFs are bounded to 30 MB and the first eight pages; XML is bounded to 2 MB and does
not accept declared entities. Equal PDF hashes reuse native extraction within a
batch and immutable private storage. Formatting-only corrections reuse saved evidence
and preserve original source dates. Unchanged successful records do not download again;
failed detail attempts retry after six hours. Timestamped exchange attachments are
treated as stable links, not revalidated on every scan. This is not exhaustive OCR,
full-document interpretation or detection of unannounced same-URL replacements.

The existing scheduled filing sync prepares at most six pending records per run,
independent of the sleeping API. No Gemini key or new workflow variable is required.
Operators can prepare/backfill with:

```powershell
python -m finn.filing_details --limit 60
python -m finn.filing_details --symbol NTPC --retry-unavailable --limit 20
```

Unsupported/ambiguous text remains headline-only, with its limitation and original
link. A PDF failure can retain actual exchange-feed detail; it cannot substitute a
different document or an invented explanation.

## Actual reviewed cases and checks

The review used **37 captured filings across 11 of the 15 watchlist companies**.
All original IDs, publication times, descriptions and URLs were checked against a
pre-change backup and are unchanged. At validation, 19 records have official-document
excerpts, 11 have substantive feed detail, and seven remain headline-only. Three
uncertain classifications remain visible. These counts are observations, not fixed
application rules or a claim of complete market coverage.

- **NTPC:** 12 original records become six events within one company row. Seven
  results/debt/dividend-related records share a verified September 2026 results
  package. The two tested results PDFs are the same 30-page, 18.3 MB document. Each
  exchange record retains its own link and review state. The solar commercial-
  operation disclosure stays separate.
- **KPIT:** the PDF and structured disclosure share the named director's identity
  and effective date. They form one scheduled term-completion event. Prof. Rajiv Lal
  completed his second independent-director term on 31 October 2026; this is an Update,
  not an asserted unexpected resignation. A CEO resignation still has higher priority.
- **Reliance:** recordings/presentations mentioning results are distinguished from
  results statements. The board's enabling debt-issue authorisation retains the
  disclosed **up to Rs. 15,000 crore** and does not claim funds were raised.
- **Tata Steel:** ambiguous commercial-paper table content is not promoted into an
  apparently parsed financial summary. Original evidence remains available.

Verification:

- **209 backend tests passed** in the final regression; targeted filing/classification
  tests were used during development. One pre-existing Starlette/httpx deprecation
  warning remains.
- **12 frontend model tests passed:** conservative grouping, original-source
  retention, action relevance, uncertainty, chronology and combined filter boundaries.
- Four targeted browser scenes passed: 1440x1000 and 390x844, Light and Dark, with
  320px overflow checks. They exercise the real records above, source links/passages,
  review/undo/counts, chronological routine inclusion, native keyboard expansion,
  invalid/empty windows and independent EOD thresholds. No model job is submitted.
- A labelled recorded-fallback check passed with the same 37 real filing records and
  neutral KPIT grouping. Only the bundled filing capture and its sync metadata were
  refreshed; unrelated recorded price/research captures keep their original dates.
- Build, privileged-credential asset scan, targeted Ruff and formatting checks pass.
  A repeated live enrichment run reports zero downloads, updates or pending records.

```powershell
python scripts/npm.py run test:briefing:model
python scripts/npm.py run test:briefing
python scripts/npm.py run build
python scripts/check_frontend_secrets.py
```

The browser check defaults to the local preview on port 4173 and uses a frozen copy
of actual anonymous GET responses for repeatability. Use `FINN_BROWSER_URL` for
another target. Source/inspection and before/after artifacts remain ignored under
`artifacts/briefing-redesign`. No new dependencies were installed.

## Expanded event refinement

The subsequent refinement keeps the default company list, filters, chronology,
sidebar and navigation. Company previews deduplicate titles and disappear when
the company is opened. Event headers show category and date before expansion;
scheduled tenure events explicitly label their effective date. Their short preview
disappears on expansion, leaving one explanation with distinct verified facts.
Generic support-document/media-release boilerplate does not add a second paragraph.

Expanded order is explanation, research/review actions, **Official sources**, then
**View evidence/details**. The sources are plain links with dates and useful page
references, prioritising actual results PDFs and readable notices. Every original
filing ID/URL remains intact. Multiple sources retain individual review toggles,
with Review all and undo above. Single-source events use their event review control.
One optional inspector shows a chosen document's exact excerpts, pages/fields,
original title, publication time, identifier, extraction scope and limitations.
There are no per-source cards or nested evidence disclosures.

The six original documents were rechecked, with source SHA-256 and page/field
references retained:

- KPIT's two disclosures confirm Prof. Rajiv Lal's second-term completion effective
  at close of business on 31 October 2026. The PDF page 1 and XML remarks additionally
  confirm cessation of his KPIT Technologies Inc. directorship and Nomination &
  Remuneration (HR) Committee membership that day. These facts appear once; the
  original wording remains in evidence.
- NTPC's PDF and XML both identify the **31 October 2026** audio call and the same
  company recording link (with/without `www`). They form one event with two sources.
- Reliance's PDF and XML both identify the **30 October 2026** audio call and the same
  company webcast link. They form one event with two sources. Its investor presentation
  stays separate. The period of results discussed comes from the PDF, not the XML's
  publication date.

Recording grouping requires explicit call date **and** recording URL/type; shared
headings, publication dates, company names or mutable IR landing links alone do not
group records. Conflicting/missing dates, conflicting XML fields and unsafe URLs
abstain. New ingestion uses the same parser. An optional bounded upgrade command
refreshes only previously cached recording/tenure evidence lacking the new reference:

```powershell
python -m finn.filing_details --symbol NTPC --refresh-event-evidence --limit 2
```

The local NSE `nsearchives` hostname failed to resolve during verification. Its
official `archives.nseindia.com` counterpart served the same dated paths. The bounded
extractor now tries that host on connection failure only, records the actual fetched
URL and keeps the original announcement link unchanged. Six targeted document
refreshes succeeded; no unrelated research or financial pipeline was rerun. Existing
successful references remain cached. The labelled bundled snapshot retains its
original rows/order, prices/research captures and capture metadata; only the three
companies' event evidence was updated.

Validation: **21** targeted filing-detail tests and **15** frontend model tests pass.
Four real-data browser scenes cover desktop/mobile in both themes, plus 320px
overflow, source selection/PDF-page links, per-filing review, Review all/undo, unchanged
filters/chronology and keyboard expansion. Rendered KPIT, NTPC and Reliance events
were inspected, including mobile source wrapping. Build and credential-asset scan
pass. No model jobs, migrations, environment changes or new dependencies are required.

## Event review and topic corrections

The next focused change keeps the visual layout. Every event now has a single
**Mark reviewed / Reviewed · Undo** control; source rows contain links only. Review
still persists the original filing IDs in `finn-read-v1`. Immediate event undo
restores the previous mixed state, including filings already reviewed before the
action. The existing last-action undo remains available. After reload the saved
review state remains; a reviewed event can be marked unreviewed. Company counts
and filters continue to count underlying filings. Chronological activity reuses
the same event groups, sorted by newest publication, so it also reviews an event
as a whole rather than offering different per-source review semantics.

The short NTPC descriptions were not incomplete at source. The formatter removed
the last word of unpunctuated text and capped descriptions at 450 characters.
It also inherited a 750-character initial-summary cap. These display limits are
removed. Formatting reuses the complete preserved exchange feed, recovering
**for Dividend** and **30 September 2026** without inventing words or fetching
new documents. Collapsed previews use the existing CSS line clamp; expanded
paragraphs have no character truncation. A bounded native excerpt contributes
its first complete sentence, avoiding a cropped trailing phrase. If the primary
source itself ends in ellipsis, it stays incomplete and carries an explicit note.
Extraction download/page limits remain in place; this is not a full-document or
financial-table interpretation change.

NTPC's shared 30-page attachment really includes several developments. Its cover
letter separately lists results, interim dividend/record date, debt disclosures,
issue-proceeds statements and security-cover certificates. Sharing that packet
does not make them one reviewable investor event. The 12 original filings now
form eight events:

| Development | Sources | Relationship |
|---|---:|---|
| Financial results | 2 | Actual results filings for the same reported period |
| Interim dividend and record date | 3 | PDF declaration, record-date PDF and approved XML dividend share the explicit interim type and 6 November 2026 record date |
| Issue-proceeds statement | 1 | Separate subject, not a claim of new funds raised |
| Security-cover certificate | 1 | Separate subject, with no inferred coverage ratio |
| Debt-related financial disclosures | 1 | Separate subject, no extracted debt-performance conclusion |
| Operational/financial snapshot | 1 | Remains a separate business update |
| Solar commercial operation | 1 | Remains separate |
| Earnings-call recording | 2 | Existing verified call-date/recording-link match |

Debt-topic duplicate grouping additionally requires an identical document hash;
the same quarter/subject alone cannot merge different certificates or revisions.
Dividend grouping does not use board/publication date or a shared results period.
It abstains on missing/conflicting types or record dates, and requires the XML's
explicit approval. The dividend amount comes from its substantive declaration;
record date comes from the primary references. No payment-date promise or table
conclusion is inferred. The original filing IDs, descriptions, links, timestamps,
source hashes and original PDF fetch times were preserved.

The existing generic ingestion pipeline extracts these references for new filings.
For the cached NTPC records a bounded upgrade processed eight sources, reusing
the stored PDF's native extraction across seven rows and fetching one XML. It
did not rerun price, research, model or financial-result pipelines. Cached summary
formatting required no source downloads. Operators can repeat the idempotent upgrade:

```powershell
python -m finn.filing_details --symbol NTPC --refresh-topics --limit 8
```

Validation covers 27 targeted filing-detail cases and 16 frontend model cases,
including full-word restoration, original incomplete text, safe native fragments,
distinct topics, reference conflicts and shared PDF reuse. Four browser scenes
cover desktop/mobile in both themes, the affected full descriptions, event-only
review, counts, original links, evidence inspection, chronological grouping and
legacy mixed-state undo/reload. No new migration, deployment setting or dependency
is required. Existing research/retrieval and financial calculations are unchanged.
