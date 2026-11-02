// Faults are UI transport fixtures; financial values/passages are recorded real sources.
import { chromium, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'

const load = async (name) =>
  JSON.parse(
    await readFile(new URL('../../artifacts/financial-metrics/' + name, import.meta.url), 'utf8'),
  )
const answer = await load('TMCV-bare.json')
const context = (await load('TMCV-bare-evidence.json'))[0].context
const quarterly = JSON.parse(
  await readFile(
    new URL('../../artifacts/research-redesign/fixtures.json', import.meta.url),
    'utf8',
  ),
)['CCL:results']
const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const browser = await chromium.launch()
try {
  for (const width of [1440, 390])
    for (const theme of ['light', 'dark']) {
      const page = await browser.newPage({ viewport: { width, height: 900 }, colorScheme: theme })
      await page.addInitScript(() => {
        const original = AbortSignal.timeout.bind(AbortSignal)
        window.evidenceTimeouts = []
        AbortSignal.timeout = (ms) => {
          window.evidenceTimeouts.push(ms)
          return original(ms === 15000 && window.evidenceTimeoutShort ? 80 : ms) // Accelerate only the timeout fault.
        }
      })
      let mode = 'verified',
        activeAnswer = answer,
        activeContext = context,
        researchCalls = 0,
        evidenceCalls = 0,
        release
      const errors = []
      page.on('pageerror', (error) => errors.push(error.message))
      await page.route('**/rest/v1/**', (route) => route.fulfill({ json: [] }))
      await page.route('**/research', (route) => {
        researchCalls++
        return route.fulfill({
          json: { state: 'completed', job_id: activeAnswer.id, result: activeAnswer },
        })
      })
      await page.route('**/research/*/evidence/*', async (route) => {
        evidenceCalls++
        if (activeAnswer === quarterly) {
          const request = new URL(route.request().url())
          const claim = quarterly.claims[Number(request.searchParams.get('claim_index'))]
          activeContext = {
            research_id: quarterly.id,
            symbol: quarterly.symbol,
            citation: claim.citation,
          }
        }
        const current = mode
        if (current === 'pending')
          await new Promise((resolve) => {
            release = resolve
          })
        if (current === 'timeout') await new Promise((resolve) => setTimeout(resolve, 220))
        if (current === 'network') return route.abort('failed')
        const detail =
          current === 'failed'
            ? {
                code: 'passage_mismatch',
                message: 'The original stored passage differs.',
                retryable: false,
              }
            : {
                code: 'source_temporarily_unavailable',
                message: 'The stored source cannot currently be rechecked.',
                retryable: true,
              }
        const result =
          current === 'failed' || current === 'unavailable'
            ? { status: current === 'failed' ? 422 : 503, json: { detail } }
            : {
                json: {
                  ...activeContext,
                  citation: {
                    ...activeContext.citation,
                    reporting_period: null,
                    published_at: null,
                    fetched_at: null,
                    ...(current === 'wrong-citation' ? { id: 'not-the-selected-citation' } : {}),
                  },
                },
              }
        await route.fulfill(result).catch(() => {}) // The bounded request may already have aborted.
      })
      await page.goto(base + '/?view=research&symbol=TMCV')
      await page.getByLabel('Your question').fill(answer.question)
      await page.getByRole('button', { name: 'Investigate', exact: true }).click()
      const opener = page
        .getByLabel('Verified financial metrics')
        .getByRole('button', { name: /View evidence/ })
      const drawer = page.getByRole('dialog')
      const ask = drawer.getByRole('button', { name: 'Ask about this evidence', exact: true })
      const status = (value) => drawer.locator(`[data-verification-state="${value}"]`)
      mode = 'pending'
      await opener.click()
      await expect(status('loading')).toBeVisible()
      await expect(ask).toBeDisabled()
      await expect(drawer.locator('blockquote')).toHaveText(context.citation.quote)
      release()
      await expect(status('verified')).toBeVisible()
      await expect(ask).toBeEnabled()
      await expect(drawer.locator('dl')).toContainText('Not established')
      const original = drawer.getByRole('link', { name: /Open original document/ })
      await expect(original).toHaveAttribute(
        'href',
        (context.citation.document_url || context.citation.source_url).split('#')[0] +
          '#page=' +
          context.citation.pdf_page,
      )
      await page.keyboard.press('Escape')
      for (const fault of ['unavailable', 'network', 'failed', 'wrong-citation', 'timeout']) {
        mode = fault
        await page.evaluate((value) => {
          window.evidenceTimeoutShort = value
        }, fault === 'timeout')
        const requestsBefore = evidenceCalls
        await opener.click()
        await expect(
          status(['failed', 'wrong-citation'].includes(fault) ? 'failed' : 'unavailable'),
        ).toBeVisible()
        await expect(ask).toBeDisabled()
        await expect(drawer.locator('blockquote')).toHaveText(context.citation.quote)
        await expect(original).toBeVisible()
        expect(evidenceCalls).toBe(requestsBefore + 1) // No hidden retries or new research jobs.
        if (['unavailable', 'network', 'timeout'].includes(fault)) {
          mode = 'verified'
          await page.evaluate(() => {
            window.evidenceTimeoutShort = false
          })
          await drawer.getByRole('button', { name: 'Retry verification', exact: true }).click()
          await expect(status('verified')).toBeVisible()
          await expect(ask).toBeEnabled()
        } else
          await expect(drawer.getByRole('button', { name: 'Retry verification' })).toHaveCount(0)
        await page.keyboard.press('Escape')
      }
      expect(researchCalls).toBe(1)
      if (width === 1440 && theme === 'light') {
        activeAnswer = quarterly
        activeContext = {
          research_id: quarterly.id,
          symbol: quarterly.symbol,
          citation: quarterly.claims[0].citation,
        }
        mode = 'verified'
        await page.route('**/research/*/evidence/*/image', (route) =>
          route.fulfill({ status: 404 }),
        )
        await page.goto(base + '/?view=research&symbol=CCL')
        await page.getByLabel('Your question').fill(quarterly.question)
        await page.getByRole('button', { name: 'Investigate', exact: true }).click()
        await page.locator('.financial-number').first().click()
        await expect(status('verified')).toBeVisible()
        await drawer
          .getByRole('button', { name: 'View original statement page', exact: true })
          .click()
        await expect(
          drawer.getByText('The page preview is unavailable.', { exact: false }),
        ).toBeVisible()
        await expect(status('verified')).toBeVisible()
        await expect(ask).toBeEnabled()
        await page.keyboard.press('Escape')
      }
      expect(await page.evaluate(() => window.evidenceTimeouts.includes(15000))).toBe(true)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      expect(errors).toEqual([])
      console.log(
        JSON.stringify({
          width,
          theme,
          states: 'loading, verified, unavailable, failed',
          checks:
            'metadata, network, timeout, mismatch, retry-only-evidence, follow-up gates, original PDF',
        }),
      )
      await page.close()
    }
} finally {
  await browser.close()
}
