import assert from 'node:assert/strict';
import fs from 'node:fs';
import {parseActionClip} from './src/action-library.js';
import {currentFrameDetails} from './src/playback-data-preview.js';
const base=new URL('./public/',import.meta.url);
const manifest=JSON.parse(fs.readFileSync(new URL('action-library/manifest.json',base)));
for(const m of manifest){const c=parseActionClip(JSON.parse(fs.readFileSync(new URL(m.url.slice(1),base))));for(const i of [0,Math.floor(c.frames.length/2),c.frames.length-1]){const d=currentFrameDetails(c,c.frames[i],i);assert.deepEqual(d.values,c.signal[i]);assert.deepEqual(d.raw,c.raw[i]);assert.deepEqual(d.baseline,c.baseline[i]);assert.equal(d.time,c.times[i]);}assert.match(currentFrameDetails(c,c.frames[0],0).sampling,/Measured frame/);}
const c={fps:20,signal:Array.from({length:11},()=>[null,.5]),measuredTimes:[0,1],sourceFrames:[8,9]};const d=currentFrameDetails(c,{values:[0,.5]},10);assert.equal(d.values[0],null);assert.match(d.sampling,/Interpolated: measured 8 → 9/);assert.equal(d.maximum,.5);
assert.match(currentFrameDetails(c,{values:[0,.5]},21).sampling,/Hold of measured frame 9/);
console.log('PASS: current signal/raw/baseline match all 9 clips; missing values and interpolated/held source frames identified.');
