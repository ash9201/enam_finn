// Real captured sources frozen per run; event review and sort checks make no model calls.
import { chromium, expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { groupEvents } from '../src/briefing-model.ts'
const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const out = fileURLToPath(new URL('../../artifacts/briefing-redesign/browser/', import.meta.url))
await mkdir(out, { recursive: true })
const browser = await chromium.launch(),
  cache = new Map(),
  checks = []
const data = (table) =>
  JSON.parse(
    [...cache].find(([url]) => new URL(url).pathname.endsWith('/' + table))[1].body.toString(),
  )
let lastPage
async function captured(route) {
  const request = route.request()
  if (request.method() !== 'GET') throw new Error('Review must stay browser-local')
  if (!cache.has(request.url())) {
    const response = await fetch(request.url(), { headers: request.headers() }),
      headers = Object.fromEntries(response.headers)
    expect(response.status).toBe(200)
    delete headers['content-encoding']
    delete headers['content-length']
    cache.set(request.url(), {
      status: response.status,
      headers,
      body: Buffer.from(await response.arrayBuffer()),
    })
  }
  return cache.get(request.url())
}
async function openResults(page) {
  await page.getByRole('button', { name: '7 days', exact: true }).click()
  await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('NTPC')
  const company = page.locator('.company-group[data-symbol="NTPC"]')
  if ((await company.getAttribute('open')) === null)
    await company.locator(':scope > summary').click()
  const event = company
    .locator('.filing-event')
    .filter({ has: page.locator('.filing-primary-action[href*="analysis=results"]') })
  if ((await event.locator('.event-details').getAttribute('open')) === null)
    await event.locator('.event-summary').click()
  return { company, event }
}
try {
  for (const [theme, width] of [
    ['light', 1440],
    ['dark', 390],
    ['dark', 1440],
    ['light', 390],
  ]) {
    const page = await browser.newPage({
        viewport: { width, height: 950 },
        colorScheme: theme,
        reducedMotion: 'reduce',
      }),
      errors = []
    lastPage = page
    page.on('pageerror', (e) => errors.push(e.message))
    await page.route('**/rest/v1/**', async (route) => route.fulfill(await captured(route)))
    await page.goto(base)
    await page.getByRole('button', { name: '7 days', exact: true }).click()
    await expect(page.locator('.company-group').first()).toBeVisible({ timeout: 25000 })
    await expect(
      page.getByRole('button', { name: 'Grouped by company', exact: true }),
    ).toHaveAttribute('aria-pressed', 'true')
    await expect(page.locator('.filing-count')).toHaveCount(0)
    const allSources = data('finn_filings'),
      ntpc = groupEvents(allSources.filter((f) => f.symbol === 'NTPC'))
    const companyOrder = await page
      .locator('.company-group')
      .evaluateAll((nodes) => nodes.map((n) => n.dataset.symbol))
    const company = page.locator('.company-group[data-symbol="NTPC"]')
    await company.locator(':scope > summary').click()
    await expect(company.locator('.company-counts')).toContainText(`${ntpc.length} events`)
    expect(await company.locator(':scope > summary').innerText()).not.toMatch(/filings|sources/)
    const event = company
      .locator('.filing-event')
      .filter({ has: page.locator('.filing-primary-action[href*="analysis=results"]') })
    const eventOrder = await company
      .locator('.filing-event')
      .evaluateAll((nodes) => nodes.map((n) => n.dataset.eventKey))
    await event.locator('.event-summary').click()
    await expect(event.locator('.event-priority')).toHaveText('Significant')
    await expect(event.locator('.review-state')).toHaveText('Unreviewed')
    const expected = ntpc.find((e) => e.actualResults)
    expect(
      await event
        .locator('.original-filing')
        .evaluateAll((nodes) => nodes.map((n) => n.getAttribute('href')).sort()),
    ).toEqual(expected.filings.map((f) => f.source_url).sort())
    expect(await event.locator('.event-summary').innerText()).not.toMatch(/\d+ sources/)
    await event.getByRole('button', { name: 'Mark reviewed', exact: true }).click()
    await expect(event.locator('.review-state')).toContainText('Reviewed')
    await expect(page.locator('.review-feedback')).toContainText('1 event')
    const ledger = await page.evaluate(() =>
      JSON.parse(localStorage.getItem('finn-event-reviews-v2')),
    )
    expect(Object.keys(ledger.receipts[expected.key].sources).sort()).toEqual(
      expected.filings.map((f) => f.id).sort(),
    )
    expect(
      await page
        .locator('.company-group')
        .evaluateAll((nodes) => nodes.map((n) => n.dataset.symbol)),
    ).toEqual(companyOrder)
    expect(
      await company
        .locator('.filing-event')
        .evaluateAll((nodes) => nodes.map((n) => n.dataset.eventKey)),
    ).toEqual(eventOrder)
    await expect(company.locator('.company-counts')).toContainText(`${ntpc.length - 1} unreviewed`)
    await page.getByRole('button', { name: 'Undo last change' }).click()
    await expect(event.locator('.review-state')).toHaveText('Unreviewed')
    await event.getByRole('button', { name: 'Mark reviewed', exact: true }).click()
    await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('NTPC')
    await page.getByRole('combobox', { name: 'Category', exact: true }).selectOption('results')
    await page.getByRole('combobox', { name: 'Review status' }).selectOption('reviewed')
    await page
      .getByRole('combobox', { name: 'Significance', exact: true })
      .selectOption('significant')
    await expect(page.locator('.filing-event')).toHaveCount(1)
    await expect(event.locator('.original-filing')).toHaveCount(expected.filings.length)
    await page.getByRole('button', { name: 'Custom', exact: true }).click()
    await page.getByLabel('From (IST)').fill('2026-10-31T00:00')
    await page.getByLabel('To (IST)').fill('2026-10-31T23:59')
    await expect(page.locator('.filing-event')).toHaveCount(1)
    await page.getByRole('combobox', { name: 'Significance', exact: true }).selectOption('routine')
    await expect(page.getByRole('heading', { name: 'No events match this view' })).toBeVisible()
    await page.getByRole('button', { name: 'Reset filters', exact: true }).click()
    await page.getByRole('button', { name: '7 days', exact: true }).click()
    await page.getByRole('combobox', { name: 'Company order' }).selectOption('name')
    const names = await page.locator('.company-group .company-name').allTextContents()
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b, 'en-IN')))
    await page.getByRole('combobox', { name: 'Company order' }).selectOption('count')
    const counts = await page.locator('.company-group .company-counts > span').allTextContents()
    expect(counts.map((n) => parseInt(n))).toEqual(
      counts.map((n) => parseInt(n)).sort((a, b) => b - a),
    )
    await page.getByRole('button', { name: 'Chronological', exact: true }).click()
    const include = page.getByRole('checkbox', { name: /Include.*routine events/ })
    if (await include.count()) await include.check()
    for (const direction of ['asc', 'desc']) {
      await page.getByRole('combobox', { name: 'Event order' }).selectOption(direction)
      const times = await page
        .locator('.filing-event')
        .evaluateAll((nodes) => nodes.map((n) => Date.parse(n.dataset.publishedAt)))
      expect(times).toEqual([...times].sort((a, b) => (direction === 'asc' ? a - b : b - a)))
    }
    await page.getByRole('button', { name: 'Grouped by company', exact: true }).click()
    await page.getByRole('button', { name: 'Alert thresholds', exact: true }).click()
    await page.getByRole('slider', { name: 'Daily price move threshold' }).fill('15')
    await page.getByRole('slider', { name: 'Volume threshold' }).fill('5')
    await page.getByRole('button', { name: 'Custom', exact: true }).click()
    await page.getByLabel('From (IST)').fill('2030-01-01T00:00')
    await page.getByLabel('To (IST)').fill('2030-01-02T00:00')
    await expect(page.getByRole('heading', { name: 'No events match this view' })).toBeVisible()
    await expect(page.locator('.market-monitor')).toBeVisible()
    await expect(page.getByRole('slider', { name: 'Daily price move threshold' })).toHaveValue('15')
    await page.getByRole('button', { name: 'Reset filters', exact: true }).click()
    await page.getByRole('button', { name: 'Alert thresholds', exact: true }).click()
    await openResults(page)
    if ((width === 1440 && theme === 'light') || (width === 390 && theme === 'dark')) {
      await event.scrollIntoViewIfNeeded()
      await page.screenshot({ path: `${out}/${width}-${theme}-event-review.png` })
    }
    if (width === 390) await page.setViewportSize({ width: 320, height: 844 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    expect(errors).toEqual([])
    checks.push({
      width,
      theme,
      event_counts: true,
      whole_sources: true,
      stable_review_order: true,
      combined_filters: true,
      significance: true,
      chronology_both_directions: true,
      eod_independent: true,
      errors,
    })
    await page.close()
  }
  // Explicit transport replay of newly added/changed evidence; source facts are not published.
  const rows = data('finn_filings'),
    original = groupEvents(rows.filter((f) => f.symbol === 'NTPC')).find((e) => e.actualResults)
  const page = await browser.newPage({ viewport: { width: 390, height: 950 }, colorScheme: 'dark' })
  lastPage = page
  let mutation = 'none'
  await page.addInitScript(
    (id) => localStorage.setItem('finn-read-v1', JSON.stringify([id])),
    original.filings[0].id,
  )
  await page.route('**/rest/v1/**', async (route) => {
    const response = await captured(route)
    if (new URL(route.request().url()).pathname.endsWith('/finn_filings') && mutation !== 'none') {
      const changed = JSON.parse(response.body.toString()),
        source = changed.find((f) => f.id === original.filings[0].id)
      if (mutation === 'new')
        changed.push({
          ...source,
          id: 'ui-added-source',
          source_url: 'https://nsearchives.nseindia.com/ui-replay-source.pdf',
          description: source.description + ' UI-only additional evidence replay.',
        })
      else source.description += ' UI-only changed-source replay.'
      return route.fulfill({ ...response, body: JSON.stringify(changed) })
    }
    return route.fulfill(response)
  })
  await page.goto(base)
  let { event } = await openResults(page)
  await expect(event.locator('.review-state')).toHaveText('Updated since review')
  await event.getByRole('button', { name: 'Mark reviewed', exact: true }).click()
  await page.reload()
  ;({ event } = await openResults(page))
  await expect(event.locator('.review-state')).toContainText('Reviewed')
  mutation = 'new'
  await page.reload()
  ;({ event } = await openResults(page))
  await expect(event.locator('.review-state')).toHaveText('Updated since review')
  await expect(event.locator('.original-filing')).toHaveCount(original.filings.length + 1)
  await event.getByRole('button', { name: 'Mark reviewed', exact: true }).click()
  await page.reload()
  ;({ event } = await openResults(page))
  await expect(event.locator('.review-state')).toContainText('Reviewed')
  mutation = 'changed'
  await page.reload()
  ;({ event } = await openResults(page))
  await expect(event.locator('.review-state')).toHaveText('Updated since review')
  checks.push({
    scenario: 'legacy partial review, reload, new source and changed source replays',
    event_level_persistence: true,
    updated_since_review: true,
  })
  await page.close()
  await writeFile(`${out}/checks.json`, JSON.stringify(checks, null, 2))
  console.log(
    'PASS: four event-review/sort/filter theme/viewport scenes and legacy/new-evidence replay; no model calls.',
  )
} catch (error) {
  if (lastPage && !lastPage.isClosed()) await lastPage.screenshot({ path: `${out}/failure.png` })
  throw error
} finally {
  await browser.close()
}
