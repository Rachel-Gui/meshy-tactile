# Meshy Tactile

Interactive 3D tactile heatmaps for Human arm, Robot arm and Finger sensors.

Live dashboard: https://meshy-tactile.vercel.app

The current built-in library contains **9 Direct actions**: front touch, back touch and grab for each model. See [Current dataset](CURRENT_DATASET.md) for source paths, checksums and update instructions.

| Directory | Purpose |
|---|---|
| `human_arm/action_library/` | Current Human arm data: 96 nodes, 3 actions |
| `robot_arm/action_library/` | Current Robot arm data: 132 nodes, 3 actions |
| `finger/action_library/` | Current Finger data: 18 nodes, 3 actions |
| `web/` | Dashboard, local service and export tools; see [setup](web/README.md) |
| `models/` | Rhino, Grasshopper and CAD models |
| `models/hand/` | Reference-inspired hand with naturally curled fingers; OBJ and generator |
| `tools/viewers/` | Desktop data viewers and acquisition tools |
| `Archive/` | Historical data, figures, import copies and provenance records |
| `icra2026_tactile_sleeve/` | Research manuscript and figures |

Double-click `start_dashboard.command` to start the local dashboard at http://127.0.0.1:8001.
Run `python3 tools/viewers/view_all_heatmaps.py` for the desktop action viewer.

Finger includes an optional hand scene with the sleeve on the index finger. Camera capture supports Space-key photos, optional webcam video and timestamp-aligned sensor exports. Shared CSV uploads support preview links and owner-controlled deletion.

Current documentation and dashboard controls use English. Historical source material in Archive is preserved in its original language for provenance.
