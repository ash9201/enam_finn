import { useEffect, useState } from 'react'
import { AppFooter, PageHeading } from './layout'

type Check = {
  state: 'checking' | 'reachable' | 'unavailable'
  message: string
  checkedAt?: string
}
const checking = (message: string): Check => ({ state: 'checking', message })

export default function SystemStatus({
  returnHref,
  active,
}: {
  returnHref: string
  active: boolean
}) {
  const [attempt, setAttempt] = useState(0)
  const [api, setApi] = useState<Check>(
    checking('Checking the research service. This may take up to a minute.'),
  )
  const [cache, setCache] = useState<Check>(checking('Checking access to saved company data.'))
  useEffect(() => {
    if (!active) return
    const controller = new AbortController()
    setApi(checking('Checking the research service. This may take up to a minute.'))
    setCache(checking('Checking access to saved company data.'))
    async function checkApi() {
      try {
        const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
        if (!base) throw new Error('Service unavailable')
        const r = await fetch(`${base}/health/live`, {
          cache: 'no-store',
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(90000)]),
        })
        if (!r.ok) throw new Error('Service unavailable')
        const data = await r.json()
        if (data.status !== 'ok' || data.service !== 'finn-api')
          throw new Error('Service unavailable')
        if (!controller.signal.aborted)
          setApi({
            state: 'reachable',
            message: 'The research service is reachable.',
            checkedAt: new Date().toISOString(),
          })
      } catch {
        if (!controller.signal.aborted)
          setApi({
            state: 'unavailable',
            message:
              'The research service could not be reached. You can return to FINN and view available saved information.',
            checkedAt: new Date().toISOString(),
          })
      }
    }
    async function checkCache() {
      try {
        const url = import.meta.env.VITE_SUPABASE_URL || '',
          key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || ''
        if (!url || !key) throw new Error('Saved data unavailable')
        const r = await fetch(
          `${url.replace(/\/$/, '')}/rest/v1/finn_companies?select=symbol&portfolio=eq.true&limit=1`,
          {
            headers: { apikey: key },
            cache: 'no-store',
            signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
          },
        )
        if (!r.ok || !Array.isArray(await r.json())) throw new Error('Saved data unavailable')
        if (!controller.signal.aborted)
          setCache({
            state: 'reachable',
            message: 'Live access to saved company data is available.',
            checkedAt: new Date().toISOString(),
          })
      } catch {
        if (!controller.signal.aborted)
          setCache({
            state: 'unavailable',
            message:
              'Live saved data could not be reached. Any historical snapshot in FINN remains labelled with its original date.',
            checkedAt: new Date().toISOString(),
          })
      }
    }
    void checkApi()
    void checkCache()
    return () => controller.abort()
  }, [active, attempt])
  return (
    <main className="system-status" id="status-content" tabIndex={-1}>
      <PageHeading
        title="System Status"
        actions={
          <a className="back-to-finn" href={returnHref} data-return-to-finn>
            Back to FINN
          </a>
        }
      />
      <p className="status-scope">
        Connection checks only. Data freshness and source coverage are shown on the relevant FINN
        page.
      </p>
      <div className="system-checks" aria-live="polite">
        {(
          [
            ['Research service', api],
            ['Saved data', cache],
          ] as const
        ).map(([title, check]) => (
          <section className="system-check" key={title}>
            <div className="panel-top">
              <h2>{title}</h2>
              <span className={`status ${check.state}`}>
                {check.state === 'reachable'
                  ? 'Connected'
                  : check.state === 'checking'
                    ? 'Checking'
                    : 'Unavailable'}
              </span>
            </div>
            <p>{check.message}</p>
            {check.checkedAt && (
              <small>
                Checked{' '}
                {new Intl.DateTimeFormat('en-IN', {
                  hour: 'numeric',
                  minute: '2-digit',
                  second: '2-digit',
                  timeZoneName: 'short',
                }).format(new Date(check.checkedAt))}
              </small>
            )}
          </section>
        ))}
      </div>
      <button
        className="secondary"
        disabled={api.state === 'checking' || cache.state === 'checking'}
        onClick={() => setAttempt((value) => value + 1)}
      >
        Check again
      </button>
      <p className="fine-print">
        A connected service does not verify market data, AI availability or document completeness.
        Failed checks do not substitute historical information for a live connection.
      </p>
      <AppFooter />
    </main>
  )
}
