# Portfolio watchlist redesign — 2 November 2026

Portfolio uses a sortable table above 850px and compact responsive rows below
that breakpoint. Both are the same semantic table and data; no duplicate card
interface or new dependency is introduced. Full company names, sectors, per-share
Last close, signed 1D change, attention indicators and Research actions stay visible.
Company-name buttons expand trading volume, volume ratio and source limitations.

## Existing data and attention rules

- The existing anonymous Supabase company, price, filing and sync-status reads
  are unchanged. Watchlist membership remains 15; researched companies outside
  the watchlist cannot affect the common date or rows.
- Close and percentage values are formatted from saved observations, without
  recalculating EOD returns. Missing figures stay unavailable. Positive/negative
  percentages include a sign, alongside their existing theme colours.
- Price and volume signals use the existing browser-local thresholds (default
  ±4% and 2× prior 20-session average). The exact predicate is shared with Briefing.
  Failed price fetches cannot create signals from retained values.
- Recent-event counts use the existing Briefing grouping of non-routine captured
  filings within seven days. These count events rather than individual PDFs,
  exclude future records, and retain all source identities/review state in Briefing.
- **Prioritize unusual activity** is a separate checkbox, enabled by default.
  Companies crossing either configured threshold form the first group; one versus
  two triggers does not add an implicit ranking. The selected sort applies within
  both groups. With the checkbox off, it applies across all companies.
- Default sort is most recent captured activity. Other choices include oldest
  activity, company A–Z/Z–A, daily gain/decline and event count. Missing values sort
  last in either direction; ties use company name A–Z and ticker. There is no added
  investment score or recommendation. Alert thresholds sits beside these controls;
  browser-local persistence is explained in Methodology instead of repeated captions.
- Event links open the company's seven-day Briefing with its group expanded.
  Explicit links reset retained filters; normal section switching preserves them.
  Research links continue using canonical symbols, including encoded `M&M`.

## Freshness and attribution

The latest valid saved watchlist session appears once above the table, explicitly
labelled **End-of-day prices / Not live**. Verification observed **30 October 2026**
in the live saved data. This is not a claim that a new session was fetched.

Data sources / Methodology contains the actual common saved source note, threshold
definitions, capture limitations and successful sync times. Current data attributes
the latest close/volume to the NSE daily file and prior 20 sessions to Yahoo Finance.
Each row preserves its original HTTPS source link as a secondary action. A different
source note is surfaced for that row and retained in its details.

Older sessions relative to the common saved session, failed refreshes and missing
prices get local warnings. Failed refreshes preserve and label their actual saved
close; missing data never becomes zero. The common absolute date and shared sync
warnings remain visible. No new holiday calendar or live-market claim is introduced.
Existing labelled recorded-snapshot recovery is unchanged.

The 2 November follow-up moves unadjusted-close/split methodology into the shared
Methodology disclosure. The old sentence was emitted for every company, regardless
of an actual split. Rows now retain only recorded `price_change_note`, `volume_note`,
or other specific adjustment details. New snapshots attach a daily-suppression note
only when the existing split guard actually suppressed the daily comparison.
Legacy generic captions are hidden without inferring that a split occurred. Price
and volume calculations, thresholds, source links, sorting and row expansion are unchanged.

## Targeted verification

```powershell
python scripts/npm.py run test:portfolio:model
python scripts/npm.py run test:briefing:model
python scripts/npm.py run build
python scripts/check_frontend_secrets.py
# Serve frontend/dist on 4173, then:
python scripts/npm.py run test:portfolio
```

Six model tests cover boundary thresholds, unavailable/failed values, signed
sorting, attention ordering, real recorded filing grouping, valid session dates,
source preservation and encoded company identities. Recorded model fixtures are
explicitly historical; browser checks capture live anonymous Supabase responses
once per run and replay those same responses across scenes.

Browser verification passed at 1440px and 390px in both light and dark themes,
with a 320px overflow check. It checks all 15 companies' values, sources, signals
and links; sorting; keyboard expansion; shared settings; section-state preservation;
repeated filtered Briefing navigation; Research selection; and rendered text contrast.
Two additional, explicitly browser-only failure replays check missing data, retained
saved closes without alerts, error details and preferences after reload. They never
write to Supabase or change actual saved prices.

Ignored `artifacts/portfolio-redesign/` contains the JSON checks, captured source
responses and four screenshots used for visual inspection. Existing smoke/demo
selectors and the price-provenance check were updated for rows and central metadata.
The cheap model test also runs in CI. No research generation, ingestion, financial
calculation or backend source pipeline was run for this frontend task.
