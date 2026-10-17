import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import type { Page } from '@playwright/test';
import { test, expect } from '../e2e/helpers';

/**
 * One full-page screenshot per main page and viewport, written to $SHOTS_DIR/<viewport>-<page>.png.
 * Run against two builds and diffed by scripts/compare-screenshots.sh. Everything non-deterministic is pinned:
 * web fonts and remote images are stubbed, the WebGL canvas is masked, CSS motion is disabled.
 */
const OUT = process.env.SHOTS_DIR ?? 'shots/local';

// 8x8 flat tile standing in for every remote photo, so layout (not image content) is what gets compared.
const TILE = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAAIGNIUk0AAHomAACAhAAA+gAAAIDoAAB1MAAA6mAAADqYAAAXcJy6UTwAAAAGUExURcnDuf///13xQ7oAAAABYktHRAH/Ai3eAAAAB3RJTUUH6goREgs640TNeAAAAAtJREFUCNdjYEAFAAAQAAGhxSHBAAAAAElFTkSuQmCC', 'base64');

const PAGES: { name: string; path: string; fullPage?: boolean }[] = [
  { name: 'landing', path: '/', fullPage: false }, // scroll-driven 3D journey: first viewport only
  { name: 'recipes', path: '/recipes' },
  { name: 'recipe-detail', path: '/recipe/1' },
  { name: 'can-cook', path: '/can-cook' },
  { name: 'pantry', path: '/pantry' },
  { name: 'ai-chef', path: '/ai-chef' },
  { name: 'auth', path: '/auth' },
  { name: 'not-found', path: '/definitely-not-a-route' },
];

test.beforeAll(() => mkdirSync(OUT, { recursive: true }));

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.route('https://fonts.googleapis.com/**', (r) => r.fulfill({ status: 200, contentType: 'text/css', body: '/* stub */' }));
  await page.route('https://fonts.gstatic.com/**', (r) => r.fulfill({ status: 200, contentType: 'font/woff2', body: '' }));
  await page.route('https://images.unsplash.com/**', (r) =>
    r.fulfill({ status: 200, contentType: 'image/png', headers: { 'access-control-allow-origin': '*' }, body: TILE })
  );
});

async function settle(page: Page) {
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  const loader = page.getByText(/Preparing your kitchen/i);
  if (await loader.isVisible()) await expect(loader).toBeHidden({ timeout: 30_000 });
  await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}' });
  await page.waitForTimeout(1500); // let JS-driven entrance animations (framer-motion) finish
}

async function shoot(page: Page, project: string, name: string, fullPage: boolean) {
  await page.screenshot({
    path: join(OUT, `${project}-${name}.png`),
    fullPage,
    animations: 'disabled',
    caret: 'hide',
    mask: [page.locator('canvas')], // WebGL output is not pixel-stable
  });
}

for (const p of PAGES) {
  test(p.name, async ({ page }, testInfo) => {
    await page.goto(p.path);
    await settle(page);
    await shoot(page, testInfo.project.name, p.name, p.fullPage ?? true);
  });
}

test('pantry with the fridge scanner open', async ({ page }, testInfo) => {
  await page.goto('/pantry');
  await page.getByRole('button', { name: /Scan Fridge Photo|Scan More/ }).first().click();
  await expect(page.getByAltText('Sample Fridge')).toBeVisible();
  await settle(page);
  await shoot(page, testInfo.project.name, 'pantry-scanner', false);
});
