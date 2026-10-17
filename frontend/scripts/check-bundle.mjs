#!/usr/bin/env node
/**
 * Bundle budget check - run after `npm run build` (`npm run check:bundle`, also in ci.yml).
 *
 * Why it exists: one stray `import * as THREE from 'three'` in an eagerly loaded module once put ~360 kB of
 * three.js into the entry chunk of every route, while the 3D scene itself was (correctly) lazy. The only symptom
 * was a Vite size warning that was easy to wave away. This turns it into a hard failure.
 *
 * The *initial graph* is exactly what `dist/index.html` loads up front: the entry <script> plus every
 * <link rel="modulepreload">. Lazy route chunks and the lazy 3D scene are not part of it.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const KB = 1000; // Vite reports sizes in kB = 1000 bytes
const BUDGET = {
  // Measured 185 kB on 2026-10-17 (was 313 kB for the entry chunk alone before route splitting).
  initialGzipKb: 220,
  // Any single chunk, minified. Largest non-3D chunk today: ~208 kB.
  chunkRawKb: 300,
  // Documented exception: three.js + r3f + postprocessing, loaded only by the lazy landing-page scene
  // (~920 kB today). Raise deliberately, never by accident.
  perChunkRawKb: { 'vendor-three': 1000 },
};
// Strings that only exist in the three.js renderer bundle (they survive minification in warning messages).
const THREE_MARKER = 'WebGLRenderer';
const FORBIDDEN_INITIAL = /^(vendor-three|JourneyScene)$/;

const dist = fileURLToPath(new URL('../dist/', import.meta.url));
const assets = join(dist, 'assets');
const chunkName = (file) => file.replace(/\.js$/, '').replace(/-[A-Za-z0-9_-]{8}$/, '');
const read = (file) => readFileSync(join(assets, file));
const kb = (n) => (n / KB).toFixed(1).padStart(7);

let html;
try {
  html = readFileSync(join(dist, 'index.html'), 'utf8');
} catch {
  console.error('dist/index.html not found - run `npm run build` first.');
  process.exit(2);
}

const initial = [...new Set([...html.matchAll(/(?:src|href)="\/assets\/([^"]+\.js)"/g)].map((m) => m[1]))];
if (initial.length === 0) {
  console.error('Could not find the entry script in dist/index.html.');
  process.exit(2);
}

const problems = [];

console.log('Initial graph (downloaded by every first visit):');
let initialGzip = 0;
for (const file of initial) {
  const buf = read(file);
  const gz = gzipSync(buf, { level: 9 }).length;
  initialGzip += gz;
  console.log(`  ${file.padEnd(40)} ${kb(buf.length)} kB   gz ${kb(gz)} kB`);
  if (FORBIDDEN_INITIAL.test(chunkName(file))) problems.push(`${file}: the lazy 3D scene/vendor chunk is in the initial graph`);
  if (buf.includes(THREE_MARKER)) {
    problems.push(`${file}: contains three.js (${THREE_MARKER}); something eagerly imports 'three' (grep: from 'three')`);
  }
}
console.log(`  ${'TOTAL'.padEnd(40)} ${' '.repeat(7)}      gz ${kb(initialGzip)} kB  (budget ${BUDGET.initialGzipKb} kB)`);
if (initialGzip > BUDGET.initialGzipKb * KB) {
  problems.push(`initial graph is ${(initialGzip / KB).toFixed(1)} kB gzipped, over the ${BUDGET.initialGzipKb} kB budget`);
}

console.log('\nAll chunks:');
for (const file of readdirSync(assets).filter((f) => f.endsWith('.js')).sort()) {
  const size = read(file).length;
  const name = chunkName(file);
  const limit = BUDGET.perChunkRawKb[name] ?? BUDGET.chunkRawKb;
  const over = size > limit * KB;
  console.log(`  ${file.padEnd(40)} ${kb(size)} kB   limit ${String(limit).padStart(4)} kB${over ? '   <-- OVER' : ''}`);
  if (over) problems.push(`${file}: ${(size / KB).toFixed(1)} kB exceeds its ${limit} kB budget`);
}

if (problems.length) {
  console.error(`\nBundle budget FAILED (${problems.length}):`);
  for (const p of problems) console.error(`  - ${p}`);
  console.error('\nIf the growth is intended, raise the budget in scripts/check-bundle.mjs in the same PR and say why.');
  process.exit(1);
}
console.log('\nBundle budget OK.');
