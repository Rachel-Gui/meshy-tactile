import { createFingerHandScene } from './finger-hand-scene.js';
import { zipSync, strToU8 } from 'fflate';
import { createCameraCapture, recordStream, nearestFrame } from './camera-capture.js';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { parsePlaybackCsv } from './playback-csv.js';
import { parseActionClip } from './action-library.js';
import { createPlaybackDataPreview } from './playback-data-preview.js';
import { createRingActionMapping, mapRingActionFrame } from './ring-action-mapping.js';
import { WebSerialSensor, webSerialSupported } from './web-serial-sensor.js';
import './styles.css';

const ROWS = 12;
const COLUMNS = 8;
const SENSOR_COUNT = ROWS * COLUMNS;
const RING_SENSOR_COUNT = 30;
const ROBOT_SENSOR_COUNT = 132;
const modelForCount = count => count === 132 ? 'robot' : count === 18 ? 'ring' : 'arm';
const HOSTED_MODE = import.meta.env.PROD
  && !['localhost', '127.0.0.1'].includes(location.hostname);
const HOSTED_DATASETS = [];


const state = {
  model: null,
  geometry: null,
  material: null,
  sensorPoints: null,
  sensorPositions: [],
  distanceMatrix: null,
  sensorAngles: new Float32Array(ROBOT_SENSOR_COUNT),
  values: new Float32Array(ROBOT_SENSOR_COUNT),
  rawVolts: new Float32Array(ROBOT_SENSOR_COUNT),
  radius: 25,
  gain: 1,
  threshold: 0,
  opacity: 1,
  palette: 'thermal',
  selectedSensor: null,
  heatDirty: true,
  lastSequence: -1,
  frameCounter: 0,
  frameCounterStarted: performance.now(),
  modelCenter: new THREE.Vector3(),
  modelSize: new THREE.Vector3(250, 124, 124),
  modelMetadata: null,
  recording: null,
  playbackScrubbing: false,
  playbackPlaying: true,
  playbackFps: 15,
  autoClearCount: 0,
  sourceMode: 'playback',
  modelMode: 'arm',
  activeSensorCount: SENSOR_COUNT,
  hostedDatasets: new Map(HOSTED_DATASETS.map((dataset) => [dataset.id, dataset])),
  hostedPlaybackFrames: null,
  actionClip: null,
  ringActionMapping: null,
  playbackRequest: 0,
  hostedPlaybackIndex: 0,
  hostedLastFrameAt: 0,
  hostedStartedAt: performance.now(),
  hostedSequence: 0,
  hostedAutoClearEnabled: true,
};

const elements = {
  viewport: document.querySelector('#viewport'),
  modelLoading: document.querySelector('#model-loading'),
  modelStatus: document.querySelector('#model-status'),
  pointCount: document.querySelector('#point-count'),
  connectionPill: document.querySelector('#connection-pill'),
  connectionText: document.querySelector('#connection-text'),
  sourceMessage: document.querySelector('#source-message'),
  portSelect: document.querySelector('#port-select'),
  playbackSelect: document.querySelector('#playback-select'),
  playbackUpload: document.querySelector('#playback-upload'),
  playbackFile: document.querySelector('#playback-file'),
  playbackUploadButton: document.querySelector('#playback-upload-button'),
  playbackUploadStatus: document.querySelector('#playback-upload-status'),
  playbackPreview: document.querySelector('#playback-preview'),
  playbackPreviewTitle: document.querySelector('#playback-preview-title'),
  playbackPreviewMeta: document.querySelector('#playback-preview-meta'),
  playbackPreviewSample: document.querySelector('#playback-preview-sample'),
  playbackTimeline: document.querySelector('#playback-timeline'),
  playbackToggle: document.querySelector('#playback-toggle'),
  playbackScrubber: document.querySelector('#playback-scrubber'),
  playbackCurrentTime: document.querySelector('#playback-current-time'),
  playbackTotalTime: document.querySelector('#playback-total-time'),
  playbackFrameLabel: document.querySelector('#playback-frame-label'),
  sensorMatrix: document.querySelector('#sensor-matrix'),
  frameRate: document.querySelector('#frame-rate'),
  frameSequence: document.querySelector('#frame-sequence'),
  modelMeta: document.querySelector('#model-meta'),
  modelLength: document.querySelector('#model-length'),
  modelFrontDiameter: document.querySelector('#model-front-diameter'),
  modelRearDiameter: document.querySelector('#model-rear-diameter'),
  modelMessage: document.querySelector('#model-message'),
  selectedCard: document.querySelector('#selected-card'),
  selectedIndex: document.querySelector('#selected-index'),
  selectedValue: document.querySelector('#selected-value'),
  selectedVoltage: document.querySelector('#selected-voltage'),
  selectedAngle: document.querySelector('#selected-angle'),
  legend: document.querySelector('#legend'),
  recordStart: document.querySelector('#record-start'),
  recordClear: document.querySelector('#record-clear'),
  recordStop: document.querySelector('#record-stop'),
  autoClear: document.querySelector('#auto-clear'),
  recordingStatus: document.querySelector('#recording-status'),
  recordingMeta: document.querySelector('#recording-meta'),
  recordingMessage: document.querySelector('#recording-message'),
  modelControl: document.querySelector('#model-control'),
};

const hostedSerialSensor = HOSTED_MODE && webSerialSupported()
  ? new WebSerialSensor({
    onFrame: (frame) => applyFramePayload({
      type: 'frame',
      mode: 'serial',
      connected: true,
      port: frame.label,
      error: null,
      sequence: ++state.hostedSequence,
      timestamp: Date.now() / 1000,
      values: frame.values,
      rawVolts: frame.rawVolts,
      autoClearEnabled: frame.autoClearEnabled,
      autoClearCount: frame.autoClearCount,
    }),
    onStatus: updateHostedSerialStatus,
  })
  : null;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x070a12);

const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 4000);
camera.up.set(0, 0, 1);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;
elements.viewport.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.055;
controls.screenSpacePanning = true;
controls.minDistance = 45;
controls.maxDistance = 1200;

scene.add(new THREE.HemisphereLight(0xa8c8ff, 0x101421, 1.65));
const keyLight = new THREE.DirectionalLight(0xffffff, 2.0);
keyLight.position.set(-120, -160, 220);
scene.add(keyLight);
const rimLight = new THREE.DirectionalLight(0x55bbff, 1.7);
rimLight.position.set(260, 120, 80);
scene.add(rimLight);

const grid = new THREE.GridHelper(520, 26, 0x263a57, 0x162136);
grid.rotation.x = Math.PI / 2;
grid.position.z = -72;
grid.material.transparent = true;
grid.material.opacity = 0.34;
scene.add(grid);

function applyTheme(theme) {
  const light = theme === 'light';
  document.documentElement.dataset.theme = light ? 'light' : 'dark';
  localStorage.setItem('tactile-theme', light ? 'light' : 'dark');
  scene.background.set(light ? 0xf4f6f9 : 0x070a12);
  grid.material.opacity = light ? 0.24 : 0.34;
  renderer.toneMappingExposure = light ? 1.02 : 1.12;
  document.querySelector('#theme-icon').textContent = light ? '☾' : '☀';
  document.querySelector('#theme-label').textContent = light ? 'Dark' : 'Light';
}

document.querySelector('#theme-toggle').addEventListener('click', () => {
  const nextTheme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  applyTheme(nextTheme);
});

applyTheme(localStorage.getItem('tactile-theme') ?? 'dark');

const modelGroup = new THREE.Group();
scene.add(modelGroup);
const fingerHand = createFingerHandScene();
fingerHand.visible = false;
scene.add(fingerHand);
const fingerSceneControl = document.querySelector('#finger-scene-control');
const fingerHandToggle = document.querySelector('#finger-hand-toggle');
fingerHandToggle.addEventListener('change', () => applyPresentation());
async function applyPresentation() {
  await fingerHand.userData.ready;
  fingerSceneControl.hidden = state.modelMode !== 'ring';
  fingerHand.visible = state.modelMode === 'ring' && fingerHandToggle.checked;
  const bounds = new THREE.Box3().setFromObject(modelGroup);
  if (fingerHand.visible) bounds.union(new THREE.Box3().setFromObject(fingerHand));
  bounds.getCenter(state.modelCenter);
  bounds.getSize(state.modelSize);
  grid.position.z = -72;
  grid.scale.setScalar(1);
  controls.maxDistance = state.modelMode === 'ring' ? (fingerHand.visible ? 650 : 250) : 1200;
  if (state.sensorPoints) state.sensorPoints.material.depthTest = false;
  fitCamera('perspective', false);
}

const raycaster = new THREE.Raycaster();
raycaster.params.Points.threshold = 5;
const mouse = new THREE.Vector2();
let cameraTween = null;

const paletteStops = {
  thermal: [
    [0.00, '#141e6e'], [0.25, '#00aaff'], [0.50, '#1edc78'],
    [0.75, '#ffdc00'], [1.00, '#e61e14'],
  ],
  plasma: [
    [0.00, '#180b3d'], [0.25, '#6f1d91'], [0.50, '#cc4778'],
    [0.75, '#f89540'], [1.00, '#f0f921'],
  ],
  mono: [
    [0.00, '#081529'], [0.30, '#094d73'], [0.62, '#19b9ca'], [1.00, '#d9ffff'],
  ],
};

