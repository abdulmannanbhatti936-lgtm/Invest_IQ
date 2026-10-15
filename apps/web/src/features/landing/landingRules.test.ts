// Run with: npm test (Node's built-in test runner)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { bloomMode, hash, rayLayout, sectorCount, zoomFrame } from './landingRules.ts';

const capable = { reducedMotion: false, webgl: true, cores: 8, saveData: false };

test('the bloom animates only on a capable device without a reduced-motion request', () => {
  assert.equal(bloomMode(capable), 'animated');
  assert.equal(bloomMode({ ...capable, cores: undefined }), 'animated');
});

test('reduced motion, no WebGL, a low-power device or Save-Data get the static image', () => {
  assert.equal(bloomMode({ ...capable, reducedMotion: true }), 'static');
  assert.equal(bloomMode({ ...capable, webgl: false }), 'static');
  assert.equal(bloomMode({ ...capable, cores: 4 }), 'static');
  assert.equal(bloomMode({ ...capable, saveData: true }), 'static');
});

test('rays are deterministic and independent of anything but ticker and sector', () => {
  const companies = [
    { ticker: 'HBL', sector: 'Commercial Banks' },
    { ticker: 'LUCK', sector: 'Cement' },
  ];
  assert.deepEqual(rayLayout(companies), rayLayout(companies));
  assert.equal(hash('HBL'), hash('HBL'));
  assert.notEqual(hash('HBL'), hash('UBL'));
});

test('each sector owns its own slice of the fan, in alphabetical order', () => {
  const rays = rayLayout([
    { ticker: 'HBL', sector: 'Commercial Banks' },
    { ticker: 'LUCK', sector: 'Cement' },
    { ticker: 'UBL', sector: 'Commercial Banks' },
  ]);
  assert.deepEqual(
    rays.map((r) => r.sectorIndex),
    [1, 0, 1],
  );
  for (const r of rays) {
    assert.ok(r.length >= 3 && r.length <= 5.6);
    assert.ok(Math.abs(Math.hypot(r.x, r.y / 0.9, r.z / 0.6) - 1) < 1e-9);
  }
});

test('the sector-only list (no tickers) still gives one ray per company', () => {
  const rays = rayLayout([{ sector: 'Cement' }, { sector: 'Cement' }, { sector: 'Fertilizer' }]);
  assert.equal(rays.length, 3);
  assert.notDeepEqual(rays[0], rays[1]);
  assert.equal(
    sectorCount([{ sector: 'Cement' }, { sector: 'Fertilizer' }, { sector: 'Cement' }]),
    2,
  );
});

const view = { cover: 1.8, centerOffset: 120, viewportHeight: 900, reducedMotion: false };

test('zoom: headline alone first, the screenshot below the fold', () => {
  const f = zoomFrame(0, view);
  assert.equal(f.headlineOpacity, 1);
  assert.equal(f.screenY, 120 + 900);
  assert.equal(f.scale, 1.8);
  assert.equal(f.frameOpacity, 0);
});

test('zoom: at the end the screenshot sits in the device with the headline above it', () => {
  const f = zoomFrame(1, view);
  assert.equal(f.screenY, 0);
  assert.equal(f.scale, 1);
  assert.equal(f.frameOpacity, 1);
  assert.equal(f.headlineOpacity, 1);
  assert.equal(f.headlineScale, 0.7);
});

test('zoom: reduced motion shows the final frame at any scroll position', () => {
  const f = zoomFrame(0.1, { ...view, reducedMotion: true });
  assert.deepEqual(f, zoomFrame(1, view));
});
