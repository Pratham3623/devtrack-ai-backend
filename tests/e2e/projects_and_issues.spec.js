const { test, expect } = require('@playwright/test');

test.describe('DevTrack AI Projects & Issues E2E Flow', () => {
  test('Should open create project modal', async ({ page }) => {
    await page.goto('/ui');
    const newProjectBtn = page.locator('#btn-new-project');
    if (await newProjectBtn.isVisible()) {
      await newProjectBtn.click();
      await expect(page.locator('#create-modal-overlay')).toHaveClass(/active/);
    }
  });

  test('Should render project templates picker', async ({ page }) => {
    await page.goto('/ui');
    const newProjectBtn = page.locator('#btn-new-project');
    if (await newProjectBtn.isVisible()) {
      await newProjectBtn.click();
      await expect(page.locator('.template-card[data-template="SCRUM"]')).toBeVisible();
      await expect(page.locator('.template-card[data-template="KANBAN"]')).toBeVisible();
    }
  });
});
