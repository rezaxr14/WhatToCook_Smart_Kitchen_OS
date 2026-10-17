import { test, expect } from '../e2e/helpers';

/**
 * Route pages are lazy, content-hashed chunks. After a deploy a stale tab asks for a chunk name that no longer
 * exists; src/utils/chunkReload.ts reloads once instead of leaving a blank page. This runs against the
 * production build because only it has real hashed chunks.
 */
test('a failed lazy route chunk recovers with exactly one reload', async ({ page }) => {
  let chunkRequests = 0;
  await page.route(/\/assets\/RecipesPage-[A-Za-z0-9_-]+\.js$/, (route) => {
    chunkRequests += 1;
    return chunkRequests === 1 ? route.abort() : route.continue(); // first request fails, like a deleted chunk
  });

  await page.goto('/auth');
  await expect(page.locator('#root')).not.toBeEmpty();

  let reloads = 0;
  page.on('load', () => {
    reloads += 1;
  });
  await page.locator('a[href="/recipes"]').first().click(); // client-side navigation triggers the lazy import

  await expect.poll(() => chunkRequests, { timeout: 15_000 }).toBeGreaterThanOrEqual(2);
  await expect(page).toHaveURL(/\/recipes$/);
  await expect(page.getByRole('heading').first()).toBeVisible();
  expect(reloads).toBe(1);
});

test('a chunk that keeps failing does not cause a reload loop', async ({ page }) => {
  await page.route(/\/assets\/RecipesPage-[A-Za-z0-9_-]+\.js$/, (route) => route.abort());

  await page.goto('/auth');
  await expect(page.locator('#root')).not.toBeEmpty();

  let reloads = 0;
  page.on('load', () => {
    reloads += 1;
  });
  await page.locator('a[href="/recipes"]').first().click();
  await expect.poll(() => reloads, { timeout: 15_000 }).toBe(1); // one recovery attempt...
  await page.waitForTimeout(3_000); // ...a loop would reload again within moments; the cooldown must stop it
  expect(reloads).toBe(1);
});
