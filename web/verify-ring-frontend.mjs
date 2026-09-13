// Runs the actual model loaders and heatmap computation with Three.js geometry.
// Rendering/UI are stubbed; this does not replace a visual browser check.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import * as THREE from 'three';

const source = await readFile(new URL('./src/main.js', import.meta.url), 'utf8');
const asset = JSON.parse(await readFile(new URL('./public/assets/ring-model.json', import.meta.url), 'utf8'));
const hash = createHash('sha256').update(await readFile(new URL('../models/tactile/ring.gh', import.meta.url))).digest('hex');
assert.equal(asset.metadata.sourceSha256, hash);
assert.equal(asset.metadata.stripWidth, 3);
const armAsset = JSON.parse(await readFile(new URL('./public/assets/model.json', import.meta.url), 'utf8'));
assert.equal(armAsset.metadata.stripWidth, 4);
assert.equal(armAsset.metadata.sourceSha256,
  createHash('sha256').update(await readFile(new URL('../models/tactile/1.gh', import.meta.url))).digest('hex'));
assert.equal(asset.sensors.length, 30);
assert.equal(asset.geometry.positions.length, asset.metadata.vertexCount * 3);
assert.equal(asset.geometry.normals.length, asset.geometry.positions.length);
assert.equal(asset.geometry.colors.length, asset.geometry.positions.length);
assert.equal(asset.geometry.indices.length, asset.metadata.triangleCount * 3);
assert(asset.geometry.positions.every(Number.isFinite));
assert(asset.geometry.normals.every(Number.isFinite));
assert(asset.geometry.indices.every((i) => Number.isInteger(i) && i >= 0 && i < asset.metadata.vertexCount));
assert.equal(new Set(asset.sensors.map((s) => s.position.join(','))).size, 30);
assert(asset.sensors.every((s, i) => s.index === i && s.position[0] > 0.01 && s.position[0] < 26.99));

const state = {
  modelMode: 'ring', opacity: 0.6, modelCenter: new THREE.Vector3(), modelSize: new THREE.Vector3(),
  values: new Float32Array(96), radius: 3, threshold: 0, gain: 1,
};
const buttons = [{}, {}];
const elements = Object.fromEntries(['pointCount', 'modelMeta', 'modelStatus', 'modelLength',
  'modelFrontDiameter', 'modelRearDiameter', 'modelMessage'].map((key) => [key, {}]));
elements.modelControl = { querySelectorAll: () => buttons };
elements.modelLoading = { classList: { add() {} } };
const modelGroup = new THREE.Group();
const controls = { target: new THREE.Vector3() };
const raycaster = new THREE.Raycaster();
const document = { querySelector: () => ({ checked: true }), querySelectorAll: () => [] };
let matrixCount;
const buildSensorMatrix = () => { matrixCount = state.activeSensorCount; };
const fetch = async (url) => ({ ok: true, json: async () => JSON.parse(await readFile(new URL(`./public${url}`, import.meta.url), 'utf8')) });
const helpers = source.slice(source.indexOf('function computeSensorAngles('), source.indexOf('async function loadModel('));
const loaders = source.slice(source.indexOf('async function loadModel('), source.indexOf('const workingColor ='));
const heatmap = source.slice(source.indexOf('const workingColor ='), source.indexOf('function updateMatrix('));
const run = new Function('THREE', 'state', 'elements', 'modelGroup', 'controls', 'raycaster',
  'document', 'buildSensorMatrix', 'fetch', 'requestAnimationFrame', `
  const ROWS = 12, COLUMNS = 8, SENSOR_COUNT = 96, RING_SENSOR_COUNT = 30;
  let cameraTween = null;
  const fitCamera = () => {};
  const applyPresentation = async () => {};
  const colorAt = (v, palette, target) => target.setRGB(v, v * 0.5, 1 - v);
  ${helpers}\n${loaders}\n${heatmap}
  return {loadModel, updateHeatmap};
`)(THREE, state, elements, modelGroup, controls, raycaster, document,
  buildSensorMatrix, fetch, (callback) => callback());

await run.loadModel();
assert.equal(matrixCount, 30);
assert.equal(modelGroup.children.length, 2, 'mesh and crossing markers only');
assert.equal(state.geometry.attributes.position.count, asset.metadata.vertexCount);
assert.deepEqual(state.sensorPositions.map((p) => p.toArray()), asset.sensors.map((s) => s.position));
assert.equal(state.sensorAngles.length, 30);
assert(state.sensorAngles.every((a) => a > 0 && a <= 90));
assert.equal(state.distanceMatrix.length, asset.metadata.vertexCount * 30);
assert.equal(state.sensorPoints.visible, true);
assert.equal(state.material.opacity, 0.6);
assert.equal(buttons.every((b) => b.disabled === false), true);

run.updateHeatmap();
const baseline = state.geometry.attributes.color.array.slice();
state.values[0] = 1;
state.heatDirty = true;
run.updateHeatmap();
const active = state.geometry.attributes.color.array;
let changed = 0;
for (let i = 0; i < active.length; i += 3) {
  if (active[i] !== baseline[i]) changed += 1;
}
assert(changed > 0 && changed < asset.metadata.vertexCount, 'single crossing produces a local heat field');
assert(active.every(Number.isFinite));

let disposed = false;
state.geometry.addEventListener('dispose', () => { disposed = true; });
state.modelMode = 'arm';
await run.loadModel();
assert(disposed);
assert.equal(matrixCount, 96);
assert.equal(state.sensorPositions.length, 96);
assert.equal(state.distanceMatrix.length, state.geometry.attributes.position.count * 96);
run.updateHeatmap();
state.modelMode = 'ring';
await run.loadModel();
run.updateHeatmap();
assert.equal(matrixCount, 30);
assert.equal(modelGroup.children.length, 2);
assert.equal(state.geometry.attributes.position.count, asset.metadata.vertexCount);
console.log(`PASS: GH asset identity, mesh integrity, 30 crossings, localized heat (${changed} vertices), Arm/Ring switching and disposal`);
