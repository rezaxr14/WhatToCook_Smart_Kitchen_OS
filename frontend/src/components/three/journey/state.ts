
/**
 * Shared scroll state for the landing journey. The page scroll handler in
 * LandingPage writes `progress` (0..1 across the whole journey track); the 3D
 * scene reads it inside useFrame — no React re-renders, 60fps-friendly.
 */
export const journey = { progress: 0 };

/** Smoothed pointer (normalized -1..1) for cinematic parallax. */
export const pointer = {
  x: 0,
  y: 0,
  tx: 0,
  ty: 0,
  active: false,
};

/** Smooth 0..1 ramp of p between a..b. */
export const seg = (p: number, a: number, b: number): number => {
  // Same maths as THREE.MathUtils.smoothstep. Inlined on purpose: this module is imported eagerly by the landing
  // page, and `import * as THREE` here pulled ~360 kB of three into the entry chunk of EVERY route even though
  // the 3D scene itself is lazy-loaded. Keep three out of anything the entry chunk imports.
  if (p <= a) return 0;
  if (p >= b) return 1;
  const x = (p - a) / (b - a);
  return x * x * (3 - 2 * x);
};

/** Window ramp: 0 → 1 between a..b, 1 → 0 between c..d. */
export const win = (p: number, a: number, b: number, c: number, d: number): number =>
  seg(p, a, b) * (1 - seg(p, c, d));

export const isMobileDevice = (): boolean => {
  try {
    return window.matchMedia('(pointer: coarse)').matches || window.innerWidth < 768;
  } catch {
    return false;
  }
};

export const prefersReducedMotion = (): boolean => {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
};

/** Rough GPU-class check: true when we can afford heavy post-processing. */
export const canAffordPostFX = (): boolean => {
  try {
    if (prefersReducedMotion()) return false;
    if (isMobileDevice()) {
      // Mobile: mid-range+ only (>=4GB RAM heuristic) + landscape-ish dpr cap
      const mem = (navigator as unknown as { deviceMemory?: number }).deviceMemory ?? 4;
      return mem >= 4;
    }
    return true;
  } catch {
    return false;
  }
};

/** Hook up (once) the global mouse parallax source. */
export const initPointerParallax = (): (() => void) => {
  if (typeof window === 'undefined') return () => {};
  const onMove = (e: PointerEvent) => {
    if (e.pointerType !== 'mouse') return;
    pointer.active = true;
    pointer.tx = (e.clientX / window.innerWidth) * 2 - 1;
    pointer.ty = -((e.clientY / window.innerHeight) * 2 - 1);
  };
  window.addEventListener('pointermove', onMove, { passive: true });
  return () => window.removeEventListener('pointermove', onMove);
};
