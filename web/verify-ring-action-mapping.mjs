import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRingActionMapping, mapRingActionFrame } from './src/ring-action-mapping.js';
import { parseActionClip } from './src/action-library.js';
const sensors = JSON.parse(await readFile(new URL('./public/assets/ring-model.json', import.meta.url))).sensors;
const manifest = JSON.parse(await readFile(new URL('./public/action-library/manifest.json', import.meta.url)));
let clips = 0;
for (const entry of manifest.filter(d => d.sensorCount === 18)) {
  const clip = parseActionClip(JSON.parse(await readFile(new URL(`./public${entry.url}`, import.meta.url))));
  const mapping = createRingActionMapping(clip.coordinates, sensors);
  assert.equal(new Set(mapping).size, 18);
  assert.deepEqual(createRingActionMapping(clip.coordinates, [...sensors].reverse()), mapping);
  for (let source = 0; source < 18; source++) {
    const values = Array(18).fill(0); values[source] = 1;
    const mapped = mapRingActionFrame({ values, rawVolts: Array(18).fill(2) }, mapping);
    assert.equal(mapped.values.reduce((a,b)=>a+b,0),1);
    assert.equal(mapped.values[mapping[source]],1);
    const coordinate = clip.coordinates[source];
    const slot = (coordinate.row - coordinate.column + 6) % 6;
    const x = sensors[mapping[source]].position[0];
    assert(slot === 0 ? x < 10 : slot === 1 ? x > 10 && x < 16 : x > 16);
  }
  for (const frame of clip.frames) {
    const mapped = mapRingActionFrame(frame, mapping);
    mapping.forEach((target,source)=>assert(Math.abs(mapped.values[target]-frame.values[source])<1e-6));
    for (let i=0;i<96;i++) if (!mapping.includes(i)) assert.equal(mapped.values[i],0);
  }
  clips++;
}
assert.equal(clips,3);
console.log('PASS: all 3 current clips map to 18 unique Ring crossings; axial tiers, isolated node activation, frame values and unused crossings verified');
