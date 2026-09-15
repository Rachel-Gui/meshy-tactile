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

- **Human arm latest** uses the 2026-09-14 mapping-fixed CSV: 6,631 supplied frames at 20 FPS, with combined playback and nine scene entries. Values, node order and 3× slow timing are preserved. See `human_arm/latest-data-manifest.json`.
- **Other action libraries** retain three Finger, three Robot Direct and three Robot contact-voltage clips.
- **Previous library (historical)** contained 12 actions: 3 additional Robot arm contact-voltage clips plus 9 Direct actions: 3 Human arm (96 nodes), 3 Finger (18 nodes), and 3 Robot arm (132 nodes). Each category has front touch, back touch and grab. See [the current data guide](../CURRENT_DATASET.md) for canonical XLSX paths and checksums.
- The frontend reads `public/action-library/manifest.json` and the corresponding JSON files. Signal Combined is interpolated to 20 FPS; original measurement timing, Raw and Baseline are retained.
- Finger's 18 measured nodes map to 18 of the model's 30 crossings; unused crossings are not additional measurements.
- **Live sensor** uses USB serial at 1,000,000 baud. Hosted Chrome/Edge uses Web Serial; local mode uses FastAPI.
- **Auto clear stale data** resets stable residual signals after five seconds. Disable for intentional sustained presses.
- CSV uploads support 18/96/132 nodes. Shared uploads persist in Vercel Blob online and SQLite locally; deletion requires the uploader's browser owner key.
- Everyone sees uploaded CSV/Excel recordings in the **Shared uploads** groups, including uploads for other models. The catalog refreshes every 30 seconds while the page is visible, on returning to the tab, or with **Refresh uploads**. Selecting an upload switches to its model; catalog refreshes do not restart playback. Existing saved uploads are included automatically.
- Hosted uploads require a connected private Vercel Blob store with `BLOB_READ_WRITE_TOKEN` available to the deployed project. The public catalog returns only recording metadata; CSV content is fetched when selected, and owner deletion keys remain private. Local SQLite catalogs are shared by visitors using the same app server.

Historical recordings and figures are in `../Archive/`; they are not built-in playback sources. Simulation and Zero controls have been removed. Grasshopper reload requires the local service.

Validate shared uploads with `python3 -m unittest web.server.test_shared_uploads -v` from the repository root and `node verify-shared-uploads.mjs` from `web/`.

## Update geometry

`ring.gh` uses **3 mm strip widths**, constructed with centreline offsets
of +1.5/-1.5 mm. `1.gh` retains **4 mm** widths (+2/-2 mm). The exported metadata records `stripWidth`
and the source GH checksum. `../Archive/model_backups/1.before-width4.gh` preserves the previous
6 mm arm definition. `../Archive/validation_reports/strip-width-validation.json` records the Rhino
solution checks for both models.

### Ring mode

The **Ring** button loads `public/assets/ring-model.json`, exported directly
from the repaired `../models/tactile/ring.gh`. It displays the woven strip mesh and its 30
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

Arm opens in **Sensor only**, showing the isolated sensor and heat field.
Select **On arm** to load and show a matte white display mannequin with a
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

Keep Rhino 8 and `/Users/a0000/Desktop/tactile/models/tactile/1.gh` open. Change the
Grasshopper sliders, wait for the solution to finish, then click **Reload** in
the Model geometry section. The dashboard exports the current `HeatmapMesh`
and the ordered 96 sensor positions without baking.

## Rebuild the frontend

```bash
cd /Users/a0000/Desktop/tactile/web
npm install
npm run build
```

## Recording source

Reviewed workbooks are exported to `public/action-library/` by:

```bash
/Users/a0000/anaconda3/bin/python tools/export_action_library.py
npm run build
node verify-action-library.mjs
```

