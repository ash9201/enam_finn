import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  dateBounds,
  groupEvents,
  makeEvent,
  presentation,
  primaryAction,
  selectFilings,
  eventTone,
  eventExplanation,
  companyPreview,
} from '../src/briefing-model.ts'

const defaults = { company: '', category: '', review: 'all', window: '7d', start: '', end: '' }
const now = Date.parse('2026-11-01T12:00:00+05:30')
const row = (id, values = {}) => ({
  id,
  symbol: 'TEST',
  company_name: 'Test Limited',
  title: 'Financial Results Updates',
  description: 'Financial Results Updates',
  source_url: `https://nsearchives.nseindia.com/${id}.pdf`,
  published_at: '2026-10-31T10:00:00+00:00',
  category: 'results',
  priority: 3,
  review_reason: 'old generic advice',
  ...values,
})
const detail = (key, values = {}) => ({
  version: 'official-filing-narrative-v1',
  headline: 'Results for September 2026',
  summary: 'The company filed its results.',
  event_key: key,
  event_kind: 'results',
  category: 'results',
  priority: 3,
  actual_results: true,
  evidence: [],
  ...values,
})

test('explicit related-period filings group, with all original identities retained', () => {
  const records = [
    row('a', { enrichment: detail('results:2026-09-30') }),
    row('b', { enrichment: detail('results:2026-09-30') }),
  ]
  const events = groupEvents(records)
  assert.equal(events.length, 1)
  assert.deepEqual(
    events[0].filings.map((f) => f.id),
    ['a', 'b'],
  )
  assert.equal(primaryAction(events[0]).label, 'Compare financials')
})
test('same company and day do not group unrelated or uncertain announcements', () => {
  const records = [row('a'), row('b', { category: 'business_update' })]
  assert.equal(groupEvents(records).length, 2)
})
test('an event reference cannot group different companies or reporting periods', () => {
  const records = [
    row('a', { enrichment: detail('results:2026-09-30') }),
    row('b', { symbol: 'OTHER', enrichment: detail('results:2026-09-30') }),
    row('c', { enrichment: detail('results:2026-06-30') }),
  ]
  assert.equal(groupEvents(records).length, 3)
})
test('leadership tenure fallback is neutral, informative, and hides DIN from summary', () => {
  const record = row('a', {
    category: 'management_change',
    description:
      'Prof. Rajiv Lal (DIN: 09360601) completed his 2nd term as an Independent Director.',
  })
  const info = presentation(record)
  assert.equal(info.priority, 1)
  assert.match(info.summary, /Rajiv Lal/)
  assert.doesNotMatch(info.summary, /09360601/)
  assert.equal(eventTone(makeEvent([record], 'a')).label, 'Routine')
})
test('generic financial headlines do not manufacture detail or enable comparisons', () => {
  const record = row('a'),
    info = presentation(record)
  assert.equal(info.summary, null)
  assert.equal(info.status, 'headline_only')
  assert.equal(primaryAction(makeEvent([record], 'a')).label, 'Investigate')
})
test('meeting notice stays separate from a verified result action', () => {
  const record = row('notice', {
    category: 'meeting_notice',
    priority: 1,
    description: 'Board meeting intimation to consider quarterly results.',
  })
  assert.equal(primaryAction(makeEvent([record], 'notice')), null)
})
test('company, category, review and dates combine at filing level', () => {
  const records = [
    row('a'),
    row('b', { symbol: 'OTHER' }),
    row('c', { category: 'routine', priority: 0 }),
    row('d', { published_at: '2025-10-31T10:00:00+00:00' }),
  ]
  const filters = { ...defaults, company: 'TEST', category: 'results', review: 'unreviewed' }
  assert.deepEqual(
    selectFilings(records, filters, new Set(), now).map((f) => f.id),
    ['a'],
  )
  assert.equal(selectFilings(records, filters, new Set(['a']), now).length, 0)
})
test('reviewed-only and all preserve distinct counts and do not alter events', () => {
  const records = [row('a'), row('b')],
    read = new Set(['a'])
  assert.equal(selectFilings(records, { ...defaults, review: 'reviewed' }, read, now).length, 1)
  assert.equal(selectFilings(records, defaults, read, now).length, 2)
})
test('latest activity is chronological instead of sorting materiality first', () => {
  const records = [
    row('material', { published_at: '2026-10-30T10:00:00+00:00' }),
    row('routine', { priority: 0, category: 'routine' }),
  ]
  assert.deepEqual(
    selectFilings(records, defaults, new Set(), now).map((f) => f.id),
    ['routine', 'material'],
  )
})
test('custom end includes the displayed minute; invalid windows are explicit', () => {
  const filters = {
    ...defaults,
    window: 'custom',
    start: '2026-10-31T15:30',
    end: '2026-10-31T15:30',
  }
  assert.equal(
    selectFilings(
      [row('a', { published_at: '2026-10-31T10:00:59+00:00' })],
      filters,
      new Set(),
      now,
    ).length,
    1,
  )
  assert.equal(dateBounds({ ...filters, start: '2026-11-01T15:30' }).valid, false)
})
test('unclassified disclosures remain visible with an explicit uncertainty label', () => {
  const event = makeEvent([row('a', { category: 'unclassified', priority: 2 })], 'a')
  assert.equal(eventTone(event).key, 'unclassified')
  assert.equal(selectFilings(event.filings, defaults, new Set(), now).length, 1)
})
test('every original filing appears once across grouped events', () => {
  const rows = Array.from({ length: 20 }, (_, i) =>
    row(`id${i}`, {
      symbol: i % 2 ? 'B' : 'A',
      enrichment: detail(i % 3 ? 'results:2026-09-30' : null),
    }),
  )
  const flattened = groupEvents(rows).flatMap((e) => e.filings)
  assert.equal(flattened.length, rows.length)
  assert.equal(new Set(flattened.map((f) => f.id)).size, rows.length)
})

