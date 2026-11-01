export type FilingEvidence = {
  quote: string
  pdf_page: number | null
  field?: string | null
  kind: string
}
export type FilingDetails = {
  version: string
  status: string
  headline: string
  summary: string | null
  category: string
  priority: number
  event_kind: string
  event_key: string | null
  period_end: string | null
  effective_date?: string | null
  additional_details?: string[]
  recording_reference?: { call_date: string; url: string; kind: string; event_key: string } | null
  actual_results: boolean
  interpretation: string | null
  evidence: FilingEvidence[]
  limitation: string | null
  checked_at: string
  source: {
    url: string
    method: string
    sha256: string
    total_pages: number | null
    pages_scanned: number | null
    fetched_at: string
  } | null
}
export type Filing = {
  id: string
  symbol: string
  company_name: string
  title: string
  description: string
  source_url: string
  published_at: string
  category: string
  priority: number
  review_reason: string
  enrichment?: FilingDetails | null
}
export type Company = { symbol: string; name: string; sector: string }
export type FilingEvent = {
  key: string
  symbol: string
  filings: Filing[]
  title: string
  summary: string | null
  priority: number
  category: string
  actualResults: boolean
  newest: string
}
export type FilingFilters = {
  company: string
  category: string
  review: string
  window: string
  start: string
  end: string
}
export const CATEGORIES: Record<string, string> = {
  results: 'Results',
  management_change: 'Leadership',
  corporate_action: 'Corporate actions',
  business_update: 'Business updates',
  m_and_a: 'Mergers & acquisitions',
  litigation: 'Legal & regulatory',
  capital: 'Funding & debt',
  credit_rating: 'Credit ratings',
  earnings_call: 'Calls & presentations',
  meeting_notice: 'Board meeting notices',
  investor_meeting: 'Investor meeting notices',
  publication: 'Publications',
  routine: 'Routine disclosures',
  unclassified: 'Classification pending',
}

export function presentation(filing: Filing): FilingDetails {
  if (filing.enrichment?.version?.startsWith('official-filing-narrative-')) return filing.enrichment
  const body = filing.description.split('|SUBJECT:')[0].trim()
  const scheduled =
    /independent\s+director/i.test(body) &&
    /complet\w*.{0,45}(?:term|tenure)/i.test(body) &&
    !/\bresign(?:ed|ation)?\b/i.test(body)
  let summary = body
    .replace(
      /^.{0,180}?(?:has informed the Exchange(?: that| about| regarding)?|has submitted to the Exchange[, ]*)\s*/i,
      '',
    )
    .replace(/\(?\bDIN\s*[:\-]?\s*\d{8}\)?/gi, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (
    summary.toLowerCase().replace(/[ .]+$/, '') ===
      filing.title.toLowerCase().replace(/[ .]+$/, '') ||
    /^change in directors\/kmp|^general updates$/i.test(summary)
  )
    summary = ''
  const category = scheduled ? 'management_change' : filing.category
  return {
    version: 'exchange-feed-presentation',
    status: summary ? 'feed_details' : 'headline_only',
    headline: scheduled
      ? 'Independent director completes scheduled term'
      : category === 'results'
        ? 'Financial results disclosure'
        : category === 'meeting_notice'
          ? 'Board meeting notice'
          : category === 'unclassified'
            ? 'Announcement awaiting classification'
            : filing.title,
    summary: summary ? summary[0].toUpperCase() + summary.slice(1) : null,
    category,
    priority: scheduled ? 1 : filing.priority,
    event_kind: category,
    event_key: null,
    period_end: null,
    actual_results: /(?:approved|submitted|adopted).{0,170}financial results/i.test(body),
    interpretation: scheduled
      ? 'Scheduled term completion is disclosed; an unexpected resignation is not established.'
      : null,
    evidence: summary ? [{ quote: body, pdf_page: null, kind: 'exchange_feed' }] : [],
    limitation: null,
    checked_at: '',
    source: null,
  }
}

export function dateBounds(filters: FilingFilters, now = Date.now()) {
  const from =
    filters.window === 'custom'
      ? filters.start
        ? new Date(`${filters.start}:00+05:30`).getTime()
        : 0
      : now - (filters.window === '7d' ? 7 : 1) * 86400000
  const to =
    filters.window === 'custom' && filters.end
      ? new Date(`${filters.end}:00+05:30`).getTime() + 59999
      : now
  return { from, to, valid: Number.isFinite(from) && Number.isFinite(to) && from <= to }
}

export function selectFilings(
  filings: Filing[],
  filters: FilingFilters,
  reviewed: ReadonlySet<string>,
  now = Date.now(),
) {
  const bounds = dateBounds(filters, now)
  if (!bounds.valid) return []
  return filings
    .filter((filing) => {
      const date = new Date(filing.published_at).getTime(),
        detail = presentation(filing)
      return (
        date >= bounds.from &&
        date <= bounds.to &&
        (!filters.company || filing.symbol === filters.company) &&
        (!filters.category || detail.category === filters.category) &&
        (filters.review === 'all' || reviewed.has(filing.id) === (filters.review === 'reviewed'))
      )
    })
    .sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at))
}

