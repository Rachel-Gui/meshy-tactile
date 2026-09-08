import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const bytes = await readFile(new URL('./public/assets/arm-mannequin.glb', import.meta.url));
const gltf = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
const mannequin = gltf.scene;
mannequin.updateMatrixWorld(true);
const mesh = mannequin.children[0];
assert(mesh.geometry.attributes.position.count > 10000);
assert([...mesh.geometry.attributes.position.array].every(Number.isFinite));
assert(mesh.material.roughness > 0.5 && mesh.material.metalness === 0);
const bounds = new THREE.Box3().setFromObject(mannequin);
assert(bounds.min.x < -190 && bounds.max.z > 150, 'hand and bent upper arm extend beyond the sleeve');

const payload = JSON.parse(await readFile(new URL('./public/assets/model.json', import.meta.url), 'utf8'));
const p = payload.geometry.positions;
const ray = new THREE.Raycaster();
const gaps=[];
for(let i=0;i<p.length;i+=3*97){
  const point=new THREE.Vector3(p[i],p[i+1],p[i+2]);
  if(point.x<5||point.x>245) continue;
  ray.set(point,new THREE.Vector3(0,-point.y,-point.z).normalize());
  const hit=ray.intersectObject(mannequin,true)[0];
  assert(hit,'Each sampled strip point should have arm beneath it');
  assert(hit.distance>0.5&&hit.distance<3.5,`Fit gap ${hit.distance}`);
  gaps.push(hit.distance);
}
assert(gaps.length>50);

// Execute the actual scene switching function, with the real GLB and geometry.
const source=await readFile(new URL('./src/main.js',import.meta.url),'utf8');
const start=source.indexOf('async function applyPresentation()');
const code=source.slice(start,source.indexOf('const raycaster =',start));
const state={modelMode:'arm',presentation:'wearing',modelCenter:new THREE.Vector3(),modelSize:new THREE.Vector3(),sensorPoints:{material:{}}};
const scene=new THREE.Scene();
const modelGroup=new THREE.Group();
const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(p,3));
modelGroup.add(new THREE.Mesh(geometry,new THREE.MeshBasicMaterial()));scene.add(modelGroup);
const grid=new THREE.Object3D();const controls={};
const nodes=new Map();const document={querySelector:(key)=>{if(!nodes.has(key))nodes.set(key,{});return nodes.get(key);},querySelectorAll:()=>[]};
const apply=new Function('THREE','state','scene','modelGroup','grid','controls','document','GLTFLoader',`
 let armMannequin=null,armMannequinPromise=null;const fitCamera=()=>{};
 ${code}
 return applyPresentation;
`)(THREE,state,scene,modelGroup,grid,controls,document,class{async loadAsync(){return gltf;}});
await apply();assert(mannequin.visible);assert(state.modelSize.x>450);assert(state.sensorPoints.material.depthTest);
state.presentation='sensor';await apply();assert(!mannequin.visible);assert(state.modelSize.x<260);
state.presentation='wearing';state.modelMode='ring';await apply();assert(!mannequin.visible);assert(nodes.get('#scene-options').hidden);
state.modelMode='arm';await apply();assert(mannequin.visible);assert.equal(scene.children.filter(c=>c===mannequin).length,1);
console.log(`PASS: white GLB, ${gaps.length} fit samples (${Math.min(...gaps).toFixed(2)}–${Math.max(...gaps).toFixed(2)} mm), scene visibility, camera bounds, cached switching`);
