export const SERIAL_BAUD_RATE = 1_000_000;

const ROWS = 12;
const COLUMNS = 8;
const SENSOR_COUNT = ROWS * COLUMNS;
const VREF = 3.3;
const PHYSICAL_PIN_MAP = [1, 3, 5, 7, 2, 4, 6, 8, 10, 12, 14, 16];
const AUTO_CLEAR_IDLE_MS = 5000;
const AUTO_CLEAR_CHANGE_EPSILON = 0.015;
const AUTO_CLEAR_SIGNAL_THRESHOLD = 0.05;

export function webSerialSupported() {
  return 'serial' in navigator;
}

export function scanPoints() {
  return Array.from({ length: SENSOR_COUNT }, (_, index) => {
    const row = Math.floor(index / COLUMNS);
    const cyclicOffset = (index % COLUMNS) + 1;
    return [
      PHYSICAL_PIN_MAP[row] - 1,
      PHYSICAL_PIN_MAP[(row + cyclicOffset) % ROWS] - 1,
    ];
  });
}

export function signalFromHistory(voltage, history) {
  if (history.length < 4) return 0;
  const sorted = [...history].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  const baseline = sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
  const threshold = Math.max(0.12, baseline * 0.15);
  const fullDrop = Math.max(baseline * 0.5, threshold + baseline * 0.1);
  const pressureDrop = baseline - voltage;
  if (pressureDrop <= threshold) return 0;
  return Math.max(0, Math.min(1, (pressureDrop - threshold) / (fullDrop - threshold)));
}

