export async function chooseResearchCompany(page, symbol) {
  await page.getByRole('button', { name: 'Find company', exact: true }).click()
  await page.getByRole('combobox', { name: 'Find a company' }).fill(symbol)
  const escaped = symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  await page
    .getByRole('option')
    .filter({ has: page.locator('small', { hasText: new RegExp('^' + escaped + '$') }) })
    .first()
    .click()
}
