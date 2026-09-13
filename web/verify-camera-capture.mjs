import assert from 'node:assert/strict';
import { nearestFrame, recordStream } from './src/camera-capture.js';
assert.equal(nearestFrame([], 3), null);
const frames = [{ tMs: 10, sequence: 1 }, { tMs: 30, sequence: 2 }, { tMs: 90, sequence: 3 }];
assert.equal(nearestFrame(frames, 0).index, 0);
assert.equal(nearestFrame(frames, 100).index, 2);
assert.equal(nearestFrame(frames, 20).index, 0);
assert.equal(nearestFrame(frames, 28).deltaMs, 2);
assert.equal(nearestFrame(frames, 32).deltaMs, -2);
class Recorder extends EventTarget {
  state = 'inactive';
  start() { this.state = 'recording'; this.dispatchEvent(new Event('start')); }
  stop() {
    this.state = 'inactive';
    const event = new Event('dataavailable'); event.data = new Blob(['last chunk']);
    this.dispatchEvent(event); this.dispatchEvent(new Event('stop'));
  }
}
globalThis.MediaRecorder = Recorder;
const recording = recordStream({}, performance.now(), 'video/webm');
assert.ok(recording.timing.startedEventMs >= 0);
const blob = await recording.stop();
assert.equal(await blob.text(), 'last chunk');
assert.equal(await recording.stop(), blob, 'retry retains final recording');
console.log('Camera alignment boundaries and recorder final-chunk/retry checks passed');
