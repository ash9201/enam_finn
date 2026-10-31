import { useEffect, useState } from 'react'
import { publicRead } from './data'
import Navigation from './navigation'
import ThemeSelector from './theme'

type Filing = {
  id: string
  symbol: string
  company_name: string
  title: string
  description: string
  source_url: string
  published_at: string
  category: string
  priority: number
  review_reason: string
}
type Price = {
  symbol: string
  data: {
    last_session: string
    close: number
    volume: number
    price_change_pct: number | null
    volume_ratio: number | null
    volume_note?: string
    source_note?: string | null
    source_url?: string | null
  } | null
  error: string | null
  last_success_at: string | null
}
type Sync = {
  id: string
  state: string
  last_success_at: string | null
  error: string | null
  details: {
    updated?: number
    portfolio_companies?: number
    coverage?: string
    automation_verified?: boolean
    execution_origin?: string
  }
  captured_since: string | null
}
type Company = { symbol: string; name: string; sector: string }
const dateTime = (date: string) =>
  new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  }).format(new Date(date)) + ' IST'
const rupees = (value: number) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(value)
const label = (category: string) =>
  ({
    m_and_a: 'M&A',
    management_change: 'Leadership',
    litigation: 'Legal & regulatory',
    results: 'Results',
    earnings_call: 'Earnings call',
    routine: 'Routine',
    publication: 'Publication',
    meeting_notice: 'Board meeting',
    investor_meeting: 'Investor meeting',
    capital: 'Capital',
    corporate_action: 'Corporate action',
    credit_rating: 'Credit rating',
    business_update: 'Business update',
    unclassified: 'Review filing',
  })[category] || category

function savedPreferences(): { price?: number; volume?: number } {
  try {
    const value = JSON.parse(localStorage.getItem('finn-alerts-v1') || '{}')
    return value && typeof value === 'object' ? value : {}
  } catch {
    return {}
  }
}
function savedRead(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem('finn-read-v1') || '[]')
    return Array.isArray(value) ? value.filter((item) => typeof item === 'string') : []
  } catch {
    return []
  }
}

