#!/usr/bin/env python3
"""Display the tactile sensor stream from the user-supplied downloaded_tactilesensor_a2.ino."""

from __future__ import annotations

import argparse
from collections import deque
import csv
from datetime import datetime
from pathlib import Path
import queue
import re
import sys
import threading
import time

import matplotlib

matplotlib.use("TkAgg")

import matplotlib.animation as animation
import matplotlib.pyplot as plt
from matplotlib.colors import PowerNorm
from matplotlib.patches import Rectangle
from matplotlib.widgets import Button, Slider
import numpy as np

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    raise SystemExit("pyserial is required: python3 -m pip install pyserial")


BAUD_RATE = 1_000_000
RAW_ROWS = 32
RAW_COLS = 32
DEFAULT_ACTIVE_PINS = (1, 3, 5, 7, 9, 11)
SAMPLE_INTERVAL_S = 0.05
FRAME_TIMEOUT_S = 3.0
VREF = 3.3
RAW_DISPLAY_MIN_V = 0.8
RAW_DISPLAY_MAX_V = 1.7
SHORT_AS_OPEN_THRESHOLD_V = 0.2
SHORT_QUALIFY_TIME_S = 2.0

SMOOTHING_ALPHA = 0.35
BASELINE_FLOOR_V = 0.10
ACTIVITY_FULL_SCALE_FRACTION = 0.50
FULL_PRESS_V = 0.80
SIGNAL_RELEASE_V = 1.70
SIGNAL_VISIBLE_V = 1.55
RAW_DISPLAY_GAMMA = 2.2
NOISE_SIGMA_MULTIPLIER = 6.0
ROLLING_BASELINE_WINDOW_S = 5.0
ROLLING_BASELINE_ROUND_MULTIPLIER = 2.25
ROLLING_BASELINE_MIN_AGE_S = 2.0
ROLLING_BASELINE_MIN_SAMPLES = 2
SIGNIFICANT_CHANGE_V = 0.12
SIGNIFICANT_CHANGE_FRACTION = 0.08
DEFAULT_SENSITIVITY = 1.0
MAX_EVENTS_PER_GUI_UPDATE = 64

# Raw voltage and Signal share the same high-contrast palette. Raw voltage is
# reversed because low voltage means stronger pressure on this hardware.
RAW_VOLTAGE_CMAP = "turbo_r"
SIGNAL_CMAP = "turbo"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Serial port; auto-detected when omitted")
    parser.add_argument("--baud", type=int, default=BAUD_RATE)
    parser.add_argument("--rows", type=int, default=RAW_ROWS)
    parser.add_argument("--cols", type=int, default=RAW_COLS)
    parser.add_argument(
        "--interval",
        type=float,
        default=SAMPLE_INTERVAL_S,
        help="requested full-frame interval in seconds (adjustable in the GUI)",
    )
    parser.add_argument(
        "--pins",
        default=",".join(map(str, DEFAULT_ACTIVE_PINS)),
        help="comma-separated 1-based row/column pins to display; use 'all' for full scan",
    )
    parser.add_argument(
        "--points",
        help="explicit points such as R7C5,R1C7; scans only these intersections",
    )
    parser.add_argument(
        "--logical-points",
        help=(
            "logical 1..6 points such as R6C4,R1C5; maps each axis through "
            "physical pins 1,3,5,7,9,11"
        ),
    )
    parser.add_argument(
        "--unwrap-three-rows",
        action="store_true",
        help="unwrap cyclic logical R/C points into a three-row by six-column sensor",
    )
    parser.add_argument(
        "--dual-units",
        action="store_true",
        help=(
            "scan two restored 3x6 units: odd physical pins for unit 1 and "
            "even physical pins for unit 2"
        ),
    )
    parser.add_argument(
        "--pin-map",
        help=(
            "comma-separated physical pins for a full logical square grid; "
            "example: 1,3,5,7,2,4,6,8,10,12,14,16"
        ),
    )
    parser.add_argument(
        "--cyclic-offsets",
        help=(
            "with --pin-map, scan only these cyclic logical column offsets; "
            "example 1,2,3,4,5,6,7,8 gives R1C2 through R1C9"
        ),
    )
    parser.add_argument(
        "--compact-cyclic",
        action="store_true",
        help="pack cyclic points into contiguous rows without empty grid cells",
    )
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=DEFAULT_SENSITIVITY,
        help="detection sensitivity from 0.25 to 5.0; higher detects smaller changes",
    )
    parser.add_argument(
        "--contact-drop-fraction",
        type=float,
        help=(
            "require this fractional voltage drop from each sensor's own baseline; "
            "for example 0.15 requires a 15%% drop"
        ),
    )
    parser.add_argument(
        "--record-dir",
        default="tactile_data",
        help="directory used by the GUI CSV recorder",
    )
    parser.add_argument(
        "--show-raw-delta",
        action="store_true",
        help="show an additional ungated voltage-change heatmap",
    )
    parser.add_argument(
        "--tabbed-secondary",
        action="store_true",
        help="show raw delta and processed signal as selectable views on one axis",
    )
    parser.add_argument(
        "--legacy-visible-signal",
        action="store_true",
        help="restore the earlier three-panel display and unfiltered raw voltage behavior",
    )
    parser.add_argument(
        "--mode",
        choices=("point", "batch96", "legacy"),
        default="point",
        help="point reads one node; batch96 reads all 96 cyclic nodes per command",
    )
    return parser.parse_args()


def find_port(requested: str | None) -> str:
    if requested:
        return requested
    devices = [item.device for item in list_ports.comports()]
    candidates = [
        item
        for item in devices
        if "usbserial" in item.lower() or "usbmodem" in item.lower()
    ]
    candidates.sort(key=lambda item: (not item.startswith("/dev/cu."), item))
    if candidates:
        return candidates[0]
    available = "\n".join(f"  {item}" for item in devices) or "  (none)"
    raise SystemExit(f"ESP32 serial port was not found. Available ports:\n{available}")


def read_exact(ser: serial.Serial, size: int, timeout_s: float) -> bytes:
    result = bytearray()
    deadline = time.monotonic() + timeout_s
    while len(result) < size:
        chunk = ser.read(size - len(result))
        if chunk:
            result.extend(chunk)
        elif time.monotonic() >= deadline:
            raise TimeoutError(f"received {len(result)} of {size} bytes")
    return bytes(result)


def request_frame(ser: serial.Serial, rows: int, cols: int, sequence: int):
    ser.write(b"w")
    ser.flush()
    payload = read_exact(ser, rows * cols, FRAME_TIMEOUT_S)
    delimiter = read_exact(ser, 1, FRAME_TIMEOUT_S)
    if delimiter != b"\n":
        raise RuntimeError(f"bad legacy frame delimiter: {delimiter!r}")
    return np.frombuffer(payload, dtype=np.uint8).copy(), sequence + 1


