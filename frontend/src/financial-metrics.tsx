import EvidenceButton, { type EvidenceCitation } from './evidence-button'
import './financial-metrics.css'

type Figure = {
  name: string
  display_value: string
  unit: string
  currency?: string | null
  period_end: string
  basis: string
  inputs?: Figure[]
  claim_index?: number
  period_kind?: string
}
type MetricResult = Partial<Figure> & {
  id: string
  name: string
  status: 'verified' | 'unavailable'
  method?: string
  formula?: string
  interpretation?: string
  reason?: string
  claim_index?: number
  support: string
  requested_years?: number[]
  requested_period_ends?: string[]
}
export type MetricData = { results: MetricResult[]; numerical_intent_satisfied: boolean }

const unitLabel = (figure: Partial<Figure>) =>
  figure.unit === 'times'
    ? '×'
    : figure.unit === '%'
      ? '%'
      : `${figure.currency || ''} ${figure.unit?.startsWith('per_') ? figure.unit.replace('_', ' ') : figure.unit || ''}`.trim()

function InputSources({
  figures,
  onEvidence,
  citations,
}: {
  figures: Figure[]
  onEvidence: (index: number) => void
  citations: EvidenceCitation[]
}) {
  return (
    <ul>
      {figures.map((input, i) => (
        <li key={i}>
          <strong>{input.name}:</strong> {input.display_value} {unitLabel(input)} ·{' '}
          {input.period_end} · {input.basis}{' '}
          {input.claim_index !== undefined && (
            <EvidenceButton
              citation={citations[input.claim_index]}
              onClick={() => onEvidence(input.claim_index!)}
            />
          )}
          {!!input.inputs?.length && (
            <InputSources figures={input.inputs} onEvidence={onEvidence} citations={citations} />
          )}
        </li>
      ))}
    </ul>
  )
}

export default function FinancialMetrics({
  data,
  onEvidence,
  citations,
}: {
  data: MetricData
  onEvidence: (index: number) => void
  citations: EvidenceCitation[]
}) {
  return (
    <section className="metric-answers" aria-label="Verified financial metrics">
      {data.results.map((result, index) => (
        <article className="metric-answer" key={`${result.id}-${result.period_end || index}`}>
          <div className="metric-title">
            <h3>{result.name}</h3>
            <span className="saved-label">
              {result.status === 'unavailable'
                ? 'Not verified'
                : result.method === 'calculated'
                  ? 'Calculated'
                  : 'Reported'}
            </span>
          </div>
          {result.status === 'verified' ? (
            <>
              <p className="metric-value">
                {result.display_value}
                <span>{unitLabel(result)}</span>
              </p>
              <p className="metric-period">
                {result.period_kind === 'quarter'
                  ? 'Quarter ended '
                  : result.period_kind === 'year'
                    ? 'Year ended '
                    : result.period_kind === 'stub'
                      ? 'Partial period to '
                      : 'At '}
                {result.period_end} · {result.basis}
              </p>
              <p>{result.interpretation}</p>
              {result.formula && (
                <details className="metric-formula">
                  <summary>Formula and verified inputs</summary>
                  <p>{result.formula}</p>
                  <InputSources
                    figures={result.inputs || []}
                    onEvidence={onEvidence}
                    citations={citations}
                  />
                  <small>All inputs retain their original citations in the evidence panel.</small>
                </details>
              )}
              <EvidenceButton
                citation={
                  result.claim_index !== undefined ? citations[result.claim_index] : undefined
                }
                onClick={() => result.claim_index !== undefined && onEvidence(result.claim_index)}
              >
                {result.method === 'calculated' ? 'Inspect input sources' : 'View evidence'}
              </EvidenceButton>
              {result.support === 'dated_reported_only' && (
                <p className="metric-period">Dated reported value · Not a live valuation</p>
              )}
            </>
          ) : (
            <>
              {!!(result.requested_period_ends?.length || result.requested_years?.length) && (
                <p className="metric-period">
                  Requested:{' '}
                  {(result.requested_period_ends?.length
                    ? result.requested_period_ends
                    : result.requested_years
                  )?.join(', ')}
                  {result.basis ? ` · ${result.basis}` : ''}
                </p>
              )}
              <p className="metric-missing" role="status">
                {result.reason}
              </p>
            </>
          )}
        </article>
      ))}
    </section>
  )
}
