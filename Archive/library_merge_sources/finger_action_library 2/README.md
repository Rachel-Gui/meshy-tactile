# Tactile action heatmap library

Reviewed finger-sensor and robot-arm action data is collected here without
changing the original recordings or the earlier processed-result folders.

## Subfolders

- `30point_recordings_18node_sparse/`: actions extracted from older 30-point
  scans and mapped to the corrected 18-node sparse 6x6 McKibben topology.
  Regenerate with `ESP32 reader/tools/grip/process_finger_recordings_6x3.py`.
- `18point_6x6_sparse/`: 18-node sparse 6x6 action clips plus their index.
  Regenerate with
  `ESP32 reader/tools/grip/extract_18point_action_segments.py`.
- `96point_12x8/`: full 12x8-layout action clips plus their index.
  Regenerate with
  `ESP32 reader/tools/grip/extract_96point_action_segments.py`.
- `robot_arm_132node/`: provisional front/back and reviewed grasp clips on the
  11×12 robot-arm layout, with complete node mapping and reconstruction notes.
  Regenerate with
  `ESP32 reader/tools/grip/extract_robot_arm_action_segments.py`.

## Kept selection (2026-09-10)

The finger portion originally held 57 reviewed action clips (12 + 16 + 29). Most of
that was near-duplicate repeats of the same gesture within one recording
session, and several clips had a weak or unclear signal. Each dataset now
keeps only one clip per action type -- the clearest, highest-confidence
`front_touch`, `back_touch`, and `grasp` example. The new robot-arm dataset adds
three provisional/reviewed representatives, for **12 total current clips**:

| dataset    | front_touch | back_touch | grasp |
|------------|-------------|------------|-------|
| 30-point   | A002        | A001       | A003  |
| 18-point   | E005        | E008       | E012  |
| 96-point   | E015        | E022       | E009  |
| robot-arm 132-node | R002 | R001 | R003 |

Selection ranked confidence (high before medium) first, then peak signal
energy, then peak active-node count, with one manual override: 96-point
`back_touch` kept `E022` over the confidence-ranked `E008`, because `E022`'s
weaker confidence label reflects an unconfirmed front/back orientation call
from the original review, not a weaker signal -- it is visibly the stronger
clip. `E005` (18-point front_touch) does not fully settle back to baseline by
the end of its window; it was still the strongest front_touch example
available in that recording.

The other 48 clips were moved, not deleted, into a `segments_weak_signal_backup_20260910/`
folder (and matching `..._weak_signal_backup_20260910.xlsx` index) alongside
each dataset's `segments/`. The 30-point dataset has no per-action files, so
its 9 excluded actions live in a separate
`finger_actions_18node_6x6_sparse_weak_signal_backup_20260910.xlsx` workbook
with the same sheet layout as the main one. To restore any clip, move its file
back into `segments/` (or its Action Index row back into the main workbook for
30-point) -- the viewer picks up whatever is in `segments/` directly.

## Clip framing

Every clip runs baseline to baseline. Each one reaches back from the reviewed
contact core to a settled pre-contact lead-in and forward through the release,
so an action can be read as a whole instead of opening at peak signal. An edge
settles on the calmest frame within reach rather than on a fixed threshold,
because these recordings rest at whatever level their stuck nodes hold, not at
zero. A lead may reach back to the previous action's core and a release forward
to the next one's, so neighbouring clips can share the quiet stretch between
them.

A few clips still cannot open or close on the baseline, because the recording
never returns there inside the room available -- among the 9 kept clips, only
`E005` (18-point front_touch, see "Kept selection" below); among the 48 moved
to backup, `A006`/`A011` (30-point) and `E004`/`E006` (18-point) had the same
issue. In each case the reviewed cores are adjacent or a stuck node holds a
constant floor.

## One viewer for everything

Run from the PCB project root:

```bash
python3 "ESP32 reader/data/processed/finger_action_library/view_all_heatmaps.py"
```

Use the **Dataset** dropdown to select 30, 18, 96, or robot-arm 132-node data. Use the
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
kept only under `legacy_compressed_mapping/` and is not loaded by the viewer.
