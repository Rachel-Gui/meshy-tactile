# Reference-inspired hand

Continuous closed hand surface reconstructed approximately from the user's reference image, not an exact reconstruction or anatomical scan. Units: mm. Index finger follows X and fits inside the existing 27 mm Finger sleeve without changing sensor coordinates. Five tapered digits, joint volumes, palm/thenar volume and a flat wrist cut. Frontend adds separate nail meshes.

`hand.obj` contains the continuous skin mesh and can be imported into Rhino or Blender. `build_hand.py` regenerates it and `web/public/assets/hand-model.json` using NumPy and scikit-image. JSON includes nail placement metadata. Frontend: `web/src/finger-hand-scene.js`.
