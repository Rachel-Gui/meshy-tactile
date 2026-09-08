# Anatomical arm source

`human-base.obj` is the MakeHuman core base mesh, obtained from:
https://github.com/makehumancommunity/makehuman/blob/master/makehuman/data/3dobjs/base.obj

Retrieved 2026-09-06. The OBJ explicitly states that it was released under
CC0 in September 2020. The upstream license is preserved in
`LICENSE-makehuman.md`; official explanation:
https://static.makehumancommunity.org/about/license.html

`../generate-arm-mannequin.py` extracts the left arm, closes the upper-arm
cut, poses the elbow and wrist, adjusts finger spread/proportions, adds subtle
dorsal relief, subdivides the surface and fits the forearm inside the existing
GH sensor. It exports `../public/assets/arm-mannequin.glb` in millimetres.
This replaces the earlier capsule/voxel mannequin. This is a posed display
mesh, not a scan of the user's hand or an exact reconstruction of the reference.

Joint refinement: original finger lengths/webs are preserved, with mild
PIP/DIP-pivot flexion and smooth spatial influence. Pronation is distributed
along the forearm instead of concentrating a large twist at the wrist.

Generation: Python with numpy. Preview: `../render-arm-preview.py` also needs
matplotlib. The preview is an offline geometry render, not a browser screenshot.
