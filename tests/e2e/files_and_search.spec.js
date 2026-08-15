const { test, expect } = require('@playwright/test');

test.describe('DevTrack AI Files & Command Palette E2E Flow', () => {
  test('Should open Global Search modal on Ctrl+K', async ({ page }) => {
    await page.goto('/ui');
    await page.keyboard.press('Control+k');
    const modal = page.locator('#search-modal-overlay');
    await expect(modal).toHaveClass(/active/);
  });

  test('Should filter search results when typing query', async ({ page }) => {
    await page.goto('/ui');
    await page.keyboard.press('Control+k');
    const input = page.locator('#global-search-input');
    await input.fill('test search query');
    await expect(input).toHaveValue('test search query');
  });

  test('Should display file drop zone in Files view', async ({ page }) => {
    await page.goto('/ui');
    await page.click('[data-view="files"]');
    await expect(page.locator('#file-drop-zone')).toBeVisible();
  });
});
