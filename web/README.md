# Tactile 3D Dashboard

Local macOS dashboard for the 96-point Grasshopper tactile model.

## Start

Double-click `start_dashboard.command`, then open:

```text
http://127.0.0.1:8001
```

Or run:

```bash
cd /Users/a0000/Desktop/tactile
/Users/a0000/anaconda3/bin/python -m uvicorn web.server.app:app --host 127.0.0.1 --port 8001
```

## Data modes

- **Simulation** works without hardware and sends 96 animated values.
- **Recorded data** accepts CSV uploads directly in the dashboard. Files must
  contain `scan_index`, `raw_voltage_v`, and `signal_0_to_1`, include at least
  one complete 96-point frame, and be no larger than 100 MB. Uploaded files are
  kept in `uploaded_playback_data/` so they remain available after a restart.
- **Live sensor** auto-detects a `usbserial` or `usbmodem` port and uses the
  existing one-point protocol at 1,000,000 baud.
- **Auto clear stale data** is enabled by default. In live sensor mode, a
  non-zero signal that stops changing for five seconds is automatically reset
  and recalibrated. Turn it off for intentional long, static presses.
- **Zero** clears the per-sensor rolling baselines. Keep the sensor untouched
  briefly after calibration.

On the hosted Vercel site, Simulation and Recorded data run completely in the
browser. The five built-in CSV recordings are published with the frontend, and
an uploaded CSV remains private to the current browser tab. Live USB sensor,
Grasshopper reload, persistent uploads, and automatic live-sensor clearing use
the local FastAPI app because a hosted website cannot access those local
devices or files.

## Update geometry

Keep Rhino 8 and `/Users/a0000/Desktop/tactile/1.gh` open. Change the
Grasshopper sliders, wait for the solution to finish, then click **Reload** in
the Model geometry section. The dashboard exports the current `HeatmapMesh`
and the ordered 96 sensor positions without baking.

## Rebuild the frontend

```bash
cd /Users/a0000/Desktop/tactile/web
npm install
npm run build
```
