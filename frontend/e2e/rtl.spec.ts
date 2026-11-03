import { test, expect } from '@playwright/test';

/**
 * RTL smoke for the two right-to-left UI languages.
 *
 * Runs as its own projects (`rtl-fa`, `rtl-ar`) so the English suites keep
 * their language. The language is seeded in localStorage before the app boots,
 * which is how the real switcher persists it.
 */

const ROUTES = ['/', '/recipes', '/recipe/1', '/pantry', '/can-cook', '/ai-chef', '/auth'];

const languageFor = (project: string): 'fa' | 'ar' => (project === 'rtl-ar' ? 'ar' : 'fa');

test.beforeEach(async ({ page }, testInfo) => {
  const language = languageFor(testInfo.project.name);
  await page.addInitScript((lang) => {
    localStorage.setItem('whattocook_language_selected', lang);
    localStorage.setItem('language', lang);
  }, language);
});

test('the document declares the RTL language and direction', async ({ page }, testInfo) => {
  const language = languageFor(testInfo.project.name);
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.locator('html')).toHaveAttribute('lang', language);
});

for (const path of ROUTES) {
  test(`route ${path} stays inside the viewport in RTL`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#root')).not.toBeEmpty();

    // A physical margin/padding/position left behind usually shows up as the
    // page growing wider than the viewport once the document is RTL.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow, `${path} overflows horizontally in RTL`).toBeLessThanOrEqual(2);
  });
}

test('recipe display fields are localized', async ({ page }, testInfo) => {
  const language = languageFor(testInfo.project.name);
  await page.goto('/recipe/1');
  await page.waitForLoadState('networkidle');

  const heading = page.locator('h1').first();
  await expect(heading).toBeVisible();

  // Recipe id 1 (Grilled Cheese) has fa/ar translations, so the heading must be
  // the localized display name, not the canonical English one.
  await expect(heading).toHaveText(/[\u0600-\u06FF]/);
  await expect(heading).not.toHaveText(/Grilled Cheese/i);

  const sample = language === 'fa' ? 'پنیر' : 'جبن';
  await expect(heading).toContainText(sample);
});

test('free-text inputs follow the UI until text is typed', async ({ page }) => {
  await page.goto('/recipes');
  await page.waitForLoadState('networkidle');

  const input = page.locator('input[type="text"]').first();
  await expect(input).toBeVisible();

  // Empty: follow the RTL UI (a bare dir="auto" would resolve to LTR and put
  // the placeholder on the wrong side).
  await expect(input).toHaveCSS('direction', 'rtl');

  // Latin text: let the browser detect LTR.
  await input.fill('pasta');
  await expect(input).toHaveCSS('direction', 'ltr');

  // Persian/Arabic text: back to RTL.
  await input.fill('پنیر');
  await expect(input).toHaveCSS('direction', 'rtl');
});
