// Real document-backed results. Live actions run once; subsequent scenes replay those exact answers.
import { chromium, expect } from '@playwright/test'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const api = process.env.FINN_RESEARCH_API_URL || 'https://finn-api-source-test.onrender.com'
const out = fileURLToPath(new URL('../../artifacts/research-redesign/', import.meta.url))
await mkdir(out, { recursive: true })
const fixtures = JSON.parse(await readFile(out + '/fixtures.json', 'utf8'))
for (const [key, answer] of Object.entries(fixtures))
  if (!key.endsWith('one-basis')) fixtures[answer.symbol + ':' + answer.question] = answer
const actions = {
  results:
    'Compare the latest reported quarterly Revenue, EBITDA, PBT and PAT with the previous quarter and year-ago quarter.',
  outlook: 'What did management say about demand and growth?',
  risks: 'What are the main risks discussed in the annual report?',
  comparison: 'Trace one earlier management statement against later earnings-call evidence.',
}
const browser = await chromium.launch()
const checks = []
let lastPage
async function selectCompany(page, symbol) {
  await page.getByRole('button', { name: 'Find company', exact: true }).click()
  const input = page.getByRole('combobox', { name: 'Find a company' })
  await input.fill(symbol)
  await page
    .getByRole('option')
    .filter({
      has: page.locator('small', {
        hasText: new RegExp('^' + symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$'),
      }),
    })
    .first()
    .click()
  await expect(page.getByLabel('Selected company')).toContainText(symbol)
}
async function audit(root) {
  const result = await root.evaluate((element) => {
    const rgb = (value) => value.match(/[\d.]+/g)?.map(Number) || [0, 0, 0, 0]
    const background = (element) => {
      for (let node = element; node; node = node.parentElement) {
        const v = rgb(getComputedStyle(node).backgroundColor)
        if (v[3] === undefined || v[3] >= 0.99) return v
      }
      return [255, 255, 255]
    }
    const lum = (c) =>
      c
        .slice(0, 3)
        .map((x) => x / 255)
        .map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4))
        .reduce((a, c, i) => a + c * [0.2126, 0.7152, 0.0722][i], 0)
    const bad = []
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT)
    while (walker.nextNode()) {
      const n = walker.currentNode,
        e = n.parentElement
      if (
        !n.textContent.trim() ||
        e.closest('.sr-only') ||
        !e.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) ||
        e.closest('option')
      )
        continue
      const s = getComputedStyle(e),
        [a, b] = [lum(rgb(s.color)), lum(background(e))].sort((a, b) => b - a)
      const large =
        parseFloat(s.fontSize) >= 24 ||
        (parseFloat(s.fontSize) >= 18.66 && Number(s.fontWeight) >= 700)
      if ((a + 0.05) / (b + 0.05) < (large ? 3 : 4.5))
        bad.push({ text: n.textContent.slice(0, 50), ratio: (a + 0.05) / (b + 0.05) })
    }
    return bad
  })
  expect(result).toEqual([])
}
try {
  for (const [theme, width] of [
    ['light', 1440],
    ['dark', 390],
    ['dark', 1440],
    ['light', 390],
  ]) {
    const context = await browser.newContext({
      viewport: { width, height: 900 },
      colorScheme: theme,
      reducedMotion: 'reduce',
    })
    const page = await context.newPage()
    lastPage = page
    const errors = []
    const requests = []
    let directoryRequests = 0
    let pageLoads = 1
    const live = process.env.FINN_VERIFY_LIVE_ACTIONS === '1' && width === 1440 && theme === 'light'
    page.on('pageerror', (error) => errors.push(error.message))
    page.on('request', (request) => {
      if (new URL(request.url()).pathname.endsWith('/company-directory.json')) directoryRequests++
    })
    await page.route('**/*', async (route) => {
      const request = route.request(),
        u = new URL(request.url())
      if (!/^\/(research|jobs|companies)(\/|$)/.test(u.pathname)) return route.continue()
      if (request.method() === 'OPTIONS')
        return route.fulfill({
          status: 204,
          headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
          },
        })
      if (u.pathname === '/research' && request.method() === 'POST') {
        const body = request.postDataJSON()
        requests.push(body)
        if (!live) {
          const answer = fixtures[body.symbol + ':' + body.question]
          if (!answer)
            throw new Error('Missing real recorded answer: ' + body.symbol + ' ' + body.question)
          return route.fulfill({
            json: { state: 'completed', job_id: answer.id, result: answer },
            headers: { 'Access-Control-Allow-Origin': '*' },
          })
        }
      }
      const response = await fetch(api + u.pathname + u.search, {
        method: request.method(),
        headers: { 'Content-Type': 'application/json' },
        body: request.postData() || undefined,
        signal: AbortSignal.timeout(110000),
      })
      const body = Buffer.from(await response.arrayBuffer())
      if (live) {
        try {
          const data = JSON.parse(body)
          if (data.state === 'completed' && data.result?.question)
            fixtures[data.result.symbol + ':' + data.result.question] = data.result
        } catch {}
      }
      const headers = {
        ...Object.fromEntries(response.headers),
        'Access-Control-Allow-Origin': '*',
      }
      delete headers['content-encoding']
      delete headers['content-length']
      return route.fulfill({ status: response.status, body, headers })
    })
    await page.goto(base + '/?view=research&symbol=NTPC&analysis=results')
    await expect(page.locator('.financial-results')).toHaveCount(1, { timeout: 30000 })
    const financial = fixtures['NTPC:results'].financial_results
    for (const basis of ['standalone', 'consolidated']) {
      await page
        .getByRole('button', {
          name: basis === 'standalone' ? 'Standalone' : 'Consolidated',
          exact: true,
        })
        .click()
      await expect(page.locator('.financial-results')).toHaveAttribute('data-basis', basis)
      await expect(page.getByRole('table', { name: basis + ' quarterly figures' })).toHaveCount(1)
      const expected = Number(
        financial.bases[basis].rows.find((row) => row.metric === 'Revenue').figures.latest
          .display_value,
      ).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      await expect(page.locator('.financial-number').first()).toContainText(expected)
    }
    await page.getByRole('button', { name: 'Standalone', exact: true }).click()
    await page.locator('[data-research-action="results"]').click()
    await expect(page.locator('.financial-results')).toHaveAttribute('data-basis', 'standalone')
    await expect(page.locator('.financial-results')).toHaveCount(1)
    await page.locator('.financial-number').first().click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(
      page.getByRole('dialog').getByRole('link', { name: /Open original document/ }),
    ).toHaveAttribute('href', /#page=\d+/)
    await page.getByRole('button', { name: /Ask about this evidence/ }).click()
    await expect(page.getByLabel('Active evidence context')).toContainText('NTPC')
    await page.getByRole('button', { name: 'Remove evidence context' }).click()
    await expect(page.getByLabel('Active evidence context')).toHaveCount(0)
    await page.getByRole('button', { name: 'Find company', exact: true }).click()
    const input = page.getByRole('combobox', { name: 'Find a company' })
    await input.fill('Jindal')
    await expect(page.getByRole('option').filter({ hasText: 'JINDALSTEL' })).toBeVisible()
    expect(await page.getByRole('option').count()).toBeGreaterThan(3)
    await input.press('Enter')
    await expect(
      page.getByRole('status').filter({ hasText: 'Select the intended company' }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Investigate', exact: true })).toBeDisabled()
    await input.fill('JINDALSTEEL')
    await input.press('ArrowDown')
    await input.press('Enter')
    await expect(page.getByLabel('Selected company')).toContainText('JINDALSTEL')
    expect(new URL(page.url()).searchParams.get('symbol')).toBe('JINDALSTEL')
    await selectCompany(page, 'SUNPHARMA')
    await page.locator('[data-research-action="results"]').click()
    await expect(page.locator('.financial-results')).toBeVisible({ timeout: 30000 })
    for (const basis of ['standalone', 'consolidated']) {
      await page
        .getByRole('button', {
          name: basis === 'standalone' ? 'Standalone' : 'Consolidated',
          exact: true,
        })
        .click()
      await expect(page.locator('.financial-results')).toHaveAttribute('data-basis', basis)
      await expect(page.getByRole('table', { name: basis + ' quarterly figures' })).toHaveCount(1)
      const value = fixtures['SUNPHARMA:results'].financial_results.bases[basis].rows.find(
        (row) => row.metric === 'Revenue',
      ).figures.latest.display_value
      await expect(page.locator('.financial-number').first()).toContainText(
        Number(value).toLocaleString('en-IN', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }),
      )
    }
    await page
      .getByLabel('Your question')
      .fill('Explain the main sources of demand for this company.')
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Briefing', exact: true })
      .click()
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Research', exact: true })
      .click()
    await expect(page.getByLabel('Selected company')).toContainText('SUNPHARMA')
    await expect(page.getByLabel('Your question')).toHaveValue(
      'Explain the main sources of demand for this company.',
    )
    await selectCompany(page, 'NTPC')
    await selectCompany(page, 'SUNPHARMA')
    await expect(page.getByLabel('Your question')).toHaveValue(
      'Explain the main sources of demand for this company.',
    )
    await expect(page.locator('.financial-results')).toHaveCount(1)
    if (width === 1440 && theme === 'light') {
      pageLoads++
      await page.reload()
      await expect(page.getByLabel('Selected company')).toContainText('SUNPHARMA')
      await expect(page.getByLabel('Your question')).toHaveValue(
        'Explain the main sources of demand for this company.',
      )
      await expect(page.locator('.financial-results')).toHaveCount(1, { timeout: 30000 })
    }
    await expect(
      page.getByRole('button', { name: /View all.*companies|Hide companies/ }),
    ).toHaveAttribute('aria-expanded', 'false')
    await page.getByRole('button', { name: /View all.*companies|Hide companies/ }).click()
    await expect(page.getByLabel('Watchlist companies').getByRole('button')).toHaveCount(15)
    await page
      .getByLabel('Watchlist companies')
      .getByRole('button')
      .filter({ has: page.locator('small', { hasText: /^CCL$/ }) })
      .click()
    for (const action of ['results', 'outlook', 'risks', 'comparison']) {
      await page.locator(`[data-research-action="${action}"]`).click()
      await expect(page.locator('.answer-question')).toHaveText(actions[action], {
        timeout: 180000,
      })
      await expect(page.locator('.research-progress')).toHaveCount(0, { timeout: 180000 })
      await expect(page.locator('.research-error')).toHaveCount(0)
      if (action === 'results') await expect(page.locator('.financial-results')).toHaveCount(1)
      if (action === 'comparison') {
        await expect(page.locator('.comparison-content')).toHaveCount(1)
        await expect(page.locator('.financial-results')).toHaveCount(0)
        await page.locator('.comparison-sides .citation-button').first().click()
        await expect(page.getByRole('dialog')).toBeVisible()
        await page.keyboard.press('Escape')
      }
    }
    expect(
      requests.filter(
        (body) => body.symbol === 'CCL' && [actions.outlook, actions.risks].includes(body.question),
      ).length,
    ).toBe(2)
    await expect(page.locator('.research-details')).not.toHaveAttribute('open', '')
    await audit(page.locator('.research-form'))
    await audit(page.locator('.answer-panel'))
    if ((width === 1440 && theme === 'light') || (width === 390 && theme === 'dark')) {
      await page.locator('.answer-panel').scrollIntoViewIfNeeded()
      await page.screenshot({ path: `${out}/${width}-${theme}-comparison.png` })
      await page.getByRole('button', { name: 'Find company', exact: true }).click()
      await page.getByRole('combobox', { name: 'Find a company' }).fill('Jindal')
      await page.screenshot({ path: `${out}/${width}-${theme}-search.png` })
      await page.keyboard.press('Escape')
    }
    if (width < 600) await page.setViewportSize({ width: 320, height: 740 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    expect(directoryRequests).toBeGreaterThanOrEqual(pageLoads)
    expect(directoryRequests).toBeLessThanOrEqual(pageLoads * 2) // persistent read + optional bundled fallback
    expect(errors).toEqual([])
    checks.push({
      theme,
      width,
      live_actions: live,
      financial_basis_switches: true,
      company_search: true,
      one_directory_fetch: true,
      preserved_workspace: true,
      evidence: true,
      all_four_actions: true,
    })
    console.log(`PASS ${width}px ${theme}; ${live ? 'live' : 'recorded real'} quick actions`)
    await page.unrouteAll({ behavior: 'ignoreErrors' })
    await context.close()
  }
  // Controlled latency/failure with genuine stored answers: no model requests.
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    colorScheme: 'dark',
    reducedMotion: 'reduce',
  })
  const page = await context.newPage()
  lastPage = page
  let defaultReturned = false,
    resultsReturned = false,
    refresh = false
  await page.route('**/*', async (route) => {
    const request = route.request(),
      u = new URL(request.url())
    if (u.pathname.endsWith('/rest/v1/finn_research_cache')) {
      const symbol = (u.searchParams.get('symbol') || '').replace(/^eq\./, '')
      const question = (u.searchParams.get('question') || '').replace(/^eq\./, '')
      let answer = null
      if (symbol === 'INFY') {
        if (question === actions.results) {
          answer = fixtures['INFY:results']
          resultsReturned = true
        } else if (question === 'Explain the core business and its main services or products.') {
          await new Promise((resolve) => setTimeout(resolve, 1800))
          answer = fixtures['INFY:overview']
          defaultReturned = true
        }
      } else if (symbol === 'NTPC' && question === actions.results)
        answer = fixtures['NTPC:one-basis']
      return route.fulfill({
        json: answer ? [{ result: answer, created_at: answer.generated_at }] : [],
        headers: { 'Access-Control-Allow-Origin': '*' },
      })
    }
    if (u.pathname === '/research' && request.method() === 'POST') {
      if (!refresh)
        throw new Error('Cached financial selection should not start an API/model request')
      await new Promise((resolve) => setTimeout(resolve, 600))
      return route.fulfill({
        status: 503,
        json: { detail: 'Controlled temporary source failure for the UI test.' },
        headers: { 'Access-Control-Allow-Origin': '*' },
      })
    }
    if (request.method() === 'OPTIONS' && u.pathname === '/research')
      return route.fulfill({
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Headers': 'Content-Type',
          'Access-Control-Allow-Methods': 'POST,OPTIONS',
        },
      })
    return route.continue()
  })
  await page.goto(base + '/?view=research&symbol=INFY')
  await expect.poll(() => resultsReturned).toBe(true)
  await page.locator('[data-research-action="results"]').click()
  await expect(page.locator('.financial-results')).toHaveCount(1)
  await page.getByRole('button', { name: 'Standalone', exact: true }).click()
  await expect.poll(() => defaultReturned).toBe(true)
  await expect(page.locator('.financial-results')).toHaveAttribute('data-basis', 'standalone')
  await expect(page.locator('.answer-question')).toHaveText(actions.results)
  refresh = true
  await page.getByRole('button', { name: /^Refresh sources/ }).click()
  await expect(page.locator('.research-progress')).toBeVisible()
  await expect(page.locator('.financial-results')).toHaveCount(1)
  await expect(page.getByRole('alert')).toContainText('Controlled temporary source failure')
  await expect(page.locator('.financial-results')).toHaveAttribute('data-basis', 'standalone')
  await page.goto(base + '/?view=research&symbol=NTPC&analysis=results')
  await expect(page.locator('.financial-results')).toHaveAttribute('data-basis', 'standalone')
  await expect(page.getByRole('group', { name: 'Accounting basis' })).toHaveCount(0)
  await expect(page.locator('.basis-availability')).toContainText('Consolidated')
  await expect(page.locator('.financial-results')).toHaveCount(1)
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await context.close()
  checks.push({
    guard_cases: 'late overview, failed refresh, real archived single basis',
    status: 'passed',
  })
  console.log(
    'PASS delayed overview, refresh failure, and real single-basis result; no model calls',
  )
} catch (error) {
  if (lastPage && !lastPage.isClosed()) await lastPage.screenshot({ path: out + '/failure.png' })
  throw error
} finally {
  for (const context of browser.contexts())
    for (const page of context.pages()) await page.unrouteAll({ behavior: 'ignoreErrors' })
  await browser.close()
  await writeFile(out + '/fixtures.json', JSON.stringify(fixtures, null, 2))
  await writeFile(out + '/checks.json', JSON.stringify(checks, null, 2))
}
