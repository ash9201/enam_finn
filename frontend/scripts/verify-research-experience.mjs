// Consolidated UI checks. Review fixtures are real private pipeline outputs;
// evidence, page previews, jobs, readiness and one follow-up use the live API.
import { chromium, expect } from '@playwright/test'
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const relay = process.env.FINN_EXPERIENCE_API_URL
const useSnapshots = process.env.FINN_USE_REVIEW_SNAPSHOTS === 'true'
const root = new URL('../../artifacts/experience-audit/', import.meta.url)
const output = new URL('../../artifacts/experience-browser/', import.meta.url)
await mkdir(output, { recursive: true })
const snapshots = new Map()
if (useSnapshots) {
  for (const [symbol, name, question] of [
    ['HDFCBANK', 'HDFCBANK-improved-results', 'results'],
    ['M&M', 'M&M-improved-results', 'results'],
    ['CCL', 'CCL-overview', 'overview'],
    ['INFY', 'INFY-overview', 'overview'],
    ['CCL', 'CCL-improved-comparison', 'comparison'],
    ['KPITTECH', 'KPITTECH-improved-comparison', 'comparison'],
  ])
    snapshots.set(
      symbol + ':' + question,
      JSON.parse(await readFile(new URL(name + '.json', root), 'utf8')),
    )
}

async function audit(locator) {
  const result = await locator.evaluate((element) => {
    const rgb = (value) => value.match(/[\d.]+/g)?.map(Number) || [0, 0, 0, 0]
    const background = (e) => {
      for (let n = e; n; n = n.parentElement) {
        const c = rgb(getComputedStyle(n).backgroundColor)
        if (c[3] === undefined || c[3] >= 0.99) return c
      }
      return [255, 255, 255]
    }
    const lum = (c) =>
      c
        .slice(0, 3)
        .map((x) => x / 255)
        .map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4))
        .reduce((a, x, i) => a + x * [0.2126, 0.7152, 0.0722][i], 0)
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT),
      bad = []
    while (walker.nextNode()) {
      const n = walker.currentNode,
        e = n.parentElement
      if (
        !n.textContent.trim() ||
        e.closest('.sr-only') ||
        !e.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
      )
        continue
      const s = getComputedStyle(e),
        [a, b] = [lum(rgb(s.color)), lum(background(e))].sort((x, y) => y - x)
      const large =
        parseFloat(s.fontSize) >= 24 ||
        (parseFloat(s.fontSize) >= 18.66 && Number(s.fontWeight) >= 700)
      if ((a + 0.05) / (b + 0.05) < (large ? 3 : 4.5))
        bad.push({ text: n.textContent.slice(0, 50), ratio: (a + 0.05) / (b + 0.05) })
    }
    return { bad, overflow: document.documentElement.scrollWidth > innerWidth }
  })
  expect(result.bad).toEqual([])
  expect(result.overflow).toBe(false)
}