export default function BriefingApp({ portfolio = false }: { portfolio?: boolean }) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [filings, setFilings] = useState<Filing[]>([])
  const [prices, setPrices] = useState<Price[]>([])
  const [syncs, setSyncs] = useState<Sync[]>([])
  const [windowSize, setWindowSize] = useState('24h')
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  const [priceThreshold, setPriceThreshold] = useState(Number(savedPreferences().price) || 4)
  const [volumeThreshold, setVolumeThreshold] = useState(Number(savedPreferences().volume) || 2)
  const [showSettings, setShowSettings] = useState(false)
  const [read, setRead] = useState<string[]>(savedRead)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [routineOpen, setRoutineOpen] = useState(false)
  const [lastLoaded, setLastLoaded] = useState('')

  async function load() {
    try {
      const [companyRows, filingRows, priceRows, syncRows] = await Promise.all([
        publicRead('finn_companies', {
          select: 'symbol,name,sector',
          portfolio: 'eq.true',
          order: 'symbol',
        }),
        publicRead('finn_filings', { select: '*', order: 'published_at.desc', limit: '1000' }),
        publicRead('finn_price_snapshots', { select: '*', order: 'symbol' }),
        publicRead('finn_sync_status', { select: '*' }),
      ])
      setCompanies(companyRows)
      setFilings(filingRows)
      setPrices(priceRows)
      setSyncs(syncRows)
      setError('')
      setLastLoaded(new Date().toISOString())
    } catch {
      setError(
        'The portfolio update could not be loaded. Any information already displayed is the previously saved snapshot, with its original dates.',
      )
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    void load()
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') void load()
    }, 60000)
    return () => clearInterval(interval)
  }, [])
  useEffect(() => {
    try {
      localStorage.setItem(
        'finn-alerts-v1',
        JSON.stringify({ price: priceThreshold, volume: volumeThreshold }),
      )
    } catch {
      /* Preferences still apply in this session. */
    }
  }, [priceThreshold, volumeThreshold])
  function markRead(id: string) {
    const next = read.includes(id) ? read.filter((value) => value !== id) : [...read, id]
    setRead(next)
    try {
      localStorage.setItem('finn-read-v1', JSON.stringify(next))
    } catch {
      /* Session-only read state. */
    }
  }
  const from =
    windowSize === 'custom'
      ? customStart
        ? new Date(`${customStart}:00+05:30`).getTime()
        : 0
      : Date.now() - (windowSize === '7d' ? 7 : 1) * 86400000
  const to =
    windowSize === 'custom' && customEnd ? new Date(`${customEnd}:00+05:30`).getTime() : Date.now()
  const filtered = filings
    .filter((filing) => {
      const time = new Date(filing.published_at).getTime()
      return time >= from && time <= to
    })
    .sort(
      (a, b) => b.priority - a.priority || +new Date(b.published_at) - +new Date(a.published_at),
    )
  const important = filtered.filter((filing) => filing.priority > 0)
  const routine = filtered.filter((filing) => filing.priority === 0)
  const alerts = prices.filter(
    (price) =>
      !price.error &&
      price.data &&
      ((price.data.price_change_pct !== null &&
        Math.abs(price.data.price_change_pct) >= priceThreshold) ||
        (price.data.volume_ratio !== null && price.data.volume_ratio >= volumeThreshold)),
  )
  const filingsSync = syncs.find((sync) => sync.id === 'filings')
  const pricesSync = syncs.find((sync) => sync.id === 'prices')
  const missingPrices =
    companies.length - prices.filter((price) => price.data && !price.error).length
  const researchLink = (symbol: string, refresh = false) =>
    `/?view=research&symbol=${encodeURIComponent(symbol)}${refresh ? '&refresh=1' : ''}`

  function filingCard(filing: Filing) {
    return (
      <article
        className={`filing-card ${read.includes(filing.id) ? 'is-read' : ''}`}
        key={filing.id}
      >
        <div className="filing-meta">
          <span className="ticker-badge">{filing.symbol}</span>
          <span className={`event-category priority-${filing.priority}`}>
            {label(filing.category)}
          </span>
          <time dateTime={filing.published_at}>{dateTime(filing.published_at)}</time>
        </div>
        <h3>{filing.title}</h3>
        <p className="filing-description">{filing.description.split('|SUBJECT:')[0]}</p>
        <p className="review-reason">{filing.review_reason}</p>
        <div className="filing-actions">
          <a href={researchLink(filing.symbol, true)} className="investigate-link">
            Investigate ↗
          </a>
          <a href={filing.source_url} target="_blank" rel="noopener noreferrer">
            Original filing ↗
          </a>
          <button
            aria-label={
              read.includes(filing.id)
                ? `Mark ${filing.symbol} unread`
                : `Mark ${filing.symbol} reviewed`
            }
            onClick={() => markRead(filing.id)}
          >
            {read.includes(filing.id) ? 'Reviewed ✓' : 'Mark reviewed'}
          </button>
        </div>
      </article>
    )
  }

  return (
    <main className="briefing-app">
      <header>
        <a href="/" className="wordmark" aria-label="FINN home">
          finn<span>.</span>
        </a>
        <div className="research-header">
          <span className="active-label">{portfolio ? 'Portfolio' : 'Your briefing'}</span>
          <button className="text-button" onClick={() => setShowSettings(!showSettings)}>
            Alert settings ⚙
          </button>
          <ThemeSelector />
        </div>
      </header>
      <section className="briefing-intro">
        <p className="eyebrow">
          {portfolio ? 'THE COMPANIES YOU FOLLOW.' : 'A LITTLE LESS NOISE.'}
        </p>
        <h1>
          {portfolio ? (
            <>
              A view of
              <br />
              your watchlist.
            </>
          ) : (
            <>
              What deserves
              <br />
              your attention.
            </>
          )}
        </h1>
        <p className="lead">
          {portfolio
            ? 'A mock portfolio of 15 listed companies. Prices reflect completed trading sessions.'
            : 'The changes worth reviewing across your portfolio. The routine paperwork stays out of your way.'}
        </p>
      </section>
      {showSettings && (
        <section className="settings-panel" aria-label="Alert settings">
          <div>
            <h2>Your definition of unusual.</h2>
            <p>Applied to the latest completed session. Saved in this browser.</p>
          </div>
          <label>
            Daily move: ±{priceThreshold}%
            <input
              aria-label="Daily price move threshold"
              type="range"
              min="1"
              max="15"
              step="0.5"
              value={priceThreshold}
              onChange={(event) => setPriceThreshold(Number(event.target.value))}
            />
          </label>
          <label>
            Volume: {volumeThreshold}× prior 20-session mean
            <input
              aria-label="Volume threshold"
              type="range"
              min="1"
              max="5"
              step="0.25"
              value={volumeThreshold}
              onChange={(event) => setVolumeThreshold(Number(event.target.value))}
            />
          </label>
        </section>
      )}
      {error && (
        <div className="research-error" role="alert">
          {error}
          <button className="text-button" onClick={() => void load()}>
            Try again ↻
          </button>
        </div>
      )}
      {loading && (
        <p className="muted" role="status">
          Loading saved portfolio updates…
        </p>
      )}
      {!loading && (
        <>
          <div className="briefing-stats">
            <div>
              <strong>{companies.length}</strong>
              <span>companies followed</span>
            </div>
            <div>
              <strong>{important.length}</strong>
              <span>filings to review</span>
            </div>
            <div>
              <strong>{alerts.length}</strong>
              <span>EOD signals</span>
            </div>
            <div>
              <strong>{routine.length}</strong>
              <span>routine filings tucked away</span>
            </div>
          </div>
          <div className="freshness">
            <span>
              {filingsSync?.last_success_at
                ? `Filings checked ${dateTime(filingsSync.last_success_at)}`
                : 'Filings not yet collected'}
            </span>
            <span>
              {pricesSync?.last_success_at
                ? `EOD checked ${dateTime(pricesSync.last_success_at)}`
                : 'EOD not fully refreshed'}
            </span>
            <button className="text-button" onClick={() => void load()}>
              Reload saved updates ↻
            </button>
          </div>
          {syncs.some((sync) => sync.state === 'failed' || sync.state === 'partial') && (
            <div className="coverage-warning" role="status">
              Some sources are incomplete.{' '}
              {syncs
                .filter((sync) => sync.error)
                .map((sync) => (
                  <span key={sync.id}>
                    {sync.id}: {sync.error}{' '}
                  </span>
                ))}
            </div>
          )}
          {portfolio ? (
            <section className="portfolio-grid" aria-label="Portfolio watchlist">
              {companies.map((company) => {
                const price = prices.find((item) => item.symbol === company.symbol)
                return (
                  <article key={company.symbol} className="portfolio-card">
                    <div className="portfolio-card-top">
                      <span className="ticker-badge">{company.symbol}</span>
                      <span>{company.sector}</span>
                    </div>
                    <h2>{company.name}</h2>
                    <div className="portfolio-price">
                      <strong>{price?.data ? rupees(price.data.close) : '—'}</strong>
                      <span
                        className={
                          price?.data?.price_change_pct !== null &&
                          (price?.data?.price_change_pct || 0) < 0
                            ? 'negative'
                            : 'positive'
                        }
                      >
                        {price?.data?.price_change_pct != null
                          ? `${price.data.price_change_pct > 0 ? '+' : ''}${price.data.price_change_pct.toFixed(2)}%`
                          : 'Comparison unavailable'}
                      </span>
                    </div>
                    <p>
                      {price?.data ? `EOD · ${price.data.last_session}` : 'Price unavailable'}
                      {price?.error ? ' · Refresh failed; last saved value shown' : ''}
                    </p>
                    {price?.data?.source_note && (
                      <p className="fine-print">
                        {price.data.source_note}{' '}
                        {price.data.source_url?.startsWith('https://nsearchives.nseindia.com/') && (
                          <a href={price.data.source_url} target="_blank" rel="noopener noreferrer">
                            NSE source ↗
                          </a>
                        )}
                      </p>
                    )}
                    <a className="investigate-link" href={researchLink(company.symbol)}>
                      Research company ↗
                    </a>
                  </article>
                )
              })}
            </section>
          ) : (
            <>
              {alerts.length > 0 && (
                <section className="signals-section">
                  <div className="section-heading">
                    <h2>Unusual, by your rules.</h2>
                    <span>Latest completed session</span>
                  </div>
                  <div className="signal-grid">
                    {alerts.map((price) => (
                      <article className="signal-card" key={price.symbol}>
                        <div>
                          <span className="ticker-badge">{price.symbol}</span>
                          <span className="signal-date">{price.data!.last_session} · EOD</span>
                        </div>
                        <h3>
                          {price.data!.price_change_pct !== null &&
                          Math.abs(price.data!.price_change_pct) >= priceThreshold
                            ? `${price.data!.price_change_pct > 0 ? '+' : ''}${price.data!.price_change_pct.toFixed(2)}% daily move`
                            : `${price.data!.volume_ratio!.toFixed(2)}× normal volume`}
                        </h3>
                        <p>
                          {price.data!.volume_ratio !== null
                            ? `Volume ${price.data!.volume_ratio.toFixed(2)}× the previous 20 sessions’ average.`
                            : 'Volume comparison unavailable.'}
                        </p>
                        <a href={researchLink(price.symbol)} className="investigate-link">
                          Research the business ↗
                        </a>
                      </article>
                    ))}
                  </div>
                </section>
              )}
              <section className="filings-section" aria-labelledby="filings-heading">
                <div className="section-heading">
                  <h2 id="filings-heading">Your portfolio, filtered.</h2>
                  <div className="window-options" aria-label="Filing time window">
                    {[
                      ['24h', '24 hours'],
                      ['7d', '7 days'],
                      ['custom', 'Custom'],
                    ].map(([value, text]) => (
                      <button
                        key={value}
                        aria-pressed={windowSize === value}
                        onClick={() => setWindowSize(value)}
                      >
                        {text}
                      </button>
                    ))}
                  </div>
                </div>
                {windowSize === 'custom' && (
                  <div className="custom-window">
                    <label>
                      From (IST)
                      <input
                        type="datetime-local"
                        value={customStart}
                        onChange={(event) => setCustomStart(event.target.value)}
                      />
                    </label>
                    <label>
                      To (IST)
                      <input
                        type="datetime-local"
                        value={customEnd}
                        onChange={(event) => setCustomEnd(event.target.value)}
                      />
                    </label>
                  </div>
                )}
                {from > to ? (
                  <p className="coverage-warning">Choose an end time after the start time.</p>
                ) : important.length ? (
                  important.map(filingCard)
                ) : (
                  <div className="quiet-state">
                    <span aria-hidden="true">✓</span>
                    <h3>
                      {filingsSync?.last_success_at
                        ? 'A quieter window.'
                        : 'The first scan is still pending.'}
                    </h3>
                    <p>
                      {filingsSync?.last_success_at
                        ? 'No non-routine filings were captured in this period. Expand routine items or choose a wider window.'
                        : 'A missing scan does not mean nothing happened. No announcements have been invented.'}
                    </p>
                    {filingsSync?.last_success_at && windowSize !== '7d' && (
                      <button className="text-button" onClick={() => setWindowSize('7d')}>
                        Review the last 7 days
                      </button>
                    )}
                  </div>
                )}
                {routine.length > 0 && (
                  <div className="routine-section">
                    <button
                      className="routine-toggle"
                      aria-expanded={routineOpen}
                      onClick={() => setRoutineOpen(!routineOpen)}
                    >
                      <span>
                        {routine.length} routine {routine.length === 1 ? 'filing' : 'filings'}
                      </span>
                      <span>{routineOpen ? 'Collapse −' : 'Expand +'}</span>
                    </button>
                    {routineOpen && routine.map(filingCard)}
                  </div>
                )}
              </section>
            </>
          )}
          <div className="coverage-footnote">
            <strong>Know the coverage.</strong>
            <p>
              Recent NSE RSS and filings captured since monitoring began
              {filingsSync?.captured_since ? ` (${dateTime(filingsSync.captured_since)})` : ''}.
              Earlier history may be incomplete.{' '}
              {filingsSync?.details.automation_verified === false
                ? 'The last refresh was manual; automatic announcement updates are not yet verified. '
                : filingsSync?.details.automation_verified === true
                  ? 'Announcements are checked on a schedule. '
                  : 'Coverage reflects the last completed scan shown above. '}
              EOD signals use the latest completed session, independently of the filing window.{' '}
              {missingPrices > 0
                ? `${missingPrices} of ${companies.length} prices need attention.`
                : `${prices.length} portfolio prices available.`}
            </p>
          </div>
        </>
      )}
      <footer>
        <span>Less noise. More room for judgment.</span>
        <span>
          {lastLoaded ? `Saved updates loaded ${dateTime(lastLoaded)}` : 'No live prices'}
        </span>
      </footer>
      <Navigation active={portfolio ? 'portfolio' : 'briefing'} />
    </main>
  )
}
