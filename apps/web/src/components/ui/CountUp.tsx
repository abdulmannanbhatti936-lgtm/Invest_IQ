import { useEffect, useRef, useState } from 'react';
import { motion } from '@investiq/design-tokens';

const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * A figure that counts up once when it first appears (Design.md §11, capped at 400 ms) and
 * always ends on exactly `format(value)`: the animation only ever shows the API's own figure
 * at rest. Later changes of `value` (a refetch) switch instantly.
 */
export const CountUp = ({
  value,
  format,
  exact,
}: {
  value: number;
  format: (n: number) => string;
  /** The API's own formatted figure, shown once the count ends (defaults to format(value)) */
  exact?: string;
}) => {
  const [shown, setShown] = useState(() => (reducedMotion() ? value : 0));
  const done = useRef(reducedMotion());

  useEffect(() => {
    if (done.current) {
      setShown(value);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / motion.countUpMs);
      setShown(value * (1 - (1 - t) ** 3));
      if (t < 1) frame = requestAnimationFrame(tick);
      else done.current = true;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return <>{done.current ? (exact ?? format(value)) : format(shown)}</>;
};
