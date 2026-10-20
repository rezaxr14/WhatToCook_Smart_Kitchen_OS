import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendTarget = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';

// Same-origin backend routes (nginx does this in production, see nginx.conf). Vite matches proxy keys as
// string *prefixes*: a bare '/ai' also swallowed the SPA route /ai-chef (hard refresh -> Django 404), and the
// backend has no root-level /ai/ route anyway, so it is not proxied.
const proxy = Object.fromEntries(
  ['/api', '/media', '/legacy'].map((path) => [
    path,
    { target: backendTarget, changeOrigin: true, secure: false },
  ])
);

/**
 * The SPA's production Content-Security-Policy, read from the nginx snippet so `vite preview` (used by
 * `npm run test:e2e:csp`) enforces exactly what nginx sends. Fails loudly if the snippet changes shape.
 */
function spaCsp(): string {
  const conf = readFileSync(new URL('./nginx/csp-spa.conf', import.meta.url), 'utf8');
  const match = conf.match(/^add_header Content-Security-Policy "([^"]+)" always;$/m);
  if (!match) {
    throw new Error('nginx/csp-spa.conf must contain a single `add_header Content-Security-Policy "..." always;` line');
  }
  return match[1];
}

// Stable vendor chunks: libraries change far less often than app code, so splitting them keeps them cached across
// deploys. three & friends only ever load with the lazy 3D scene (never in the entry graph, see
// scripts/check-bundle.mjs), so they get their own chunk.
const THREE_PACKAGES = new Set(['three', 'postprocessing', 'react-reconciler', 'its-fine', 'react-use-measure', 'three-stdlib']);

function manualChunks(id: string): string | undefined {
  const pkg = id.match(/node_modules\/((?:@[^/]+\/)?[^/]+)/)?.[1];
  if (!pkg) return undefined;
  if (THREE_PACKAGES.has(pkg) || pkg.startsWith('@react-three/')) return 'vendor-three';
  if (['react', 'react-dom', 'scheduler', 'react-router', 'cookie', 'set-cookie-parser'].includes(pkg)) return 'vendor-react';
  if (['framer-motion', 'motion-dom', 'motion-utils'].includes(pkg)) return 'vendor-motion';
  if (pkg.includes('i18next')) return 'vendor-i18n';
  if (pkg.startsWith('@tanstack/')) return 'vendor-query';
  return undefined;
}

export default defineConfig({
  plugins: [react()],
  build: {
    // Matches the documented budget for the lazy 3D vendor chunk (the largest legitimate chunk). Everything else
    // is held to a much tighter limit by `npm run check:bundle`, which CI runs after the build.
    chunkSizeWarningLimit: 1000,
    rollupOptions: { output: { manualChunks } },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    proxy,
  },
  preview: {
    port: 4173,
    proxy,
    headers: { 'Content-Security-Policy': spaCsp() },
  },
});
