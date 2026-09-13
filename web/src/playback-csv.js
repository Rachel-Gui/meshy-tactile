const REQUIRED_COLUMNS = ['scan_index', 'raw_voltage_v', 'signal_0_to_1'];

function parseLegacyCsv(text, sensorCount = 96) {
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
  if (!frames.length) throw new Error(`CSV contains no complete ${sensorCount}-point frames`);

  return { rows: rowCount, frames, sample };
}

// RFC-style quoted cells, BOM, CRLF, and Excel comma/semicolon/tab exports.
function csvRows(text) {
  const clean = text.replace(/^\uFEFF/, '');
  const first = clean.split(/\r?\n/, 1)[0];
  const separator = first.includes('\t') ? '\t' : first.includes(';') && !first.includes(',') ? ';' : ',';
  const rows = []; let row = []; let cell = ''; let quoted = false;
  for (let i = 0; i < clean.length; i++) {
    const c = clean[i];
    if (c === '"') {
      if (quoted && clean[i + 1] === '"') { cell += '"'; i++; }
      else if (quoted || !cell.length) quoted = !quoted;
      else throw new Error('Invalid CSV quoting');
    } else if (!quoted && (c === separator || c === '\n' || c === '\r')) {
      row.push(cell.trim()); cell = '';
      if (c !== separator) {
        if (row.some(v => v !== '')) rows.push(row);
        row = [];
        if (c === '\r' && clean[i + 1] === '\n') i++;
      }
    } else cell += c;
  }
  if (quoted) throw new Error('CSV contains an unclosed quoted field');
  row.push(cell.trim()); if (row.some(v => v !== '')) rows.push(row);
  return rows;
}

export function parsePlaybackCsv(text, sensorCount = 96) {
  const rows = csvRows(text); const headers = rows.shift();
  if (!headers) throw new Error('The selected CSV is empty');
  if (new Set(headers).size !== headers.length) throw new Error('CSV contains duplicate column names');
  const nodes = headers.map((name, index) => ({name,index,number:Number(name.slice(1))}))
    .filter(n => /^N\d+$/i.test(n.name)).sort((a,b)=>a.number-b.number);
  if (!nodes.length) return parseLegacyCsv(text, sensorCount);
  const count = nodes.length;
  if (![18,96,132].includes(count) || nodes.some((n,i)=>n.number!==i+1)) {
    throw new Error('Expected consecutive N001–N018, N001–N096, or N001–N132 columns');
  }
  if (!rows.length) throw new Error('CSV has no measured frames');
  const col = name => headers.indexOf(name);
  const timeColumn = ['action_elapsed_s','action_time_s','source_elapsed_s','source_time_s'].map(col).find(i=>i>=0);
  const timestampColumn = col('timestamp');
  const measuredTimes = []; const measured = [];
  for (const [i,row] of rows.entries()) {
    if (row.length !== headers.length) throw new Error(`CSV row ${i+2} has an incorrect number of columns`);
    const values = nodes.map(n => {
      if (row[n.index] === '') throw new Error(`Missing ${n.name} at row ${i+2}`);
      const value = Number(row[n.index]);
      if (!Number.isFinite(value) || value<0 || value>1) throw new Error(`Row ${i+2}: upload Signal Combined (0–1), not Raw Data or voltage`);
      return value;
    });
    const t = timeColumn !== undefined ? (row[timeColumn] === '' ? NaN : Number(row[timeColumn]))
      : timestampColumn >= 0 ? Date.parse(row[timestampColumn])/1000 : i*.05;
    if (!Number.isFinite(t) || (i>0 && t<=measuredTimes[i-1])) throw new Error('Recording times must be valid and strictly increasing');
    measuredTimes.push(t); measured.push(values);
  }
  const start=measuredTimes[0]; const times=measuredTimes.map(t=>t-start);
  const total=Math.ceil(times.at(-1)*20-1e-7)+1;
  if (total*count>6_000_000) throw new Error('Recording is too long for browser preview; upload a shorter clip');
  const frames=[]; let left=0;
  for(let i=0;i<total;i++) {
    const t=i/20;
    while(left+1<times.length && times[left+1]<=t) left++;
    const right=Math.min(left+1,times.length-1);
    const mix=right===left?0:Math.min(1,(t-times[left])/(times[right]-times[left]));
    frames.push({values:measured[left].map((v,j)=>v+(measured[right][j]-v)*mix),rawVolts:Array(count).fill(NaN)});
  }
  const columns=count===96?8:count===132?12:6;
  const coordinates=Array.from({length:count},(_,i)=>count===18
    ? {row:(i%6+Math.floor(i/6))%6+1,column:i%6+1}
    : {row:Math.floor(i/columns)+1,column:i%columns+1});
  return {sensorCount:count,rows:rows.length,frames,sample:[],fps:20,originalFrames:rows.length,
    interpolated:total!==rows.length || times.some((t,i)=>Math.abs(t-i/20)>1e-6),
    times:Array.from({length:total},(_,i)=>i/20),measuredTimes:times,coordinates,
    labels:nodes.map(n=>n.name),source:'Uploaded CSV',signalLayer:'Signal Combined',
    recordedAt:timestampColumn>=0?rows[0][timestampColumn]:null,
    timingSource:timeColumn!==undefined?headers[timeColumn]:timestampColumn>=0?'timestamp':'assumed 20 FPS',
    missingSamples:0};
}
