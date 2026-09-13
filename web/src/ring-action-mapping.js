// Display registration only: six source columns wrap around the Rhino X axis.
// Source slot (row-column mod 6) selects the low/middle/high X crossing tier.
// No physical wiring calibration is implied by this geometric registration.
export function createRingActionMapping(coordinates, sensors) {
  if (coordinates.length !== 18 || sensors.length !== 30) throw new Error('Expected 18 nodes and 30 Ring crossings');
  const sorted = [...sensors].sort((a, b) => a.position[0] - b.position[0]);
  const tiers = [sorted.slice(0, 10), sorted.slice(10, 20), sorted.slice(20)];
  const used = new Set();
  const mapping = coordinates.map(({ row, column }) => {
    const slot = (row - column + 6) % 6;
    if (slot > 2 || column < 1 || column > 6) throw new Error('Invalid sparse coordinate');
    const angle = (column - 1) * Math.PI / 3;
    const candidates = tiers[slot].map(sensor => {
      const delta = Math.atan2(sensor.position[2], sensor.position[1]) - angle;
      return { index: sensor.index, distance: Math.abs(Math.atan2(Math.sin(delta), Math.cos(delta))) };
    }).sort((a, b) => Math.abs(a.distance - b.distance) < 1e-5 ? a.index - b.index : a.distance - b.distance);
    const target = candidates[0].index;
    if (!Number.isInteger(target) || target < 0 || target >= 30 || used.has(target)) throw new Error('Ring mapping must be one-to-one');
    used.add(target);
    return target;
  });
  return mapping;
}

export function mapRingActionFrame(frame, mapping) {
  const values = new Float32Array(96);
  const rawVolts = new Float32Array(96).fill(NaN);
  mapping.forEach((target, source) => {
    values[target] = frame.values[source];
    rawVolts[target] = frame.rawVolts[source];
  });
  return { values, rawVolts };
}
