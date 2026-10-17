import { defineConfig, devices } from '@playwright/test';

/**
 * Screenshots of the main pages for before/after comparison (.github/workflows/visual.yml).
 *
 * This config deliberately has NO webServer: the workflow serves two builds (base on :4174, branch on :4173)
 * and runs this same spec against each, so both sides use identical script, browser, fonts and data.
 *   VISUAL_BASE_URL  which build to shoot      (default http://localhost:4173)
 *   SHOTS_DIR        where the PNGs are written (default shots/local)
 */
export default defineConfig({
  testDir: './e2e-visual',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: process.env.VISUAL_BASE_URL ?? 'http://localhost:4173',
    bypassCSP: true, // this suite is about pixels; the CSP is covered by e2e-csp
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'], deviceScaleFactor: 1 } },
  ],
});
