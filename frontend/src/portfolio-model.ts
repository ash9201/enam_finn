import { groupEvents, type Company, type Filing } from './briefing-model.ts'

export type Price = {
  symbol: string
  data: {
    last_session: string
    close: number
    volume: number
    price_change_pct: number | null
    volume_ratio: number | null
    volume_note?: string | null
    source_note?: string | null
    source_url?: string | null
    provider?: string
    adjustment?: string
    price_change_note?: string | null
  } | null
  error: string | null
  last_success_at: string | null
}
export type SortKey = 'name' | 'change' | 'recent' | 'events'
export type WatchRow = {
  company: Company
  price?: Price
  signals: { price: boolean; volume: boolean }
  events: number
  latestEvent: string | null
}
export const finite = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value)
export function priceSignals(
  price: Price | undefined,
  priceThreshold: number,
  volumeThreshold: number,
) {
  return {
    price:
      !price?.error &&
      finite(price?.data?.price_change_pct) &&
      Math.abs(price.data.price_change_pct) >= priceThreshold,
    volume:
      !price?.error &&
      finite(price?.data?.volume_ratio) &&
      price.data.volume_ratio >= volumeThreshold,
  }
}
export function commonSession(prices: Price[]) {
  return (
    prices
      .map((price) => price.data?.last_session)
      .filter((value): value is string => {
        if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
        const parsed = new Date(value + 'T00:00:00Z')
        return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
      })
      .sort()
      .at(-1) || null
  )
}
export function commonSourceNote(prices: Price[]) {
  const counts = new Map<string, number>()
  for (const price of prices) {
    const note = price.data?.source_note
    if (note) counts.set(note, (counts.get(note) || 0) + 1)
  }
  return [...counts].sort((a, b) => b[1] - a[1])[0]?.[0] || null
}
export function watchRows(
  companies: Company[],
  prices: Price[],
  filings: Filing[],
  priceThreshold: number,
  volumeThreshold: number,
  now = Date.now(),
): WatchRow[] {
  const recent = filings.filter((filing) => {
    const date = Date.parse(filing.published_at)
    return date >= now - 7 * 86400000 && date <= now
  })
  const events = groupEvents(recent).filter((event) => event.priority > 0)
  return companies.map((company) => {
    const price = prices.find((price) => price.symbol === company.symbol)
    const companyEvents = events.filter((event) => event.symbol === company.symbol)
    return {
      company,
      price,
      signals: priceSignals(price, priceThreshold, volumeThreshold),
      events: companyEvents.length,
      latestEvent:
        companyEvents
          .map((event) => event.newest)
          .sort((a, b) => Date.parse(a) - Date.parse(b))
          .at(-1) || null,
    }
  })
}
export function sortWatchRows(
  rows: WatchRow[],
  key: SortKey,
  direction: 'asc' | 'desc',
  prioritize = false,
) {
  const name = (a: WatchRow, b: WatchRow) =>
    a.company.name.localeCompare(b.company.name, 'en-IN') ||
    a.company.symbol.localeCompare(b.company.symbol)
  return [...rows].sort((a, b) => {
    if (prioritize) {
      const flagged = (row: WatchRow) => Number(row.signals.price || row.signals.volume)
      const group = flagged(b) - flagged(a)
      if (group) return group
    }
    let compared = 0
    if (key === 'name') compared = a.company.name.localeCompare(b.company.name, 'en-IN')
    else {
      const value = (row: WatchRow) =>
        key === 'change'
          ? row.price?.data?.price_change_pct
          : key === 'events'
            ? row.events
            : row.latestEvent
              ? Date.parse(row.latestEvent)
              : null
      const av = value(a),
        bv = value(b)
      if (!finite(av)) return !finite(bv) ? name(a, b) : 1
      if (!finite(bv)) return -1
      compared = av - bv
    }
    return (direction === 'desc' ? -compared : compared) || name(a, b)
  })
}

export function sourceLink(price?: Price) {
  const value = price?.data?.source_url
  if (!value) return null
  try {
    const url = new URL(value)
    if (url.protocol !== 'https:' || url.username || url.password) return null
    return {
      href: value,
      label: ['nsearchives.nseindia.com', 'archives.nseindia.com', 'www.nseindia.com'].includes(
        url.hostname,
      )
        ? 'NSE source'
        : 'Market source',
    }
  } catch {
    return null
  }
}
export const companyBriefing = (symbol: string) =>
  `/?view=briefing&company=${encodeURIComponent(symbol)}&window=7d`
