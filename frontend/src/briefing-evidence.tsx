import { useId, useState } from 'react'
import { eventSources, presentation, sourceLabel, type FilingEvent } from './briefing-model'

export default function BriefingEvidence({ event }: { event: FilingEvent }) {
  const sources = eventSources(event)
  const [selected, setSelected] = useState(sources[0].id)
  const selectId = useId()
  const filing = sources.find((f) => f.id === selected) || sources[0]
  const detail = presentation(filing)
  const excerpts = detail.evidence.filter(
    (item, i, all) =>
      !all.some(
        (other, j) =>
          j !== i &&
          other.quote.includes(item.quote) &&
          (other.quote.length > item.quote.length || j < i),
      ),
  )
  const date = (value: string) =>
    new Intl.DateTimeFormat('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      timeZone: 'Asia/Kolkata',
    }).format(new Date(value)) + ' IST'
  const original = filing.source_url.startsWith('https://') ? filing.source_url : null
  return (
    <details className="event-evidence">
      <summary>View evidence/details</summary>
      <div className="evidence-inspection">
        {event.filings.length > 1 && (
          <div className="evidence-source-picker">
            <label htmlFor={selectId}>Source to inspect</label>
            <select id={selectId} value={filing.id} onChange={(e) => setSelected(e.target.value)}>
              {sources.map((source, i) => (
                <option key={source.id} value={source.id}>
                  {i + 1}. {sourceLabel(source)} · {date(source.published_at)}
                </option>
              ))}
            </select>
          </div>
        )}
        <dl className="filing-source-meta">
          <div>
            <dt>Original title</dt>
            <dd>{filing.title}</dd>
          </div>
          <div>
            <dt>Filed</dt>
            <dd>{date(filing.published_at)}</dd>
          </div>
          <div>
            <dt>Filing ID</dt>
            <dd>{filing.id}</dd>
          </div>
        </dl>
        {detail.interpretation && <p>{detail.interpretation}</p>}
        {excerpts.length ? (
          excerpts.map((e, index) => (
            <div className="filing-excerpt" key={index}>
              <span>
                {e.kind === 'exchange_feed'
                  ? 'Exchange announcement'
                  : e.pdf_page
                    ? `Official document · PDF page ${e.pdf_page}`
                    : 'Official structured disclosure'}
              </span>
              <blockquote>{e.quote}</blockquote>
              {e.field && <small>Source field: {e.field}</small>}
              {original && e.pdf_page && (
                <a
                  href={`${(detail.source?.url || original).split('#')[0]}#page=${e.pdf_page}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open supporting PDF page ↗
                </a>
              )}
            </div>
          ))
        ) : (
          <p>Only the exchange headline is available. Detailed facts have not been extracted.</p>
        )}
        {detail.source && (
          <p className="source-check-note">
            Official source checked {date(detail.source.fetched_at)}.
            {detail.source.total_pages
              ? ` Native text inspected on ${detail.source.pages_scanned} of ${detail.source.total_pages} PDF pages; this is not a full-document analysis.`
              : ''}
          </p>
        )}
        {detail.limitation && <p className="source-check-note">{detail.limitation}</p>}
        {original && (
          <a href={original} target="_blank" rel="noopener noreferrer">
            Open original filing ↗
          </a>
        )}
      </div>
    </details>
  )
}
