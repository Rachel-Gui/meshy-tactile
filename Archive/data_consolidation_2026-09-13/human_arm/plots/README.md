# Arm 3D heatmap plots

Five 300-DPI PNGs generated from the existing measured 96-channel action exports and `web/public/assets/model.json`.

- Three per-action images show two opposite views of peak total signal.
- `arm_contact_comparison.png`: common-view comparison.
- `grasp_time_sequence.png`: four measured frames and summed-signal timeline.

Selection uses the strongest peak summed signal among complete, non-temporally-interpolated clips in each action class. Exact sources, frames and timestamps are in `selection.json`. These are representative high-response examples, not class averages.

The frontend channel mapping is preserved: reverse the eight exported sensor coordinates within each of 12 rows. Vertex signal uses the frontend maximum smoothstep influence with a 25 mm radius, gain 1 and threshold 0. Triangle colors average their vertex values. All plots share the 0–1 processed-signal scale (not calibrated force/pressure); spatial interpolation is visual only. The mesh is the current exported Arm geometry. Opposite views reveal contacts hidden on the far surface. No generated or simulated sensor data is used.

Regenerate from project root:

```sh
/Users/a0000/anaconda3/bin/python human_arm/plots/generate_heatmaps.py
```
