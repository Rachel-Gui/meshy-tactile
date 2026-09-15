import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as THREE from 'three';
import {createFingerPair} from './src/finger-pair.js';
const nodes=new Map();
function node(key){if(!nodes.has(key))nodes.set(key,{value:'0',listeners:{},classList:{toggle(){}},setAttribute(){},addEventListener(e,fn){this.listeners[e]=fn;}});return nodes.get(key);}
const select=[node('A'),node('B')],inputs=[node('fileA'),node('fileB')];
const panel={querySelector:node,querySelectorAll:q=>q==='[data-select]'?select:inputs};
globalThis.document={createElement:()=>({getContext:()=>({fillRect(){},fillText(){}})})};
const pair=createFingerPair(panel,(v,p,c)=>c.setRGB(v,0,1-v));
const asset=JSON.parse(readFileSync(new URL('public/assets/ring-model.json',import.meta.url)));
const geometry=new THREE.BufferGeometry();
geometry.setAttribute('position',new THREE.Float32BufferAttribute(asset.geometry.positions,3));
geometry.setAttribute('color',new THREE.Float32BufferAttribute(asset.geometry.colors,3));
const model=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial());
const points=new THREE.Points(geometry.clone(),new THREE.PointsMaterial());
const matrix=new Float32Array(geometry.attributes.position.count*30);
const sensors=asset.sensors.map(s=>new THREE.Vector3(...s.position));
pair.prepare(model,points,matrix,sensors);pair.group.visible=true;
const pivots=pair.group.children.filter(x=>x.isGroup);
assert.equal(pivots.length,2);
assert.notEqual(pivots[0].children[0].geometry,pivots[1].children[0].geometry);
assert.notEqual(pivots[0].children[0].material,pivots[1].children[0].material);
const bPosition=pivots[1].position.clone();
node('[data-angle]').value='90';node('[data-angle]').listeners.input();
assert.equal(pivots[0].rotation.x,Math.PI/2);assert.equal(pivots[1].rotation.x,0);assert(pivots[1].position.equals(bPosition));
select[1].listeners.click();node('[data-angle]').value='-45';node('[data-angle]').listeners.input();
assert.equal(pivots[0].rotation.x,Math.PI/2);assert.equal(pivots[1].rotation.x,-Math.PI/4);
const header=Array.from({length:18},(_,i)=>'N'+String(i+1).padStart(3,'0')).join(',');
for(const [i,value] of [1,0].entries()){
 const csv=header+'\n'+Array(18).fill(value).join(',');
 inputs[i].files=[{name:`${i}.csv`,size:csv.length,text:async()=>csv}];await inputs[i].listeners.change();
 assert(node(`[data-file-status="${i}"]`).textContent.includes('1 frames'));
}
pair.update(0,{radius:3,threshold:0,gain:1,palette:'thermal',opacity:1,sensorPoints:{visible:true}});
assert.equal(pivots[0].children[0].geometry.attributes.color.getX(0),1);
assert.equal(pivots[1].children[0].geometry.attributes.color.getX(0),0);
console.log('PASS: A/B have independent geometry, independent uploads/heatmaps, and independent axial rotation.');
