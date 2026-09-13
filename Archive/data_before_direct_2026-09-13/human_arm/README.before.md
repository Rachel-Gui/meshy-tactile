# Human arm

`action_library/96point_12x8/` contains all 29 current human-arm actions and their full index (96 channels, 12×8).

`recordings/` contains the original 96-point recordings; `plots/` contains the 3D heatmap images and generation script.

`action_library/selected_actions.json` marks the selected representatives without duplicating clips. Historical crop versions and selection indexes remain in dataset `archive/` folders. The full action set is the default.

From the project root, run `python3 tools/viewers/view_all_heatmaps.py` to view all three categories.

## Human arm model

The current `models/tactile/1.gh` and `models/tactile/human_arm.3dm` have no end bands. The original 96-node woven sensor layout is retained. Earlier band variants are archived under `Archive/model_backups/`.
