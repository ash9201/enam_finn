import { chromium, expect } from '@playwright/test'
import { mkdir, writeFile, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const output = fileURLToPath(new URL('../../artifacts/theme-browser/', import.meta.url))
await mkdir(output, { recursive: true })
for (const name of ['style.css', 'briefing.css', 'research.css']) {
  const css = await readFile(new URL(`../src/${name}`, import.meta.url), 'utf8')
  if (/#[\da-f]{3,8}\b|\brgba?\(/i.test(css))
    throw new Error(`${name} has a colour outside shared tokens.`)
}
const browser = await chromium.launch({ headless: true })
const checks = []

async function theme(page, value) {
  await expect(page.locator('html')).toHaveAttribute('data-theme', value)
  await expect(page.locator('html')).toHaveCSS('color-scheme', value)
}

async function audit(page, scene) {
  const result = await page.evaluate(() => {
    const rgb = (value) => value.match(/[\d.]+/g)?.map(Number) || [0, 0, 0, 0]
    const composite = (fg, bg) => {
      const alpha = fg[3] ?? 1
      return fg.slice(0, 3).map((c, i) => c * alpha + bg[i] * (1 - alpha))
    }
    const background = (element) => {
      const chain = []
      for (let node = element; node; node = node.parentElement) chain.unshift(node)
      return chain.reduce(
        (bg, node) => composite(rgb(getComputedStyle(node).backgroundColor), bg),
        [255, 255, 255],
      )
    }
    const luminance = (color) =>
      color
        .map((c) => c / 255)
        .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
        .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0)
    const failures = []
    let count = 0
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    while (walker.nextNode()) {
      const node = walker.currentNode
      const element = node.parentElement
      if (
        !node.textContent.trim() ||
        !element ||
        element.closest('script,style,option,.sr-only,:disabled')
      )
        continue
      if (!element.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue
      const style = getComputedStyle(element)
      const bg = background(element)
      const fg = composite(rgb(style.color), bg)
      const [a, b] = [luminance(fg), luminance(bg)].sort((a, b) => b - a)
      const ratio = (a + 0.05) / (b + 0.05)
      const large =
        parseFloat(style.fontSize) >= 24 ||
        (parseFloat(style.fontSize) >= 18.66 && Number(style.fontWeight) >= 700)
      count++
      if (ratio < (large ? 3 : 4.5))
        failures.push({
          text: node.textContent.trim().slice(0, 70),
          ratio: +ratio.toFixed(2),
          color: style.color,
          background: bg,
        })
    }
    return {
      text_nodes: count,
      failures,
      overflow: document.documentElement.scrollWidth > innerWidth,
    }
  })
  if (result.overflow || result.failures.length)
    throw new Error(`${scene}: ${JSON.stringify(result)}`)
  checks.push({ scene, ...result })
}

try {
  for (const [size, viewport] of [
    ['mobile', { width: 390, height: 844 }],
    ['desktop', { width: 1440, height: 1000 }],
  ]) {
    for (const choice of ['light', 'dark']) {
      const context = await browser.newContext({ viewport, colorScheme: choice })
      const page = await context.newPage()
      const errors = []
      page.on('pageerror', (error) => errors.push(error.message))
      // Real, explicitly dated bundled evidence; no live source/model writes.
      let releaseData
      const gate = new Promise((resolve) => {
        releaseData = resolve
      })
      await context.route('**/rest/v1/**', async (route) => {
        await gate
        await route.abort('failed')
      })
      await page.goto(base, { waitUntil: 'domcontentloaded' })
      await page.getByLabel('Colour theme').selectOption(choice)
      await page.getByText('Loading saved portfolio updates…').waitFor()
      await theme(page, choice)
      await audit(page, `${size}-${choice}-loading`)
      releaseData()
      await page.locator('.filing-card').first().waitFor()
      await page.getByRole('button', { name: /Alert settings/ }).click()
      await page.getByLabel('Daily price move threshold').fill('3')
      await page.getByLabel('Volume threshold').fill('1.5')
      await page.getByRole('button', { name: 'Custom', exact: true }).click()
      await audit(page, `${size}-${choice}-briefing-settings`)
      await page.getByRole('button', { name: '7 days', exact: true }).click()
      if (await page.locator('.routine-toggle').count())
        await page.locator('.routine-toggle').click()
      await audit(page, `${size}-${choice}-routine`)
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.screenshot({ path: `${output}/${size}-${choice}-top.png` })
      await page.screenshot({ path: `${output}/${size}-${choice}-briefing.png`, fullPage: true })

      await page
        .getByRole('navigation', { name: 'Main navigation' })
        .getByRole('link', { name: 'Portfolio' })
        .click()
      await theme(page, choice)
      await expect(page.getByLabel('Colour theme')).toHaveValue(choice)
      await expect(page.locator('.portfolio-card')).toHaveCount(15)
      const positive = page.locator('.portfolio-price .positive').first()
      const negative = page.locator('.portfolio-price .negative').first()
      if ((await positive.count()) && (await negative.count())) {
        if (
          (await positive.evaluate((e) => getComputedStyle(e).color)) ===
          (await negative.evaluate((e) => getComputedStyle(e).color))
        )
          throw new Error('Financial indicators lost their distinct colours.')
      }
      await audit(page, `${size}-${choice}-portfolio`)
      await page.screenshot({ path: `${output}/${size}-${choice}-portfolio.png`, fullPage: true })

      await page.goto(`${base}/?view=research&symbol=INFY`, { waitUntil: 'networkidle' })
      await page.locator('.answer-panel').waitFor()
      await audit(page, `${size}-${choice}-research`)
      await page.locator('.citation-button').first().click()
      await page.getByRole('dialog').waitFor()
      await audit(page, `${size}-${choice}-evidence`)
      await page.screenshot({ path: `${output}/${size}-${choice}-evidence.png` })
      await page.getByRole('button', { name: 'Close evidence' }).click()
      await page.screenshot({ path: `${output}/${size}-${choice}-research.png`, fullPage: true })
      // Simulated transport states only; no model/backend request is sent.
      let fail = false
      const cors = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
      }
      await page.route('**/research', (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          headers: cors,
          body: JSON.stringify({ job_id: 'theme-ui-test' }),
        }),
      )
      await page.route('**/jobs/theme-ui-test', (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          headers: cors,
          body: JSON.stringify(
            fail
              ? {
                  state: 'failed',
                  stage: 'failed',
                  error: 'Simulated source failure for theme verification.',
                }
              : { state: 'running', stage: 'analysis' },
          ),
        }),
      )
      await page.getByRole('button', { name: 'Investigate', exact: true }).click()
      await page.locator('.research-progress').waitFor()
      await audit(page, `${size}-${choice}-research-progress`)
      fail = true
      await page.getByRole('alert').waitFor({ timeout: 15000 })
      await audit(page, `${size}-${choice}-research-error`)
      await page.screenshot({ path: `${output}/${size}-${choice}-error.png`, fullPage: true })

      await page.goto(`${base}/?view=foundation`, { waitUntil: 'networkidle' })
      await page.route('**/health/live', (route) =>
        route.fulfill({ status: 503, headers: cors, body: 'Simulated failure' }),
      )
      await page.getByRole('button', { name: 'Check API connection' }).click()
      await page.getByText('API unavailable', { exact: true }).waitFor()
      await audit(page, `${size}-${choice}-foundation-error`)
      if (errors.length) throw new Error(errors.join('\n'))
      await context.close()
    }
  }

  // Preferences, OS changes and cross-tab updates use the real browser storage/media APIs.
  const context = await browser.newContext({
    viewport: { width: 320, height: 780 },
    colorScheme: 'dark',
  })
  await context.route('**/rest/v1/**', (route) => route.abort('failed'))
  const page = await context.newPage()
  await page.goto(base, { waitUntil: 'networkidle' })
  await theme(page, 'dark')
  await expect(page.getByLabel('Colour theme')).toHaveValue('system')
  await page.emulateMedia({ colorScheme: 'light' })
  await theme(page, 'light')
  await page.getByLabel('Colour theme').selectOption('dark')
  await theme(page, 'dark')
  await page.reload({ waitUntil: 'networkidle' })
  await theme(page, 'dark')
  await expect(page.getByLabel('Colour theme')).toHaveValue('dark')
  await audit(page, 'narrow-mobile-persisted-dark')
  const tab = await context.newPage()
  await tab.goto(`${base}/?view=foundation`, { waitUntil: 'networkidle' })
  await tab.getByLabel('Colour theme').selectOption('light')
  await theme(page, 'light')
  await expect(page.getByLabel('Colour theme')).toHaveValue('light')
  await tab.getByLabel('Colour theme').selectOption('system')
  await expect(page.getByLabel('Colour theme')).toHaveValue('system')
  await page.emulateMedia({ colorScheme: 'dark' })
  await theme(page, 'dark')
  await tab.evaluate(() => localStorage.removeItem('finn-theme'))
  await expect(page.getByLabel('Colour theme')).toHaveValue('system')
  await page.getByLabel('Colour theme').focus()
  await expect(page.locator('.theme-picker')).toHaveCSS('outline-style', 'solid')
  await context.close()
  checks.push({
    scene: 'preferences',
    default_system: true,
    live_os_changes: true,
    persistence: true,
    cross_tab: true,
    keyboard_focus: true,
    narrow_mobile: true,
  })

  // Hold the application bundle to inspect startup before React can correct anything.
  for (const [stored, os, expected] of [
    [null, 'dark', 'dark'],
    ['dark', 'light', 'dark'],
    ['light', 'dark', 'light'],
    ['system', 'dark', 'dark'],
    ['invalid', 'dark', 'dark'],
  ]) {
    const boot = await browser.newContext({ colorScheme: os })
    await boot.addInitScript((value) => {
      if (value === null) localStorage.removeItem('finn-theme')
      else localStorage.setItem('finn-theme', value)
    }, stored)
    let releaseBundle
    const gate = new Promise((resolve) => {
      releaseBundle = resolve
    })
    await boot.route('**/assets/*.js', async (route) => {
      await gate
      await route.abort('failed')
    })
    const page = await boot.newPage()
    await page.goto(base, { waitUntil: 'commit' })
    await theme(page, expected)
    const early = await page.evaluate(() => ({
      rootEmpty: document.querySelector('#root')?.childElementCount === 0,
      canvas: getComputedStyle(document.documentElement).getPropertyValue('--canvas').trim(),
      meta: document.querySelector('meta[name="theme-color"]').content,
    }))
    if (!early.rootEmpty || early.meta !== early.canvas)
      throw new Error(
        'Startup theme depends on the application bundle or has the wrong browser colour.',
      )
    checks.push({ scene: 'before-react', stored, os, expected, ...early })
    releaseBundle()
    await boot.close()
  }
  const blocked = await browser.newContext({ colorScheme: 'dark' })
  await blocked.addInitScript(() =>
    Object.defineProperty(window, 'localStorage', {
      get() {
        throw new DOMException('Blocked', 'SecurityError')
      },
    }),
  )
  const blockedPage = await blocked.newPage()
  await blockedPage.goto(`${base}/?view=foundation`, { waitUntil: 'networkidle' })
  await theme(blockedPage, 'dark')
  await blockedPage.getByLabel('Colour theme').selectOption('light')
  await theme(blockedPage, 'light')
  await blocked.close()
  checks.push({ scene: 'blocked-storage', system_default: true, session_switch: true })
  await writeFile(
    `${output}/checks.json`,
    JSON.stringify({ checked_at: new Date().toISOString(), base, checks }, null, 2),
  )
  console.log(
    `PASS: ${checks.length} theme scenes; Light/Dark/System, persisted/cross-tab preferences, startup, contrast and responsive states.`,
  )
} finally {
  await browser.close()
}
