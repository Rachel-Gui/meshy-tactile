# Finger action heatmap library

Reviewed finger-sensor action data is collected here; arm data lives in
`../arm/96point_12x8/`. This organization preserves the
original recordings or the earlier processed-result folders.

## Subfolders

- `30point_recordings_18node_sparse/`: actions extracted from older 30-point
  scans and mapped to the corrected 18-node sparse 6x6 McKibben topology.
  Regenerate with `ESP32 reader/tools/grip/process_finger_recordings_6x3.py`.
- `18point_6x6_sparse/`: 16 individual 18-node sparse 6x6 action clips plus
  their index. Regenerate with
  `ESP32 reader/tools/grip/extract_18point_action_segments.py`.
- `../arm/96point_12x8/`: 29 individual arm full-layout action clips plus their index.
  Regenerate with
  `ESP32 reader/tools/grip/extract_96point_action_segments.py`.

## Clip framing

Every clip runs baseline to baseline. Each one reaches back from the reviewed
contact core to a settled pre-contact lead-in and forward through the release,
so an action can be read as a whole instead of opening at peak signal. An edge
settles on the calmest frame within reach rather than on a fixed threshold,
because these recordings rest at whatever level their stuck nodes hold, not at
zero. A lead may reach back to the previous action's core and a release forward
to the next one's, so neighbouring clips can share the quiet stretch between
them.

Five clips still cannot open or close on the baseline, because the recording
never returns there inside the room available: `A006`, `A011` (30-point) and
`E004`, `E005`, `E006` (18-point). In each case the reviewed cores are adjacent
or a stuck node holds a constant floor.

## One viewer for everything

Run from the tactile project root:

```bash
python3 "finger_action_library/view_all_heatmaps.py"
```

Use the **Dataset** dropdown to select 30, 18, or 96 points. Use the
**Action/file** dropdown to jump directly to any reviewed action. The frame
slider, frame buttons, and Play button navigate inside the selected clip.
The colored **当前动作** box shows the current action type: blue for front
touch, orange for back touch, and green for grasp.

Slow recordings are display-resampled to approximately 20 FPS (`0.05 s` per
frame) with time-linear interpolation of Raw, Baseline, and Signal. This only
improves playback; the source workbooks and measured frame counts are not
changed. The status line identifies interpolated playback.

Keyboard shortcuts:

- Left/Right: previous/next frame.
- PageUp/PageDown: previous/next action.
- Space: play/pause.

Both 18-node datasets use six global rows and six columns. Their occupied-row
pattern is `123`, `234`, `345`, `456`, `561`, `612`, so each column contains
three nodes and adjacent columns share two rows. The viewer draws them as a
dense **3x6** grid ordered by column: display column *i* is McKibben column
*i*, and display rows 1-3 are that column's three nodes in topology order.
The empty crossings of the sparse 6x6 frame are not drawn at all.

For the individual 18-node and 96-point clips, the viewer shows Raw Data, the
time-varying Baseline, and cleaned Signal together. The older combined
30-point-source workbook contains processed Signal only, so its corrected
sparse 6x6 Signal panel is shown alone. The superseded compressed 3-row copy is
kept only under `../Archive/legacy_action_data/30point_recordings_18node_sparse/legacy_compressed_mapping/` and is not loaded by the viewer.

## Archived versions

Superseded press-only workbooks and clips are in
`../Archive/legacy_action_data/`, preserving their dataset subdirectories.
The regeneration scripts named above belong to the original ESP32 reader
project and are not included in this standalone library.