test('company previews deduplicate titles without merging unrelated disclosures', () => {
  const records = [row('a'), row('b')]
  const events = groupEvents(records)
  assert.equal(events.length, 2)
  assert.equal(companyPreview(events), events[0].title)
})

test('an explanation keeps distinct numeric facts and removes repeated/supporting boilerplate', () => {
  const records = [
    row('a', { enrichment: detail('same', { summary: 'Dividend of Rs. 3 per share declared.' }) }),
    row('b', { enrichment: detail('same', { summary: 'Dividend of Rs. 3 per share declared.' }) }),
    row('c', { enrichment: detail('same', { summary: 'Record date is 6 November 2026.' }) }),
    row('d', {
      enrichment: detail('same', {
        summary: 'Supporting debt disclosure within the filed financial-results package.',
      }),
    }),
  ]
  const explanation = eventExplanation(groupEvents(records)[0])
  assert.equal((explanation.match(/Rs\. 3/g) || []).length, 1)
  assert.match(explanation, /6 November 2026/)
  assert.doesNotMatch(explanation, /Supporting debt/)
})

test('reviewed real NTPC/Reliance recording pairs retain every source; KPIT roles appear once', () => {
  const records = JSON.parse(
    readFileSync(new URL('../public/recorded-snapshot.json', import.meta.url)),
  ).tables.finn_filings
  for (const symbol of ['NTPC', 'RELIANCE']) {
    const originals = records.filter(
      (f) => f.symbol === symbol && f.enrichment?.recording_reference,
    )
    assert.equal(originals.length, 2)
    const events = groupEvents(originals)
    assert.equal(events.length, 1)
    assert.deepEqual(
      new Set(events[0].filings.map((f) => f.id)),
      new Set(originals.map((f) => f.id)),
    )
    assert.equal((eventExplanation(events[0]).match(/recording is available/g) || []).length, 1)
    assert.match(eventExplanation(events[0]), /period ended 30 Sep 2026/)
  }
  const kpit = groupEvents(records.filter((f) => f.symbol === 'KPITTECH'))[0]
  assert.equal(kpit.filings.length, 2)
  const explanation = eventExplanation(kpit)
  assert.equal((explanation.match(/completed his/g) || []).length, 1)
  assert.equal((explanation.match(/Nomination & Remuneration/g) || []).length, 1)
  assert.match(explanation, /effective at the close of business/)
})

test('real NTPC results, dividend and different debt subjects remain separate developments', () => {
  const records = JSON.parse(
    readFileSync(new URL('../public/recorded-snapshot.json', import.meta.url)),
  ).tables.finn_filings.filter((f) => f.symbol === 'NTPC')
  const events = groupEvents(records)
  assert.equal(events.length, 8)
  const results = events.filter((event) => event.actualResults)
  assert.equal(results.length, 1)
  assert.equal(results[0].filings.length, 2)
  assert.equal(results[0].category, 'results')
  const dividend = events.find((event) => event.key.includes(':dividend:'))
  assert.equal(dividend.filings.length, 3)
  const explanation = eventExplanation(dividend)
  assert.match(explanation, /Rs\. 3 per equity share/)
  assert.match(explanation, /record date is 6 Nov 2026/)
  assert.equal((explanation.match(/record date/gi) || []).length, 1)
  assert.equal(events.filter((event) => event.category === 'capital').length, 3)
  assert.ok(
    events
      .filter((event) => event.category === 'capital')
      .every((event) => event.filings.length === 1 && !event.actualResults),
  )
  assert.deepEqual(
    new Set(events.flatMap((e) => e.filings.map((f) => f.id))),
    new Set(records.map((f) => f.id)),
  )
})
