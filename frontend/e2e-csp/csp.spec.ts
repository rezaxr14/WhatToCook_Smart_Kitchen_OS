import { readFileSync } from 'node:fs';
import type { Page } from '@playwright/test';
import { test, expect } from '../e2e/helpers';

/**
 * The production build, served with the real CSP (nginx/csp-spa.conf), must run every main flow
 * without a single policy violation. Violations are collected two ways: the in-page
 * `securitypolicyviolation` event and Chromium's "Refused to ..." console errors.
 */

const csp = readFileSync(new URL('../nginx/csp-spa.conf', import.meta.url), 'utf8').match(
  /^add_header Content-Security-Policy "([^"]+)" always;$/m
)![1];

// 1x1 transparent PNG.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=',
  'base64'
);

let consoleViolations: string[] = [];

test.beforeEach(async ({ page }) => {
  consoleViolations = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' && /content security policy/i.test(msg.text())) {
      consoleViolations.push(msg.text());
    }
  });

  await page.addInitScript(() => {
    const w = window as unknown as { __cspViolations: string[] };
    w.__cspViolations = [];
    document.addEventListener('securitypolicyviolation', (e) => {
      w.__cspViolations.push(`${e.violatedDirective} <- ${e.blockedURI}`);
    });
  });

  // Third parties are stubbed so the suite is hermetic. The CSP is enforced by the browser *before*
  // any request is made, so a blocked host still reports a violation even though it is stubbed.
  await page.route('https://fonts.googleapis.com/**', (r) =>
    r.fulfill({ status: 200, contentType: 'text/css', body: '/* fonts stub */' })
  );
  await page.route('https://fonts.gstatic.com/**', (r) =>
    r.fulfill({ status: 200, contentType: 'font/woff2', body: '' })
  );
  await page.route('https://images.unsplash.com/**', (r) =>
    r.fulfill({ status: 200, contentType: 'image/png', headers: { 'access-control-allow-origin': '*' }, body: PNG })
  );
});

async function violations(page: Page): Promise<string[]> {
  const inPage = await page.evaluate(() => (window as unknown as { __cspViolations?: string[] }).__cspViolations ?? []);
  return [...inPage, ...consoleViolations];
}

test('the preview enforces the policy from nginx/csp-spa.conf', async ({ page }) => {
  const response = await page.goto('/');
  expect(response!.headers()['content-security-policy']).toBe(csp);
  expect(csp).toMatch(/script-src 'self'(;|$)/); // no 'unsafe-inline' / 'unsafe-eval' for scripts
  expect(csp).toContain("frame-ancestors 'none'");
});

test('landing page and the 3D journey run without violations', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText(/already have dinner/i);
  await expect(page.locator('canvas')).toBeVisible({ timeout: 30_000 });
  const loader = page.getByText(/Preparing your kitchen/i);
  if (await loader.isVisible()) await expect(loader).toBeHidden({ timeout: 20_000 });
  expect(await violations(page)).toEqual([]);
});

test('web fonts are activated without an inline onload handler', async ({ page }) => {
  await page.goto('/');
  const link = page.locator('link[data-async-style]');
  await expect(link).toHaveCount(1);
  await expect.poll(() => link.evaluate((el) => (el as HTMLLinkElement).media)).toBe('all');
  expect(await page.locator('[onload]').count()).toBe(0);
  expect(await violations(page)).toEqual([]);
});

// Deep links are loaded with page.goto (a full document request), which also guards the dev/preview proxy
// from swallowing SPA routes: Vite proxies by path *prefix*, and a bare '/ai' once hijacked '/ai-chef'.
const ROUTES = ['/recipes', '/recipe/1', '/can-cook', '/pantry', '/ai-chef', '/ai', '/aichef', '/auth', '/definitely-not-a-route'];

for (const path of ROUTES) {
  test(`route ${path} renders without violations`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#root')).not.toBeEmpty();
    expect(await violations(page)).toEqual([]);
  });
}

test.describe('fridge scanner', () => {
  const scanResponse = {
    status: 'success',
    detected_count: 2,
    detected_ingredients: [
      { name: 'Eggs', category: 'Dairy & Eggs', confidence: 0.95 },
      { name: 'Milk', category: 'Dairy & Eggs', confidence: 0.9 },
    ],
    auto_added: false,
    added_ingredients: [],
    pantry: null,
  };

  test.beforeEach(async ({ page }) => {
    await page.route('**/api/pantry/scan-image/', (route) => route.fulfill({ json: scanResponse }));
    await page.goto('/pantry');
    await page.getByRole('button', { name: /Scan Fridge Photo|Scan More/ }).first().click();
  });

  test('a sample photo is fetched cross-origin and scanned (connect-src + img-src)', async ({ page }) => {
    await page.getByAltText('Sample Fridge').click();
    await expect(page.getByText('Eggs').first()).toBeVisible({ timeout: 15_000 });
    expect(await violations(page)).toEqual([]);
  });

  test('an uploaded photo previews through a blob: URL (img-src blob:)', async ({ page }) => {
    await page.locator('input[type="file"]').first().setInputFiles({ name: 'fridge.png', mimeType: 'image/png', buffer: PNG });
    await expect(page.locator('img[src^="blob:"]')).toBeVisible();
    expect(await violations(page)).toEqual([]);
  });
});
