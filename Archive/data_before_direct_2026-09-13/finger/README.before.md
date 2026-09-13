# Finger

`action_library/` contains all 28 current finger actions: 12 from 30-point recordings mapped to 18 nodes, and 16 sparse 18-node clips.

`recordings/` contains the original finger recordings.

`action_library/selected_actions.json` marks the selected representatives without duplicating clips. Historical crop versions and selection indexes remain in dataset `archive/` folders. The full action set is the default.

From the project root, run `python3 tools/viewers/view_all_heatmaps.py` to view all three categories.

Both ends have 3 mm wide bands, controlled by the End Band Width (mm) Grasshopper slider. Rhino snapshot: `models/tactile/finger_end_bands.3dm`.
