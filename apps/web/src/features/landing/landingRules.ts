// The landing page's decisions as pure functions, so each rule is unit-tested without a browser.

export interface DeviceHints {
  reducedMotion: boolean;
  webgl: boolean;
  /** navigator.hardwareConcurrency, when the browser reports it */
  cores?: number;
  /** The Save-Data request hint (navigator.connection.saveData) */
  saveData?: boolean;
}

/**
 * The animated 3D bloom only when the visitor has not asked for less motion, WebGL works, the
 * device is not low-powered and data saving is off; otherwise the static image of it.
 */
export const bloomMode = (d: DeviceHints): 'animated' | 'static' =>
  d.reducedMotion || !d.webgl || d.saveData || (d.cores !== undefined && d.cores <= 4)
    ? 'static'
    : 'animated';

/** Stable 32-bit hash of a string, so a ray's angle and length never depend on any price. */
export const hash = (text: string): number =>
  [...text].reduce((h, ch) => (Math.imul(h, 31) + ch.charCodeAt(0)) >>> 0, 7);

export interface Ray {
  sector: string;
  sectorIndex: number;
  /** Unit direction of the ray */
  x: number;
  y: number;
  z: number;
  length: number;
}

/**
 * One ray per company, fanned out from one point: each sector owns an equal slice of the fan
 * (sectors in alphabetical order), and the ray's place inside it and its length come from a hash
 * of the ticker (or of the sector and position when tickers are hidden).
 */
export const rayLayout = (companies: { ticker?: string; sector: string }[]): Ray[] => {
  const sectors = [...new Set(companies.map((c) => c.sector))].sort();
  const slice = (Math.PI * 1.9) / Math.max(1, sectors.length);
  return companies.map((c, i) => {
    const sectorIndex = sectors.indexOf(c.sector);
    const h = hash(c.ticker ?? `${c.sector}#${i}`);
    const theta = -Math.PI * 0.95 + (sectorIndex + 0.15 + 0.7 * ((h % 997) / 997)) * slice;
    const phi = 0.35 + 0.75 * (((h >>> 10) % 991) / 991);
    return {
      sector: c.sector,
      sectorIndex,
      x: Math.cos(theta) * Math.sin(phi),
      y: Math.sin(theta) * Math.sin(phi) * 0.9,
      z: Math.cos(phi) * 0.6,
      length: 3 + 2.6 * (((h >>> 3) % 983) / 983),
    };
  });
};

export const sectorCount = (companies: { sector: string }[]) =>
  new Set(companies.map((c) => c.sector)).size;

const clamp = (v: number) => Math.min(1, Math.max(0, v));
const easeOut = (t: number) => 1 - (1 - t) ** 3;

export interface ZoomFrame {
  /** The screenshot's vertical offset (px) and scale relative to its place in the device */
  screenY: number;
  scale: number;
  headlineOpacity: number;
  headlineScale: number;
  frameOpacity: number;
}

/**
 * The scroll-driven zoom: first the headline alone, then the screenshot rises full-bleed and
 * shrinks into the device frame while the headline returns smaller above it. `progress` is how
 * far the pinned section has been scrolled (0 to 1); `cover` is the scale at which the screenshot
 * fills the viewport; `centerOffset` the distance from the device's centre to the viewport's.
 * Under reduced motion the final frame is shown at once.
 */
export const zoomFrame = (
  progress: number,
  {
    cover,
    centerOffset,
    viewportHeight,
    reducedMotion,
  }: {
    cover: number;
    centerOffset: number;
    viewportHeight: number;
    reducedMotion: boolean;
  },
): ZoomFrame => {
  if (reducedMotion) {
    return { screenY: 0, scale: 1, headlineOpacity: 1, headlineScale: 0.7, frameOpacity: 1 };
  }
  const rise = clamp(progress / 0.22);
  const shrink = easeOut(clamp((progress - 0.22) / 0.6));
  return {
    screenY: centerOffset * (1 - shrink) + (1 - rise) * viewportHeight,
    scale: cover + (1 - cover) * shrink,
    headlineOpacity: Math.max(clamp(1 - shrink / 0.15), clamp((shrink - 0.65) / 0.35)),
    headlineScale: shrink > 0.5 ? 0.7 : 1.15,
    frameOpacity: clamp((shrink - 0.6) / 0.4),
  };
};
