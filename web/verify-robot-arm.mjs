import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const model=JSON.parse(await readFile(new URL('./public/assets/robot-arm-model.json',import.meta.url)));
const {metadata:m,geometry:g,sensors}=model;
assert.equal(m.length,250);assert.equal(m.frontDiameter,32);assert.equal(m.rearDiameter,32);
assert.equal(sensors.length,132);assert.equal(new Set(sensors.map(s=>s.node)).size,132);
const pos=[];
for(let i=0;i<g.positions.length;i+=3)pos.push(g.positions.slice(i,i+3));
assert(Math.abs(Math.min(...pos.map(p=>p[0])))<1e-6);assert(Math.abs(Math.max(...pos.map(p=>p[0]))-250)<1e-6);
assert.equal(m.endBandWidth,5);assert.equal(m.endBandCount,2);
assert(pos.slice(0,m.bandStartVertex).every(p=>Math.abs(Math.hypot(p[1],p[2])-16)<1e-4));
assert(pos.slice(m.bandStartVertex).every(p=>[16.1,16.3].some(r=>Math.abs(Math.hypot(p[1],p[2])-r)<1e-4)&&(p[0]<=5||p[0]>=245)));
assert(g.indices.every(i=>Number.isInteger(i)&&i>=0&&i<pos.length));
for(const s of sensors){
 const t=s.position[0]/250,angle=Math.atan2(s.position[2],s.position[1]);
 const c=s.displayColumn-1,r=s.displayRow;
 assert(Math.abs(t-r/12)<1e-8);
 const wrap=a=>Math.atan2(Math.sin(a),Math.cos(a));
 assert(Math.abs(wrap(angle-(2*Math.PI*c/12+Math.PI*t)))<1e-8);
 assert(Math.abs(wrap(angle-(2*Math.PI*((c+r)%12)/12-Math.PI*t)))<1e-8);
}
const manifest=JSON.parse(await readFile(new URL('./public/action-library/manifest.json',import.meta.url)));
for(const entry of manifest.filter(d=>d.sensorCount===132)){
 const clip=JSON.parse(await readFile(new URL('./public'+entry.url,import.meta.url)));
 assert.deepEqual(clip.labels,sensors.map(s=>s.node));
 assert.deepEqual(clip.coordinates,sensors.map(s=>({row:s.displayRow,column:s.displayColumn})));
 assert(clip.signal.every(row=>row.length===132&&row.every(v=>Number.isFinite(v)&&v>=0&&v<=1)));
}
assert.equal(await readFile(new URL('./dist/assets/robot-arm-model.json',import.meta.url),'utf8'),await readFile(new URL('./public/assets/robot-arm-model.json',import.meta.url),'utf8'));
console.log('PASS: 250 × Ø32 mm mesh; 132 unique interior intersections on both helical families; all three clips match node labels and coordinates; deployed asset identical.');
