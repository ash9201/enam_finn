// UI-only transport replay of recorded real research; no model/source-ingestion calls.
import { chromium, expect } from '@playwright/test'
import { readFile, mkdir } from 'node:fs/promises'

const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const read = async (path) =>
  JSON.parse(await readFile(new URL('../../artifacts/' + path, import.meta.url), 'utf8'))
const fixtures = await read('research-redesign/fixtures.json')
const { root, followup } = await read('release/evidence-followup-mix-real.json')
const answers = [
  fixtures['INFY:overview'],
  fixtures['CCL:comparison'],
  fixtures['CCL:results'],
  root,
  followup,
]
const allClaims = (answer) => [
  ...answer.claims,
  ...[answer.comparison?.earlier, answer.comparison?.later].filter(Boolean),
  ...(answer.comparison?.analysis_claims || []),
  ...(answer.comparison?.additional_context || []),
]
const browser = await chromium.launch()
const output = new URL('../../artifacts/evidence-controls/', import.meta.url)
await mkdir(output, { recursive: true })
try {
  for (const width of [1440, 390])
    for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({
        viewport: { width, height: 900 },
        colorScheme: theme,
      })
      const page = await context.newPage()
      const errors = [],
        requests = []
      page.on('pageerror', (error) => errors.push(error.message))
      await page.route('**/rest/v1/**', (route) => route.fulfill({ json: [] }))
      await page.route('**/research', async (route) => {
        const body = route.request().postDataJSON()
        requests.push(body)
        const answer = answers.find((a) => a.symbol === body.symbol && a.question === body.question)
        if (!answer) throw new Error('No recorded answer for ' + body.question)
        await route.fulfill({ json: { state: 'completed', result: answer, job_id: answer.id } })
      })
      await page.route('**/research/*/evidence/*', async (route) => {
        const url = new URL(route.request().url()),
          parts = url.pathname.split('/')
        const answer = answers.find((a) => a.id === parts[2])
        const citation = allClaims(answer)
          .flatMap((c) => c.citations || [c.citation])
          .find((c) => c.id === parts[4])
        if (!citation) throw new Error('Unknown original citation')
        await route.fulfill({ json: { citation } })
      })
      async function ask(answer, navigate = true) {
        if (navigate) await page.goto(`${base}/?view=research&symbol=${answer.symbol}`)
        await page.getByLabel('Your question').fill(answer.question)
        await page.getByRole('button', { name: 'Investigate', exact: true }).click()
        await expect(page.locator('.answer-question')).toHaveText(answer.question)
      }
      async function inspect(button, citation) {
        await expect(button).toContainText(citation.document_label)
        await expect(button).toContainText('p. ' + citation.pdf_page)
        await expect(button).toHaveAttribute('aria-haspopup', 'dialog')
        await button.focus()
        await page.keyboard.press('Shift')
        expect(await button.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe('none')
        await page.keyboard.press('Enter')
        const drawer = page.getByRole('dialog')
        await expect(drawer.locator('blockquote')).toHaveText(citation.quote)
        const original = drawer.getByRole('link', { name: /Open original document/ })
        const destination =
          (citation.document_url || citation.source_url).split('#')[0] +
          '#page=' +
          citation.pdf_page
        await expect(original).toHaveAttribute('href', destination)
        await expect(original).toHaveAttribute('target', '_blank')
        return { drawer, original, destination }
      }
      const overview = answers[0]
      await ask(overview)
      const index = overview.claims.findIndex((c) => c.citations?.length > 1)
      const claim = overview.claims[index],
        chips = page.locator('.claim-list > li').nth(index).locator('.evidence-button')
      await expect(chips).toHaveCount(claim.citations.length)
      for (let i = 0; i < claim.citations.length; i++) {
        const { drawer, original, destination } = await inspect(chips.nth(i), claim.citations[i])
        if (i === 0) {
          await drawer.getByRole('button', { name: /^Source 2/ }).click()
          await expect(drawer.locator('blockquote')).toHaveText(claim.citations[1].quote)
        }
        if (i === 1 && width === 1440 && theme === 'light') {
          // Observe the real external URL without downloading the PDF during a UI test.
          await context.route(destination.split('#')[0], (route) =>
            route.fulfill({
              contentType: 'text/html',
              body: '<title>External PDF destination</title>',
            }),
          )
          const popup = context.waitForEvent('page')
          await original.click()
          const documentPage = await popup
          await documentPage.waitForLoadState()
          expect(documentPage.url()).toBe(destination)
          await documentPage.close()
        }
        await page.keyboard.press('Escape')
        await expect(chips.nth(i)).toBeFocused()
      }
      const before = await chips.first().boundingBox()
      await inspect(chips.first(), claim.citations[0])
      await page.keyboard.press('Escape')
      const after = await chips.first().boundingBox()
      expect(Math.abs(before.width - after.width)).toBeLessThan(1)
      if ((width === 1440 && theme === 'dark') || (width === 390 && theme === 'light'))
        await page.screenshot({
          path: new URL(`chips-${width}-${theme}.png`, output).pathname.replace(/^\/(\w:)/, '$1'),
          fullPage: true,
        })
      await ask(answers[1])
      await expect(page.locator('.comparison-sides .evidence-button')).toHaveCount(2)
      await inspect(
        page.locator('.comparison-sides .evidence-button').first(),
        answers[1].comparison.earlier.citation,
      )
      await page.keyboard.press('Escape')
      await ask(answers[2])
      await page.getByRole('button', { name: /Inspect Revenue QoQ calculation/ }).click()
      const latest = page.getByRole('button', { name: /Latest figure evidence/ })
      await expect(latest).toHaveClass(/evidence-button/)
      await latest.click()
      await expect(page.getByRole('dialog')).toBeVisible()
      await page.keyboard.press('Escape')
      await ask(root)
      const anchorIndex = root.claims.findIndex(
        (c) => c.citation.id === followup.evidence_context.citation_id,
      )
      await inspect(
        page.locator('.claim-list > li').nth(anchorIndex).locator('.evidence-button').first(),
        root.claims[anchorIndex].citation,
      )
      await page.getByRole('button', { name: 'Ask about this evidence', exact: true }).click()
      await expect(
        page.getByLabel('Active evidence context').locator('.evidence-button'),
      ).toBeVisible()
      await ask(followup, false)
      expect(requests.at(-1).context.citation_id).toBe(followup.evidence_context.citation_id)
      await inspect(
        page.locator('.claim-list .evidence-button').first(),
        followup.claims[0].citation,
      )
      await page.keyboard.press('Escape')
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      await page.goto(base + '/?view=briefing')
      await expect(page.getByText('Know the coverage.', { exact: true })).toHaveCount(0)
      await expect(page.locator('.coverage-footnote')).toContainText(
        'Earlier history may be incomplete',
      )
      expect(errors).toEqual([])
      console.log(
        JSON.stringify({
          width,
          theme,
          checks:
            'multi-source, keyboard/focus, original PDF, source switching, comparison, financial, follow-up, footer, no overflow/layout shift',
        }),
      )
      await context.close()
    }
} finally {
  await browser.close()
}
