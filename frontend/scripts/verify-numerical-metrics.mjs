// Rendering fixtures are real, source-verified numerical answers, not a live model run.
import { chromium, expect } from '@playwright/test'
import { readFile, mkdir, writeFile } from 'node:fs/promises'

const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const root = new URL('../../artifacts/financial-metrics/', import.meta.url)
const output = new URL('../../artifacts/financial-metrics-browser/', import.meta.url)
const load = async (name) => JSON.parse(await readFile(new URL(name, root), 'utf8'))
const answers = { TMCV: await load('TMCV-bare.json'), V2RETAIL: await load('V2RETAIL-margin.json') }
const unavailable = await load('TMCV-unavailable.json')
const evidence = {
  TMCV: await load('TMCV-bare-evidence.json'),
  V2RETAIL: await load('V2RETAIL-margin-evidence.json'),
}
await mkdir(output, { recursive: true })
const browser = await chromium.launch()
const results = []
try {
  for (const [theme, width] of [
    ['light', 1440],
    ['dark', 1440],
    ['light', 390],
    ['dark', 390],
  ]) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, colorScheme: theme })
    const errors = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.route('**/research', async (route) => {
      if (route.request().method() !== 'POST') return route.continue()
      const { symbol, question } = route.request().postDataJSON()
      await route.fulfill({
        json: {
          job_id: 'render-fixture',
          state: 'completed',
          result: question.includes('2019') ? unavailable : answers[symbol],
        },
      })
    })
    await page.route('**/research/*/evidence/*', async (route) => {
      const url = new URL(route.request().url()),
        symbol = url.searchParams.get('symbol')
      const index = Number(url.searchParams.get('claim_index') || 0)
      await route.fulfill({ json: evidence[symbol][index].context })
    })
    for (const [symbol, question] of [
      ['TMCV', 'debt to equity ratio'],
      ['V2RETAIL', 'net profit margin quarterly'],
    ]) {
      await page.goto(`${base}/?view=research&symbol=${symbol}`)
      await page.getByLabel('Your question').fill(question)
      await page.getByRole('button', { name: 'Investigate', exact: true }).click()
      const panel = page.getByLabel('Verified financial metrics')
      await expect(panel).toBeVisible()
      await expect(panel.locator('.metric-value')).toContainText(
        answers[symbol].financial_metrics.results[0].display_value,
      )
      await expect(panel).toContainText(answers[symbol].financial_metrics.results[0].period_end)
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      ).toBe(true)
      if (symbol === 'V2RETAIL') {
        await panel.getByText('Formula and verified inputs', { exact: true }).click()
        await expect(panel.locator('.metric-formula')).toContainText('Revenue from operations')
        const sources = panel.getByRole('button', { name: 'Source', exact: true })
        await expect(sources).toHaveCount(2)
        await sources.nth(1).click()
      } else {
        await panel.getByRole('button', { name: /View source evidence/ }).click()
      }
      await expect(page.getByRole('dialog')).toBeVisible()
      await expect(
        page.getByText('Passage verified against the stored original document.'),
      ).toBeVisible()
      await expect(page.getByRole('dialog').locator('blockquote')).toContainText(
        evidence[symbol][symbol === 'V2RETAIL' ? 1 : 0].context.citation.quote,
      )
      await page.getByRole('button', { name: 'Ask about this evidence', exact: true }).click()
      await expect(page.getByLabel('Active evidence context')).toBeVisible()
      await expect(page.getByLabel('Selected company')).toContainText(symbol)
      if ((theme === 'dark' && width === 1440) || (theme === 'light' && width === 390))
        await page.screenshot({
          path: new URL(`${symbol}-${theme}-${width}.png`, output).pathname.replace(
            /^\/(\w:)/,
            '$1',
          ),
          fullPage: true,
        })
    }
    await page.goto(`${base}/?view=research&symbol=TMCV`)
    await page.getByLabel('Your question').fill('ROIC FY2019')
    await page.getByRole('button', { name: 'Investigate', exact: true }).click()
    await expect(page.locator('.metric-missing')).toContainText('could not be verified')
    await expect(page.locator('.metric-value')).toHaveCount(0)
    await expect(page.getByLabel('Verified financial metrics')).toContainText('2019')
    expect(errors).toEqual([])
    results.push({
      theme,
      width,
      verified: [
        'reported metric',
        'calculated metric',
        'input sources',
        'evidence follow-up',
        'no overflow',
      ],
    })
    await page.close()
  }
  await writeFile(new URL('checks.json', output), JSON.stringify(results, null, 2))
} finally {
  await browser.close()
}
console.log(JSON.stringify(results))
