// Opt-in: replay a real private root answer, then exercise real API jobs/cache.
// Generate the local fixture with scripts/verify_evidence_research.py first.
import { chromium, expect } from '@playwright/test'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const api = process.env.FINN_EVIDENCE_API_URL || 'http://127.0.0.1:8000'
const output = fileURLToPath(new URL('../../artifacts/evidence-browser/', import.meta.url))
const fixture = JSON.parse(
  await readFile(
    new URL('../../artifacts/release/evidence-followup-mix-real.json', import.meta.url),
    'utf8',
  ),
)
const { root, followup } = fixture
const selected = root.claims.find((c) => c.citation.id === followup.evidence_context.citation_id)
if (!selected) throw new Error('The real-source fixture has no matching anchor.')
await mkdir(output, { recursive: true })
const cors = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
}
const browser = await chromium.launch()
const checks = []

async function screenshot(page, name) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  expect(overflow).toBe(false)
  await page.screenshot({ path: `${output}/${name}.png` })
}

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
      const requests = []
      let liveResult
      let rejectContext = false
      page.on('pageerror', (error) => errors.push(error.message))
      // Only the initial view uses a transport replay; evidence reads and follow-up jobs are real.
      await page.route('**/rest/v1/**', (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          headers: cors,
          body: JSON.stringify(
            route.request().url().includes('/finn_companies')
              ? [
                  {
                    symbol: root.symbol,
                    name: root.company_name,
                    sector: 'Consumer',
                    source_checked_at: root.source_checked_at,
                  },
                ]
              : [],
          ),
        }),
      )
      await page.route(
        (url) => /\/(research|jobs)(\/|$)/.test(url.pathname),
        async (route) => {
          const request = route.request()
          if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors })
          const url = new URL(request.url())
          if (url.pathname === '/research' && request.method() === 'POST') {
            const body = request.postDataJSON()
            if (!body.context)
              return route.fulfill({ json: { job_id: 'replayed-root' }, headers: cors })
            requests.push(body)
            if (rejectContext)
              return route.fulfill({ json: { job_id: 'missing-context-test' }, headers: cors })
          }
          if (
            url.pathname === '/jobs/replayed-root' ||
            url.pathname === '/jobs/missing-context-test'
          )
            return route.fulfill({
              json: { state: 'completed', stage: 'completed', result: root },
              headers: cors,
            })
          const response = await route.fetch({
            url: `${api}${url.pathname}${url.search}`,
            timeout: 100000,
          })
          if (url.pathname.startsWith('/jobs/') && response.ok()) {
            const data = await response.json()
            if (data.state === 'completed') liveResult = data.result
          }
          await route.fulfill({ response, headers: { ...response.headers(), ...cors } })
        },
      )
      await page.goto(`${base}/?view=research&symbol=${root.symbol}`, { waitUntil: 'networkidle' })
      await page.getByLabel('Your question').fill(root.question)
      await page.getByRole('button', { name: 'Investigate', exact: true }).click()
      await expect(page.locator('.answer-panel')).toBeVisible({ timeout: 20000 })
      const claimButton = page.getByRole('button', {
        name: `Review evidence: ${selected.statement}`,
        exact: true,
      })
      await claimButton.click()
      const dialog = page.getByRole('dialog')
      await expect(dialog.locator('blockquote')).toHaveText(selected.citation.quote)
      await expect(
        dialog.getByText('Passage verified against the stored original document.'),
      ).toBeVisible({ timeout: 30000 })
      await expect(dialog).toContainText(/28\s+Jul\s+2026/)
      await expect(dialog.getByRole('link', { name: /Open original document/ })).toHaveAttribute(
        'href',
        new RegExp(`#page=${selected.citation.pdf_page}$`),
      )
      await expect(page.locator('body')).toHaveCSS('overflow', 'hidden')
      await screenshot(page, `${size}-${theme}-passage`)
      // Keyboard dismissal restores focus; opening a citation gives the same evidence.
      await page.keyboard.press('Escape')
      await expect(dialog).toHaveCount(0)
      await expect(claimButton).toBeFocused()
      await page.locator('.claim-list .citation-button').nth(root.claims.indexOf(selected)).click()
      await dialog.getByRole('button', { name: /What happened later/ }).click()
      await expect(page.locator('.active-evidence')).toContainText(selected.statement)
      await expect(page.getByLabel('NSE ticker')).toHaveValue(root.symbol)
      await expect(page.getByLabel('Your question')).toBeFocused()
      await page.getByRole('checkbox', { name: /Check latest sources/ }).uncheck()
      await page.getByLabel('Your question').fill(followup.question)
      await screenshot(page, `${size}-${theme}-context`)
      await page.getByRole('button', { name: 'Investigate', exact: true }).click()
      await expect(page.locator('.answer-context')).toBeVisible({ timeout: 90000 })
      expect(liveResult?.cached).toBe(true)
      expect(liveResult?.id).toBe(followup.id)
      expect(requests[0].context).toEqual({
        research_id: root.id,
        citation_id: selected.citation.id,
        claim_index: root.claims.indexOf(selected),
        intent: 'later',
      })
      expect(
        liveResult.claims.every((c) => c.citation.document_id !== selected.citation.document_id),
      ).toBe(true)
      await expect(page.locator('.source-relation').first()).toContainText('Later source')
      await expect(page.locator('.active-evidence')).toContainText(selected.statement)
      await page.locator('.answer-context').scrollIntoViewIfNeeded()
      await screenshot(page, `${size}-${theme}-later-answer`)
      const nextIndex = Math.min(1, liveResult.claims.length - 1)
      await page.locator('.claim-list .claim-statement').nth(nextIndex).click()
      await expect(
        dialog.getByText('Passage verified against the stored original document.'),
      ).toBeVisible({ timeout: 30000 })
      await expect(dialog).toContainText(/16\s+Oct\s+2026/)
      await expect(dialog.locator('blockquote')).toHaveText(
        liveResult.claims[nextIndex].citation.quote,
      )
      const ask = dialog.getByRole('button', { name: /Ask about this evidence/ })
      await expect(ask).toBeInViewport()
      await ask.click()
      await expect(page.getByLabel('Your question')).toHaveValue('')
      await expect(page.locator('.active-evidence')).toContainText(
        liveResult.claims[nextIndex].statement,
      )
      await page.getByRole('button', { name: 'Remove evidence context' }).click()
      await expect(page.locator('.active-evidence')).toHaveCount(0)
      await expect(page.locator('.answer-question')).toHaveText(root.question)
      await page
        .getByRole('navigation', { name: 'Research trail' })
        .getByRole('button', { name: followup.question, exact: true })
        .click()
      await expect(page.locator('.active-evidence')).toContainText(selected.statement)
      // An older backend must never silently substitute a general answer for a follow-up.
      rejectContext = true
      await page.getByRole('button', { name: 'Investigate', exact: true }).click()
      await expect(page.getByRole('alert')).toContainText(/evidence context/i, { timeout: 20000 })
      await expect(page.locator('.active-evidence')).toContainText(selected.statement)
      await page.getByLabel('NSE ticker').fill('INFY')
      await expect(page.locator('.active-evidence')).toHaveCount(0)
      await expect(page.getByRole('navigation', { name: 'Research trail' })).toHaveCount(0)
      expect(errors).toEqual([])
      checks.push({
        size,
        theme,
        real_followup_cached: true,
        claim_count: liveResult.claims.length,
        keyboard_focus: true,
        context_clear_and_restore: true,
        context_failure_guard: true,
        overflow: false,
      })
      await context.close()
      console.log(
        `${size} / ${theme}: evidence, real API follow-up, context and failure checks passed`,
      )
    }
  }
  await writeFile(`${output}/checks.json`, JSON.stringify(checks, null, 2))
} finally {
  await browser.close()
}
