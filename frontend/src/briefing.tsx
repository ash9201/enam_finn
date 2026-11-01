import { useEffect, useState } from 'react'
import { publicRead } from './data'
import { AppFooter, PageHeading } from './layout'
import BriefingWorkspace from './briefing-workspace'
import { groupEvents, type Filing } from './briefing-model'
import {
  emptyReviews,
  isEventReviews,
  migrateReviews,
  type EventReviews,
  type ReviewChanges,
} from './event-reviews'
import PortfolioWorkspace from './portfolio-workspace'
import { priceSignals, type Price } from './portfolio-model'

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
let sessionPreferences: { price?: number; volume?: number } = {}
function savedPreferences(): { price?: number; volume?: number } {
  try {
    const value = JSON.parse(localStorage.getItem('finn-alerts-v1') || '{}')
    return value && typeof value === 'object' ? value : {}
  } catch {
    return sessionPreferences
  }
}
let sessionReviews: EventReviews | null = null
function savedReviews(filings: Filing[]): EventReviews {
  try {
    const saved = JSON.parse(localStorage.getItem('finn-event-reviews-v2') || 'null')
    if (isEventReviews(saved)) return saved
  } catch {
    // A damaged newer slot must not discard the original per-filing reviews.
  }
  try {
    const old = JSON.parse(localStorage.getItem('finn-read-v1') || '[]')
    return migrateReviews(
      groupEvents(filings),
      Array.isArray(old) ? old.filter((id) => typeof id === 'string') : [],
    )
  } catch {
    return sessionReviews || emptyReviews()
  }
}

export default function BriefingApp({
  portfolio = false,
  active = true,
  entryUrl,
  entryKey = 0,
}: {
  portfolio?: boolean
  active?: boolean
  entryUrl?: string
  entryKey?: number
}) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [filings, setFilings] = useState<Filing[]>([])
  const [prices, setPrices] = useState<Price[]>([])
  const [syncs, setSyncs] = useState<Sync[]>([])
  const [priceThreshold, setPriceThreshold] = useState(Number(savedPreferences().price) || 4)
  const [volumeThreshold, setVolumeThreshold] = useState(Number(savedPreferences().volume) || 2)
  const [showSettings, setShowSettings] = useState(false)
  const [reviews, setReviews] = useState<EventReviews | null>(null)
  const [reviewStorageWarning, setReviewStorageWarning] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
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
      if (!portfolio) setReviews((previous) => previous || savedReviews(filingRows))
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
    if (!active) return
    // Alert preferences are shared by both retained views.
    const preferences = savedPreferences()
    setPriceThreshold(Number(preferences.price) || 4)
    setVolumeThreshold(Number(preferences.volume) || 2)
    void load()
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') void load()
    }, 60000)
    return () => clearInterval(interval)
  }, [active])
  useEffect(() => {
    sessionPreferences = { price: priceThreshold, volume: volumeThreshold }
    try {
      localStorage.setItem(
        'finn-alerts-v1',
        JSON.stringify({ price: priceThreshold, volume: volumeThreshold }),
      )
    } catch {
      /* Preferences still apply in this session. */
    }
  }, [priceThreshold, volumeThreshold])
  useEffect(() => {
    if (!reviews || portfolio) return
    sessionReviews = reviews
    try {
      localStorage.setItem('finn-event-reviews-v2', JSON.stringify(reviews))
      setReviewStorageWarning(false)
    } catch {
      setReviewStorageWarning(true)
    }
  }, [reviews, portfolio])
  function updateReview(changes: ReviewChanges) {
    setReviews((previous) => {
      const next = { ...(previous || emptyReviews()), receipts: { ...(previous?.receipts || {}) } }
      for (const [key, receipt] of Object.entries(changes)) {
        if (receipt) next.receipts[key] = receipt
        else delete next.receipts[key]
      }
      return next
    })
  }

  const alerts = prices.filter((price) => {
    const signals = priceSignals(price, priceThreshold, volumeThreshold)
    return signals.price || signals.volume
  })
  const filingsSync = syncs.find((sync) => sync.id === 'filings')
  const pricesSync = syncs.find((sync) => sync.id === 'prices')
  const missingPrices =
    companies.length - prices.filter((price) => price.data && !price.error).length
  const alertSettings = (
    <section
      className="settings-panel"
      id={`${portfolio ? 'portfolio' : 'briefing'}-settings`}
      aria-label="Alert settings"
    >
      <div>
        <h2>Alert thresholds</h2>
      </div>
      <label>
        Daily move: &plusmn;{priceThreshold}%
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
        Volume: {volumeThreshold}&times; prior 20-session average
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
  )

  return (
    <main
      className="briefing-app"
      id={portfolio ? 'portfolio-content' : 'briefing-content'}
      tabIndex={-1}
    >
      <PageHeading title={portfolio ? 'Your Portfolio' : 'Your Briefing'} />
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
          {!portfolio && (
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
          )}
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
            <PortfolioWorkspace
              companies={companies}
              settings={showSettings ? alertSettings : null}
              settingsOpen={showSettings}
              onSettings={() => setShowSettings(!showSettings)}
              prices={prices}
              filings={filings}
              priceThreshold={priceThreshold}
              volumeThreshold={volumeThreshold}
              onReload={() => void load()}
              pricesCheckedAt={pricesSync?.last_success_at}
              filingsCheckedAt={filingsSync?.last_success_at}
              capturedSince={filingsSync?.captured_since}
            />
          ) : (
            <BriefingWorkspace
              entryUrl={entryUrl}
              entryKey={entryKey}
              filings={filings}
              companies={companies}
              reviews={reviews || emptyReviews()}
              reviewStorageWarning={reviewStorageWarning}
              onReview={updateReview}
              signals={alerts}
              settings={alertSettings}
              settingsOpen={showSettings}
              onSettings={() => setShowSettings(!showSettings)}
              priceThreshold={priceThreshold}
              volumeThreshold={volumeThreshold}
            />
          )}
          {!portfolio && (
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
          )}
        </>
      )}
      <AppFooter>
        <span>
          {lastLoaded ? `Saved updates loaded ${dateTime(lastLoaded)}` : 'No live prices'}
        </span>
      </AppFooter>
    </main>
  )
}
