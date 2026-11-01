import { chromium, expect } from '@playwright/test'
import { readFile, mkdir, writeFile } from 'node:fs/promises'

const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const local = process.env.FINN_QA_API_URL || 'http://127.0.0.1:8003'
const fixtures = new Map()
for (const symbol of ['NTPC', 'SUNPHARMA', 'M&M'])
  fixtures.set(
    symbol,
    JSON.parse(
      await readFile(
        new URL(`../../artifacts/targeted-fixes/${symbol}-financial.json`, import.meta.url),
        'utf8',
      ),
    ),
  )
const browser = await chromium.launch()
const checks = []
let lastPage
await mkdir(new URL('../../artifacts/investor-qa-browser/', import.meta.url), { recursive: true })
try {
  for (const [symbol, theme, viewport] of [
    ['NTPC', 'light', { width: 390, height: 844 }],
    ['NTPC', 'dark', { width: 1440, height: 1000 }],
    ['SUNPHARMA', 'dark', { width: 390, height: 844 }],
    ['SUNPHARMA', 'light', { width: 1440, height: 1000 }],
  ]) {
    const ctx = await browser.newContext({ viewport, colorScheme: theme, reducedMotion: 'reduce' })
    await ctx.addInitScript((t) => localStorage.setItem('finn-theme', t), theme)
    const page = await ctx.newPage(),
      errors = []
    lastPage = page
    page.on('pageerror', (e) => errors.push(e.message))
    await page.route('**/*', async (route) => {
      const req = route.request(),
        u = new URL(req.url())
      if (
        u.pathname.endsWith('/finn_research_cache') &&
        u.searchParams.get('question')?.includes('quarterly Revenue')
      ) {
        const ticker = u.searchParams.get('symbol')?.replace(/^eq\./, ''),
          r = fixtures.get(ticker)
        if (r)
          return route.fulfill({
            json: [{ result: r }],
            headers: { 'Access-Control-Allow-Origin': '*' },
          })
      }
      if (/^\/(research|jobs)(\/|$)/.test(u.pathname)) {
        if (req.method() === 'OPTIONS')
          return route.fulfill({
            status: 204,
            headers: {
              'Access-Control-Allow-Origin': '*',
              'Access-Control-Allow-Headers': 'Content-Type',
              'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
            },
          })
        const r = await fetch(local + u.pathname + u.search, {
          method: req.method(),
          headers: { 'Content-Type': 'application/json' },
          body: req.postData() || undefined,
        })
        return route.fulfill({
          status: r.status,
          body: Buffer.from(await r.arrayBuffer()),
          headers: {
            'Content-Type': r.headers.get('content-type') || 'application/json',
            'Access-Control-Allow-Origin': '*',
          },
        })
      }
      return route.continue()
    })
    await page.goto(base + '/?view=research&analysis=results&symbol=' + symbol)
    await expect(page.locator('.financial-results')).toHaveCount(1, { timeout: 30000 })
    await page.evaluate(() => {
      window.__maxFinancial = 1
      new MutationObserver(
        () =>
          (window.__maxFinancial = Math.max(
            window.__maxFinancial,
            document.querySelectorAll('.financial-results').length,
          )),
      ).observe(document.getElementById('root'), { childList: true, subtree: true })
    })
    await page
      .locator('.research-form textarea')
      .fill('Explain these results using the company documents.')
    await expect(page.locator('.financial-results')).toHaveCount(1)
    await page
      .locator('.research-form textarea')
      .fill(
        'Compare the latest reported quarterly Revenue, EBITDA, PBT and PAT with the previous quarter and year-ago quarter.',
      )
    for (let cycle = 0; cycle < 3; cycle++) {
      await page.locator('.financial-bases button').filter({ hasText: 'Standalone' }).click()
      await expect(page.locator('.financial-results')).toHaveAttribute('data-basis', 'standalone')
      await expect(page.locator('table[aria-label="standalone quarterly figures"]')).toHaveCount(1)
      if (symbol === 'NTPC')
        await expect(page.locator('button[aria-label^="Inspect standalone PBT for"]')).toHaveCount(
          3,
        )
      await page.locator('.financial-bases button').filter({ hasText: 'Consolidated' }).click()
      await expect(page.locator('.financial-results')).toHaveAttribute('data-basis', 'consolidated')
      if (symbol === 'NTPC')
        await expect(
          page.locator('button[aria-label^="Inspect consolidated PBT for"]'),
        ).toHaveCount(0)
      await page.getByRole('button', { name: /Quarterly results/ }).click()
      await expect(page.locator('.financial-results')).toHaveCount(1)
    }
    await expect(page.locator('.financial-performance')).toBeVisible()
    if (symbol === 'SUNPHARMA') {
      await expect(page.locator('.financial-performance')).toContainText('Revenue rose')
      await expect(page.locator('.financial-performance')).toContainText('PBT fell')
      await expect(page.locator('.financial-performance')).toContainText('PAT fell')
      await expect(page.locator('.disclosed-context')).toHaveCount(2)
    }
    for (const proportion of [0, 0.5, 1]) {
      await page
        .locator('.research-app')
        .evaluate((el, n) => (el.scrollTop = n * (el.scrollHeight - el.clientHeight)), proportion)
      const content = await page.locator('.research-app').boundingBox(),
        nav = await page.getByRole('navigation', { name: 'Main navigation' }).boundingBox()
      expect(content.y + content.height).toBeLessThanOrEqual(nav.y)
    }
    if (symbol === 'SUNPHARMA' && theme === 'dark') {
      await page.evaluate(() => {
        const banner = document.createElement('div')
        banner.className = 'recorded-notice'
        banner.id = 'qa-layout-notice'
        banner.textContent = 'Recorded demo layout check. Original source dates remain visible.'
        document.getElementById('root').prepend(banner)
      })
      const nav = await page.getByRole('navigation', { name: 'Main navigation' }).boundingBox()
      expect(nav.y + nav.height).toBeLessThanOrEqual(viewport.height)
      await page.evaluate(() => document.getElementById('qa-layout-notice').remove())
    }
    if (symbol === 'NTPC' && theme === 'light') {
      await page.getByRole('button', { name: 'Investigate', exact: true }).click()
      await expect(page.locator('.research-progress')).toHaveCount(0, { timeout: 30000 })
      await expect(page.locator('.financial-results')).toHaveCount(1)
      await page.locator('.financial-table-wrap .financial-number').first().click()
      await expect(
        page.getByRole('dialog').getByRole('button', { name: 'Ask about this evidence' }),
      ).toBeEnabled({ timeout: 20000 })
      await page.getByRole('button', { name: 'Close evidence' }).click()
    }
    expect(await page.evaluate(() => window.__maxFinancial)).toBe(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    expect(errors).toEqual([])
    if (symbol === 'NTPC' && theme === 'dark') {
      await page.goto(base + '/?view=research&analysis=results&symbol=M%26M')
      await expect(
        page.locator('.financial-bases button').filter({ hasText: 'Standalone' }),
      ).toBeDisabled({ timeout: 30000 })
      await expect(page.locator('.basis-availability')).toContainText('unavailable or unverified')
    }
    checks.push({ symbol, theme, viewport, status: 'passed', errors })
    await ctx.close()
  }
} catch (error) {
  if (lastPage && !lastPage.isClosed()) {
    console.log(
      JSON.stringify(
        await lastPage.evaluate(() => ({
          rawCount: document.querySelectorAll('.financial-results').length,
          max: window.__maxFinancial,
          parents: [...document.querySelectorAll('.financial-results')].map((e) => ({
            parent: e.parentElement.className,
            grandparent: e.parentElement.parentElement.className,
          })),
          root: document.getElementById('root').children.length,
        })),
      ),
    )
    await writeFile(
      new URL('../../artifacts/investor-qa-browser/failure.html', import.meta.url),
      await lastPage.content(),
    )
    await lastPage.screenshot({
      path: new URL(
        '../../artifacts/investor-qa-browser/failure.png',
        import.meta.url,
      ).pathname.replace(/^\/(\w:)/, '$1'),
    })
  }
  throw error
} finally {
  await browser.close()
  await writeFile(
    new URL('../../artifacts/investor-qa-browser/checks.json', import.meta.url),
    JSON.stringify(checks, null, 2),
  )
}
console.log(JSON.stringify(checks))