function deviceLabel(port) {
  const { usbVendorId, usbProductId } = port.getInfo();
  if (usbVendorId === undefined) return 'USB serial';
  const vendor = usbVendorId.toString(16).padStart(4, '0');
  const product = usbProductId?.toString(16).padStart(4, '0');
  return product ? `USB ${vendor}:${product}` : `USB ${vendor}`;
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export class WebSerialSensor {
  constructor({ onFrame, onStatus }) {
    this.onFrame = onFrame;
    this.onStatus = onStatus;
    this.session = null;
    this.sequence = 0;
    this.autoClearEnabled = true;
    this.autoClearCount = 0;
  }

  get connected() {
    return Boolean(this.session?.running);
  }

  setAutoClearEnabled(enabled) {
    this.autoClearEnabled = enabled;
    if (this.session) this.resetAutoClearTracking(this.session);
  }

  resetCalibration() {
    if (!this.session) return;
    this.session.histories.forEach((history) => history.splice(0));
    this.resetAutoClearTracking(this.session);
  }

  resetAutoClearTracking(session) {
    session.lastValues.fill(0);
    session.lastSignalChangeAt = performance.now();
    session.autoClearArmed = false;
  }

  async connect() {
    if (!webSerialSupported()) throw new Error('Web Serial is not supported by this browser');
    if (this.connected) return this.session.label;

    const port = await navigator.serial.requestPort();
    try {
      await port.open({
        baudRate: SERIAL_BAUD_RATE,
        dataBits: 8,
        stopBits: 1,
        parity: 'none',
        flowControl: 'none',
        bufferSize: 4096,
      });
      this.onStatus?.({ state: 'opening', label: deviceLabel(port) });
      await delay(2000);
      if (!port.readable || !port.writable) throw new Error('The serial port could not be opened');

      const session = {
        port,
        label: deviceLabel(port),
        reader: port.readable.getReader(),
        writer: port.writable.getWriter(),
        queue: [],
        running: true,
        histories: Array.from({ length: SENSOR_COUNT }, () => []),
        lastValues: new Float32Array(SENSOR_COUNT),
        lastSignalChangeAt: performance.now(),
        autoClearArmed: false,
        done: null,
      };
      this.session = session;
      this.onStatus?.({ state: 'connected', label: session.label });
      session.done = this.scanLoop(session);
      return session.label;
    } catch (error) {
      try {
        await port.close();
      } catch {
        // The port may already be closed.
      }
      throw error;
    }
  }

  async disconnect() {
    const session = this.session;
    if (!session) return;
    session.running = false;
    try {
      await session.reader.cancel();
    } catch {
      // A disconnected device may reject cancellation.
    }
    await session.done;
  }

  async readByte(session, deadline) {
    while (!session.queue.length) {
      const remaining = deadline - performance.now();
      if (remaining <= 0) throw new Error('Serial response timed out');
      let timeoutId;
      const timeout = new Promise((_, reject) => {
        timeoutId = setTimeout(() => reject(new Error('Serial response timed out')), remaining);
      });
      const result = await Promise.race([session.reader.read(), timeout]);
      clearTimeout(timeoutId);
      if (result.done) throw new Error('The serial device was disconnected');
      if (result.value) session.queue.push(...result.value);
    }
    return session.queue.shift();
  }

  async requestPoint(session, row, column) {
    await session.writer.write(Uint8Array.of('p'.charCodeAt(0), row, column));
    const deadline = performance.now() + 2000;
    let previous = -1;
    let headerFound = false;
    while (performance.now() < deadline) {
      const current = await this.readByte(session, deadline);
      if (previous === 0xA5 && current === 0x5A) {
        headerFound = true;
        break;
      }
      previous = current;
    }
    if (!headerFound) throw new Error('Point response header was not received');

    const responseRow = await this.readByte(session, deadline);
    const responseColumn = await this.readByte(session, deadline);
    const sample = await this.readByte(session, deadline);
    const checksum = await this.readByte(session, deadline);
    const expected = 0xA5 ^ 0x5A ^ responseRow ^ responseColumn ^ sample;
    if (checksum !== expected) throw new Error('Point response checksum error');
    if (responseRow !== row || responseColumn !== column) {
      throw new Error('Point response address mismatch');
    }
    return sample;
  }

  processAutoClear(session, values) {
    const now = performance.now();
    const maximumSignal = Math.max(...values);
    let maximumChange = 0;
    values.forEach((value, index) => {
      maximumChange = Math.max(maximumChange, Math.abs(value - session.lastValues[index]));
    });

    let autoCleared = false;
    if (!this.autoClearEnabled || maximumSignal < AUTO_CLEAR_SIGNAL_THRESHOLD) {
      session.autoClearArmed = false;
      session.lastSignalChangeAt = now;
    } else if (!session.autoClearArmed) {
      session.autoClearArmed = true;
      session.lastSignalChangeAt = now;
    } else if (maximumChange >= AUTO_CLEAR_CHANGE_EPSILON) {
      session.lastSignalChangeAt = now;
    } else if (now - session.lastSignalChangeAt >= AUTO_CLEAR_IDLE_MS) {
      session.histories.forEach((history) => history.splice(0));
      values.fill(0);
      session.autoClearArmed = false;
      session.lastSignalChangeAt = now;
      this.autoClearCount += 1;
      autoCleared = true;
    }
    session.lastValues.set(values);
    return autoCleared;
  }

  async scanLoop(session) {
    let failure = null;
    try {
      const points = scanPoints();
      while (session.running) {
        const rawVolts = new Float32Array(SENSOR_COUNT);
        const values = new Float32Array(SENSOR_COUNT);
        for (let index = 0; index < points.length && session.running; index += 1) {
          const [row, column] = points[index];
          const sample = await this.requestPoint(session, row, column);
          const voltage = sample * (VREF / 255);
          rawVolts[index] = voltage;
          const history = session.histories[index];
          const signal = signalFromHistory(voltage, history);
          values[index] = signal;
          if (signal < 0.05) {
            history.push(voltage);
            if (history.length > 24) history.shift();
          }
        }
        if (!session.running) break;
        this.processAutoClear(session, values);
        this.onFrame?.({
          values,
          rawVolts,
          sequence: ++this.sequence,
          label: session.label,
          autoClearEnabled: this.autoClearEnabled,
          autoClearCount: this.autoClearCount,
        });
      }
    } catch (error) {
      if (session.running) failure = error;
    } finally {
      session.running = false;
      try {
        await session.reader.cancel();
      } catch {
        // Ignore cleanup errors after unplugging.
      }
      try {
        session.reader.releaseLock();
        session.writer.releaseLock();
      } catch {
        // Locks can already be released after an operating-system disconnect.
      }
      try {
        await session.port.close();
      } catch {
        // The operating system may have already closed it.
      }
      if (this.session === session) this.session = null;
      this.onStatus?.({
        state: failure ? 'error' : 'disconnected',
        label: session.label,
        error: failure,
      });
    }
  }
}
