const REQUIRED_COLUMNS = ['scan_index', 'raw_voltage_v', 'signal_0_to_1'];

export function parsePlaybackCsv(text, sensorCount = 96) {
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/);
  const headerLine = lines.shift();
  if (!headerLine) throw new Error('The selected CSV is empty');

  const headers = headerLine.split(',').map((header) => header.trim());
  const columns = Object.fromEntries(headers.map((header, index) => [header, index]));
  const missing = REQUIRED_COLUMNS.filter((column) => columns[column] === undefined);
  if (missing.length) throw new Error(`CSV is missing required columns: ${missing.join(', ')}`);

  const frames = [];
  const sample = [];
  let values = new Float32Array(sensorCount);
  let rawVolts = new Float32Array(sensorCount);
  let seen = new Uint8Array(sensorCount);
  let seenCount = 0;
  let rowCount = 0;

  const finishFrame = () => {
    if (seenCount === sensorCount) frames.push({ values, rawVolts });
    values = new Float32Array(sensorCount);
    rawVolts = new Float32Array(sensorCount);
    seen = new Uint8Array(sensorCount);
    seenCount = 0;
  };

  lines.forEach((line) => {
    if (!line.trim()) return;
    rowCount += 1;
    const cells = line.split(',');
    const scanIndex = Number.parseInt(cells[columns.scan_index], 10);
    const index = scanIndex - 1;
    const voltage = Number.parseFloat(cells[columns.raw_voltage_v]);
    const signal = Number.parseFloat(cells[columns.signal_0_to_1]);
    if (!Number.isInteger(index) || index < 0 || index >= sensorCount
      || !Number.isFinite(voltage) || !Number.isFinite(signal)) return;

    if (index === 0 && seenCount > 0) finishFrame();
    if (!seen[index]) {
      seen[index] = 1;
      seenCount += 1;
    }
    values[index] = Math.max(0, Math.min(1, signal));
    rawVolts[index] = voltage;

    if (sample.length < 5) {
      const sensorRow = cells[columns.sensor_row] || String(Math.floor(index / 8) + 1);
      const point = cells[columns.point_in_row] || String((index % 8) + 1);
      sample.push({
        scanIndex: String(scanIndex),
        sensor: `R${sensorRow} · P${point}`,
        voltage: Number.isFinite(voltage) ? voltage.toFixed(6) : '—',
        signal: Number.isFinite(signal) ? signal.toFixed(6) : '—',
      });
    }
  });
  if (seenCount > 0) finishFrame();
  if (!frames.length) throw new Error('CSV contains no complete 96-point frames');

  return { rows: rowCount, frames, sample };
}
