import * as THREE from 'three';

// Millimetres, Rhino Z-up. Index-finger axis matches the unchanged GH sleeve X axis.
export function createFingerHandScene() {
  const hand = new THREE.Group();
  hand.name = 'Illustrative hand · index finger sleeve';
  const skin = new THREE.MeshStandardMaterial({ color: '#c7b7a6', roughness: 0.88, metalness: 0 });
  const nail = new THREE.MeshStandardMaterial({ color: '#e3d5c8', roughness: 0.62 });
  function ellipsoid(center, scale, material = skin) {
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 40, 28), material);
    mesh.position.set(...center); mesh.scale.set(...scale); hand.add(mesh); return mesh;
  }
  function digit(base, length, radius, angle = 0) {
    // Smooth tapered closed surface, including a rounded fingertip.
    const profile = [[0,0],[radius*.8,1],[radius,5],[radius*.97,length*.28],[radius*.88,length*.55],[radius*.79,length*.78],[radius*.65,length*.91],[radius*.4,length*.97],[0,length]];
    const mesh = new THREE.Mesh(new THREE.LatheGeometry(profile.map(([r,x])=>new THREE.Vector2(r,x)),48),skin);
    mesh.rotation.z = -Math.PI/2 + angle; mesh.position.set(...base); hand.add(mesh);
    const x=base[0]+Math.cos(angle)*length*.87, y=base[1]+Math.sin(angle)*length*.87;
    const tip=ellipsoid([x,y,base[2]+radius*.66],[length*.095,radius*.57,.65],nail);tip.rotation.z=angle;
  }
  ellipsoid([-39,-25,-1],[37,35,11]);
  ellipsoid([-72,-28,-2],[27,23,9]);
  digit([-10,0,0],74,7.7); // radius remains inside the sleeve's 8.5 mm minimum radius
  digit([-8,-19,-1],83,8.1,-.025);
  digit([-12,-38,-2],76,7.7,-.07);
  digit([-21,-55,-3],60,6.4,-.15);
  ellipsoid([-48,1,-3],[19,16,11]);
  digit([-42,8,-3],51,9,.67);
  hand.userData.illustrative = true;
  return hand;
}
