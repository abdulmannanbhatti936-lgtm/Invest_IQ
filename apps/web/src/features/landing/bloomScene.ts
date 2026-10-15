// The hero's "market bloom" in plain three.js (team decision 2026-10-15: no react-three-fiber).
// Loaded only by Bloom.tsx through a dynamic import, so three.js is its own chunk on the landing
// route. One ray and one glowing node per company; sparks travel outward; the bloom breathes and
// leans gently toward the pointer. Hovering a node reports it so the page can label it.
import {
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  Group,
  LineBasicMaterial,
  LineSegments,
  NormalBlending,
  PerspectiveCamera,
  Points,
  Raycaster,
  Scene,
  ShaderMaterial,
  Vector2,
  Vector3,
  WebGLRenderer,
} from 'three';
import type { Ray } from './landingRules';

export interface BloomPalette {
  stops: [string, string, string];
  /** Light backgrounds need normal blending; additive glow only works on dark ones */
  dark: boolean;
}

export interface BloomScene {
  setActive: (index: number | null) => void;
  setPalette: (palette: BloomPalette) => void;
  /** Mirrors the bloom to the other side for right-to-left pages */
  setSide: (side: 1 | -1) => void;
  setRunning: (running: boolean) => void;
  dispose: () => void;
}

const SPARKS = 5;

const glowTexture = () => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 64;
  const g = canvas.getContext('2d')!;
  const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, 'rgba(255,255,255,1)');
  r.addColorStop(0.25, 'rgba(255,255,255,.85)');
  r.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = r;
  g.fillRect(0, 0, 64, 64);
  return new CanvasTexture(canvas);
};

const sectorColors = (rays: Ray[], stops: string[]) => {
  const [a, b, c] = stops.map((s) => new Color(s));
  const sectors = Math.max(1, ...rays.map((r) => r.sectorIndex + 1));
  return rays.map((r) => {
    const t = sectors > 1 ? r.sectorIndex / (sectors - 1) : 0;
    return t < 0.5 ? a.clone().lerp(b, t * 2) : b.clone().lerp(c, (t - 0.5) * 2);
  });
};

