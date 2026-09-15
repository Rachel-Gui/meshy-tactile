# Finger website upload and key frames

Validated against `meshy-tactile` commit `905b5ba58562f340f82624ec870ffdf9d8ae8bf8` (2026-09-15).

## Updated website logic

- Finger Sleeve mode has two independent uploads: Sleeve A and Sleeve B.
- Each upload must contain exactly `N001` through `N018`; a combined 36-node file is rejected.
- Accepted timing columns include `action_elapsed_s`; time must be finite and strictly increasing.
- Every node value must be present, finite, and within 0–1. The browser resamples to 20 FPS.
- Files must be smaller than 3 MB.
- Leave both website sleeve-angle controls at 0 degrees for these files; direction changes are already encoded in the data.

## Mapping applied

The website assigns N001–N006, N007–N012, and N013–N018 to the low, middle, and high axial crossing tiers. Within each tier, node columns map to 0°, 60°, 120°, 180°, 240°, and 300°. The source crossed-ribbon phase was therefore corrected by `+1, +1, +2` columns for the three tiers. Palm/front is centered on C3 (120°, nearest the default 135° camera-facing direction); back is centered on C6 (300°).

## Upload pairs

Upload the matching `_A_18node.csv` and `_B_18node.csv` files into Sleeve A and Sleeve B, then press Restart / Play both.

| sequence | Sleeve A | Sleeve B | frames | duration |
|---|---|---|---:|---:|
| all8 | `finger_all8_palm_front_A_18node.csv` | `finger_all8_palm_front_B_18node.csv` | 448 | 22.35 s |
| group1 | `finger_group1_palm_back_back_palm_A_18node.csv` | `finger_group1_palm_back_back_palm_B_18node.csv` | 222 | 11.05 s |
| group2 | `finger_group2_palm_back_back_palm_A_18node.csv` | `finger_group2_palm_back_back_palm_B_18node.csv` | 216 | 10.75 s |

## All eight, palm/front

The website key frame is identical for Sleeve A and B because the paired clips are peak-synchronized.

| position | orientation | Sleeve A action / source frame | Sleeve B action / source frame | website frame (0-based) | website frame (1-based) | time |
|---:|---|---|---|---:|---:|---:|
| 1 | palm | R1G-023 / 269 | R1G-024 / 279 | 25 | 26 | 1.25 |
| 2 | palm | R1G-024 / 279 | R1G-023 / 269 | 86 | 87 | 4.30 |
| 3 | palm | R1G-025 / 365 | R1G-026 / 388 | 148 | 149 | 7.40 |
| 4 | palm | R1G-026 / 388 | R1G-025 / 365 | 203 | 204 | 10.15 |
| 5 | palm | R1G-027 / 418 | R1G-020 / 229 | 257 | 258 | 12.85 |
| 6 | palm | R1G-020 / 229 | R1G-027 / 418 | 316 | 317 | 15.80 |
| 7 | palm | R1G-017 / 176 | R1G-018 / 190 | 375 | 376 | 18.75 |
| 8 | palm | R1G-018 / 190 | R1G-017 / 176 | 429 | 430 | 21.45 |

## Group 1: palm-back-back-palm

The website key frame is identical for Sleeve A and B because the paired clips are peak-synchronized.

| position | orientation | Sleeve A action / source frame | Sleeve B action / source frame | website frame (0-based) | website frame (1-based) | time |
|---:|---|---|---|---:|---:|---:|
| 1 | palm | R1G-023 / 269 | R1G-024 / 279 | 25 | 26 | 1.25 |
| 2 | back | R1G-024 / 279 | R1G-023 / 269 | 86 | 87 | 4.30 |
| 3 | back | R1G-025 / 365 | R1G-026 / 388 | 148 | 149 | 7.40 |
| 4 | palm | R1G-026 / 388 | R1G-025 / 365 | 203 | 204 | 10.15 |

## Group 2: palm-back-back-palm

The website key frame is identical for Sleeve A and B because the paired clips are peak-synchronized.

| position | orientation | Sleeve A action / source frame | Sleeve B action / source frame | website frame (0-based) | website frame (1-based) | time |
|---:|---|---|---|---:|---:|---:|
| 1 | palm | R1G-027 / 418 | R1G-020 / 229 | 25 | 26 | 1.25 |
| 2 | back | R1G-020 / 229 | R1G-027 / 418 | 84 | 85 | 4.20 |
| 3 | back | R1G-017 / 176 | R1G-018 / 190 | 143 | 144 | 7.15 |
| 4 | palm | R1G-018 / 190 | R1G-017 / 176 | 197 | 198 | 9.85 |

## Source references

- Commit: https://github.com/Rachel-Gui/meshy-tactile/commit/905b5ba58562f340f82624ec870ffdf9d8ae8bf8
- A/B uploader: https://github.com/Rachel-Gui/meshy-tactile/blob/main/web/src/finger-pair.js
- CSV parser: https://github.com/Rachel-Gui/meshy-tactile/blob/main/web/src/playback-csv.js
- Ring mapping: https://github.com/Rachel-Gui/meshy-tactile/blob/main/web/src/ring-action-mapping.js
