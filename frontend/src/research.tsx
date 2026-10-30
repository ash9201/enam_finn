import { useEffect, useRef, useState } from 'react'
import Navigation from './navigation'
import { publicRead } from './data'

type Citation = {
  id: string
  document_id: string
  pdf_page: number
  quote: string
  source_url: string
  document_url?: string
  kind: string
  document_label: string
  published_at: string | null
  reporting_period: string | null
  fetched_at: string
}
type Claim = { statement: string; citation: Citation }
type Answer = {
  id: string
  symbol: string
  company_name: string
  question: string
  status: string
  claims: Claim[]
  comparison?: {
    earlier: Claim
    later: Claim
    verdict: string
    basis: string
    assessment: string
  } | null
  limitations: string[]
  coverage: { annual_reports: number; transcripts: number }
  source_checked_at: string
  generated_at: string
  cached: boolean
  retrieval_mode: string
}
type Company = {
  symbol: string
  name: string
  sector: string | null
  source_checked_at: string | null
}
const DEFAULT_QUESTION = 'Explain the core business and its main services or products.'
const COMPARISON_QUESTION =
  'Trace one earlier management statement against later earnings-call evidence.'
const QUESTIONS = [
  DEFAULT_QUESTION,
  'What did management say about demand and growth?',
  'What are the main risks discussed in the annual report?',
]
const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const stamp = (date: string) =>
  new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  }).format(new Date(date)) + ' IST'

async function api(path: string, body?: unknown) {
  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(100000),
    })
  } catch {
    throw new Error(
      'FINN could not connect. Check your connection or site-specific content-blocking settings, then retry.',
    )
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(
      typeof data.detail === 'string'
        ? data.detail
        : 'The research service is unavailable. Please retry.',
    )
  }
  return response.json()
}

function Evidence({ citation, onClose }: { citation: Citation; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    dialog.current?.showModal()
  }, [])
  const target = citation.document_url || citation.source_url
  const safeUrl = target.startsWith('https://') ? target : undefined
  return (
    <dialog
      className="evidence-dialog"
      ref={dialog}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === dialog.current) onClose()
      }}
      aria-labelledby="evidence-title"
    >
      <div className="drawer-head">
        <p className="eyebrow">PRIMARY SOURCE</p>
        <button className="icon-button" onClick={onClose} aria-label="Close evidence">
          ×
        </button>
      </div>
      <h2 id="evidence-title">{citation.document_label}</h2>
      <p className="muted">
        PDF page {citation.pdf_page} ·{' '}
        {citation.kind === 'annual_report' ? 'Annual report' : 'Call transcript'}
      </p>
      <blockquote>{citation.quote}</blockquote>
      <dl>
        <div>
          <dt>Reporting period</dt>
          <dd>{citation.reporting_period || 'Not verified'}</dd>
        </div>
        <div>
          <dt>Publication date</dt>
          <dd>{citation.published_at ? stamp(citation.published_at) : 'Not verified'}</dd>
        </div>
        <div>
          <dt>Document retrieved</dt>
          <dd>{stamp(citation.fetched_at)}</dd>
        </div>
      </dl>
      <p className="fine-print">
        The document label comes from the source index. It does not establish a verified publication
        or reporting date. PDF page numbering may differ from the report’s printed pages.
      </p>
      {safeUrl && (
        <a
          className="source-link"
          href={`${safeUrl}${safeUrl.includes('#') ? '' : `#page=${citation.pdf_page}`}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open original document ↗
        </a>
      )}
    </dialog>
  )
}

