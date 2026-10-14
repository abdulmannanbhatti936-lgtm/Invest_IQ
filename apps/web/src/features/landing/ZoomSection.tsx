import { useEffect, useRef } from 'react';
import { useTranslation } from '@investiq/i18n';
import { useTheme } from '../../lib/theme';
import { zoomFrame } from './landingRules';

const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * Scroll-driven zoom (Revolut-style header): the section is pinned while the headline gives
 * way to a real screenshot of the portfolio screen, which shrinks from full-bleed into a laptop
 * frame (a phone frame below 640 px). No animation library: one passive scroll listener and
 * requestAnimationFrame. Under reduced motion it shows the final frame.
 */
export const ZoomSection = ({ builtOn }: { builtOn: string }) => {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const section = useRef<HTMLElement>(null);
  const device = useRef<HTMLDivElement>(null);
  const screen = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLDivElement>(null);
  const headline = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0;
      if (!section.current || !device.current || !screen.current) return;
      const box = section.current.getBoundingClientRect();
      const progress = Math.min(
        1,
        Math.max(0, -box.top / Math.max(1, box.height - window.innerHeight)),
      );
      const d = device.current.getBoundingClientRect();
      const f = zoomFrame(progress, {
        cover: Math.max(window.innerWidth / d.width, window.innerHeight / d.height) * 1.02,
        centerOffset: window.innerHeight / 2 - (d.top + d.height / 2),
        viewportHeight: window.innerHeight,
        reducedMotion: reduced(),
      });
      screen.current.style.transform = `translateY(${f.screenY}px) scale(${f.scale})`;
      screen.current.style.borderRadius = `${f.scale > 1.01 ? 0 : 12}px`;
      if (frame.current) frame.current.style.opacity = String(f.frameOpacity);
      if (headline.current) {
        headline.current.style.opacity = String(f.headlineOpacity);
        headline.current.style.transform = `scale(${f.headlineScale})`;
      }
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
  }, []);

  const lang = i18n.language.startsWith('ur') ? 'ur' : 'en';
  return (
    <section ref={section} className="relative h-[320vh] bg-bg" aria-labelledby="zoom-title">
      <div className="sticky top-0 flex h-svh items-center justify-center overflow-hidden">
        <h2
          id="zoom-title"
          ref={headline}
          className="absolute top-[10vh] z-10 w-full origin-top px-4 text-center font-display text-4xl font-bold tracking-tight text-ink sm:text-7xl"
        >
          {t('landing.zoom.titleStart')}{' '}
          <span className="bg-gradient-to-r from-gradient-1 via-gradient-2 to-gradient-3 bg-clip-text text-transparent">
            {t('landing.zoom.titleEnd')}
          </span>
        </h2>
        <div
          ref={device}
          className="absolute top-[28vh] aspect-[9/16] w-[64vw] sm:aspect-[16/10] sm:w-[min(58vw,860px)]"
        >
          <div
            ref={frame}
            className="absolute -inset-4 rounded-[24px] bg-[#0b0b0b] opacity-0 shadow-e3 ring-1 ring-line"
            aria-hidden="true"
          />
          <div
            ref={screen}
            className="absolute inset-0 origin-center overflow-hidden rounded-control bg-surface will-change-transform"
          >
            <picture>
              <source
                media="(max-width: 639px)"
                srcSet={`/landing/portfolio-${theme}-${lang}-m390.webp`}
              />
              <img
                src={`/landing/portfolio-${theme}-${lang}.webp`}
                alt={t('landing.zoom.alt')}
                loading="lazy"
                decoding="async"
                className="h-full w-full object-cover object-top"
              />
            </picture>
          </div>
        </div>
        <p className="absolute bottom-6 z-10 w-full px-4 text-center text-xs text-muted">
          {t('landing.zoom.caption', { date: builtOn })}
        </p>
      </div>
    </section>
  );
};
