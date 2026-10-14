// Design.md §11: micro-interactions 100-150 ms, panels 200-300 ms, nothing in the app over
// 400 ms; ease-out entering, ease-in leaving. The landing page's bloom and scroll section are
// the recorded exception (Design.md §11 deviation, 2026-10-15) and stop under reduced motion.
export const motion = {
  duration: {
    micro: '150ms',
    panel: '250ms',
    max: '400ms',
  },
  /** Figures count up on first appearance, capped below Design §11's ~500 ms */
  countUpMs: 400,
  easing: {
    enter: 'cubic-bezier(0, 0, 0.2, 1)',
    exit: 'cubic-bezier(0.4, 0, 1, 1)',
  },
};
