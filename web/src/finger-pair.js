import * as THREE from 'three';
import { parsePlaybackCsv } from './playback-csv.js';
import { createRingActionMapping, mapRingActionFrame } from './ring-action-mapping.js';

export function createFingerPair(panel, colorAt) {
  const group = new THREE.Group();
  group.name = 'Finger sleeves A and B';
  const slots = [];
  let sourceGeometry = null, distances, sensors, selected = 0;
  let playing = true, elapsed = 0, lastTime = null;
  const angleInput = panel.querySelector('[data-angle]');
  const angleOutput = panel.querySelector('[data-angle-output]');
  const buttons = [...panel.querySelectorAll('[data-select]')];
  function select(index) {
    selected = index;
    buttons.forEach((button, i) => {
      button.classList.toggle('active', i === index);
      button.setAttribute('aria-pressed', String(i === index));
    });
    slots.forEach((slot, i) => { slot.outline.visible = i === index; });
    angleInput.value = String(slots[index]?.angle ?? 0);
    angleOutput.textContent = `${angleInput.value} deg`;
    panel.querySelector('[data-selected]').textContent = `Rotate sleeve ${index === 0 ? 'A' : 'B'} around its axis`;
  }
  buttons.forEach((button, i) => button.addEventListener('click', () => select(i)));
  angleInput.addEventListener('input', () => {
    const slot = slots[selected];
    if (!slot) return;
    slot.angle = Number(angleInput.value);
    slot.pivot.rotation.x = THREE.MathUtils.degToRad(slot.angle);
    angleOutput.textContent = `${slot.angle} deg`;
    slot.outline.update();
  });
  panel.querySelector('[data-reset]').addEventListener('click', () => {
    angleInput.value = '0'; angleInput.dispatchEvent(new Event('input'));
  });
  panel.querySelector('[data-play]').addEventListener('click', event => {
    playing = !playing; event.target.textContent = playing ? 'Pause both' : 'Play both';
  });
  panel.querySelector('[data-restart]').addEventListener('click', () => { elapsed = 0; slots.forEach(s => {s.frame = -1;}); });
  panel.querySelectorAll('[data-file]').forEach((input, index) => {
    input.addEventListener('change', async () => {
      const file = input.files?.[0]; if (!file || !slots[index]) return;
      const status = panel.querySelector(`[data-file-status="${index}"]`);
      input.disabled = true;
      try {
        if (file.size > 3 * 1024 * 1024) throw new Error('Use a file smaller than 3 MB');
        const csv = /\.xlsx$/i.test(file.name)
          ? (await import('./playback-excel.js')).excelToCsv(await file.arrayBuffer()) : await file.text();
        const clip = parsePlaybackCsv(csv, 18);
        const count = clip.sensorCount ?? clip.frames[0]?.values.length;
        if (count !== 18) throw new Error('Use Finger data with 18 nodes (N001 through N018)');
        const coordinates = clip.coordinates ?? Array.from({length:18}, (_,i) => ({row: Math.floor(i/6)+1, column:i%6+1}));
        // Legacy files need explicit sparse coordinates; do not guess their wiring.
        if (count === 18 && !clip.coordinates) throw new Error('Use the Finger Excel/CSV format with node coordinates');
        const mapping = count === 18 ? createRingActionMapping(coordinates, sensors) : null;
        slots[index].clip = clip; slots[index].mapping = mapping; slots[index].frame = -1;
        elapsed = 0; slots.forEach(s => { s.frame = -1; });
        status.textContent = `${file.name} / ${clip.frames.length} frames`;
        select(index);
      } catch (error) { status.textContent = error.message; }
      finally { input.disabled = false; input.value = ''; }
    });
  });
  function prepare(model, points, matrix, positions) {
    distances = matrix;
    sensors = positions.map((p, index) => ({index, position:p.toArray()}));
    if (sourceGeometry === model.geometry) return;
    sourceGeometry = model.geometry;
    const saved = slots.map(s => ({angle:s.angle,clip:s.clip,mapping:s.mapping}));
    group.traverse(object => {
      object.geometry?.dispose();
      if (object.material) {object.material.map?.dispose();object.material.dispose();}
    });
    group.clear(); slots.length = 0;
    model.geometry.computeBoundingBox();
    const bounds = model.geometry.boundingBox;
    const center = bounds.getCenter(new THREE.Vector3());
    for (let i = 0; i < 2; i++) {
      const pivot = new THREE.Group();
      pivot.position.y = i === 0 ? 17 : -17;
      pivot.scale.x = 18 / (bounds.max.x - bounds.min.x);
      const mesh = new THREE.Mesh(model.geometry.clone(), model.material.clone());
      const markers = new THREE.Points(points.geometry.clone(), points.material.clone());
      mesh.position.copy(center).negate(); markers.position.copy(center).negate();
      mesh.userData.sleeveIndex = i; markers.userData.sleeveIndex = i;
      pivot.add(mesh, markers); group.add(pivot);
      const canvas = document.createElement('canvas');canvas.width=128;canvas.height=64;
      const ctx=canvas.getContext('2d');ctx.fillStyle=i===0?'#38bdf8':'#fbbf24';
      ctx.fillRect(0,0,128,64);ctx.fillStyle='#07111e';ctx.font='bold 44px sans-serif';ctx.textAlign='center';ctx.fillText(i===0?'A':'B',64,48);
      const label=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(canvas),depthTest:false}));
      label.position.set(0,pivot.position.y,16);label.scale.set(10,5,1);group.add(label);
      const outline=new THREE.BoxHelper(pivot,i===0?0x38bdf8:0xfbbf24);group.add(outline);
      const slot={pivot,mesh,markers,outline,angle:0,clip:null,mapping:null,frame:-1,key:'',...saved[i]};
      pivot.rotation.x=THREE.MathUtils.degToRad(slot.angle);outline.update();slots.push(slot);
    }
    select(selected);
  }
  const color = new THREE.Color();
  function update(now, state) {
    if (!group.visible) { lastTime=null; return; }
    if (lastTime !== null && playing) elapsed += (now-lastTime)/1000;
    lastTime=now;
    const duration = Math.max(0,...slots.map(s => s.clip ? s.clip.frames.length/(s.clip.fps||20):0));
    if (duration && elapsed>=duration) elapsed %= duration;
    slots.forEach(slot => {
      slot.markers.visible=state.sensorPoints?.visible ?? false;
      slot.mesh.material.opacity=state.opacity;slot.mesh.material.transparent=state.opacity<.999;
      const index=slot.clip ? Math.min(slot.clip.frames.length-1,Math.floor(elapsed*(slot.clip.fps||20))):-1;
      const key=[state.radius,state.threshold,state.gain,state.palette].join('/');
      if(slot.frame===index && slot.key===key)return;
      slot.frame=index;slot.key=key;
      const frame=index>=0?slot.clip.frames[index]:null;
      const values=frame?(slot.mapping?mapRingActionFrame(frame,slot.mapping).values:frame.values):new Float32Array(30);
      const colors=slot.mesh.geometry.attributes.color;
      for(let vertex=0;vertex<colors.count;vertex++) {
        let strongest=0;
        for(let sensor=0;sensor<30;sensor++) {
          const d=distances[vertex*30+sensor];if(d>=state.radius)continue;
          const value=Math.min(1,Math.max(0,(values[sensor]-state.threshold)/Math.max(.001,1-state.threshold))*state.gain);
          const t=1-d/state.radius;strongest=Math.max(strongest,value*t*t*(3-2*t));
        }
        colorAt(strongest,state.palette,color);colors.setXYZ(vertex,color.r,color.g,color.b);
      }
      colors.needsUpdate=true;
    });
  }
  function pick(raycaster) {
    const hit=raycaster.intersectObjects(slots.map(s=>s.mesh),false)[0];
    if(hit) {select(hit.object.userData.sleeveIndex);return true;}return false;
  }
  group.visible=false;
  return {group,prepare,update,pick};
}
