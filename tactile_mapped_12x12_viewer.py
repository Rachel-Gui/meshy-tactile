#!/usr/bin/env python3
"""12x12 tactile viewer using the requested logical-to-physical pin map."""

import sys

from tactile_full_scan_viewer import main


PHYSICAL_PIN_MAP = "1,3,5,7,2,4,6,8,10,12,14,16"


if __name__ == "__main__":
    sys.argv.extend(
        (
            "--pin-map",
            PHYSICAL_PIN_MAP,
            "--interval",
            str(0.5 / (12 * 12)),
            "--tabbed-secondary",
            "--contact-drop-fraction",
            "0.15",
            "--sensitivity",
            "1.0",
        )
    )
    raise SystemExit(main())
