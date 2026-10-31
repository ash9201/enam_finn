import { useEffect, useRef, useState } from 'react'
import Navigation from './navigation'
import { publicRead } from './data'
import ThemeSelector from './theme'

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
  document_date?: string
  document_date_basis?: string
  document_date_pdf_page?: number
}
type Claim = { statement: string; citation: Citation }
type Intent = 'question' | 'repeated' | 'later' | 'perspective'
type EvidenceContext = {
  research_id: string
  citation_id: string
  claim_index?: number
  intent: Intent
  symbol: string
  claim: string
  citation: Citation
}
type Selection = {
  answer: Pick<Answer, 'id' | 'symbol' | 'company_name'>
  claim: Claim
  claimIndex?: number
}
const PATHS: { intent: Intent; label: string; detail: string; question: string }[] = [
  {
    intent: 'repeated',
    label: 'Was it repeated?',
    detail: 'Look for the same message in other calls.',
    question:
      'Has management repeated this statement in other earnings calls? Show the independent supporting passages, or say what is missing.',
  },
  {
    intent: 'later',
    label: 'What happened later?',
    detail: 'Check later evidence without assuming a target was met.',
    question:
      'Do later company documents support this statement, or is it not yet assessable? Distinguish an observation from delivery of a target.',
  },
  {
    intent: 'perspective',
    label: 'Find another perspective',
    detail: 'Look for context, qualifications or a different account.',
    question:
      'What do other company documents add to, qualify, or put in perspective about this statement?',
  },
]
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
  evidence_context?: EvidenceContext
  investigation?: {
    other_documents_retrieved: number
    history_requested: boolean
    assessment?: string
  }
}
type Company = {
  symbol: string
  name: string
  sector: string | null
  source_checked_at: string | null
}
function evidenceSelection(answer: Answer, claim: Claim): Selection {
  const claims = [
    ...answer.claims,
    ...([answer.comparison?.earlier, answer.comparison?.later].filter(Boolean) as Claim[]),
  ]
  return { answer, claim, claimIndex: claims.indexOf(claim) }
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
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  }).format(new Date(date)) + ' IST'

