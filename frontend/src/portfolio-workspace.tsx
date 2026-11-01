import { Fragment, useId, useState } from 'react'
import type { Company, Filing } from './briefing-model'
import {
  commonSession,
  commonSourceNote,
  companyBriefing,
  finite,
  sortWatchRows,
  sourceLink,
  watchRows,
  type Price,
  type SortKey,
} from './portfolio-model'
import './portfolio-workspace.css'

const date = (value: string) =>
  new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'Asia/Kolkata',
  }).format(new Date(value.length === 10 ? value + 'T00:00:00+05:30' : value))
const stamp = (value: string) =>
  new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  }).format(new Date(value)) + ' IST'
const rupees = (value: number) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
const change = (value: number) => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`

export default function PortfolioWorkspace({
  companies,
  prices,
  filings,
  priceThreshold,
  volumeThreshold,
  onReload,
  pricesCheckedAt,
  filingsCheckedAt,
  capturedSince,
}: {
  companies: Company[]
  prices: Price[]
  filings: Filing[]
  priceThreshold: number
  volumeThreshold: number
  onReload: () => void
  pricesCheckedAt?: string | null
  filingsCheckedAt?: string | null
  capturedSince?: string | null
}) {
  const [sort, setSort] = useState<{ key: SortKey; direction: 'asc' | 'desc' }>({
    key: 'activity',
    direction: 'desc',
  })
  const [expanded, setExpanded] = useState(new Set<string>())
  const prefix = useId()
  const rows = watchRows(companies, prices, filings, priceThreshold, volumeThreshold)
  const scopedPrices = rows.flatMap((row) => (row.price ? [row.price] : []))
  const session = commonSession(scopedPrices),
    method = commonSourceNote(scopedPrices)
  const sorted = sortWatchRows(rows, sort.key, sort.direction)
  function toggleSort(key: SortKey) {
    setSort((previous) => ({
      key,
      direction:
        previous.key === key
          ? previous.direction === 'asc'
            ? 'desc'
            : 'asc'
          : key === 'name'
            ? 'asc'
            : 'desc',
    }))
  }
  function sortHeader(key: SortKey, label: string) {
    return (
      <th
        scope="col"
        className={key === 'change' ? 'numeric' : undefined}
        aria-sort={
          sort.key === key ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'
        }
      >
        <span className="mobile-column-label">{label}</span>
        <button
          type="button"
          onClick={() => toggleSort(key)}
          aria-label={`Sort by ${label.toLowerCase()}`}
        >
          {label}
          <span aria-hidden="true">
            {sort.key === key ? (sort.direction === 'asc' ? ' ↑' : ' ↓') : ' ↕'}
          </span>
        </button>
      </th>
    )
  }
  return (
    <section className="portfolio-workspace" aria-label="Portfolio watchlist">
      <div className="portfolio-overview">
        <div>
          <p className="portfolio-scope">
            {companies.length} companies · Mock watchlist · Individual share prices
          </p>
          <p className="portfolio-session">
            {session ? (
              <>
                End-of-day prices · <time dateTime={session}>{date(session)}</time>
              </>
            ) : (
              'Closing prices are unavailable'
            )}{' '}
            <span>Not live</span>
          </p>
        </div>
        <div className="portfolio-controls">
          <label>
            Sort by
            <select
              aria-label="Sort watchlist"
              value={`${sort.key}:${sort.direction}`}
              onChange={(event) => {
                const [key, direction] = event.target.value.split(':')
                setSort({ key: key as SortKey, direction: direction as 'asc' | 'desc' })
              }}
            >
              <option value="activity:desc">Attention first</option>
              <option value="activity:asc">Activity: low to high</option>
              <option value="name:asc">Company: A–Z</option>
              <option value="name:desc">Company: Z–A</option>
              <option value="change:desc">1D change: high to low</option>
              <option value="change:asc">1D change: low to high</option>
            </select>
          </label>
          <button className="text-button" onClick={onReload}>
            Reload saved updates ↻
          </button>
        </div>
      </div>
      <details className="portfolio-method">
        <summary>Data sources / Methodology</summary>
        <div>
          <p>
            {method ||
              'Source attribution follows each saved observation. Available official files are linked beside each company.'}
          </p>
          <p>
            Last close is the price of one share at the end of the reported session. 1D change is
            its close-to-close price movement. These are not investment values or portfolio returns.
          </p>
          <p>
            Price-move indicators use your ±{priceThreshold}% threshold; volume indicators use{' '}
            {volumeThreshold}× the previous 20 trading sessions’ average. The current session is
            excluded from that average. Missing or split-affected comparisons remain unavailable.
          </p>
          <p>
            Recent events are non-routine disclosures captured over the last seven days, grouped
            using Briefing’s existing source-backed references. Capture began{' '}
            {capturedSince ? stamp(capturedSince) : 'when monitoring started'}; earlier history may
            be incomplete.
          </p>
          <p>
            Attention first sorts by the number of triggered EOD thresholds, then captured event
            count, then company name. Indicators describe saved data, not recommendations.
          </p>
          <p className="portfolio-checks">
            EOD checked {pricesCheckedAt ? stamp(pricesCheckedAt) : 'not yet verified'} · Filings
            checked {filingsCheckedAt ? stamp(filingsCheckedAt) : 'not yet verified'}.
          </p>
        </div>
      </details>
      <p className="portfolio-activity-scope">
        Attention: configured EOD signals and captured events from the last 7 days.
      </p>
      {rows.length ? (
        <table className="portfolio-table" role="table" aria-label="Companies followed">
          <colgroup>
            <col className="company-col" />
            <col className="sector-col" />
            <col className="price-col" />
            <col className="change-col" />
            <col className="activity-col" />
            <col className="actions-col" />
          </colgroup>
          <thead>
            <tr>
              {sortHeader('name', 'Company name')}
              <th scope="col">Sector</th>
              <th scope="col" className="numeric">
                Last close
              </th>
              {sortHeader('change', '1D change')}
              {sortHeader('activity', 'Activity')}
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => {
              const { company, price, signals } = row,
                data = price?.data,
                open = expanded.has(company.symbol),
                source = sourceLink(price)
              const older = !!data?.last_session && !!session && data.last_session !== session
              const id = `${prefix}-${company.symbol.replace(/[^A-Z0-9-]/g, '-')}`
              const pct = finite(data?.price_change_pct) ? data.price_change_pct : null
              const alternate = !!data?.source_note && !!method && data.source_note !== method
              return (
                <Fragment key={company.symbol}>
                  <tr
                    className="portfolio-row"
                    data-symbol={company.symbol}
                    data-change={pct ?? ''}
                    data-session={data?.last_session || ''}
                  >
                    <th scope="row" className="portfolio-company-cell">
                      <button
                        className="portfolio-company-toggle"
                        aria-expanded={open}
                        aria-controls={open ? id : undefined}
                        aria-label={`${open ? 'Hide' : 'Show'} details for ${company.name}`}
                        onClick={() =>
                          setExpanded((previous) => {
                            const next = new Set(previous)
                            if (next.has(company.symbol)) next.delete(company.symbol)
                            else next.add(company.symbol)
                            return next
                          })
                        }
                      >
                        <span
                          className={open ? 'portfolio-chevron open' : 'portfolio-chevron'}
                          aria-hidden="true"
                        >
                          ›
                        </span>
                        <span>
                          <strong>{company.name}</strong>
                          <span className="portfolio-company-meta">
                            {company.symbol}
                            <span className="mobile-sector">
                              {' '}
                              · {company.sector || 'Sector not provided'}
                            </span>
                          </span>
                        </span>
                      </button>
                      {(older || price?.error || !finite(data?.close) || alternate) && (
                        <span className="portfolio-row-warning">
                          {!finite(data?.close)
                            ? 'Price unavailable'
                            : price?.error
                              ? 'Refresh failed · saved close'
                              : older
                                ? `Older close · ${date(data!.last_session)}`
                                : 'Different market-data source'}
                          {older && price?.error ? ` · ${date(data!.last_session)}` : ''}
                        </span>
                      )}
                    </th>
                    <td className="portfolio-sector-cell">{company.sector || '—'}</td>
                    <td className="portfolio-close numeric">
                      <span className="mobile-column-label">Last close</span>
                      {finite(data?.close) ? (
                        rupees(data.close)
                      ) : (
                        <span className="portfolio-missing">
                          —<span className="sr-only">Last close unavailable</span>
                        </span>
                      )}
                    </td>
                    <td
                      className={`portfolio-change numeric ${pct === null || pct === 0 ? '' : pct < 0 ? 'negative' : 'positive'}`}
                    >
                      <span className="mobile-column-label">1D change</span>
                      {pct !== null ? (
                        change(pct)
                      ) : (
                        <span className="portfolio-missing">
                          —<span className="sr-only">Daily comparison unavailable</span>
                        </span>
                      )}
                    </td>
                    <td className="portfolio-attention">
                      {signals.price && <span className="portfolio-signal">Price move</span>}
                      {signals.volume && (
                        <span className="portfolio-signal">
                          {data!.volume_ratio!.toFixed(2)}× volume
                        </span>
                      )}
                      {row.events > 0 && (
                        <a href={companyBriefing(company.symbol)} className="portfolio-event-link">
                          {row.events} {row.events === 1 ? 'event' : 'events'} · 7d ↗
                        </a>
                      )}
                      {!signals.price && !signals.volume && !row.events && (
                        <span className="portfolio-quiet">No captured flags</span>
                      )}
                    </td>
                    <td className="portfolio-actions">
                      <a
                        className="portfolio-research"
                        href={`/?view=research&symbol=${encodeURIComponent(company.symbol)}`}
                      >
                        Research company ↗
                      </a>
                      {source && (
                        <a
                          className="portfolio-source"
                          href={source.href}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {source.label} ↗
                        </a>
                      )}
                    </td>
                  </tr>
                  {open && (
                    <tr className="portfolio-detail-row">
                      <td colSpan={6} id={id}>
                        <section
                          className="portfolio-detail"
                          aria-label={`${company.name} details`}
                        >
                          <dl>
                            <div>
                              <dt>Trading volume</dt>
                              <dd>
                                {finite(data?.volume)
                                  ? `${data.volume.toLocaleString('en-IN')} shares`
                                  : 'Unavailable'}
                              </dd>
                            </div>
                            <div>
                              <dt>Volume / 20-session average</dt>
                              <dd>
                                {finite(data?.volume_ratio)
                                  ? `${data.volume_ratio.toFixed(2)}×`
                                  : 'Unavailable'}
                              </dd>
                            </div>
                            <div>
                              <dt>Latest captured event</dt>
                              <dd>
                                {row.latestEvent
                                  ? stamp(row.latestEvent)
                                  : 'None captured in 7 days'}
                              </dd>
                            </div>
                          </dl>
                          {price?.error && (
                            <p className="portfolio-detail-warning">
                              Refresh failed: {price.error}{' '}
                              {price.last_success_at
                                ? `Last successful fetch ${stamp(price.last_success_at)}.`
                                : ''}
                            </p>
                          )}
                          {data?.volume_note && <p>{data.volume_note}</p>}
                          {alternate && <p>{data!.source_note}</p>}
                          {data?.adjustment && <p>{data.adjustment}</p>}
                          <a href={companyBriefing(company.symbol)}>Open company Briefing ↗</a>
                        </section>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      ) : (
        <p className="portfolio-empty">
          The watchlist has not loaded. Reload saved updates to try again.
        </p>
      )}
    </section>
  )
}
