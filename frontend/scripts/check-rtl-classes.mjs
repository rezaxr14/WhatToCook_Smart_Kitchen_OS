#!/usr/bin/env node
/**
 * Guards the SPA against physical-direction Tailwind utilities.
 *
 * In an RTL UI `ml-4`, `pl-2`, `text-left`, `left-3`, `border-l`, ... stay
 * physically left/right and visibly break the layout. Use the logical
 * equivalents instead: `ms/me`, `ps/pe`, `text-start/end`, `start/end`,
 * `border-s/e`, `rounded-s/e`, `space-x` (avoid), and `rtl:rotate-180` for
 * direction icons.
 *
 * Intentional exceptions live in ALLOWED below: a mouse-following cursor and
 * the `left-1/2 -translate-x-1/2` centering idiom (centering is physical on
 * purpose and identical in both directions).
 *
 * Run: npm run check:rtl
 */
import { readdir, readFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', 'src');
const CLASS_ATTR =
  /className\s*=\s*(?:"([^"]*)"|'([^']*)'|`([^`]*)`|\{\s*`([^`]*)`\s*\})/g;
const PHYSICAL =
  /^-?(ml|mr|pl|pr|left|right|text-left|text-right|border-l|border-r|rounded-l|rounded-r|space-x)(-|$)/;
const ALLOWED = new Set([
  'left-1/2', // -- paired with -translate-x-1/2 to center
  'ml-[-3px]', // CustomCursor: follows the physical mouse position
  'mt-[-3px]',
  '-ml-5',
  '-mt-5',
]);

async function files(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await files(path)));
    else if (entry.name.endsWith('.tsx')) out.push(path);
  }
  return out;
}

const problems = [];
for (const file of await files(SRC)) {
  const text = await readFile(file, 'utf8');
  const lines = text.split('\n');
  for (const [index, line] of lines.entries()) {
    for (const match of line.matchAll(CLASS_ATTR)) {
      const value = match[1] ?? match[2] ?? match[3] ?? match[4] ?? '';
      for (const raw of value.split(/\s+/)) {
        if (!raw) continue;
        const token = raw.slice(raw.lastIndexOf(':') + 1);
        if (!PHYSICAL.test(token) || ALLOWED.has(token)) continue;
        problems.push(`${relative(SRC, file)}:${index + 1}: ${token}`);
      }
    }
  }
}

if (problems.length) {
  console.error('Physical direction utilities found — use logical ones (ms/me, ps/pe, start/end, text-start/end):');
  for (const problem of problems) console.error(`  ${problem}`);
  process.exit(1);
}
console.log('No physical direction utilities found.');
