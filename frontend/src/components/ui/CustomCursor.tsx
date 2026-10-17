import React, { useEffect, useRef } from 'react';

/**
 * Minimal trailing cursor with contextual labels (VIEW / COOK / EXPLORE).
 * Desktop-only; elements opt in via [data-cursor="LABEL"].
 */
export const CustomCursor: React.FC = () => {
  const dot = useRef<HTMLDivElement>(null);
  const ring = useRef<HTMLDivElement>(null);
  const label = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (window.matchMedia('(pointer: coarse)').matches) return;
    const d = dot.current;
    const r = ring.current;
    const l = label.current;
    if (!d || !r || !l) return;

    let x = window.innerWidth / 2;
    let y = window.innerHeight / 2;
    let rx = x;
    let ry = y;
    let raf = 0;

    const onMove = (e: PointerEvent) => {
      x = e.clientX;
      y = e.clientY;
      d.style.transform = `translate(${x}px, ${y}px)`;
    };
    const onOver = (e: Event) => {
      const target = (e.target as HTMLElement | null)?.closest?.('[data-cursor]') as HTMLElement | null;
      const text = target?.getAttribute('data-cursor') || '';
      l.textContent = text;
      r.style.opacity = text ? '1' : '0.55';
      r.style.borderColor = text ? 'rgba(245,185,92,0.9)' : 'rgba(255,244,230,0.55)';
    };
    const loop = () => {
      rx += (x - rx) * 0.16;
      ry += (y - ry) * 0.16;
      r.style.transform = `translate(${rx}px, ${ry}px)`;
      raf = requestAnimationFrame(loop);
    };

    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerover', onOver, { passive: true });
    raf = requestAnimationFrame(loop);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerover', onOver);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div className="pointer-events-none fixed inset-0 z-90 hidden md:block" aria-hidden>
      <div
        ref={dot}
        className="absolute ml-[-3px] mt-[-3px] h-1.5 w-1.5 rounded-full bg-amber-200"
        style={{ left: 0, top: 0 }}
      />
      <div
        ref={ring}
        className="absolute -ml-5 -mt-5 flex h-10 w-10 items-center justify-center rounded-full border transition-[border-color,opacity] duration-200"
        style={{ left: 0, top: 0, borderColor: 'rgba(255,244,230,0.55)', opacity: 0.55 }}
      >
        <span ref={label} className="text-[8px] font-black tracking-[0.22em] text-amber-200" />
      </div>
    </div>
  );
};
