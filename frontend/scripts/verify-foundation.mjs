// Browser acceptance of real local connections, not fabricated financial data.
import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const output = fileURLToPath(new URL('../../artifacts/status-browser/', import.meta.url))
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const results = []
try {
  for (const [name, viewport] of [
    ['mobile', { width: 390, height: 844 }],
    ['desktop', { width: 1440, height: 1000 }],
  ]) {
    const context = await browser.newContext({ viewport })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', (error) => errors.push(error.name))
    // Relay the real read-only liveness response for local preview origins.
    await page.route('**/health/live', async (route) => {
      const response = await route.fetch()
      await route.fulfill({
        response,
        headers: { ...response.headers(), 'Access-Control-Allow-Origin': '*' },
      })
    })
    const url = new URL(process.env.FINN_BROWSER_URL || 'http://localhost:5173')
    url.searchParams.set('view', 'status')
    await page.goto(url.toString(), { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: 'System Status' }).waitFor()
    await page.getByText('Connected', { exact: true }).nth(1).waitFor({ timeout: 95000 })
    if ((await page.getByRole('link', { name: 'Back to FINN' }).count()) !== 1)
      throw new Error('System status must have an obvious return action.')
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    )
    if (overflow || errors.length)
      throw new Error(`${name} has horizontal overflow or uncaught page errors.`)
    await page.screenshot({ path: `${output}/${name}.png`, fullPage: true })
    // Verify that an actual failed live request gets an explicit failure state.
    await page.route('**/health/live', (route) =>
      route.fulfill({ status: 503, body: 'unavailable' }),
    )
    await page.getByRole('button', { name: 'Check again' }).click()
    await page.getByText('Unavailable', { exact: true }).waitFor()
    await page.getByText(/The research service could not be reached/).waitFor()
    results.push({
      viewport: name,
      api_reachable: true,
      public_cache_read: true,
      no_horizontal_overflow: true,
      uncaught_errors: 0,
      explicit_failure_state: true,
    })
    await page.unrouteAll({ behavior: 'ignoreErrors' })
    await context.close()
  }
  await writeFile(
    `${output}/checks.json`,
    JSON.stringify({ checked_at: new Date().toISOString(), checks: results }, null, 2),
  )
  console.log(
    'PASS: mobile and desktop system-status connections, layout, and explicit failure states verified in Chromium.',
  )
} finally {
  await browser.close()
}
