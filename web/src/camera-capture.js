// All alignment uses the browser monotonic clock, never the device clock.
export function nearestFrame(frames, tMs) {
  if (!frames.length) return null;
  let lo = 0, hi = frames.length;
  while (lo < hi) { const mid = (lo + hi) >>> 1; if (frames[mid].tMs < tMs) lo = mid + 1; else hi = mid; }
  const index = lo === frames.length ? lo - 1 : lo > 0 && tMs - frames[lo - 1].tMs <= frames[lo].tMs - tMs ? lo - 1 : lo;
  return { index, sequence: frames[index].sequence, tMs: frames[index].tMs, deltaMs: frames[index].tMs - tMs };
}

export function recordStream(stream, origin, mimeType) {
  const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 6_000_000 });
  const chunks = [], timing = { requestedStartMs: performance.now() - origin, startedEventMs: null, errors: [] };
  recorder.addEventListener('start', () => { timing.startedEventMs = performance.now() - origin; });
  recorder.addEventListener('dataavailable', event => { if (event.data.size) chunks.push(event.data); });
  recorder.addEventListener('error', event => timing.errors.push(event.error?.message || 'Media recorder error'));
  const done = new Promise(resolve => recorder.addEventListener('stop', () => resolve(new Blob(chunks, { type: mimeType })), { once: true }));
  recorder.start(1000);
  return { timing, stop() { if (recorder.state !== 'inactive') recorder.stop(); return done; } };
}

export function createCameraCapture(getSession, report) {
  const video = document.querySelector('#camera-preview');
  const toggle = document.querySelector('#camera-toggle');
  const photo = document.querySelector('#camera-photo');
  const option = document.querySelector('#camera-record-video');
  const status = document.querySelector('#camera-status');
  let stream = null, opening = false, lastFrame = null, callback = null;
  function update() {
    const session = getSession();
    toggle.disabled = opening || Boolean(session);
    toggle.textContent = stream ? 'Close camera' : 'Open camera';
    option.disabled = Boolean(session);
    photo.disabled = !stream || !session || session.stopping;
    video.hidden = !stream;
  }
  function trackFrame(now, metadata) {
    lastFrame = { observedPerformanceMs: now, previewMediaTimeSeconds: metadata.mediaTime, presentedFrames: metadata.presentedFrames };
    callback = video.requestVideoFrameCallback(trackFrame);
  }
  function close() {
    if (callback !== null) video.cancelVideoFrameCallback?.(callback);
    stream?.getTracks().forEach(track => track.stop());
    stream = null; video.srcObject = null; lastFrame = null; update();
  }
  toggle.addEventListener('click', async () => {
    if (stream) { close(); status.textContent = 'Camera off'; return; }
    opening = true; update();
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera requires HTTPS or localhost and a supported browser.');
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      video.srcObject = stream;
      await video.play();
      if (video.requestVideoFrameCallback) callback = video.requestVideoFrameCallback(trackFrame);
      stream.getVideoTracks()[0].addEventListener('ended', () => { const session = getSession(); if (session) session.cameraDisconnectedMs = performance.now() - session.startedPerformance; close(); report('Camera disconnected. Stop & save to preserve captured data.'); });
      status.textContent = 'Camera ready · no audio';
    } catch (error) { close(); report(`Camera: ${error.message}`); }
    finally { opening = false; update(); }
  });
  function takePhoto() {
    const session = getSession();
    if (!stream || !session || session.stopping || video.readyState < 2) return;
    const tMs = performance.now() - session.startedPerformance;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const entry = { filename: `photos/photo-${String(session.photos.length + 1).padStart(4, '0')}.jpg`, tMs, timestamp: new Date(session.startedAt.getTime() + tMs).toISOString(), previewFrame: lastFrame ? { ...lastFrame, tMs: lastFrame.observedPerformanceMs - session.startedPerformance } : null };
    session.photos.push(entry);
    session.pendingPhotos.push(new Promise(resolve => canvas.toBlob(blob => { entry.blob = blob; if (!blob) entry.error = 'JPEG encoding failed'; resolve(); }, 'image/jpeg', 0.95)));
    status.textContent = `${session.photos.length} photos · latest ${(tMs / 1000).toFixed(3)} s`;
  }
  photo.addEventListener('click', takePhoto);
  window.addEventListener('keydown', event => {
    if (event.code !== 'Space' || event.repeat || event.ctrlKey || event.metaKey || event.altKey || event.target.closest?.('input, textarea, select, [contenteditable="true"]')) return;
    if (stream && getSession() && !getSession().stopping) { event.preventDefault(); takePhoto(); }
  });
  window.addEventListener('pagehide', close);
  return {
    update,
    start(session, mimeType) {
      if (option.checked && !stream) throw new Error('Open the camera before starting camera video.');
      session.photos = []; session.pendingPhotos = []; session.cameraFrames = [];
      if (!option.checked) return;
      // Record a canvas with the session time burned into every rendered image.
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      function draw() {
        const tMs = performance.now() - session.startedPerformance;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#000b'; ctx.fillRect(0, canvas.height - 36, canvas.width, 36);
        ctx.fillStyle = '#fff'; ctx.font = '18px monospace';
        ctx.fillText(`Session ${(tMs / 1000).toFixed(3)} s | ${new Date(session.startedAt.getTime() + tMs).toISOString()}`, 10, canvas.height - 12);
        session.cameraFrames.push({ tMs, previewMediaTimeSeconds: lastFrame?.previewMediaTimeSeconds ?? null });
      }
      draw();
      const capture = canvas.captureStream(30);
      const recording = recordStream(capture, session.startedPerformance, mimeType);
      const timer = setInterval(draw, 1000 / 30);
      session.cameraRecording = { timing: recording.timing, async stop() { clearInterval(timer); const blob = await recording.stop(); capture.getTracks().forEach(track => track.stop()); return blob; } };
    },
  };
}