export function makeEvent(filings: Filing[], key: string): FilingEvent {
  const ordered = [...filings].sort(
    (a, b) =>
      presentation(b).priority - presentation(a).priority ||
      Date.parse(b.published_at) - Date.parse(a.published_at),
  )
  const lead =
    ordered.find((f) => presentation(f).actual_results && presentation(f).category === 'results') ||
    ordered.find((f) => presentation(f).recording_reference && presentation(f).period_end) ||
    ordered[0]
  const detail = presentation(lead)
  return {
    key,
    symbol: lead.symbol,
    filings: [...filings].sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at)),
    title:
      filings.length > 1 && detail.event_kind === 'results'
        ? detail.headline + ' & related disclosures'
        : detail.headline,
    summary: detail.summary,
    priority: Math.max(...filings.map((f) => presentation(f).priority)),
    category:
      ordered.some((f) => presentation(f).category === 'unclassified') &&
      ordered.every((f) => presentation(f).category === 'unclassified')
        ? 'unclassified'
        : detail.category,
    actualResults: filings.some(
      (f) => presentation(f).actual_results && presentation(f).category === 'results',
    ),
    newest: filings.reduce(
      (latest, f) => (f.published_at > latest ? f.published_at : latest),
      filings[0].published_at,
    ),
  }
}

export function groupEvents(filings: Filing[]): FilingEvent[] {
  const groups = new Map<string, Filing[]>()
  for (const filing of filings) {
    // Only explicit source-backed relationships. No same-day/company deduplication.
    const key = `${filing.symbol}:${presentation(filing).event_key || filing.id}`
    groups.set(key, [...(groups.get(key) || []), filing])
  }
  return [...groups].map(([key, items]) => makeEvent(items, key))
}

const normalized = (text: string) =>
  text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()

export function eventExplanation(event: FilingEvent) {
  const candidates = [
    event.summary,
    ...event.filings.flatMap((filing) => {
      const detail = presentation(filing)
      return [detail.summary, ...(detail.additional_details || [])]
    }),
  ]
  const facts: string[] = []
  for (const original of candidates) {
    if (
      !original ||
      /^Supporting debt disclosure within|\b(?:attach|enclos)\w*.{0,35}(?:media|press) release/i.test(
        original,
      )
    )
      continue
    // A narrow wording cleanup; the underlying exact source passages stay unchanged.
    const text = original.replace(
      /^Accordingly, (he|she|they) (?:has|have) also ceased to be a Director of (.+?), material unlisted subsidiary of the Company and member of (.+?) of the Company, effective from said date\.$/i,
      (_, person: string, subsidiary: string, committee: string) =>
        `${person.toLowerCase() === 'he' ? 'His' : person.toLowerCase() === 'she' ? 'Her' : 'Their'} directorship of ${subsidiary}, a material unlisted subsidiary, and membership of the ${committee} also ended on the same date.`,
    )
    const key = normalized(text)
    if (facts.some((fact) => normalized(fact).includes(key))) continue
    // Prefer a complete version of the same passage, retaining distinct additional facts.
    const shorter = facts.findIndex((fact) => key.includes(normalized(fact)))
    if (shorter >= 0) facts[shorter] = text
    else facts.push(text)
  }
  return facts.join(' ')
}

export function companyPreview(events: FilingEvent[]) {
  return [...new Set(events.map((event) => event.title))].slice(0, 2).join(' · ')
}

export function eventCategory(event: FilingEvent) {
  return (
    (
      {
        results: 'Financial results',
        corporate_action: 'Corporate action',
        earnings_call: 'Earnings call',
        unclassified: 'Disclosure',
        meeting_notice: 'Board meeting',
        investor_meeting: 'Investor meeting',
      } as Record<string, string>
    )[event.category] ||
    CATEGORIES[event.category] ||
    'Disclosure'
  )
}

export function sourceLabel(filing: Filing) {
  const detail = presentation(filing)
  const structured = /\.xml(?:$|\?)/i.test(filing.source_url)
  let purpose = detail.headline
  if (detail.recording_reference || /recording/i.test(purpose))
    purpose = structured ? 'Structured recording disclosure' : 'Earnings-call recording notice'
  else if (detail.event_kind === 'scheduled_tenure')
    purpose = structured ? 'Structured leadership disclosure' : 'Director tenure notice'
  else if (/board meeting/i.test(filing.title)) purpose = 'Board outcome'
  else if (/financial results updates/i.test(filing.title)) purpose = 'Quarterly results filing'
  else if (/record date/i.test(filing.title)) purpose = 'Dividend record-date notice'
  else if (/dividend/i.test(filing.title)) purpose = 'Dividend declaration'
  else if (/press release/i.test(filing.title)) purpose = 'Results press release'
  return `${purpose}${structured || !/\.pdf(?:$|\?)/i.test(filing.source_url) ? '' : ' (PDF)'}`
}

export function eventSources(event: FilingEvent) {
  const score = (filing: Filing) => {
    const detail = presentation(filing)
    return (
      (detail.actual_results && detail.category === 'results' ? 10 : 0) +
      (detail.source?.method === 'native_pdf_text' ? 1 : 0)
    )
  }
  return [...event.filings].sort(
    (a, b) => score(b) - score(a) || Date.parse(b.published_at) - Date.parse(a.published_at),
  )
}

export function eventTone(event: FilingEvent) {
  if (event.category === 'unclassified')
    return { key: 'uncertain', label: 'Classification pending' }
  if (event.priority === 0) return { key: 'routine', label: 'Routine' }
  if (event.priority >= 3) return { key: 'material', label: 'Material' }
  return { key: 'update', label: 'Update' }
}

export function primaryAction(event: FilingEvent) {
  if (event.actualResults)
    return {
      label: 'Compare financials',
      href: `/?view=research&symbol=${encodeURIComponent(event.symbol)}&analysis=results`,
    }
  if (event.priority > 0 && !['meeting_notice', 'investor_meeting'].includes(event.category))
    return {
      label: 'Investigate',
      href: `/?view=research&symbol=${encodeURIComponent(event.symbol)}`,
    }
  return null
}
