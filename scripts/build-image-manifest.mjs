#!/usr/bin/env node
/**
 * Generates `GetFood/data/image-manifest.json` from the photos committed under
 * `media/`. The manifest maps the logical catalog path (`dishes/risotto.webp`)
 * to the content-hashed file on disk (`dishes/risotto.6ffa9ed3.webp`).
 *
 * The dish catalog is the source of truth for which hashed copy is current; a
 * catalog file always wins over a legacy fixed-path copy with the same name.
 * Run `node scripts/build-image-manifest.mjs` after changing the photo set.
 */
import { access, readdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const MEDIA = join(ROOT, 'media');
const catalog = JSON.parse(await readFile(join(ROOT, 'dish-catalog.json'), 'utf8'));

const catalogFiles = new Set();
for (const dish of catalog.dishes ?? []) {
  for (const file of dish.files ?? []) {
    if (!file?.file) continue;
    catalogFiles.add(file.file);
    try {
      await access(join(MEDIA, file.file));
    } catch {
      throw new Error(`dish-catalog.json references a missing photo: ${file.file}`);
    }
  }
}

const manifest = {};
for (const folder of ['dishes', 'ingredients', 'recipes']) {
  const names = await readdir(join(MEDIA, folder)).catch(() => []);
  const entries = names.map((name) => {
    const match = /^(.*)\.([0-9a-f]{8})\.([a-z0-9]+)$/i.exec(name);
    return { name, match, logical: match ? `${match[1]}.${match[3]}` : name };
  });

  const byLogical = new Map();
  for (const entry of entries) {
    const list = byLogical.get(entry.logical) ?? [];
    list.push(entry);
    byLogical.set(entry.logical, list);
  }

  for (const [logical, candidates] of byLogical) {
    const hashed = candidates.filter((entry) => entry.match);
    const fromCatalog = candidates.find((entry) => catalogFiles.has(`${folder}/${entry.name}`));
    const chosen =
      fromCatalog ??
      (hashed.length === 1
        ? hashed[0]
        : hashed.length > 1
          ? [...hashed].sort((a, b) => a.name.localeCompare(b.name))[0]
          : candidates[0]);
    manifest[`${folder}/${logical}`] = `${folder}/${chosen.name}`;
  }
}

const out = join(ROOT, 'GetFood', 'data', 'image-manifest.json');
await writeFile(out, JSON.stringify(manifest, null, 2) + '\n');
console.log(`wrote ${Object.keys(manifest).length} image aliases to ${relative(ROOT, out)}`);
