import { expect, test } from '@playwright/test'

test('connects to FastAPI and navigates documentation', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await expect(page.getByText('API connected')).toBeVisible()
  await page.getByRole('link', { name: 'Methodology', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Evidence before interpretation.' })).toBeVisible()
  await page.goto('/')
  await page.screenshot({ path: '../.artifacts/foundation-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByText('API connected')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: '../.artifacts/foundation-mobile.png', fullPage: true })
  expect(errors).toEqual([])
})

test('shows a real API failure and allows retry', async ({ page }) => {
  await page.route('**/api/v1/health', route => route.fulfill({ status: 503, body: '{}' }))
  await page.goto('/')
  await expect(page.getByText('API unavailable')).toBeVisible()
  await page.unroute('**/api/v1/health')
  await page.getByRole('button', { name: 'Retry connection' }).click()
  await expect(page.getByText('API connected')).toBeVisible()
})