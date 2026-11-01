import {
  dateBounds,
  eventTone,
  presentation,
  type FilingEvent,
  type FilingFilters,
} from './briefing-model.ts'

export type EventReceipt = { reviewedAt: string; sources: Record<string, string> }
export type EventReviews = { version: 2; receipts: Record<string, EventReceipt> }
export type ReviewChanges = Record<string, EventReceipt | null>
export const emptyReviews = (): EventReviews => ({ version: 2, receipts: {} })

// Keep exact meaningful content, not fetch/check times or priority scores. A rescan
// alone must not undo a review. Identical duplicate evidence is already covered;
// new content or a changed source version needs another review.
export function eventReceipt(
  event: FilingEvent,
  reviewedAt = new Date().toISOString(),
): EventReceipt {
  return {
    reviewedAt,
    sources: Object.fromEntries(
      event.filings.map((filing) => {
        const detail = presentation(filing)
        return [
          filing.id,
          JSON.stringify([
            detail.source?.sha256 || filing.source_url,
            filing.description,
            detail.headline,
            detail.summary,
            detail.additional_details || [],
            detail.evidence.map((e) => [e.quote, e.pdf_page]),
            detail.recording_reference || null,
            detail.dividend_reference || null,
          ]),
        ]
      }),
    ),
  }
}
export function reviewState(
  event: FilingEvent,
  reviews: EventReviews,
): 'reviewed' | 'unreviewed' | 'updated' {
  const previous = reviews.receipts[event.key]
  if (!previous) return 'unreviewed'
  const current = eventReceipt(event).sources
  const seen = new Set(Object.values(previous.sources))
  return Object.entries(current).every(
    ([id, value]) => previous.sources[id] === value || seen.has(value),
  )
    ? 'reviewed'
    : 'updated'
}
export function migrateReviews(events: FilingEvent[], legacyIds: string[]): EventReviews {
  const legacy = new Set(legacyIds),
    reviews = emptyReviews()
  for (const event of events) {
    const receipt = eventReceipt(event, 'legacy')
    receipt.sources = Object.fromEntries(
      Object.entries(receipt.sources).filter(([id]) => legacy.has(id)),
    )
    if (Object.keys(receipt.sources).length) reviews.receipts[event.key] = receipt
  }
  return reviews
}
export function isEventReviews(value: unknown): value is EventReviews {
  if (!value || typeof value !== 'object') return false
  const data = value as EventReviews
  return (
    data.version === 2 &&
    !!data.receipts &&
    typeof data.receipts === 'object' &&
    !Array.isArray(data.receipts) &&
    Object.values(data.receipts).every(
      (receipt) =>
        receipt &&
        typeof receipt.reviewedAt === 'string' &&
        receipt.sources &&
        typeof receipt.sources === 'object' &&
        !Array.isArray(receipt.sources) &&
        Object.values(receipt.sources).every((source) => typeof source === 'string'),
    )
  )
}
export function selectEvents(
  events: FilingEvent[],
  filters: FilingFilters,
  reviews: EventReviews,
  now = Date.now(),
) {
  const bounds = dateBounds(filters, now)
  if (!bounds.valid) return []
  return events.filter((event) => {
    const state = reviewState(event, reviews)
    return (
      (!filters.company || event.symbol === filters.company) &&
      (!filters.category || event.category === filters.category) &&
      (!filters.significance || eventTone(event).key === filters.significance) &&
      (filters.review === 'all' ||
        (filters.review === 'updated'
          ? state === 'updated'
          : filters.review === 'reviewed'
            ? state === 'reviewed'
            : state !== 'reviewed')) &&
      event.filings.some((filing) => {
        const date = Date.parse(filing.published_at)
        return date >= bounds.from && date <= bounds.to
      })
    )
  })
}
export function orderEvents(events: FilingEvent[], direction = 'desc') {
  return [...events].sort(
    (a, b) =>
      (Date.parse(a.newest) - Date.parse(b.newest)) * (direction === 'asc' ? 1 : -1) ||
      a.key.localeCompare(b.key),
  )
}
