// Inspect actual dated prices and source labels; no mocked financial data.
import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const output = fileURLToPath(new URL('../../artifacts/price-browser/', import.meta.url))
await mkdir(output, { recursive: true })
const base = process.env.FINN_BROWSER_URL || 'http://localhost:5173'
const expectedSession = process.env.FINN_EXPECT_SESSION
const expectFailure = process.env.FINN_EXPECT_PRICE_FAILURE === 'true'
const browser = await chromium.launch({ headless: true })
const checks = []
try {
  for (const [name, viewport] of [
    ['mobile', { width: 390, height: 844 }],
    ['desktop', { width: 1440, height: 1000 }],
  ]) {
    const page = await browser.newPage({ viewport })
    const errors = []
    page.on('pageerror', (error) => errors.push(error.name))
    await page.goto(`${base}/?view=portfolio`, { waitUntil: 'networkidle' })
    const cards = page.locator('.portfolio-card')
    await cards.first().waitFor({ timeout: 20000 })
    if ((await cards.count()) !== 15) throw new Error('Expected 15 portfolio price cards.')
    let officialSources = 0
    for (const card of await cards.all()) {
      const text = await card.innerText()
      const session = text.match(/EOD\s*·\s*(\d{4}-\d{2}-\d{2})/)?.[1]
      if (!session || (expectedSession && session !== expectedSession))
        throw new Error(`Unexpected displayed price session: ${session}`)
      if (text.includes('Refresh failed') !== expectFailure)
        throw new Error('Displayed refresh status does not match the verified source state.')
      const sources = card.getByRole('link', { name: 'NSE source' })
      if (await sources.count()) {
        const href = await sources.first().getAttribute('href')
        if (
          !href.startsWith('https://nsearchives.nseindia.com/content/cm/') ||
          !href.includes(session.replaceAll('-', '')) ||
          !text.includes('Prior 20 sessions: Yahoo Finance.')
        )
          throw new Error('Mixed-provider price provenance is missing or dated incorrectly.')
        officialSources++
      }
    }
    if (
      (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) ||
      errors.length
    )
      throw new Error('Price labels caused overflow or an uncaught browser error.')
    await cards.first().evaluate((element) => element.scrollIntoView({ block: 'center' }))
    await cards
      .first()
      .screenshot({
        path: `${output}/${name}-${expectFailure ? 'failed-refresh' : 'verified-source'}.png`,
      })
    checks.push({
      viewport: name,
      companies: 15,
      expected_session: expectedSession,
      explicit_failure: expectFailure,
      official_sources: officialSources,
      page_errors: errors.length,
    })
    await page.close()
  }
  await writeFile(
    `${output}/${expectFailure ? 'failure' : 'success'}-checks.json`,
    JSON.stringify({ checked_at: new Date().toISOString(), checks }, null, 2),
  )
  console.log(
    'PASS: actual price sessions, source links, refresh labels and mobile/desktop layout.',
  )
} finally {
  await browser.close()
}
