import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createCompanySearch } from '../src/company-search.ts'
const directory = JSON.parse(
  readFileSync(new URL('../public/company-directory.json', import.meta.url)),
)
const search = createCompanySearch(directory.companies)
test('directory is a dated official equity capture with unique canonical symbols', () => {
  assert.ok(directory.companies.length > 2500)
  assert.equal(
    new Set(directory.companies.map((row) => row.symbol)).size,
    directory.companies.length,
  )
  assert.equal(directory.sources.length, 3)
  assert.ok(directory.sources.every((url) => url.startsWith('https://archives.nseindia.com/')))
  assert.ok(Number.isFinite(Date.parse(directory.checked_at)))
})
test('Jindal names and the natural JINDALSTEEL spelling resolve to canonical suggestions', () => {
  for (const query of ['Jindal Steel', 'JINDALSTEEL', 'Jindal Steel Limited', 'jindl steel'])
    assert.equal(search(query)[0].symbol, 'JINDALSTEL')
  const matches = search('Jindal')
  assert.ok(matches.length > 3)
  assert.ok(matches.some((row) => row.symbol === 'JINDALSTEL'))
  assert.ok(matches.some((row) => row.symbol === 'JINDALSAW'))
})
test('exact symbols and names outrank fuzzy suggestions', () => {
  assert.deepEqual(
    search('INFY').map((row) => row.symbol),
    ['INFY'],
  )
  assert.equal(search('Infosys')[0].symbol, 'INFY')
  assert.equal(search('infsys')[0].symbol, 'INFY')
  assert.equal(search('INFY.NS')[0].symbol, 'INFY')
})
test('acronyms, ampersands and official historical identities are searchable', () => {
  for (const [q, symbol] of [
    ['JSPL', 'JINDALSTEL'],
    ['HUL', 'HINDUNILVR'],
    ['L&T', 'LT'],
    ['M&M', 'M&M'],
    ['M and M', 'M&M'],
    ['SAWPIPES', 'JINDALSAW'],
  ])
    assert.equal(search(q)[0]?.symbol, symbol, q)
  assert.equal(search('HDFC').filter((row) => row.symbol.startsWith('HDFC')).length, 3)
})
test('unknown and empty inputs never manufacture a listing', () => {
  assert.deepEqual(search(''), [])
  assert.deepEqual(search('companythatdoesnotexist12345'), [])
  assert.ok(search('Jindal', 3).length <= 3)
})