def request_point(ser: serial.Serial, row: int, column: int) -> int:
    ser.write(bytes((ord("p"), row, column)))
    ser.flush()
    window = bytearray()
    deadline = time.monotonic() + FRAME_TIMEOUT_S
    while time.monotonic() < deadline:
        value = ser.read(1)
        if not value:
            continue
        window.extend(value)
        if len(window) > 2:
            del window[0]
        if bytes(window) == b"\xA5\x5A":
            break
    else:
        raise TimeoutError("point response header A5 5A not received")

    rest = read_exact(ser, 4, FRAME_TIMEOUT_S)
    response_row, response_col, sample, checksum = rest
    expected_checksum = 0xA5 ^ 0x5A ^ response_row ^ response_col ^ sample
    if checksum != expected_checksum:
        raise RuntimeError("point response checksum error")
    if (response_row, response_col) != (row, column):
        raise RuntimeError(
            f"point response mismatch: requested R{row + 1}C{column + 1}, "
            f"received R{response_row + 1}C{response_col + 1}"
        )
    return sample


def request_batch96(ser: serial.Serial, expected_count: int):
    ser.write(b"b")
    ser.flush()
    window = bytearray()
    deadline = time.monotonic() + FRAME_TIMEOUT_S
    while time.monotonic() < deadline:
        value = ser.read(1)
        if not value:
            continue
        window.extend(value)
        if len(window) > 2:
            del window[0]
        if bytes(window) == b"\xA6\x5B":
            break
    else:
        raise TimeoutError("batch response header A6 5B not received")
    count, sequence = read_exact(ser, 2, FRAME_TIMEOUT_S)
    if count != expected_count:
        raise RuntimeError(
            f"batch point count mismatch: received {count}, expected {expected_count}"
        )
    payload = read_exact(ser, count, FRAME_TIMEOUT_S)
    received_checksum = read_exact(ser, 1, FRAME_TIMEOUT_S)[0]
    checksum = 0xA6 ^ 0x5B ^ count ^ sequence
    for value in payload:
        checksum ^= value
    if received_checksum != checksum:
        raise RuntimeError("batch response checksum error")
    return np.frombuffer(payload, dtype=np.uint8).copy(), sequence


class FrameReader(threading.Thread):
    def __init__(
        self,
        ser: serial.Serial,
        rows: int,
        cols: int,
        mode: str,
        interval_s: float,
        points: list[tuple[int, int]],
        output: queue.Queue,
    ):
        super().__init__(daemon=True)
        self.ser = ser
        self.rows = rows
        self.cols = cols
        self.mode = mode
        self.interval_s = interval_s
        self.points = points
        self.output = output
        self.stop_event = threading.Event()

    def run(self):
        next_request = time.monotonic()
        sequence = -1
        point_index = 0
        point_frame = np.zeros((self.rows, self.cols), dtype=np.float32)
        while not self.stop_event.is_set():
            try:
                wait_s = next_request - time.monotonic()
                if wait_s > 0 and self.stop_event.wait(wait_s):
                    return
                next_request = max(
                    next_request + self.interval_s,
                    time.monotonic(),
                )
                if self.mode == "point":
                    row, column = self.points[point_index]
                    sample = request_point(self.ser, row, column)
                    point_frame[row, column] = sample * (VREF / 255.0)
                    round_complete = point_index == len(self.points) - 1
                    if round_complete:
                        sequence += 1
                    self.output.put(
                        (
                            "frame",
                            time.monotonic(),
                            point_frame.copy(),
                            sequence,
                            point_index,
                            round_complete,
                        )
                    )
                    point_index = (point_index + 1) % len(self.points)
                elif self.mode == "batch96":
                    raw, sequence = request_batch96(self.ser, len(self.points))
                    point_frame.fill(0.0)
                    for point_value, (row, column) in zip(raw, self.points):
                        point_frame[row, column] = point_value * (VREF / 255.0)
                    self.output.put(
                        (
                            "frame",
                            time.monotonic(),
                            point_frame.copy(),
                            sequence,
                            -1,
                            True,
                        )
                    )
                else:
                    raw, sequence = request_frame(
                        self.ser, self.rows, self.cols, sequence
                    )
                    frame_v = raw.reshape(self.rows, self.cols).astype(np.float32) * (
                        VREF / 255.0
                    )
                    self.output.put(
                        ("frame", time.monotonic(), frame_v, sequence, -1, True)
                    )
            except (TimeoutError, RuntimeError, serial.SerialException, OSError) as exc:
                if not self.stop_event.is_set():
                    self.output.put(("error", str(exc)))
                return

    def stop(self):
        self.stop_event.set()


def rolling_activity(
    value: float,
    history: deque,
    sensitivity: float,
    contact_drop_fraction: float | None = None,
) -> tuple[float, float, float, bool]:
    """Compare one new sample with only that sensor's preceding history."""
    if len(history) < ROLLING_BASELINE_MIN_SAMPLES:
        return 0.0, value, 0.0, False

    values = np.fromiter((sample for _, sample in history), dtype=np.float64)
    baseline = float(np.median(values))
    mad = float(np.median(np.abs(values - baseline)))
    robust_sigma = 1.4826 * mad
    scale = max(abs(baseline), BASELINE_FLOOR_V)
    base_threshold_v = max(
        SIGNIFICANT_CHANGE_V,
        SIGNIFICANT_CHANGE_FRACTION * scale,
        NOISE_SIGMA_MULTIPLIER * robust_sigma,
    )
    threshold_v = base_threshold_v / sensitivity
    pressure_drop_v = baseline - value
    if contact_drop_fraction is not None:
        # Conservative mode for resistive sensors: compare each point only
        # against its own baseline. A 15% setting on a 1.8 V baseline means
        # the signal remains off until the voltage falls below about 1.53 V.
        onset_fraction = contact_drop_fraction / sensitivity
        # A noisy/floating node must also clear its own measured noise floor.
        # This keeps a quiet 15% touch detectable while preventing ordinary
        # idle variation from being promoted to a sensor signal.
        threshold_v = max(onset_fraction * scale, base_threshold_v / sensitivity)
        full_drop_v = max(0.50 * scale, threshold_v + 0.10 * scale)
        activity = (
            float(
                np.clip(
                    (pressure_drop_v - threshold_v)
                    / (full_drop_v - threshold_v),
                    0.0,
                    1.0,
                )
            )
            if pressure_drop_v > threshold_v
            else 0.0
        )
        return activity, baseline, threshold_v, True

    # Pressure lowers voltage. Use an absolute voltage scale so a sustained
    # press remains visible instead of being absorbed by the rolling baseline.
    # The adaptive threshold still detects lighter transient touches, while
    # values around 1.5 V and below are always shown as definite pressure.
    absolute_strength = float(
        np.clip(
            (SIGNAL_RELEASE_V - value) / (SIGNAL_RELEASE_V - FULL_PRESS_V),
            0.0,
            1.0,
        )
    )
    if value <= SIGNAL_VISIBLE_V or pressure_drop_v > threshold_v:
        activity = absolute_strength
    else:
        activity = 0.0
    return activity, baseline, threshold_v, True


