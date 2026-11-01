# Shared application layout - phase 1

The first redesign phase replaces application chrome, page introductions and shared
spacing. Briefing cards, the research composer/results, financial tables, evidence
drawers and portfolio cards retain their existing contents and interactions.

- Desktop (768px and above): one compact persistent header with section navigation,
  a small wordmark and the existing Light/Dark/System selector.
- Mobile: the same header plus a full-width bottom navigation row. Both sit outside
  the scrolling page. Safe-area insets and `100dvh` prevent content from extending
  underneath either control; financial tables retain their own horizontal scrolling.
- Shared titles are Your Briefing, Company Research and Your Portfolio. Promotional
  introductions/footer copy and the large four-column summary are removed. Relevant
  counts sit beside filings/signals or the demo watchlist; freshness stays visible.
- `layout.css` owns shared spacing tokens, gutters, heading size, common container
  padding and navigation. Existing semantic palette tokens serve both themes.

## Navigation and state

The small History API shell mounts views on first visit and retains them for that
browser session. Switching sections keeps drafts, results, evidence context, financial
basis, filters, open settings and scroll position. Hidden views are also `inert`;
only the visible main/navigation is exposed to assistive technology. Navigation uses
native links, browser Back/Forward and a keyboard skip link, with focus moved to the
active main after section changes. Theme selection remains global and persistent.

Explicit research links from filings/portfolio open the requested company even if
the same URL was visited before. They intentionally begin a new research entry.
Background research jobs continue across ordinary section switches. Source modals
close when leaving Research, while the follow-up context remains available on return.
Inactive Briefing/Portfolio polling pauses; shared alert preferences are reconciled
when a view becomes active, with session memory when storage is blocked. Reloading still uses existing cache/preferences rather
than persisting the entire research workspace in browser storage.

## System Status

`/?view=status` is accessible through a quiet footer link and has a Back to FINN
action returning to the previous section. The old `/?view=foundation` URL remains
an alias, without milestone/setup copy. Live API liveness and live public saved-data
access are checked separately with timestamps, cancellation and retry. This page
does not claim to verify model availability, market-data freshness or document
coverage. It does not use a historical fallback as proof of connectivity. Normal
errors stay within their page.

## Targeted acceptance

Run a configured local frontend and existing API, or build the preview using the
deployed API URL. No dependency installation or schema changes are needed.

```powershell
python scripts/npm.py run build
python scripts/check_frontend_secrets.py
python scripts/npm.py run test:layout
python scripts/npm.py run test:browser
```

`test:layout` defaults to `http://127.0.0.1:4173`; `test:browser` defaults to the dev
server. Set `FINN_BROWSER_URL` for another target. Read-only API responses are relayed
for local-preview CORS in the harness; no production CORS settings change.

Acceptance covers 390x844 and 1440x1000 in both themes, plus 320px width and short
landscape geometry. Checks include single visible landmarks, active navigation,
draft/filter/scroll preservation, history, deliberate company links, NTPC basis
retention, unobscured content, real figure evidence/follow-up context, theme switching
and keyboard focus. A separate transport simulation uses an unchanged real saved
INFY answer to verify in-flight job retention and inline service errors without
calling a model. Shared alert preferences and mobile/desktop status failures are
checked too. Screenshots/results remain ignored in `artifacts/shared-layout` and
`artifacts/status-browser`.

All five layout/state scenes and both status viewport checks passed. A targeted
blocked-storage check also passed for shared session thresholds and theme switching.

TypeScript/Vite build and privileged-credential asset scan pass. No backend, ingestion,
retrieval, financial arithmetic, schema or model settings changed; unrelated backend
tests were not rerun for each theme. Page-specific redesign work remains for later phases.
