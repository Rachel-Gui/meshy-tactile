# Robot arm

`action_library/robot_arm_132node/` contains 3 current actions (132 channels, 11×12). The Mapping sheet defines node positions. Use Signal Reconstructed; Signal Recorded is zero. Front/back labels are provisional.

Open http://127.0.0.1:8001/?model=robot for the 132-node model and recorded actions.

`action_library/selected_actions.json` marks the selected representatives without duplicating clips. Historical crop versions and selection indexes remain in dataset `archive/` folders. The full action set is the default.

From the project root, run `python3 tools/viewers/view_all_heatmaps.py` to view all three categories.

## 32 mm Rhino / Grasshopper model

`../models/robot_arm/robot_arm_132_32mm.gh` and `.3dm`: 250 mm length, both end diameters 32 mm, ribbon width 4 mm. The definition derives native sliders and the Python3 component from `1.gh`; the degenerate chord projection is replaced by opposite half-turn surface helices. It has 132 unique interior intersections; end pairs are excluded. Node names and PCB ports follow the workbook Mapping. Circumferential mounting phase and front/back orientation remain uncalibrated. This is a geometric sensor surface, not a manufacturing-certified solid.

Change native GH sliders, then click Reload in the local Robot arm frontend to save/export the active definition. The initial standalone `.3dm` is a snapshot. `web/build_robot_arm_model.py` rebuilds the initial 250 × Ø32 design and `.3dm`; `web/export_robot_arm_model.py` exports edits. Both run in Rhino via rhinocode.

Paper 2D/3D figures are in `plots/paper/`, with SVG, 600-DPI PNG, captions and source provenance.

Both ends have 5 mm wide bands, controlled by the End Band Width (mm) Grasshopper slider.
