# Briefing redesign - 1 November 2026

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
