/**
 * Dish photo helpers for AI-generated ideas.
 *
 * Everything here is served from the locally bundled `/media/` set: the
 * deployment cannot reach Unsplash and the SPA CSP only allows `'self'` (plus
 * the Supabase fallback host). The API usually supplies a resolved `image`;
 * these helpers only cover a missing or duplicated one.
 */

const DISH_PHOTO_MAP: Record<string, string> = {
  // Desserts & sweets
  ice_cream: '/media/recipes/affogato.jpg',
  gelato: '/media/recipes/affogato.jpg',
  cheesecake: '/media/dishes/chocolate.12bef7db.webp',
  cake: '/media/dishes/chocolate.12bef7db.webp',
  tiramisu: '/media/dishes/chocolate.12bef7db.webp',
  crepe: '/media/recipes/banana_crepes.jpg',
  waffle: '/media/recipes/pancakes.jpg',
  pancake: '/media/recipes/pancakes.jpg',

  // Sandwiches & melts
  grilled_cheese: '/media/recipes/grilled_cheese.jpg',
  sandwich: '/media/recipes/grilled_cheese.jpg',
  burger: '/media/dishes/beef.d26da077.webp',
  toast: '/media/recipes/avocado_toast.jpg',

  // Eggs & breakfast
  omelette: '/media/recipes/omelette.jpg',
  shakshuka: '/media/recipes/shakshuka.jpg',
  eggs: '/media/recipes/omelette.jpg',

  // Pasta & pizza
  pasta: '/media/dishes/spaghetti.78861a40.webp',
  spaghetti: '/media/dishes/spaghetti.78861a40.webp',
  carbonara: '/media/recipes/carbonara.jpg',
  pizza: '/media/dishes/pastitsio.caf30ef0.webp',
  risotto: '/media/dishes/risotto.6ffa9ed3.webp',

  // Poultry, meat & seafood
  chicken: '/media/recipes/chicken_skillet.jpg',
  steak: '/media/dishes/beef.d26da077.webp',
  beef: '/media/dishes/beef.d26da077.webp',
  salmon: '/media/dishes/hamsi.702db228.webp',
  shrimp: '/media/recipes/garlic_shrimp.jpg',
  stew: '/media/dishes/ghormeh-sabzi.cacaffc6.webp',
  curry: '/media/dishes/stir_fry.49bf429b.webp',

  // Asian, bowls & salads
  rice: '/media/recipes/garlic_fried_rice.jpg',
  ramen: '/media/dishes/stir_fry.49bf429b.webp',
  noodles: '/media/dishes/stir_fry.49bf429b.webp',
  taco: '/media/dishes/fish_tacos.bf2e5862.webp',
  salad: '/media/dishes/greek_salad.1415cf1d.webp',
  soup: '/media/dishes/lentil_soup.8fa7b7f6.webp',
};

const DEFAULT_GOURMET_PHOTOS = [
  '/media/recipes/carbonara.jpg',
  '/media/dishes/grilled.d1de580f.webp',
  '/media/dishes/beef.d26da077.webp',
  '/media/dishes/greek_salad.1415cf1d.webp',
  '/media/dishes/stir_fry.49bf429b.webp',
  '/media/dishes/lentil_soup.8fa7b7f6.webp',
  '/media/dishes/chicken.17808de0.webp',
  '/media/dishes/potatoes.25aad58e.webp',
  '/media/recipes/pancakes.jpg',
  '/media/dishes/chocolate.12bef7db.webp',
  '/media/dishes/kabab-koobideh.feaffc8f.webp',
  '/media/dishes/turkish-breakfast.b6b34316.webp',
];

const isLocalImage = (url?: string | null): url is string =>
  Boolean(url && (url.startsWith('/media/') || url.startsWith('/placeholder.svg')));

export function getDishImageUrl(dishName: string, existingUrl?: string): string {
  // The API resolves dishes against the same catalog, so its local path wins.
  if (isLocalImage(existingUrl)) {
    return existingUrl;
  }

  if (!dishName) {
    return DEFAULT_GOURMET_PHOTOS[0];
  }

  const lower = dishName.toLowerCase();

  for (const [key, url] of Object.entries(DISH_PHOTO_MAP)) {
    const searchWord = key.replace('_', ' ');
    if (lower.includes(searchWord)) {
      return url;
    }
  }

  // Consistent pseudo-hash index for varied fallbacks.
  let hash = 0;
  for (let i = 0; i < dishName.length; i++) {
    hash = (hash << 5) - hash + dishName.charCodeAt(i);
    hash |= 0;
  }
  const idx = Math.abs(hash) % DEFAULT_GOURMET_PHOTOS.length;
  return DEFAULT_GOURMET_PHOTOS[idx];
}

/**
 * Assign a photo URL to every dish in a list, guaranteeing that no two
 * DIFFERENT dishes on the same page share a photo. Keeps a dish's natural
 * photo when it is unique; rotates through the local pool only for collisions.
 */
export function assignUniqueDishPhotos(
  dishes: Array<{ name: string; image?: string | null }>,
): string[] {
  const pool: string[] = [];
  const poolSeen = new Set<string>();
  const absorb = (url: string) => {
    if (url && !poolSeen.has(url)) {
      poolSeen.add(url);
      pool.push(url);
    }
  };
  for (const url of Object.values(DISH_PHOTO_MAP)) absorb(url);
  for (const url of DEFAULT_GOURMET_PHOTOS) absorb(url);

  const natural = dishes.map((d) => getDishImageUrl(d.name, d.image ?? undefined));
  const used = new Set<string>();
  const out: string[] = [];
  for (let i = 0; i < natural.length; i++) {
    let url = natural[i];
    if (used.has(url) && pool.length > 1) {
      const start = Math.max(0, pool.indexOf(url));
      let probe = (start + 1) % pool.length;
      let guard = 0;
      while (used.has(pool[probe]) && guard < pool.length) {
        probe = (probe + 1) % pool.length;
        guard += 1;
      }
      url = pool[probe];
    }
    used.add(url);
    out.push(url);
  }
  return out;
}
