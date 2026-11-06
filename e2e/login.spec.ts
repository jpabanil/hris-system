// Resolved from the frontend install so this file loads without its own node_modules.
import { expect, test } from '../frontend/node_modules/@playwright/test/index.js'

test('login shows the wordmark', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'HRIS' })).toBeVisible()
})
