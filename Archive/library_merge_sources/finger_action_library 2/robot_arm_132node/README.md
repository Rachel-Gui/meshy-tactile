# Robot-arm 132-node reviewed actions

This folder is the shareable robot-arm action set extracted from
`tactile_132points_20260912_192911.xlsx`. The original recording was read only
and was not modified.

## Reviewed clips

| ID | Action | Source frames | Source time | Confidence | Interpretation |
|---|---|---:|---:|---|---|
| R001 | `back_touch` | 6–8 | 17.74–23.02 s | low | Display columns 7–12 dominate at frame 8. The following touch starts immediately, so this clip has no clean release tail. |
| R002 | `front_touch` | 9–13 | 25.66–36.23 s | low | Display columns 1–6 dominate at frames 9–10. Later frames contain a broad transition/ghost response before returning near baseline. |
| R003 | `grasp` | 14–18 | 38.87–49.43 s | high | Broad, balanced response across both sleeve halves, followed by decay toward baseline. |

`front_touch` and `back_touch` are provisional because one full 132-node scan
takes about 2.64 seconds and those two contacts are adjacent in the recording.
The convention used here is display columns 1–6 = front and columns 7–12 =
back. Confirm the physical mounting once; if the sleeve is reversed, swap only
the two action names. The heatmap/node mapping does not change.

## Workbook contents

Each file in `segments/` contains:

- `Raw Data`: measured voltage, unchanged from the source.
- `Baseline`: reconstructed as `Raw Data - Delta Recorded`.
- `Signal Reconstructed`: normalized pressure proxy from 0 to 1.
- `Pressure Drop V`: pressure-associated voltage drop after a 0.03 V floor.
- `Delta Recorded`: original signed recorder delta.
- `Signal Recorded`: original recorder output. It is all zero in this session.
- `Mapping`: exact node-to-heatmap and physical PCB-port mapping.
- `Metadata`: action label, confidence, source frames and limitations.

The reconstruction is:

```text
Pressure Drop V     = max(-Delta Recorded - 0.03 V, 0)
Signal Reconstructed = clip(Pressure Drop V / 0.20 V, 0, 1)
```

For analysis, use `Signal Reconstructed` rather than the all-zero
`Signal Recorded` sheet. Raw values are always retained, so a different signal
formula can be applied later.

## Ribbon and PCB mapping

Both logical ROW and COL terminals use the same 12 odd PCB MUX channels:

```text
Logical terminal: 1  2  3  4  5  6  7  8  9  10 11 12
PCB channel:      1  3  5  7  9  11 13 15 17 19 21 23
```

Circular ribbon order:

```text
COL: 1, 10, 12, 6, 2, 3, 7, 11, 5, 8, 9, 4
ROW: 6,  1,  4, 2, 9, 7,11, 10, 3,12, 5, 8
```

Ribbons at the same position are bottom pairs and are excluded from the sensing
area. Each COL crosses the following 11 ROW ribbons. This produces 132 nodes in
an 11-row × 12-column display:

| Display column | COL ribbon | Excluded bottom ROW | Display rows 1→11 (ROW ribbon) |
|---:|---:|---:|---|
| 1 | 1 | 6 | 1, 4, 2, 9, 7, 11, 10, 3, 12, 5, 8 |
| 2 | 10 | 1 | 4, 2, 9, 7, 11, 10, 3, 12, 5, 8, 6 |
| 3 | 12 | 4 | 2, 9, 7, 11, 10, 3, 12, 5, 8, 6, 1 |
| 4 | 6 | 2 | 9, 7, 11, 10, 3, 12, 5, 8, 6, 1, 4 |
| 5 | 2 | 9 | 7, 11, 10, 3, 12, 5, 8, 6, 1, 4, 2 |
| 6 | 3 | 7 | 11, 10, 3, 12, 5, 8, 6, 1, 4, 2, 9 |
| 7 | 7 | 11 | 10, 3, 12, 5, 8, 6, 1, 4, 2, 9, 7 |
| 8 | 11 | 10 | 3, 12, 5, 8, 6, 1, 4, 2, 9, 7, 11 |
| 9 | 5 | 3 | 12, 5, 8, 6, 1, 4, 2, 9, 7, 11, 10 |
| 10 | 8 | 12 | 5, 8, 6, 1, 4, 2, 9, 7, 11, 10, 3 |
| 11 | 9 | 5 | 8, 6, 1, 4, 2, 9, 7, 11, 10, 3, 12 |
| 12 | 4 | 8 | 6, 1, 4, 2, 9, 7, 11, 10, 3, 12, 5 |

The data columns are stored column-major: the first 11 values belong to display
column 1, the next 11 to display column 2, and so on. `Mapping` is the canonical
source and should be used instead of hard-coding this table.

## Restore a heatmap

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

path = "segments/R003_grasp_tactile_132points_20260912_192911_f0014-f0018.xlsx"
data = pd.read_excel(path, sheet_name="Signal Reconstructed")
mapping = pd.read_excel(path, sheet_name="Mapping")

frame = 1
heatmap = np.full((11, 12), np.nan)
for node in mapping.itertuples(index=False):
    heatmap[node.display_row - 1, node.display_column - 1] = data.loc[frame, node.node]

plt.imshow(heatmap, vmin=0, vmax=1, cmap="turbo", aspect="auto")
plt.xticks(range(12), [1, 10, 12, 6, 2, 3, 7, 11, 5, 8, 9, 4])
plt.yticks(range(11), range(1, 12))
plt.xlabel("COL ribbon")
plt.ylabel("Position after excluded bottom pair")
plt.colorbar(label="Signal Reconstructed")
plt.show()
```

From the PCB project root, the bundled viewer can display all reviewed datasets:

```bash
python3 "ESP32 reader/data/processed/finger_action_library/view_all_heatmaps.py"
```

Select **Robot arm 132-node → 11×12** from the Dataset menu.

## Regeneration

```bash
python3 "ESP32 reader/tools/grip/extract_robot_arm_action_segments.py"
```

This regenerates the three clips and `action_index.xlsx` from the unchanged
source recording.
