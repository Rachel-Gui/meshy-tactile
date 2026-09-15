# Arm 96-node frontend upload — FINAL

This flat folder contains nine individual final CSV files plus one combined CSV
for the meshy-tactile frontend. Upload one `*_UPLOAD.csv` file at a time.

`00_ALL_9_SCENES_FRONT_FACING_3X_SLOW_SMOOTH_MAPPING_FIXED_UPLOAD.csv` combines
all nine scenes at 20 FPS. It preserves every original keyframe and inserts two
cubic-smooth transition frames between neighboring frames, so playback is exactly
three times slower. Each complete signal field is rotated by an integer number
of circumference rows so its energy is centered on the website's default camera
front (about 135 degrees). The quiet scene separators are slowed as well.

- `01`-`03`: middle-arm palm grab actions LMP005-LMP007.
- `04`-`06`: three-location finger press actions V221-01 to V221-03.
- `07`-`09`: polished table-contact actions TBL002-TBL004; continuous interior
  contact core with softly incomplete measured edges.
- Format: normalized Signal Combined, 0 to 1.
- Node order: frontend 12 rows x 8 axial channels, N001...N096.
- Circumference order: C1,C12,C11,...,C2, matching the website 3D weave.
- The frontend performs its own eight-channel model-direction reversal; do not
  transpose, remap, or mirror these files again.
