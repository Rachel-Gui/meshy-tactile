# Current dataset

## Consolidated delivery — 20260914

Current sources for all three models are under `meshy_arm_finger_delivery_20260914/`. Human arm includes nine documented keyframes (combined source indices 291, 1539, 2187, 2760, 3273, 3966, 4851, 5553, 6327); Robot arm includes three; Finger includes 16 synchronized A/B keyframe pairs. All signal values and encoded mappings are retained exactly.

Frontend display gain defaults to 1.8× (adjustable); this is a visualization setting, not a change to normalized sensor measurements. Enhanced PNG exports use the same gain and a transparent foreground for Finger to reveal rear contact regions.

Earlier delivery notes below describe superseded source locations.

## Final Robot arm and Finger delivery

`meshy_arm_finger_delivery_Final/` is authoritative for the new Robot arm front-facing recordings and independent Finger A/B sequences. Robot playback contains the 938-frame combined recording plus RB004/RB003/RB001 clips; prior Robot Direct/voltage clips are retained on disk but removed from the active catalog. Human arm remains unchanged.

Finger Sleeve mode has three delivered A/B pairs (all8, group1, group2), available without manual upload, with 16 synchronized key-frame selections. Use the six 18-node files; the 36-node files are reference only. Keep sleeve rotations at 0 degrees. The catalog contains 17 single-model playback entries; the three Finger pairs use a separate catalog at `web/public/delivery-final/finger-pairs.json`.

Regenerate with `python3 web/tools/export_action_library.py`; verify with `node web/verify-delivery.mjs`. Key-frame screenshot provenance is in `outputs/delivery-final-keyframes/frames.json`.

## Latest Human arm override — 2026-09-14

The authoritative Human arm source is now `human_arm/00_ALL_9_SCENES_FRONT_FACING_3X_SLOW_SMOOTH_MAPPING_FIXED_UPLOAD.csv`: 96 nodes, 6,631 display frames, 9 scenes, 331.5 seconds at 20 FPS. Preserve the supplied front-facing mapping, smoothing and 3× slow timing. No extra interpolation or rotation is applied. Checksums and scene boundaries are in `human_arm/latest-data-manifest.json`.

The frontend has 19 entries: the combined Human arm recording, its nine scenes, three Finger Direct actions, three Robot Direct actions and three Robot contact-voltage actions. Earlier Human arm XLSX files and the workbook index remain historical; the desktop XLSX viewer is unchanged.

Regenerate with `python3 web/tools/export_action_library.py`, build with `npm --prefix web run build`, then run `node web/verify-action-library.mjs`, `node web/verify-playback-data-preview.mjs` and `python3 web/tools/verify_human_arm_latest.py`.

## Previous Direct baseline

Version: **2026-09-13 Direct**, containing 9 Direct actions plus 3 Robot arm contact-voltage actions (12 total). Each category has front_touch, back_touch and grab.

| Category | Nodes | Canonical XLSX directory | IDs: front / back / grab |
|---|---:|---|---|
| Human arm | 96 | `human_arm/action_library/96point_12x8/segments/` | E025 / E022 / E009 |
| Robot arm | 132 | `robot_arm/action_library/robot_arm_132node/segments/` | R003 / R007 / R004 |
| Finger | 18 | `finger/action_library/18point_6x6_sparse/segments/` | E015 / E008 / E007 |

Index: [action_index.xlsx](action_index.xlsx). Source paths and SHA-256 checksums: [current-data-manifest.json](current-data-manifest.json). Maintain these canonical directories; the former `new` import package is archived.

The frontend loads `web/public/action-library/manifest.json` and its JSON clips. The desktop viewer reads the canonical XLSX files. Signal Combined is the primary signal, interpolated to 20 FPS for playback. Original measurement times, Raw and Baseline are retained; interpolation does not create additional measurements.

After updating source workbooks, update the index and checksum manifest, then run:

```bash
python3 web/tools/export_action_library.py
node web/verify-action-library.mjs
node web/verify-playback-data-preview.mjs
npm --prefix web run build
```

Deploy to update the public dashboard. User-uploaded datasets are separate from these 9 built-in actions.

## Archives

- `Archive/data_before_direct_2026-09-13/`: previous 60-action library, frontend JSON and historical tools.
- `Archive/data_consolidation_2026-09-13/new/`: original import package; its 9 action files are byte-identical to the canonical sources. Its index retains the original import paths.
- `Archive/data_consolidation_2026-09-13/{human_arm,finger}/recordings/`: previous raw recordings.
- Figure directories within that archive contain historical plots, not plots of the current 9 actions.
- `moves.json` records each original path, archive path and SHA-256 checksum. No source data was deleted.

## Robot arm contact-voltage addition

Canonical source: `robot_arm/action_library/contact_voltage_display/`.
RB004 axial_column (281 display frames), RB003 pinch_end (535), RB001 palm_grab (122).
The combined CSV repeats those 938 rows and is not a fourth catalog entry.
These files contain volts with masked cells, not normalized Signal Combined.
The frontend preserves voltage and nulls, uses a shared 0–2.10 V inverse color scale,
and does not repeat the source display flips/shifts or interpolate again.
Original Direct workbooks and action_index.xlsx remain unchanged; the additional CSV
source checksums are in that directory's manifest.json. arm/ retains the import copy.