function createPaletteLookup(stops) {
  const lookup = new Float32Array(256 * 3);
  for (let colorIndex = 0; colorIndex < 256; colorIndex += 1) {
    const value = colorIndex / 255;
    for (let stopIndex = 0; stopIndex < stops.length - 1; stopIndex += 1) {
      const [startT, startHex] = stops[stopIndex];
      const [endT, endHex] = stops[stopIndex + 1];
      if (value <= endT) {
        const amount = (value - startT) / (endT - startT);
        const color = new THREE.Color(startHex).lerp(new THREE.Color(endHex), amount);
        lookup[colorIndex * 3] = color.r;
        lookup[colorIndex * 3 + 1] = color.g;
        lookup[colorIndex * 3 + 2] = color.b;
        break;
      }
    }
  }
  return lookup;
}

const paletteLookups = Object.fromEntries(
  Object.entries(paletteStops).map(([name, stops]) => [name, createPaletteLookup(stops)]),
);

function colorAt(value, palette = state.palette, target = new THREE.Color()) {
  const clamped = Math.max(0, Math.min(1, value));
  const lookup = paletteLookups[palette];
  const index = Math.round(clamped * 255) * 3;
  return target.setRGB(lookup[index], lookup[index + 1], lookup[index + 2]);
}

function updateLegend() {
  elements.legend.style.background = `linear-gradient(90deg, ${paletteStops[state.palette].map(([, color]) => color).join(',')})`;
}

function buildSensorMatrix() {
  elements.sensorMatrix.replaceChildren();
  elements.sensorMatrix.style.gridTemplateColumns = `repeat(${state.modelMode === 'robot' ? 12 : state.modelMode === 'ring' ? 10 : COLUMNS}, 1fr)`;
  document.querySelector('.matrix-section .section-heading span').textContent = state.modelMode === 'robot' ? '11 × 12' : state.modelMode === 'ring' ? '3 × 10' : '12 × 8';
  document.querySelector('.matrix-labels').textContent = state.modelMode === 'robot' ? '132 nodes · workbook display layout' : state.modelMode === 'ring' ? 'Ring crossings' : 'A strips · offset 1 → 8';
  const fragment = document.createDocumentFragment();
  for (let index = 0; index < state.activeSensorCount; index += 1) {
    const button = document.createElement('button');
    button.className = 'sensor-cell';
    button.type = 'button';
    button.dataset.index = String(index);
    button.title = state.modelMode === 'ring'
      ? `Crossing ${String(index + 1).padStart(2, '0')}`
      : `A${String(Math.floor(index / COLUMNS) + 1).padStart(2, '0')} · offset ${(index % COLUMNS) + 1}`;
    if (state.modelMode === 'robot') button.title = state.actionClip?.labels[index] || `Node ${index + 1}`;
    if (state.sourceMode === 'playback' && state.modelMode === 'ring' && state.ringActionMapping) {
      const source = state.ringActionMapping.indexOf(index);
      button.title = source < 0 ? `Crossing ${index + 1} · no input` : `${state.actionClip.labels[source]} → Crossing ${index + 1}`;
    }
    button.addEventListener('click', () => selectSensor(index));
    fragment.appendChild(button);
  }
  elements.sensorMatrix.appendChild(fragment);
}

function selectSensor(index) {
  state.selectedSensor = index;
  document.querySelectorAll('.sensor-cell').forEach((cell, cellIndex) => {
    cell.classList.toggle('selected', cellIndex === index);
  });
  elements.selectedCard.classList.add('visible');
  updateSelectedCard();
}

function updateSelectedCard() {
  if (state.selectedSensor === null) return;
  const index = state.selectedSensor;
  if (state.modelMode === 'ring') {
    const source = state.sourceMode === 'playback' ? state.ringActionMapping?.indexOf(index) : undefined;
    elements.selectedIndex.textContent = `Crossing ${String(index + 1).padStart(2, '0')}${source >= 0 ? ` · ${state.actionClip.labels[source]}` : source === -1 ? ' · no input' : ''}`;
  } else if (state.modelMode === 'robot') {
    elements.selectedIndex.textContent = state.actionClip?.labels[index] || `Node ${index + 1}`;
  } else {
    const row = Math.floor(index / COLUMNS) + 1;
    const column = (index % COLUMNS) + 1;
    elements.selectedIndex.textContent = `A${String(row).padStart(2, '0')} · ${String(column).padStart(2, '0')}`;
  }
  elements.selectedValue.textContent = `${Math.round(state.values[index] * 100)}%`;
  elements.selectedVoltage.textContent = Number.isFinite(state.rawVolts[index]) ? `${state.rawVolts[index].toFixed(3)} V` : '—';
  const angle = state.sensorAngles[index];
  elements.selectedAngle.textContent = `Strip angle ${angle > 0 ? `${angle.toFixed(1)}°` : '—'}`;
}

function computeSensorAngles(positions) {
  const count = positions.length;
  const angles = new Float32Array(count);
  const physicalColumn = (row, slot) => (row + slot + 1) % ROWS;

  for (let index = 0; index < count; index += 1) {
    const row = Math.floor(index / COLUMNS);
    const slot = index % COLUMNS;
    const current = positions[index];
    const previousA = slot > 0 ? positions[index - 1] : null;
    const nextA = slot < COLUMNS - 1 ? positions[index + 1] : null;
    const tangentA = new THREE.Vector3();
    if (previousA && nextA) tangentA.subVectors(nextA, previousA);
    else if (nextA) tangentA.subVectors(nextA, current);
    else if (previousA) tangentA.subVectors(current, previousA);

    const sameColumn = [];
    const targetColumn = physicalColumn(row, slot);
    for (let candidate = 0; candidate < count; candidate += 1) {
      if (candidate === index) continue;
      const candidateRow = Math.floor(candidate / COLUMNS);
      const candidateSlot = candidate % COLUMNS;
      if (physicalColumn(candidateRow, candidateSlot) === targetColumn) {
        sameColumn.push({ index: candidate, row: candidateRow });
      }
    }
    sameColumn.sort((a, b) => Math.abs(a.row - row) - Math.abs(b.row - row));
    const tangentB = new THREE.Vector3();
    if (sameColumn.length > 1) {
      const first = positions[sameColumn[0].index];
      const second = positions[sameColumn[1].index];
      tangentB.subVectors(second, first);
    } else if (sameColumn.length === 1) {
      tangentB.subVectors(positions[sameColumn[0].index], current);
    }

    if (tangentA.lengthSq() > 0 && tangentB.lengthSq() > 0) {
      const cosine = Math.abs(tangentA.normalize().dot(tangentB.normalize()));
      angles[index] = Math.acos(Math.min(1, Math.max(0, cosine))) * 180 / Math.PI;
    }
  }
  return angles;
}

function endDiameter(positions, bounds, fromFront) {
  const band = Math.max(1, bounds.max.x - bounds.min.x) * 0.03;
  const edge = fromFront ? bounds.min.x + band : bounds.max.x - band;
  let minY = Infinity;
  let maxY = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;

  for (let index = 0; index < positions.length; index += 3) {
    const x = positions[index];
    if (fromFront ? x > edge : x < edge) continue;
    minY = Math.min(minY, positions[index + 1]);
    maxY = Math.max(maxY, positions[index + 1]);
    minZ = Math.min(minZ, positions[index + 2]);
    maxZ = Math.max(maxZ, positions[index + 2]);
  }

  return Math.max(maxY - minY, maxZ - minZ);
}

function modelSensorIndex(channelIndex) {
  const rowStart = Math.floor(channelIndex / COLUMNS) * COLUMNS;
  const pointInRow = channelIndex % COLUMNS;
  return rowStart + (COLUMNS - 1 - pointInRow);
}

