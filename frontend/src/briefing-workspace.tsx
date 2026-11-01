import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import './briefing-workspace.css'
import BriefingEvidence from './briefing-evidence'
import {
  eventReceipt,
  orderEvents,
  reviewState,
  selectEvents,
  type EventReviews,
  type EventReceipt,
  type ReviewChanges,
} from './event-reviews'
import {
  CATEGORIES,
  companyPreview,
  eventCategory,
  eventExplanation,
  eventSources,
  sourceLabel,
  dateBounds,
  eventTone,
  groupEvents,
  presentation,
  primaryAction,
  type Company,
  type Filing,
  type FilingEvent,
  type FilingFilters,
} from './briefing-model'

type Signal = {
  symbol: string
  data: {
    last_session: string
    price_change_pct: number | null
    volume_ratio: number | null
  } | null
}
const stamp = (value: string) =>
  new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  }).format(new Date(value)) + ' IST'
const research = (symbol: string) => `/?view=research&symbol=${encodeURIComponent(symbol)}`

export default function BriefingWorkspace({
  filings,
  companies,
  reviews,
  reviewStorageWarning,
  onReview,
  signals,
  settings,
  settingsOpen,
  onSettings,
  priceThreshold,
  volumeThreshold,
  entryUrl,
  entryKey,
}: {
  filings: Filing[]
  companies: Company[]
  reviews: EventReviews
  reviewStorageWarning: boolean
  onReview: (changes: ReviewChanges) => void
  signals: Signal[]
  settings: ReactNode
  settingsOpen: boolean
  onSettings: () => void
  priceThreshold: number
  volumeThreshold: number
  entryUrl?: string
  entryKey?: number
}) {
  const [filters, setFilters] = useState<FilingFilters>({
    company: '',
    category: '',
    review: 'all',
    window: '24h',
    start: '',
    end: '',
  })
  const [view, setView] = useState('company')
  const [companySort, setCompanySort] = useState('recent')
  const [chronology, setChronology] = useState('desc')
  const [includeRoutine, setIncludeRoutine] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  useEffect(() => {
    const params = new URL(entryUrl || window.location.href, window.location.origin).searchParams
    const company = params.get('company')
    if (!company || !/^[A-Z0-9&-]{1,30}$/.test(company)) return
    setFilters({
      company,
      category: '',
      review: 'all',
      window: params.get('window') === '24h' ? '24h' : '7d',
      start: '',
      end: '',
    })
    setView('company')
    setExpanded((previous) => new Set([...previous, `main:${company}`]))
  }, [entryUrl, entryKey])
  const [undo, setUndo] = useState<{ previous: ReviewChanges; count: number } | null>(null)
  const eventReviews = useRef(new Map<string, EventReceipt | null>())
  const allEvents = useMemo(() => groupEvents(filings), [filings])
  const events = selectEvents(allEvents, filters, reviews)
  const routine = events.filter((event) => event.priority === 0)
  const showRoutine = includeRoutine || filters.significance === 'routine' || !!filters.category
  const displayedEvents =
    view === 'company' ? events : events.filter((event) => showRoutine || event.priority > 0)
  const unreviewed = displayedEvents.filter(
    (event) => reviewState(event, reviews) !== 'reviewed',
  ).length
  const visibleExpanded = events.some((event) => expanded.has(`main:${event.symbol}`))
  const bounds = dateBounds(filters)
  const companyName = (symbol: string) =>
    companies.find((c) => c.symbol === symbol)?.name ||
    filings.find((f) => f.symbol === symbol)?.company_name ||
    symbol
  const updateFilter = (key: keyof FilingFilters, value: string) =>
    setFilters((previous) => ({ ...previous, [key]: value }))
  function changeReview(changes: ReviewChanges) {
    setUndo({
      previous: Object.fromEntries(
        Object.keys(changes).map((key) => [key, reviews.receipts[key] || null]),
      ),
      count: Object.keys(changes).length,
    })
    onReview(changes)
  }
  function undoReview() {
    if (!undo) return
    onReview(undo.previous)
    setUndo(null)
  }
  function reviewEvent(event: FilingEvent) {
    if (reviewState(event, reviews) !== 'reviewed') {
      eventReviews.current.set(event.key, reviews.receipts[event.key] || null)
      changeReview({ [event.key]: eventReceipt(event) })
    } else changeReview({ [event.key]: eventReviews.current.get(event.key) || null })
  }

  function sourceRow(filing: Filing) {
    const detail = presentation(filing)
    const page = detail.evidence.find((e) => e.pdf_page)?.pdf_page
    const label = sourceLabel(filing)
    return (
      <li className="filing-source" key={filing.id} data-filing-id={filing.id}>
        <div className="filing-source-link">
          {filing.source_url.startsWith('https://') ? (
            <a
              className="original-filing"
              href={filing.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {label} <span aria-hidden="true">&#8599;</span>
            </a>
          ) : (
            <span>{label}</span>
          )}
          <span className="source-reference">
            <time dateTime={filing.published_at}>
              {new Intl.DateTimeFormat('en-IN', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
                timeZone: 'Asia/Kolkata',
              }).format(new Date(filing.published_at))}
            </time>
            {page ? ` · p. ${page}` : ''}
          </span>
        </div>
      </li>
    )
  }

  function eventRow(event: FilingEvent, withCompany = false) {
    const state = reviewState(event, reviews),
      outstanding = state !== 'reviewed'
    const tone = eventTone(event),
      action = primaryAction(event)
    const explanation = eventExplanation(event)
    const effective = event.filings.map((f) => presentation(f).effective_date).find(Boolean)
    return (
      <article
        className={`filing-event ${outstanding ? '' : 'is-reviewed'}`}
        data-event-key={event.key}
        data-published-at={event.newest}
        key={event.key}
      >
        <details className="event-details">
          <summary className="event-summary">
            <span className="event-chevron" aria-hidden="true">
              &#8250;
            </span>
            <span className="event-summary-content">
              {withCompany && (
                <span className="activity-company">
                  {companyName(event.symbol)} <small>{event.symbol}</small>
                </span>
              )}
              <span className="event-title-line">
                <span className="event-title">{event.title}</span>
                <time className="event-timestamp" dateTime={event.newest}>
                  {stamp(event.newest)}
                </time>
              </span>
              <span className="event-meta">
                <span className="event-category">{eventCategory(event)}</span>
                <span className={`event-priority ${tone.key}`}>{tone.label}</span>
                <span className={`review-state ${state}`}>
                  {state === 'updated'
                    ? 'Updated since review'
                    : outstanding
                      ? 'Unreviewed'
                      : '\u2713 Reviewed'}
                </span>
                {effective && (
                  <span className="event-effective">
                    Effective{' '}
                    {new Intl.DateTimeFormat('en-IN', {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                      timeZone: 'Asia/Kolkata',
                    }).format(new Date(effective + 'T00:00:00+05:30'))}
                  </span>
                )}
              </span>
              <span className="event-snippet">
                {explanation || 'Headline only · verified event details are not yet available.'}
              </span>
            </span>
          </summary>
          <div className="event-body">
            <p className="event-full-summary">
              {explanation ||
                'Only the exchange headline is available. Detailed event facts have not been extracted.'}
            </p>
            {event.filings.some((filing) => presentation(filing).summary_incomplete) && (
              <p className="source-check-note">
                The available source excerpt is incomplete. Open the original filing for full
                context.
              </p>
            )}
            <div className="event-actions">
              {action && (
                <a
                  className="filing-primary-action"
                  href={action.href}
                  title={
                    event.actualResults
                      ? 'Open this company’s latest verified quarterly results; check the reporting period in Research.'
                      : undefined
                  }
                >
                  {action.label} &#8599;
                </a>
              )}
              <button
                className="review-toggle"
                aria-pressed={!outstanding}
                onClick={() => reviewEvent(event)}
              >
                {outstanding ? 'Mark reviewed' : '✓ Reviewed · Undo'}
              </button>
            </div>
            <div className="official-sources">
              <h4>Official sources</h4>
              <ul className="event-sources" aria-label="Original announcements">
                {eventSources(event).map(sourceRow)}
              </ul>
            </div>
            <BriefingEvidence event={event} />
          </div>
        </details>
      </article>
    )
  }

  function companyGroups(items: FilingEvent[], idPrefix: string) {
    const groups = new Map<string, FilingEvent[]>()
    for (const event of items)
      groups.set(event.symbol, [...(groups.get(event.symbol) || []), event])
    const alphabetical = (a: [string, FilingEvent[]], b: [string, FilingEvent[]]) =>
      companyName(a[0]).localeCompare(companyName(b[0]), 'en-IN') || a[0].localeCompare(b[0])
    return [...groups]
      .sort((a, b) => {
        if (companySort === 'count') return b[1].length - a[1].length || alphabetical(a, b)
        if (companySort === 'recent')
          return (
            Math.max(...b[1].map((event) => Date.parse(event.newest))) -
              Math.max(...a[1].map((event) => Date.parse(event.newest))) || alphabetical(a, b)
          )
        return alphabetical(a, b)
      })
      .map(([symbol, companyEvents]) => {
        const key = `${idPrefix}:${symbol}`
        const remaining = companyEvents.filter(
          (event) => reviewState(event, reviews) !== 'reviewed',
        ).length
        const ordered = orderEvents(companyEvents)
        return (
          <details
            className={`company-group ${remaining ? '' : 'is-reviewed'}`}
            data-symbol={symbol}
            key={key}
            open={expanded.has(key)}
            onToggle={(e) => {
              const open = e.currentTarget.open
              setExpanded((previous) => {
                if (previous.has(key) === open) return previous
                const next = new Set(previous)
                if (open) next.add(key)
                else next.delete(key)
                return next
              })
            }}
          >
            <summary className="company-summary">
              <span className="company-chevron" aria-hidden="true">
                ›
              </span>
              <span className="company-summary-content">
                <span className="company-name">{companyName(symbol)}</span>
                <span className="company-ticker">{symbol}</span>
                <span className="company-preview">
                  {companyPreview(ordered)}
                  {ordered.length > 2 ? ` · +${ordered.length - 2} more` : ''}
                </span>
              </span>
              <span className="company-counts">
                <span>
                  {companyEvents.length} {companyEvents.length === 1 ? 'event' : 'events'}
                </span>
                {remaining > 0 && <small>{remaining} unreviewed</small>}
              </span>
            </summary>
            <div className="company-events">
              {ordered
                .filter((event) => showRoutine || event.priority > 0)
                .map((event) => eventRow(event))}
              {!showRoutine && ordered.some((event) => event.priority === 0) && (
                <details className="routine-section">
                  <summary className="routine-toggle">
                    <span>
                      Additional routine events{' '}
                      <small>{ordered.filter((event) => event.priority === 0).length} events</small>
                    </span>
                    <span aria-hidden="true">＋</span>
                  </summary>
                  {ordered.filter((event) => event.priority === 0).map((event) => eventRow(event))}
                </details>
              )}
            </div>
          </details>
        )
      })
  }

  return (
    <div className="briefing-monitor">
      <section className="filing-controls" aria-labelledby="filings-heading">
        <div className="filing-controls-heading">
          <div>
            <h2 id="filings-heading">Company updates</h2>
            <p className="sr-only" role="status">
              {displayedEvents.length} events in this view; {unreviewed} unreviewed.
            </p>
          </div>
          <div className="briefing-display-controls">
            <div className="view-options" role="group" aria-label="Announcement view">
              {[
                ['company', 'Grouped by company'],
                ['latest', 'Chronological'],
              ].map(([value, title]) => (
                <button key={value} aria-pressed={view === value} onClick={() => setView(value)}>
                  {title}
                </button>
              ))}
            </div>
            <div className="briefing-order">
              <label>
                {view === 'company' ? 'Company order' : 'Event order'}
                {view === 'company' ? (
                  <select
                    aria-label="Company order"
                    value={companySort}
                    onChange={(event) => setCompanySort(event.target.value)}
                  >
                    <option value="recent">Most recent update</option>
                    <option value="name">Company A-Z</option>
                    <option value="count">Most events</option>
                  </select>
                ) : (
                  <select
                    aria-label="Event order"
                    value={chronology}
                    onChange={(event) => setChronology(event.target.value)}
                  >
                    <option value="desc">Newest first</option>
                    <option value="asc">Oldest first</option>
                  </select>
                )}
              </label>
            </div>
          </div>
        </div>
        <div className="filing-filters">
          <label>
            Company
            <select
              value={filters.company}
              onChange={(e) => updateFilter('company', e.target.value)}
            >
              <option value="">All companies</option>
              {companies.map((c) => (
                <option key={c.symbol} value={c.symbol}>
                  {c.name} ({c.symbol})
                </option>
              ))}
            </select>
          </label>
          <label>
            Category
            <select
              value={filters.category}
              onChange={(e) => updateFilter('category', e.target.value)}
            >
              <option value="">All categories</option>
              {Object.entries(CATEGORIES).map(([value, title]) => (
                <option key={value} value={value}>
                  {title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Review status
            <select value={filters.review} onChange={(e) => updateFilter('review', e.target.value)}>
              <option value="all">All</option>
              <option value="unreviewed">Unreviewed</option>
              <option value="reviewed">Reviewed</option>
              <option value="updated">Updated since review</option>
            </select>
          </label>
          <label>
            Significance
            <select
              value={filters.significance || ''}
              onChange={(event) => updateFilter('significance', event.target.value)}
            >
              <option value="">All significance</option>
              <option value="significant">Significant</option>
              <option value="routine">Routine</option>
              <option value="unclassified">Unclassified</option>
            </select>
          </label>
        </div>
        <div className="filing-date-bar">
          <span>Filing date</span>
          <div className="window-options" role="group" aria-label="Filing time window">
            {[
              ['24h', '24 hours'],
              ['7d', '7 days'],
              ['custom', 'Custom'],
            ].map(([value, title]) => (
              <button
                key={value}
                aria-pressed={filters.window === value}
                onClick={() => updateFilter('window', value)}
              >
                {title}
              </button>
            ))}
          </div>
          <button
            className="filter-reset"
            onClick={() =>
              setFilters({
                company: '',
                category: '',
                significance: '',
                review: 'all',
                window: '24h',
                start: '',
                end: '',
              })
            }
          >
            Reset filters
          </button>
        </div>
        {filters.window === 'custom' && (
          <div className="custom-window">
            <label>
              From (IST)
              <input
                type="datetime-local"
                value={filters.start}
                onChange={(e) => updateFilter('start', e.target.value)}
              />
            </label>
            <label>
              To (IST)
              <input
                type="datetime-local"
                value={filters.end}
                onChange={(e) => updateFilter('end', e.target.value)}
              />
            </label>
          </div>
        )}
        {!bounds.valid && (
          <p className="coverage-warning" role="alert">
            Choose an end time after the start time.
          </p>
        )}
        <a className="market-jump" href="#signals-heading">
          Unusual activity &amp; thresholds &darr;
        </a>
        <details className="briefing-method">
          <summary>Review &amp; significance</summary>
          <p>
            Each distinct event is one reviewable item, regardless of its sources. Reviews and alert
            thresholds are saved in this browser. Date filters match captured filings; included
            events retain all their sources. New or changed supporting evidence is marked Updated
            since review and remains in Unreviewed.
          </p>
          <p>
            Significant means the existing classification assigns priority 2 or 3 (for example
            reported results or consequential business developments). Routine covers scheduled,
            informational and administrative disclosures at priority 0 or 1. Unclassified means
            classification is still pending. These labels do not establish regulatory materiality or
            investment advice.
          </p>
          <p>
            Companies use the selected order; events within each company use newest update first.
            Equal dates or counts use company name, then ticker; equal event times use a stable
            event key. Reviewing an event does not change its sort position. EOD alerts use
            completed sessions independently of filing-date filters.
          </p>
        </details>
        {reviewStorageWarning && (
          <p className="coverage-warning" role="status">
            Review changes are kept for this session because browser storage is unavailable.
          </p>
        )}
      </section>
      {undo && (
        <div className="review-feedback" role="status">
          <span>
            Review state updated for {undo.count} {undo.count === 1 ? 'event' : 'events'}.
          </span>
          <button className="text-button" onClick={undoReview}>
            Undo last change
          </button>
          <button
            className="review-dismiss"
            aria-label="Dismiss review message"
            onClick={() => setUndo(null)}
          >
            ×
          </button>
        </div>
      )}
      <div className="briefing-workspace">
        <section
          className="announcement-list"
          aria-label={view === 'company' ? 'Announcements by company' : 'Latest announcements'}
        >
          <div className="list-heading">
            <span>
              {view === 'company'
                ? `${new Set(events.map((e) => e.symbol)).size} companies with captured updates`
                : 'Newest announcements first · publication time'}
            </span>
            {view === 'company' && events.length > 0 ? (
              <button
                className="text-button"
                onClick={() =>
                  setExpanded(
                    visibleExpanded ? new Set() : new Set(events.map((e) => `main:${e.symbol}`)),
                  )
                }
              >
                {visibleExpanded ? 'Collapse companies' : 'Expand companies'}
              </button>
            ) : (
              routine.length > 0 && (
                <label className="include-routine">
                  <input
                    type="checkbox"
                    checked={includeRoutine}
                    onChange={(e) => setIncludeRoutine(e.target.checked)}
                  />
                  Include {routine.length} additional routine events
                </label>
              )
            )}
          </div>
          {view === 'company'
            ? companyGroups(events, 'main')
            : orderEvents(displayedEvents, chronology).map((event) => eventRow(event, true))}
          {bounds.valid &&
            (view === 'company'
              ? !events.length
              : !events.some((event) => showRoutine || event.priority > 0)) && (
              <div className="briefing-empty">
                <h3>No events match this view</h3>
                <p>
                  This reflects captured announcements, not proof that no event occurred. Include
                  routine items, change the filters or widen the date range.
                </p>
                {filters.window !== '7d' && (
                  <button className="text-button" onClick={() => updateFilter('window', '7d')}>
                    Review the last 7 days
                  </button>
                )}
              </div>
            )}
        </section>
        <aside className="market-monitor" aria-labelledby="signals-heading">
          <div className="market-monitor-heading">
            <h2 id="signals-heading" tabIndex={-1}>
              Unusual activity
            </h2>
            <button
              className="text-button"
              aria-expanded={settingsOpen}
              aria-controls="briefing-settings"
              onClick={onSettings}
            >
              Alert thresholds
            </button>
          </div>
          <p className="market-clock">Completed sessions · whole watchlist</p>
          {settingsOpen && settings}
          <p className="signal-count">
            {signals.length} signals at ±{priceThreshold}% or {volumeThreshold}× volume
          </p>
          {signals.map((signal) => {
            const data = signal.data!,
              move = data.price_change_pct,
              moved = move !== null && Math.abs(move) >= priceThreshold
            return (
              <article className="signal-row" key={signal.symbol}>
                <div>
                  <strong>{companyName(signal.symbol)}</strong>
                  <span>{signal.symbol}</span>
                </div>
                <p className={`signal-value ${moved ? (move! < 0 ? 'negative' : 'positive') : ''}`}>
                  {moved
                    ? `${move! > 0 ? '+' : ''}${move!.toFixed(2)}%`
                    : `${data.volume_ratio?.toFixed(2)}×`}{' '}
                  <small>{moved ? 'daily move' : 'usual volume'}</small>
                </p>
                <p className="signal-session">
                  Session {data.last_session}
                  {data.volume_ratio !== null && moved
                    ? ` · Volume ${data.volume_ratio.toFixed(2)}×`
                    : ''}
                </p>
                <a className="investigate-link" href={research(signal.symbol)}>
                  Investigate ↗
                </a>
              </article>
            )
          })}
          {!signals.length && (
            <p className="signal-empty">
              No qualifying signals in the available completed-session data. Check coverage below
              for missing or failed prices.
            </p>
          )}
          <p className="market-clock">
            Volume uses the prior 20 trading sessions. These signals are independent of the filing
            filters.
          </p>
        </aside>
      </div>
    </div>
  )
}
