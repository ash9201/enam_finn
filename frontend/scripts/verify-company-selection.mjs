// Read-only company selection / methodology checks. No research jobs or model calls.
import { chromium, expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
const base = process.env.FINN_BROWSER_URL || 'http://127.0.0.1:4173'
const out = fileURLToPath(new URL('../../artifacts/company-resolution/', import.meta.url))
await mkdir(out, { recursive: true })
const browser = await chromium.launch(),
  checks = []
let lastPage
try {
  for (const [theme, width] of [
    ['light', 1440],
    ['dark', 390],
    ['dark', 1440],
    ['light', 390],
  ]) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, colorScheme: theme }),
      errors = []
    lastPage = page
    page.on('pageerror', (e) => errors.push(e.message))
    await page.route('**/research', (route) => {
      if (route.request().method() === 'POST')
        throw new Error('Company selection must not generate research')
      return route.continue()
    })
    await page.goto(base + '/?view=research&symbol=INFY')
    await expect(page.locator('.answer-panel')).toBeVisible({ timeout: 25000 })
    const questionBox = await page.getByLabel('Your question').boundingBox()
    const investigateBox = await page
      .getByRole('button', { name: 'Investigate', exact: true })
      .boundingBox()
    expect(Math.abs(investigateBox.x - questionBox.x)).toBeLessThan(2)
    expect(investigateBox.y).toBeGreaterThanOrEqual(questionBox.y + questionBox.height)
    const selected = page.getByLabel('Selected company'),
      find = page.getByRole('button', { name: 'Find company', exact: true })
    await expect(selected).toContainText('Infosys')
    const nameBox = await selected.locator('strong').boundingBox(),
      actionBox = await find.boundingBox()
    if (width > 600) expect(actionBox.x - nameBox.x - nameBox.width).toBeLessThan(40)
    expect(await page.locator('main').innerText()).not.toContain(
      'Any NSE company with accessible primary documents',
    )
    await find.click()
    const input = page.getByRole('combobox', { name: 'Find a company' }),
      options = page.locator('.company-suggestions [role="option"]')
    for (const [query, symbol] of [
      ['Infosys', 'INFY'],
      ['infsys', 'INFY'],
      ['HUL', 'HINDUNILVR'],
      ['M and M', 'M&M'],
    ]) {
      await input.fill(query)
      await expect(options.first()).toContainText(symbol)
    }
    await input.fill('companythatdoesnotexist12345')
    await expect(page.getByText('No matching listing found.', { exact: false })).toBeVisible()
    await input.fill('Jindal')
    await input.press('Enter')
    await expect(
      page.getByRole('status').filter({ hasText: 'Select the intended company' }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Investigate', exact: true })).toBeDisabled()
    await input.fill('TCS')
    await input.press('ArrowDown')
    await input.press('Enter')
    await expect(selected).toContainText('TCS')
    await page.getByRole('button', { name: 'View all 15 companies', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Hide companies', exact: true })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    await expect(page.getByLabel('Watchlist companies').getByRole('button')).toHaveCount(15)
    await page
      .getByLabel('Watchlist companies')
      .getByRole('button')
      .filter({ has: page.locator('small', { hasText: /^INFY$/ }) })
      .click()
    await expect(selected).toContainText('INFY')
    await find.click()
    await expect(page.getByLabel('Recent companies')).toContainText('TCS')
    await expect(page.locator('.directory-details')).not.toHaveAttribute('open', '')
    await page.locator('.directory-details summary').click()
    await expect(page.locator('.directory-details')).toContainText('Official NSE snapshot checked')
    expect(await page.locator('.directory-details a').count()).toBeGreaterThan(0)
    await page.getByRole('button', { name: 'Cancel', exact: true }).click()
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Portfolio', exact: true })
      .click()
    await expect(page.locator('.portfolio-row')).toHaveCount(15)
    await page.locator('.portfolio-row[data-symbol="INFY"] button').click()
    await expect(page.locator('.portfolio-detail')).not.toContainText(
      'Unadjusted closes; split-affected daily comparison suppressed',
    )
    await expect(page.locator('.portfolio-detail')).not.toContainText('Unadjusted closes.')
    await page.locator('.portfolio-method summary').click()
    await expect(page.locator('.portfolio-method')).toContainText('Prices use unadjusted closes')
    await expect(page.locator('.portfolio-method')).toContainText(
      'comparisons are withheld when a split affects',
    )
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    expect(errors).toEqual([])
    if ((width === 1440 && theme === 'light') || (width === 390 && theme === 'dark')) {
      await page
        .getByRole('navigation', { name: 'Main navigation' })
        .getByRole('link', { name: 'Research', exact: true })
        .click()
      await page.screenshot({ path: `${out}/${width}-${theme}-selection.png` })
    }
    checks.push({
      theme,
      width,
      name_symbol_alias_typo_and_ambiguity: true,
      new_company: 'TCS',
      watchlist_labels_and_recents: true,
      secondary_provenance: true,
      shared_methodology: true,
      model_calls: 0,
      errors,
    })
    await page.close()
  }
  // Explicit browser-only reference-store outage; bundled official identities remain usable.
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, colorScheme: 'dark' })
  lastPage = page
  await page.route('**/storage/v1/object/public/finn-reference/company-directory.json', (route) =>
    route.fulfill({ status: 403, body: 'reference access unavailable' }),
  )
  await page.goto(base + '/?view=research&symbol=INFY')
  await page.getByRole('button', { name: 'Find company', exact: true }).click()
  await page.getByRole('combobox', { name: 'Find a company' }).fill('TCS')
  await expect(page.locator('.company-suggestions [role="option"]').first()).toContainText('TCS')
  await page.getByRole('combobox', { name: 'Find a company' }).press('Escape')
  await expect(page.getByLabel('Selected company')).toContainText('INFY')
  checks.push({
    scenario: 'public reference HTTP 403',
    verified_bundled_search: true,
    known_identity_preserved: true,
  })
  await page.close()
  await writeFile(
    `${out}/checks.json`,
    JSON.stringify({ checked_at: new Date().toISOString(), checks }, null, 2),
  )
  console.log(
    'PASS: four theme/viewport selection and methodology scenes, plus persistent-reference 403 fallback; no model calls.',
  )
} catch (error) {
  if (lastPage && !lastPage.isClosed()) await lastPage.screenshot({ path: `${out}/failure.png` })
  throw error
} finally {
  await browser.close()
}
