import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { parseActionClip } from './src/action-library.js';
const manifest = JSON.parse(await readFile(new URL('./public/action-library/manifest.json', import.meta.url)));
assert.equal(manifest.length, 17);
assert.equal(new Set(manifest.map(d => d.id)).size, 17);
const groups = new Map();
let frames = 0; let missing = 0;
for (const entry of manifest) {
  const text = await readFile(new URL(`./public${entry.url}`, import.meta.url), 'utf8');
  const data = JSON.parse(text); const clip = parseActionClip(data);
  assert.equal(clip.frames.length, entry.frames);
  assert.equal(clip.sensorCount, entry.sensorCount);
  assert.equal(clip.frames.length, clip.times.length);
  assert(clip.frames.every(f => f.values.length === clip.sensorCount && f.values.every(Number.isFinite)));
  assert(clip.times.every((t,i) => i === 0 ? t === 0 : Math.abs(t-clip.times[i-1]-.05)<1e-5));
  assert.equal(new Set(clip.coordinates.map(p => `${p.row},${p.column}`)).size, clip.sensorCount);
  if (clip.sensorCount === 18) {
    for (const p of clip.coordinates) assert((p.row - p.column + 6) % 6 < 3);
  }
  groups.set(entry.group, (groups.get(entry.group)||0)+1);
  missing += clip.missingSamples; frames += clip.frames.length;
  assert.equal(await readFile(new URL(`./dist${entry.url}`, import.meta.url), 'utf8'), text);
}
assert.deepEqual([...groups.values()], [4,10,3]);
assert.throws(() => parseActionClip({sensorCount:18,signal:[[1]],labels:[],times:[0]}));
console.log(`PASS: 17 entries (4 delivered Robot arm + 10 Human arm + 3 Finger Direct), ${frames} playback frames, correct sparse coordinates, timing and built assets; ${missing} missing measurements retained as null in source JSON`);
