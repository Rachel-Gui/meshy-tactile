import * as THREE from 'three';

// Joint centres from models/hand/build_hand.py, in millimetres.
export const FINGER_JOINTS = [
  [[-16, 0, 0], [27, 0, 0], [43, 1, -6], [55, 2, -17]],
  [[-12, -18, 0], [20, -19, -3], [41, -20, -13], [55, -21, -28]],
  [[-15, -37, -1], [14, -38, -5], [33, -40, -17], [44, -41, -32]],
];
const RADII = [[7.5, 7.1, 6.1, 5.2], [8, 7.5, 6.5, 5.5], [7.6, 7.1, 6.1, 5.1]];
export const MULTI_SLEEVE_LENGTH = 18;
export const FINGER_LAYOUTS = {
  'index-three': [[0, 0], [0, 1], [0, 2]],
  'three-distal': [[0, 2], [1, 2]],
  'three-staggered': [[0, 0], [1, 1]],
};

export function createSleeveLayout(mode, model, points, hand) {
  const layout = new THREE.Group();
  layout.name = `Finger sleeves: ${mode}`;
  const positions = model.geometry.getAttribute('position');
  model.geometry.computeBoundingBox();
  const box = model.geometry.boundingBox;
  const sourceLength = box.max.x - box.min.x;
  let innerRadius = Infinity;
  for (let i = 0; i < positions.count; i++) {
    innerRadius = Math.min(innerRadius, Math.hypot(positions.getY(i), positions.getZ(i)));
  }
  for (const [finger, joint] of FINGER_LAYOUTS[mode] ?? []) {
    const start = new THREE.Vector3(...FINGER_JOINTS[finger][joint]);
    const end = new THREE.Vector3(...FINGER_JOINTS[finger][joint + 1]);
    const axis = end.clone().sub(start).normalize();
    const center = start.clone().add(end).multiplyScalar(0.5);
    // Sample the actual hand surface within this phalanx to leave clearance.
    let radius = Math.max(RADII[finger][joint], RADII[finger][joint + 1]);
    hand.traverse(object => {
      if (!object.isMesh || object.geometry.type === 'SphereGeometry') return;
      const vertices = object.geometry.getAttribute('position');
      const delta = new THREE.Vector3();
      for (let i = 0; i < vertices.count; i++) {
        delta.fromBufferAttribute(vertices, i).sub(center);
        const axial = delta.dot(axis);
        const radial = delta.addScaledVector(axis, -axial).length();
        if (Math.abs(axial) <= MULTI_SLEEVE_LENGTH / 2 && radial < RADII[finger][joint] + 2) {
          radius = Math.max(radius, radial);
        }
      }
    });
    const sleeve = new THREE.Group();
    sleeve.userData = {finger, joint, lengthMm: MULTI_SLEEVE_LENGTH};
    sleeve.position.copy(center);
    sleeve.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), axis);
    sleeve.scale.set(MULTI_SLEEVE_LENGTH / sourceLength, (radius + 0.3) / innerRadius, (radius + 0.3) / innerRadius);
    const mesh = model.clone();
    const markers = points.clone();
    mesh.position.x = markers.position.x = -(box.min.x + box.max.x) / 2;
    sleeve.add(mesh, markers);
    layout.add(sleeve);
  }
  return layout;
}