export default function ResearchApp() {
  const [companies, setCompanies] = useState<Company[]>([])
  const initial = new URLSearchParams(window.location.search)
  const [ticker, setTicker] = useState(initial.get('symbol') || 'INFY')
  const [question, setQuestion] = useState(
    initial.get('question')?.slice(0, 600) || DEFAULT_QUESTION,
  )
  const [needsRefresh, setNeedsRefresh] = useState(initial.get('refresh') === '1')
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [stage, setStage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loadingSaved, setLoadingSaved] = useState(true)
  const [selected, setSelected] = useState<Citation | null>(null)
  const [savedComparison, setSavedComparison] = useState<Answer | null>(null)
  const generation = useRef(0)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    publicRead('finn_companies', {
      select: 'symbol,name,sector,source_checked_at',
      portfolio: 'eq.true',
      order: 'symbol',
    })
      .then(setCompanies)
      .catch(() => {})
    return () => {
      mounted.current = false
      generation.current += 1
    }
  }, [])

  useEffect(() => {
    if (busy) return
    const token = ++generation.current
    setLoadingSaved(true)
    publicRead('finn_research_cache', {
      select: 'result,created_at',
      symbol: `eq.${ticker}`,
      question: `eq.${DEFAULT_QUESTION}`,
      is_public: 'eq.true',
      order: 'created_at.desc',
      limit: '1',
    })
      .then((rows) => {
        if (generation.current === token)
          setAnswer(rows[0] ? { ...rows[0].result, cached: true } : null)
      })
      .catch(() => {
        if (generation.current === token)
          setError('Saved research is temporarily unavailable. You can still submit a question.')
      })
      .finally(() => {
        if (generation.current === token) setLoadingSaved(false)
      })
    publicRead('finn_research_cache', {
      select: 'result',
      symbol: `eq.${ticker}`,
      question: `eq.${COMPARISON_QUESTION}`,
      is_public: 'eq.true',
      order: 'created_at.desc',
      limit: '1',
    })
      .then((rows) => {
        if (generation.current === token)
          setSavedComparison(rows[0] ? { ...rows[0].result, cached: true } : null)
      })
      .catch(() => {})
    // A completed job should remain visible; switching companies triggers this read.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker])

  async function ask(refresh = needsRefresh) {
    if (busy) return
    const symbol = ticker.trim().toUpperCase().replace(/\.NS$/, '')
    if (!/^[A-Z0-9&-]{1,30}$/.test(symbol)) {
      setError('Enter an NSE ticker, such as INFY or POLYCAB.')
      return
    }
    if (question.trim().length < 8) {
      setError('Ask a complete question so FINN can find useful evidence.')
      return
    }
    const token = ++generation.current
    setBusy(true)
    setLoadingSaved(false)
    setError('')
    setStage('Connecting to your research workspace…')
    try {
      const started = await api('/research', { symbol, question, refresh })
      for (let attempt = 0; attempt < 240; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 2000))
        if (!mounted.current || generation.current !== token) return
        const job = await api(`/jobs/${started.job_id}`)
        if (job.state === 'failed')
          throw new Error(job.error || 'Research could not finish. Please retry.')
        if (job.state === 'completed') {
          if (job.result.comparison) setSavedComparison(job.result)
          setAnswer(job.result)
          setNeedsRefresh(false)
          setStage('')
          return
        }
        const stages: Record<string, string> = {
          queued: 'Waiting for the current research to finish…',
          discovery: 'Finding the company’s original documents…',
          retrieval: 'Finding relevant passages in the company’s documents…',
          analysis: 'Reading the evidence and checking citations…',
        }
        setStage(
          job.stage.startsWith('extraction:')
            ? `Collecting and reading document ${job.stage.split(':')[1]}…`
            : stages[job.stage] || 'Preparing your research…',
        )
      }
      throw new Error(
        'This request is taking longer than expected. No answer has been substituted; please retry shortly.',
      )
    } catch (err) {
      if (mounted.current && generation.current === token)
        setError(err instanceof Error ? err.message : 'Research could not finish.')
    } finally {
      if (mounted.current && generation.current === token) {
        setBusy(false)
        setStage('')
      }
    }
  }

  function choose(symbol: string) {
    if (busy) return
    setTicker(symbol)
    setQuestion(DEFAULT_QUESTION)
    setError('')
    setAnswer(null)
  }
  const current =
    answer?.symbol === ticker.trim().toUpperCase().replace(/\.NS$/, '') ? answer : null
  return (
    <main className="research-app">
      <header>
        <a href="/" className="wordmark" aria-label="FINN home">
          finn<span>.</span>
        </a>
        <div className="research-header">
          <span className="active-label">Research</span>
          <a href="?view=foundation" className="muted">
            Connection status ↗
          </a>
        </div>
      </header>
      <section className="research-intro">
        <p className="eyebrow">A CLOSER LOOK.</p>
        <h1>
          Know the business.
          <br />
          See the evidence.
        </h1>
        <p className="lead">
          A clear view of a company, drawn from its own reports and earnings calls. Every point
          takes you back to the source.
        </p>
      </section>
      <section className="research-form" aria-labelledby="research-heading">
        <h2 id="research-heading">What are you looking into?</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void ask()
          }}
        >
          <div className="form-row">
            <label className="ticker-label">
              NSE ticker
              <input
                aria-label="NSE ticker"
                value={ticker}
                maxLength={30}
                disabled={busy}
                autoCapitalize="characters"
                autoComplete="off"
                spellCheck={false}
                onChange={(event) => {
                  setTicker(event.target.value.toUpperCase())
                  setError('')
                }}
              />
            </label>
            <label className="question-label">
              Your question
              <textarea
                aria-label="Your question"
                value={question}
                maxLength={600}
                disabled={busy}
                onChange={(event) => setQuestion(event.target.value)}
                rows={2}
              />
            </label>
          </div>
          <div className="form-bottom">
            <p>Any NSE company with accessible primary documents.</p>
            <button type="submit" disabled={busy}>
              {busy ? 'Investigating…' : 'Investigate'}
              <span aria-hidden="true">↗</span>
            </button>
          </div>
        </form>
        <div className="question-options" aria-label="Suggested questions">
          {QUESTIONS.slice(1).map((prompt) => (
            <button
              className="text-chip"
              key={prompt}
              disabled={busy}
              onClick={() => setQuestion(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
      </section>
      {companies.length > 0 && (
        <section className="company-strip" aria-label="Portfolio companies">
          <p className="eyebrow">YOUR WATCHLIST · {companies.length} COMPANIES</p>
          <div>
            {companies.map((company) => (
              <button
                className={`company-chip ${ticker === company.symbol ? 'chosen' : ''}`}
                key={company.symbol}
                onClick={() => choose(company.symbol)}
                disabled={busy}
                title={company.name}
              >
                {company.symbol}
                <span>{company.source_checked_at ? '◦' : '+'}</span>
              </button>
            ))}
          </div>
        </section>
      )}
      {busy && (
        <div className="research-progress" role="status" aria-live="polite">
          <span className="pulse-dot" />
          <div>
            <strong>{stage}</strong>
            <p>
              New companies take longer while their documents are collected. Saved research stays
              available.
            </p>
          </div>
        </div>
      )}
      {error && (
        <div className="research-error" role="alert">
          <strong>We couldn’t finish that request.</strong>
          <p>{error}</p>
          {current && <small>The previously saved answer below has not been refreshed.</small>}
        </div>
      )}
      {!busy && loadingSaved && (
        <p className="muted" role="status">
          Looking for saved research…
        </p>
      )}
      {current && (
        <section className="answer-panel" aria-labelledby="answer-heading">
          <div className="answer-heading">
            <div>
              <p className="eyebrow">{current.symbol} · COMPANY RESEARCH</p>
              <h2 id="answer-heading">{current.company_name}</h2>
            </div>
            <span className="saved-label">
              {current.cached ? 'Saved research' : 'Source-backed answer'}
            </span>
          </div>
          <p className="answer-question">{current.question}</p>
          <div className="coverage-line">
            <span>{current.coverage.annual_reports} annual report</span>
            <span>{current.coverage.transcripts} call transcripts</span>
            <span>Keyword search</span>
          </div>
          {current.claims.length ? (
            <ol className="claim-list">
              {current.claims.map((claim, index) => (
                <li key={`${claim.citation.id}-${index}`}>
                  <span className="claim-number">0{index + 1}</span>
                  <div>
                    <p>{claim.statement}</p>
                    <button className="citation-button" onClick={() => setSelected(claim.citation)}>
                      {claim.citation.document_label} · PDF p. {claim.citation.pdf_page}
                      <span aria-hidden="true"> ↗</span>
                    </button>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="empty-evidence">
              The available documents don’t support a reliable answer to this question.
            </p>
          )}
          <div className="answer-bottom">
            <p>
              Generated {stamp(current.generated_at)}
              <br />
              Sources checked {stamp(current.source_checked_at)}
            </p>
            <button className="text-button" disabled={busy} onClick={() => void ask(true)}>
              Refresh sources ↻
            </button>
          </div>
          <details className="coverage-notes">
            <summary>Coverage & limitations</summary>
            <ul>
              {current.limitations.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </details>
        </section>
      )}
      {savedComparison?.symbol === ticker && savedComparison.comparison && (
        <section className="comparison-panel" aria-labelledby="comparison-heading">
          <p className="eyebrow">NARRATIVE & EVIDENCE</p>
          <div className="comparison-title">
            <h2 id="comparison-heading">Follow the statement.</h2>
            <span className="saved-label">
              {(
                {
                  supported: 'Later evidence supports it',
                  diverged: 'Evidence diverges',
                  not_assessable: 'Not yet assessable',
                } as Record<string, string>
              )[savedComparison.comparison.verdict] || 'Review the evidence'}
            </span>
          </div>
          <div className="comparison-sides">
            {[
              ['Earlier statement', savedComparison.comparison.earlier],
              ['Later evidence', savedComparison.comparison.later],
            ].map(([heading, raw]) => {
              const claim = raw as Claim
              return (
                <div key={heading as string}>
                  <p className="eyebrow">{heading as string}</p>
                  <p>{claim.statement}</p>
                  <button className="citation-button" onClick={() => setSelected(claim.citation)}>
                    {claim.citation.document_label} · PDF p. {claim.citation.pdf_page} ↗
                  </button>
                </div>
              )
            })}
          </div>
          <p className="comparison-assessment">{savedComparison.comparison.assessment}</p>
          <p className="fine-print">
            Generated {stamp(savedComparison.generated_at)}. A statement-level comparison, not a
            verdict on the whole company.
          </p>
        </section>
      )}
      <div className="comparison-action">
        <button
          className="text-button"
          disabled={busy}
          onClick={() => setQuestion(COMPARISON_QUESTION)}
        >
          Trace a management statement ↗
        </button>
        <span>Compare earlier commentary with later call evidence.</span>
      </div>
      {!current && !busy && !loadingSaved && (
        <section className="research-empty">
          <span aria-hidden="true">↗</span>
          <h2>Start with a question.</h2>
          <p>
            Enter a ticker and investigate. FINN will find original documents and show what the
            evidence can—and cannot—support.
          </p>
        </section>
      )}
      <footer>
        <span>Primary documents. Clear sources. Your judgment.</span>
        <span>Reports and calls · No live market prices</span>
      </footer>
      {selected && <Evidence citation={selected} onClose={() => setSelected(null)} />}
      <Navigation active="research" />
    </main>
  )
}
