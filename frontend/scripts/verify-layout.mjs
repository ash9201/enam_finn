// Shared-shell acceptance against saved real company data; no generation requests.
import { chromium, expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const output = fileURLToPath(new URL('../../artifacts/shared-layout/', import.meta.url))
await mkdir(output, { recursive: true })
const browser = await chromium.launch()
const checks = []
const savedReads = new Map()
let lastPage

async function geometry(page, mobile) {
  const result = await page.evaluate(() => {
    const view = document.querySelector('.app-view:not([hidden])').getBoundingClientRect()
    const header = document.querySelector('.app-header').getBoundingClientRect()
    const nav = document.querySelector('.mobile-navigation').getBoundingClientRect()
    return {
      top: view.top,
      bottom: view.bottom,
      headerBottom: header.bottom,
      navTop: nav.top,
      navBottom: nav.bottom,
      height: innerHeight,
      overflow: document.documentElement.scrollWidth > innerWidth,
    }
  })
  expect(result.overflow).toBe(false)
  expect(result.top).toBeGreaterThanOrEqual(result.headerBottom)
  if (mobile) {
    expect(result.bottom).toBeLessThanOrEqual(result.navTop)
    expect(result.navBottom).toBeLessThanOrEqual(result.height)
  }
  await expect(page.getByRole('main')).toHaveCount(1)
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toHaveCount(1)
}

try {
  for (const viewport of [
    { width: 390, height: 844 },
    { width: 1440, height: 1000 },
  ]) {
    for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({
        viewport,
        colorScheme: theme,
        reducedMotion: 'reduce',
      })
      const page = await context.newPage()
      lastPage = page
      const errors = []
      page.on('pageerror', (e) => errors.push(e.message))
      // A local-preview CORS relay for real read-only API requests. No facts are fabricated.
      await page.route('**/*', async (route) => {
        const request = route.request(),
          url = new URL(request.url())
        if (url.pathname.startsWith('/rest/v1/') && request.method() === 'GET') {
          if (!savedReads.has(url.href)) {
            const response = await route.fetch()
            savedReads.set(url.href, {
              status: response.status(),
              body: await response.body(),
              headers: response.headers(),
            })
          }
          return route.fulfill(savedReads.get(url.href))
        }
        if (
          url.hostname.endsWith('.onrender.com') &&
          /^\/(health|research|jobs|companies)(\/|$)/.test(url.pathname)
        ) {
          const cors = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,OPTIONS',
          }
          if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors })
          if (request.method() !== 'GET')
            throw new Error('Layout checks must not submit a model job')
          const response = await route.fetch()
          return route.fulfill({ response, headers: { ...response.headers(), ...cors } })
        }
        return route.continue()
      })
      const nav = (name) =>
        page
          .getByRole('navigation', { name: 'Main navigation' })
          .getByRole('link', { name, exact: true })
      const activeView = () => page.locator('.app-view:not([hidden])')
      await page.goto(base)
      await expect(page.getByRole('heading', { name: 'Your Briefing', exact: true })).toBeVisible()
      await expect(page.locator('.freshness')).toBeVisible({ timeout: 25000 })
      await expect(nav('Briefing')).toHaveAttribute('aria-current', 'page')
      await expect(page.locator('.briefing-stats')).toHaveCount(0)
      expect(
        await page.locator('.freshness').evaluate((el) => el.getBoundingClientRect().top),
      ).toBeLessThan(190)
      await geometry(page, viewport.width < 768)
      await page.getByRole('button', { name: 'Custom', exact: true }).click()
      await page.getByLabel('From (IST)').fill('2026-10-01T00:00')
      await page.getByLabel('To (IST)').fill('2026-10-31T23:59')
      await page.getByRole('button', { name: 'Alert settings', exact: true }).click()
      await page.getByRole('slider', { name: 'Daily price move threshold' }).fill('3')
      await page.getByRole('button', { name: 'Alert settings', exact: true }).click()
      await activeView().evaluate((el) => (el.scrollTop = 320))
      const briefingScroll = await activeView().evaluate((el) => el.scrollTop)

      await nav('Research').click()
      await expect(
        page.getByRole('heading', { name: 'Company Research', exact: true }),
      ).toBeVisible()
      await expect(page.locator('.answer-panel')).toBeVisible({ timeout: 25000 })
      const question = page.locator('.research-form textarea')
      const draft = 'Compare management statements without assuming a verdict.'
      await question.fill(draft)
      await activeView().evaluate((el) => (el.scrollTop = 480))
      const researchScroll = await activeView().evaluate((el) => el.scrollTop)
      await nav('Portfolio').click()
      await expect(page.locator('.portfolio-card')).toHaveCount(15, { timeout: 25000 })
      await expect(nav('Portfolio')).toHaveAttribute('aria-current', 'page')
      await nav('Research').click()
      await expect(question).toHaveValue(draft)
      expect(
        Math.abs((await activeView().evaluate((el) => el.scrollTop)) - researchScroll),
      ).toBeLessThan(3)
      await page.goBack()
      await expect(page.getByRole('heading', { name: 'Your Portfolio' })).toBeVisible()
      await page.goForward()
      await expect(question).toHaveValue(draft)
      await page.getByRole('main').getByRole('link', { name: 'System status', exact: true }).click()
      await expect(page.getByRole('heading', { name: 'System Status' })).toBeVisible()
      await expect(page.getByText('Connected', { exact: true })).toHaveCount(2, { timeout: 95000 })
      expect(await page.getByRole('main').innerText()).not.toMatch(
        /milestone|foundation|environment variables|apply.*SQL/i,
      )
      await page.getByRole('link', { name: 'Back to FINN' }).click()
      await expect(question).toHaveValue(draft)
      await nav('Briefing').click()
      expect(
        Math.abs((await activeView().evaluate((el) => el.scrollTop)) - briefingScroll),
      ).toBeLessThan(3)
      await expect(page.getByLabel('From (IST)')).toHaveValue('2026-10-01T00:00')
      await expect(page.getByRole('button', { name: 'Custom', exact: true })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      await page.getByRole('button', { name: 'Alert settings', exact: true }).click()
      await expect(page.getByRole('slider', { name: 'Daily price move threshold' })).toHaveValue('3')
      await page.getByRole('button', { name: 'Alert settings', exact: true }).click()
      await activeView().evaluate((el) => (el.scrollTop = 0))
      await page.screenshot({ path: `${output}/${viewport.width}-${theme}-briefing.png` })
      await nav('Portfolio').click()
      await page.locator('.portfolio-card a[href*="symbol=INFY"]').click()
      await expect(page.getByLabel('NSE ticker')).toHaveValue('INFY')
      await expect(question).not.toHaveValue(draft)
      // A deliberate company link must work even when its URL matches the old entry URL.
      await page.getByLabel('NSE ticker').fill('NTPC')
      await nav('Portfolio').click()
      await page.locator('.portfolio-card a[href*="symbol=INFY"]').click()
      await expect(page.getByLabel('NSE ticker')).toHaveValue('INFY')

      await page.goto(base + '/?view=research&analysis=results&symbol=NTPC')
      await expect(page.locator('.financial-results')).toHaveCount(1, { timeout: 25000 })
      await page.locator('.financial-bases button').filter({ hasText: 'Standalone' }).click()
      await expect(page.locator('button[aria-label^="Inspect standalone PBT for"]')).toHaveCount(3)
      await nav('Portfolio').click()
      await nav('Research').click()
      await expect(page.locator('.financial-results')).toHaveAttribute('data-basis', 'standalone')
      for (const ratio of [0, 0.5, 1]) {
        await activeView().evaluate(
          (el, n) => (el.scrollTop = n * (el.scrollHeight - el.clientHeight)),
          ratio,
        )
        await geometry(page, viewport.width < 768)
      }
      if (viewport.width === 390 && theme === 'light') {
        await page.locator('.financial-number').first().click()
        await expect(page.getByRole('dialog')).toBeVisible()
        await expect(page.getByRole('button', { name: 'Ask about this evidence' })).toBeEnabled({
          timeout: 20000,
        })
        await page.getByRole('button', { name: 'Ask about this evidence' }).click()
        await expect(page.getByLabel('Active evidence context')).toBeVisible()
        await nav('Portfolio').click()
        await nav('Research').click()
        await expect(page.getByLabel('Active evidence context')).toBeVisible()
        await page.getByRole('button', { name: 'Remove evidence context' }).click()
      }
      await activeView().evaluate((el) => (el.scrollTop = 0))
      await page.screenshot({ path: `${output}/${viewport.width}-${theme}-research.png` })
      await page.getByLabel('Colour theme').selectOption(theme === 'light' ? 'dark' : 'light')
      await expect(page.locator('html')).toHaveAttribute(
        'data-theme',
        theme === 'light' ? 'dark' : 'light',
      )
      await page.getByLabel('Colour theme').selectOption('system')
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await page.getByRole('link', { name: 'Skip to content' }).focus()
      await page.keyboard.press('Enter')
      await expect(page.getByRole('main')).toBeFocused()
      if (viewport.width === 390) {
        await page.setViewportSize({ width: 320, height: 740 })
        await geometry(page, true)
        await page.setViewportSize({ width: 844, height: 390 })
        await geometry(page, false)
      }
      expect(errors).toEqual([])
      checks.push({
        viewport,
        theme,
        navigation: true,
        history: true,
        drafts_filters_results_scroll_retained: true,
        company_links: true,
        status_return: true,
        content_unobscured: true,
        keyboard: true,
        page_errors: errors,
      })
      console.log(`PASS: ${viewport.width}px ${theme} shared layout`)
      await page.unrouteAll({ behavior: 'ignoreErrors' })
      await context.close()
    }
  }
  // One focused asynchronous-state check. Transport is simulated; the answer is
  // an unchanged real saved INFY response fetched in the matrix above.
  const answer = [...savedReads.values()]
    .map((r) => {
      try {
        return JSON.parse(r.body.toString())[0]?.result
      } catch {
        return null
      }
    })
    .find((result) => result?.symbol === 'INFY' && result.status === 'answered')
  expect(answer).toBeTruthy()
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const page = await context.newPage()
  lastPage = page
  let complete = false,
    fail = false
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  }
  await page.route('**/research', (route) =>
    route.fulfill({
      status: fail ? 503 : 202,
      headers: cors,
      json: fail
        ? { detail: 'Simulated service failure for navigation verification.' }
        : { job_id: 'layout-state-test', state: 'queued' },
    }),
  )
  await page.route('**/jobs/layout-state-test', (route) =>
    route.fulfill({
      headers: cors,
      json: complete
        ? { state: 'completed', stage: 'completed', result: answer }
        : { state: 'running', stage: 'analysis' },
    }),
  )
  const nav = (name) =>
    page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name, exact: true })
  await page.goto(base)
  await page.getByRole('button', { name: 'Alert settings', exact: true }).click()
  await page.getByRole('slider', { name: 'Daily price move threshold' }).fill('3.5')
  await nav('Portfolio').click()
  await page.getByRole('button', { name: 'Alert settings', exact: true }).click()
  await expect(page.getByRole('slider', { name: 'Daily price move threshold' })).toHaveValue('3.5')
  await page.getByRole('slider', { name: 'Daily price move threshold' }).fill('4.5')
  await nav('Briefing').click()
  await expect(page.getByRole('slider', { name: 'Daily price move threshold' })).toHaveValue('4.5')
  await nav('Research').click()
  await page.locator('.research-form textarea').fill(answer.question)
  await page.getByRole('button', { name: 'Investigate', exact: true }).click()
  await expect(page.locator('.research-progress')).toBeVisible()
  await nav('Portfolio').click()
  complete = true
  await nav('Research').click()
  await expect(page.locator('.research-progress')).toHaveCount(0, { timeout: 15000 })
  await expect(page.locator('.answer-panel')).toBeVisible()
  fail = true
  await page.getByRole('button', { name: 'Investigate', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Simulated service failure')
  expect(new URL(page.url()).searchParams.get('view')).toBe('research')
  await expect(page.getByRole('heading', { name: 'Company Research' })).toBeVisible()
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await context.close()
  checks.push({
    transport_simulated: true,
    real_saved_answer: true,
    in_flight_job_retained: true,
    errors_remain_on_page: true,
    shared_alert_preferences: true,
  })
} catch (error) {
  if (lastPage && !lastPage.isClosed()) {
    await lastPage.screenshot({ path: `${output}/failure.png` })
    await writeFile(`${output}/failure.html`, await lastPage.content())
  }
  throw error
} finally {
  for (const context of browser.contexts())
    for (const page of context.pages()) await page.unrouteAll({ behavior: 'ignoreErrors' })
  await browser.close()
  await writeFile(`${output}/checks.json`, JSON.stringify(checks, null, 2))
}
console.log(
  `PASS: ${checks.length} shared-layout scenes; responsive navigation, state/history, keyboard, themes, financial tables and evidence.`,
)
