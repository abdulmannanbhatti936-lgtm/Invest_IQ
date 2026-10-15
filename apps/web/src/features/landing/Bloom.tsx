import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from '@investiq/i18n';
import { useTheme, useThemeColors } from '../../lib/theme';
import type { BloomScene } from './bloomScene';
import { bloomMode, rayLayout } from './landingRules';
import type { BloomCompany } from './landingData';

const webglAvailable = () => {
  try {
    const canvas = document.createElement('canvas');
    return Boolean(canvas.getContext('webgl2') ?? canvas.getContext('webgl'));
  } catch {
    return false;
  }
};

const afterFirstPaint = () =>
  new Promise<void>((resolve) => {
    const idle = () => {
      if (typeof window.requestIdleCallback === 'function') {
        window.requestIdleCallback(() => resolve(), { timeout: 2000 });
      } else {
        setTimeout(resolve, 200);
      }
    };
    if (document.readyState === 'complete') idle();
    else window.addEventListener('load', idle, { once: true });
  });

const deviceHints = () => {
  const nav = navigator as Navigator & { connection?: { saveData?: boolean } };
  return {
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    webgl: webglAvailable(),
    cores: nav.hardwareConcurrency || undefined,
    saveData: nav.connection?.saveData ?? false,
  };
};

/**
 * The hero's market bloom. three.js is fetched only when the animated version will run; on
 * reduced motion, low-power devices, Save-Data or without WebGL the static image is shown. A
 * list of every company (or sector) is the keyboard and screen-reader way in: focusing an entry
 * lights its node.
 */
export const Bloom = ({ companies }: { companies: BloomCompany[] }) => {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const colors = useThemeColors();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sceneRef = useRef<BloomScene | null>(null);
  const [mode] = useState(() => bloomMode(deviceHints()));
  const [failed, setFailed] = useState(false);
  const [label, setLabel] = useState<{ index: number; x: number; y: number } | null>(null);
  const rays = useMemo(() => rayLayout(companies), [companies]);
  const side = i18n.dir() === 'rtl' ? -1 : 1;
  const palette = useMemo(
    () => ({
      stops: [colors.gradient1, colors.gradient2, colors.gradient3] as [string, string, string],
      dark: theme === 'dark',
    }),
    [colors, theme],
  );
  const animated = mode === 'animated' && !failed;

  useEffect(() => {
    if (!animated || !canvasRef.current) return;
    let disposed = false;
    const canvas = canvasRef.current;
    // three.js (130 KB gzip) is fetched only once the page has painted and the browser is idle,
    // so it never delays the headline (the LCP element)
    afterFirstPaint()
      .then(() => import('./bloomScene'))
      .then(({ createBloom }) => {
        if (disposed) return;
        sceneRef.current = createBloom(canvas, rays, palette, (index, x, y) =>
          setLabel((prev) =>
            index === null
              ? prev && null
              : prev?.index === index && Math.abs(prev.x - x) < 1 && Math.abs(prev.y - y) < 1
                ? prev
                : { index, x, y },
          ),
        );
        sceneRef.current.setSide(side);
      })
      .catch(() => setFailed(true));

    // Stop drawing when the hero is off screen or the tab is hidden
    const observer = new IntersectionObserver(([entry]) =>
      sceneRef.current?.setRunning(entry.isIntersecting && !document.hidden),
    );
    observer.observe(canvas);
    const onVisibility = () => sceneRef.current?.setRunning(!document.hidden);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      disposed = true;
      observer.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
      sceneRef.current?.dispose();
      sceneRef.current = null;
    };
    // The scene is built once; palette and side changes are pushed into it below
  }, [animated, rays]);

  useEffect(() => sceneRef.current?.setPalette(palette), [palette]);
  useEffect(() => sceneRef.current?.setSide(side), [side]);

  const active = label ? companies[label.index] : null;

  return (
    <>
      {animated ? (
        <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden="true" />
      ) : (
        <img
          src={`/landing/bloom-${theme}.webp`}
          alt=""
          className={`absolute inset-0 h-full w-full object-cover ${
            side === -1 ? '-scale-x-100' : ''
          }`}
          decoding="async"
        />
      )}
      {active && label && (
        <div
          role="status"
          dir="ltr"
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-control border border-line bg-surface px-2 text-sm whitespace-nowrap text-ink shadow-e2"
          style={{ left: label.x, top: label.y - 16 }}
        >
          {active.ticker && <strong className="tabular-nums">{active.ticker} </strong>}
          <span className="text-muted">
            {active.ticker ? '· ' : ''}
            {active.sector}
          </span>
        </div>
      )}
      <details className="absolute bottom-4 start-4 z-10 max-w-[calc(100%-32px)] sm:start-8">
        <summary className="cursor-pointer text-xs text-muted hover:text-ink">
          {t(companies[0]?.ticker ? 'landing.hero.browse' : 'landing.hero.browseSectors', {
            count: companies.length,
          })}
        </summary>
        <ul className="mt-2 grid max-h-40 grid-cols-[repeat(auto-fill,minmax(88px,1fr))] gap-2 overflow-auto rounded-control border border-line bg-surface p-2 sm:w-[520px]">
          {companies.map((c, i) => (
            <li key={c.ticker ?? `${c.sector}-${i}`}>
              <button
                type="button"
                dir="ltr"
                aria-label={c.ticker ? `${c.ticker}, ${c.sector}` : c.sector}
                className="min-h-8 w-full truncate rounded-control border border-line px-2 text-xs text-ink hover:bg-sunken"
                onFocus={() => sceneRef.current?.setActive(i)}
                onBlur={() => sceneRef.current?.setActive(null)}
                onMouseEnter={() => sceneRef.current?.setActive(i)}
                onMouseLeave={() => sceneRef.current?.setActive(null)}
              >
                {c.ticker ?? c.sector}
              </button>
            </li>
          ))}
        </ul>
      </details>
    </>
  );
};
