// Freeze real anonymous saved data for this run; no ingestion, research or model calls.
import { chromium, expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { commonSession, sortWatchRows, watchRows } from '../src/portfolio-model.ts'
const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const out = fileURLToPath(new URL('../../artifacts/portfolio-redesign/', import.meta.url))
await mkdir(out, { recursive: true })
const browser = await chromium.launch(),
  cache = new Map(),
  checks = []
const data = (table) =>
  JSON.parse(
    [...cache].find(([url]) => new URL(url).pathname.endsWith('/' + table))[1].body.toString(),
  )
const money = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
const percent = (value) => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
async function audit(root) {
  const result = await root.evaluate((element) => {
    const rgb = (value) => value.match(/[\d.]+/g)?.map(Number) || [0, 0, 0, 0]
    const background = (element) => {
      for (let node = element; node; node = node.parentElement) {
        const v = rgb(getComputedStyle(node).backgroundColor)
        if (v[3] === undefined || v[3] >= 0.99) return v
      }
      return [255, 255, 255]
    }
    const lum = (c) =>
      c
        .slice(0, 3)
        .map((x) => x / 255)
        .map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4))
        .reduce((a, c, i) => a + c * [0.2126, 0.7152, 0.0722][i], 0)
    const bad = []
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT)
    while (walker.nextNode()) {
      const n = walker.currentNode,
        e = n.parentElement
      if (
        !n.textContent.trim() ||
        e.closest('.sr-only') ||
        !e.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) ||
        e.closest('option')
      )
        continue
      const s = getComputedStyle(e),
        [a, b] = [lum(rgb(s.color)), lum(background(e))].sort((a, b) => b - a)
      const large =
        parseFloat(s.fontSize) >= 24 ||
        (parseFloat(s.fontSize) >= 18.66 && Number(s.fontWeight) >= 700)
      if ((a + 0.05) / (b + 0.05) < (large ? 3 : 4.5))
        bad.push({ text: n.textContent.slice(0, 50), ratio: (a + 0.05) / (b + 0.05) })
    }
    return bad
  })
  expect(result).toEqual([])
}
let lastPage
try {
  for (const [theme, width] of [
    ['light', 1440],
    ['dark', 390],
    ['dark', 1440],
    ['light', 390],
  ]) {
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
      colorScheme: theme,
      reducedMotion: 'reduce',
    })
    const page = await context.newPage(),
      errors = []
    lastPage = page
    page.on('pageerror', (error) => errors.push(error.message))
    await page.route('**/rest/v1/**', async (route) => {
      const request = route.request()
      if (request.method() !== 'GET') throw new Error('Portfolio checks must remain read-only')
      if (!cache.has(request.url())) {
        const response = await fetch(request.url(), { headers: request.headers() }),
          headers = Object.fromEntries(response.headers)
        expect(response.status).toBe(200)
        delete headers['content-encoding']
        delete headers['content-length']
        cache.set(request.url(), {
          status: response.status,
          body: Buffer.from(await response.arrayBuffer()),
          headers,
        })
      }
      return route.fulfill(cache.get(request.url()))
    })
    await page.route('**/research', (route) => {
      if (route.request().method() === 'POST')
        throw new Error('No research generations in Portfolio checks')
      return route.continue()
    })
    await page.goto(`${base}/?view=portfolio`)
    const root = page.locator('[data-view="portfolio"]'),
      rows = root.locator('.portfolio-row')
    await expect(rows).toHaveCount(15, { timeout: 25000 })
    await expect(page.locator('.recorded-notice')).toHaveCount(0)
    const companies = data('finn_companies'),
      prices = data('finn_price_snapshots'),
      filings = data('finn_filings')
    await expect(root.locator('.portfolio-session time')).toHaveAttribute(
      'datetime',
      commonSession(prices),
    )
    await expect(root.locator('.portfolio-session')).toContainText('Not live')
    await expect(root.locator('.portfolio-method')).not.toHaveAttribute('open', '')
    const expected = watchRows(companies, prices, filings, 4, 2)
    const identities = () => rows.evaluateAll((nodes) => nodes.map((n) => n.dataset.symbol))
    expect(await identities()).toEqual(
      sortWatchRows(expected, 'recent', 'desc', true).map((r) => r.company.symbol),
    )
    for (const company of companies) {
      const row = root.locator(`.portfolio-row[data-symbol="${company.symbol}"]`),
        price = prices.find((p) => p.symbol === company.symbol),
        e = expected.find((r) => r.company.symbol === company.symbol)
      await expect(row.locator('strong')).toHaveText(company.name)
      if (price?.data) {
        await expect(row.locator('.portfolio-close')).toContainText(money(price.data.close))
        if (price.data.price_change_pct !== null)
          await expect(row.locator('.portfolio-change')).toContainText(
            percent(price.data.price_change_pct),
          )
        if (price.data.source_url)
          await expect(row.locator('.portfolio-source')).toHaveAttribute(
            'href',
            price.data.source_url,
          )
      }
      await expect(row.locator('.portfolio-signal')).toHaveCount(
        Number(e.signals.price) + Number(e.signals.volume),
      )
      if (e.events)
        await expect(row.locator('.portfolio-event-link')).toContainText(
          `${e.events} ${e.events === 1 ? 'event' : 'events'}`,
        )
      await expect(row.locator('.portfolio-research')).toHaveAttribute(
        'href',
        `/?view=research&symbol=${encodeURIComponent(company.symbol)}`,
      )
      expect(await row.innerText()).not.toContain('Prior 20 sessions: Yahoo Finance.')
    }
    const select = root.getByRole('combobox', { name: 'Sort watchlist' })
    await root.getByRole('checkbox', { name: 'Prioritize unusual activity' }).uncheck()
    for (const direction of ['desc', 'asc']) {
      if (width > 850) await root.getByRole('button', { name: 'Sort by 1d change' }).click()
      else await select.selectOption(`change:${direction}`)
      expect(await identities()).toEqual(
        sortWatchRows(expected, 'change', direction).map((r) => r.company.symbol),
      )
    }
    if (width > 850) await root.getByRole('button', { name: 'Sort by company name' }).click()
    else await select.selectOption('name:asc')
    expect(await identities()).toEqual(
      sortWatchRows(expected, 'name', 'asc').map((r) => r.company.symbol),
    )
    const infy = root.locator('.portfolio-row[data-symbol="INFY"]'),
      toggle = infy.locator('.portfolio-company-toggle')
    await toggle.focus()
    await page.keyboard.press('Enter')
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
    const details = root.getByRole('region', { name: 'Infosys Limited details' })
    await expect(details).toContainText(
      prices.find((p) => p.symbol === 'INFY').data.volume.toLocaleString('en-IN'),
    )
    await root.locator('.portfolio-method summary').click()
    await expect(root.locator('.portfolio-method')).toContainText(
      'Prior 20 sessions: Yahoo Finance.',
    )
    await root.locator('.portfolio-method summary').click()
    // Same real dataset, investor thresholds changed through the existing controls.
    await root.getByRole('button', { name: 'Alert thresholds', exact: true }).click()
    await root.getByRole('slider', { name: 'Daily price move threshold' }).fill('1')
    await root.getByRole('slider', { name: 'Volume threshold' }).fill('1')
    for (const e of watchRows(companies, prices, filings, 1, 1))
      await expect(
        root.locator(`.portfolio-row[data-symbol="${e.company.symbol}"] .portfolio-signal`),
      ).toHaveCount(Number(e.signals.price) + Number(e.signals.volume))
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem('finn-alerts-v1')))).toEqual({
      price: 1,
      volume: 1,
    })
    await root.getByRole('checkbox', { name: 'Prioritize unusual activity' }).check()
    expect(await identities()).toEqual(
      sortWatchRows(watchRows(companies, prices, filings, 1, 1), 'name', 'asc', true).map(
        (row) => row.company.symbol,
      ),
    )
    await root.getByRole('checkbox', { name: 'Prioritize unusual activity' }).uncheck()
    await root.getByRole('button', { name: 'Alert thresholds', exact: true }).click()
    const eventRow = expected.find((r) => r.events > 0),
      eventLink = root.locator(
        `.portfolio-row[data-symbol="${eventRow.company.symbol}"] .portfolio-event-link`,
      )
    await eventLink.click()
    const briefing = page.locator('[data-view="briefing"]')
    await expect(briefing.getByRole('combobox', { name: 'Company', exact: true })).toHaveValue(
      eventRow.company.symbol,
    )
    await expect(
      briefing.locator(`.company-group[data-symbol="${eventRow.company.symbol}"]`),
    ).toHaveAttribute('open', '')
    await expect(briefing.getByRole('button', { name: '7 days', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await briefing.getByRole('combobox', { name: 'Company', exact: true }).selectOption('NTPC')
    await page.locator('a[data-section="portfolio"]:visible').click()
    await expect(select).toHaveValue('name:asc')
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
    // Repeating the same explicit company link must override retained manual filters.
    await eventLink.click()
    await expect(briefing.getByRole('combobox', { name: 'Company', exact: true })).toHaveValue(
      eventRow.company.symbol,
    )
    await page.locator('a[data-section="portfolio"]:visible').click()
    await infy.locator('.portfolio-research').click()
    await expect(
      page.locator('[data-view="research"] [aria-label="Selected company"]'),
    ).toContainText('INFY', { timeout: 20000 })
    await page.locator('a[data-section="portfolio"]:visible').click()
    await expect(select).toHaveValue('name:asc')
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await root.getByRole('button', { name: 'Alert thresholds', exact: true }).click()
    await expect(root.getByRole('slider', { name: 'Daily price move threshold' })).toHaveValue('1')
    await root.getByRole('button', { name: 'Alert thresholds', exact: true }).click()
    await toggle.click()
    const overflow = await root.evaluate((node) =>
      [node, ...node.querySelectorAll('*')]
        .filter(
          (n) =>
            n.checkVisibility?.() &&
            !n.closest('.sr-only') &&
            !(innerWidth <= 850 && n.closest('thead')),
        )
        .some(
          (n) =>
            n.getBoundingClientRect().right > innerWidth + 1 &&
            getComputedStyle(n).position !== 'absolute',
        ),
    )
    expect(overflow).toBe(false)
    await audit(root.locator('.portfolio-workspace'))
    expect(errors).toEqual([])
    await root.locator('.portfolio-overview').scrollIntoViewIfNeeded()
    await page.screenshot({ path: `${out}/${theme}-${width}.png` })
    if (width === 390) {
      await page.setViewportSize({ width: 320, height: 844 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(
        false,
      )
    }
    checks.push({
      theme,
      width,
      companies: 15,
      source: 'live Supabase GETs frozen per run',
      values_sources_sort_expansion_links_preferences: true,
      page_errors: errors,
    })
    await context.close()
  }
  // Explicit browser-only failure replay: retain a real saved INFY close and remove
  // RELIANCE's data. Never publish these injected errors or alter source prices.
  for (const [theme, width] of [
    ['light', 1440],
    ['dark', 390],
  ]) {
    const context = await browser.newContext({
      viewport: { width, height: 900 },
      colorScheme: theme,
    })
    const page = await context.newPage()
    lastPage = page
    await page.route('**/rest/v1/**', async (route) => {
      const response = cache.get(route.request().url())
      if (!response) return route.continue()
      if (new URL(route.request().url()).pathname.endsWith('/finn_price_snapshots')) {
        const prices = JSON.parse(response.body.toString()).map((p) =>
          p.symbol === 'INFY'
            ? { ...p, error: 'Browser-only failure replay' }
            : p.symbol === 'RELIANCE'
              ? { ...p, data: null, error: 'Browser-only missing-data replay' }
              : p,
        )
        return route.fulfill({ ...response, body: JSON.stringify(prices) })
      }
      return route.fulfill(response)
    })
    await page.goto(`${base}/?view=portfolio`)
    const root = page.locator('[data-view="portfolio"]')
    await expect(root.locator('.portfolio-row')).toHaveCount(15)
    const infy = root.locator('.portfolio-row[data-symbol="INFY"]'),
      missing = root.locator('.portfolio-row[data-symbol="RELIANCE"]')
    await expect(infy.locator('.portfolio-row-warning')).toHaveText('Refresh failed · saved close')
    await expect(infy.locator('.portfolio-close')).toContainText(
      money(data('finn_price_snapshots').find((p) => p.symbol === 'INFY').data.close),
    )
    await expect(infy.locator('.portfolio-signal')).toHaveCount(0)
    await expect(missing.locator('.portfolio-row-warning')).toHaveText('Price unavailable')
    await expect(missing.locator('.portfolio-close')).toContainText('Last close unavailable')
    await expect(missing.locator('.portfolio-source')).toHaveCount(0)
    await infy.locator('button').click()
    await expect(root.locator('.portfolio-detail-warning')).toContainText(
      'Browser-only failure replay',
    )
    await audit(root.locator('.portfolio-workspace'))
    // Preferences survive a page reload, not merely section switching.
    await root.getByRole('button', { name: 'Alert thresholds', exact: true }).click()
    await root.getByRole('slider', { name: 'Daily price move threshold' }).fill('1')
    await page.reload()
    await root.getByRole('button', { name: 'Alert thresholds', exact: true }).click()
    await expect(root.getByRole('slider', { name: 'Daily price move threshold' })).toHaveValue('1')
    checks.push({
      theme,
      width,
      scenario: 'explicit browser-only failed refresh/missing data replay',
      saved_prices_unchanged: true,
      persistence_after_reload: true,
    })
    await context.close()
  }
  await writeFile(
    `${out}/checks.json`,
    JSON.stringify({ checked_at: new Date().toISOString(), checks }, null, 2),
  )
  await writeFile(
    `${out}/saved-responses.json`,
    JSON.stringify(
      Object.fromEntries(
        [...cache].map(([url, value]) => [
          new URL(url).pathname,
          JSON.parse(value.body.toString()),
        ]),
      ),
      null,
      2,
    ),
  )
  console.log(
    'PASS: Portfolio values, source links, sorting, expansion, shared thresholds and filtered navigation; desktop/mobile in both themes.',
  )
} catch (error) {
  if (lastPage && !lastPage.isClosed()) await lastPage.screenshot({ path: `${out}/failure.png` })
  throw error
} finally {
  await browser.close()
}
