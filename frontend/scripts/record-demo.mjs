import { chromium } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const output = fileURLToPath(new URL('../../artifacts/demo/', import.meta.url))
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
  recordVideo: { dir: output, size: { width: 390, height: 844 } },
})
const page = await context.newPage()
const video = page.video()
const base = process.env.FINN_BROWSER_URL || 'http://localhost:5173'
const pause = () => page.waitForTimeout(2500)
try {
  await page.goto(base, { waitUntil: 'networkidle' })
  await page.locator('.filing-card').first().waitFor({ timeout: 20000 })
  await pause()
  await page.locator('.filing-card').first().scrollIntoViewIfNeeded()
  await pause()
  await page.getByRole('button', { name: '7 days', exact: true }).click()
  await pause()
  await page.getByRole('button', { name: /Alert settings/ }).click()
  await page.getByLabel('Daily price move threshold').scrollIntoViewIfNeeded()
  await page.getByLabel('Daily price move threshold').fill('3')
  await pause()
  await page.goto(`${base}/?view=research&symbol=INFY`, { waitUntil: 'networkidle' })
  await page.getByRole('heading', { name: 'Infosys Limited' }).waitFor({ timeout: 20000 })
  await page.locator('.answer-panel').scrollIntoViewIfNeeded()
  await pause()
  await page.locator('.answer-panel .citation-button').first().click()
  await pause()
  await page.getByRole('button', { name: 'Close evidence' }).click()
  await page.locator('.comparison-panel').scrollIntoViewIfNeeded()
  await pause()
  await pause()
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Portfolio' })
    .click()
  await page.locator('.portfolio-card').first().waitFor({ timeout: 20000 })
  await page.locator('.portfolio-card').first().scrollIntoViewIfNeeded()
  await pause()
  await page.locator('.portfolio-card').nth(4).scrollIntoViewIfNeeded()
  await pause()
} finally {
  await context.close()
  if (video) await video.saveAs(`${output}/finn-phone-demo.webm`)
  await browser.close()
}
console.log('Saved phone walkthrough: artifacts/demo/finn-phone-demo.webm')
