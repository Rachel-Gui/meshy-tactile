import * as THREE from 'three';

export function createFingerHandScene() {
  const hand = new THREE.Group();
  hand.name = 'Reference-inspired sculpted hand';
  hand.userData.ready = fetch('/assets/hand-model.json').then(response => {
    if (!response.ok) throw new Error('Hand model could not be loaded');
    return response.json();
  }).then(data => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(data.positions, 3));
    geometry.setIndex(data.indices); geometry.computeVertexNormals();
    const skin = new THREE.MeshStandardMaterial({ color: '#b9b4b0', roughness: .72, metalness: .02, side: THREE.DoubleSide });
    hand.add(new THREE.Mesh(geometry, skin));
    const nailMaterial = new THREE.MeshStandardMaterial({ color: '#c9c3bf', roughness: .46 });
    for (const nail of data.nails) {
      const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 28, 16), nailMaterial);
      mesh.position.set(...nail.center); mesh.scale.set(nail.length / 2, nail.width / 2, .55); const direction = new THREE.Vector3(...nail.direction);
      const normal = new THREE.Vector3(...nail.normal);
      const side = new THREE.Vector3().crossVectors(normal, direction).normalize();
      mesh.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(direction, side, normal));
      hand.add(mesh);
    }
  });
  return hand;
}
