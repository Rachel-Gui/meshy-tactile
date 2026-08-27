import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import './styles.css';

const ROWS = 12;
const COLUMNS = 8;
const SENSOR_COUNT = ROWS * COLUMNS;

const state = {
  model: null,
  geometry: null,
  material: null,
  sensorPoints: null,
  sensorPositions: [],
  distanceMatrix: null,
  sensorAngles: new Float32Array(SENSOR_COUNT),
  values: new Float32Array(SENSOR_COUNT),
  rawVolts: new Float32Array(SENSOR_COUNT),
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
};

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
  const fragment = document.createDocumentFragment();
  for (let index = 0; index < SENSOR_COUNT; index += 1) {
    const button = document.createElement('button');
    button.className = 'sensor-cell';
    button.type = 'button';
    button.dataset.index = String(index);
    button.title = `A${String(Math.floor(index / COLUMNS) + 1).padStart(2, '0')} · offset ${(index % COLUMNS) + 1}`;
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
  const row = Math.floor(index / COLUMNS) + 1;
  const column = (index % COLUMNS) + 1;
  elements.selectedIndex.textContent = `A${String(row).padStart(2, '0')} · ${String(column).padStart(2, '0')}`;
  elements.selectedValue.textContent = `${Math.round(state.values[index] * 100)}%`;
  elements.selectedVoltage.textContent = `${state.rawVolts[index].toFixed(3)} V`;
  const angle = state.sensorAngles[index];
  elements.selectedAngle.textContent = `Strip angle ${angle > 0 ? `${angle.toFixed(1)}°` : '—'}`;
}

function computeSensorAngles(positions) {
  const angles = new Float32Array(SENSOR_COUNT);
  const physicalColumn = (row, slot) => (row + slot + 1) % ROWS;

  for (let index = 0; index < SENSOR_COUNT; index += 1) {
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
    for (let candidate = 0; candidate < SENSOR_COUNT; candidate += 1) {
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

async function loadModel() {
  const response = await fetch('/assets/model.json', { cache: 'no-store' });
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
    transparent: false,
    opacity: 1,
  });
  const model = new THREE.Mesh(geometry, material);
  model.name = 'Heatmap strips';
  modelGroup.add(model);

  const sensorPositions = payload.sensors.map((sensor) => new THREE.Vector3(...sensor.position));
  const markerGeometry = new THREE.BufferGeometry().setFromPoints(sensorPositions);
  markerGeometry.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(SENSOR_COUNT * 3), 3));
  const markerMaterial = new THREE.PointsMaterial({
    size: 4.0,
    sizeAttenuation: true,
    vertexColors: true,
    transparent: true,
    opacity: 0.95,
    depthTest: false,
  });
  const sensorPoints = new THREE.Points(markerGeometry, markerMaterial);
  sensorPoints.visible = false;
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
  state.sensorAngles = computeSensorAngles(sensorPositions);

  elements.pointCount.textContent = String(payload.metadata.sensorCount);
  elements.modelMeta.textContent = `${payload.metadata.vertexCount.toLocaleString()} vertices`;
  elements.modelStatus.textContent = 'GH live mesh';
  elements.modelLength.textContent = state.modelSize.x.toFixed(1);
  elements.modelFrontDiameter.textContent = endDiameter(source.positions, geometry.boundingBox, true).toFixed(1);
  elements.modelRearDiameter.textContent = endDiameter(source.positions, geometry.boundingBox, false).toFixed(1);
  fitCamera('perspective', false);
  await precomputeDistances();
  state.heatDirty = true;
  elements.modelLoading.classList.add('hidden');
}

