import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const output = fileURLToPath(new URL('../../artifacts/product-browser/', import.meta.url))
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const base = process.env.FINN_BROWSER_URL || 'http://localhost:5173'
const checks = []
try {
  for (const [name, viewport] of [
    ['mobile', { width: 390, height: 844 }],
    ['desktop', { width: 1440, height: 1000 }],
  ]) {
    const context = await browser.newContext({ viewport })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', (error) => errors.push(error.name))
    await page.goto(base, { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: /What deserves/ }).waitFor()
    await page.getByText('companies followed', { exact: true }).waitFor({ timeout: 20000 })
    if ((await page.locator('.filing-card').count()) < 1)
      throw new Error('No actual portfolio filings loaded.')
    await page.getByRole('button', { name: '7 days', exact: true }).click()
    await page.getByRole('button', { name: 'Custom', exact: true }).click()
    await page.getByLabel('From (IST)').fill('2026-10-01T00:00')
    await page.getByLabel('To (IST)').fill('2026-10-31T23:59')
    await page.getByLabel('From (IST)').fill('2030-01-01T00:00')
    await page.getByLabel('To (IST)').fill('2030-01-02T00:00')
    await page.getByRole('button', { name: 'Review the last 7 days', exact: true }).click()
    if ((await page.locator('.filing-card').count()) < 1)
      throw new Error('Empty window did not recover through the explicit seven-day action.')
    await page.getByRole('button', { name: '24 hours', exact: true }).click()
    const routine = page.locator('.routine-toggle')
    if (await routine.count()) {
      await routine.click()
      if ((await routine.getAttribute('aria-expanded')) !== 'true')
        throw new Error('Routine filings did not expand.')
    }
    await page.getByRole('button', { name: /Alert settings/ }).click()
    await page.getByLabel('Daily price move threshold').fill('3')
    await page.getByLabel('Volume threshold').fill('1.5')
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: /Alert settings/ }).click()
    if ((await page.getByLabel('Daily price move threshold').inputValue()) !== '3')
      throw new Error('Alert preferences were not preserved.')
    await page.screenshot({ path: `${output}/${name}-briefing.png`, fullPage: true })
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Portfolio' })
      .click()
    await page.locator('.portfolio-card').first().waitFor({ timeout: 20000 })
    if ((await page.locator('.portfolio-card').count()) !== 15)
      throw new Error('Portfolio does not contain 15 real company snapshots.')
    await page.screenshot({ path: `${output}/${name}-portfolio.png`, fullPage: true })
    await page.goto(`${base}/?view=research&symbol=INFY`, { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: 'Infosys Limited' }).waitFor({ timeout: 20000 })
    await page.getByRole('heading', { name: 'Follow the statement.' }).waitFor({ timeout: 20000 })
    if (!(await page.locator('.comparison-panel').innerText()).includes('Not yet assessable'))
      throw new Error('Comparison verdict is missing or overconfident.')
    if ((await page.locator('.comparison-panel .citation-button').count()) !== 2)
      throw new Error('Both comparison sources must be accessible.')
    await page.locator('.citation-button').first().click()
    await page.getByRole('dialog').waitFor()
    if ((await page.locator('blockquote').innerText()).length < 12)
      throw new Error('Citation excerpt is missing.')
    await page.getByRole('button', { name: 'Close evidence' }).click()
    await page.screenshot({ path: `${output}/${name}-research.png`, fullPage: true })
    if (name === 'mobile') {
      // Identical question exercises a real persisted job but should reuse the model cache.
      let interruptedStatus = false
      await page.route('**/jobs/*', (route) => {
        if (!interruptedStatus) {
          interruptedStatus = true
          return route.abort('failed')
        }
        return route.continue()
      })
      await page.getByRole('button', { name: 'Investigate', exact: true }).click()
      await page
        .getByRole('button', { name: 'Investigating…', exact: true })
        .waitFor({ state: 'detached', timeout: 120000 })
      if (await page.getByRole('alert').count())
        throw new Error(await page.getByRole('alert').innerText())
      await page.getByLabel('NSE ticker').fill('ZZZFINN42')
      await page.getByRole('button', { name: 'Investigate', exact: true }).click()
      await page.getByRole('alert').waitFor({ timeout: 60000 })
      if (!(await page.getByRole('alert').innerText()).includes('not found'))
        throw new Error('Unknown ticker did not fail honestly.')
      if (await page.locator('.answer-panel').count())
        throw new Error('Unknown ticker was given another company’s answer.')
    }
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    )
    if (overflow || errors.length)
      throw new Error(`${name}: horizontal overflow or uncaught page error.`)
    checks.push({
      viewport: name,
      conservative_comparison: true,
      real_filings: true,
      windows: true,
      persistent_thresholds: true,
      portfolio_15: true,
      primary_citations: true,
      no_overflow: true,
      page_errors: errors.length,
    })
    await context.close()
  }
  const recorded = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const offline = await recorded.newPage()
  await offline.route('**/rest/v1/**', (route) => route.abort('failed'))
  await offline.goto(base, { waitUntil: 'networkidle' })
  await offline.getByText(/Recorded demo snapshot/).waitFor({ timeout: 20000 })
  if ((await offline.locator('.filing-card').count()) < 1)
    throw new Error('Recorded snapshot failed to render saved filings.')
  await offline.screenshot({ path: `${output}/mobile-recorded.png`, fullPage: true })
  await offline
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Portfolio' })
    .click()
  await offline.locator('.portfolio-card').first().waitFor()
  if ((await offline.locator('.portfolio-card').count()) !== 15)
    throw new Error('Recorded portfolio is incomplete.')
  checks.push({ viewport: 'mobile-recorded', historical_banner: true, portfolio_15: true })
  await recorded.close()
  await writeFile(
    `${output}/checks.json`,
    JSON.stringify({ checked_at: new Date().toISOString(), checks }, null, 2),
  )
  console.log(
    'PASS: real briefing/portfolio/research at phone and desktop sizes; citations, persisted jobs, unknown ticker, windows and settings verified.',
  )
} finally {
  await browser.close()
}