export const createBloom = (
  canvas: HTMLCanvasElement,
  rays: Ray[],
  palette: BloomPalette,
  onHover: (index: number | null, x: number, y: number) => void,
): BloomScene => {
  const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true });
  const scene = new Scene();
  const camera = new PerspectiveCamera(42, 1, 0.1, 100);
  camera.position.set(0, 0, 11);
  const group = new Group();
  scene.add(group);

  const n = rays.length;
  let colors = sectorColors(rays, palette.stops);
  let dark = palette.dark;

  const rayPos = new Float32Array(n * 6);
  const rayCol = new Float32Array(n * 6);
  const rayGeo = new BufferGeometry();
  rayGeo.setAttribute('position', new BufferAttribute(rayPos, 3));
  rayGeo.setAttribute('color', new BufferAttribute(rayCol, 3));
  const rayMat = new LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    depthWrite: false,
  });
  group.add(new LineSegments(rayGeo, rayMat));

  const pointMaterial = new ShaderMaterial({
    uniforms: { map: { value: glowTexture() } },
    vertexShader: `attribute float size; attribute vec3 color; varying vec3 vC;
      void main(){ vC = color; vec4 mv = modelViewMatrix * vec4(position, 1.0);
      gl_PointSize = size * (300.0 / -mv.z); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform sampler2D map; varying vec3 vC;
      void main(){ gl_FragColor = vec4(vC, texture2D(map, gl_PointCoord).a); }`,
    transparent: true,
    depthWrite: false,
  });

  const makePoints = (count: number) => {
    const geo = new BufferGeometry();
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);
    const size = new Float32Array(count);
    geo.setAttribute('position', new BufferAttribute(pos, 3));
    geo.setAttribute('color', new BufferAttribute(col, 3));
    geo.setAttribute('size', new BufferAttribute(size, 1));
    return { geo, pos, col, size, points: new Points(geo, pointMaterial) };
  };
  const nodes = makePoints(n);
  const sparks = makePoints(n * SPARKS);
  const core = makePoints(1);
  core.col.set([1, 1, 1]);
  core.size[0] = 2.6;
  group.add(nodes.points, sparks.points, core.points);

  const applyBlending = () => {
    const blending = dark ? AdditiveBlending : NormalBlending;
    rayMat.blending = blending;
    pointMaterial.blending = blending;
    rayMat.opacity = dark ? 0.75 : 0.9;
    rayMat.needsUpdate = pointMaterial.needsUpdate = true;
    // On a light background the centre is drawn in the first stop instead of white
    const centre = dark ? new Color('#FFFFFF') : new Color(palette.stops[0]);
    core.col.set([centre.r, centre.g, centre.b]);
  };
  applyBlending();

  let active: number | null = null;
  let side: 1 | -1 = 1;
  let running = true;
  let frame = 0;
  const target = new Vector2(0, 0);
  const pointer = new Vector2(0, 0);
  const raycaster = new Raycaster();
  raycaster.params.Points = { threshold: 0.28 };
  const v = new Vector3();

  const layout = () => {
    const { clientWidth: w, clientHeight: h } = canvas;
    const mobile = w < 640;
    group.position.set(mobile ? 0 : 2.4 * side, mobile ? -3.2 : -0.4, 0);
    group.scale.setScalar(mobile ? 0.62 : 1);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
  };
  const resizeObserver = new ResizeObserver(layout);
  resizeObserver.observe(canvas);
  layout();

  const reportActive = () => {
    if (active === null) return onHover(null, 0, 0);
    v.set(nodes.pos[active * 3], nodes.pos[active * 3 + 1], nodes.pos[active * 3 + 2])
      .applyMatrix4(group.matrixWorld)
      .project(camera);
    onHover(active, ((v.x + 1) / 2) * canvas.clientWidth, ((1 - v.y) / 2) * canvas.clientHeight);
  };

  const draw = (ms: number) => {
    const t = ms / 1000;
    const breathe = 1 + 0.035 * Math.sin(t * 0.7);
    group.rotation.y += (target.x * 0.22 + Math.sin(t * 0.15) * 0.08 - group.rotation.y) * 0.04;
    group.rotation.x += (-target.y * 0.14 - group.rotation.x) * 0.04;
    for (let i = 0; i < n; i++) {
      const r = rays[i];
      const c = colors[i];
      const on = i === active;
      const dim = active !== null && !on ? 0.35 : 1;
      const len = r.length * (breathe + 0.025 * Math.sin(t * 1.3 + i));
      const x = r.x * len;
      const y = r.y * len;
      const z = r.z * len;
      const boost = on ? 1.6 : 1;
      rayPos.set([0, 0, 0, x, y, z], i * 6);
      rayCol.set(
        [
          c.r * 0.05,
          c.g * 0.05,
          c.b * 0.05,
          c.r * dim * boost,
          c.g * dim * boost,
          c.b * dim * boost,
        ],
        i * 6,
      );
      nodes.pos.set([x, y, z], i * 3);
      const lift = on ? 0.4 : 0;
      nodes.col.set(
        [
          Math.min(1, c.r * dim + lift),
          Math.min(1, c.g * dim + lift),
          Math.min(1, c.b * dim + lift),
        ],
        i * 3,
      );
      nodes.size[i] = on ? 1.5 : 0.55 + 0.15 * Math.sin(t * 2 + i);
      for (let k = 0; k < SPARKS; k++) {
        const p = (t * 0.12 + k / SPARKS + (i % 7) * 0.031) % 1;
        const j = i * SPARKS + k;
        const a = Math.sin(Math.PI * p) * dim;
        sparks.pos.set([x * p, y * p, z * p], j * 3);
        sparks.col.set([c.r * a, c.g * a, c.b * a], j * 3);
        sparks.size[j] = 0.22;
      }
    }
    for (const geo of [rayGeo, nodes.geo, sparks.geo]) {
      for (const name of Object.keys(geo.attributes)) geo.attributes[name].needsUpdate = true;
    }
    core.geo.attributes.color.needsUpdate = true;
    renderer.render(scene, camera);
    reportActive();
    if (running) frame = requestAnimationFrame(draw);
  };
  frame = requestAnimationFrame(draw);

  const onPointerMove = (e: PointerEvent) => {
    const rect = canvas.getBoundingClientRect();
    pointer.set(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1,
    );
    target.copy(pointer);
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObject(nodes.points)[0];
    active = hit?.index ?? null;
  };
  const onPointerLeave = () => {
    target.set(0, 0);
    active = null;
  };
  const host = canvas.parentElement ?? canvas;
  host.addEventListener('pointermove', onPointerMove);
  host.addEventListener('pointerleave', onPointerLeave);

  return {
    setActive: (index) => {
      active = index;
    },
    setPalette: (next) => {
      palette = next;
      colors = sectorColors(rays, next.stops);
      dark = next.dark;
      applyBlending();
    },
    setSide: (next) => {
      side = next;
      layout();
    },
    setRunning: (next) => {
      if (next === running) return;
      running = next;
      if (running) frame = requestAnimationFrame(draw);
      else cancelAnimationFrame(frame);
    },
    dispose: () => {
      running = false;
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      host.removeEventListener('pointermove', onPointerMove);
      host.removeEventListener('pointerleave', onPointerLeave);
      for (const geo of [rayGeo, nodes.geo, sparks.geo, core.geo]) geo.dispose();
      rayMat.dispose();
      pointMaterial.dispose();
      renderer.dispose();
    },
  };
};
