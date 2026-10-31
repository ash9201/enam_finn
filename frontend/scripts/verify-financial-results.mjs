// Real published source snapshots. Optional local API forwarding; no fake figures.
import { chromium, expect } from '@playwright/test'
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const localApi = process.env.FINN_FINANCIAL_API_URL
const output = fileURLToPath(new URL('../../artifacts/financial-browser/', import.meta.url))
const followup = JSON.parse(
  await readFile(
    new URL('../../artifacts/financial-results/followup.json', import.meta.url),
    'utf8',
  ),
)
await mkdir(output, { recursive: true })
const browser = await chromium.launch()
const checks = []

async function audit(root) {
  const result = await root.evaluate((element) => {
    const rgb = (value) => value.match(/[\d.]+/g)?.map(Number) || [0, 0, 0, 0]
    const background = (element) => {
      for (let node = element; node; node = node.parentElement) {
        const value = rgb(getComputedStyle(node).backgroundColor)
        if (value[3] === undefined || value[3] >= 0.99) return value
      }
      return [255, 255, 255]
    }
    const lum = (color) =>
      color
        .slice(0, 3)
        .map((c) => c / 255)
        .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
        .reduce((a, c, i) => a + c * [0.2126, 0.7152, 0.0722][i], 0)
    const bad = []
    let count = 0
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT)
    while (walker.nextNode()) {
      const node = walker.currentNode,
        e = node.parentElement
      if (
        !node.textContent.trim() ||
        e.closest('.sr-only') ||
        !e.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
      )
        continue
      const style = getComputedStyle(e),
        fg = rgb(style.color),
        bg = background(e),
        [a, b] = [lum(fg), lum(bg)].sort((a, b) => b - a)
      const ratio = (a + 0.05) / (b + 0.05),
        large =
          parseFloat(style.fontSize) >= 24 ||
          (parseFloat(style.fontSize) >= 18.66 && Number(style.fontWeight) >= 700)
      count++
      if (ratio < (large ? 3 : 4.5)) bad.push({ text: node.textContent.slice(0, 60), ratio })
    }
    return { count, bad, overflow: document.documentElement.scrollWidth > innerWidth }
  })
  expect(result.bad).toEqual([])
  expect(result.overflow).toBe(false)
  return result.count
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
      page.on('pageerror', (error) => errors.push(error.message))
      if (localApi)
        await page.route(
          (url) => /^\/(research|jobs)(\/|$)/.test(url.pathname),
          async (route) => {
            const request = route.request(),
              u = new URL(request.url()),
              cors = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
              }
            if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors })
            const response = await route.fetch({
              url: `${localApi}${u.pathname}${u.search}`,
              timeout: 100000,
            })
            await route.fulfill({ response, headers: { ...response.headers(), ...cors } })
          },
        )
      await page.goto(`${base}/?view=research&symbol=POLYCAB&analysis=results`, {
        waitUntil: 'networkidle',
      })
      await expect(page.locator('.financial-results')).toBeVisible({ timeout: 30000 })
      const figures = page.getByRole('table', { name: 'consolidated quarterly figures' })
      await expect(
        figures.getByRole('button', { name: 'Inspect consolidated Revenue for 2026-09-30' }),
      ).toContainText('98,989.01')
      await expect(
        figures.getByRole('button', { name: 'Inspect consolidated Revenue for 2025-09-30' }),
      ).toContainText('64,772.11')
      await expect(figures.getByRole('row', { name: /EBITDA/ }).getByRole('button')).toHaveCount(0)
      const count = await audit(page.locator('.financial-results'))
      if (size === 'mobile' && theme === 'light') {
        await page.locator('.financial-heading').scrollIntoViewIfNeeded()
        await page.screenshot({ path: `${output}/mobile-light-results.png` })
      }
      await page.getByRole('button', { name: 'Inspect Revenue QoQ calculation' }).click()
      const calculation = page.getByRole('complementary', { name: 'Financial calculation' })
      await expect(calculation).toContainText('16891.69')
      await expect(calculation).toContainText('20.58%')
      await calculation.getByRole('button', { name: /Latest figure evidence/ }).click()
      const dialog = page.getByRole('dialog')
      await expect(
        dialog.getByText('Passage verified against the stored original document.'),
      ).toBeVisible({ timeout: 30000 })
      await expect(
        dialog.getByRole('region', { name: 'Selected financial source cell' }),
      ).toContainText('98,989.01')
      await expect(dialog).toContainText('2026-09-30')
      const evidenceCount = await audit(dialog)
      if (size === 'mobile' && theme === 'dark')
        await page.screenshot({ path: `${output}/mobile-dark-cell-evidence.png` })
      await page.getByRole('button', { name: 'Close evidence' }).click()
      await page.getByRole('button', { name: 'Close calculation' }).click()
      await page.getByRole('button', { name: 'Standalone', exact: true }).click()
      const standalone = page.getByRole('table', { name: 'standalone quarterly figures' })
      await expect(
        standalone.getByRole('button', { name: 'Inspect standalone PAT for 2026-09-30' }),
      ).toContainText('9,651.73')
      await expect(standalone.getByText('Restated', { exact: true })).toHaveCount(3)
      if (size === 'mobile' && theme === 'light') {
        // High claim indexes and shared rows must retain the exact selected quarter/basis.
        await standalone
          .getByRole('button', { name: 'Inspect standalone PAT for 2025-09-30' })
          .click()
        await expect(
          dialog.getByText('Passage verified against the stored original document.'),
        ).toBeVisible({ timeout: 30000 })
        await expect(dialog).toContainText('2025-09-30')
        await expect(
          dialog.getByRole('region', { name: 'Selected financial source cell' }),
        ).toContainText('6,710.23')
        await page.getByRole('button', { name: 'Close evidence' }).click()
        await page.getByRole('button', { name: 'Consolidated', exact: true }).click()
        await page
          .getByRole('button', { name: 'Inspect consolidated Revenue for 2026-09-30' })
          .click()
        await dialog.getByRole('button', { name: /Ask about this evidence/ }).click()
        await expect(page.getByLabel('NSE ticker')).toHaveValue('POLYCAB')
        await expect(page.locator('.active-evidence')).toContainText('98989.01')
        await page.getByLabel('Your question').fill(followup.question)
        await page.getByRole('button', { name: 'Investigate', exact: true }).click()
        await expect(page.locator('.answer-context')).toBeVisible({ timeout: 90000 })
        await expect(page.locator('.claim-list')).toBeVisible()
        await expect(page.locator('.answer-question')).toHaveText(followup.question)
        await page.getByRole('button', { name: 'Remove evidence context' }).click()
        await expect(page.locator('.financial-results')).toBeVisible()
      }
      if (size === 'desktop' && theme === 'dark') {
        await page.goto(`${base}/?view=research&symbol=CCL&analysis=results`, {
          waitUntil: 'networkidle',
        })
        await expect(page.locator('.financial-results')).toBeVisible()
        await expect(
          page.getByRole('button', { name: 'Inspect consolidated Revenue for 2026-09-30' }),
        ).toHaveCount(0)
        await expect(
          page.getByRole('button', { name: 'Inspect PBT QoQ calculation' }),
        ).toBeDisabled()
        await page.getByRole('button', { name: 'Standalone', exact: true }).click()
        expect(await page.locator('.financial-movement.negative').count()).toBeGreaterThan(0)
        await audit(page.locator('.financial-results'))
      }
      expect(errors).toEqual([])
      checks.push({
        size,
        theme,
        visible_text_checks: count + evidenceCount,
        contrast: true,
        overflow: false,
        real_sources: true,
      })
      await context.close()
      console.log(
        `${size}/${theme}: financial figures, basis, calculation and evidence checks passed`,
      )
    }
  }
  await writeFile(`${output}/checks.json`, JSON.stringify(checks, null, 2))
} finally {
  await browser.close()
}
