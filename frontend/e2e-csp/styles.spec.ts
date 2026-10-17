import { test, expect } from '../e2e/helpers';

/**
 * Tailwind 4 changed two preflight defaults that no class rename can restore, so src/index.css re-adds the
 * Tailwind 3 behaviour in @layer base. These run against the production build (the real compiled CSS).
 */
test.describe('Tailwind 4 preflight compat rules', () => {
  test('enabled buttons keep the pointer cursor', async ({ page }) => {
    await page.goto('/auth');
    const button = page.locator('button:visible:not([disabled])').first();
    await expect(button).toBeVisible();
    expect(await button.evaluate((el) => getComputedStyle(el).cursor)).toBe('pointer');
  });

  test('placeholders keep the gray-400 colour', async ({ page }) => {
    await page.goto('/auth');
    const input = page.locator('input[placeholder]:visible').first();
    await expect(input).toBeVisible();
    const { placeholder, expected } = await input.evaluate((el) => {
      // Resolve the theme token the same way the browser does, instead of hard-coding a colour syntax (oklch).
      const probe = document.createElement('div');
      probe.style.color = 'var(--color-gray-400)';
      document.body.appendChild(probe);
      const expected = getComputedStyle(probe).color;
      probe.remove();
      return { placeholder: getComputedStyle(el, '::placeholder').color, expected };
    });
    expect(placeholder).toBe(expected);
  });
});