async function api(path: string, body?: unknown) {
  let response: Response
  const request = () =>
    fetch(`${apiBase}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(100000),
    })
  try {
    try {
      response = await request()
    } catch (error) {
      if (body !== undefined) throw error
      // A sleeping/redeploying free service can close a status connection. GET is
      // safe to retry; never automatically resubmit an ambiguous model request.
      await new Promise((resolve) => setTimeout(resolve, 700))
      response = await request()
    }
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

function Evidence({
  selection,
  onClose,
  onAsk,
  canFollow,
}: {
  selection: Selection
  onClose: () => void
  onAsk: (intent: Intent, citation: Citation) => void
  canFollow: boolean
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [citation, setCitation] = useState(selection.claim.citation)
  const [verification, setVerification] = useState('Verifying source details…')
  const [unavailable, setUnavailable] = useState(false)
  useEffect(() => {
    const panel = dialog.current
    const previousFocus = document.activeElement
    panel?.showModal()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    let active = true
    api(
      `/research/${selection.answer.id}/evidence/${selection.claim.citation.id}?symbol=${encodeURIComponent(selection.answer.symbol)}${selection.claimIndex !== undefined ? `&claim_index=${selection.claimIndex}` : ''}`,
    )
      .then((data) => {
        if (active) {
          setCitation(data.citation)
          setVerification('Passage verified against the stored original document.')
        }
      })
      .catch((err) => {
        if (active) {
          setVerification('Showing the saved excerpt. ' + err.message)
          setUnavailable(
            /no longer|does not belong|changed|unavailable for this company/.test(err.message),
          )
        }
      })
    return () => {
      active = false
      document.body.style.overflow = previousOverflow
      panel?.close()
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected)
        previousFocus.focus({ preventScroll: true })
    }
  }, [selection])
  const target = citation.document_url || citation.source_url
  const safeUrl = target.startsWith('https://') ? target.split('#')[0] : undefined
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
      <div className="evidence-top">
        <div className="drawer-head">
          <p className="eyebrow">{selection.answer.symbol} · PRIMARY EVIDENCE</p>
          <button className="icon-button" onClick={onClose} aria-label="Close evidence" autoFocus>
            ×
          </button>
        </div>
        <h2 id="evidence-title">{citation.document_label}</h2>
        <p className="muted">
          {citation.kind === 'annual_report' ? 'Annual report' : 'Call transcript'} · PDF page{' '}
          {citation.pdf_page}
        </p>
      </div>
      <div className="evidence-scroll">
        <p className="eyebrow">THE CLAIM YOU OPENED</p>
        <p className="evidence-claim">{selection.claim.statement}</p>
        <p className="eyebrow">EXACT SUPPORTING PASSAGE</p>
        <blockquote>{citation.quote}</blockquote>
        <p className="fine-print" role="status">
          {verification}
        </p>
        <dl>
          {citation.document_date && (
            <div>
              <dt>
                {citation.document_date_basis === 'Repeated call header'
                  ? 'Call date in original text'
                  : 'Document date'}
              </dt>
              <dd>
                {new Intl.DateTimeFormat('en-IN', {
                  day: 'numeric',
                  month: 'short',
                  year: 'numeric',
                  timeZone: 'Asia/Kolkata',
                }).format(new Date(citation.document_date))}
              </dd>
            </div>
          )}
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
          The index label is shown separately from verified dates. PDF page numbers may differ from
          printed pages. An exact quote still needs your judgment about what it supports.
        </p>
        <div className="evidence-paths" aria-label="Evidence investigation paths">
          <p className="eyebrow">FOLLOW THE EVIDENCE</p>
          {PATHS.map((path) => (
            <button
              key={path.intent}
              className="evidence-path"
              disabled={unavailable || !canFollow}
              onClick={() => onAsk(path.intent, citation)}
            >
              <strong>
                {path.label} <span aria-hidden="true">↗</span>
              </strong>
              <span>{path.detail}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="evidence-bottom">
        <button
          className="evidence-ask"
          disabled={unavailable || !canFollow}
          onClick={() => onAsk('question', citation)}
        >
          Ask about this evidence <span aria-hidden="true">↗</span>
        </button>
        {safeUrl && (
          <a
            className="evidence-original"
            href={`${safeUrl}#page=${citation.pdf_page}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open original document · PDF p. {citation.pdf_page} ↗
          </a>
        )}
      </div>
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
  const [selected, setSelected] = useState<Selection | null>(null)
  const [context, setContext] = useState<EvidenceContext | null>(null)
  const [includeHistory, setIncludeHistory] = useState(false)
  const [trail, setTrail] = useState<Answer[]>([])
  const questionInput = useRef<HTMLTextAreaElement>(null)
  const composer = useRef<HTMLElement>(null)
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

  async function ask(
    refresh = needsRefresh,
    query = question,
    anchor = context,
    history = includeHistory,
  ) {
    if (busy) return
    const symbol = ticker.trim().toUpperCase().replace(/\.NS$/, '')
    if (!/^[A-Z0-9&-]{1,30}$/.test(symbol)) {
      setError('Enter an NSE ticker, such as INFY or POLYCAB.')
      return
    }
    if (query.trim().length < 8) {
      setError('Ask a complete question so FINN can find useful evidence.')
      return
    }
    const token = ++generation.current
    setBusy(true)
    setLoadingSaved(false)
    setError('')
    setStage('Connecting to your research workspace…')
    try {
      if (anchor && anchor.symbol !== symbol)
        throw new Error('Select evidence from this company before following it up.')
      const started = await api('/research', {
        symbol,
        question: query,
        refresh,
        include_history: history,
        context: anchor
          ? {
              research_id: anchor.research_id,
              citation_id: anchor.citation_id,
              claim_index: anchor.claim_index,
              intent: anchor.intent,
            }
          : null,
      })
      for (let attempt = 0; attempt < 240; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 2000))
        if (!mounted.current || generation.current !== token) return
        const job = await api(`/jobs/${started.job_id}`)
        if (job.state === 'failed')
          throw new Error(job.error || 'Research could not finish. Please retry.')
        if (job.state === 'completed') {
          if (
            anchor &&
            (job.result.evidence_context?.research_id !== anchor.research_id ||
              job.result.evidence_context?.citation_id !== anchor.citation_id ||
              (anchor.claim_index !== undefined &&
                job.result.evidence_context?.claim_index !== anchor.claim_index))
          )
            throw new Error(
              'The service did not preserve the selected evidence context. No contextual answer was substituted. Retry after the service finishes updating.',
            )
          if (job.result.comparison) setSavedComparison(job.result)
          if (answer?.symbol === symbol)
            setTrail((items) =>
              [...items.filter((item) => item.id !== answer.id), answer].slice(-6),
            )
          setAnswer(job.result)
          setQuestion(query)
          setContext(anchor)
          setIncludeHistory(history)
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
        const [, document, phase, page] = job.stage.split(':')
        const extractionStage =
          phase === 'pages'
            ? `Reading document ${document} · page ${page}`
            : phase === 'download'
              ? `Downloading original document ${document}…`
              : phase === 'tables'
                ? `Preserving table context in document ${document}…`
                : phase === 'saving'
                  ? `Saving evidence for document ${document}…`
                  : `Collecting and reading document ${document}…`
        setStage(
          job.stage.startsWith('extraction:')
            ? extractionStage
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
    setContext(null)
    setIncludeHistory(false)
    setTrail([])
    setSelected(null)
    setSavedComparison(null)
    setQuestion(DEFAULT_QUESTION)
    setError('')
    setAnswer(null)
  }
  function focusComposer() {
    requestAnimationFrame(() => {
      composer.current?.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
        block: 'start',
      })
      questionInput.current?.focus({ preventScroll: true })
    })
  }
  function followEvidence(intent: Intent, citation: Citation) {
    if (!selected || busy) return
    setContext({
      research_id: selected.answer.id,
      citation_id: citation.id,
      claim_index: selected.claimIndex,
      intent,
      symbol: selected.answer.symbol,
      claim: selected.claim.statement,
      citation,
    })
    setTicker(selected.answer.symbol)
    setQuestion(PATHS.find((path) => path.intent === intent)?.question || '')
    setNeedsRefresh(intent === 'later')
    setIncludeHistory(intent === 'repeated')
    setSelected(null)
    setError('')
    focusComposer()
  }
  function generalResearch() {
    if (busy) return
    setContext(null)
    setIncludeHistory(false)
    setNeedsRefresh(false)
    setQuestion(DEFAULT_QUESTION)
    if (answer?.evidence_context) {
      setTrail((items) => [...items.filter((item) => item.id !== answer.id), answer].slice(-6))
      setAnswer(
        [...trail].reverse().find((item) => !item.evidence_context && item.symbol === ticker) ||
          null,
      )
    }
    setError('')
    focusComposer()
  }
  function revisit(item: Answer) {
    if (busy) return
    if (answer && answer.id !== item.id)
      setTrail((items) => [...items.filter((entry) => entry.id !== answer.id), answer].slice(-6))
    setAnswer(item)
    setQuestion(item.question)
    setContext(item.evidence_context || null)
    setIncludeHistory(false)
    setNeedsRefresh(false)
    setError('')
  }
  const current =
    answer?.symbol === ticker.trim().toUpperCase().replace(/\.NS$/, '') ? answer : null
  const visibleTrail = trail.filter((item) => item.id !== current?.id)
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
          <ThemeSelector />
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
      <section className="research-form" aria-labelledby="research-heading" ref={composer}>
        <h2 id="research-heading">
          {context ? 'Follow this evidence.' : 'What are you looking into?'}
        </h2>
        {context && (
          <aside className="active-evidence" aria-label="Active evidence context">
            <div className="context-heading">
              <span className="eyebrow">
                {context.symbol} ·{' '}
                {PATHS.find((path) => path.intent === context.intent)?.label || 'EVIDENCE CONTEXT'}
              </span>
              <button
                type="button"
                className="context-remove"
                disabled={busy}
                aria-label="Remove evidence context"
                onClick={generalResearch}
              >
                ×
              </button>
            </div>
            <p>{context.claim}</p>
            <button
              type="button"
              className="citation-button"
              disabled={busy}
              onClick={() =>
                setSelected({
                  answer: {
                    id: context.research_id,
                    symbol: context.symbol,
                    company_name: current?.company_name || ticker,
                  },
                  claim: { statement: context.claim, citation: context.citation },
                  claimIndex: context.claim_index,
                })
              }
            >
              {context.citation.document_label} · PDF p. {context.citation.pdf_page} ↗
            </button>
            <small>
              This passage is the starting point. FINN searches other {context.symbol} reports and
              calls too.
            </small>
            <button type="button" className="text-button" disabled={busy} onClick={generalResearch}>
              Return to general company research ↗
            </button>
          </aside>
        )}
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
                  setContext(null)
                  setIncludeHistory(false)
                  setTrail([])
                  setSavedComparison(null)
                  setError('')
                }}
              />
            </label>
            <label className="question-label">
              Your question
              <textarea
                aria-label="Your question"
                ref={questionInput}
                placeholder={
                  context
                    ? 'Ask a question about this statement…'
                    : 'What would you like to understand?'
                }
                value={question}
                maxLength={600}
                disabled={busy}
                onChange={(event) => setQuestion(event.target.value)}
                rows={2}
              />
            </label>
          </div>
          <div className="form-bottom">
            <p>
              {context
                ? `Searching ${context.symbol} across company documents.`
                : 'Any NSE company with accessible primary documents.'}
            </p>
            <button type="submit" disabled={busy}>
              {busy ? 'Investigating…' : 'Investigate'}
              <span aria-hidden="true">↗</span>
            </button>
          </div>
        </form>
        {context && (
          <div className="context-options">
            <label>
              <input
                type="checkbox"
                checked={includeHistory}
                disabled={busy}
                onChange={(event) => setIncludeHistory(event.target.checked)}
              />{' '}
              Add earlier documents{' '}
              <span>
                Up to two reports and four calls. Earlier-document coverage stays enabled.
              </span>
            </label>
            <label>
              <input
                type="checkbox"
                checked={needsRefresh}
                disabled={busy}
                onChange={(event) => setNeedsRefresh(event.target.checked)}
              />{' '}
              Check latest sources <span>Discover newly available reports and calls.</span>
            </label>
          </div>
        )}
        <div className="question-options" aria-label="Suggested questions">
          {!context &&
            QUESTIONS.slice(1).map((prompt) => (
              <button
                className="text-chip"
                key={prompt}
                disabled={busy}
                onClick={() => setQuestion(prompt)}
              >
                {prompt}
              </button>
            ))}
          {context &&
            PATHS.map((path) => (
              <button
                type="button"
                className="text-chip"
                key={path.intent}
                disabled={busy}
                onClick={() => {
                  setContext({ ...context, intent: path.intent })
                  setQuestion(path.question)
                  setIncludeHistory(path.intent === 'repeated')
                  setNeedsRefresh(path.intent === 'later')
                  focusComposer()
                }}
              >
                {path.label}
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
      {visibleTrail.length > 0 && (
        <nav className="research-trail" aria-label="Research trail">
          <p className="eyebrow">YOUR INVESTIGATION</p>
          <div>
            {visibleTrail.map((item) => (
              <button
                className="text-chip"
                key={item.id}
                disabled={busy}
                onClick={() => revisit(item)}
              >
                {item.question}
              </button>
            ))}
          </div>
        </nav>
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
          {current.evidence_context && (
            <div className="answer-context">
              <span className="eyebrow">FOLLOW-UP ON SELECTED EVIDENCE</span>
              <p>{current.evidence_context.claim}</p>
              <small>
                {current.evidence_context.citation.document_label} · PDF p.{' '}
                {current.evidence_context.citation.pdf_page} ·{' '}
                {current.investigation?.other_documents_retrieved || 0} other documents retrieved
              </small>
            </div>
          )}
          <p className="answer-question">{current.question}</p>
          {current.investigation?.assessment && (
            <p className="investigation-note" role="status">
              {current.investigation.assessment}
            </p>
          )}
          <div className="coverage-line">
            <span>
              {current.coverage.annual_reports} annual{' '}
              {current.coverage.annual_reports === 1 ? 'report' : 'reports'}
            </span>
            <span>{current.coverage.transcripts} call transcripts</span>
            <span>{current.retrieval_mode === 'hybrid' ? 'Hybrid search' : 'Keyword search'}</span>
          </div>
          {current.claims.length ? (
            <ol className="claim-list">
              {current.claims.map((claim, index) => (
                <li key={`${claim.citation.id}-${index}`}>
                  <span className="claim-number">0{index + 1}</span>
                  <div>
                    {current.evidence_context && (
                      <span className="source-relation">
                        {claim.citation.document_id ===
                        current.evidence_context.citation.document_id
                          ? 'Starting document'
                          : claim.citation.document_date &&
                              current.evidence_context.citation.document_date &&
                              claim.citation.document_date.slice(0, 10) >
                                current.evidence_context.citation.document_date.slice(0, 10)
                            ? 'Later source'
                            : claim.citation.document_date &&
                                current.evidence_context.citation.document_date &&
                                claim.citation.document_date.slice(0, 10) <
                                  current.evidence_context.citation.document_date.slice(0, 10)
                              ? 'Earlier source'
                              : 'Another company document'}
                        {claim.citation.document_date
                          ? ' · ' +
                            new Intl.DateTimeFormat('en-IN', {
                              day: 'numeric',
                              month: 'short',
                              year: 'numeric',
                              timeZone: 'Asia/Kolkata',
                            }).format(new Date(claim.citation.document_date))
                          : ''}
                      </span>
                    )}
                    <button
                      className="claim-statement"
                      onClick={() => setSelected(evidenceSelection(current, claim))}
                      aria-label={`Review evidence: ${claim.statement}`}
                    >
                      {claim.statement}
                    </button>
                    <button
                      className="citation-button"
                      onClick={() => setSelected(evidenceSelection(current, claim))}
                    >
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
            <button
              className="text-button"
              disabled={busy}
              onClick={() =>
                void ask(
                  true,
                  current.question,
                  current.evidence_context || null,
                  current.investigation?.history_requested || false,
                )
              }
            >
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
                  <button
                    className="claim-statement"
                    onClick={() => setSelected(evidenceSelection(savedComparison, claim))}
                  >
                    {claim.statement}
                  </button>
                  <button
                    className="citation-button"
                    onClick={() => setSelected(evidenceSelection(savedComparison, claim))}
                  >
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
      {selected && (
        <Evidence
          selection={selected}
          onClose={() => setSelected(null)}
          onAsk={followEvidence}
          canFollow={!busy}
        />
      )}
      <Navigation active="research" />
    </main>
  )
}
