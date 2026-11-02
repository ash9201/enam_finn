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
}: {
  figures: Figure[]
  onEvidence: (index: number) => void
}) {
  return (
    <ul>
      {figures.map((input, i) => (
        <li key={i}>
          <strong>{input.name}:</strong> {input.display_value} {unitLabel(input)} ·{' '}
          {input.period_end} · {input.basis}{' '}
          {input.claim_index !== undefined && (
            <button className="citation-button" onClick={() => onEvidence(input.claim_index!)}>
              Source
            </button>
          )}
          {!!input.inputs?.length && (
            <InputSources figures={input.inputs} onEvidence={onEvidence} />
          )}
        </li>
      ))}
    </ul>
  )
}

export default function FinancialMetrics({
  data,
  onEvidence,
}: {
  data: MetricData
  onEvidence: (index: number) => void
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
                  <InputSources figures={result.inputs || []} onEvidence={onEvidence} />
                  <small>All inputs retain their original citations in the evidence panel.</small>
                </details>
              )}
              <button
                className="citation-button"
                onClick={() => result.claim_index !== undefined && onEvidence(result.claim_index)}
              >
                {result.method === 'calculated' ? 'Inspect input sources' : 'View source evidence'}{' '}
                <span aria-hidden="true">↗</span>
              </button>
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
