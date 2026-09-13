export function parseActionClip(data) {
  const count = data.sensorCount;
  if (![18, 96, 132].includes(count) || !data.signal?.length || data.labels.length !== count
      || data.times.length !== data.signal.length) throw new Error('Invalid action clip');
  for (const field of ['signal', 'raw', 'baseline']) {
    if (data[field] == null) continue;
    if (data[field].length !== data.signal.length || data[field].some(row => row.length !== count || row.some(v => v !== null && !Number.isFinite(v)))) {
      throw new Error(`Invalid ${field} samples`);
    }
  }
  const frames = data.signal.map((values, i) => ({
    values: values.map(v => v ?? 0), rawVolts: data.raw?.[i]?.map(v => v ?? NaN) ?? Array(count).fill(NaN), baseline: data.baseline?.[i] ?? null,
  }));
  return { ...data, frames, rows: frames.length * count, sample: [], missingSamples: ['signal','raw','baseline'].reduce((total, key) => total + (data[key] || []).reduce((n, row) => n + row.filter(v => v === null).length, 0), 0) };
}
