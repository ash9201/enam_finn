import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  commonSession,
  commonSourceNote,
  priceSignals,
  sortWatchRows,
  sourceLink,
  watchRows,
  companyBriefing,
} from '../src/portfolio-model.ts'
import { groupEvents } from '../src/briefing-model.ts'

const snapshot = JSON.parse(
  readFileSync(new URL('../public/recorded-snapshot.json', import.meta.url)),
).tables
const price = (change = 4, ratio = 2, error = null) => ({
  symbol: 'TEST',
  data: {
    last_session: '2026-10-30',
    close: 100,
    volume: 200,
    price_change_pct: change,
    volume_ratio: ratio,
  },
  error,
  last_success_at: null,
})
test('signal boundaries match existing alert rules, including negative moves and failed/missing data', () => {
  assert.deepEqual(priceSignals(price(), 4, 2), { price: true, volume: true })
  assert.deepEqual(priceSignals(price(-4, 1.99), 4, 2), { price: true, volume: false })
  assert.deepEqual(priceSignals(price(3.99, 2), 4, 2), { price: false, volume: true })
  for (const row of [
    undefined,
    { ...price(), data: null },
    price(null, null),
    price(NaN, Infinity),
    price(5, 3, 'fetch failed'),
  ])
    assert.deepEqual(priceSignals(row, 4, 2), { price: false, volume: false })
})
test('signed numeric sorting keeps unavailable values last in either direction and preserves input', () => {
  const companies = ['B', 'C', 'A', 'D'].map((symbol) => ({ symbol, name: symbol, sector: 'Test' }))
  const prices = [price(-3), price(12), price(0), price(null)].map((p, i) => ({
    ...p,
    symbol: companies[i].symbol,
  }))
  const rows = watchRows(companies, prices, [], 4, 2)
  assert.deepEqual(
    sortWatchRows(rows, 'change', 'desc').map((r) => r.company.symbol),
    ['C', 'A', 'B', 'D'],
  )
  assert.deepEqual(
    sortWatchRows(rows, 'change', 'asc').map((r) => r.company.symbol),
    ['B', 'A', 'C', 'D'],
  )
  assert.deepEqual(
    sortWatchRows(rows, 'name', 'asc').map((r) => r.company.symbol),
    ['A', 'B', 'C', 'D'],
  )
  assert.deepEqual(
    rows.map((r) => r.company.symbol),
    ['B', 'C', 'A', 'D'],
  )
})
test('real recorded filing counts reuse Briefing grouping; routine, future and old records are excluded', () => {
  const companies = snapshot.finn_companies.filter((c) => c.portfolio),
    prices = snapshot.finn_price_snapshots,
    filings = snapshot.finn_filings
  assert.equal(companies.length, 15)
  const now = Date.parse('2026-11-02T12:00:00+05:30')
  const expected = groupEvents(
    filings.filter(
      (f) => Date.parse(f.published_at) >= now - 7 * 86400000 && Date.parse(f.published_at) <= now,
    ),
  ).filter((e) => e.priority > 0)
  const invalid = [
    { ...filings[0], id: 'future-test', published_at: '2099-01-01' },
    { ...filings[0], id: 'old-test', published_at: '2000-01-01' },
  ]
  const rows = watchRows(companies, prices, [...filings, ...invalid], 4, 2, now)
  for (const row of rows)
    assert.equal(row.events, expected.filter((e) => e.symbol === row.company.symbol).length)
  const sorted = sortWatchRows(rows, 'activity', 'desc')
  for (let i = 1; i < sorted.length; i++) {
    const count = (r) => Number(r.signals.price) + Number(r.signals.volume)
    assert.ok(count(sorted[i - 1]) >= count(sorted[i]))
    if (count(sorted[i - 1]) === count(sorted[i]))
      assert.ok(sorted[i - 1].events >= sorted[i].events)
  }
})
test('activity uses signal count before events, with company-name tie break', () => {
  const row = (name, signals, events) => ({ company: { name, symbol: name }, signals, events })
  const rows = [
    row('C', { price: false, volume: false }, 12),
    row('B', { price: true, volume: true }, 0),
    row('A', { price: true, volume: false }, 5),
    row('D', { price: true, volume: false }, 5),
  ]
  assert.deepEqual(
    sortWatchRows(rows, 'activity', 'desc').map((r) => r.company.name),
    ['B', 'A', 'D', 'C'],
  )
})
test('common session validates dates and preserves saved-data dates without guessing trading calendars', () => {
  const withDate = (value) => ({ ...price(), data: { ...price().data, last_session: value } })
  assert.equal(
    commonSession([
      withDate('2026-10-29'),
      withDate('2026-10-30'),
      withDate('2026-02-30'),
      withDate('invalid'),
    ]),
    '2026-10-30',
  )
  assert.equal(commonSession([price(4, 2, 'refresh failed')]), '2026-10-30')
  assert.equal(commonSession([]), null)
  assert.equal(
    commonSourceNote(snapshot.finn_price_snapshots),
    'Latest close/volume: NSE daily file. Prior 20 sessions: Yahoo Finance.',
  )
})
test('original source URLs and encoded company identities are preserved; unsafe links excluded', () => {
  for (const p of snapshot.finn_price_snapshots) assert.equal(sourceLink(p).href, p.data.source_url)
  for (const url of [
    'javascript:alert(1)',
    'http://example.com',
    'https://user:secret@example.com',
  ])
    assert.equal(sourceLink({ ...price(), data: { ...price().data, source_url: url } }), null)
  assert.equal(
    new URL(companyBriefing('M&M'), 'https://finn.example').searchParams.get('company'),
    'M&M',
  )
})