The exporter uses the desktop viewer's mapping and 20 FPS interpolation.
Original workbooks are unchanged; unavailable measurements remain null in JSON.
Vite copies these assets into `dist/action-library/`; old built-in CSV assets
are no longer included. Previous persistent uploads were moved to
`../Archive/frontend_uploads_before_action_library_20260911/`.

Ring 3 mm validation: `../Archive/validation_reports/ring-width-3mm.json`.
Previous 4 mm Ring definition: `../Archive/model_backups/ring.before-width3.gh`.

### Robot arm mode

Open `http://127.0.0.1:8001/?model=robot`. The GH-exported sleeve is 250 mm long with 32 mm diameter at both ends and 132 mapped interior crossings. The Robot arm selector loads R001/R002/R003 reconstructed signals. Playback is interpolated to 20 FPS; the original 3/5/5 scan counts remain shown. Front/back labels and mounting orientation are provisional. USB live input remains the 96-channel protocol and is disabled in Robot arm mode.

The local Reload button saves/exports the active Robot arm GH definition through `export_robot_arm_model.py`. New model files: `models/robot_arm/robot_arm_132_32mm.gh` and `.3dm`.

## CSV upload preview

Upload CSV accepts the current Signal Combined worksheet exported as CSV: N001…N018 (Finger), N001…N096 (Human arm), or N001…N132 (Robot arm), with row-major node order. It auto-detects the model and preserves elapsed timing through 20 FPS interpolation. Supported time columns: action_elapsed_s, action_time_s, source_elapsed_s, source_time_s, or timestamp; without time columns it assumes 20 FPS. Values must be finite 0–1 responses. The old 96-point scan_index/raw_voltage_v/signal_0_to_1 CSV remains supported.

Uploaded CSV previews persist in private Vercel Blob storage in production and SQLite locally. Share preview creates a link readable by anyone who has it. Delete my upload requires the private owner key stored in the uploader’s browser localStorage; the share URL does not contain that key. Clearing browser storage loses deletion access. NEW and upload/recording timestamps are shown. Upload CSV or Excel .xlsx directly (maximum file size 3 MB; server request limit 4 MB). Excel imports select the Signal Combined sheet, or accept a single-sheet table with time and N001… columns. Older .xls files must be saved as .xlsx. The browser converts the selected sheet to CSV for shared storage; other workbook sheets and formatting are not stored.

Verification: node web/verify-upload-csv.mjs.

## Production deployment

GitHub `Rachel-Gui/meshy-tactile`, branch `main`, automatically deploys the Vercel `meshy-tactile` project with root directory `web` and Vite build. API entrypoints serve upload/share/delete only; local serial and Rhino control remain local. A connected private Blob store supplies `BLOB_READ_WRITE_TOKEN` (server-only). No credentials are committed.

### Camera and sensor capture

In Live recording, click **Open camera** and allow camera access (HTTPS or localhost).
Optionally select **Record camera video**, then **Start recording**. Press Space or
**Photo · Space** to capture stills. **Stop & save** downloads one ZIP containing
model.webm, optional camera.webm, photos/, alignment.json (all sensor values and
photo-to-nearest-frame matches), and sensor-timestamps.csv. Nothing is uploaded.
Keep the tab visible; recordings are held in memory until export, so use short
sessions and save before closing or refreshing the page. Audio is not captured.

All `tMs` values use the same browser monotonic session clock; the epoch anchor is
stored in `clock.epochStartMs`. Original sensor timestamps remain in `timestamp`.
Sensor alignment is browser receipt time, not hardware acquisition time. Photos
include click time and latest preview-frame timing when supported. Camera video
has session seconds and UTC burned into each rendered image; its rendered-frame
log is in `cameraVideo.renderedFrames`. Recorder start-event offsets are approximate,
not exact encoded presentation timestamps. Camera buffering and browser scheduling
mean this is not hardware-level synchronization. `nearestSensorFrame.deltaMs` is
sensor receipt minus photo click time; matches are null when no data arrived.

Validation: `node web/verify-camera-capture.mjs` from the repository root.
