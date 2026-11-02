import EvidenceButton, { type EvidenceCitation } from './evidence-button'
import { useRef, useState } from 'react'
import './financial-results.css'

export const RESULTS_QUESTION =
  'Compare the latest reported quarterly Revenue, EBITDA, PBT and PAT with the previous quarter and year-ago quarter.'
type Figure = {
  display_value: string
  claim_index: number
  row_label: string
  definition: string
  restated?: boolean
}
type Change = { absolute: string | null; percent: string | null; reason: string | null }
type MetricRow = {
  metric: string
  figures: Record<string, Figure>
  qoq: Change
  yoy: Change
  missing_reason: string
}
export type ResultsData = {
  periods: Record<string, string>
  bases: Record<
    string,
    {
      unit: string
      currency: string
      rows: MetricRow[]
      performance?: { statement: string; comparison: string; claim_indices: number[] }[]
      context_claim_indices?: number[]
    }
  >
  performance_caveat?: string
  performance_version?: string
  context_version?: string
  rejected_cells: string[]
  sources: {
    id: string
    source_url: string
    final_url: string
    discovery_label: string
    fetched_at: string
  }[]
  policy: string
}
export type FinancialEvidence = {
  metric: string
  raw_value: string
  row_label: string
  column_header: string
  table_header: string
  period_end: string
  unit: string
  currency: string
  accounting_basis: string
  definition: string
  image_verification?: { method: string; model: string }
}
const number = (value: string) =>
  new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(
    Number(value),
  )
const quarterDate = (value: string) =>
  value
    ? new Intl.DateTimeFormat('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        timeZone: 'Asia/Kolkata',
      }).format(new Date(value))
    : 'Unverified'

function Movement({
  change,
  onInspect,
  label,
}: {
  change: Change
  onInspect: () => void
  label: string
}) {
  const tone =
    change.absolute === null || Number(change.absolute) === 0
      ? ''
      : Number(change.absolute) > 0
        ? 'positive'
        : 'negative'
  return (
    <div className={`financial-movement ${tone}`}>
      <button
        className="financial-change-button"
        aria-label={label}
        disabled={change.absolute === null}
        onClick={onInspect}
      >
        <strong>
          {change.absolute !== null
            ? `${Number(change.absolute) > 0 ? '+' : ''}${number(change.absolute)}`
            : '—'}
        </strong>
        <span>
          {change.percent !== null
            ? `${Number(change.percent) > 0 ? '+' : ''}${number(change.percent)}%`
            : '—'}
        </span>
      </button>
      {change.reason && <small>{change.reason}</small>}
    </div>
  )
}

