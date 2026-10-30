import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'
import ResearchApp from './research'
import './research.css'
import BriefingApp from './briefing'
import './briefing.css'
import { RecordedDataNotice } from './data'

type Status = 'unchecked' | 'checking' | 'reachable' | 'unavailable'

function App() {
  const [status, setStatus] = useState<Status>('unchecked')
  const [message, setMessage] = useState(
    'The frontend is running. External dependencies have not been verified.',
  )
  const [cacheMessage, setCacheMessage] = useState('Public cache connection has not been checked.')
  const [checkingCache, setCheckingCache] = useState(false)
  const publicUrl = import.meta.env.VITE_SUPABASE_URL || ''
  const publicKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || ''
  async function checkCache() {
    setCheckingCache(true)
    try {
      if (!publicUrl || !publicKey) throw new Error('Public configuration is absent')
      const response = await fetch(
        `${publicUrl.replace(/\/$/, '')}/rest/v1/finn_public_status?id=eq.foundation&select=id,state,note`,
        { headers: { apikey: publicKey }, signal: AbortSignal.timeout(15000), cache: 'no-store' },
      )
      if (!response.ok) throw new Error('Public cache is unavailable')
      const rows: { id: string; state: string }[] = await response.json()
      if (rows.length !== 1 || rows[0].id !== 'foundation' || rows[0].state !== 'foundation_only')
        throw new Error('Unexpected cache response')
      setCacheMessage(
        'The publishable key can read the foundation status. Source documents and privileged tables stay private.',
      )
    } catch {
      setCacheMessage(
        'Public cache check failed. Confirm the environment variables and apply the foundation SQL; no fallback data is shown.',
      )
    } finally {
      setCheckingCache(false)
    }
  }
  async function checkApi() {
    setStatus('checking')
    setMessage('Contacting the API. A free Render service may need about a minute to wake.')
    try {
      const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
      const response = await fetch(`${base}/health/live`, {
        signal: AbortSignal.timeout(90000),
        cache: 'no-store',
      })
      if (!response.ok) throw new Error('API health check failed')
      const data: { service?: string; status?: string } = await response.json()
      if (data.service !== 'finn-api' || data.status !== 'ok')
        throw new Error('Unexpected API response')
      setStatus('reachable')
      setMessage(
        'The FINN API is reachable. This checks connectivity, not market data, model access, or storage.',
      )
    } catch {
      setStatus('unavailable')
      setMessage(
        'The API could not be reached. No cached or invented financial data has been substituted.',
      )
    }
  }
  return (
    <main>
      <header>
        <a href="/" className="wordmark" aria-label="FINN home">
          finn<span>.</span>
        </a>
        <span className="milestone">MILESTONE 00</span>
      </header>
      <section className="intro">
        <p className="eyebrow">A LITTLE LESS NOISE.</p>
        <h1>
          Good decisions
          <br />
          start with evidence.
        </h1>
        <p className="lead">
          The foundation comes first. We’re checking the sources, models, and infrastructure before
          building the investor experience.
        </p>
      </section>
      <section className="panel" aria-labelledby="foundation-heading">
        <div className="panel-top">
          <h2 id="foundation-heading">Foundation check</h2>
          <span className={`status ${status}`}>
            {status === 'reachable'
              ? 'API reachable'
              : status === 'checking'
                ? 'Checking'
                : status === 'unavailable'
                  ? 'API unavailable'
                  : 'Not verified'}
          </span>
        </div>
        <p role="status" aria-live="polite" className="status-message">
          {message}
        </p>
        <button onClick={checkApi} disabled={status === 'checking'}>
          {status === 'checking' ? 'Connecting…' : 'Check API connection'}
          <span aria-hidden="true">↗</span>
        </button>
        <div className="cache-check">
          <p className="status-message" role="status" aria-live="polite">
            {cacheMessage}
          </p>
          <button
            className="secondary"
            onClick={checkCache}
            disabled={checkingCache || !publicUrl || !publicKey}
          >
            {checkingCache ? 'Checking cache…' : 'Check public cache'}
            <span aria-hidden="true">↗</span>
          </button>
          <small>
            Public environment:{' '}
            {publicUrl && publicKey ? 'URL and publishable key available' : 'not configured'}. No
            secret key is sent to the browser.
          </small>
        </div>
        <div className="checklist">
          <div>
            <span>01</span>
            <p>Public sources</p>
            <small>Verified by feasibility report</small>
          </div>
          <div>
            <span>02</span>
            <p>Models & storage</p>
            <small>Authenticated checks required</small>
          </div>
          <div>
            <span>03</span>
            <p>Investor workflows</p>
            <small>Gated until dependencies pass</small>
          </div>
        </div>
      </section>
      <footer>
        <span>Built for attention. Grounded in primary sources.</span>
        <span>Foundation only · No market data displayed</span>
      </footer>
    </main>
  )
}

const view = new URLSearchParams(window.location.search).get('view') || 'briefing'
createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RecordedDataNotice />
    {view === 'foundation' ? (
      <App />
    ) : view === 'research' ? (
      <ResearchApp />
    ) : (
      <BriefingApp portfolio={view === 'portfolio'} />
    )}
  </React.StrictMode>,
)