async function loadModel() {
  const buttons = [...elements.modelControl.querySelectorAll('button')];
  buttons.forEach((button) => { button.disabled = true; });
  state.distanceMatrix = null;
  state.model = null;
  state.geometry = null;
  state.material = null;
  state.sensorPoints = null;
  cameraTween = null;
  modelGroup.traverse((object) => {
    object.geometry?.dispose();
    object.material?.dispose();
  });
  modelGroup.clear();
  const ring = state.modelMode === 'ring';
  state.activeSensorCount = state.modelMode === 'robot' ? ROBOT_SENSOR_COUNT : ring ? RING_SENSOR_COUNT : SENSOR_COUNT;
  state.selectedSensor = null;
  elements.selectedCard.classList.remove('visible');
  controls.minDistance = ring ? 15 : 45;
  controls.maxDistance = ring ? 250 : 1200;
  raycaster.params.Points.threshold = ring ? 0.7 : 5;
  buildSensorMatrix();
  try {
    if (ring) await loadRingModel();
    else await loadArmModel();
    await applyPresentation();
    document.querySelector('#source-control button[data-mode="serial"]').disabled = state.modelMode === 'robot' || (HOSTED_MODE && !hostedSerialSensor);
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

async function loadRingModel() {
  const response = await fetch('/assets/ring-model.json', { cache: 'no-store' });
  if (!response.ok) throw new Error(`Ring model request failed: ${response.status}`);
  const payload = await response.json();
  if (payload.metadata.sensorCount !== RING_SENSOR_COUNT || payload.sensors.length !== RING_SENSOR_COUNT) {
    throw new Error('Ring model must contain 30 internal sensor crossings');
  }
  const source = payload.geometry;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(source.positions, 3));
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(source.normals, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(source.colors, 3));
  geometry.setIndex(source.indices);
  geometry.computeBoundingSphere();
  const material = new THREE.MeshStandardMaterial({
    vertexColors: true, side: THREE.DoubleSide, metalness: 0.02, roughness: 0.62,
    opacity: state.opacity, transparent: state.opacity < 0.999,
  });
  const model = new THREE.Mesh(geometry, material);
  model.name = 'Ring Grasshopper strips';
  modelGroup.add(model);

  // Preserve SensorIntersections order; these are internal strip crossings.
  const sensorPositions = payload.sensors.map((sensor) => new THREE.Vector3(...sensor.position));
  const markerGeometry = new THREE.BufferGeometry().setFromPoints(sensorPositions);
  markerGeometry.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(RING_SENSOR_COUNT * 3), 3));
  const sensorPoints = new THREE.Points(markerGeometry, new THREE.PointsMaterial({
    size: 0.8, sizeAttenuation: true, vertexColors: true,
    transparent: true, opacity: 0.95, depthTest: false,
  }));
  sensorPoints.visible = document.querySelector('#show-sensors').checked;
  sensorPoints.renderOrder = 10;
  modelGroup.add(sensorPoints);

  geometry.computeBoundingBox();
  geometry.boundingBox.getCenter(state.modelCenter);
  geometry.boundingBox.getSize(state.modelSize);
  controls.target.copy(state.modelCenter);
  state.model = model;
  state.modelMetadata = payload.metadata;
  state.geometry = geometry;
  state.material = material;
  state.sensorPoints = sensorPoints;
  state.sensorPositions = sensorPositions;
  state.sensorAngles = Float32Array.from(payload.sensors, (sensor) => sensor.crossingAngle);
  elements.pointCount.textContent = String(RING_SENSOR_COUNT);
  elements.modelMeta.textContent = `${payload.metadata.vertexCount.toLocaleString()} vertices`;
  elements.modelStatus.textContent = 'Ring mesh';
  elements.modelLength.textContent = String(payload.metadata.length);
  elements.modelFrontDiameter.textContent = String(payload.metadata.frontDiameter);
  elements.modelRearDiameter.textContent = String(payload.metadata.rearDiameter);
  elements.modelMessage.textContent = `30 internal sensor crossings · ${payload.metadata.stripWidth} mm strips`;
  fitCamera('perspective', false);
  await precomputeDistances();
  state.heatDirty = true;
  elements.modelLoading.classList.add('hidden');
}


async function loadArmModel() {
  modelGroup.clear();
  const robot = state.modelMode === 'robot';
  state.activeSensorCount = robot ? ROBOT_SENSOR_COUNT : SENSOR_COUNT;
  const response = await fetch(robot ? '/assets/robot-arm-model.json' : '/assets/model.json', { cache: 'no-store' });
  if (!response.ok) throw new Error(`Model download failed: ${response.status}`);
  if (!response.ok) throw new Error(`Model request failed: ${response.status}`);
  const payload = await response.json();
  const source = payload.geometry;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(source.positions, 3));
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(source.normals, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(source.colors, 3));
  geometry.setIndex(source.indices);
  geometry.computeBoundingSphere();

  const material = new THREE.MeshStandardMaterial({
    vertexColors: true,
    side: THREE.DoubleSide,
    metalness: 0.02,
    roughness: 0.62,
    transparent: state.opacity < 0.999,
    opacity: state.opacity,
  });
  const model = new THREE.Mesh(geometry, material);
  model.name = 'Heatmap strips';
  modelGroup.add(model);

  // The physical channels run from the large end toward the small end, while
  // Grasshopper exports each row in the opposite direction. Reverse the eight
  // points within every row so channel 1 maps to the large end and channel 8
  // maps to the small end without changing the incoming channel numbering.
  const sensorPositions = Array.from(
    { length: state.activeSensorCount },
    (_, channelIndex) => new THREE.Vector3(
      ...payload.sensors[robot ? channelIndex : modelSensorIndex(channelIndex)].position,
    ),
  );
  const markerGeometry = new THREE.BufferGeometry().setFromPoints(sensorPositions);
  markerGeometry.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(state.activeSensorCount * 3), 3));
  const markerMaterial = new THREE.PointsMaterial({
    size: 4.0,
    sizeAttenuation: true,
    vertexColors: true,
    transparent: true,
    opacity: 0.95,
    depthTest: false,
  });
  const sensorPoints = new THREE.Points(markerGeometry, markerMaterial);
  sensorPoints.visible = document.querySelector('#show-sensors').checked;
  sensorPoints.renderOrder = 10;
  modelGroup.add(sensorPoints);

  geometry.computeBoundingBox();
  geometry.boundingBox.getCenter(state.modelCenter);
  geometry.boundingBox.getSize(state.modelSize);
  controls.target.copy(state.modelCenter);

  state.model = model;
  state.modelMetadata = payload.metadata;
  state.geometry = geometry;
  state.material = material;
  state.sensorPoints = sensorPoints;
  state.sensorPositions = sensorPositions;
  state.sensorAngles = robot ? new Float32Array(payload.sensors.map(s => s.crossingAngle || 0)) : computeSensorAngles(sensorPositions);

  elements.pointCount.textContent = String(payload.metadata.sensorCount);
  elements.modelMeta.textContent = `${payload.metadata.vertexCount.toLocaleString()} vertices`;
  elements.modelStatus.textContent = robot ? 'Robot arm · GH mesh' : 'GH live mesh';
  elements.modelMessage.textContent = `${state.activeSensorCount} sensor crossings · ${payload.metadata.stripWidth} mm strips`;
  elements.modelLength.textContent = (payload.metadata.length ?? state.modelSize.x).toFixed(1);
  elements.modelFrontDiameter.textContent = (payload.metadata.frontDiameter ?? endDiameter(source.positions, geometry.boundingBox, true)).toFixed(1);
  elements.modelRearDiameter.textContent = (payload.metadata.rearDiameter ?? endDiameter(source.positions, geometry.boundingBox, false)).toFixed(1);
  fitCamera('perspective', false);
  await precomputeDistances();
  state.heatDirty = true;
  elements.modelLoading.classList.add('hidden');
}

async function precomputeDistances() {
  const positions = state.geometry.attributes.position.array;
  const vertexCount = positions.length / 3;
  const sensorCount = state.activeSensorCount;
  const distances = new Float32Array(vertexCount * sensorCount);

  for (let vertexIndex = 0; vertexIndex < vertexCount; vertexIndex += 1) {
    const x = positions[vertexIndex * 3];
    const y = positions[vertexIndex * 3 + 1];
    const z = positions[vertexIndex * 3 + 2];
    const offset = vertexIndex * sensorCount;
    for (let sensorIndex = 0; sensorIndex < sensorCount; sensorIndex += 1) {
      const sensor = state.sensorPositions[sensorIndex];
      distances[offset + sensorIndex] = Math.hypot(x - sensor.x, y - sensor.y, z - sensor.z);
    }
    if (vertexIndex > 0 && vertexIndex % 3000 === 0) {
      await new Promise(requestAnimationFrame);
    }
  }
  state.distanceMatrix = distances;
}

const workingColor = new THREE.Color();
function updateHeatmap() {
  if (!state.geometry || !state.distanceMatrix) return;
  const colors = state.geometry.attributes.color.array;
  const markerColors = state.sensorPoints.geometry.attributes.color.array;
  const vertexCount = colors.length / 3;
  const denominator = Math.max(0.001, 1 - state.threshold);
  const sensorCount = state.activeSensorCount;
  const adjustedValues = new Float32Array(sensorCount);

  for (let sensorIndex = 0; sensorIndex < sensorCount; sensorIndex += 1) {
    const adjusted = Math.min(1, Math.max(0, (state.values[sensorIndex] - state.threshold) / denominator) * state.gain);
    adjustedValues[sensorIndex] = adjusted;
    markerColors[sensorIndex * 3] = 0.82;
    markerColors[sensorIndex * 3 + 1] = 0.85;
    markerColors[sensorIndex * 3 + 2] = 0.9;
  }

  for (let vertexIndex = 0; vertexIndex < vertexCount; vertexIndex += 1) {
    let strongest = 0;
    const distanceOffset = vertexIndex * sensorCount;
    for (let sensorIndex = 0; sensorIndex < sensorCount; sensorIndex += 1) {
      const distance = state.distanceMatrix[distanceOffset + sensorIndex];
      if (distance >= state.radius) continue;
      const adjusted = adjustedValues[sensorIndex];
      if (adjusted <= 0.001) continue;
      const amount = 1 - distance / state.radius;
      const falloff = amount * amount * (3 - 2 * amount);
      strongest = Math.max(strongest, adjusted * falloff);
    }
    colorAt(strongest, state.palette, workingColor);
    colors[vertexIndex * 3] = workingColor.r;
    colors[vertexIndex * 3 + 1] = workingColor.g;
    colors[vertexIndex * 3 + 2] = workingColor.b;
  }

  state.geometry.attributes.color.needsUpdate = true;
  state.sensorPoints.geometry.attributes.color.needsUpdate = true;
  state.heatDirty = false;
}

