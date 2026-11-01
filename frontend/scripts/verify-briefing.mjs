// Real captured filings, frozen per run for deterministic UI checks; no model calls.
import { chromium, expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const out = fileURLToPath(new URL('../../artifacts/briefing-redesign/browser/', import.meta.url))
await mkdir(out, { recursive: true })
const browser = await chromium.launch()
const cache = new Map(),
  checks = []
let lastPage
try {
  for (const [theme, viewport] of [
    ['light', { width: 1440, height: 1000 }],
    ['dark', { width: 390, height: 844 }],
    ['dark', { width: 1440, height: 1000 }],
    ['light', { width: 390, height: 844 }],
  ]) {
    const context = await browser.newContext({
      viewport,
      colorScheme: theme,
      reducedMotion: 'reduce',
    })
    const page = await context.newPage(),
      errors = []
    lastPage = page
    page.on('pageerror', (e) => errors.push(e.message))
    await page.route('**/rest/v1/**', async (route) => {
      const request = route.request()
      if (request.method() !== 'GET') throw new Error('Briefing review must stay browser-local')
      if (!cache.has(request.url())) {
        const response = await route.fetch()
        const headers = { ...response.headers() }
        delete headers['content-encoding']
        delete headers['content-length']
        cache.set(request.url(), {
          status: response.status(),
          body: await response.body(),
          headers,
        })
      }
      return route.fulfill(cache.get(request.url()))
    })
    await page.goto(base)
    await expect(page.getByRole('heading', { name: 'Your Briefing' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'By company', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await page.getByRole('button', { name: '7 days', exact: true }).click()
    await expect(page.locator('.company-group').first()).toBeVisible({ timeout: 25000 })
    const actualFilings = JSON.parse(
      [...cache]
        .find(([url]) => new URL(url).pathname.endsWith('/finn_filings'))[1]
        .body.toString(),
    )
    const count = actualFilings.length
    expect(count).toBeGreaterThan(20)
    const symbols = await page
      .locator('.company-group')
      .evaluateAll((nodes) => nodes.map((n) => n.dataset.symbol))
    expect(new Set(symbols).size).toBe(symbols.length)
    await expect(page.locator('.filing-count')).toContainText(`${count} matching filings`)
    await expect(page.locator('.filing-count')).toContainText(`${count} unreviewed`)
    await page.screenshot({ path: `${out}/${viewport.width}-${theme}-overview.png` })

    await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('NTPC')
    const ntpc = actualFilings.filter((f) => f.symbol === 'NTPC'),
      company = page.locator('.company-group[data-symbol="NTPC"]')
    await expect(company).toHaveCount(1)
    await company.locator(':scope > summary').click()
    const results = company
      .locator('.filing-event')
      .filter({ has: page.locator('.filing-primary-action', { hasText: 'Compare financials' }) })
    await expect(results).toHaveCount(1)
    await results.locator('.event-summary').click()
    const expectedResultIds = ntpc
      .filter((f) => f.enrichment?.event_key === 'results:2026-09-30')
      .map((f) => f.id)
    const displayedIds = await results
      .locator('.filing-source')
      .evaluateAll((nodes) => nodes.map((n) => n.dataset.filingId))
    expect(displayedIds.sort()).toEqual(expectedResultIds.sort())
    expect(displayedIds.length).toBeGreaterThan(3)
    await expect(results.locator('.event-snippet')).toContainText('Standalone and Consolidated')
    for (const record of ntpc.filter((f) => expectedResultIds.includes(f.id))) {
      await expect(
        results.locator(`[data-filing-id="${record.id}"] a.original-filing`),
      ).toHaveAttribute('href', record.source_url)
    }
    const source = results.locator('.filing-source').first()
    await source.locator('.source-passages > summary').click()
    await expect(source.locator('.filing-excerpt').first()).toBeVisible()
    await results.getByRole('button', { name: 'Review all', exact: true }).click()
    await expect(results).toHaveClass(/is-reviewed/)
    await expect(company.locator('.company-counts')).toContainText(
      `${ntpc.length - expectedResultIds.length} unreviewed`,
    )
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem('finn-read-v1')).length)).toBe(
      expectedResultIds.length,
    )
    await page.getByRole('combobox', { name: 'Review status' }).selectOption('unreviewed')
    await expect(page.locator('.filing-count')).toContainText(
      `${ntpc.length - expectedResultIds.length} matching filings`,
    )
    await page.getByRole('button', { name: 'Undo last change' }).click()
    await expect(page.locator('.filing-count')).toContainText(`${ntpc.length} matching filings`)
    await page.getByRole('combobox', { name: 'Category', exact: true }).selectOption('results')
    await expect(page.locator('.filing-count')).toContainText(
      `${ntpc.filter((f) => f.enrichment?.category === 'results').length} matching filings`,
    )
    await page.getByRole('combobox', { name: 'Review status' }).selectOption('all')
    await page
      .getByRole('combobox', { name: 'Category', exact: true })
      .selectOption('management_change')
    await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('KPITTECH')
    const kpit = page.locator('.company-group[data-symbol="KPITTECH"]')
    await kpit.locator(':scope > summary').click()
    await expect(kpit.locator('.filing-event')).toHaveCount(1)
    await expect(kpit.locator('.event-title')).toContainText('scheduled term')
    await expect(kpit.locator('.event-priority')).toHaveText('Update')
    await expect(kpit.locator('.event-snippet')).toContainText('Prof. Rajiv Lal')
    expect(await kpit.locator('.event-summary').innerText()).not.toMatch(
      /09360601|concerning|execution and oversight/,
    )
    await kpit.locator('.event-summary').click()
    await kpit.locator('.filing-source').first().locator('.source-passages > summary').click()
    await expect(kpit.locator('.source-passages[open]')).toContainText(
      'completion of a scheduled term',
    )
    await page.screenshot({ path: `${out}/${viewport.width}-${theme}-leadership.png` })

    await page.getByRole('combobox', { name: 'Company', exact: true }).selectOption('')
    await page.getByRole('combobox', { name: 'Category', exact: true }).selectOption('')
    await page.getByRole('button', { name: 'Latest activity', exact: true }).click()
    const include = page.getByRole('checkbox', { name: /Include .* routine filings/ })
    if (await include.count()) await include.check()
    await expect(page.locator('.announcement-list > .filing-event')).toHaveCount(count)
    const times = await page
      .locator('.announcement-list > .filing-event .event-meta time')
      .evaluateAll((nodes) => nodes.map((n) => Date.parse(n.dateTime)))
    expect(times).toEqual([...times].sort((a, b) => b - a))
    await expect(page.locator('.activity-company').first()).toContainText(/Limited|Ltd/i)
    await page.getByRole('button', { name: 'By company', exact: true }).focus()
    await page.keyboard.press('Enter')
    await page.getByRole('combobox', { name: 'Category', exact: true }).selectOption('routine')
    await page.getByRole('button', { name: 'Expand companies', exact: true }).click()
    const routine = page.locator('.routine-section').first()
    if (await routine.count()) {
      await routine.locator(':scope > summary').focus()
      await page.keyboard.press('Space')
      await expect(routine).toHaveAttribute('open', '')
      await expect(routine.locator('.filing-primary-action')).toHaveCount(0)
    }
    await page.getByRole('button', { name: 'Alert settings', exact: true }).click()
    await expect(page.locator('.market-monitor .settings-panel')).toBeVisible()
    await page.getByRole('slider', { name: 'Daily price move threshold' }).fill('3')
    await page.getByRole('slider', { name: 'Volume threshold' }).fill('2')
    const signals = await page.locator('.signal-row').count()
    await page.getByRole('button', { name: 'Custom', exact: true }).click()
    await page.getByLabel('From (IST)').fill('2030-01-01T00:00')
    await page.getByLabel('To (IST)').fill('2030-01-02T00:00')
    await expect(page.locator('.company-group')).toHaveCount(0)
    expect(await page.locator('.signal-row').count()).toBe(signals)
    await page.getByRole('slider', { name: 'Daily price move threshold' }).fill('15')
    await page.getByRole('slider', { name: 'Volume threshold' }).fill('5')
    await expect(page.locator('.market-monitor')).toBeVisible()
    await expect(page.locator('.signal-empty')).toBeVisible()
    await page.getByLabel('From (IST)').fill('2030-01-03T00:00')
    await expect(page.getByRole('alert')).toContainText('end time after the start')
    await page.getByRole('button', { name: 'Reset filters', exact: true }).click()
    const scroller = page.locator('.app-view:not([hidden])')
    for (const at of [0, 0.5, 1]) {
      await scroller.evaluate(
        (el, n) => (el.scrollTop = n * (el.scrollHeight - el.clientHeight)),
        at,
      )
      const area = await scroller.boundingBox(),
        nav = await page.getByRole('navigation', { name: 'Main navigation' }).boundingBox()
      if (viewport.width < 768) expect(area.y + area.height).toBeLessThanOrEqual(nav.y)
    }
    if (viewport.width === 390) {
      await page.setViewportSize({ width: 320, height: 740 })
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    expect(errors).toEqual([])
    checks.push({
      viewport,
      theme,
      real_filings: count,
      companies_unique: true,
      related_sources_retained: true,
      kpit_tenure: true,
      filters_review_undo: true,
      chronological_activity: true,
      eod_independent: true,
      keyboard: true,
      no_overflow: true,
    })
    console.log(`PASS: ${viewport.width}px ${theme} Briefing`)
    await page.unrouteAll({ behavior: 'ignoreErrors' })
    await context.close()
  }
} catch (error) {
  if (lastPage && !lastPage.isClosed()) {
    await lastPage.screenshot({ path: `${out}/failure.png` })
    await writeFile(`${out}/failure.html`, await lastPage.content())
  }
  throw error
} finally {
  for (const context of browser.contexts())
    for (const page of context.pages()) await page.unrouteAll({ behavior: 'ignoreErrors' })
  await browser.close()
  await writeFile(`${out}/checks.json`, JSON.stringify(checks, null, 2))
}
console.log(`PASS: ${checks.length} Briefing viewport/theme scenes; no model generation.`)
