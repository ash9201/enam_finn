import { test } from 'node:test'
import assert from 'node:assert/strict'
import { groupEvents, eventTone } from '../src/briefing-model.ts'
import {
  emptyReviews,
  eventReceipt,
  migrateReviews,
  orderEvents,
  reviewState,
  selectEvents,
} from '../src/event-reviews.ts'
const source = (id, changes = {}) => ({
  id,
  symbol: 'TEST',
  company_name: 'Test Limited',
  title: 'Financial results',
  description: 'Approved results for September.',
  source_url: `https://nsearchives.nseindia.com/${id}.pdf`,
  published_at: '2026-10-31T10:00:00Z',
  category: 'results',
  priority: 3,
  review_reason: '',
  enrichment: {
    version: 'official-filing-narrative-v1',
    headline: 'Quarterly results',
    summary: 'Approved results for September.',
    event_key: 'results:2026-09-30',
    event_kind: 'results',
    category: 'results',
    priority: 3,
    actual_results: true,
    evidence: [],
  },
  ...changes,
})
const filters = {
  company: '',
  category: '',
  review: 'all',
  window: '7d',
  start: '',
  end: '',
  significance: '',
}
const now = Date.parse('2026-11-02T00:00:00Z')
test('three sources form one review item, and partial legacy reads migrate as updated', () => {
  const events = groupEvents([source('a'), source('b'), source('c')])
  assert.equal(events.length, 1)
  assert.equal(reviewState(events[0], migrateReviews(events, ['a'])), 'updated')
  assert.equal(reviewState(events[0], migrateReviews(events, ['a', 'b', 'c'])), 'reviewed')
  assert.equal(
    selectEvents(events, { ...filters, review: 'unreviewed' }, emptyReviews(), now).length,
    1,
  )
})
test('new sources and meaningful revisions require review; rescans do not', () => {
  const a = source('a'),
    event = groupEvents([a])[0],
    reviews = { version: 2, receipts: { [event.key]: eventReceipt(event) } }
  assert.equal(
    reviewState(
      groupEvents([
        { ...a, enrichment: { ...a.enrichment, checked_at: '2026-11-02', priority: 2 } },
      ])[0],
      reviews,
    ),
    'reviewed',
  )
  assert.equal(reviewState(groupEvents([a, source('b')])[0], reviews), 'updated')
  assert.equal(
    reviewState(
      groupEvents([a, { ...a, id: 'duplicate', published_at: '2026-11-01T00:00:00Z' }])[0],
      reviews,
    ),
    'reviewed',
  )
  assert.equal(
    reviewState(
      groupEvents([{ ...a, description: 'Revised profit figure disclosed.' }])[0],
      reviews,
    ),
    'updated',
  )
  assert.equal(
    reviewState(event, { version: 2, receipts: { [event.key]: eventReceipt(event) } }),
    'reviewed',
  )
})
test('review/date/category/significance filters apply to whole events with every source intact', () => {
  const rows = [source('a'), source('b', { published_at: '2026-10-20T00:00:00Z' })],
    event = groupEvents(rows)[0]
  const reviews = { version: 2, receipts: { [event.key]: eventReceipt(event) } }
  const selected = selectEvents(
    [event],
    {
      ...filters,
      company: 'TEST',
      category: 'results',
      significance: 'significant',
      review: 'reviewed',
    },
    reviews,
    now,
  )
  assert.equal(selected.length, 1)
  assert.equal(selected[0].filings.length, 2)
  assert.equal(
    selectEvents([event], { ...filters, significance: 'routine' }, reviews, now).length,
    0,
  )
  assert.equal(selectEvents([event], { ...filters, review: 'unreviewed' }, reviews, now).length, 0)
  const updated = groupEvents([...rows, source('c')])[0]
  assert.equal(selectEvents([updated], { ...filters, review: 'updated' }, reviews, now).length, 1)
  assert.equal(
    selectEvents([updated], { ...filters, review: 'unreviewed' }, reviews, now).length,
    1,
  )
})
test('event order uses publication time and stable keys, independent of review state', () => {
  const events = groupEvents([
    source('a', { enrichment: null, priority: 1 }),
    source('b', { enrichment: null, priority: 3 }),
    source('c', { published_at: '2026-10-30T00:00:00Z', enrichment: null }),
  ])
  assert.deepEqual(
    orderEvents(events).map((e) => e.key),
    ['TEST:a', 'TEST:b', 'TEST:c'],
  )
  assert.deepEqual(
    orderEvents(events, 'asc').map((e) => e.key),
    ['TEST:c', 'TEST:a', 'TEST:b'],
  )
  const reviews = { version: 2, receipts: { [events[0].key]: eventReceipt(events[0]) } }
  assert.deepEqual(
    orderEvents(selectEvents(events, filters, reviews, now)).map((e) => e.key),
    orderEvents(events).map((e) => e.key),
  )
})
test('equal-time source order and mixed time zones produce a deterministic latest event', () => {
  const a = source('a', { published_at: '2026-10-31T14:00:00+05:30' }),
    b = source('b', { published_at: '2026-10-31T10:00:00Z' })
  assert.equal(groupEvents([a, b])[0].newest, b.published_at)
  const one = source('a'),
    two = source('b')
  assert.deepEqual(groupEvents([one, two])[0], groupEvents([two, one])[0])
})
test('a verified dividend and results in one filing stay independent events with one original identity', () => {
  const a = source('a'),
    dividend = { record_date: '2026-11-06', type: 'interim', event_key: 'dividend:2026-11-06' }
  const events = groupEvents([
    { ...a, enrichment: { ...a.enrichment, dividend_reference: dividend } },
  ])
  assert.equal(events.length, 2)
  assert.equal(new Set(events.map((e) => e.category)).size, 2)
  assert.ok(
    events.every((e) => e.filings[0].id === 'a' && e.filings[0].source_url === a.source_url),
  )
  const reviews = { version: 2, receipts: { [events[0].key]: eventReceipt(events[0]) } }
  assert.equal(reviewState(events[0], reviews), 'reviewed')
  assert.equal(reviewState(events[1], reviews), 'unreviewed')
  assert.equal(
    groupEvents([
      source('other', { description: 'Board outcome mentions several matters.', enrichment: null }),
    ]).length,
    1,
  )
})
test('significance is distinct from category and does not claim regulatory materiality', () => {
  assert.equal(eventTone(groupEvents([source('a')])[0]).label, 'Significant')
  assert.equal(
    eventTone(
      groupEvents([
        source('b', { category: 'management_change', priority: 1, enrichment: null }),
      ])[0],
    ).label,
    'Routine',
  )
  assert.equal(
    eventTone(
      groupEvents([source('c', { category: 'unclassified', priority: 3, enrichment: null })])[0],
    ).label,
    'Unclassified',
  )
})