export default function FinancialResults({
  data,
  onEvidence,
  claims,
}: {
  data: ResultsData
  onEvidence: (index: number) => void
  claims?: { statement: string; citation?: EvidenceCitation }[]
}) {
  const available = ['consolidated', 'standalone'].filter((basis) =>
    data.bases[basis]?.rows.some((row) => Object.keys(row.figures).length > 0),
  )
  const [choice, setChoice] = useState('consolidated')
  const [calculation, setCalculation] = useState<{ row: MetricRow; kind: 'qoq' | 'yoy' } | null>(
    null,
  )
  const calculationPanel = useRef<HTMLElement>(null)
  function inspect(row: MetricRow, kind: 'qoq' | 'yoy') {
    setCalculation({ row, kind })
    requestAnimationFrame(() =>
      calculationPanel.current?.scrollIntoView({
        block: 'nearest',
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      }),
    )
  }
  const basis = available.includes(choice) ? choice : available[0]
  const statement = data.bases[basis]
  if (!statement)
    return (
      <div className="empty-evidence">
        <p>
          This filing’s figures could not yet be verified. You can inspect the original document or
          retry the remaining figures later.
        </p>
        {data.sources.map((source) => (
          <p key={source.id}>
            <a
              href={source.final_url || source.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {source.discovery_label} · Original filing ↗
            </a>
          </p>
        ))}
      </div>
    )
  return (
    <div className="financial-results" data-basis={basis}>
      <div className="financial-heading">
        <div>
          <p className="eyebrow">QUARTERLY RESULTS</p>
          <h3>Quarter ended {quarterDate(data.periods.latest)}</h3>
        </div>
        {available.length > 1 ? (
          <div className="financial-bases" role="group" aria-label="Accounting basis">
            {['consolidated', 'standalone'].map((value) => (
              <button
                type="button"
                key={value}
                disabled={!available.includes(value)}
                title={
                  !available.includes(value)
                    ? 'No verified figures are available for this accounting basis.'
                    : undefined
                }
                aria-pressed={basis === value}
                onClick={() => {
                  setChoice(value)
                  setCalculation(null)
                }}
              >
                {value === 'consolidated' ? 'Consolidated' : 'Standalone'}
              </button>
            ))}
          </div>
        ) : (
          <span className="basis-current">
            {basis === 'consolidated' ? 'Consolidated' : 'Standalone'}
          </span>
        )}
      </div>
      {available.length < 2 && (
        <p className="basis-availability">
          {available.includes('consolidated') ? 'Standalone' : 'Consolidated'} figures are
          unavailable or unverified in the current sources.
        </p>
      )}
      <p className="financial-unit">
        All figures in {statement.currency} {statement.unit}. Tap a figure to inspect its source
        cell.
      </p>
      {statement.performance?.length ? (
        <aside className="financial-performance" aria-label={`${basis} financial performance`}>
          <p className="eyebrow">WHAT THE FIGURES SHOW</p>
          {statement.performance.map((note) => (
            <div key={note.comparison}>
              <p>{note.statement}</p>
              <details>
                <summary>Inspect supporting figures</summary>
                <div className="performance-sources">
                  {note.claim_indices.map((index) => (
                    <EvidenceButton
                      type="button"
                      key={index}
                      onClick={() => onEvidence(index)}
                      citation={claims?.[index]?.citation}
                    >
                      {statement.rows.flatMap((row) =>
                        Object.entries(row.figures)
                          .filter(([, figure]) => figure.claim_index === index)
                          .map(([role]) => `${row.metric} · ${quarterDate(data.periods[role])}`),
                      )[0] || `Figure ${index + 1}`}
                    </EvidenceButton>
                  ))}
                </div>
              </details>
            </div>
          ))}
          <small>{data.performance_caveat}</small>
          {statement.context_claim_indices?.map(
            (index) =>
              claims?.[index] && (
                <div className="disclosed-context" key={index}>
                  <p className="eyebrow">DISCLOSED CONTEXT</p>
                  <button
                    type="button"
                    className="claim-statement"
                    onClick={() => onEvidence(index)}
                  >
                    {claims[index].statement}
                  </button>
                  <EvidenceButton
                    type="button"
                    onClick={() => onEvidence(index)}
                    citation={claims?.[index]?.citation}
                  >
                    Inspect original filing passage
                  </EvidenceButton>
                  <small>
                    These are disclosed items for this quarter, not a complete attribution of the
                    change.
                  </small>
                </div>
              ),
          )}
        </aside>
      ) : null}
      {statement.rows.some(
        (row) =>
          row.metric !== 'EBITDA' &&
          ['latest', 'previous', 'year_ago'].some((period) => !row.figures[period]),
      ) && (
        <p className="financial-partial">
          Some revenue or profit figures could not be verified. Available figures and valid
          comparisons are shown; missing values are left blank.
        </p>
      )}
      <div
        className="financial-table-wrap"
        tabIndex={0}
        role="region"
        aria-label="Quarterly figures; scroll horizontally on smaller screens"
      >
        <table className="financial-table" aria-label={`${basis} quarterly figures`}>
          <caption>Reported figures · {basis}</caption>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              {['latest', 'previous', 'year_ago'].map((role) => (
                <th scope="col" key={role}>
                  <span>
                    {role === 'latest'
                      ? 'Latest'
                      : role === 'previous'
                        ? 'Prior quarter'
                        : 'Year ago'}
                  </span>
                  <small>{quarterDate(data.periods[role])}</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {statement.rows.map((row) => (
              <tr key={row.metric}>
                <th scope="row">
                  {row.metric}
                  <small>
                    {row.metric === 'Revenue'
                      ? Object.values(row.figures).some(
                          (figure) => figure.definition === 'bank_total_income',
                        )
                        ? 'Bank: total income'
                        : 'From operations'
                      : row.metric === 'PAT'
                        ? basis === 'standalone'
                          ? 'Company PAT'
                          : 'Group, before attribution'
                        : row.metric === 'EBITDA'
                          ? 'Reported only'
                          : 'As reported'}
                  </small>
                </th>
                {['latest', 'previous', 'year_ago'].map((role) => (
                  <td key={role}>
                    {row.figures[role] ? (
                      <button
                        className="financial-number"
                        aria-label={`Inspect ${basis} ${row.metric} for ${data.periods[role]}`}
                        onClick={() => onEvidence(row.figures[role].claim_index)}
                      >
                        {number(row.figures[role].display_value)}
                        {row.figures[role].restated && <small>Restated</small>}
                        <span className="sr-only"> · source evidence</span>
                      </button>
                    ) : (
                      <span className="financial-missing" title={row.missing_reason}>
                        —<span className="sr-only">{row.missing_reason}</span>
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <table className="financial-table financial-changes" aria-label={`${basis} quarter changes`}>
        <caption>
          Changes · {statement.currency} {statement.unit} and percent
        </caption>
        <thead>
          <tr>
            <th scope="col">Metric</th>
            <th scope="col">QoQ</th>
            <th scope="col">YoY</th>
          </tr>
        </thead>
        <tbody>
          {statement.rows.map((row) => (
            <tr key={row.metric}>
              <th scope="row">{row.metric}</th>
              <td>
                <Movement
                  change={row.qoq}
                  label={`Inspect ${row.metric} QoQ calculation`}
                  onInspect={() => inspect(row, 'qoq')}
                />
              </td>
              <td>
                <Movement
                  change={row.yoy}
                  label={`Inspect ${row.metric} YoY calculation`}
                  onInspect={() => inspect(row, 'yoy')}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {calculation && (
        <aside
          className="financial-calculation"
          aria-label="Financial calculation"
          ref={calculationPanel}
          aria-live="polite"
        >
          <p className="eyebrow">
            {calculation.row.metric} · {calculation.kind.toUpperCase()} CALCULATION
          </p>
          <p>
            Latest − {calculation.kind === 'qoq' ? 'prior quarter' : 'year-ago quarter'} ={' '}
            {calculation.row[calculation.kind].absolute} {statement.currency} {statement.unit}.
          </p>
          <p>
            Percentage change = (latest − base) ÷ base × 100
            {calculation.row[calculation.kind].percent !== null
              ? ` = ${calculation.row[calculation.kind].percent}%.`
              : '. ' + calculation.row[calculation.kind].reason}
          </p>
          <p>
            Calculations use unrounded source values. Displayed figures are rounded to two decimals.
          </p>
          <div>
            <EvidenceButton
              onClick={() => onEvidence(calculation.row.figures.latest.claim_index)}
              citation={claims?.[calculation.row.figures.latest.claim_index]?.citation}
            >
              Latest figure evidence
            </EvidenceButton>
            <EvidenceButton
              onClick={() =>
                onEvidence(
                  calculation.row.figures[calculation.kind === 'qoq' ? 'previous' : 'year_ago']
                    .claim_index,
                )
              }
              citation={
                claims?.[
                  calculation.row.figures[calculation.kind === 'qoq' ? 'previous' : 'year_ago']
                    .claim_index
                ]?.citation
              }
            >
              Base figure evidence
            </EvidenceButton>
            <button className="text-chip" onClick={() => setCalculation(null)}>
              Close calculation
            </button>
          </div>
        </aside>
      )}
      <details className="financial-coverage">
        <summary>
          Source coverage &amp; withheld cells
          {data.rejected_cells.length ? ` · ${data.rejected_cells.length}` : ''}
        </summary>
        <p className="financial-policy">
          {data.policy} Changes are arithmetic, not an assessment of investment merit.
        </p>
        <p>
          EBITDA is unavailable when the filing does not report it explicitly. “—” is not zero.
          Figures from different accounting bases are never combined.
        </p>
        {data.sources.map((source) => (
          <p key={source.id}>
            <a href={source.final_url} target="_blank" rel="noopener noreferrer">
              {source.discovery_label} · original filing ↗
            </a>
            <small>Retrieved {quarterDate(source.fetched_at)}</small>
          </p>
        ))}
        {data.rejected_cells.length > 0 && (
          <ul>
            {data.rejected_cells.map((note, index) => (
              <li key={index}>{note}</li>
            ))}
          </ul>
        )}
      </details>
    </div>
  )
}
