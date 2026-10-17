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

export default defineConfig({
  plugins: [react()],
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
