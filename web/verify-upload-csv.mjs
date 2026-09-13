import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {parsePlaybackCsv} from './src/playback-csv.js';
import {createRingActionMapping} from './src/ring-action-mapping.js';
const sensors=JSON.parse(await readFile(new URL('./public/assets/ring-model.json',import.meta.url))).sensors;
const fixture=(count=18,rows=['0,0','1,1'])=>['action_time_s,'+Array.from({length:count},(_,i)=>`N${String(i+1).padStart(3,'0')}`).join(','),...rows.map(r=>{const[t,v]=r.split(',');return [t,...Array(count).fill(v)].join(',');})].join('\n');
for(const count of [18,96,132]){const p=parsePlaybackCsv(fixture(count));assert.equal(p.sensorCount,count);assert.equal(p.frames.length,21);assert.equal(p.frames[10].values[0],.5);assert.equal(p.frames.at(-1).values[0],1);if(count===18)assert.equal(new Set(createRingActionMapping(p.coordinates,sensors)).size,18);}
assert.throws(()=>parsePlaybackCsv(fixture(19)),/consecutive/);
assert.throws(()=>parsePlaybackCsv(fixture(18,['0,0','0,1'])),/increasing/);
assert.throws(()=>parsePlaybackCsv(fixture(18,['0,2'])),/Signal Combined/);
assert.throws(()=>parsePlaybackCsv(fixture().replace('N018','N017')),/duplicate/);
assert.throws(()=>parsePlaybackCsv(fixture().replace('0,0,0','0,,0')),/Missing/);
const quoted=parsePlaybackCsv('\uFEFF'+fixture().replace('action_time_s','"action_time_s"').replaceAll('\n','\r\n'));assert.equal(quoted.frames.length,21);
assert.equal(parsePlaybackCsv(fixture().replaceAll(',',';')).frames.length,21);
const legacy=['scan_index,raw_voltage_v,signal_0_to_1',...Array.from({length:96},(_,i)=>`${i+1},1.5,0.2`)].join('\n');assert.equal(parsePlaybackCsv(legacy).frames.length,1);
if(process.argv[2]){
 for(const f of JSON.parse(await readFile(process.argv[2]))){const p=parsePlaybackCsv(await readFile(f.file,'utf8'));assert.equal(p.sensorCount,f.count);assert.equal(p.originalFrames,f.frames);assert.deepEqual(p.frames[0].values,f.first);p.frames.at(-1).values.forEach((v,i)=>assert(Math.abs(v-f.last[i])<1e-8));assert(p.times.at(-1)>=f.duration-1e-8);assert(p.times.at(-1)-f.duration<.050001);assert(p.recordedAt);}
}
console.log('PASS: 18/96/132 detection, interpolation, release endpoints, timestamps, sparse mapping, quoted CSV, malformed input and legacy CSV.');
