import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import {parsePlaybackCsv} from './src/playback-csv.js';
import {createRingActionMapping} from './src/ring-action-mapping.js';
const root=new URL('../',import.meta.url),base=new URL('public/',import.meta.url);
const pairs=JSON.parse(fs.readFileSync(new URL('delivery-final/finger-pairs.json',base)));
const model=JSON.parse(fs.readFileSync(new URL('assets/ring-model.json',base)));
assert.equal(pairs.length,3);assert.equal(pairs.reduce((n,p)=>n+p.keyframes.length,0),16);
for(const pair of pairs)for(const sleeve of ['A','B']){
 const bytes=fs.readFileSync(new URL(pair[sleeve].slice(1),base));assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),pair[sleeve+'Sha256']);
 assert.deepEqual(bytes,fs.readFileSync(new URL('meshy_arm_finger_delivery_20260914/finger/'+pair[sleeve].split('/').at(-1),root)));
 const clip=parsePlaybackCsv(bytes.toString(),18);assert.equal(clip.frames.length,pair.frames);assert.equal(clip.sensorCount,18);
 const mapping=createRingActionMapping(clip.coordinates,model.sensors.map((s,index)=>({index,position:s.position})));assert.equal(new Set(mapping).size,18);
 for(const k of pair.keyframes){assert.equal(clip.times[k.index],k.time);assert(Math.max(...clip.frames[k.index].values)>0);}
}
const robot=JSON.parse(fs.readFileSync(new URL('action-library/delivery_robot_all.json',base)));
const source=parsePlaybackCsv(fs.readFileSync(new URL(robot.source,root),'utf8'),132);assert.equal(robot.signal.length,938);
for(let i=0;i<938;i++)for(let j=0;j<132;j++)assert(Math.abs(source.frames[i].values[j]-robot.signal[i][j])<1e-8);
assert.deepEqual(robot.keyframes.map(k=>k.index),[257,538,887]);
console.log('PASS: all delivered A/B CSV bytes, 16 paired keys, mapping uniqueness and all 123816 Robot signal samples verified.');