function updateMatrix() {
  document.querySelectorAll('.sensor-cell').forEach((cell, index) => {
    const value = state.values[index];
    colorAt(value, state.palette, workingColor);
    cell.style.backgroundColor = `#${workingColor.getHexString()}`;
  });
  updateSelectedCard();
}

function recordingFilename(stamp, suffix) {
  return `tactile-recording-${stamp}.${suffix}`;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function recordingStamp(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, '-');
}

function recordingMimeType() {
  const candidates = [
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
  ];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) ?? '';
}

function updateRecordingUi() {
  const recording = state.recording;
  const active = Boolean(recording);
  elements.recordStart.disabled = active;
  elements.recordStop.disabled = !active || recording.stopping;
  cameraCapture.update();
  elements.recordStart.textContent = active ? 'Recording…' : 'Start recording';
  elements.recordingStatus.textContent = active ? 'REC' : 'Ready';
  elements.recordingStatus.classList.toggle('recording-live', active);
}

async function clearLiveData() {
  state.values.fill(0);
  state.rawVolts.fill(0);
  state.heatDirty = true;
  updateMatrix();
  if (HOSTED_MODE) {
    hostedSerialSensor?.resetCalibration();
    elements.recordingMessage.classList.remove('error');
    elements.recordingMessage.textContent = state.sourceMode === 'serial'
      ? 'Live data cleared — keep the sensor untouched briefly'
      : 'Browser data cleared';
    return;
  }
  try {
    const response = await fetch('/api/calibrate', { method: 'POST' });
    if (!response.ok) throw new Error('Clear request failed');
    elements.recordingMessage.classList.remove('error');
    elements.recordingMessage.textContent = 'Live data cleared — keep the sensor untouched briefly';
  } catch (error) {
    elements.recordingMessage.classList.add('error');
    elements.recordingMessage.textContent = error.message;
  }
}

const cameraCapture = createCameraCapture(() => state.recording, message => {
  elements.recordingMessage.textContent = message;
  elements.recordingMessage.classList.add('error');
});

async function startRecording() {
  if (state.recording) return;
  let recording;
  try {
    if (!window.MediaRecorder || !renderer.domElement.captureStream) throw new Error('This browser does not support video recording.');
    const mimeType = recordingMimeType();
    if (!mimeType) throw new Error('No supported WebM video format was found.');
    recording = { startedAt: new Date(), startedPerformance: performance.now(), frames: [], mimeType,
      model: structuredClone(state.modelMetadata), settings: { radius: state.radius, gain: state.gain, threshold: state.threshold, opacity: state.opacity, palette: state.palette } };
    cameraCapture.start(recording, mimeType);
    recording.stream = renderer.domElement.captureStream(30);
    recording.modelRecording = recordStream(recording.stream, recording.startedPerformance, mimeType);
    state.recording = recording;
    elements.recordingMessage.classList.remove('error');
    elements.recordingMessage.textContent = 'Recording · Space to take a photo · keep this tab visible';
    elements.recordingMeta.textContent = '0 frames · 0:00';
    updateRecordingUi();
  } catch (error) {
    await recording?.cameraRecording?.stop();
    recording?.stream?.getTracks().forEach(track => track.stop());
    elements.recordingMessage.textContent = error.message;
    elements.recordingMessage.classList.add('error');
  }
}

async function stopRecording() {
  const recording = state.recording;
  if (!recording || recording.stopping) return;
  recording.stopping = true;
  recording.durationMs = performance.now() - recording.startedPerformance;
  updateRecordingUi();
  elements.recordingMessage.textContent = 'Preparing ZIP…';
  try {
    const [modelVideo, cameraVideo] = await Promise.all([recording.modelRecording.stop(), recording.cameraRecording?.stop(), Promise.all(recording.pendingPhotos)]);
    const files = { 'model.webm': new Uint8Array(await modelVideo.arrayBuffer()) };
    if (cameraVideo) files['camera.webm'] = new Uint8Array(await cameraVideo.arrayBuffer());
    const photos = await Promise.all(recording.photos.map(async ({ blob, ...entry }) => {
      if (blob) files[entry.filename] = new Uint8Array(await blob.arrayBuffer());
      return { ...entry, nearestSensorFrame: nearestFrame(recording.frames, entry.tMs) };
    }));
    const payload = {
      cameraDisconnectedMs: recording.cameraDisconnectedMs ?? null,
      format: 'tactile-sensor-recording-v2', startedAt: recording.startedAt.toISOString(),
      endedAt: new Date(recording.startedAt.getTime() + recording.durationMs).toISOString(), durationMs: recording.durationMs,
      clock: { basis: 'performance.now relative to session start', epochStartMs: recording.startedAt.getTime(), sensorTime: 'browser frame receipt; original timestamp preserved separately', cameraTime: 'browser canvas draw/photo click; not hardware exposure time', videoAlignment: 'camera video displays session seconds on each image; recorder event offsets are approximate', deltaConvention: 'nearest sensor tMs minus photo tMs' },
      video: { filename: 'model.webm', mimeType: recording.mimeType, ...recording.modelRecording.timing },
      cameraVideo: cameraVideo ? { filename: 'camera.webm', mimeType: recording.mimeType, ...recording.cameraRecording.timing, renderedFrames: recording.cameraFrames } : null,
      model: recording.model, settings: recording.settings, photos, frames: recording.frames,
    };
    files['alignment.json'] = strToU8(JSON.stringify(payload, null, 2));
    files['sensor-timestamps.csv'] = strToU8('frame_index,session_ms,epoch_ms,source_timestamp,sequence,mode\n' + recording.frames.map((frame, i) => [i, frame.tMs, recording.startedAt.getTime() + frame.tMs, frame.timestamp, frame.sequence, frame.mode].map(value => JSON.stringify(value ?? '')).join(',')).join('\n'));
    downloadBlob(new Blob([zipSync(files, { level: 0 })], { type: 'application/zip' }), recordingFilename(recordingStamp(recording.startedAt), 'zip'));
    elements.recordingMessage.classList.remove('error');
    elements.recordingMessage.textContent = `Saved ZIP · ${recording.frames.length} sensor frames · ${photos.length} photos${cameraVideo ? ' · camera video' : ''}`;
    state.recording = null;
  } catch (error) {
    recording.stopping = false;
    elements.recordingMessage.textContent = `Export failed: ${error.message}. Click Stop & save to retry.`;
    elements.recordingMessage.classList.add('error');
  } finally {
    recording.stream.getTracks().forEach(track => track.stop());
    updateRecordingUi();
  }
}

window.addEventListener('beforeunload', event => {
  if (state.recording) { event.preventDefault(); event.returnValue = ''; }
});