async function precomputeDistances() {
  const positions = state.geometry.attributes.position.array;
  const vertexCount = positions.length / 3;
  const distances = new Float32Array(vertexCount * SENSOR_COUNT);

  for (let vertexIndex = 0; vertexIndex < vertexCount; vertexIndex += 1) {
    const x = positions[vertexIndex * 3];
    const y = positions[vertexIndex * 3 + 1];
    const z = positions[vertexIndex * 3 + 2];
    const offset = vertexIndex * SENSOR_COUNT;
    for (let sensorIndex = 0; sensorIndex < SENSOR_COUNT; sensorIndex += 1) {
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
  const adjustedValues = new Float32Array(SENSOR_COUNT);

  for (let sensorIndex = 0; sensorIndex < SENSOR_COUNT; sensorIndex += 1) {
    const adjusted = Math.min(1, Math.max(0, (state.values[sensorIndex] - state.threshold) / denominator) * state.gain);
    adjustedValues[sensorIndex] = adjusted;
    markerColors[sensorIndex * 3] = 0.82;
    markerColors[sensorIndex * 3 + 1] = 0.85;
    markerColors[sensorIndex * 3 + 2] = 0.9;
  }

  for (let vertexIndex = 0; vertexIndex < vertexCount; vertexIndex += 1) {
    let strongest = 0;
    const distanceOffset = vertexIndex * SENSOR_COUNT;
    for (let sensorIndex = 0; sensorIndex < SENSOR_COUNT; sensorIndex += 1) {
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
  elements.recordStop.disabled = !active;
  elements.recordStart.textContent = active ? 'Recording…' : 'Start recording';
  elements.recordingStatus.textContent = active ? 'REC' : 'Ready';
  elements.recordingStatus.classList.toggle('recording-live', active);
}

async function clearLiveData() {
  state.values.fill(0);
  state.rawVolts.fill(0);
  state.heatDirty = true;
  updateMatrix();
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

function startRecording() {
  if (!window.MediaRecorder || !renderer.domElement.captureStream) {
    elements.recordingMessage.textContent = 'This browser does not support model video recording.';
    elements.recordingMessage.classList.add('error');
    return;
  }

  const mimeType = recordingMimeType();
  if (!mimeType) {
    elements.recordingMessage.textContent = 'No supported WebM video format was found.';
    elements.recordingMessage.classList.add('error');
    return;
  }

  const startedAt = new Date();
  const startedPerformance = performance.now();
  const chunks = [];
  const stream = renderer.domElement.captureStream(30);
  const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 8_000_000 });
  const recording = {
    recorder,
    stream,
    startedAt,
    startedPerformance,
    frames: [],
    chunks,
  };
  state.recording = recording;
  recorder.addEventListener('dataavailable', (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  });
  recorder.addEventListener('stop', () => finishRecording(recording, mimeType));
  recorder.start(1000);
  elements.recordingMessage.classList.remove('error');
  elements.recordingMessage.textContent = 'Recording model video and sensor frames…';
  elements.recordingMeta.textContent = '0 frames · 0:00';
  updateRecordingUi();
}

function stopRecording() {
  if (!state.recording) return;
  state.recording.recorder.stop();
  state.recording.stream.getTracks().forEach((track) => track.stop());
  elements.recordingMessage.textContent = 'Preparing files…';
  elements.recordStop.disabled = true;
}

function finishRecording(recording, mimeType) {
  if (state.recording !== recording) return;
  const endedAt = new Date();
  const durationMs = Math.max(0, performance.now() - recording.startedPerformance);
  const stamp = recordingStamp(recording.startedAt);
  const payload = {
    format: 'tactile-sensor-recording-v1',
    startedAt: recording.startedAt.toISOString(),
    endedAt: endedAt.toISOString(),
    durationMs: Math.round(durationMs),
    video: { mimeType, canvasWidth: renderer.domElement.width, canvasHeight: renderer.domElement.height },
    model: state.modelMetadata,
    settings: { radius: state.radius, gain: state.gain, threshold: state.threshold, opacity: state.opacity, palette: state.palette },
    frames: recording.frames,
  };
  downloadBlob(new Blob(recording.chunks, { type: mimeType }), recordingFilename(stamp, 'webm'));
  downloadBlob(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }), recordingFilename(stamp, 'json'));
  state.recording = null;
  elements.recordingMessage.classList.remove('error');
  elements.recordingMessage.textContent = `Saved video + data · ${recording.frames.length} frames`;
  elements.recordingMeta.textContent = `${recording.frames.length} frames · ${(durationMs / 1000).toFixed(1)}s`;
  updateRecordingUi();
}

elements.recordStart.addEventListener('click', startRecording);
elements.recordStop.addEventListener('click', stopRecording);
elements.recordClear.addEventListener('click', clearLiveData);
elements.autoClear.addEventListener('change', async () => {
  const enabled = elements.autoClear.checked;
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
  const distance = Math.max(170, diagonal * 1.45);
  const poses = {
    perspective: new THREE.Vector3(center.x - distance * 0.65, center.y - distance * 0.85, center.z + distance * 0.52),
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

bindRange('radius', 'radius', (value) => value.toFixed(0));
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
  const defaults = { radius: 25, gain: 1, threshold: 0, opacity: 1 };
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

async function refreshPlaybackDatasets(selectedDataset = null) {
  try {
    const response = await fetch('/api/playback-datasets');
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail ?? 'Could not load recordings');
    elements.playbackSelect.querySelectorAll('option:not(:first-child)').forEach((option) => option.remove());
    payload.datasets.forEach((dataset) => {
      const option = document.createElement('option');
      option.value = dataset.id;
      option.textContent = dataset.label;
      elements.playbackSelect.appendChild(option);
    });
    if (selectedDataset && payload.datasets.some((dataset) => dataset.id === selectedDataset)) {
      elements.playbackSelect.value = selectedDataset;
    }
    return payload.datasets;
  } catch {
    // The backend may not be running yet.
    return [];
  }
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
    const response = await fetch(`/api/playback-datasets/upload?filename=${encodeURIComponent(file.name)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'text/csv' },
      body: file,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail ?? 'CSV upload failed');

    await refreshPlaybackDatasets(payload.id);
    await previewPlaybackDataset(payload.id);
    await setSourceMode('playback');
    elements.playbackUploadStatus.textContent = `${payload.frames.toLocaleString()} frames ready`;
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
  if (!dataset) {
    elements.playbackPreview.hidden = true;
    elements.playbackTimeline.hidden = true;
    return;
  }
  const response = await fetch(`/api/playback-preview/${encodeURIComponent(dataset)}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail ?? 'Playback preview failed');
  elements.playbackPreview.hidden = false;
  elements.playbackTimeline.hidden = false;
  elements.playbackPreviewTitle.textContent = payload.label;
  elements.playbackPreviewMeta.textContent = `${payload.rows.toLocaleString()} samples · ${payload.frames.toLocaleString()} complete frames · 96 sensors`;
  elements.playbackPreviewSample.textContent = payload.sample
    .map((row) => `#${row.scanIndex} ${row.sensor}  ${row.voltage} V  signal ${row.signal}`)
    .join('\n');
  updatePlaybackTimeline(0, payload.frames, false);
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
  const response = await fetch('/api/playback/control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ frame_index: frameIndex, playing }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail ?? 'Playback control failed');
  return payload;
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
    elements.sourceMessage.textContent = 'Choose a recording to start playback';
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

document.querySelector('#calibrate-button').addEventListener('click', async () => {
  await clearLiveData();
  elements.sourceMessage.textContent = 'Zero calibration requested — keep the sensor untouched';
});

document.querySelector('#reload-model').addEventListener('click', async () => {
  const button = document.querySelector('#reload-model');
  button.disabled = true;
  button.textContent = 'Working';
  elements.modelMessage.classList.remove('error');
  elements.modelMessage.textContent = 'Exporting the active Grasshopper heatmap mesh…';
  try {
    const response = await fetch(apiUrl('/api/model/reload'), { method: 'POST' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail ?? 'Grasshopper export failed');
    elements.modelMessage.textContent = 'Model updated. Reloading viewer…';
    location.reload();
  } catch (error) {
    elements.modelMessage.classList.add('error');
    elements.modelMessage.textContent = error.message;
    button.disabled = false;
    button.textContent = 'Reload';
  }
});

function websocketAddress() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${location.host}/api/ws`;
}

function connectWebSocket() {
  const socket = new WebSocket(websocketAddress());
  socket.addEventListener('open', () => {
    elements.connectionPill.classList.remove('error');
    elements.connectionText.textContent = 'Data online';
  });
  socket.addEventListener('message', (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type !== 'frame' || payload.values.length !== SENSOR_COUNT) return;
    state.values.set(payload.values);
    state.rawVolts.set(payload.rawVolts);
    state.heatDirty = true;
    state.frameCounter += 1;
    state.lastSequence = payload.sequence;
    elements.autoClear.checked = payload.autoClearEnabled !== false;
    if ((payload.autoClearCount ?? 0) > state.autoClearCount) {
      state.autoClearCount = payload.autoClearCount;
      elements.recordingMessage.classList.remove('error');
      elements.recordingMessage.textContent = 'Stale live sensor data cleared automatically';
    }
    if (state.recording) {
      state.recording.frames.push({
        tMs: Math.round(performance.now() - state.recording.startedPerformance),
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
  });
  socket.addEventListener('close', () => {
    elements.connectionPill.classList.add('error');
    elements.connectionText.textContent = 'Backend offline';
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

buildSensorMatrix();
updateLegend();
refreshPorts();
refreshPlaybackDatasets();
connectWebSocket();
loadModel().catch((error) => {
  elements.modelStatus.textContent = 'Model error';
  elements.modelLoading.querySelector('span').textContent = error.message;
  console.error(error);
});
resize();
requestAnimationFrame(animate);
