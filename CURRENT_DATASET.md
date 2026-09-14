# Current dataset

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
