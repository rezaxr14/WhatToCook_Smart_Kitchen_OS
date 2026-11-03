import { test, expect, langSelectedInitScript } from './helpers';

/**
 * Image tiers, end to end:
 *
 *   1. the local `/media/...` file exists            → use it
 *   2. it is missing, `image_fallback` (Supabase) works → use the fallback
 *   3. both are missing / blocked                     → bundled placeholder
 *
 * The API is mocked so the test does not depend on seeded rows, and the
 * Supabase host is fulfilled locally so the suite stays offline-safe.
 */

const SUPABASE_HOST = 'lderdvhteofqemiivosz.supabase.co';
const FALLBACK = `https://${SUPABASE_HOST}/storage/v1/object/public/dish-images/missing-dish.webp`;

// 1×1 transparent PNG.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64'
);

const recipe = (overrides: Record<string, unknown> = {}) => ({
  id: 901,
  name: 'Tier Test Dish',
  description: 'Only exists to exercise the image fallback chain.',
  instructions: 'None.',
  cooking_time: 10,
  servings: 1,
  category: 'Dinner',
  difficulty: 'Easy',
  ingredients: [],
  image: '/media/dishes/tier-test-missing.webp',
  ...overrides,
});

async function mockRecipes(page: import('@playwright/test').Page, recipes: unknown[]) {
  await page.route('**/api/recipes/', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(recipes) })
  );
}

const cardImage = (page: import('@playwright/test').Page) =>
  page.locator('a[href="/recipe/901"] img').first();

test.beforeEach(async ({ page }) => {
  await page.addInitScript(langSelectedInitScript);
});

test('a missing local photo falls back to the Supabase copy', async ({ page }) => {
  await mockRecipes(page, [recipe({ image_fallback: FALLBACK })]);
  await page.route(`https://${SUPABASE_HOST}/**`, (route) =>
    route.fulfill({ status: 200, contentType: 'image/png', body: PNG })
  );

  await page.goto('/recipes');
  const image = cardImage(page);
  await expect(image).toHaveAttribute('src', FALLBACK);
  await expect.poll(() => image.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
});

test('when the local photo and the fallback both fail, the bundled placeholder wins', async ({ page }) => {
  await mockRecipes(page, [recipe({ image_fallback: FALLBACK })]);
  // Simulate an unreachable Supabase (bucket not deployed yet, offline CI).
  await page.route(`https://${SUPABASE_HOST}/**`, (route) => route.abort());

  await page.goto('/recipes');
  const image = cardImage(page);
  await expect(image).toHaveAttribute('src', '/placeholder.svg');
  await expect.poll(() => image.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
});

test('blocking every third-party host still leaves zero broken images on the page', async ({ page }) => {
  const recipes = [
    recipe({ image_fallback: FALLBACK }),
    recipe({
      id: 902,
      name: 'Tier Test Dish Without Fallback',
      image: '/media/dishes/also-missing.webp',
      image_fallback: null,
    }),
  ];
  // One handler: Playwright matches routes from the last registered backwards,
  // so a catch-all added after the API mock would shadow it.
  await page.route('**/*', (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/recipes/') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(recipes),
      });
    }
    if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') return route.continue();
    return route.abort();
  });

  await page.goto('/recipes');
  await page.waitForLoadState('networkidle');

  // Let SafeImage walk every stage (local → fallback → placeholder).
  await expect
    .poll(async () =>
      page.locator('img').evaluateAll((images: HTMLImageElement[]) =>
        images.filter((img) => img.complete && img.naturalWidth > 0).length
      )
    )
    .toBeGreaterThan(0);

  const broken = await page.locator('img').evaluateAll((images: HTMLImageElement[]) =>
    images
      .filter((img) => img.getBoundingClientRect().width > 0)
      .filter((img) => !img.complete || img.naturalWidth === 0)
      .map((img) => img.currentSrc || img.src)
  );
  expect(broken).toEqual([]);
});
