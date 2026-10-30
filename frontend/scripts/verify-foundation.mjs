// Browser acceptance of real local connections, not fabricated financial data.
import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const output = fileURLToPath(new URL('../../artifacts/milestone-0/browser/', import.meta.url))
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
    const url = new URL(process.env.FINN_BROWSER_URL || 'http://localhost:5173')
    url.searchParams.set('view', 'foundation')
    await page.goto(url.toString(), { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: /Good decisions/ }).waitFor()
    await page.getByRole('button', { name: 'Check API connection' }).click()
    await page.getByText('API reachable', { exact: true }).waitFor({ timeout: 95000 })
    const cache = page.getByRole('button', { name: 'Check public cache' })
    if (!(await cache.isEnabled()))
      throw new Error('Public Supabase environment is missing from the frontend.')
    await cache.click()
    await page
      .getByText(/The publishable key can read the foundation status/)
      .waitFor({ timeout: 20000 })
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
    await page.getByRole('button', { name: 'Check API connection' }).click()
    await page.getByText('API unavailable', { exact: true }).waitFor()
    await page.getByText(/No cached or invented financial data has been substituted/).waitFor()
    results.push({
      viewport: name,
      api_reachable: true,
      public_cache_read: true,
      no_horizontal_overflow: true,
      uncaught_errors: 0,
      explicit_failure_state: true,
    })
    await context.close()
  }
  await writeFile(
    `${output}/checks.json`,
    JSON.stringify({ checked_at: new Date().toISOString(), checks: results }, null, 2),
  )
  console.log(
    'PASS: mobile and desktop API/cache connections, layout, and explicit failure states verified in Chromium.',
  )
} finally {
  await browser.close()
}
