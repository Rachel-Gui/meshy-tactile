# Human-arm key frames

The combined upload contains nine front-facing 96-node scenes at 20 FPS. It is three-times slowed with smooth interpolation. Each listed key frame is the maximum total signal inside that scene's action phase.

| action | combined frame (0-based) | combined time | source frame | source local time | slowed action-local time | rotation rows |
|---|---:|---:|---:|---:|---:|---:|
| LMP005 | 291 | 14.55 s | 87 | 4.35 s | 13.05 s | +3 |
| LMP006 | 1539 | 76.95 s | 213 | 10.65 s | 31.95 s | -5 |
| LMP007 | 2187 | 109.35 s | 127 | 6.35 s | 19.05 s | +2 |
| V221-01 | 2760 | 138.00 s | 88 | 4.40 s | 13.20 s | +4 |
| V221-02 | 3273 | 163.65 s | 28 | 1.40 s | 4.20 s | +4 |
| V221-03 | 3966 | 198.30 s | 28 | 1.40 s | 4.20 s | +4 |
| TBL002 | 4851 | 242.55 s | 92 | 4.60 s | 13.80 s | -1 |
| TBL003 | 5553 | 277.65 s | 147 | 7.35 s | 22.05 s | +1 |
| TBL004 | 6327 | 316.35 s | 133 | 6.65 s | 19.95 s | +3 |

`combined time` is the time to seek in the all-nine-scenes CSV. `source local time` is the equivalent position before three-times slowing.
