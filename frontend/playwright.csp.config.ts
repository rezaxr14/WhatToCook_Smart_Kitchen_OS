import { defineConfig, devices } from '@playwright/test';

/**
 * Runs the SPA's *production build* under the exact Content-Security-Policy nginx sends
 * (read from nginx/csp-spa.conf by vite.config.ts). The regular e2e suite uses the Vite dev server,
 * which has no CSP and injects inline scripts, so it cannot catch a policy that breaks the app.
 *
 * Needs the Django API on :8000 (same as the regular suite). Run: npm run test:e2e:csp
 */
export default defineConfig({
  testDir: './e2e-csp',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:4173',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium-csp', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run build && npx vite preview --port 4173 --strictPort',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 180 * 1000,
  },
});
