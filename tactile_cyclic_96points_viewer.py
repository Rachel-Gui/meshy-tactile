#!/usr/bin/env python3
"""Display the 96 real intersections in the 12x12 cyclic tactile layout."""

import sys

from tactile_full_scan_viewer import main


PHYSICAL_PIN_MAP = "1,3,5,7,2,4,6,8,10,12,14,16"
CYCLIC_OFFSETS = "1,2,3,4,5,6,7,8"
POINT_COUNT = 12 * 8


if __name__ == "__main__":
    sys.argv.extend(
        (
            "--pin-map",
            PHYSICAL_PIN_MAP,
            "--cyclic-offsets",
            CYCLIC_OFFSETS,
            "--compact-cyclic",
            "--interval",
            str(0.5 / POINT_COUNT),
            "--tabbed-secondary",
            "--contact-drop-fraction",
            "0.15",
            "--sensitivity",
            "1.0",
        )
    )
    raise SystemExit(main())