elements.recordStart.addEventListener('click', startRecording);
elements.recordStop.addEventListener('click', stopRecording);
elements.recordClear.addEventListener('click', clearLiveData);
elements.autoClear.addEventListener('change', async () => {
  const enabled = elements.autoClear.checked;
  if (HOSTED_MODE) {
    state.hostedAutoClearEnabled = enabled;
    hostedSerialSensor?.setAutoClearEnabled(enabled);
    elements.recordingMessage.classList.remove('error');
    elements.recordingMessage.textContent = enabled
      ? 'Auto clear enabled · resets stable residual data after 5 seconds'
      : 'Auto clear disabled';
    return;
  }
  elements.autoClear.disabled = true;
  try {
    const response = await fetch('/api/auto-clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail ?? 'Auto clear update failed');
    elements.recordingMessage.classList.remove('error');
    elements.recordingMessage.textContent = enabled
      ? `Auto clear enabled · resets stable residual data after ${payload.idleSeconds} seconds`
      : 'Auto clear disabled';
  } catch (error) {
    elements.autoClear.checked = !enabled;
    elements.recordingMessage.classList.add('error');
    elements.recordingMessage.textContent = error.message;
  } finally {
    elements.autoClear.disabled = false;
  }
});
updateRecordingUi();

function cameraPose(view) {
  const center = state.modelCenter;
  const diagonal = state.modelSize.length();
  const distance = Math.max(state.modelMode === 'ring' ? 35 : 170, diagonal * 1.45);
  const poses = {
    perspective: new THREE.Vector3(center.x - distance * 0.65, center.y + distance * (fingerHand.visible ? 0.85 : -0.85), center.z + distance * 0.72),
    front: new THREE.Vector3(center.x - distance, center.y, center.z),
    back: new THREE.Vector3(center.x + distance, center.y, center.z),
    left: new THREE.Vector3(center.x, center.y - distance, center.z),
    right: new THREE.Vector3(center.x, center.y + distance, center.z),
    top: new THREE.Vector3(center.x, center.y, center.z + distance),
  };
  return poses[view] ?? poses.perspective;
}

function fitCamera(view = 'perspective', animated = true) {
  const destination = cameraPose(view);
  const target = state.modelCenter.clone();
  if (!animated) {
    camera.position.copy(destination);
    controls.target.copy(target);
    controls.update();
    return;
  }
  cameraTween = {
    start: performance.now(),
    duration: 620,
    fromPosition: camera.position.clone(),
    toPosition: destination,
    fromTarget: controls.target.clone(),
    toTarget: target,
  };
}

function updateCameraTween(now) {
  if (!cameraTween) return;
  const progress = Math.min(1, (now - cameraTween.start) / cameraTween.duration);
  const eased = 1 - Math.pow(1 - progress, 3);
  camera.position.lerpVectors(cameraTween.fromPosition, cameraTween.toPosition, eased);
  controls.target.lerpVectors(cameraTween.fromTarget, cameraTween.toTarget, eased);
  if (progress >= 1) cameraTween = null;
}

function resize() {
  const { clientWidth, clientHeight } = elements.viewport;
  renderer.setSize(clientWidth, clientHeight, false);
  camera.aspect = clientWidth / Math.max(1, clientHeight);
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(elements.viewport);

function animate(now) {
  requestAnimationFrame(animate);
  updateCameraTween(now);
  if (HOSTED_MODE || state.sourceMode === 'playback') updateHostedRuntime(now);
  if (state.heatDirty) updateHeatmap();
  controls.update();
  renderer.render(scene, camera);
}

renderer.domElement.addEventListener('pointerdown', (event) => {
  if (!state.sensorPoints?.visible) return;
  const rect = renderer.domElement.getBoundingClientRect();
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(mouse, camera);
  const hit = raycaster.intersectObject(state.sensorPoints)[0];
  if (hit) selectSensor(hit.index);
});

function setRangeFill(input) {
  const min = Number(input.min);
  const max = Number(input.max);
  const percent = ((Number(input.value) - min) / (max - min)) * 100;
  input.style.setProperty('--fill', `${percent}%`);
}

function bindRange(id, stateKey, formatter) {
  const input = document.querySelector(`#${id}`);
  const output = document.querySelector(`#${id}-output`);
  const update = () => {
    state[stateKey] = Number(input.value);
    output.textContent = formatter(state[stateKey]);
    setRangeFill(input);
    state.heatDirty = true;
  };
  input.addEventListener('input', update);
  update();
}

bindRange('radius', 'radius', (value) => Number(value.toFixed(1)).toString());
bindRange('gain', 'gain', (value) => `${value.toFixed(2)}×`);
bindRange('threshold', 'threshold', (value) => `${Math.round(value * 100)}%`);
bindRange('opacity', 'opacity', (value) => `${Math.round(value * 100)}%`);

document.querySelector('#opacity').addEventListener('input', () => {
  if (!state.material) return;
  state.material.opacity = state.opacity;
  state.material.transparent = state.opacity < 0.999;
  state.material.needsUpdate = true;
});

document.querySelector('#palette').addEventListener('change', (event) => {
  state.palette = event.target.value;
  state.heatDirty = true;
  updateLegend();
  updateMatrix();
});

document.querySelector('#show-sensors').addEventListener('change', (event) => {
  if (state.sensorPoints) state.sensorPoints.visible = event.target.checked;
});
document.querySelector('#show-grid').addEventListener('change', (event) => {
  grid.visible = event.target.checked;
});

document.querySelector('#reset-heatmap').addEventListener('click', () => {
  const defaults = { radius: state.modelMode === 'ring' ? 3 : state.modelMode === 'robot' ? 10 : 25, gain: 1, threshold: 0, opacity: 1 };
  Object.entries(defaults).forEach(([id, value]) => {
    const input = document.querySelector(`#${id}`);
    input.value = String(value);
    input.dispatchEvent(new Event('input'));
  });
  document.querySelector('#palette').value = 'thermal';
  document.querySelector('#palette').dispatchEvent(new Event('change'));
});

function apiUrl(path) {
  return path;
}

async function refreshPorts() {
  try {
    const response = await fetch(apiUrl('/api/ports'));
    const payload = await response.json();
    elements.portSelect.querySelectorAll('option:not(:first-child)').forEach((option) => option.remove());
    payload.ports.forEach((port) => {
      const option = document.createElement('option');
      option.value = port;
      option.textContent = port;
      elements.portSelect.appendChild(option);
    });
  } catch {
    // WebSocket status will communicate backend availability.
  }
}

function renderHostedPlaybackOptions(selectedDataset = null) {
  elements.playbackSelect.replaceChildren(new Option('Choose an action', ''));
  const groups = new Map();
  state.hostedDatasets.forEach(dataset => {
    const mode = modelForCount(dataset.sensorCount || dataset.parsed?.sensorCount);
    if (mode !== state.modelMode) return;
    const name = `${mode === 'robot' ? 'Robot arm' : mode === 'arm' ? 'Human arm' : 'Finger'} · ${dataset.group || 'Uploaded recordings'}`;
    if (!groups.has(name)) {
      const group = document.createElement('optgroup'); group.label = name;
      groups.set(name, group); elements.playbackSelect.append(group);
    }
    groups.get(name).append(new Option(dataset.uploadedAt ? `NEW · ${dataset.label} · ${new Date(dataset.uploadedAt).toLocaleString()}` : dataset.label, dataset.id));
  });
  if (selectedDataset && state.hostedDatasets.has(selectedDataset)) elements.playbackSelect.value = selectedDataset;
}

async function loadHostedDataset(datasetId) {
  const dataset = state.hostedDatasets.get(datasetId);
  if (!dataset) throw new Error('Playback dataset was not found');
  if (!dataset.parsed) {
    const response = await fetch(dataset.url);
    if (!response.ok) throw new Error(`Recording download failed: ${response.status}`);
    dataset.parsed = dataset.url.endsWith('.json')
      ? parseActionClip(await response.json()) : parsePlaybackCsv(await response.text(), SENSOR_COUNT);
  }
  return dataset;
}

async function refreshPlaybackDatasets(selectedDataset = null) {
  try {
    const response = await fetch('/action-library/manifest.json');
    if (!response.ok) throw new Error('Could not load the action library');
    const datasets = await response.json();
    for (const [id, entry] of state.hostedDatasets) if (entry.url) state.hostedDatasets.delete(id);
    datasets.forEach(dataset => {
      if (!state.hostedDatasets.has(dataset.id)) state.hostedDatasets.set(dataset.id, dataset);
    });
    renderHostedPlaybackOptions(selectedDataset);
    return datasets;
  } catch (error) {
    elements.sourceMessage.textContent = error.message;
    elements.sourceMessage.classList.add('error');
    return [];
  }
}

function readUploadOwners() {
  try { return JSON.parse(localStorage.getItem('tactile-upload-owners') || '{}'); }
  catch { return {}; }
}
async function uploadError(response) {
  try { const data = await response.json(); return typeof data.detail === 'string' ? data.detail : 'Upload service unavailable'; }
  catch { return 'Shared upload service unavailable. Connect to the app server.'; }
}
function updateUploadActions(dataset) {
  const share = document.querySelector('#share-upload');
  const remove = document.querySelector('#delete-upload');
  share.hidden = !dataset?.shareId;
  remove.hidden = !dataset?.shareId || !readUploadOwners()[dataset.shareId];
  document.querySelector('#upload-share-link').hidden = true;
}
document.querySelector('#share-upload').addEventListener('click', async () => {
  const dataset = state.hostedDatasets.get(elements.playbackSelect.value);
  if (!dataset?.shareId) return;
  const url = new URL(location.href); url.search = ''; url.hash = ''; url.searchParams.set('upload', dataset.shareId);
  const input = document.querySelector('#upload-share-link'); input.value = url.href; input.hidden = false; input.select();
  try { await navigator.clipboard.writeText(url.href); elements.sourceMessage.textContent = 'Share link copied'; }
  catch { elements.sourceMessage.textContent = 'Copy the preview link below'; }
});
document.querySelector('#delete-upload').addEventListener('click', async () => {
  const dataset = state.hostedDatasets.get(elements.playbackSelect.value);
  if (!dataset?.shareId || !confirm(`Delete “${dataset.label}”? Its shared link will stop working.`)) return;
  const button = document.querySelector('#delete-upload'); button.disabled = true;
  try {
    const owners = readUploadOwners();
    const response = await fetch(`/api/shared-uploads/${dataset.shareId}`, {method:'DELETE',headers:{Authorization:`Bearer ${owners[dataset.shareId] || ''}`}});
    if (!response.ok) throw new Error(await uploadError(response));
    delete owners[dataset.shareId]; localStorage.setItem('tactile-upload-owners', JSON.stringify(owners));
    state.hostedDatasets.delete(dataset.id);
    const fallback = [...state.hostedDatasets.values()].find(d=>modelForCount(d.sensorCount)===state.modelMode);
    renderHostedPlaybackOptions(fallback?.id); updateUploadActions(null);
    await previewPlaybackDataset(fallback?.id || '');
    const url=new URL(location.href); url.searchParams.delete('upload');history.replaceState(null,'',url);
    elements.sourceMessage.textContent = 'Upload deleted; shared link disabled';
  } catch (error) { elements.sourceMessage.textContent = error.message; }
  finally { button.disabled = false; }
});
async function restoreSharedUploads() {
  const sharedId = new URLSearchParams(location.search).get('upload');
  const ids = new Set([...Object.keys(readUploadOwners()), ...(sharedId ? [sharedId] : [])]);
  await Promise.all([...ids].map(async id => {
    try {
      const response = await fetch(`/api/shared-uploads/${encodeURIComponent(id)}`);
      if (!response.ok) {
        if (response.status === 404) {const owners=readUploadOwners();delete owners[id];localStorage.setItem('tactile-upload-owners',JSON.stringify(owners));}
        if (id===sharedId) throw new Error(await uploadError(response));
        return;
      }
      const dataset=await response.json();state.hostedDatasets.set(dataset.id,dataset);
    } catch(error) { if(id===sharedId) elements.sourceMessage.textContent=error.message; }
  }));
  return sharedId ? state.hostedDatasets.get(`shared_${sharedId}`) : null;
}

elements.playbackUploadButton.addEventListener('click', () => elements.playbackFile.click());

elements.playbackFile.addEventListener('change', async () => {
  const file = elements.playbackFile.files?.[0];
  if (!file) return;

  elements.playbackUpload.classList.remove('error');
  elements.playbackUpload.classList.add('uploading');
  elements.playbackUploadButton.disabled = true;
  elements.playbackUploadButton.textContent = 'Uploading…';
  elements.playbackUploadStatus.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;

  try {
    if (file.size > 3 * 1024 * 1024) throw new Error('CSV must be 3 MB or smaller');
    {
      const csv = await file.text();
      const parsed = parsePlaybackCsv(csv, SENSOR_COUNT);
      const owners = readUploadOwners();
      // Check storage before uploading: the private deletion key must survive refresh.
      localStorage.setItem('tactile-upload-owners', JSON.stringify(owners));
      const uploadBody = JSON.stringify({filename: file.name, csv});
      if (new Blob([uploadBody]).size > 4 * 1024 * 1024) throw new Error('CSV encoding exceeds the upload limit; use a shorter clip');
      const response = await fetch('/api/shared-uploads', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: uploadBody,
      });
      if (!response.ok) throw new Error(await uploadError(response));
      const saved = await response.json();
      owners[saved.shareId] = saved.ownerToken;
      localStorage.setItem('tactile-upload-owners', JSON.stringify(owners));
      const id = saved.id;
      delete saved.ownerToken;
      state.hostedDatasets.set(id, {...saved, parsed});
      renderHostedPlaybackOptions(id);
      await previewPlaybackDataset(id);
      await setSourceMode('playback');
      elements.playbackUploadStatus.textContent = `${parsed.frames.length.toLocaleString()} frames ready`;
      return;
    }
  } catch (error) {
    elements.playbackUpload.classList.add('error');
    elements.playbackUploadStatus.textContent = error.message;
  } finally {
    elements.playbackUpload.classList.remove('uploading');
    elements.playbackUploadButton.disabled = false;
    elements.playbackUploadButton.textContent = 'Upload CSV';
    elements.playbackFile.value = '';
  }
});

async function previewPlaybackDataset(dataset) {
  const request = ++state.playbackRequest;
  state.playbackPlaying = false;
  if (!dataset) {
    state.hostedPlaybackFrames = null;
    state.playbackPlaying = false;
    state.values.fill(0); state.rawVolts.fill(0); state.heatDirty = true;
    elements.playbackPreview.hidden = true;
    elements.playbackTimeline.hidden = true;
    return;
  }
  const hostedDataset = await loadHostedDataset(dataset);
  if (request !== state.playbackRequest) return;
  const payload = hostedDataset.parsed;
  state.actionClip = payload.sensorCount ? payload : null;
  state.hostedPlaybackFrames = payload.frames;
  state.hostedPlaybackIndex = 0;
  state.playbackFps = payload.fps || 15;
  state.playbackPlaying = false;
  const modelMode = modelForCount(payload.sensorCount);
  state.ringActionMapping = null;
  state.values.fill(0); state.rawVolts.fill(NaN); state.heatDirty = true;
  if (state.modelMode !== modelMode) {
    state.modelMode = modelMode;
    const radiusInput = document.querySelector('#radius');
    const ring = modelMode === 'ring';
    radiusInput.min = ring ? '0.5' : '4';
    radiusInput.max = ring ? '12' : '70';
    radiusInput.step = ring ? '0.5' : '1';
    radiusInput.value = ring ? '3' : state.modelMode === 'robot' ? '10' : '25';
    radiusInput.dispatchEvent(new Event('input'));
    elements.modelControl.querySelectorAll('button').forEach(b => b.classList.toggle('active', b.dataset.model === modelMode));
    await loadModel();
    if (request !== state.playbackRequest) return;
  }
  renderHostedPlaybackOptions(dataset);
  if (modelMode === 'ring') {
    state.ringActionMapping = createRingActionMapping(payload.coordinates,
      state.sensorPositions.map((p, index) => ({ index, position: p.toArray() })));
    elements.modelMessage.textContent = '18 nodes mapped onto Ring · geometric display alignment';
  }
  buildSensorMatrix();
  elements.playbackPreview.hidden = false;
  elements.playbackTimeline.hidden = false;
  elements.playbackPreviewTitle.textContent = hostedDataset.label;
  document.querySelector('#playback-new-badge').hidden = !hostedDataset.uploadedAt;
  const uploadTime = document.querySelector('#playback-upload-time');
  uploadTime.hidden = !hostedDataset.uploadedAt;
  uploadTime.textContent = hostedDataset.uploadedAt ? `Uploaded ${new Date(hostedDataset.uploadedAt).toLocaleString()}` : '';
  if (hostedDataset.uploadedAt) uploadTime.dateTime = hostedDataset.uploadedAt;
  updateUploadActions(hostedDataset);
  elements.playbackPreviewMeta.textContent = `${payload.frames.length.toLocaleString()} playback frames · ${payload.sensorCount || 96} sensors`;
  elements.playbackPreviewSample.textContent = payload.source
    ? `${payload.originalFrames} measured frames · ${payload.interpolated ? 'interpolated to 20 FPS' : '20 FPS'}\n${payload.raw ? 'Raw / baseline / signal available' : 'Processed signal only'}${payload.missingSamples ? `\n${payload.missingSamples} missing measurements shown as —` : ''}`
    : payload.sample.map(row => `#${row.scanIndex} ${row.sensor}  ${row.voltage} V  signal ${row.signal}`).join('\n');
  if (payload.recordedAt) elements.playbackPreviewSample.textContent += `\nRecorded ${payload.recordedAt}`;
  if (payload.timingSource) elements.playbackPreviewSample.textContent += `\nTime: ${payload.timingSource}`;
  if (payload.signalLayer) elements.playbackPreviewSample.textContent += `\n${payload.signalLayer}`;
  if (payload.sensorCount === 132) elements.playbackPreviewSample.textContent += '\nReconstructed signal · front/back labels provisional';
  updatePlaybackTimeline(0, payload.frames.length, false);
  applyHostedPlaybackFrame();
}

function formatPlaybackTime(frameIndex, fps = state.playbackFps) {
  const seconds = Math.max(0, frameIndex) / Math.max(1, fps);
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${(seconds % 60).toFixed(1).padStart(4, '0')}`;
}

function updatePlaybackTimeline(frameIndex, totalFrames, playing = state.playbackPlaying) {
  const total = Math.max(1, totalFrames || 1);
  const index = Math.min(total - 1, Math.max(0, frameIndex || 0));
  state.playbackPlaying = playing;
  elements.playbackScrubber.max = String(total - 1);
  elements.playbackScrubber.value = String(index);
  elements.playbackScrubber.style.setProperty('--fill', `${total > 1 ? (index / (total - 1)) * 100 : 0}%`);
  elements.playbackCurrentTime.textContent = formatPlaybackTime(index);
  elements.playbackTotalTime.textContent = formatPlaybackTime(total - 1);
  elements.playbackFrameLabel.textContent = `Frame ${(index + 1).toLocaleString()} / ${total.toLocaleString()}`;
  elements.playbackToggle.textContent = playing ? 'Ⅱ' : '▶';
  elements.playbackToggle.setAttribute('aria-label', playing ? 'Pause playback' : 'Play recording');
  elements.playbackToggle.title = playing ? 'Pause playback' : 'Play recording';
}

async function controlPlayback({ frameIndex = null, playing = null } = {}) {
  {
    const total = state.hostedPlaybackFrames?.length ?? 0;
    if (!total) throw new Error('Choose a recording first');
    if (frameIndex !== null) {
      state.hostedPlaybackIndex = Math.min(total - 1, Math.max(0, frameIndex));
    }
    if (playing !== null) state.playbackPlaying = playing;
    state.hostedLastFrameAt = performance.now();
    applyHostedPlaybackFrame();
    return { ok: true, frameIndex: state.hostedPlaybackIndex, playing: state.playbackPlaying };
  }
}

elements.playbackToggle.addEventListener('click', async () => {
  try {
    await controlPlayback({ playing: !state.playbackPlaying });
  } catch (error) {
    elements.sourceMessage.classList.add('error');
    elements.sourceMessage.textContent = error.message;
  }
});

elements.playbackScrubber.addEventListener('pointerdown', () => {
  state.playbackScrubbing = true;
});

elements.playbackScrubber.addEventListener('input', () => {
  const frameIndex = Number(elements.playbackScrubber.value);
  updatePlaybackTimeline(frameIndex, Number(elements.playbackScrubber.max) + 1, false);
  controlPlayback({ frameIndex, playing: false }).catch((error) => {
    elements.sourceMessage.classList.add('error');
    elements.sourceMessage.textContent = error.message;
  });
});

elements.playbackScrubber.addEventListener('change', () => {
  state.playbackScrubbing = false;
});

async function setSourceMode(mode) {
  if (mode === 'serial' && state.modelMode === 'robot') throw new Error('Robot arm: select a recorded 132-node action');
  document.querySelectorAll('#source-control button').forEach((button) => {
    button.classList.toggle('active', button.dataset.mode === mode);
  });
  const port = elements.portSelect.value || null;
  const dataset = elements.playbackSelect.value || null;
  elements.portSelect.hidden = mode !== 'serial';
  elements.playbackSelect.hidden = mode !== 'playback';
  elements.playbackUpload.hidden = mode !== 'playback';
  elements.playbackPreview.hidden = mode !== 'playback';
  elements.playbackTimeline.hidden = mode !== 'playback' || !dataset;
  if (mode === 'playback' && !dataset) {
    elements.sourceMessage.classList.remove('error');
    state.sourceMode = 'playback';
    state.playbackPlaying = false;
    state.values.fill(0); state.rawVolts.fill(0); state.heatDirty = true;
    elements.sourceMessage.textContent = 'Choose an action to start playback';
    return;
  }
  elements.modelControl.querySelectorAll('button').forEach(b => { b.disabled = false; });
  document.querySelector('.matrix-section').hidden = false;
  elements.recordStart.disabled = Boolean(state.recording);
  document.querySelector('.footer-data > span').textContent = '96 mapped intersections';
  if (mode === 'playback') {
    if (hostedSerialSensor?.connected) await hostedSerialSensor.disconnect();
    if (!state.hostedPlaybackFrames?.length) await previewPlaybackDataset(dataset);
    state.sourceMode = 'playback';
    state.playbackPlaying = true;
    state.hostedLastFrameAt = 0;
    applyHostedPlaybackFrame();
    return;
  }
  state.sourceMode = mode;
  if (HOSTED_MODE || state.modelMode === 'robot') {
    elements.portSelect.hidden = true;
    if (mode === 'serial') {
      if (!hostedSerialSensor) {
        document.querySelectorAll('#source-control button').forEach((button) => {
          button.classList.toggle('active', button.dataset.mode === state.sourceMode);
        });
        throw new Error('Use desktop Chrome or Edge to connect a USB serial sensor');
      }
      const sourceButtons = document.querySelectorAll('#source-control button');
      sourceButtons.forEach((button) => { button.disabled = true; });
      elements.sourceMessage.classList.remove('error');
      elements.sourceMessage.textContent = 'Choose the CP2104 / USB serial device in the browser prompt…';
      try {
        const label = await hostedSerialSensor.connect();
        state.sourceMode = 'serial';
        state.hostedLastFrameAt = 0;
        elements.sourceMessage.textContent = `${label} · 1,000,000 baud`;
      } catch (error) {
        sourceButtons.forEach((button) => {
          button.classList.toggle('active', button.dataset.mode === state.sourceMode);
        });
        throw error;
      } finally {
        sourceButtons.forEach((button) => { button.disabled = false; });
      }
      return;
    }
    if (hostedSerialSensor?.connected) await hostedSerialSensor.disconnect();
    state.sourceMode = mode;
    state.hostedLastFrameAt = 0;
    elements.sourceMessage.classList.remove('error');
    elements.sourceMessage.textContent = mode === 'playback'
      ? 'Playing recorded 96-point sensor data in this browser'
      : 'Animated 96-point test data in this browser';
    return;
  }
  const response = await fetch(apiUrl('/api/mode'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, port, dataset }),
  });
  if (!response.ok) throw new Error((await response.json()).detail ?? 'Mode change failed');
  elements.sourceMessage.classList.remove('error');
  elements.sourceMessage.textContent = mode === 'serial'
    ? 'Opening CP2104 at 1,000,000 baud…'
    : mode === 'playback'
      ? 'Playing recorded 96-point sensor data'
      : 'Animated 96-point test data';
}

document.querySelectorAll('#source-control button').forEach((button) => {
  button.addEventListener('click', async () => {
    try {
      await setSourceMode(button.dataset.mode);
    } catch (error) {
      elements.sourceMessage.classList.add('error');
      elements.sourceMessage.textContent = error.message;
    }
  });
});

elements.playbackSelect.addEventListener('change', async () => {
  try {
    await previewPlaybackDataset(elements.playbackSelect.value);
    if (elements.playbackSelect.value) await setSourceMode('playback');
  } catch (error) {
    elements.sourceMessage.classList.add('error');
    elements.sourceMessage.textContent = error.message;
  }
});

document.querySelector('#reload-model').addEventListener('click', async () => {
  const button = document.querySelector('#reload-model');
  button.disabled = true;
  button.textContent = 'Working';
  elements.modelMessage.classList.remove('error');
  elements.modelMessage.textContent = 'Exporting the active Grasshopper heatmap mesh…';
  try {
    if (state.modelMode === 'ring') {
      await loadModel();
      button.disabled = false;
      button.textContent = 'Reload';
      return;
    }
    const response = await fetch(apiUrl(`/api/model/reload?model=${state.modelMode}`), { method: 'POST' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail ?? 'Grasshopper export failed');
    elements.modelMessage.textContent = 'Model updated. Reloading viewer…';
    await loadModel();
    if (state.sourceMode === 'playback') applyHostedPlaybackFrame();
    button.disabled = false;
    button.textContent = 'Reload';
  } catch (error) {
    elements.modelMessage.classList.add('error');
    elements.modelMessage.textContent = error.message;
    button.disabled = false;
    button.textContent = 'Reload';
  }
});

elements.modelControl.querySelectorAll('button').forEach((button) => {
  button.addEventListener('click', async () => {
    if (state.modelMode === button.dataset.model) return;
    if (state.sourceMode === 'playback') {
      const target = [...state.hostedDatasets.values()].find(dataset =>
        (modelForCount(dataset.sensorCount || dataset.parsed?.sensorCount)) === button.dataset.model);
      if (!target) return;
      const buttons = [...elements.modelControl.querySelectorAll('button')];
      buttons.forEach(item => { item.disabled = true; });
      try {
        await previewPlaybackDataset(target.id);
        await setSourceMode('playback');
      } catch (error) {
        elements.sourceMessage.textContent = error.message;
        elements.sourceMessage.classList.add('error');
      } finally {
        buttons.forEach(item => { item.disabled = false; });
      }
      return;
    }
    state.modelMode = button.dataset.model;
    const radiusInput = document.querySelector('#radius');
    const ring = state.modelMode === 'ring';
    radiusInput.min = ring ? '0.5' : '4';
    radiusInput.max = ring ? '12' : '70';
    radiusInput.step = ring ? '0.5' : '1';
    radiusInput.value = ring ? '3' : state.modelMode === 'robot' ? '10' : '25';
    radiusInput.dispatchEvent(new Event('input'));
    elements.modelControl.querySelectorAll('button').forEach((item) => {
      item.classList.toggle('active', item.dataset.model === state.modelMode);
    });
    state.selectedSensor = null;
    elements.selectedCard.classList.remove('visible');
    elements.modelLoading.classList.remove('hidden');
    elements.modelLoading.querySelector('span').textContent = state.modelMode === 'ring'
      ? 'Loading ring mesh'
      : 'Preparing 3D heat field';
    try {
      await loadModel();
    } catch (error) {
      elements.modelStatus.textContent = 'Model error';
      elements.modelLoading.querySelector('span').textContent = error.message;
      console.error(error);
    }
  });
});

function websocketAddress() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${location.host}/api/ws`;
}

function updateHostedSerialStatus(status) {
  if (status.state === 'opening') {
    elements.connectionPill.classList.remove('error');
    elements.connectionText.textContent = 'Opening sensor';
    elements.sourceMessage.textContent = `${status.label} · waiting for device startup…`;
  } else if (status.state === 'connected') {
    elements.connectionPill.classList.remove('error');
    elements.connectionText.textContent = 'Sensor connected';
  } else if (status.state === 'error') {
    elements.connectionPill.classList.add('error');
    elements.connectionText.textContent = 'Sensor disconnected';
    elements.sourceMessage.classList.add('error');
    elements.sourceMessage.textContent = status.error?.message ?? 'The USB sensor disconnected';
  } else if (status.state === 'disconnected' && state.sourceMode === 'serial') {
    elements.connectionPill.classList.add('error');
    elements.connectionText.textContent = 'Sensor disconnected';
  }
}

function applyFramePayload(payload) {
  if (payload.type !== 'frame' || payload.values.length !== (state.modelMode === 'robot' ? ROBOT_SENSOR_COUNT : SENSOR_COUNT)) return;
  state.values.fill(0); state.rawVolts.fill(NaN);
  state.values.set(payload.values);
  state.rawVolts.set(payload.rawVolts);
  state.heatDirty = true;
  state.frameCounter += 1;
  state.lastSequence = payload.sequence;
  if (!HOSTED_MODE || payload.mode === 'serial') {
    elements.autoClear.checked = payload.autoClearEnabled !== false;
  }
  if ((payload.autoClearCount ?? 0) > state.autoClearCount) {
    state.autoClearCount = payload.autoClearCount;
    elements.recordingMessage.classList.remove('error');
    elements.recordingMessage.textContent = 'Stale live sensor data cleared automatically';
  }
  if (state.recording && !state.recording.stopping) {
    state.recording.frames.push({
      tMs: performance.now() - state.recording.startedPerformance,
      modelMode: state.modelMode,
      sensorCount: state.activeSensorCount,
      timestamp: payload.timestamp,
      sequence: payload.sequence,
      mode: payload.mode,
      connected: payload.connected,
      port: payload.port,
      values: Array.from(payload.values),
      rawVolts: Array.from(payload.rawVolts),
    });
    const elapsedSeconds = (performance.now() - state.recording.startedPerformance) / 1000;
    elements.recordingMeta.textContent = `${state.recording.frames.length} frames · ${Math.floor(elapsedSeconds / 60)}:${String(Math.floor(elapsedSeconds % 60)).padStart(2, '0')}`;
  }
  elements.frameSequence.textContent = `Frame ${String(payload.sequence).padStart(4, '0')}`;
  elements.connectionPill.classList.toggle('error', !payload.connected);
  elements.connectionText.textContent = payload.connected
    ? payload.mode === 'serial' ? 'Sensor live' : payload.mode === 'playback' ? 'Recorded data' : 'Simulation'
    : 'Disconnected';
  if (payload.error) {
    elements.sourceMessage.classList.add('error');
    elements.sourceMessage.textContent = payload.error;
  } else if (payload.mode === 'serial') {
    elements.sourceMessage.classList.remove('error');
    elements.sourceMessage.textContent = `${payload.port ?? 'USB serial'} · 1,000,000 baud`;
  } else if (payload.mode === 'playback') {
    elements.sourceMessage.classList.remove('error');
    elements.sourceMessage.textContent = `Playing ${payload.port ?? 'recorded data'}`;
  }
  if (payload.mode === 'playback' && !state.playbackScrubbing) {
    state.playbackFps = payload.playbackFps || 15;
    updatePlaybackTimeline(payload.playbackIndex, payload.playbackTotal, payload.playbackPlaying);
  }
  updateMatrix();
}

const playbackDataPreview = createPlaybackDataPreview(document.querySelector('#current-frame-preview'), index => {
  selectSensor(index);
  renderCurrentPlaybackData();
});
function renderCurrentPlaybackData() {
  const dataset=state.hostedDatasets.get(elements.playbackSelect.value);
  const clip=dataset?.parsed;
  const frame=state.hostedPlaybackFrames?.[state.hostedPlaybackIndex];
  if(clip && frame) playbackDataPreview.update(clip,frame,state.hostedPlaybackIndex,state.playbackPlaying,state.ringActionMapping,state.selectedSensor);
}

function applyHostedPlaybackFrame() {
  const frames = state.hostedPlaybackFrames;
  if (!frames?.length) return;
  state.hostedPlaybackIndex = Math.min(frames.length - 1, Math.max(0, state.hostedPlaybackIndex));
  const frame = frames[state.hostedPlaybackIndex];
  const sparse = state.actionClip?.sensorCount === 18;
  if (sparse && !state.ringActionMapping) return;
  const mappedFrame = sparse ? mapRingActionFrame(frame, state.ringActionMapping) : frame;
  elements.recordStart.disabled = Boolean(state.recording);
  elements.recordStart.title = '';
  document.querySelector('.footer-data > span').textContent = sparse ? '18 mapped nodes · Finger' : `${state.actionClip?.sensorCount || 96} mapped intersections`;
  elements.pointCount.textContent = sparse ? '18 / 30' : `${state.actionClip?.sensorCount || 96} points`;
  applyFramePayload({
    type: 'frame',
    mode: 'playback',
    connected: true,
    port: elements.playbackSelect.selectedOptions[0]?.textContent ?? 'recorded data',
    error: null,
    sequence: ++state.hostedSequence,
    timestamp: Date.now() / 1000,
    values: mappedFrame.values,
    rawVolts: mappedFrame.rawVolts,
    playbackIndex: state.hostedPlaybackIndex,
    playbackTotal: frames.length,
    playbackPlaying: state.playbackPlaying,
    playbackFps: state.playbackFps,
    autoClearEnabled: false,
    autoClearCount: 0,
  });
  renderCurrentPlaybackData();
}

function applyHostedSimulationFrame(now) {
  const elapsed = (now - state.hostedStartedAt) / 1000;
  const simulationCount = state.modelMode === 'robot' ? ROBOT_SENSOR_COUNT : SENSOR_COUNT;
  const values = new Float32Array(simulationCount);
  const rawVolts = new Float32Array(simulationCount);
  const simulationRows = state.modelMode === 'robot' ? 11 : ROWS;
  const simulationColumns = state.modelMode === 'robot' ? 12 : COLUMNS;
  const centerRow = (elapsed * 0.55) % simulationRows;
  const centerColumn = 3.5 + Math.sin(elapsed * 0.8) * 2.2;
  for (let index = 0; index < simulationCount; index += 1) {
    const row = Math.floor(index / simulationColumns);
    const column = index % simulationColumns;
    const rowDistance = Math.min(Math.abs(row - centerRow), simulationRows - Math.abs(row - centerRow));
    const distance = Math.hypot(rowDistance / 2.2, (column - centerColumn) / 1.8);
    const pulse = 0.18 * (Math.sin(elapsed * 2.1 + index * 0.37) + 1) / 2;
    const value = Math.max(0, Math.min(1, Math.exp(-distance * distance) * 0.9 + pulse * 0.35));
    values[index] = value;
    rawVolts[index] = 3.3 * (1 - value * 0.55);
  }
  applyFramePayload({
    type: 'frame',
    mode: 'simulation',
    connected: true,
    port: null,
    error: null,
    sequence: ++state.hostedSequence,
    timestamp: Date.now() / 1000,
    values,
    rawVolts,
    autoClearEnabled: false,
    autoClearCount: 0,
  });
}

function updateHostedRuntime(now) {
  const interval = 1000 / state.playbackFps;
  if (now - state.hostedLastFrameAt < interval) return;
  if (state.sourceMode === 'serial') return;
  if (state.sourceMode === 'playback') {
    if (!state.playbackPlaying || !state.hostedPlaybackFrames?.length) return;
    if (state.hostedLastFrameAt > 0) {
      state.hostedPlaybackIndex = (state.hostedPlaybackIndex + 1) % state.hostedPlaybackFrames.length;
    }
    applyHostedPlaybackFrame();
  } else {
    applyHostedSimulationFrame(now);
  }
  state.hostedLastFrameAt = now;
}

function connectWebSocket() {
  const socket = new WebSocket(websocketAddress());
  socket.addEventListener('open', () => {
    elements.connectionPill.classList.remove('error');
    elements.connectionText.textContent = 'Data online';
  });
  socket.addEventListener('message', (event) => {
    const payload = JSON.parse(event.data);
    if (state.sourceMode !== 'playback' && state.modelMode !== 'robot') applyFramePayload(payload);
  });
  socket.addEventListener('close', () => {
    if (state.sourceMode !== 'playback') {
      elements.connectionPill.classList.add('error');
      elements.connectionText.textContent = 'Backend offline';
    }
    setTimeout(connectWebSocket, 1400);
  });
  socket.addEventListener('error', () => socket.close());
}

setInterval(() => {
  const now = performance.now();
  const elapsed = (now - state.frameCounterStarted) / 1000;
  elements.frameRate.textContent = `${(state.frameCounter / Math.max(0.001, elapsed)).toFixed(1)} Hz`;
  state.frameCounter = 0;
  state.frameCounterStarted = now;
}, 1000);

function initializeHostedMode() {
  elements.connectionPill.classList.remove('error');
  elements.connectionText.textContent = 'Browser mode';
  elements.portSelect.hidden = true;
  elements.autoClear.checked = state.hostedAutoClearEnabled;
  elements.autoClear.disabled = !hostedSerialSensor;
  const serialButton = document.querySelector('#source-control button[data-mode="serial"]');
  serialButton.disabled = !hostedSerialSensor;
  serialButton.title = hostedSerialSensor
    ? 'Choose and connect a USB serial sensor'
    : 'Web Serial requires desktop Chrome or Edge';
  const reloadButton = document.querySelector('#reload-model');
  reloadButton.disabled = true;
  reloadButton.title = 'Grasshopper reload is available in the local app';
  elements.modelMessage.textContent = 'Hosted model geometry · edit and reload through the local app';
  elements.recordingMessage.textContent = hostedSerialSensor
    ? 'Video and sensor JSON are recorded here; stale live data clears automatically.'
    : 'Recording works here; USB sensor access requires desktop Chrome or Edge.';
  elements.sourceMessage.textContent = 'Animated 96-point test data in this browser';
}

buildSensorMatrix();
updateLegend();
if (HOSTED_MODE) {
  initializeHostedMode();
} else {
  refreshPorts();
  connectWebSocket();
}
loadModel().then(async () => {
  const datasets = await refreshPlaybackDatasets();
  const sharedDataset = await restoreSharedUploads();
  if (datasets.length || sharedDataset) {
    const initialDataset = sharedDataset || datasets.find(dataset => dataset.sensorCount === (new URLSearchParams(location.search).get('model') === 'robot' ? 132 : 96)) || datasets[0];
    elements.playbackSelect.value = initialDataset.id;
    await previewPlaybackDataset(initialDataset.id);
    await setSourceMode('playback');
  }
}).catch((error) => {
  elements.modelStatus.textContent = 'Model error';
  elements.modelLoading.querySelector('span').textContent = error.message;
  console.error(error);
});
resize();
requestAnimationFrame(animate);
