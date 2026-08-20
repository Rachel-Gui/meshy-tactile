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
};

const elements = {
  viewport: document.querySelector('#viewport'),
  modelLoading: document.querySelector('#model-loading'),
  modelStatus: document.querySelector('#model-status'),
  pointCount: document.querySelector('#point-count'),
  peakValue: document.querySelector('#peak-value'),
  connectionPill: document.querySelector('#connection-pill'),
  connectionText: document.querySelector('#connection-text'),
  sourceMessage: document.querySelector('#source-message'),
  portSelect: document.querySelector('#port-select'),
  sensorMatrix: document.querySelector('#sensor-matrix'),
  frameRate: document.querySelector('#frame-rate'),
  frameSequence: document.querySelector('#frame-sequence'),
  modelMeta: document.querySelector('#model-meta'),
  modelLength: document.querySelector('#model-length'),
  modelDiameter: document.querySelector('#model-diameter'),
  modelMessage: document.querySelector('#model-message'),
  selectedCard: document.querySelector('#selected-card'),
  selectedIndex: document.querySelector('#selected-index'),
  selectedValue: document.querySelector('#selected-value'),
  selectedVoltage: document.querySelector('#selected-voltage'),
  legend: document.querySelector('#legend'),
};

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x070a12);
scene.fog = new THREE.FogExp2(0x070a12, 0.0019);

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
  scene.fog.color.set(light ? 0xf4f6f9 : 0x070a12);
  scene.fog.density = light ? 0.00135 : 0.0019;
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
  state.geometry = geometry;
  state.material = material;
  state.sensorPoints = sensorPoints;
  state.sensorPositions = sensorPositions;

  elements.pointCount.textContent = String(payload.metadata.sensorCount);
  elements.modelMeta.textContent = `${payload.metadata.vertexCount.toLocaleString()} vertices`;
  elements.modelStatus.textContent = 'GH live mesh';
  elements.modelLength.textContent = state.modelSize.x.toFixed(1);
  elements.modelDiameter.textContent = Math.max(state.modelSize.y, state.modelSize.z).toFixed(1);
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
    colorAt(adjusted, state.palette, workingColor);
    markerColors[sensorIndex * 3] = workingColor.r;
    markerColors[sensorIndex * 3 + 1] = workingColor.g;
    markerColors[sensorIndex * 3 + 2] = workingColor.b;
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
  let peak = 0;
  document.querySelectorAll('.sensor-cell').forEach((cell, index) => {
    const value = state.values[index];
    peak = Math.max(peak, value);
    colorAt(value, state.palette, workingColor);
    cell.style.backgroundColor = `#${workingColor.getHexString()}`;
  });
  elements.peakValue.textContent = `${Math.round(peak * 100)}%`;
  updateSelectedCard();
}

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

async function setSourceMode(mode) {
  document.querySelectorAll('#source-control button').forEach((button) => {
    button.classList.toggle('active', button.dataset.mode === mode);
  });
  const port = elements.portSelect.value || null;
  const response = await fetch(apiUrl('/api/mode'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, port }),
  });
  if (!response.ok) throw new Error((await response.json()).detail ?? 'Mode change failed');
  elements.sourceMessage.classList.remove('error');
  elements.sourceMessage.textContent = mode === 'serial'
    ? 'Opening CP2104 at 1,000,000 baud…'
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

document.querySelector('#calibrate-button').addEventListener('click', async () => {
  await fetch(apiUrl('/api/calibrate'), { method: 'POST' });
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
  return `${protocol}//${location.host}/ws`;
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
    elements.frameSequence.textContent = `Frame ${String(payload.sequence).padStart(4, '0')}`;
    elements.connectionPill.classList.toggle('error', !payload.connected);
    elements.connectionText.textContent = payload.connected
      ? payload.mode === 'serial' ? 'Sensor live' : 'Simulation'
      : 'Disconnected';
    if (payload.error) {
      elements.sourceMessage.classList.add('error');
      elements.sourceMessage.textContent = payload.error;
    } else if (payload.mode === 'serial') {
      elements.sourceMessage.classList.remove('error');
      elements.sourceMessage.textContent = `${payload.port ?? 'USB serial'} · 1,000,000 baud`;
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
connectWebSocket();
loadModel().catch((error) => {
  elements.modelStatus.textContent = 'Model error';
  elements.modelLoading.querySelector('span').textContent = error.message;
  console.error(error);
});
resize();
requestAnimationFrame(animate);