const checks = []
const browser = await chromium.launch()
try {
  for (const [size, viewport] of [
    ['mobile', { width: 390, height: 844 }],
    ['desktop', { width: 1440, height: 1000 }],
  ]) {
    for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({
        viewport,
        colorScheme: theme,
        reducedMotion: 'reduce',
      })
      await context.addInitScript((value) => localStorage.setItem('finn-theme', value), theme)
      const page = await context.newPage()
      const errors = []
      page.on('pageerror', (error) => errors.push(error.message))
      await page.route('**/*', async (route) => {
        const request = route.request(),
          u = new URL(request.url())
        if (useSnapshots && u.pathname.endsWith('/rest/v1/finn_research_cache')) {
          const symbol = (u.searchParams.get('symbol') || '').replace(/^eq\./, ''),
            q = u.searchParams.get('question') || ''
          const kind = q.includes('quarterly Revenue')
            ? 'results'
            : q.includes('Trace one earlier')
              ? 'comparison'
              : 'overview'
          const answer = snapshots.get(symbol + ':' + kind)
          if (answer)
            return route.fulfill({
              json: [{ result: answer, created_at: answer.generated_at }],
              headers: { 'Access-Control-Allow-Origin': '*' },
            })
        }
        if (relay && /^\/(research|jobs|companies)(\/|$)/.test(u.pathname)) {
          if (request.method() === 'OPTIONS')
            return route.fulfill({
              status: 204,
              headers: {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
              },
            })
          const response = await fetch(relay + u.pathname + u.search, {
            method: request.method(),
            headers: { 'Content-Type': 'application/json' },
            body: request.postData() || undefined,
          })
          return route.fulfill({
            status: response.status,
            body: Buffer.from(await response.arrayBuffer()),
            headers: {
              'Content-Type': response.headers.get('content-type') || 'application/json',
              'Access-Control-Allow-Origin': '*',
            },
          })
        }
        await route.continue()
      })

      await page.goto(base + '/?view=research&symbol=HDFCBANK&analysis=results')
      await expect(
        page.getByRole('table', { name: 'consolidated quarterly figures', exact: true }),
      ).toBeVisible({ timeout: 30000 })
      await expect(page.locator('.financial-table').first()).toContainText('Bank: total income')
      await audit(page.locator('.answer-panel'))
      await page
        .getByRole('button', { name: 'Inspect consolidated Revenue for 2026-09-30', exact: true })
        .click()
      const dialog = page.getByRole('dialog')
      await expect(dialog).toContainText('129358.69')
      await expect(dialog).toContainText('Two separate image reads')
      await expect(dialog.getByRole('button', { name: /Ask about this evidence/ })).toBeEnabled({
        timeout: 15000,
      })
      await audit(dialog)
      if (size === 'mobile' && theme === 'light') {
        await dialog.getByRole('button', { name: 'View original statement page' }).click()
        await expect(dialog.locator('.statement-preview img')).toBeVisible()
        await expect
          .poll(() => dialog.locator('.statement-preview img').evaluate((img) => img.naturalWidth))
          .toBeGreaterThan(500)
      }
      await dialog.getByRole('button', { name: /Ask about this evidence/ }).click()
      await expect(page.getByLabel('Active evidence context')).toContainText('HDFCBANK')
      await page.getByRole('button', { name: 'Remove evidence context' }).click()
      await expect(page.getByLabel('Active evidence context')).toHaveCount(0)

      await page.goto(base + '/?view=research&symbol=CCL')
      await expect(page.locator('.comparison-panel')).toContainText('Outlook reaffirmed', {
        timeout: 30000,
      })
      await expect(page.locator('.claim-list .analysis-heading').first()).toBeVisible()
      await audit(page.locator('.answer-panel'))
      await audit(page.locator('.comparison-panel'))
      const analysis = page.locator('.comparison-analysis')
      await expect(analysis).toBeVisible()
      await analysis.locator('.citation-button').last().click()
      await expect(
        page.getByRole('dialog').getByRole('button', { name: /Ask about this evidence/ }),
      ).toBeEnabled({ timeout: 15000 })
      if (size === 'mobile' && theme === 'light') {
        await expect(page.getByRole('dialog').getByLabel('Supporting sources')).toBeVisible()
        await page
          .getByRole('dialog')
          .getByRole('button', { name: /Ask about this evidence/ })
          .click()
        await page
          .locator('.research-form textarea')
          .fill(
            'Explain how management related volume growth to EBITDA in this statement. Keep expectations distinct from results.',
          )
        await page.getByRole('button', { name: 'Investigate', exact: true }).click()
        await expect(page.locator('.answer-context')).toBeVisible({ timeout: 120000 })
        await expect(page.locator('.research-error')).toHaveCount(0)
        await expect(page.locator('.claim-list li').first()).toBeVisible()
      } else {
        await page.getByRole('button', { name: 'Close evidence' }).click()
      }
      if (size === 'desktop' && theme === 'dark') {
        await page.goto(base + '/?view=research&symbol=M%26M&analysis=results')
        await expect(page.locator('.financial-partial')).toBeVisible({ timeout: 30000 })
        await audit(page.locator('.answer-panel'))
        await page.goto(base + '/?view=research&symbol=INFY')
        await expect(page.locator('.answer-panel')).toBeVisible({ timeout: 30000 })
        await page.getByText('Sources, coverage & search details', { exact: true }).click()
        await expect(page.locator('.search-status')).toContainText(/paused|incomplete/, {
          timeout: 20000,
        })
        await expect(page.locator('.search-status')).not.toContainText('still being prepared')
        await page.screenshot({
          path: fileURLToPath(new URL('desktop-dark-research.png', output)),
          fullPage: false,
        })
      }
      checks.push({ size, theme, status: 'passed', pageErrors: errors })
      expect(errors).toEqual([])
      await context.close()
    }
  }
} finally {
  await browser.close()
  await writeFile(new URL('checks.json', output), JSON.stringify(checks, null, 2))
}
console.log(JSON.stringify(checks))
