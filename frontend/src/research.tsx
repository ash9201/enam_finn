import { useEffect, useRef, useState } from 'react'
import { AppFooter, PageHeading } from './layout'
import { publicRead } from './data'
import CompanyPicker from './company-picker'
import FinancialResults, {
  RESULTS_QUESTION,
  type ResultsData,
  type FinancialEvidence,
} from './financial-results'

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
  financial_evidence?: FinancialEvidence
  speaker?: { name: string; role: string; pdf_page: number }
}
type Claim = {
  statement: string
  citation: Citation
  citations?: Citation[]
  heading?: string
  financial_context_timing?: string
}
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
    topic?: string
    uncertainty?: string
    additional_context?: Claim[]
    analysis_claims?: Claim[]
  } | null
  limitations: string[]
  coverage: { annual_reports: number; transcripts: number }
  source_checked_at: string
  generated_at: string
  cached: boolean
  retrieval_mode: string
  comparison_status?: string
  assessment?: string
  financial_context?: {
    research_id: string
    symbol: string
    company_name: string
    claim_index: number
    claim: Claim
    period_end: string
    source_checked_at: string
    note: string
  }
  investigation_suggestions?: string[]
  retrieval?: {
    state?: string
    index?: { ready: number; total: number }
    fallback_reason?: string
    semantic_error?: string
  }
  timings?: { queue_ms: number; processing_ms: number; span_ms: Record<string, number> }
  financial_results?: ResultsData
  reading_version?: string
  question_coverage?: { aspect: string; label: string; status: string; note: string | null }[]
  evidence_context?: EvidenceContext
  investigation?: {
    other_documents_retrieved: number
    history_requested: boolean
    assessment?: string
  }
}
type SearchStatus = {
  state: string
  checked_at?: string
  index?: { ready: number; total: number }
  activity?: { reason?: string; retry_at?: string; updated_at?: string }
}
type ProgressSource = { id: string; kind: string; label: string; source_url: string; pages: number }