def main() -> int:
    args = parse_args()
    if args.rows <= 0 or args.cols <= 0:
        raise SystemExit("rows and cols must be positive")
    if not 0.001 <= args.interval <= 2.0:
        raise SystemExit("--interval must be between 0.001 and 2.0 seconds")
    if not 0.25 <= args.sensitivity <= 5.0:
        raise SystemExit("--sensitivity must be between 0.25 and 5.0")
    if (
        args.contact_drop_fraction is not None
        and not 0.01 <= args.contact_drop_fraction <= 0.80
    ):
        raise SystemExit("--contact-drop-fraction must be between 0.01 and 0.80")
    if args.unwrap_three_rows and not args.logical_points:
        raise SystemExit("--unwrap-three-rows requires --logical-points")
    if args.unwrap_three_rows and args.mode != "point":
        raise SystemExit("--unwrap-three-rows requires --mode point")
    if args.dual_units and args.mode != "point":
        raise SystemExit("--dual-units requires --mode point")
    if args.dual_units and (args.points or args.logical_points):
        raise SystemExit("--dual-units cannot be combined with an explicit point list")
    if args.pin_map and (args.dual_units or args.points or args.logical_points):
        raise SystemExit("--pin-map cannot be combined with other point mappings")
    if args.cyclic_offsets and not args.pin_map:
        raise SystemExit("--cyclic-offsets requires --pin-map")
    if args.compact_cyclic and not args.cyclic_offsets:
        raise SystemExit("--compact-cyclic requires --cyclic-offsets")

    if args.points and args.logical_points:
        raise SystemExit("use only one of --points and --logical-points")

    explicit_points = None
    point_source_labels = None
    physical_pin_map = None
    logical_point_mode = bool(args.logical_points)
    point_specification = args.logical_points or args.points
    if args.pin_map:
        try:
            physical_pin_map = tuple(
                int(item.strip()) for item in args.pin_map.split(",")
            )
        except ValueError as exc:
            raise SystemExit("--pin-map must contain comma-separated integers") from exc
        if not physical_pin_map or len(set(physical_pin_map)) != len(physical_pin_map):
            raise SystemExit("--pin-map must contain unique physical pins")
        if any(pin < 1 or pin > min(args.rows, args.cols) for pin in physical_pin_map):
            raise SystemExit("--pin-map contains a pin outside the raw matrix")
        logical_size = len(physical_pin_map)
        displayed_rows = list(range(1, logical_size + 1))
        displayed_cols = list(range(1, logical_size + 1))
        displayed_row_labels = displayed_rows
        if args.cyclic_offsets:
            try:
                cyclic_offsets = tuple(
                    int(item.strip()) for item in args.cyclic_offsets.split(",")
                )
            except ValueError as exc:
                raise SystemExit(
                    "--cyclic-offsets must contain comma-separated integers"
                ) from exc
            if (
                not cyclic_offsets
                or len(set(cyclic_offsets)) != len(cyclic_offsets)
                or any(offset < 0 or offset >= logical_size for offset in cyclic_offsets)
            ):
                raise SystemExit(
                    "--cyclic-offsets must be unique values from 0 to grid-size-1"
                )
            explicit_points = [
                (row, ((row - 1 + offset) % logical_size) + 1)
                for row in displayed_rows
                for offset in cyclic_offsets
            ]
            if args.compact_cyclic:
                displayed_cols = list(range(1, len(cyclic_offsets) + 1))
        else:
            explicit_points = [
                (row, col)
                for row in displayed_rows
                for col in displayed_cols
            ]
        scan_points = [
            (physical_pin_map[row - 1] - 1, physical_pin_map[col - 1] - 1)
            for row, col in explicit_points
        ]
        point_display_positions = (
            [
                (point_index // len(cyclic_offsets), point_index % len(cyclic_offsets))
                for point_index in range(len(explicit_points))
            ]
            if args.compact_cyclic
            else [(row - 1, col - 1) for row, col in explicit_points]
        )
        point_source_labels = [
            (
                f"R{row}C{col}"
                if args.compact_cyclic
                else (
                    f"R{physical_pin_map[row - 1]}"
                    f"C{physical_pin_map[col - 1]}"
                )
            )
            for row, col in explicit_points
        ]
        row_indices = np.array([], dtype=int)
        col_indices = np.array([], dtype=int)
        point_specification = "pin-map"
    elif args.dual_units:
        logical_pattern = [
            (logical_row, ((logical_row + offset - 1) % 6) + 1)
            for logical_row in range(1, 7)
            for offset in (5, 4, 3)
        ]
        explicit_points = []
        scan_points = []
        point_display_positions = []
        point_source_labels = []
        unit_pin_sets = ((1, 3, 5, 7, 9, 11), (2, 4, 6, 8, 10, 12))
        for unit_index, physical_pins in enumerate(unit_pin_sets, start=1):
            for logical_row, logical_col in logical_pattern:
                physical_row = physical_pins[logical_row - 1]
                physical_col = physical_pins[logical_col - 1]
                explicit_points.append((logical_row, logical_col))
                scan_points.append((physical_row - 1, physical_col - 1))
                cyclic_offset = (logical_col - logical_row) % 6
                point_display_positions.append(
                    ((unit_index - 1) * 3 + 5 - cyclic_offset, logical_row - 1)
                )
                point_source_labels.append(f"R{logical_row}C{logical_col}")
        displayed_rows = list(range(1, 7))
        displayed_cols = list(range(1, 7))
        displayed_row_labels = ("U1-1", "U1-2", "U1-3", "U2-1", "U2-2", "U2-3")
        row_indices = np.array([], dtype=int)
        col_indices = np.array([], dtype=int)
        point_specification = "dual-units"
    elif point_specification:
        explicit_points = []
        for item in point_specification.split(","):
            match = re.fullmatch(r"\s*[Rr](\d+)[Cc](\d+)\s*", item)
            if not match:
                raise SystemExit("point list must look like R7C5,R1C7")
            row, col = map(int, match.groups())
            point_limit_row = len(DEFAULT_ACTIVE_PINS) if logical_point_mode else args.rows
            point_limit_col = len(DEFAULT_ACTIVE_PINS) if logical_point_mode else args.cols
            if row < 1 or row > point_limit_row or col < 1 or col > point_limit_col:
                raise SystemExit(f"point R{row}C{col} is outside the raw matrix")
            if (row, col) in explicit_points:
                raise SystemExit(f"duplicate point R{row}C{col}")
            explicit_points.append((row, col))
        if not explicit_points:
            raise SystemExit("--points cannot be empty")
        if args.unwrap_three_rows:
            displayed_rows = [1, 2, 3]
            displayed_cols = list(range(1, len(DEFAULT_ACTIVE_PINS) + 1))
        elif logical_point_mode:
            displayed_rows = sorted({row for row, _ in explicit_points})
            displayed_cols = sorted({col for _, col in explicit_points})
        else:
            displayed_rows = list(dict.fromkeys(row for row, _ in explicit_points))
            displayed_cols = list(dict.fromkeys(col for _, col in explicit_points))
    elif args.pins.strip().lower() == "all":
        displayed_rows = list(range(1, args.rows + 1))
        displayed_cols = list(range(1, args.cols + 1))
    else:
        try:
            displayed_rows = [int(item.strip()) for item in args.pins.split(",")]
        except ValueError as exc:
            raise SystemExit("--pins must be comma-separated integers or 'all'") from exc
        if not displayed_rows or len(set(displayed_rows)) != len(displayed_rows):
            raise SystemExit("--pins must contain unique pin numbers")
        if any(pin < 1 or pin > min(args.rows, args.cols) for pin in displayed_rows):
            raise SystemExit("--pins contains a pin outside the raw matrix")
        displayed_cols = displayed_rows.copy()
    if physical_pin_map is not None:
        pass
    elif args.dual_units:
        pass
    elif args.unwrap_three_rows:
        row_indices = np.array([], dtype=int)
        col_indices = np.array([], dtype=int)
    elif logical_point_mode:
        row_indices = np.array(
            [DEFAULT_ACTIVE_PINS[row - 1] - 1 for row in displayed_rows],
            dtype=int,
        )
        col_indices = np.array(
            [DEFAULT_ACTIVE_PINS[col - 1] - 1 for col in displayed_cols],
            dtype=int,
        )
    else:
        row_indices = np.array(displayed_rows, dtype=int) - 1
        col_indices = np.array(displayed_cols, dtype=int) - 1
    if explicit_points is None:
        explicit_points = [
            (row, column)
            for row in displayed_rows
            for column in displayed_cols
        ]
    if physical_pin_map is not None:
        pass
    elif args.dual_units:
        pass
    elif logical_point_mode:
        scan_points = [
            (DEFAULT_ACTIVE_PINS[row - 1] - 1, DEFAULT_ACTIVE_PINS[column - 1] - 1)
            for row, column in explicit_points
        ]
    else:
        scan_points = [(row - 1, column - 1) for row, column in explicit_points]

    port = find_port(args.port)
    print(
        f"Opening {port} @ {args.baud:,}, raw {args.rows}x{args.cols}, "
        f"showing pins={displayed_rows}, protocol={args.mode}, "
        f"requested interval={args.interval:.2f} s...",
        flush=True,
    )
    try:
        ser = serial.Serial(port, args.baud, timeout=0.05)
    except serial.SerialException as exc:
        raise SystemExit(f"Serial error: {exc}") from exc

    time.sleep(2.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    frame_queue: queue.Queue = queue.Queue(maxsize=16)
    reader = FrameReader(
        ser,
        args.rows,
        args.cols,
        args.mode,
        args.interval,
        scan_points,
        frame_queue,
    )

    shape = ((6, 6) if args.dual_units else (len(displayed_rows), len(displayed_cols)))
    if not args.dual_units and physical_pin_map is None:
        displayed_row_labels = displayed_rows
    display_row_lookup = {pin: index for index, pin in enumerate(displayed_rows)}
    display_col_lookup = {pin: index for index, pin in enumerate(displayed_cols)}
    if physical_pin_map is not None:
        pass
    elif args.dual_units:
        pass
    elif args.unwrap_three_rows:
        point_display_positions = []
        for logical_row, logical_col in explicit_points:
            cyclic_offset = (logical_col - logical_row) % len(DEFAULT_ACTIVE_PINS)
            if cyclic_offset not in (3, 4, 5):
                raise SystemExit(
                    f"R{logical_row}C{logical_col} does not belong to the expected "
                    "three-row cyclic sensor pattern"
                )
            # Sensor rows run from the largest cyclic offset at the top to the
            # smallest at the bottom: e.g. R1C6, R1C5, R1C4.
            point_display_positions.append((5 - cyclic_offset, logical_row - 1))
    else:
        point_display_positions = [
            (display_row_lookup[row], display_col_lookup[col])
            for row, col in explicit_points
        ]
    scan_mask = np.zeros(shape, dtype=bool)
    source_node_labels = np.full(shape, "", dtype=object)
    point_index_lookup = np.full(shape, -1, dtype=int)
    if point_source_labels is None:
        point_source_labels = [f"R{point[0]}C{point[1]}" for point in explicit_points]
    for point_index, (point_label, (display_row, display_col)) in enumerate(zip(
        point_source_labels, point_display_positions
    )
    ):
        scan_mask[display_row, display_col] = True
        source_node_labels[display_row, display_col] = point_label
        point_index_lookup[display_row, display_col] = point_index
    active_sensor_count = int(np.count_nonzero(scan_mask))
    current = np.zeros(shape, dtype=np.float64)
    smoothed = None
    baseline = np.zeros(shape, dtype=np.float64)
    threshold_v = np.zeros(shape, dtype=np.float64)
    raw_delta_v = np.zeros(shape, dtype=np.float64)
    activity = np.zeros(shape, dtype=np.float64)
    baseline_ready = np.zeros(shape, dtype=bool)
    open_circuit = np.zeros(shape, dtype=bool)
    low_voltage_since = np.full(shape, np.nan, dtype=np.float64)
    histories = [
        [deque() for _ in range(shape[1])]
        for _ in range(shape[0])
    ]
    frames = 0
    sequence = -1
    active_point_index = -1
    consecutive_zero_frames = 0
    disconnected = False
    error_message = ""

    if args.tabbed_secondary:
        figure_size = (18, 9) if physical_pin_map is not None else (15, 7.2)
        fig, (ax_raw, ax_activity) = plt.subplots(1, 2, figsize=figure_size)
        ax_delta = None
        display_axes = (ax_raw, ax_activity)
    elif args.show_raw_delta:
        fig, (ax_raw, ax_delta, ax_activity) = plt.subplots(
            1, 3, figsize=(19, 7.2)
        )
        display_axes = (ax_raw, ax_delta, ax_activity)
    else:
        fig, (ax_raw, ax_activity) = plt.subplots(1, 2, figsize=(16, 7.2))
        ax_delta = None
        display_axes = (ax_raw, ax_activity)
    layout_label = (
        f"{active_sensor_count} explicit points"
        if point_specification
        else f"{shape[0]}x{shape[1]}"
    )
    fig.canvas.manager.set_window_title(
        f"Tactile Selected Pins — {layout_label} — {args.mode}"
    )

    raw_image = ax_raw.imshow(
        np.where(scan_mask, current, np.nan),
        cmap=RAW_VOLTAGE_CMAP,
        norm=PowerNorm(
            gamma=RAW_DISPLAY_GAMMA,
            vmin=RAW_DISPLAY_MIN_V,
            vmax=RAW_DISPLAY_MAX_V,
            clip=True,
        ),
        interpolation="nearest",
        aspect="auto",
    )
    activity_image = ax_activity.imshow(
        np.where(scan_mask, current, np.nan),
        cmap=SIGNAL_CMAP,
        vmin=0.0,
        vmax=1.0,
        interpolation="nearest",
        aspect="auto",
    )
    delta_image = None
    if ax_delta is not None:
        delta_image = ax_delta.imshow(
            np.where(scan_mask, raw_delta_v, np.nan),
            cmap="coolwarm",
            vmin=-0.25,
            vmax=0.25,
            interpolation="nearest",
            aspect="auto",
        )
    fig.colorbar(
        raw_image,
        ax=ax_raw,
        fraction=0.046,
        pad=0.04,
        label="Voltage (0.8–1.7 V)",
    )
    activity_colorbar = fig.colorbar(
        activity_image,
        ax=ax_activity,
        fraction=0.046,
        pad=0.04,
        label="Signal",
    )
    if delta_image is not None:
        fig.colorbar(
            delta_image,
            ax=ax_delta,
            fraction=0.046,
            pad=0.04,
            label="Ungated ΔV (V)",
        )

    x_ticks = np.arange(shape[1])
    y_ticks = np.arange(shape[0])
    for ax in display_axes:
        ax.set_xticks(x_ticks, labels=displayed_cols)
        ax.set_yticks(y_ticks, labels=displayed_row_labels)
        ax.set_xlabel(
            "Point in row"
            if args.compact_cyclic
            else "Sensor column"
            if (args.unwrap_three_rows or args.dual_units)
            else "Column pin"
        )
        ax.set_ylabel(
            "Unit / sensor row" if args.dual_units
            else (
                "Sensor row"
                if (args.unwrap_three_rows or args.compact_cyclic)
                else "Row pin"
            )
        )
        ax.set_xticks(np.arange(-0.5, shape[1], 1), minor=True)
        ax.set_yticks(np.arange(-0.5, shape[0], 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=0.25, alpha=0.30)
        ax.tick_params(which="minor", bottom=False, left=False)
        if args.dual_units:
            ax.axhline(2.5, color="#00ffff", linewidth=3.0)

    ax_raw.set_title(
        "Raw voltage"
        if args.dual_units
        else (
            "Raw ADC Voltage — Restored 3x6 Sensor Layout"
            if args.unwrap_three_rows
            else "Raw ADC Voltage (unwired/floating inputs can be non-zero)"
        )
    )
    ax_activity.set_title("Signal")
    if ax_delta is not None:
        ax_delta.set_title("Ungated Raw ΔV vs Rolling Median")
    strongest_box = Rectangle(
        (-0.5, -0.5), 1, 1, fill=False, edgecolor="#00ff88", linewidth=3
    )
    ax_activity.add_patch(strongest_box)
    strongest_box.set_visible(False)

    show_cell_text = shape[0] * shape[1] <= 256
    cell_font_size = 5 if shape[0] >= 12 else 7
    raw_value_texts = []
    delta_value_texts = []
    value_texts = []
    if show_cell_text:
        for row in range(shape[0]):
            raw_text_row = []
            delta_text_row = []
            text_row = []
            for col in range(shape[1]):
                raw_text_row.append(
                    ax_raw.text(
                        col,
                        row,
                        (
                            f"{source_node_labels[row, col]}\n0.000 V"
                            if scan_mask[row, col]
                            else "—"
                        ),
                        ha="center",
                        va="center",
                        fontsize=cell_font_size,
                        color="white",
                    )
                )
                if ax_delta is not None:
                    delta_text_row.append(
                        ax_delta.text(
                            col,
                            row,
                            (
                                f"{source_node_labels[row, col]}\n+0.000 V"
                                if scan_mask[row, col]
                                else "—"
                            ),
                            ha="center",
                            va="center",
                            fontsize=cell_font_size,
                            color="black",
                        )
                    )
                text_row.append(
                    ax_activity.text(
                        col,
                        row,
                        (
                            f"{source_node_labels[row, col]}\n0%"
                            if scan_mask[row, col]
                            else "—"
                        ),
                        ha="center",
                        va="center",
                        fontsize=cell_font_size,
                        color="black",
                    )
                )
            raw_value_texts.append(raw_text_row)
            if ax_delta is not None:
                delta_value_texts.append(delta_text_row)
            value_texts.append(text_row)

    status = fig.text(
        0.5,
        0.055,
        "Starting...",
        ha="center",
        va="bottom",
        family="monospace",
        fontsize=11,
    )

    slider_ax = fig.add_axes((0.16, 0.018, 0.28, 0.025))
    mapped_round_control = (
        args.mode in ("point", "batch96") and physical_pin_map is not None
    )
    batch_round_control = args.mode == "batch96"
    interval_slider = Slider(
        slider_ax,
        (
            "Full round (s)"
            if mapped_round_control
            else "Point dwell (s)" if args.mode == "point" else "Frame interval (s)"
        ),
        0.02 if batch_round_control else 0.2 if mapped_round_control else 0.001,
        10.0 if mapped_round_control else 2.0,
        valinit=(
            args.interval
            if batch_round_control
            else len(scan_points) * args.interval
            if mapped_round_control
            else args.interval
        ),
        valstep=0.01 if batch_round_control else 0.1 if mapped_round_control else 0.001,
    )

    def change_interval(value):
        reader.interval_s = (
            float(value)
            if batch_round_control
            else float(value) / len(scan_points)
            if mapped_round_control
            else float(value)
        )

    interval_slider.on_changed(change_interval)

    sensitivity_ax = fig.add_axes((0.60, 0.018, 0.28, 0.025))
    sensitivity_slider = Slider(
        sensitivity_ax,
        "Sensitivity",
        0.25,
        5.0,
        valinit=args.sensitivity,
        valstep=0.05,
    )

    recording = {
        "file": None,
        "writer": None,
        "path": None,
        "start_monotonic": 0.0,
        "rows_since_flush": 0,
    }
    record_indicator = fig.text(
        0.99,
        0.985,
        "",
        ha="right",
        va="top",
        color="#c00000",
        weight="bold",
        family="monospace",
        fontsize=10,
    )

    def stop_recording(update_status=True):
        record_file = recording["file"]
        saved_path = recording["path"]
        if record_file is None:
            return
        try:
            record_file.flush()
            record_file.close()
        finally:
            recording.update(
                file=None,
                writer=None,
                path=None,
                start_monotonic=0.0,
                rows_since_flush=0,
            )
        record_indicator.set_text("")
        if args.tabbed_secondary:
            record_button.label.set_text("Start REC")
            record_button.ax.set_facecolor("#ffc6c6")
        if update_status and saved_path is not None:
            status.set_text(f"CSV saved: {saved_path}")
        fig.canvas.draw_idle()

    def toggle_recording(_event=None):
        if recording["file"] is not None:
            stop_recording()
            return
        output_dir = Path(args.record_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / datetime.now().strftime(
            "tactile_96points_%Y%m%d_%H%M%S.csv"
        )
        record_file = output_path.open("w", newline="", encoding="utf-8")
        writer = csv.writer(record_file)
        writer.writerow(
            (
                "timestamp",
                "elapsed_s",
                "round",
                "scan_index",
                "sensor_row",
                "point_in_row",
                "logical_node",
                "physical_row_pin",
                "physical_column_pin",
                "raw_voltage_v",
                "baseline_v",
                "delta_v",
                "signal_0_to_1",
                "baseline_ready",
                "short_below_0_2v",
                "persistent_short_ignored",
            )
        )
        record_file.flush()
        recording.update(
            file=record_file,
            writer=writer,
            path=output_path.resolve(),
            start_monotonic=time.monotonic(),
            rows_since_flush=0,
        )
        record_indicator.set_text(f"● REC  {output_path.name}")
        record_button.label.set_text("Stop REC")
        record_button.ax.set_facecolor("#ff7777")
        status.set_text(f"Recording CSV: {output_path.resolve()}")
        fig.canvas.draw_idle()

    def record_point_sample(
        sample_time,
        point_index,
        display_row,
        display_col,
        raw_row,
        raw_col,
        voltage,
        below_short_threshold,
        persistent_short=False,
    ):
        writer = recording["writer"]
        if writer is None:
            return
        writer.writerow(
            (
                datetime.now().isoformat(timespec="milliseconds"),
                f"{sample_time - recording['start_monotonic']:.6f}",
                max(sequence + 1, 0),
                point_index + 1,
                display_row + 1,
                display_col + 1,
                source_node_labels[display_row, display_col],
                raw_row + 1,
                raw_col + 1,
                f"{voltage:.6f}",
                f"{baseline[display_row, display_col]:.6f}",
                f"{raw_delta_v[display_row, display_col]:.6f}",
                f"{activity[display_row, display_col]:.6f}",
                int(baseline_ready[display_row, display_col]),
                int(below_short_threshold),
                int(persistent_short),
            )
        )
        recording["rows_since_flush"] += 1
        if recording["rows_since_flush"] >= len(scan_points):
            recording["file"].flush()
            recording["rows_since_flush"] = 0

    secondary_view = {"name": "delta" if args.tabbed_secondary else "signal"}
    if args.tabbed_secondary:
        delta_tab_ax = fig.add_axes((0.58, 0.935, 0.075, 0.035))
        signal_tab_ax = fig.add_axes((0.66, 0.935, 0.075, 0.035))
        reset_baseline_ax = fig.add_axes((0.74, 0.935, 0.11, 0.035))
        record_ax = fig.add_axes((0.86, 0.935, 0.11, 0.035))
        delta_tab = Button(delta_tab_ax, "Raw ΔV", color="#bcd7ff", hovercolor="#9fc5ff")
        signal_tab = Button(signal_tab_ax, "Signal", color="#eeeeee", hovercolor="#dddddd")
        reset_baseline_button = Button(
            reset_baseline_ax,
            "Reset Baseline",
            color="#ffe0a8",
            hovercolor="#ffc766",
        )
        record_button = Button(
            record_ax,
            "Start REC",
            color="#ffc6c6",
            hovercolor="#ff9999",
        )

        def reset_baseline(_event=None):
            for history_row in histories:
                for history in history_row:
                    history.clear()
            baseline.fill(0.0)
            threshold_v.fill(0.0)
            raw_delta_v.fill(0.0)
            activity.fill(0.0)
            baseline_ready.fill(False)
            open_circuit.fill(False)
            low_voltage_since.fill(np.nan)
            strongest_box.set_visible(False)
            status.set_text(
                f"Baseline reset — release sensor and rebuilding 0/"
                f"{active_sensor_count}"
            )
            fig.canvas.draw_idle()

        def select_secondary(name):
            secondary_view["name"] = name
            if secondary_view["name"] == "delta":
                activity_image.set_cmap("coolwarm")
                activity_image.set_clim(-0.25, 0.25)
                ax_activity.set_title("Raw ΔV")
                activity_colorbar.set_label("ΔV")
                delta_tab.ax.set_facecolor("#bcd7ff")
                signal_tab.ax.set_facecolor("#eeeeee")
            else:
                activity_image.set_cmap(SIGNAL_CMAP)
                activity_image.set_clim(0.0, 1.0)
                ax_activity.set_title("Signal")
                activity_colorbar.set_label("Signal")
                delta_tab.ax.set_facecolor("#eeeeee")
                signal_tab.ax.set_facecolor("#bcd7ff")
            fig.canvas.draw_idle()

        delta_tab.on_clicked(lambda _event: select_secondary("delta"))
        signal_tab.on_clicked(lambda _event: select_secondary("signal"))
        reset_baseline_button.on_clicked(reset_baseline)
        record_button.on_clicked(toggle_recording)
        select_secondary("delta")

    reader.start()

    def rolling_window_seconds() -> float:
        """Keep enough time to retain at least two earlier reads per sensor."""
        if args.mode != "point":
            return ROLLING_BASELINE_WINDOW_S
        round_seconds = len(scan_points) * reader.interval_s
        return max(
            ROLLING_BASELINE_WINDOW_S,
            ROLLING_BASELINE_ROUND_MULTIPLIER * round_seconds,
        )

    def scan_round_seconds() -> float:
        return (
            reader.interval_s
            if args.mode == "batch96"
            else len(scan_points) * reader.interval_s
        )

    def should_ignore_as_persistent_short(
        display_row: int,
        display_col: int,
        voltage: float,
        sample_time: float,
    ) -> bool:
        """Ignore only a low input that never established a normal baseline.

        A calibrated sensor falling below 0.2 V is a strong press, not a
        short.  A node that remains below 0.2 V for two seconds while trying
        to establish its idle baseline is classified as a persistent short.
        Reset Baseline clears the classification and tests the wiring again.
        """
        if args.legacy_visible_signal or voltage >= SHORT_AS_OPEN_THRESHOLD_V:
            low_voltage_since[display_row, display_col] = np.nan
            return False
        has_normal_baseline = bool(
            baseline_ready[display_row, display_col]
            and baseline[display_row, display_col] >= RAW_DISPLAY_MIN_V
            and not open_circuit[display_row, display_col]
        )
        if has_normal_baseline:
            return False
        if np.isnan(low_voltage_since[display_row, display_col]):
            low_voltage_since[display_row, display_col] = sample_time
        if (
            sample_time - low_voltage_since[display_row, display_col]
            >= SHORT_QUALIFY_TIME_S
        ):
            open_circuit[display_row, display_col] = True
            # A confirmed hardware short is a resolved inactive channel, so it
            # must not hold the whole GUI in "Building baseline" forever.
            baseline_ready[display_row, display_col] = True
        return True

    def update(_):
        nonlocal current, smoothed, baseline, frames, sequence
        nonlocal active_point_index
        nonlocal disconnected, error_message, consecutive_zero_frames
        nonlocal threshold_v, raw_delta_v, activity, baseline_ready, open_circuit

        # Never drain an actively produced queue without a bound. At fast scan
        # rates the producer can refill it as quickly as we consume it, which
        # previously kept this callback running forever and left the visible
        # baseline counter stuck even though samples were arriving.
        for _event_number in range(MAX_EVENTS_PER_GUI_UPDATE):
            try:
                event = frame_queue.get_nowait()
            except queue.Empty:
                break
            if event[0] == "error":
                disconnected = True
                error_message = event[1]
                continue
            _, sample_time, frame, sequence, active_point_index, round_complete = event
            frames += 1
            batch_raw_values = None
            if args.mode == "point" and point_specification and active_point_index >= 0:
                display_row, display_col = point_display_positions[active_point_index]
                raw_row, raw_col = scan_points[active_point_index]
                incoming_value = float(frame[raw_row, raw_col])
                if should_ignore_as_persistent_short(
                    display_row, display_col, incoming_value, sample_time
                ):
                    # Keep the last valid raw voltage while a startup short is
                    # being qualified or ignored.
                    raw_delta_v[display_row, display_col] = 0.0
                    activity[display_row, display_col] = 0.0
                    record_point_sample(
                        sample_time,
                        active_point_index,
                        display_row,
                        display_col,
                        raw_row,
                        raw_col,
                        incoming_value,
                        True,
                        bool(open_circuit[display_row, display_col]),
                    )
                    continue
                current[display_row, display_col] = incoming_value
                open_circuit[display_row, display_col] = False
            elif args.mode == "batch96":
                batch_raw_values = np.zeros(shape, dtype=np.float64)
                for point_index, ((raw_row, raw_col), (display_row, display_col)) in enumerate(
                    zip(scan_points, point_display_positions)
                ):
                    incoming_value = float(frame[raw_row, raw_col])
                    batch_raw_values[display_row, display_col] = incoming_value
                    if (
                        args.legacy_visible_signal
                        or incoming_value >= SHORT_AS_OPEN_THRESHOLD_V
                        or (
                            baseline_ready[display_row, display_col]
                            and baseline[display_row, display_col]
                            >= RAW_DISPLAY_MIN_V
                            and not open_circuit[display_row, display_col]
                        )
                    ):
                        current[display_row, display_col] = incoming_value
            else:
                current = frame[np.ix_(row_indices, col_indices)].astype(np.float64)
            if round_complete:
                if np.count_nonzero(current) == 0:
                    consecutive_zero_frames += 1
                else:
                    consecutive_zero_frames = 0
            if args.mode in ("point", "batch96"):
                smoothed = current.copy()
            elif smoothed is None:
                smoothed = current.copy()
            else:
                smoothed = (
                    (1.0 - SMOOTHING_ALPHA) * smoothed
                    + SMOOTHING_ALPHA * current
                )
            if args.mode == "point" and active_point_index >= 0:
                display_row, display_col = point_display_positions[active_point_index]
                history = histories[display_row][display_col]
                point_value = float(current[display_row, display_col])
                cutoff = sample_time - rolling_window_seconds()
                freeze_contact_baseline = bool(
                    args.contact_drop_fraction is not None
                    and baseline_ready[display_row, display_col]
                    and activity[display_row, display_col] > 0.0
                )
                if not freeze_contact_baseline:
                    while history and history[0][0] < cutoff:
                        history.popleft()
                old_enough = bool(
                    history
                    and sample_time - history[0][0] >= ROLLING_BASELINE_MIN_AGE_S
                )
                point_activity, point_baseline, point_threshold, enough_samples = (
                    rolling_activity(
                        current[display_row, display_col],
                        history,
                        sensitivity_slider.val,
                        args.contact_drop_fraction,
                    )
                )
                ready = old_enough and enough_samples
                if enough_samples:
                    baseline[display_row, display_col] = point_baseline
                    threshold_v[display_row, display_col] = point_threshold
                # Once calibrated, do not send the entire display back into
                # "Building baseline" merely because a released point is
                # collecting a fresh idle history.
                baseline_ready[display_row, display_col] = bool(
                    baseline_ready[display_row, display_col] or ready
                )
                raw_delta_v[display_row, display_col] = (
                    current[display_row, display_col] - point_baseline
                    if enough_samples
                    else 0.0
                )
                activity[display_row, display_col] = (
                    point_activity
                    if baseline_ready[display_row, display_col] and enough_samples
                    else 0.0
                )
                contact_is_active = bool(
                    args.contact_drop_fraction is not None
                    and baseline_ready[display_row, display_col]
                    and activity[display_row, display_col] > 0.0
                )
                if not contact_is_active:
                    history.append(
                        (sample_time, float(current[display_row, display_col]))
                    )
                record_point_sample(
                    sample_time,
                    active_point_index,
                    display_row,
                    display_col,
                    raw_row,
                    raw_col,
                    point_value,
                    point_value < SHORT_AS_OPEN_THRESHOLD_V,
                )
            elif args.mode != "point" and round_complete:
                # Full-frame protocols update every sensor at the same timestamp.
                for display_row in range(shape[0]):
                    for display_col in range(shape[1]):
                        if not scan_mask[display_row, display_col]:
                            continue
                        history = histories[display_row][display_col]
                        point_value = float(
                            batch_raw_values[display_row, display_col]
                            if batch_raw_values is not None
                            else current[display_row, display_col]
                        )
                        if should_ignore_as_persistent_short(
                            display_row, display_col, point_value, sample_time
                        ):
                            raw_delta_v[display_row, display_col] = 0.0
                            activity[display_row, display_col] = 0.0
                            if args.mode == "batch96":
                                point_index = int(
                                    point_index_lookup[display_row, display_col]
                                )
                                raw_row, raw_col = scan_points[point_index]
                                record_point_sample(
                                    sample_time,
                                    point_index,
                                    display_row,
                                    display_col,
                                    raw_row,
                                    raw_col,
                                    point_value,
                                    True,
                                    bool(open_circuit[display_row, display_col]),
                                )
                            continue
                        open_circuit[display_row, display_col] = False
                        cutoff = sample_time - rolling_window_seconds()
                        freeze_contact_baseline = bool(
                            args.contact_drop_fraction is not None
                            and baseline_ready[display_row, display_col]
                            and activity[display_row, display_col] > 0.0
                        )
                        if not freeze_contact_baseline:
                            while history and history[0][0] < cutoff:
                                history.popleft()
                        old_enough = bool(
                            history
                            and sample_time - history[0][0]
                            >= ROLLING_BASELINE_MIN_AGE_S
                        )
                        point_activity, point_baseline, point_threshold, enough_samples = (
                            rolling_activity(
                                current[display_row, display_col],
                                history,
                                sensitivity_slider.val,
                                args.contact_drop_fraction,
                            )
                        )
                        ready = old_enough and enough_samples
                        if enough_samples:
                            baseline[display_row, display_col] = point_baseline
                            threshold_v[display_row, display_col] = point_threshold
                        baseline_ready[display_row, display_col] = bool(
                            baseline_ready[display_row, display_col] or ready
                        )
                        raw_delta_v[display_row, display_col] = (
                            current[display_row, display_col] - point_baseline
                            if enough_samples
                            else 0.0
                        )
                        activity[display_row, display_col] = (
                            point_activity
                            if baseline_ready[display_row, display_col] and enough_samples
                            else 0.0
                        )
                        contact_is_active = bool(
                            args.contact_drop_fraction is not None
                            and baseline_ready[display_row, display_col]
                            and activity[display_row, display_col] > 0.0
                        )
                        if not contact_is_active:
                            history.append((sample_time, point_value))
                        if args.mode == "batch96":
                            point_index = int(
                                point_index_lookup[display_row, display_col]
                            )
                            raw_row, raw_col = scan_points[point_index]
                            record_point_sample(
                                sample_time,
                                point_index,
                                display_row,
                                display_col,
                                raw_row,
                                raw_col,
                                point_value,
                                point_value < SHORT_AS_OPEN_THRESHOLD_V,
                            )

        if disconnected:
            blank = np.zeros(shape, dtype=np.float64)
            raw_image.set_data(blank)
            if delta_image is not None:
                delta_image.set_data(blank)
            activity_image.set_data(blank)
            strongest_box.set_visible(False)
            if show_cell_text:
                for row in value_texts:
                    for item in row:
                        item.set_text("0")
            status.set_text(f"DISCONNECTED — {error_message}")
            fig.suptitle("DISCONNECTED — no live sensor data", color="#b00020")
            return [raw_image, activity_image, strongest_box, status]

        if smoothed is not None:
            raw_image.set_data(np.where(scan_mask, smoothed, np.nan))
        if delta_image is not None:
            delta_image.set_data(np.where(scan_mask, raw_delta_v, np.nan))

        if consecutive_zero_frames >= 3:
            blank = np.zeros(shape, dtype=np.float64)
            if delta_image is not None:
                delta_image.set_data(blank)
            activity_image.set_data(blank)
            strongest_box.set_visible(False)
            status.set_text(
                f"ADC FAILURE — selected pins are all 0x00 for "
                f"{consecutive_zero_frames} consecutive frames"
            )
            fig.suptitle(
                "SERIAL CONNECTED, BUT ADC RETURNS ONLY ZERO — check AD7466 power/CS/SDATA",
                color="#b00020",
                fontsize=14,
            )
            return [raw_image, activity_image, strongest_box, status]
        elif not disconnected:
            fig.suptitle("")

        ready_count = int(np.count_nonzero(baseline_ready))
        if ready_count < active_sensor_count or smoothed is None:
            baseline_window_s = rolling_window_seconds()
            status.set_text(
                f"Building rolling baseline {ready_count}/{active_sensor_count} sensors — "
                f"history={baseline_window_s:.1f} s  "
                f"round≈{scan_round_seconds():.2f} s"
            )
            strongest_box.set_visible(False)
        else:
            max_flat = int(np.argmax(np.where(scan_mask, activity, -np.inf)))
            max_row, max_col = np.unravel_index(max_flat, shape)
            max_value = float(activity[max_row, max_col])
            strongest_box.set_xy((max_col - 0.5, max_row - 0.5))
            strongest_box.set_visible(max_value > 0.0)
            strongest_label = (
                f"sensor=S{max_row + 1},{max_col + 1} "
                f"source={source_node_labels[max_row, max_col]}"
                if (args.unwrap_three_rows or args.dual_units or args.compact_cyclic)
                else f"strongest=R{displayed_rows[max_row]}C{displayed_cols[max_col]}"
            )
            if args.dual_units:
                status.set_text(
                    f"round {max(sequence + 1, 0)}   "
                    f"dwell {reader.interval_s:.2f}s   "
                    f"full scan {scan_round_seconds():.2f}s   "
                    f"sensitivity {sensitivity_slider.val:.2f}"
                )
            else:
                status.set_text(
                    f"round={max(sequence + 1, 0)} samples={frames}  "
                    f"{strongest_label}  "
                    f"normalized change={max_value * 100.0:.1f}%  "
                    f"gate={threshold_v[max_row, max_col]:.3f} V  "
                    f"sensitivity={sensitivity_slider.val:.2f}  "
                    f"{'frame interval' if args.mode == 'batch96' else 'point dwell'}="
                    f"{reader.interval_s:.3f} s  "
                    f"round≈{scan_round_seconds():.3f} s"
                )

        secondary_is_delta = (
            args.tabbed_secondary and secondary_view["name"] == "delta"
        )
        secondary_data = raw_delta_v if secondary_is_delta else activity
        activity_image.set_data(np.where(scan_mask, secondary_data, np.nan))
        if show_cell_text:
            for row in range(shape[0]):
                for col in range(shape[1]):
                    if not scan_mask[row, col]:
                        raw_value_texts[row][col].set_text("—")
                        if ax_delta is not None:
                            delta_value_texts[row][col].set_text("—")
                        value_texts[row][col].set_text("—")
                        value_texts[row][col].set_color("#777777")
                        continue
                    raw_value = float(current[row, col])
                    node_label = source_node_labels[row, col]
                    if args.legacy_visible_signal:
                        raw_value_texts[row][col].set_text(
                            f"{node_label}\n{raw_value:.3f} V"
                        )
                    elif raw_value > RAW_DISPLAY_MAX_V:
                        raw_value_texts[row][col].set_text(
                            f"{node_label}\n{raw_value:.3f} V HIGH"
                        )
                    elif raw_value < RAW_DISPLAY_MIN_V:
                        raw_value_texts[row][col].set_text(
                            f"{node_label}\n{raw_value:.3f} V LOW"
                        )
                    else:
                        raw_value_texts[row][col].set_text(
                            f"{node_label}\n{raw_value:.3f} V"
                        )
                    raw_value_texts[row][col].set_color(
                        "white" if raw_value < 1.0 else "black"
                    )
                    if ax_delta is not None:
                        delta_value = float(raw_delta_v[row, col])
                        delta_value_texts[row][col].set_text(
                            f"{node_label}\n{delta_value:+.3f} V"
                        )
                        delta_value_texts[row][col].set_color(
                            "white" if abs(delta_value) > 0.16 else "black"
                        )
                    if secondary_is_delta:
                        delta_value = float(raw_delta_v[row, col])
                        value_texts[row][col].set_text(
                            f"{node_label}\n{delta_value:+.3f} V"
                        )
                        value_texts[row][col].set_color(
                            "white" if abs(delta_value) > 0.16 else "black"
                        )
                    else:
                        percent = int(round(activity[row, col] * 100.0))
                        value_texts[row][col].set_text(f"{node_label}\n{percent}%")
                        value_texts[row][col].set_color(
                            "white"
                            if activity[row, col] > 0.55
                            else "black"
                        )
        return [raw_image, activity_image, strongest_box, status]

    def close(_event=None):
        stop_recording(update_status=False)
        reader.stop()
        try:
            ser.close()
        except (serial.SerialException, OSError):
            pass
        reader.join(timeout=1.0)

    fig.canvas.mpl_connect("close_event", close)
    ani = animation.FuncAnimation(
        fig,
        update,
        interval=50,
        blit=False,
        cache_frame_data=False,
    )
    _ = ani
    plt.tight_layout(rect=(0.0, 0.10, 1.0, 0.92 if args.tabbed_secondary else 0.98))
    try:
        plt.show()
    finally:
        close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
