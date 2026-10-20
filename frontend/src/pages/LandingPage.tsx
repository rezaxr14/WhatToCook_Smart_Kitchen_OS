import React, { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { ChevronDown, Sparkles, Play, Pause, ArrowRight, X, RotateCcw, Film } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { CustomCursor } from '../components/ui/CustomCursor';
import { journey, initPointerParallax, prefersReducedMotion } from '../components/three/journey/state';

/**
 * The landing experience: a single continuous 3D journey from a dark kitchen,
 * into the fridge, through the AI constellation and the recipe galaxy, into
 * the cooking sequence and the finished dish. Scroll is the timeline; the
 * JourneyScene canvas is the world; these overlays are the narration.
 *
 * A "Watch the film" mode turns the same timeline into a guided cinematic
 * tour (auto-scrolls the page, so the 3D world and every overlay stay in
 * perfect sync), with chapter navigation, play/pause and a progress rail.
 *
 * Chapter overlays are updated imperatively from a single rAF loop reading
 * window.scrollY — deliberately NOT via framer scroll-linked styles, which
 * rely on native scroll-timeline sampling that goes stale under programmatic
 * scroll jumps and heavy WebGL load.
 */

const JourneyScene = lazy(() =>
  import('../components/three/journey/JourneyScene').then((m) => ({ default: m.JourneyScene }))
);

/** Linear 0?1 ramp between two progress points (clamped). */
const lin = (v: number, a: number, b: number) => (b === a ? 1 : Math.min(1, Math.max(0, (v - a) / (b - a))));

/** Shared display typeface style — module-level so its identity never changes. */
const DISPLAY_FONT: React.CSSProperties = { fontFamily: "'Sora', 'Inter', system-ui, sans-serif" };

const CHAP_KEYS = ['hero', 'fridge', 'ai', 'galaxy', 's1', 's2', 's3', 's4', 'final', 'cta'] as const;
type ChapKey = (typeof CHAP_KEYS)[number];

/** Static per-chapter timing windows (opacity windows + vertical drift). */
const CHAP_WINDOWS: Record<
  ChapKey,
  { a: number; b: number; c: number; d: number; drift: number; startVisible?: boolean }
> = {
  // Fast fades with clean dead zones — no two captions ever share the frame.
  hero: { a: 0, b: 0.001, c: 0.07, d: 0.1, drift: 40, startVisible: true },
  fridge: { a: 0.19, b: 0.205, c: 0.315, d: 0.335, drift: 40 },
  ai: { a: 0.355, b: 0.37, c: 0.465, d: 0.485, drift: 40 },
  galaxy: { a: 0.505, b: 0.52, c: 0.585, d: 0.6, drift: 40 },
  s1: { a: 0.6, b: 0.615, c: 0.65, d: 0.668, drift: 40 },
  s2: { a: 0.672, b: 0.687, c: 0.732, d: 0.75, drift: 40 },
  s3: { a: 0.76, b: 0.775, c: 0.812, d: 0.83, drift: 40 },
  s4: { a: 0.84, b: 0.855, c: 0.885, d: 0.902, drift: 40 },
  final: { a: 0.912, b: 0.928, c: 0.96, d: 0.975, drift: 40 },
  cta: { a: 0.975, b: 0.995, c: 0.995, d: 0.995, drift: 48 }, // fade-in only (c==d → never auto-fades)
};

/* ------------------------------------------------------------------ */
/* Guided cinematic tour                                               */
/* ------------------------------------------------------------------ */

interface ChapterStop {
  p: number; // center / arrival point
  key: string; // i18n label key
}

const TOUR_STOPS: ChapterStop[] = [
  { p: 0.02, key: 'tour.stopHero' },
  { p: 0.28, key: 'tour.stopFridge' },
  { p: 0.445, key: 'tour.stopAI' },
  { p: 0.545, key: 'tour.stopGalaxy' },
  { p: 0.72, key: 'tour.stopCook' },
  { p: 0.85, key: 'tour.stopDish' },
  { p: 0.945, key: 'tour.stopFinale' },
];

/**
 * [from, to, seconds] — the film's editing rhythm.
 * Short opening cuts get the film moving within the first second or two;
 * zero-length segments are in-place "beats" that let each chapter breathe
 * before the next cut. Total ≈ 55 s.
 */
const TOUR_SEGMENTS: Array<[number, number, number]> = [
  [0, 0.12, 2.0], // opening cut — moving at full speed from the first frame
  [0.12, 0.28, 3.4], // glide to the fridge as the door swings open
  [0.28, 0.28, 2.4], // beat: fridge shelves
  [0.28, 0.445, 4.2], // pull back into the constellation
  [0.445, 0.445, 2.2], // beat: AI vision
  [0.445, 0.545, 3.4], // drift into the galaxy
  [0.545, 0.545, 2.2], // beat: galaxy
  [0.545, 0.66, 3.2], // descend to the stove — pieces drop in sequence
  [0.66, 0.66, 1.6], // beat: everything in the pan
  [0.66, 0.72, 2.0], // flame and sauce develop
  [0.72, 0.72, 2.4], // beat: cooking
  [0.72, 0.8, 2.8], // the pan becomes the plated dish
  [0.8, 0.85, 1.8], // settle the shot on the dish
  [0.85, 0.85, 2.2], // beat: the dish
  [0.85, 0.945, 3.6], // orbit while the table rises
  [0.945, 0.945, 2.0], // beat: dinner on the table
  [0.945, 1, 2.8], // pull out to the finale
];

const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

/** Ease-out for the opening cut — fastest motion at the very start. */
const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

/** Inverse of easeOutCubic (for resuming a paused opening cut). */
const easeOutCubicInv = (k: number) => 1 - Math.cbrt(1 - k);

/** Inverse of easeInOutCubic — turns a 0..1 position into the time it takes. */
const easeInOutCubicInv = (k: number) =>
  k < 0.5 ? Math.pow(k / 4, 1 / 3) : 1 - Math.pow(2 * (1 - k), 1 / 3) / 2;

type TourStatus = 'idle' | 'playing' | 'paused' | 'ended';

/** Chapter overlay — a fixed layer that appears/disappears along the timeline. */
const Chapter: React.FC<{
  k: ChapKey;
  range?: [number, number, number, number]; // overrides CHAP_WINDOWS (used by step numerals)
  drift?: number;
  startVisible?: boolean;
  className?: string;
  register: (k: string, el: HTMLDivElement | null) => void;
  children: React.ReactNode;
}> = ({ k, range, drift, startVisible, className = '', register, children }) => {
  const w = CHAP_WINDOWS[k];
  const a = range ? range[0] : w.a;
  const b = range ? range[1] : w.b;
  const c = range ? range[2] : w.c;
  const d = range ? range[3] : w.d;
  const driftPx = drift ?? w.drift;
  const startOn = startVisible ?? !!w.startVisible;
  return (
    <div
      ref={(el) => register(k, el)}
      data-chapter={k}
      className={`pointer-events-none fixed inset-0 z-10 flex ${className}`}
      style={{ opacity: startOn ? 1 : 0, visibility: startOn ? 'visible' : 'hidden' }}
    >
      {children}
    </div>
  );
};

export const LandingPage: React.FC = () => {
  const { t } = useTranslation();
  const { user, demoLogin } = useAuth();
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [veilGone, setVeilGone] = useState(false);
  const [stats, setStats] = useState<{ total_recipes: number; total_ingredients: number } | null>(null);
  const [tourStatus, setTourStatus] = useState<TourStatus>('idle');
  const [tourStopIdx, setTourStopIdx] = useState(0);

  const tourRafRef = useRef<number | null>(null);
  const segRef = useRef(0);
  const tourT0Ref = useRef(0);
  const tourBusyRef = useRef(false); // true while the rAF tour loop owns scrolling
  const chapterEls = useRef<Partial<Record<ChapKey, HTMLDivElement | null>>>({});
  const lastStopIdx = useRef(-1);
  const lastTourProgress = useRef(-1);
  const hairlineRef = useRef<HTMLDivElement | null>(null);
  const stopLabelRef = useRef<HTMLSpanElement | null>(null);
  const cueRef = useRef<HTMLDivElement | null>(null);

  // Mouse parallax for the whole scene
  useEffect(() => initPointerParallax(), []);

  // Deterministic opening shot: the journey module state and the scroll
  // position both persist across SPA navigation, so reset both on mount —
  // otherwise a back-nav or reload could resume the film mid-chapter.
  useEffect(() => {
    journey.progress = 0;
    window.scrollTo(0, 0);
  }, []);

  // Unmount the loading veil after its fade-out transition completes.
  useEffect(() => {
    if (!ready) return;
    const id = setTimeout(() => setVeilGone(true), 900);
    return () => clearTimeout(id);
  }, [ready]);

  // Veil safety net: if the WebGL scene never reports ready (context
  // blocked, driver crash, tab throttling), lift the veil anyway so the
  // hero content and text chapters stay reachable.
  useEffect(() => {
    if (ready) return;
    const id = setTimeout(() => setReady(true), 20000);
    return () => clearTimeout(id);
  }, [ready]);

  useEffect(() => {
    fetch('/api/stats/')
      .then((r) => (r.ok ? r.json() : null))
      .then(setStats)
      .catch(() => {});
  }, []);

  const registerChapter = useCallback((k: string, el: HTMLDivElement | null) => {
    chapterEls.current[k as ChapKey] = el;
  }, []);

  const chapterStyle = useCallback((k: ChapKey, v: number) => {
    const w = CHAP_WINDOWS[k];
    const startOn = !!w.startVisible;
    // A c == d window means "fade-in only, never auto fade-out" (finale).
    const fade = w.c === w.d ? 1 : 1 - lin(v, w.c, w.d);
    const o = startOn ? 1 - lin(v, w.c, w.d) : lin(v, w.a, w.b) * fade;
    let y = 0;
    if (startOn) y = -w.drift * lin(v, w.c, w.d);
    else if (v < w.a) y = w.drift;
    else y = w.drift * (1 - lin(v, w.a, w.b)) - w.drift * lin(v, w.c, w.d);
    return { o, y };
  }, []);

  // Drive the timeline from window scroll — imperative and throttling-proof.
  // rAF can be starved by heavy WebGL frames (esp. in headless/software GL),
  // so chapters are also refreshed on a small timer and on scroll events.
  useEffect(() => {
    const apply = () => {
      const doc = document.documentElement;
      const max = Math.max(1, doc.scrollHeight - window.innerHeight);
      const v = Math.min(1, Math.max(0, window.scrollY / max));
      journey.progress = v;

      for (const k of CHAP_KEYS) {
        const el = chapterEls.current[k];
        if (!el) continue;
        const { o, y } = chapterStyle(k, v);
        const rounded = Math.round(o * 1000) / 1000;
        const cur = parseFloat(el.style.opacity);
        if (Math.abs(cur - rounded) > 0.0005) el.style.opacity = String(rounded);
        el.style.visibility = rounded > 0.02 ? 'visible' : 'hidden';
        if (rounded > 0.02) el.style.transform = `translate3d(0, ${Math.round(y * 10) / 10}px, 0)`;
      }

      // hairline tracks wherever the film is (manual scroll or tour)
      if (hairlineRef.current) {
        const pct = Math.round(v * 1000);
        if (pct !== lastTourProgress.current) {
          hairlineRef.current.style.width = `${pct / 10}%`;
          lastTourProgress.current = pct;
        }
      }
      // scroll cue fades with the first push of the film
      if (cueRef.current) {
        const co = 1 - lin(v, 0, 0.035);
        const ro = Math.round(co * 100) / 100;
        if (Math.abs(parseFloat(cueRef.current.style.opacity || '1') - ro) > 0.005) {
          cueRef.current.style.opacity = String(ro);
        }
      }

      // chapter rail position
      let idx = 0;
      for (let i = 0; i < TOUR_STOPS.length; i++) {
        const lo = i === 0 ? 0 : TOUR_STOPS[i - 1].p + (TOUR_STOPS[i].p - TOUR_STOPS[i - 1].p) / 2;
        const hi = i === TOUR_STOPS.length - 1 ? 1 : TOUR_STOPS[i].p + (TOUR_STOPS[i + 1].p - TOUR_STOPS[i].p) / 2;
        if (v >= lo && v < hi) {
          idx = i;
          break;
        }
      }
      if (idx !== lastStopIdx.current) {
        lastStopIdx.current = idx;
        setTourStopIdx(idx);
        if (stopLabelRef.current) stopLabelRef.current.textContent = (t as (key: string) => string)(TOUR_STOPS[idx].key).toUpperCase();
      }
    };
    apply();
    // DOM chrome (chapter captions, hairline, cue, rail) only needs to catch
    // up when the page is actually moving — the native scroll event covers
    // manual scrolling AND the programmatic tour scrolls. A slow interval is
    // kept purely as a safety net (e.g. scroll events coalesced away).
    const timer = window.setInterval(apply, 200);
    const onScroll = () => apply();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('scroll', onScroll);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterStyle, t]);

  /** Scroll to a normalized timeline position (0..1). */
  const scrollToProgress = useCallback((p: number, behavior: ScrollBehavior = 'auto') => {
    const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    window.scrollTo({ top: p * max, behavior });
  }, []);

  const stopTourLoop = useCallback(() => {
    if (tourRafRef.current !== null) {
      window.clearInterval(tourRafRef.current);
      tourRafRef.current = null;
    }
    tourBusyRef.current = false;
  }, []);

  const endTour = useCallback(() => {
    stopTourLoop();
    setTourStatus('ended');
  }, [stopTourLoop]);

  const tourLoop = useCallback(
    () => {
      const now = performance.now();
      if (!tourT0Ref.current) tourT0Ref.current = now;
      const elapsed = (now - tourT0Ref.current) / 1000;
      const segs = TOUR_SEGMENTS;
      let acc = 0;
      let idx = segRef.current;
      let local = elapsed;
      for (let i = 0; i < idx; i++) acc += segs[i][2];
      local = Math.max(0, elapsed - acc);
      while (idx < segs.length && local > segs[idx][2]) {
        local -= segs[idx][2];
        idx += 1;
      }
      segRef.current = idx;
      if (idx >= segs.length) {
        scrollToProgress(1);
        endTour();
        return;
      }
      const [from, to, dur] = segs[idx];
      const k = idx === 0 ? easeOutCubic(Math.min(1, local / dur)) : easeInOutCubic(Math.min(1, local / dur));
      scrollToProgress(from + (to - from) * k);
    },
    [endTour, scrollToProgress]
  );

  /** Arm the tour driver: an immediate tick + a wall-clock interval. */
  const armTourLoop = useCallback(() => {
    if (tourRafRef.current !== null) window.clearInterval(tourRafRef.current);
    tourRafRef.current = window.setInterval(tourLoop, 100);
    tourLoop();
  }, [tourLoop]);

  const startTour = useCallback(() => {
    if (prefersReducedMotion()) return;
    setTourStatus('playing');
    segRef.current = 0;
    tourT0Ref.current = 0;
    tourBusyRef.current = true;
    armTourLoop();
  }, [armTourLoop]);

  const pauseTour = useCallback(() => {
    stopTourLoop();
    setTourStatus((s) => (s === 'playing' ? 'paused' : s));
  }, [stopTourLoop]);

  const resumeTour = useCallback(() => {
    if (prefersReducedMotion()) return;
    const segs = TOUR_SEGMENTS;
    const p = journey.progress;
    let idx = 0;
    for (let i = 0; i < segs.length; i++) {
      const [from, to] = segs[i];
      if (p >= from && p < to) {
        idx = i;
        break;
      }
    }
    if (p >= 1) idx = segs.length - 1;
    const [from, to, dur] = segs[idx];
    const frac = Math.max(0, Math.min(1, (p - from) / Math.max(1e-6, to - from)));
    const spentInSeg = dur * (idx === 0 ? easeOutCubicInv(frac) : easeInOutCubicInv(frac));
    let acc = 0;
    for (let i = 0; i < idx; i++) acc += segs[i][2];
    segRef.current = idx;
    tourT0Ref.current = performance.now() - (acc + spentInSeg) * 1000;
    tourBusyRef.current = true;
    setTourStatus('playing');
    armTourLoop();
  }, [armTourLoop]);

  const seekTourStop = useCallback(
    (idx: number) => {
      stopTourLoop();
      const stop = TOUR_STOPS[idx];
      scrollToProgress(stop.p);
      setTourStatus('paused');
      setTourStopIdx(idx);
    },
    [scrollToProgress, stopTourLoop]
  );

  const exitTour = useCallback(() => {
    stopTourLoop();
    setTourStatus('idle');
  }, [stopTourLoop]);

  // Manual input always takes over the film: wheel / touch / keyboard.
  useEffect(() => {
    if (tourStatus !== 'playing') return;
    const manual = () => pauseTour();
    window.addEventListener('wheel', manual, { passive: true });
    window.addEventListener('touchstart', manual, { passive: true });
    return () => {
      window.removeEventListener('wheel', manual);
      window.removeEventListener('touchstart', manual);
    };
  }, [tourStatus, pauseTour]);

  // Global keyboard: Space toggles play/pause, Escape exits the tour.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== 'Space' && e.code !== 'Escape') return;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === 'BUTTON' || tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.code === 'Escape') {
        if (tourStatus === 'playing' || tourStatus === 'paused') exitTour();
        return;
      }
      e.preventDefault();
      if (tourStatus === 'playing') pauseTour();
      else if (tourStatus === 'paused') resumeTour();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [tourStatus, pauseTour, resumeTour, exitTour]);

  useEffect(() => {
    return () => {
      if (tourRafRef.current !== null) window.clearInterval(tourRafRef.current);
    };
  }, []);

  const handleDemo = useCallback(async () => {
    try {
      await demoLogin();
      navigate('/recipes');
    } catch {
      /* toast surfaced by AuthContext */
    }
  }, [demoLogin, navigate]);

  const scrollDown = useCallback(() => {
    window.scrollTo({ top: window.innerHeight * 0.85, behavior: 'smooth' });
  }, []);

  // Stable identity for the scene-ready callback so the lazy JourneyScene
  // never re-renders because of a fresh inline closure.
  const handleSceneReady = useCallback(() => {
    setTimeout(() => setReady(true), 500);
  }, []);

  const canTour = useMemo(() => !prefersReducedMotion(), []);

  // Authenticated users go straight to their kitchen dashboard.
  // NOTE: must stay BELOW every hook — an early return above a hook breaks
  // the Rules of Hooks once the session resolves after mount.
  if (user) return <Navigate to="/recipes" replace />;

  const stopLabel = TOUR_STOPS[tourStopIdx] ? t(TOUR_STOPS[tourStopIdx].key) : '';

  return (
    <div className="relative -mt-8 bg-[#070503] text-stone-100 selection:bg-amber-500/30">
      {/* Scroll timeline: taller on desktop for a slower, more cinematic ride */}
      <div className="h-[760vh] md:h-[900vh]" />

      {/* The 3D world */}
      <div className="fixed inset-0 z-0">
        {/* deep-space fallback wash while WebGL warms up */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_70%_20%,#1c1308_0%,#070503_58%)]" />
        <Suspense fallback={null}>
          <JourneyScene onReady={handleSceneReady} />
        </Suspense>
        {/* Cinematic vignette + film grain (CSS layer, complements postFX) */}
        <div className="pointer-events-none absolute inset-0 [background:radial-gradient(ellipse_at_center,transparent_55%,rgba(0,0,0,0.5)_100%)]" />
        <div className="pointer-events-none absolute inset-0 opacity-[0.05] mix-blend-overlay [background-image:url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22120%22 height=%22120%22><filter id=%22n%22><feTurbulence type=%22fractalNoise%22 baseFrequency=%220.9%22 numOctaves=%222%22/></filter><rect width=%22120%22 height=%22120%22 filter=%22url(%23n)%22/></svg>')]" />
      </div>

      {/* During the guided tour an exit affordance floats under the app navbar */}
      {(tourStatus === 'playing' || tourStatus === 'paused') && (
        <div className="fixed right-4 top-[76px] z-30">
          <button
            onClick={exitTour}
            data-cursor="EXIT"
            className="inline-flex items-center gap-1.5 rounded-full border border-stone-100/20 bg-stone-950/55 px-3.5 py-2 text-[11px] font-bold text-stone-200 backdrop-blur-md transition-colors hover:border-amber-200/50 hover:text-amber-100"
          >
            <X className="h-3.5 w-3.5" />
            {t('tour.exit')}
          </button>
        </div>
      )}

      {/* Loading experience */}
      {!veilGone && (
        <div
          className={`fixed inset-0 z-80 flex flex-col items-center justify-center gap-6 bg-[#070503] transition-opacity duration-700 ${
 ready ? 'pointer-events-none opacity-0' : 'opacity-100'
 }`}
        >
          <div className="relative flex h-20 w-20 items-center justify-center">
            <div className="absolute inset-0 animate-spin rounded-full border border-amber-200/15 border-t-amber-300/90" style={{ animationDuration: '1.1s' }} />
            <div className="absolute inset-2.5 animate-spin rounded-full border border-transparent border-b-amber-400/50" style={{ animationDuration: '1.7s', animationDirection: 'reverse' }} />
            <div className="absolute inset-0 animate-pulse rounded-full bg-amber-400/10 blur-xl" />
            <span className="text-2xl">🍳</span>
          </div>
          <div className="text-center">
            <div className="text-sm font-black tracking-[0.45em] text-amber-100" style={DISPLAY_FONT}>
              WHATTOCOOK
            </div>
            <div className="mt-2 animate-pulse text-xs font-medium text-stone-400">{t('story.loading')}</div>
          </div>
        </div>
      )}

      {/* ---------- Chapter I — Arrival ---------- */}
      <Chapter k="hero" register={registerChapter} className="items-center">
        <div className="mx-auto max-w-5xl px-6 text-center">
          <div
            className="inline-flex items-center gap-2 rounded-full border border-amber-300/20 bg-amber-300/5 px-4 py-1.5 text-[11px] font-black tracking-[0.5em] text-amber-300/90"
            style={DISPLAY_FONT}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-amber-300 shadow-[0_0_10px_rgba(252,211,77,0.9)]" />
            {t('story.heroKicker')}
          </div>
          <h1
            className="mt-7 bg-linear-to-b/srgb from-white via-amber-50 to-amber-200/70 bg-clip-text text-5xl font-black leading-[1.02] tracking-tight text-transparent sm:text-7xl lg:text-8xl"
            style={DISPLAY_FONT}
          >
            {t('story.heroTitle')}
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-base font-medium text-stone-300/90 sm:text-lg">{t('story.heroSub')}</p>
          <div className="pointer-events-auto mt-10 flex flex-wrap items-center justify-center gap-4">
            <button
              onClick={handleDemo}
              data-cursor="COOK"
              className="group inline-flex items-center gap-2 rounded-full bg-linear-to-r/srgb from-amber-400 to-orange-500 px-7 py-3.5 text-sm font-extrabold text-stone-950 shadow-[0_8px_40px_rgba(251,146,60,0.35)] transition-transform hover:scale-105"
            >
              <Play className="h-4 w-4 fill-stone-950" />
              {t('landing.tryDemo')}
            </button>
            <button
              onClick={scrollDown}
              data-cursor="EXPLORE"
              className="inline-flex items-center gap-2 rounded-full border border-stone-100/25 bg-stone-100/5 px-7 py-3.5 text-sm font-bold text-stone-100 backdrop-blur-md transition-colors hover:border-amber-200/60"
            >
              <Sparkles className="h-4 w-4 text-amber-300" />
              {t('story.heroCta')}
            </button>
            {canTour && (
              <button
                onClick={startTour}
                data-cursor="FILM"
                className="inline-flex items-center gap-2 rounded-full border border-amber-200/30 bg-amber-400/10 px-7 py-3.5 text-sm font-bold text-amber-200 backdrop-blur-md transition-all hover:bg-amber-400/20 hover:shadow-[0_0_30px_rgba(251,191,36,0.25)]"
              >
                <Film className="h-4 w-4" />
                {t('tour.watch')}
              </button>
            )}
          </div>
        </div>
      </Chapter>

      {/* Scroll cue */}
      <div ref={cueRef} className="pointer-events-none fixed inset-x-0 bottom-24 z-10 flex justify-center"data-chapter="cue">
        <button
          onClick={scrollDown}
          className="pointer-events-auto flex flex-col items-center gap-1 text-stone-400 transition-colors hover:text-amber-200"
        >
          <span className="text-[10px] font-bold tracking-[0.35em]">{t('story.scrollCue')}</span>
          <ChevronDown className="h-4 w-4 animate-bounce" />
        </button>
      </div>

      {/* ---------- Chapter II — The fridge ---------- */}
      <Chapter k="fridge" register={registerChapter} className="items-center justify-start">
        <div className="max-w-md px-8 sm:px-16">
          <div className="text-[10px] font-black tracking-[0.4em] text-amber-300/90" style={DISPLAY_FONT}>
            01 — {t('story.heroCta')}
          </div>
          <h2 className="mt-3 text-2xl font-black leading-tight tracking-tight text-stone-50 sm:text-4xl" style={DISPLAY_FONT}>
            {t('story.fridgeTitle')}
          </h2>
          <p className="mt-3 max-w-xs text-sm font-medium leading-relaxed text-stone-300/90">{t('story.fridgeSub')}</p>
        </div>
      </Chapter>

      {/* ---------- Chapter III — AI vision ---------- */}
      <Chapter k="ai" register={registerChapter} className="items-center justify-center sm:justify-end">
        <div className="max-w-md px-6 text-center sm:text-right sm:pr-24 lg:pr-32">
          <div className="text-[10px] font-black tracking-[0.4em] text-amber-300/90" style={DISPLAY_FONT}>
            02 — AI
          </div>
          <h2 className="mt-3 text-2xl font-black leading-tight tracking-tight text-stone-50 sm:text-4xl" style={DISPLAY_FONT}>
            {t('story.aiTitle')}
          </h2>
          <p className="mt-3 max-w-xs text-sm font-medium leading-relaxed text-stone-300/90 mx-auto sm:ml-auto sm:mr-0">{t('story.aiSub')}</p>
        </div>
      </Chapter>

      {/* ---------- Chapter IV — Recipe galaxy ---------- */}
      <Chapter k="galaxy" register={registerChapter} className="items-start justify-center pt-24 sm:pt-28">
        {/* Intro Top Header */}
        <div className="max-w-xl px-4 text-center">
          <div className="mx-auto rounded-3xl border border-amber-200/20 bg-stone-950/75 p-4 sm:p-6 backdrop-blur-xl shadow-[0_16px_50px_rgba(0,0,0,0.6)]">
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-300/30 bg-amber-400/10 px-3 py-1 text-[10px] font-black tracking-widest text-amber-300 uppercase" style={DISPLAY_FONT}>
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
              03 — AI Recipe Galaxy
            </div>
            <h2 className="mt-2 text-xl sm:text-3xl md:text-4xl font-black leading-tight tracking-tight text-stone-50" style={DISPLAY_FONT}>
              {t('story.galaxyTitle')}
            </h2>
            <p className="mx-auto mt-2 max-w-md text-xs sm:text-sm font-medium text-stone-300/90 leading-relaxed">
              {t('story.galaxySub')}
            </p>
          </div>
        </div>

        {/* Mobile Spotlight Card (< md): Clean single card centered above bottom buttons */}
        <div className="md:hidden mt-5 w-full max-w-xs px-2 pointer-events-auto">
          <div className="rounded-3xl border border-amber-300/30 bg-stone-950/90 p-4 backdrop-blur-xl shadow-2xl">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-400/15 border border-emerald-400/30 px-2.5 py-0.5 text-[9px] font-black tracking-widest text-emerald-300 uppercase">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />
                96% {t('story.match')}
              </span>
              <span className="text-[10px] font-bold text-amber-200">⏱ {t('story.cardTime')}</span>
            </div>
            <div className="mt-2 text-sm font-black text-white" style={DISPLAY_FONT}>
              {t('story.cardName')}
            </div>
            <div className="mt-1 text-[10px] text-stone-400">
              {t('story.uses', { n: 6 })} · <span className="text-emerald-400 font-bold">{t('story.cardLevel')}</span>
            </div>
            <div className="mt-3 pt-2 border-t border-stone-800/80 flex items-center justify-between text-[10px] text-stone-400">
              <span>🍝 Tomato & Penne</span>
              <span className="text-amber-300 font-bold">+2 More Dishes</span>
            </div>
          </div>
        </div>

        {/* Desktop 3 Red Circles (hidden md:block): Positioned in the 3 circled zones, well away from edges & rail */}

        {/* 1. Left Circle Card (mid-left) */}
        <div className="hidden md:block absolute left-8 lg:left-14 top-[48%] -translate-y-1/2 w-60 pointer-events-auto">
          <div className="rounded-3xl border border-sky-400/30 bg-stone-950/80 p-4 backdrop-blur-xl shadow-[0_12px_40px_rgba(0,0,0,0.6)] hover:border-sky-400/60 transition-all duration-300 hover:scale-[1.03]">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-400/30 bg-sky-400/15 px-2.5 py-0.5 text-[9px] font-black tracking-widest text-sky-300 uppercase">
                <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-ping" />
                85% {t('story.match')}
              </span>
              <span className="text-[10px] font-bold text-stone-300">⏱ 10 min</span>
            </div>
            <div className="mt-2 text-sm font-black text-stone-100" style={DISPLAY_FONT}>
              {t('story.card3Name')}
            </div>
            <div className="mt-1 text-[10px] font-semibold text-stone-400">
              {t('story.uses', { n: 4 })} · <span className="text-sky-300 font-bold">Fresh bite</span>
            </div>
            <div className="mt-2 pt-2 border-t border-stone-800/80 text-[10px] text-stone-400">
              🍅 Mozzarella, Basil, Tomato
            </div>
          </div>
        </div>

        {/* 2. Bottom-Center Circle Card (lower middle) */}
        <div className="hidden md:block absolute left-1/2 -translate-x-1/2 bottom-20 lg:bottom-24 w-60 pointer-events-auto">
          <div className="rounded-3xl border border-amber-400/30 bg-stone-950/80 p-4 backdrop-blur-xl shadow-[0_12px_40px_rgba(0,0,0,0.6)] hover:border-amber-400/60 transition-all duration-300 hover:scale-[1.03]">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/30 bg-amber-400/15 px-2.5 py-0.5 text-[9px] font-black tracking-widest text-amber-300 uppercase">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-ping" />
                91% {t('story.match')}
              </span>
              <span className="text-[10px] font-bold text-stone-300">⏱ 15 min</span>
            </div>
            <div className="mt-2 text-sm font-black text-stone-100" style={DISPLAY_FONT}>
              {t('story.card2Name')}
            </div>
            <div className="mt-1 text-[10px] font-semibold text-stone-400">
              {t('story.uses', { n: 5 })} · <span className="text-amber-300 font-bold">Skillet</span>
            </div>
            <div className="mt-2 pt-2 border-t border-stone-800/80 text-[10px] text-stone-400">
              🍳 Farm Eggs, Bell Pepper, Tomato
            </div>
          </div>
        </div>

        {/* 3. Right Circle Card (lower-right, safely inset from right rail & buttons!) */}
        <div className="hidden md:block absolute right-16 lg:right-24 w-60 pointer-events-auto">
          <div className="rounded-3xl border border-emerald-400/30 bg-stone-950/80 p-4 backdrop-blur-xl shadow-[0_12px_40px_rgba(0,0,0,0.6)] hover:border-emerald-400/60 transition-all duration-300 hover:scale-[1.03]">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/30 bg-emerald-400/15 px-2.5 py-0.5 text-[9px] font-black tracking-widest text-emerald-300 uppercase">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />
                96% {t('story.match')}
              </span>
              <span className="text-[10px] font-bold text-stone-300">⏱ {t('story.cardTime')}</span>
            </div>
            <div className="mt-2 text-sm font-black text-stone-100" style={DISPLAY_FONT}>
              {t('story.cardName')}
            </div>
            <div className="mt-1 text-[10px] font-semibold text-stone-400">
              {t('story.uses', { n: 6 })} · <span className="text-emerald-300 font-bold">{t('story.cardLevel')}</span>
            </div>
            <div className="mt-2 pt-2 border-t border-stone-800/80 text-[10px] text-stone-400">
              🍝 Penne, Garlic, Vine Tomatoes
            </div>
          </div>
        </div>
      </Chapter>

      {/* ---------- Chapter V — Cooking steps ---------- */}
      {([
        [0.6, 0.615, 0.65, 0.668, 's1', '01', t('story.prep')],
        [0.672, 0.687, 0.732, 0.75, 's2', '02', t('story.cook')],
        [0.76, 0.775, 0.812, 0.83, 's3', '03', t('story.combine')],
        [0.84, 0.855, 0.885, 0.902, 's4', '04', t('story.serve')],
      ] as Array<[number, number, number, number, ChapKey, string, string]>).map(([a, b, c, d, key, num, word]) => (
        <Chapter key={key} k={key} register={registerChapter} range={[a, b, c, d]} className="items-end">
          <div className="flex items-center gap-3 p-10 sm:p-16">
            <span
              className="flex h-8 w-8 items-center justify-center rounded-full border border-amber-300/30 bg-stone-950/55 text-[11px] font-black text-amber-200 backdrop-blur-md sm:h-9 sm:w-9 sm:text-xs"
              style={DISPLAY_FONT}
            >
              {num}
            </span>
            <span className="text-[10px] font-black tracking-[0.45em] text-stone-100/90 sm:text-[11px]" style={DISPLAY_FONT}>
              {word.toUpperCase()}
            </span>
          </div>
        </Chapter>
      ))}

      {/* ---------- Chapter VI — Dinner, discovered ---------- */}
      <Chapter k="final" register={registerChapter} className="items-center">
        <div className="mx-auto grid max-w-6xl gap-10 px-8 sm:px-12 lg:grid-cols-2 lg:items-center">
          <div>
            <h2 className="text-4xl font-black leading-[1.05] tracking-tight text-stone-50 sm:text-5xl" style={DISPLAY_FONT}>
              {t('story.finalTitle')}
            </h2>
            <p className="mt-4 max-w-md text-sm font-medium text-stone-300/90 sm:text-base">{t('story.finalSub')}</p>
          </div>
          <div className="pointer-events-auto ml-auto w-full max-w-xs rounded-3xl border border-stone-100/15 bg-stone-950/60 p-6 shadow-[0_20px_80px_rgba(0,0,0,0.6)] backdrop-blur-xl">
            <div className="flex items-center justify-between">
              <span className="rounded-full bg-amber-400/15 px-2.5 py-1 text-[10px] font-black tracking-widest text-amber-300">
                94% {t('story.match')}
              </span>
              <span className="text-[10px] font-bold text-stone-400">
                {t('story.cardTime')} · {t('story.cardLevel')}
              </span>
            </div>
            <div className="mt-3 text-xl font-black tracking-tight text-stone-50" style={DISPLAY_FONT}>
              {t('story.cardName')}
            </div>
            <div className="mt-4 text-[10px] font-black tracking-[0.25em] text-stone-400">{t('story.cardIng')}</div>
            <ul className="mt-2 space-y-1 text-xs font-medium text-stone-300">
              {[t('story.ingTomato'), t('story.ingPasta'), t('story.ingGarlic'), t('story.ingBasil')].map((ing) => (
                <li key={ing} className="flex items-center gap-2">
                  <span className="h-1 w-1 rounded-full bg-amber-400" />
                  {ing}
                </li>
              ))}
            </ul>
            <div className="mt-4 flex items-center gap-2 rounded-2xl border border-amber-200/20 bg-amber-400/5 px-3 py-2">
              <span className="text-[9px] font-black tracking-[0.25em] text-amber-300/80">{t('story.cardAi')}</span>
              <span className="text-xs font-medium text-stone-300">{t('story.cardAiText')}</span>
            </div>
            <button
              onClick={() => navigate('/recipes')}
              data-cursor="COOK"
              className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-linear-to-r/srgb from-amber-400 to-orange-500 py-3 text-sm font-extrabold text-stone-950 transition-transform hover:scale-[1.03]"
            >
              {t('story.makeThis')}
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </Chapter>

      {/* ---------- Chapter VII — Finale / CTA ---------- */}
      <Chapter k="cta" register={registerChapter} className="items-center justify-center">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-5xl font-black tracking-tight text-stone-50 sm:text-7xl" style={DISPLAY_FONT}>
            {t('story.ctaTitle')}
          </h2>
          <p className="mx-auto mt-5 max-w-md text-sm font-medium text-stone-300/90 sm:text-base">{t('story.ctaSub')}</p>
          <div className="pointer-events-auto mt-9 flex flex-wrap items-center justify-center gap-4">
            <button
              onClick={handleDemo}
              data-cursor="COOK"
              className="inline-flex items-center gap-2 rounded-full bg-linear-to-r/srgb from-amber-400 to-orange-500 px-8 py-3.5 text-sm font-extrabold text-stone-950 shadow-[0_8px_40px_rgba(251,146,60,0.4)] transition-transform hover:scale-105"
            >
              <Sparkles className="h-4 w-4" />
              {t('story.ctaStart')}
            </button>
            <button
              onClick={() => navigate('/recipes')}
              data-cursor="EXPLORE"
              className="inline-flex items-center gap-2 rounded-full border border-stone-100/25 bg-stone-100/5 px-8 py-3.5 text-sm font-bold text-stone-100 backdrop-blur-md transition-colors hover:border-amber-200/60"
            >
              {t('landing.exploreRecipes')}
              <ArrowRight className="h-4 w-4" />
            </button>
            {tourStatus === 'ended' && canTour && (
              <button
                onClick={startTour}
                data-cursor="REPLAY"
                className="inline-flex items-center gap-2 rounded-full border border-amber-200/30 bg-amber-400/10 px-8 py-3.5 text-sm font-bold text-amber-200 backdrop-blur-md transition-all hover:bg-amber-400/20"
              >
                <RotateCcw className="h-4 w-4" />
                {t('tour.replay')}
              </button>
            )}
          </div>

          {/* Live platform stats */}
          {stats && (
            <div className="mt-10 flex items-center justify-center gap-3">
              {[
                [`${stats.total_recipes}+`, t('landing.statsRecipes')],
                [`${stats.total_ingredients}+`, t('landing.statsIngredients')],
              ].map(([value, label]) => (
                <div key={label} className="rounded-2xl border border-stone-100/15 bg-stone-950/50 px-5 py-3 backdrop-blur-md">
                  <div className="text-lg font-black text-amber-200" style={DISPLAY_FONT}>
                    {value}
                  </div>
                  <div className="text-[10px] font-semibold text-stone-400">{label}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Chapter>

      {/* ---------- Tour chrome: rail + pill + progress hairline ---------- */}
      {canTour && (
        <>
          {/* Chapter rail (desktop) */}
          <div className="fixed right-3 sm:right-4 top-1/2 z-30 hidden -translate-y-1/2 flex-col items-center gap-1 rounded-full border border-stone-800/70 bg-stone-950/70 p-1.5 shadow-[0_12px_40px_rgba(0,0,0,0.6)] backdrop-blur-xl md:flex">
            {TOUR_STOPS.map((stop, i) => {
              const active = tourStopIdx === i;
              return (
                <button
                  key={stop.key}
                  onClick={() => seekTourStop(i)}
                  data-cursor="CHAPTER"
                  title={t(stop.key)}
                  aria-label={t(stop.key)}
                  className="group relative flex h-8 w-8 items-center justify-center rounded-full transition-colors cursor-pointer hover:bg-white/10"
                >
                  <span
                    className={`block rounded-full transition-all duration-300 ${
 active
 ? 'h-3.5 w-3.5 bg-amber-400 ring-4 ring-amber-400/25 shadow-[0_0_14px_rgba(251,191,36,0.95)]'
 : 'h-2 w-2 bg-stone-500/80 group-hover:scale-125 group-hover:bg-amber-200'
 }`}
                  />
                  <span
                    className="pointer-events-none absolute right-11 whitespace-nowrap rounded-full border border-stone-200/20 bg-stone-950/90 px-3.5 py-1.5 text-xs font-black tracking-wide text-amber-100 opacity-0 shadow-2xl backdrop-blur-md transition-all duration-200 group-hover:opacity-100 group-hover:-translate-x-1"
                    style={DISPLAY_FONT}
                  >
                    {t(stop.key)}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Bottom control pill */}
          {(tourStatus === 'playing' || tourStatus === 'paused' || tourStatus === 'ended') && (
            <div className="fixed inset-x-0 bottom-5 z-30 flex justify-center px-4">
              <div className="pointer-events-auto flex items-center gap-3 rounded-full border bg-stone-950/70 py-1.5 pl-2 pr-4 shadow-[0_10px_40px_rgba(0,0,0,0.55)] backdrop-blur-xl">
                {tourStatus === 'ended' ? (
                  <button
                    onClick={startTour}
                    data-cursor="REPLAY"
                    className="inline-flex items-center gap-2 rounded-full bg-linear-to-r/srgb from-amber-400 to-orange-500 px-4 py-2 text-xs font-extrabold text-stone-950"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    {t('tour.replay')}
                  </button>
                ) : (
                  <button
                    onClick={tourStatus === 'playing' ? pauseTour : resumeTour}
                    data-cursor="PLAY"
                    aria-label={tourStatus === 'playing' ? t('tour.pause') : t('tour.play')}
                    className="flex h-9 w-9 items-center justify-center rounded-full bg-linear-to-r/srgb from-amber-400 to-orange-500 text-stone-950 transition-transform hover:scale-105"
                  >
                    {tourStatus === 'playing' ? (
                      <Pause className="h-4 w-4 fill-stone-950" />
                    ) : (
                      <Play className="ml-0.5 h-4 w-4 fill-stone-950" />
                    )}
                  </button>
                )}
                <span
                  ref={stopLabelRef}
                  className="text-[11px] font-black tracking-[0.22em] text-amber-100/90"
                  style={DISPLAY_FONT}
                >
                  {stopLabel.toUpperCase()}
                </span>
                {tourStatus !== 'ended' && (
                  <span className="hidden items-center gap-1.5 pl-2 text-[10px] font-semibold text-stone-500 sm:flex">
                    <span className="h-3 w-px bg-stone-700" />
                    {tourStatus === 'playing' ? t('tour.hintPause') : t('tour.hintResume')}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Progress hairline */}
          {(tourStatus === 'playing' || tourStatus === 'paused' || tourStatus === 'ended') && (
            <div className="fixed inset-x-0 bottom-0 z-30 h-[3px] bg-stone-800/60">
              <div
                ref={hairlineRef}
                className="h-full bg-linear-to-r/srgb from-amber-500 via-orange-400 to-amber-300 shadow-[0_0_12px_rgba(251,146,60,0.7)]"
                style={{ width: '0%' }}
              />
            </div>
          )}
        </>
      )}

      {/* (the app footer sits below the journey's scroll timeline) */}

      <CustomCursor />
    </div>
  );
};