function ResearchDetails({ answer }: { answer: Answer }) {
  const [health, setHealth] = useState<SearchStatus | null>(null)
  const [checking, setChecking] = useState(false)
  const checkHealth = () => {
    if (checking) return
    setChecking(true)
    void api(`/companies/${answer.symbol}/search-status`)
      .then(setHealth)
      .catch(() => setHealth({ state: 'unavailable', checked_at: new Date().toISOString() }))
      .finally(() => setChecking(false))
  }
  const messages: Record<string, string> = {
    ready: 'The document index is ready for hybrid search.',
    indexing:
      'Document indexing is running. Research continues with keyword search until it is complete.',
    paused_quota:
      'Document indexing is paused at the free search allowance. Keyword research remains available.',
    pending:
      'The document index is incomplete; no active indexing worker is confirmed. Keyword research is available.',
    failed:
      'The last indexing attempt could not finish. Saved progress is retained and keyword research is available.',
    unavailable:
      'Live semantic-search status is unavailable. This does not affect the saved evidence below.',
    disabled: 'Semantic search is switched off. Company research uses keyword search.',
  }
  return (
    <details
      className="coverage-notes research-details"
      onToggle={(event) => {
        if (event.currentTarget.open && answer.retrieval_mode !== 'validated_financial_cells')
          checkHealth()
      }}
    >
      <summary>Sources, coverage & search details</summary>
      <p>
        {answer.financial_results
          ? `${answer.financial_results.sources.length} original results filings. Figures retain their reporting period, unit and accounting basis.`
          : `${answer.coverage.annual_reports} annual reports · ${answer.coverage.transcripts} earnings-call transcripts.`}
      </p>
      <ul>
        {answer.limitations
          .filter((note) => !note.startsWith('Additional document search is still being prepared'))
          .map((note) => (
            <li key={note}>{note}</li>
          ))}
      </ul>
      {answer.retrieval_mode !== 'validated_financial_cells' && (
        <div className="search-status">
          <strong>
            Search used for this answer: {answer.retrieval_mode === 'hybrid' ? 'Hybrid' : 'Keyword'}
          </strong>
          {health ? (
            <>
              <p>{messages[health.state] || messages.pending}</p>
              {health.index && (
                <p>
                  {health.index.ready.toLocaleString('en-IN')} of{' '}
                  {health.index.total.toLocaleString('en-IN')} passages indexed.
                </p>
              )}
              {health.activity?.retry_at && (
                <p>
                  Eligible to resume after {stamp(health.activity.retry_at)}. A later request or the
                  daily maintenance run can resume it.
                </p>
              )}
              {health.checked_at && (
                <p className="fine-print">Status checked {stamp(health.checked_at)}.</p>
              )}
              <button type="button" className="text-chip" onClick={checkHealth} disabled={checking}>
                {checking ? 'Checking search status…' : 'Refresh search status'}
              </button>
            </>
          ) : (
            <p>Checking current search availability…</p>
          )}
        </div>
      )}
      {answer.timings && (
        <details className="timing-details">
          <summary>Request timing</summary>
          <p>
            Queue {(answer.timings.queue_ms / 1000).toFixed(1)} s · Processing{' '}
            {(answer.timings.processing_ms / 1000).toFixed(1)} s
          </p>
          <dl>
            {Object.entries(answer.timings.span_ms).map(([name, ms]) => (
              <div key={name}>
                <dt>{name.replaceAll('_', ' ')}</dt>
                <dd>{(ms / 1000).toFixed(2)} s</dd>
              </div>
            ))}
          </dl>
          <small>Nested operations overlap; their times do not add up to the total.</small>
        </details>
      )}
    </details>
  )
}
type Company = {
  symbol: string
  name: string
  sector: string | null
  source_checked_at: string | null
}
type Workspace = {
  question: string
  answer: Answer | null
  savedComparison: Answer | null
  savedResults: Answer | null
  context: EvidenceContext | null
  trail: Answer[]
  includeHistory: boolean
  needsRefresh: boolean
}
const workspaces = new Map<string, Workspace>()
function savedSymbol() {
  try {
    const value = localStorage.getItem('finn-research-company') || 'INFY'
    return /^[A-Z0-9&-]{1,30}$/.test(value) ? value : 'INFY'
  } catch {
    return 'INFY'
  }
}
function savedDraft(symbol: string) {
  try {
    const value = JSON.parse(localStorage.getItem('finn-research-drafts') || '{}')[symbol]
    return typeof value === 'string' ? value.slice(0, 600) : undefined
  } catch {
    return undefined
  }
}
function savedMode(symbol: string) {
  try {
    return JSON.parse(localStorage.getItem('finn-research-modes') || '{}')[symbol]
  } catch {
    return undefined
  }
}
function answerIdentity(answer: Answer) {
  return [
    answer.id,
    answer.generated_at,
    answer.source_checked_at,
    answer.financial_results?.performance_version,
    answer.financial_results?.context_version,
    answer.reading_version,
  ].join(':')
}

