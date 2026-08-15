const { test, expect } = require('@playwright/test');

test.describe('DevTrack AI Auth & Navigation E2E Flow', () => {
  test('Should load web application UI', async ({ page }) => {
    await page.goto('/ui');
    await expect(page).toHaveTitle(/DevTrack AI/i);
  });

  test('Should display sidebar view navigation items', async ({ page }) => {
    await page.goto('/ui');
    const sidebar = page.locator('.sidebar');
    await expect(sidebar).toBeVisible();
    
    // Check navigation buttons
    await expect(page.locator('[data-view="projects"]')).toBeVisible();
    await expect(page.locator('[data-view="issues"]')).toBeVisible();
    await expect(page.locator('[data-view="analytics"]')).toBeVisible();
    await expect(page.locator('[data-view="files"]')).toBeVisible();
  });

  test('Should toggle sidebar view panels when clicked', async ({ page }) => {
    await page.goto('/ui');

    // Click Analytics view
    await page.click('[data-view="analytics"]');
    await expect(page.locator('#view-analytics')).toBeVisible();

    // Click Files view
    await page.click('[data-view="files"]');
    await expect(page.locator('#view-files')).toBeVisible();
  });
});
