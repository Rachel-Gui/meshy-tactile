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
an uploaded CSV remains private to the current browser tab. On desktop Chrome
or Edge, **Live sensor** uses Web Serial to talk directly to the selected USB
device at 1,000,000 baud; sensor data never passes through Vercel. Baseline
calibration and automatic stale-data clearing also run in the browser.
Grasshopper reload and persistent uploads still require the local FastAPI app.

## Update geometry

Both `ring.gh` and `1.gh` use **4 mm strip widths**, constructed with
centreline offsets of +2/-2 mm. The exported metadata records `stripWidth`
and the source GH checksum. `1.before-width4.gh` preserves the previous
6 mm arm definition. `../strip-width-validation.json` records the Rhino
solution checks for both models.

### Ring mode

The **Ring** button loads `public/assets/ring-model.json`, exported directly
from the repaired `../ring.gh`. It displays the woven strip mesh and its 30
internal sensor crossings (27 mm long, 17/18 mm end diameters). The default
heat radius is 3 mm. Sensor labels and angles refer to actual strip crossings.

To update this asset, run `web/export_ring_model.py` in Rhino 8 with
`_-RunPythonScript`, then run `npm run build` for the local backend/production
frontend. Ring's **Reload** button rereads the exported asset; it does not run
the arm exporter. Viewing the exported Ring model does not require Rhino.

Crossing indices preserve the GH `SensorIntersections` list order. Existing
96-channel data sources currently drive Ring with their first 30 values;
hardware channel-to-crossing calibration is not supplied by this geometry
export. The original arm channel mapping remains separate.

Run `node verify-ring-frontend.mjs` to check export identity, mesh integrity,
localized heat response and Arm/Ring switching using the actual Three.js
loader code. This automated check does not render a browser screenshot.

### Arm mode

Arm opens in the **On arm** scene: a matte white display mannequin with a
hand, forearm and upper arm. **Sensor only** returns to the isolated sensor.
The scene is hidden automatically in Ring mode. Heatmap inputs and the original
GH sensor mesh are unchanged. Sensor markers respect arm occlusion when worn.

`public/assets/arm-mannequin.glb` uses MakeHuman's CC0 anatomical arm topology,
posed with a bent elbow, dropped wrist and spread fingers, and fitted to the
current 250 mm sleeve and 35/62 mm reference radii. It is not a body scan.
See `model-source/README.md` for attribution. Run
`python generate-arm-mannequin.py` (numpy required) to regenerate it, then
`node verify-wearing-scene.mjs` to check the fit and scene switching.
The fit check samples the actual strip mesh and verifies a sub-3.5 mm gap
to the underlying arm. Refit/regenerate this scene if sleeve dimensions change.

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