function evidenceSelection(answer: Answer, claim: Claim): Selection {
  const claims = [
    ...answer.claims,
    ...([answer.comparison?.earlier, answer.comparison?.later].filter(Boolean) as Claim[]),
  ]
  const index = claims.findIndex(
    (item) =>
      item === claim ||
      (item.statement === claim.statement && item.citation.id === claim.citation.id),
  )
  return { answer, claim, claimIndex: index >= 0 ? index : undefined }
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
  onSource,
}: {
  selection: Selection
  onClose: () => void
  onAsk: (intent: Intent, citation: Citation) => void
  canFollow: boolean
  onSource: (citation: Citation) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [citation, setCitation] = useState(selection.claim.citation)
  const [verification, setVerification] = useState('Verifying source details…')
  const [unavailable, setUnavailable] = useState(false)
  const [showImage, setShowImage] = useState(false)
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
        <h2 id="evidence-title">
          {citation.financial_evidence
            ? `${citation.financial_evidence.metric} evidence`
            : citation.document_label}
        </h2>
        {citation.financial_evidence && <p className="muted">{citation.document_label}</p>}
        <p className="muted">
          {citation.kind === 'quarterly_results'
            ? 'Quarterly results filing'
            : citation.kind === 'annual_report'
              ? 'Annual report'
              : 'Call transcript'}{' '}
          · PDF page {citation.pdf_page}
        </p>
      </div>
      <div className="evidence-scroll">
        {citation.financial_evidence && (
          <section className="financial-cell-evidence" aria-label="Selected financial source cell">
            <p className="eyebrow">SELECTED SOURCE CELL</p>
            <h3>
              {citation.financial_evidence.currency} {citation.financial_evidence.raw_value}{' '}
              {citation.financial_evidence.unit}
            </h3>
            <p>
              {citation.financial_evidence.accounting_basis} · quarter ended{' '}
              {citation.financial_evidence.period_end}
            </p>
            <p>
              <strong>Reported row:</strong> {citation.financial_evidence.row_label}
            </p>
            <p>
              <strong>Selected column:</strong> {citation.financial_evidence.column_header}
            </p>
            <details>
              <summary>Original statement header</summary>
              <pre>{citation.financial_evidence.table_header}</pre>
            </details>
          </section>
        )}
        <p className="eyebrow">THE CLAIM YOU OPENED</p>
        <p className="evidence-claim">{selection.claim.statement}</p>
        {selection.claim.citations && selection.claim.citations.length > 1 && (
          <div className="evidence-source-switch" aria-label="Supporting sources">
            {selection.claim.citations.map((source, index) => (
              <button
                type="button"
                key={source.id}
                aria-pressed={source.id === citation.id}
                onClick={() => onSource(source)}
              >
                Source {index + 1} · p. {source.pdf_page}
              </button>
            ))}
          </div>
        )}
        <p className="eyebrow">
          {citation.financial_evidence?.image_verification?.method === 'two_image_reads'
            ? 'VERIFIED PAGE-IMAGE TRANSCRIPTION'
            : 'EXACT SUPPORTING PASSAGE'}
        </p>
        <blockquote>{citation.quote}</blockquote>
        {citation.financial_evidence && (
          <div className="statement-preview">
            {citation.financial_evidence.image_verification && (
              <p>
                {citation.financial_evidence.image_verification.method ===
                'native_cells_verified_header'
                  ? 'This figure comes from native PDF text; its reporting metadata was checked against two page-image reads.'
                  : citation.financial_evidence.image_verification.method ===
                      'native_prose_verified_image'
                    ? 'The disclosed amount and reporting metadata agree between native PDF text and a separate image read.'
                    : 'Two separate image reads agreed on this figure and its reporting metadata.'}{' '}
                The original page is available below.
              </p>
            )}
            <button type="button" className="text-chip" onClick={() => setShowImage(!showImage)}>
              {showImage ? 'Hide statement page' : 'View original statement page'}
            </button>
            {showImage && (
              <img
                src={`${apiBase}/research/${selection.answer.id}/evidence/${citation.id}/image?symbol=${encodeURIComponent(selection.answer.symbol)}${selection.claimIndex !== undefined ? `&claim_index=${selection.claimIndex}` : ''}`}
                alt={`Original ${selection.answer.symbol} statement, PDF page ${citation.pdf_page}`}
                onError={() =>
                  setVerification(
                    'The page preview is unavailable. Open the original PDF using the link below.',
                  )
                }
              />
            )}
          </div>
        )}
        <p className="fine-print" role="status">
          {verification}
        </p>
        <dl>
          {citation.speaker && (
            <div>
              <dt>Management speaker</dt>
              <dd>
                {citation.speaker.name} · {citation.speaker.role}
                <small>
                  Role identified in the original introduction, PDF p. {citation.speaker.pdf_page}.
                </small>
              </dd>
            </div>
          )}
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

export default function ResearchApp({ active = true }: { active?: boolean }) {
  const [companies, setCompanies] = useState<Company[]>([])
  const initial = new URLSearchParams(window.location.search)
  const initialSymbol = (initial.get('symbol') || savedSymbol()).toUpperCase().replace(/\.NS$/, '')
  const session = workspaces.get(initialSymbol)
  const [ticker, setTicker] = useState(initialSymbol)
  const [question, setQuestion] = useState(
    initial.get('question')?.slice(0, 600) ||
      (initial.get('analysis') === 'results'
        ? RESULTS_QUESTION
        : (session?.question ?? savedDraft(initialSymbol) ?? DEFAULT_QUESTION)),
  )
  const [needsRefresh, setNeedsRefresh] = useState(initial.get('refresh') === '1')
  const [answer, setAnswer] = useState<Answer | null>(
    initial.get('analysis') === 'results' ? session?.savedResults || null : session?.answer || null,
  )
  const [stage, setStage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [progressSources, setProgressSources] = useState<ProgressSource[]>([])
  const [loadingSaved, setLoadingSaved] = useState(true)
  const [selected, setSelected] = useState<Selection | null>(null)
  const [context, setContext] = useState<EvidenceContext | null>(
    initial.get('analysis') === 'results' ? null : session?.context || null,
  )
  const [includeHistory, setIncludeHistory] = useState(session?.includeHistory || false)
  const [trail, setTrail] = useState<Answer[]>(session?.trail || [])
  const [pickingCompany, setPickingCompany] = useState(false)
  const questionInput = useRef<HTMLTextAreaElement>(null)
  const composer = useRef<HTMLElement>(null)
  const answerPanel = useRef<HTMLElement>(null)
  const [savedComparison, setSavedComparison] = useState<Answer | null>(
    session?.savedComparison || null,
  )
  const [savedResults, setSavedResults] = useState<Answer | null>(session?.savedResults || null)
  const generation = useRef(0)
  const savedGeneration = useRef(0)
  const savedReads = useRef(new Map<string, Promise<Answer | null>>())
  const mounted = useRef(true)
  const latestWorkspace = useRef<Workspace>(null!)
  latestWorkspace.current = {
    question,
    answer,
    savedComparison,
    savedResults,
    context,
    trail,
    includeHistory,
    needsRefresh,
  }
  useEffect(() => {
    workspaces.set(ticker, latestWorkspace.current)
    try {
      localStorage.setItem('finn-research-company', ticker)
      const drafts = JSON.parse(localStorage.getItem('finn-research-drafts') || '{}')
      drafts[ticker] = question
      localStorage.setItem(
        'finn-research-drafts',
        JSON.stringify(Object.fromEntries(Object.entries(drafts).slice(-20))),
      )
      if (answer?.symbol === ticker && !answer.evidence_context) {
        const modes = JSON.parse(localStorage.getItem('finn-research-modes') || '{}')
        modes[ticker] = answer.financial_results
          ? 'results'
          : answer.comparison
            ? 'comparison'
            : 'overview'
        localStorage.setItem('finn-research-modes', JSON.stringify(modes))
      }
    } catch {
      /* In-memory workspace remains usable. */
    }
  }, [
    ticker,
    question,
    answer,
    savedComparison,
    savedResults,
    context,
    trail,
    includeHistory,
    needsRefresh,
  ])

  useEffect(() => {
    if (!active) setSelected(null)
  }, [active])

  useEffect(() => {
    if (!busy) return
    const start = Date.now()
    setElapsed(0)
    const timer = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - start) / 1000)),
      1000,
    )
    return () => window.clearInterval(timer)
  }, [busy])

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
      savedGeneration.current += 1
    }
  }, [])

  useEffect(() => {
    if (busy) return
    const token = ++generation.current
    const savedToken = ++savedGeneration.current
    const restored = workspaces.get(ticker)?.answer
    setLoadingSaved(!restored)
    const comparisonRead = publicRead('finn_research_cache', {
      select: 'result',
      symbol: `eq.${ticker}`,
      question: `eq.${COMPARISON_QUESTION}`,
      is_public: 'eq.true',
      order: 'created_at.desc',
      limit: '1',
    })
    const resultsRead = publicRead('finn_research_cache', {
      select: 'result',
      symbol: `eq.${ticker}`,
      question: `eq.${RESULTS_QUESTION}`,
      is_public: 'eq.true',
      order: 'created_at.desc',
      limit: '1',
    })
    savedReads.current.set(
      `${ticker}:${COMPARISON_QUESTION}`,
      comparisonRead
        .then((rows) => (rows[0] ? { ...rows[0].result, cached: true } : null))
        .catch(() => null),
    )
    savedReads.current.set(
      `${ticker}:${RESULTS_QUESTION}`,
      resultsRead
        .then((rows) => (rows[0] ? { ...rows[0].result, cached: true } : null))
        .catch(() => null),
    )
    publicRead('finn_research_cache', {
      select: 'result,created_at',
      symbol: `eq.${ticker}`,
      question: `eq.${[RESULTS_QUESTION, COMPARISON_QUESTION].includes(question) ? question : savedMode(ticker) === 'results' ? RESULTS_QUESTION : savedMode(ticker) === 'comparison' ? COMPARISON_QUESTION : DEFAULT_QUESTION}`,
      is_public: 'eq.true',
      order: 'created_at.desc',
      limit: '1',
    })
      .then((rows) => {
        if (generation.current === token && !restored)
          setAnswer(rows[0] ? { ...rows[0].result, cached: true } : null)
      })
      .catch(() => {
        if (generation.current === token)
          setError('Saved research is temporarily unavailable. You can still submit a question.')
      })
      .finally(() => {
        if (generation.current === token) setLoadingSaved(false)
      })
    comparisonRead
      .then((rows) => {
        if (savedGeneration.current === savedToken && rows[0])
          setSavedComparison((previous) =>
            previous && Date.parse(previous.generated_at) > Date.parse(rows[0].result.generated_at)
              ? previous
              : { ...rows[0].result, cached: true },
          )
      })
      .catch(() => {})
    // A completed job should remain visible; switching companies triggers this read.
    resultsRead
      .then((rows) => {
        if (savedGeneration.current === savedToken && rows[0])
          setSavedResults((previous) =>
            previous && Date.parse(previous.generated_at) > Date.parse(rows[0].result.generated_at)
              ? previous
              : { ...rows[0].result, cached: true },
          )
      })
      .catch(() => {})
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
      setError('Choose a listed company using the company search.')
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
    setProgressSources([])
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
        if (started.state !== 'completed' || attempt > 0)
          await new Promise((resolve) => setTimeout(resolve, attempt === 0 ? 400 : 1800))
        if (!mounted.current || generation.current !== token) return
        const job =
          attempt === 0 && started.state === 'completed'
            ? started
            : await api(`/jobs/${started.job_id}`)
        if (job.result?._progress?.sources) setProgressSources(job.result._progress.sources)
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
          if (job.result.financial_results) setSavedResults(job.result)
          if (answer?.symbol === symbol)
            setTrail((items) =>
              [...items.filter((item) => item.id !== answer.id), answer].slice(-6),
            )
          setAnswer((previous) =>
            previous && answerIdentity(previous) === answerIdentity(job.result)
              ? previous
              : job.result,
          )
          setQuestion(query)
          setContext(anchor)
          setIncludeHistory(history)
          setNeedsRefresh(false)
          setStage('')
          requestAnimationFrame(() =>
            answerPanel.current?.scrollIntoView({
              behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
                ? 'auto'
                : 'smooth',
              block: 'start',
            }),
          )
          return
        }
        const stages: Record<string, string> = {
          queued: 'Waiting for a research worker…',
          corpus_check: 'Checking the company’s saved documents…',
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
          job.stage.startsWith('visual:')
            ? `Reading and cross-checking the original statement image · PDF p. ${document}`
            : job.stage.startsWith('extraction:')
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
    if (symbol === ticker) return
    workspaces.set(ticker, latestWorkspace.current)
    const previous = workspaces.get(symbol)
    generation.current += 1
    savedGeneration.current += 1
    setTicker(symbol)
    setContext(previous?.context || null)
    setIncludeHistory(previous?.includeHistory || false)
    setTrail(previous?.trail || [])
    setSelected(null)
    setSavedComparison(previous?.savedComparison || null)
    setSavedResults(previous?.savedResults || null)
    setQuestion(previous?.question ?? savedDraft(symbol) ?? (context ? DEFAULT_QUESTION : question))
    setNeedsRefresh(previous?.needsRefresh || false)
    setError('')
    setAnswer(previous?.answer || null)
    if (active) {
      const url = new URL(window.location.href)
      url.searchParams.set('symbol', symbol)
      for (const key of ['analysis', 'question', 'refresh']) url.searchParams.delete(key)
      window.history.replaceState(null, '', url.pathname + url.search)
      window.dispatchEvent(
        new CustomEvent('finn:research-location', { detail: url.pathname + url.search }),
      )
    }
  }
  async function explore(query: string) {
    if (busy || pickingCompany) return
    const token = ++generation.current
    setQuestion(query)
    setContext(null)
    setIncludeHistory(false)
    setNeedsRefresh(false)
    setError('')
    let saved =
      query === RESULTS_QUESTION
        ? savedResults
        : query === COMPARISON_QUESTION
          ? savedComparison
          : null
    if (!saved)
      saved = await (savedReads.current.get(`${ticker}:${query}`) || Promise.resolve(null))
    if (!mounted.current || generation.current !== token) return
    if (saved?.symbol === ticker) {
      setLoadingSaved(false)
      if (answer && answer.id !== saved.id)
        setTrail((items) => [...items.filter((item) => item.id !== answer.id), answer].slice(-6))
      setAnswer((previous) =>
        previous && answerIdentity(previous) === answerIdentity(saved) ? previous : saved,
      )
      requestAnimationFrame(() =>
        answerPanel.current?.scrollIntoView({
          block: 'start',
          behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
            ? 'auto'
            : 'smooth',
        }),
      )
    } else {
      void ask(false, query, null, false)
      requestAnimationFrame(() =>
        document.querySelector('.research-progress')?.scrollIntoView({ block: 'nearest' }),
      )
    }
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
      const previous = [...trail]
        .reverse()
        .find((item) => !item.evidence_context && item.symbol === ticker)
      setAnswer(previous || null)
      if (previous?.financial_results) setQuestion(RESULTS_QUESTION)
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
  const comparisonAnswer = current?.comparison ? current : null
  const visibleTrail = trail.filter((item) => item.id !== current?.id)
  const researchContent = (
    <main className="research-app" id="research-content" tabIndex={-1}>
      <PageHeading title="Company Research" />
      <section className="research-form" aria-labelledby="research-heading" ref={composer}>
        <h2 id="research-heading" className="sr-only">
          {context ? 'Follow selected evidence' : 'Research workspace'}
        </h2>
        <CompanyPicker
          symbol={ticker}
          watchlist={companies}
          disabled={busy}
          onSelect={choose}
          onEditing={setPickingCompany}
        />
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
            if (!pickingCompany) void ask()
          }}
        >
          <div className="form-row">
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
            {context && <p>Searching {context.symbol} across company documents.</p>}
            <button type="submit" disabled={busy || pickingCompany}>
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
        <section className="explore-company" aria-labelledby="explore-heading">
          <h3 id="explore-heading">Explore this company</h3>
          <div className="explore-actions">
            {[
              {
                id: 'results',
                label: 'Quarterly results',
                detail: 'Revenue, profit and quarterly changes',
                query: RESULTS_QUESTION,
              },
              {
                id: 'outlook',
                label: 'Management outlook',
                detail: 'Demand and growth',
                query: QUESTIONS[1],
              },
              {
                id: 'risks',
                label: 'Business risks',
                detail: 'Risks in company disclosures',
                query: QUESTIONS[2],
              },
              {
                id: 'comparison',
                label: 'Track management statements',
                detail: 'Earlier statements and later evidence',
                query: COMPARISON_QUESTION,
              },
            ].map((action) => (
              <button
                type="button"
                data-research-action={action.id}
                aria-pressed={!context && (busy ? question : current?.question) === action.query}
                key={action.id}
                disabled={busy || pickingCompany}
                title={action.detail}
                onClick={() => explore(action.query)}
              >
                <strong>
                  {action.label} <span aria-hidden="true">&#8599;</span>
                </strong>
                <small>{action.detail}</small>
              </button>
            ))}
          </div>
        </section>
        {context && (
          <div className="question-options" aria-label="Evidence investigation paths">
            {PATHS.map((path) => (
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
        )}
      </section>
      {busy && (
        <div className="research-progress" role="status" aria-live="polite">
          <span className="pulse-dot" />
          <div>
            <strong>{stage}</strong>
            <span className="elapsed-time">
              {elapsed < 60
                ? `${elapsed}s elapsed`
                : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s elapsed`}
            </span>
            <p>
              {current
                ? 'You can continue reading the saved research below while this request runs.'
                : 'First-time preparation takes longer. Original documents appear below as they are saved.'}
            </p>
          </div>
        </div>
      )}
      {(busy || error) && progressSources.length > 0 && (
        <details className="preparation-sources" aria-label="Documents saved during preparation">
          <summary>
            {progressSources.length} primary{' '}
            {progressSources.length === 1 ? 'document' : 'documents'} saved
          </summary>
          <ul>
            {progressSources.map((source) => (
              <li key={source.id}>
                <a href={source.source_url} target="_blank" rel="noopener noreferrer">
                  {source.kind.replaceAll('_', ' ')} · {source.label} ↗
                </a>
                <span>{source.pages} PDF pages</span>
              </li>
            ))}
          </ul>
          <small>
            These documents will be reused on retry. Saving a document does not yet establish an
            answer.
          </small>
        </details>
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
        <section
          key={answerIdentity(current)}
          className="answer-panel"
          aria-labelledby="answer-heading"
          ref={answerPanel}
        >
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
          {current.question_coverage?.some((item) => item.status !== 'covered') && (
            <aside className="question-gaps" aria-label="Unresolved parts of your question">
              {current.question_coverage
                .filter((item) => item.status !== 'covered')
                .map((item) => (
                  <p key={item.aspect}>
                    <strong>{item.label}:</strong> {item.note}
                  </p>
                ))}
            </aside>
          )}
          {current.investigation?.assessment && (
            <p className="investigation-note" role="status">
              {current.investigation.assessment}
            </p>
          )}
          {current.financial_results ? (
            <FinancialResults
              key={answerIdentity(current)}
              data={current.financial_results}
              claims={current.claims}
              onEvidence={(index) => {
                const claim = current.claims[index]
                if (claim) setSelected(evidenceSelection(current, claim))
              }}
            />
          ) : current.comparison ? null : current.claims.length ? (
            <ol className="claim-list">
              {current.claims.map((claim, index) => (
                <li key={`${claim.citation.id}-${index}`}>
                  <div>
                    {claim.heading && <h3 className="analysis-heading">{claim.heading}</h3>}
                    {current.evidence_context && (
                      <span className="source-relation">
                        {claim.financial_context_timing ||
                          (claim.citation.document_id ===
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
                                : 'Another company document')}
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
                    <div className="claim-sources">
                      {(claim.citations || [claim.citation]).map((citation, sourceIndex) => (
                        <button
                          className="citation-button"
                          key={`${citation.id}-${sourceIndex}`}
                          onClick={() =>
                            setSelected({
                              ...evidenceSelection(current, claim),
                              claim: { ...claim, citation },
                            })
                          }
                        >
                          {citation.document_label} · PDF p. {citation.pdf_page}
                          <span aria-hidden="true"> ↗</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <div className="empty-evidence">
              <p>
                {current.assessment ||
                  'The available passages do not yet support this question. Try an investigation below or check the latest company documents.'}
              </p>
              {current.investigation_suggestions && (
                <div className="investigation-options">
                  {current.investigation_suggestions.map((q) => (
                    <button
                      key={q}
                      className="text-chip"
                      disabled={busy}
                      onClick={() => void ask(false, q, null, false)}
                    >
                      {q} ↗
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {comparisonAnswer?.symbol === ticker && comparisonAnswer.comparison && (
            <section className="comparison-content" aria-labelledby="comparison-heading">
              <p className="eyebrow">NARRATIVE & EVIDENCE</p>
              <div className="comparison-title">
                <h3 id="comparison-heading">
                  {comparisonAnswer.comparison.topic || 'Follow the statement.'}
                </h3>
                <span className="saved-label">
                  {(
                    {
                      supported: 'Later evidence supports it',
                      diverged: 'Evidence diverges',
                      not_assessable: 'Not yet assessable',
                      not_yet_assessable: 'Not yet assessable',
                      reaffirmed: 'Outlook reaffirmed',
                      revised: 'Outlook revised',
                      progress_reported: 'Progress reported',
                      delivered: 'Milestone completed',
                    } as Record<string, string>
                  )[comparisonAnswer.comparison.verdict] || 'Review the evidence'}
                </span>
              </div>
              <div className="comparison-sides">
                {[
                  ['Earlier statement', comparisonAnswer.comparison.earlier],
                  ['Later evidence', comparisonAnswer.comparison.later],
                ].map(([heading, raw]) => {
                  const claim = raw as Claim
                  return (
                    <div key={heading as string}>
                      <p className="eyebrow">{heading as string}</p>
                      <button
                        className="claim-statement"
                        onClick={() => setSelected(evidenceSelection(comparisonAnswer, claim))}
                      >
                        {claim.statement}
                      </button>
                      <button
                        className="citation-button"
                        onClick={() => setSelected(evidenceSelection(comparisonAnswer, claim))}
                      >
                        {claim.citation.document_label} · PDF p. {claim.citation.pdf_page} ↗
                      </button>
                    </div>
                  )
                })}
              </div>
              {comparisonAnswer.comparison.analysis_claims?.length ? (
                <div className="comparison-analysis" aria-label="What the evidence indicates">
                  {comparisonAnswer.comparison.analysis_claims.map((claim) => (
                    <div key={claim.citation.id + claim.statement}>
                      <button
                        className="claim-statement"
                        onClick={() => setSelected(evidenceSelection(comparisonAnswer, claim))}
                      >
                        {claim.statement}
                      </button>
                      <div className="claim-sources">
                        {(claim.citations || [claim.citation]).map((citation) => (
                          <button
                            className="citation-button"
                            key={citation.id}
                            onClick={() =>
                              setSelected({
                                ...evidenceSelection(comparisonAnswer, claim),
                                claim: { ...claim, citation },
                              })
                            }
                          >
                            {citation.document_label} · PDF p. {citation.pdf_page} ↗
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="comparison-assessment">{comparisonAnswer.comparison.assessment}</p>
              )}
              {comparisonAnswer.comparison.uncertainty && (
                <p className="comparison-uncertainty">{comparisonAnswer.comparison.uncertainty}</p>
              )}
              {comparisonAnswer.financial_context && (
                <aside className="comparison-context">
                  <p className="eyebrow">REPORTED QUARTER CONTEXT</p>
                  <button
                    className="claim-statement"
                    onClick={() => {
                      const f = comparisonAnswer.financial_context!
                      setSelected({
                        answer: {
                          id: f.research_id,
                          symbol: f.symbol,
                          company_name: f.company_name,
                        },
                        claim: f.claim,
                        claimIndex: f.claim_index,
                      })
                    }}
                  >
                    {comparisonAnswer.financial_context.claim.statement}
                  </button>
                  <p className="fine-print">{comparisonAnswer.financial_context.note}</p>
                </aside>
              )}
              {comparisonAnswer.comparison.additional_context?.map((claim) => (
                <div className="comparison-context" key={claim.citation.id}>
                  <button
                    className="claim-statement"
                    onClick={() => setSelected(evidenceSelection(comparisonAnswer, claim))}
                  >
                    {claim.statement}
                  </button>
                  <button
                    className="citation-button"
                    onClick={() => setSelected(evidenceSelection(comparisonAnswer, claim))}
                  >
                    {claim.citation.document_label} · PDF p. {claim.citation.pdf_page} ↗
                  </button>
                </div>
              ))}
              <p className="fine-print">
                Statement-level assessment from the cited company documents.
              </p>
            </section>
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
          <ResearchDetails key={current.id} answer={current} />
        </section>
      )}
      {!current && !busy && !loadingSaved && (
        <section className="research-empty">
          <span aria-hidden="true">↗</span>
          <h2>No saved answer yet</h2>
          <p>
            Choose a company and investigate. FINN will find original documents and show what the
            evidence can—and cannot—support.
          </p>
        </section>
      )}
      <AppFooter>
        <span>Reports and calls · No live market prices</span>
      </AppFooter>
      {selected && (
        <Evidence
          key={selected.claim.citation.id}
          selection={selected}
          onClose={() => setSelected(null)}
          onAsk={followEvidence}
          canFollow={!busy}
          onSource={(citation) =>
            setSelected({ ...selected, claim: { ...selected.claim, citation } })
          }
        />
      )}
    </main>
  )
  return researchContent
}
