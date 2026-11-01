import { useState, type ReactNode } from 'react'
import './briefing-workspace.css'
import {
  CATEGORIES,
  dateBounds,
  eventTone,
  groupEvents,
  makeEvent,
  presentation,
  primaryAction,
  selectFilings,
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
  read,
  onReview,
  signals,
  settings,
  settingsOpen,
  onSettings,
  priceThreshold,
  volumeThreshold,
}: {
  filings: Filing[]
  companies: Company[]
  read: string[]
  onReview: (ids: string[], reviewed: boolean) => void
  signals: Signal[]
  settings: ReactNode
  settingsOpen: boolean
  onSettings: () => void
  priceThreshold: number
  volumeThreshold: number
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
  const [includeRoutine, setIncludeRoutine] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [undo, setUndo] = useState<{
    ids: string[]
    previous: Set<string>
    reviewed: boolean
  } | null>(null)
  const reviewed = new Set(read)
  const matching = selectFilings(filings, filters, reviewed)
  const events = groupEvents(matching)
  const routine = events.filter((event) => event.priority === 0)
  const unreviewed = matching.filter((filing) => !reviewed.has(filing.id)).length
  const visibleExpanded = events.some((event) => expanded.has(`main:${event.symbol}`))
  const bounds = dateBounds(filters)
  const companyName = (symbol: string) =>
    companies.find((c) => c.symbol === symbol)?.name ||
    filings.find((f) => f.symbol === symbol)?.company_name ||
    symbol
  const updateFilter = (key: keyof FilingFilters, value: string) =>
    setFilters((previous) => ({ ...previous, [key]: value }))
  function changeReview(ids: string[], value: boolean) {
    setUndo({ ids, previous: new Set(read), reviewed: value })
    onReview(ids, value)
  }
  function undoReview() {
    if (!undo) return
    onReview(
      undo.ids.filter((id) => undo.previous.has(id)),
      true,
    )
    onReview(
      undo.ids.filter((id) => !undo.previous.has(id)),
      false,
    )
    setUndo(null)
  }

  function sourceRow(filing: Filing, controls: boolean) {
    const detail = presentation(filing),
      isReviewed = reviewed.has(filing.id)
    const url = filing.source_url.startsWith('https://') ? filing.source_url : null
    return (
      <li
        className={`filing-source ${isReviewed ? 'is-reviewed' : ''}`}
        key={filing.id}
        data-filing-id={filing.id}
      >
        <div className="filing-source-heading">
          <strong>{filing.title}</strong>
          <time dateTime={filing.published_at}>{stamp(filing.published_at)}</time>
        </div>
        {controls && (
          <div className="filing-source-actions">
            {url && (
              <a href={url} target="_blank" rel="noopener noreferrer" className="original-filing">
                Original filing ↗
              </a>
            )}
            <button
              className="review-toggle"
              aria-pressed={isReviewed}
              onClick={() => changeReview([filing.id], !isReviewed)}
            >
              {isReviewed ? '✓ Reviewed · Undo' : 'Mark reviewed'}
            </button>
          </div>
        )}
        <details className="source-passages">
          <summary>Filing details &amp; supporting text</summary>
          <dl className="filing-source-meta">
            <div>
              <dt>Exchange title</dt>
              <dd>{filing.title}</dd>
            </div>
            <div>
              <dt>Category</dt>
              <dd>{CATEGORIES[detail.category] || detail.category}</dd>
            </div>
          </dl>
          {detail.interpretation && <p>{detail.interpretation}</p>}
          {detail.evidence.length ? (
            detail.evidence.map((e, index) => (
              <div className="filing-excerpt" key={index}>
                <span>
                  {e.kind === 'exchange_feed'
                    ? 'NSE announcement text'
                    : e.pdf_page
                      ? `Official filing · PDF page ${e.pdf_page}`
                      : 'Official exchange structured disclosure'}
                </span>
                <blockquote>{e.quote}</blockquote>
                {e.field && <small>Source field: {e.field}</small>}
                {url && e.pdf_page && (
                  <a
                    href={`${(detail.source?.url || url).split('#')[0]}#page=${e.pdf_page}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open supporting PDF page ↗
                  </a>
                )}
              </div>
            ))
          ) : (
            <p>
              Only the exchange headline is available. Detailed event facts have not been extracted.
            </p>
          )}
          {detail.source && (
            <p className="source-check-note">
              Official source checked {stamp(detail.source.fetched_at)}.
              {detail.source.total_pages
                ? ` Native text inspected on ${detail.source.pages_scanned} of ${detail.source.total_pages} PDF pages; this is not a full-document analysis.`
                : ''}
            </p>
          )}
          {detail.limitation && <p className="source-check-note">{detail.limitation}</p>}
          <details className="raw-announcement">
            <summary>Original exchange wording &amp; identifiers</summary>
            <p>{filing.description.split('|SUBJECT:')[0]}</p>
          </details>
        </details>
      </li>
    )
  }

  function eventRow(event: FilingEvent, withCompany = false) {
    const outstanding = event.filings.filter((f) => !reviewed.has(f.id)).length
    const tone = eventTone(event),
      action = primaryAction(event)
    const summaries = [
      ...new Set(event.filings.map((f) => presentation(f).summary).filter(Boolean)),
    ]
    return (
      <article
        className={`filing-event ${outstanding ? '' : 'is-reviewed'}`}
        data-event-key={event.key}
        key={event.key}
      >
        <details className="event-details">
          <summary className="event-summary">
            <span className="event-chevron" aria-hidden="true">
              ›
            </span>
            <span className="event-summary-content">
              {withCompany && (
                <span className="activity-company">
                  {companyName(event.symbol)} <small>{event.symbol}</small>
                </span>
              )}
              <span className="event-title">{event.title}</span>
              <span className="event-snippet">
                {event.summary || 'Headline only · verified event details are not yet available.'}
              </span>
              <span className="event-meta">
                <span className={`event-priority ${tone.key}`}>{tone.label}</span>
                <time dateTime={event.newest}>{stamp(event.newest)}</time>
                <span>
                  {event.filings.length} {event.filings.length === 1 ? 'filing' : 'related filings'}
                </span>
                <span className="review-state">
                  {outstanding ? `${outstanding} unreviewed` : '✓ Reviewed'}
                </span>
              </span>
            </span>
          </summary>
          <div className="event-body">
            {event.summary && <p className="event-full-summary">{event.summary}</p>}
            {event.filings.length > 1 && (
              <p className="grouping-note">
                Grouped by a source-backed event reference. Each announcement keeps its own source
                and review state.
              </p>
            )}
            {summaries.length > 1 && (
              <ul className="event-additional-details">
                {summaries
                  .filter((s) => s !== event.summary)
                  .slice(0, 3)
                  .map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
              </ul>
            )}
            <ul className="event-sources" aria-label="Original announcements">
              {event.filings.map((filing) => sourceRow(filing, event.filings.length > 1))}
            </ul>
          </div>
        </details>
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
              {action.label} ↗
            </a>
          )}
          {event.filings.length === 1 && event.filings[0].source_url.startsWith('https://') && (
            <a
              className="filing-secondary-action"
              href={event.filings[0].source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Original filing ↗
            </a>
          )}
          <button
            className="review-toggle"
            aria-pressed={!outstanding}
            onClick={() =>
              changeReview(
                event.filings.map((f) => f.id),
                !!outstanding,
              )
            }
          >
            {outstanding
              ? event.filings.length > 1
                ? 'Review all'
                : 'Mark reviewed'
              : '✓ Reviewed · Undo'}
          </button>
        </div>
      </article>
    )
  }

  function companyGroups(items: FilingEvent[], idPrefix: string) {
    const groups = new Map<string, FilingEvent[]>()
    for (const event of items)
      groups.set(event.symbol, [...(groups.get(event.symbol) || []), event])
    const score = (items: FilingEvent[]) =>
      Math.max(
        0,
        ...items.filter((e) => e.filings.some((f) => !reviewed.has(f.id))).map((e) => e.priority),
      )
    return [...groups]
      .sort(
        (a, b) =>
          score(b[1]) - score(a[1]) ||
          Math.max(...b[1].map((e) => Date.parse(e.newest))) -
            Math.max(...a[1].map((e) => Date.parse(e.newest))),
      )
      .map(([symbol, companyEvents]) => {
        const key = `${idPrefix}:${symbol}`
        const sources = companyEvents.flatMap((e) => e.filings),
          remaining = sources.filter((f) => !reviewed.has(f.id)).length
        const ordered = [...companyEvents].sort(
          (a, b) => b.priority - a.priority || Date.parse(b.newest) - Date.parse(a.newest),
        )
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
                  {ordered
                    .slice(0, 2)
                    .map((e) => e.title)
                    .join(' · ')}
                  {ordered.length > 2 ? ` · +${ordered.length - 2} more` : ''}
                </span>
              </span>
              <span className="company-counts">
                <span>{remaining ? `${remaining} unreviewed` : '✓ All reviewed'}</span>
                <small>
                  {companyEvents.length} {companyEvents.length === 1 ? 'event' : 'events'} ·{' '}
                  {sources.length} filings
                </small>
              </span>
            </summary>
            <div className="company-events">
              {ordered.filter((event) => event.priority > 0).map((event) => eventRow(event))}
              {ordered.some((event) => event.priority === 0) && (
                <details className="routine-section">
                  <summary className="routine-toggle">
                    <span>
                      Routine disclosures{' '}
                      <small>
                        {
                          ordered
                            .filter((event) => event.priority === 0)
                            .flatMap((event) => event.filings).length
                        }{' '}
                        filings
                      </small>
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
            <p className="filing-count" role="status">
              {matching.length} matching {matching.length === 1 ? 'filing' : 'filings'} ·{' '}
              {unreviewed} unreviewed
            </p>
          </div>
          <div className="view-options" role="group" aria-label="Announcement view">
            {[
              ['company', 'By company'],
              ['latest', 'Latest activity'],
            ].map(([value, title]) => (
              <button key={value} aria-pressed={view === value} onClick={() => setView(value)}>
                {title}
              </button>
            ))}
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
        <p className="review-local-note">
          Review state is saved in this browser only. Counts reflect these filing filters.
        </p>
      </section>
      {undo && (
        <div className="review-feedback" role="status">
          <span>
            {undo.ids.length} {undo.ids.length === 1 ? 'filing' : 'filings'} marked{' '}
            {undo.reviewed ? 'reviewed' : 'unreviewed'}.
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
                  Include {routine.flatMap((e) => e.filings).length} routine filings
                </label>
              )
            )}
          </div>
          {view === 'company'
            ? companyGroups(events, 'main')
            : matching
                .filter((f) => includeRoutine || presentation(f).priority > 0)
                .map((f) => eventRow(makeEvent([f], f.id), true))}
          {bounds.valid &&
            (view === 'company'
              ? !events.length
              : !matching.some((f) => includeRoutine || presentation(f).priority > 0)) && (
              <div className="briefing-empty">
                <h3>No filings match this view</h3>
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
              Alert settings
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
