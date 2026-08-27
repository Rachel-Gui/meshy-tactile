"""FastAPI backend for the local tactile 3D dashboard."""

from __future__ import annotations

import asyncio
import csv
from collections import deque
from contextlib import asynccontextmanager
import math
from pathlib import Path
import re
import statistics
import threading
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # The simulation mode remains available without pyserial.
    serial = None
    list_ports = None


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BAUD_RATE = 1_000_000
ROWS = 12
COLUMNS = 8
SENSOR_COUNT = ROWS * COLUMNS
PLAYBACK_FPS = 15.0
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
AUTO_CLEAR_IDLE_SECONDS = 5.0
AUTO_CLEAR_CHANGE_EPSILON = 0.015
AUTO_CLEAR_SIGNAL_THRESHOLD = 0.05
VREF = 3.3
PHYSICAL_PIN_MAP = (1, 3, 5, 7, 2, 4, 6, 8, 10, 12, 14, 16)
PLAYBACK_DIR = ROOT.parent / "tactile_data_for_colleague_20260819"
UPLOAD_DIR = ROOT.parent / "uploaded_playback_data"
PLAYBACK_DATASETS = {
    "tactile_96points_20260817_194852": PLAYBACK_DIR / "tactile_96points_20260817_194852.csv",
    "tactile_96points_20260817_200426": PLAYBACK_DIR / "tactile_96points_20260817_200426.csv",
    "tactile_96points_20260825_144129": PLAYBACK_DIR / "tactile_96points_20260825_144129.csv",
    "tactile_96points_20260825_144214": PLAYBACK_DIR / "tactile_96points_20260825_144214.csv",
    "tactile_96points_20260827_115909": ROOT.parent / "tactile_96points_20260827_115909.csv",
}
PLAYBACK_LABELS = {
    "tactile_96points_20260817_194852": "August 17, 19:48",
    "tactile_96points_20260817_200426": "August 17, 20:04",
    "tactile_96points_20260825_144129": "August 25, 14:41:29",
    "tactile_96points_20260825_144214": "August 25, 14:42:14",
    "tactile_96points_20260827_115909": "August 27, 11:59:09",
}


def register_saved_uploads():
    if not UPLOAD_DIR.exists():
        return
    for path in sorted(UPLOAD_DIR.glob("*.csv")):
        dataset_id = path.stem
        display_name = dataset_id.split("__", 1)[-1].replace("_", " ")
        PLAYBACK_DATASETS[dataset_id] = path
        PLAYBACK_LABELS[dataset_id] = f"Uploaded · {display_name}"


register_saved_uploads()


class ModeRequest(BaseModel):
    mode: Literal["simulation", "playback", "serial"]
    port: str | None = None
    dataset: str | None = None


class PlaybackControlRequest(BaseModel):
    frame_index: int | None = None
    playing: bool | None = None


class AutoClearRequest(BaseModel):
    enabled: bool


class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = "simulation"
        self.requested_port: str | None = None
        self.requested_dataset: str | None = None
        self.connected = True
        self.port: str | None = None
        self.error: str | None = None
        self.sequence = 0
        self.values = [0.0] * SENSOR_COUNT
        self.raw_volts = [0.0] * SENSOR_COUNT
        self.updated_at = time.time()
        self.calibrate_requested = False
        self.playback_index = 0
        self.playback_total = 0
        self.playback_playing = True
        self.playback_seek_requested: int | None = None
        self.auto_clear_enabled = True
        self.auto_clear_count = 0
        self.last_auto_cleared_at: float | None = None

    def snapshot(self):
        with self.lock:
            return {
                "type": "frame",
                "mode": self.mode,
                "connected": self.connected,
                "port": self.port,
                "error": self.error,
                "sequence": self.sequence,
                "timestamp": self.updated_at,
                "values": list(self.values),
                "rawVolts": list(self.raw_volts),
                "playbackIndex": self.playback_index,
                "playbackTotal": self.playback_total,
                "playbackPlaying": self.playback_playing,
                "playbackFps": PLAYBACK_FPS,
                "autoClearEnabled": self.auto_clear_enabled,
                "autoClearIdleSeconds": AUTO_CLEAR_IDLE_SECONDS,
                "autoClearCount": self.auto_clear_count,
                "lastAutoClearedAt": self.last_auto_cleared_at,
            }

    def set_mode(self, mode: str, port: str | None, dataset: str | None):
        with self.lock:
            self.mode = mode
            self.requested_port = port
            self.requested_dataset = dataset
            self.connected = mode in {"simulation", "playback"}
            self.port = None
            self.error = None
            if mode == "playback":
                self.playback_index = 0
                self.playback_total = 0
                self.playback_playing = True
                self.playback_seek_requested = 0

    def set_playback_control(self, frame_index: int | None, playing: bool | None):
        with self.lock:
            if frame_index is not None:
                maximum = max(0, self.playback_total - 1)
                target = min(maximum, max(0, frame_index))
                self.playback_index = target
                self.playback_seek_requested = target
            if playing is not None:
                self.playback_playing = playing

    def request_calibration(self):
        with self.lock:
            self.calibrate_requested = True
            self.values = [0.0] * SENSOR_COUNT
            self.raw_volts = [0.0] * SENSOR_COUNT
            self.sequence += 1
            self.updated_at = time.time()

    def set_auto_clear(self, enabled: bool):
        with self.lock:
            self.auto_clear_enabled = enabled


def available_ports():
    if list_ports is None:
        return []
    return [item.device for item in list_ports.comports()]


def load_playback_frames(dataset: str):
    path = PLAYBACK_DATASETS.get(dataset)
    if path is None or not path.exists():
        raise RuntimeError("Playback dataset was not found")

    frames = []
    current_values = [None] * SENSOR_COUNT
    current_volts = [None] * SENSOR_COUNT

    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                index = int(row["scan_index"]) - 1
                value = float(row["signal_0_to_1"])
                voltage = float(row["raw_voltage_v"])
            except (KeyError, TypeError, ValueError):
                continue

            if not 0 <= index < SENSOR_COUNT:
                continue
            if index == 0 and any(item is not None for item in current_values):
                if all(item is not None for item in current_values):
                    frames.append((current_values, current_volts))
                current_values = [None] * SENSOR_COUNT
                current_volts = [None] * SENSOR_COUNT
            current_values[index] = value
            current_volts[index] = voltage

    if all(item is not None for item in current_values):
        frames.append((current_values, current_volts))
    if not frames:
        raise RuntimeError("Playback dataset contains no complete 96-point frames")
    return frames


def inspect_playback_file(path: Path):
    required_fields = {"scan_index", "raw_voltage_v", "signal_0_to_1"}
    total_rows = 0
    valid_rows = 0
    complete_frames = 0
    frame_indexes = set()

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required_fields.issubset(reader.fieldnames):
            missing = ", ".join(sorted(required_fields.difference(reader.fieldnames or [])))
            raise ValueError(f"CSV is missing required columns: {missing}")

        for row in reader:
            total_rows += 1
            try:
                index = int(row["scan_index"]) - 1
                float(row["signal_0_to_1"])
                float(row["raw_voltage_v"])
            except (TypeError, ValueError):
                continue
            if not 0 <= index < SENSOR_COUNT:
                continue
            if index == 0 and frame_indexes:
                if len(frame_indexes) == SENSOR_COUNT:
                    complete_frames += 1
                frame_indexes = set()
            frame_indexes.add(index)
            valid_rows += 1

    if len(frame_indexes) == SENSOR_COUNT:
        complete_frames += 1
    if not complete_frames:
        raise ValueError("CSV contains no complete 96-point frames")
    return total_rows, valid_rows, complete_frames


def choose_port(requested: str | None):
    if requested:
        return requested
    devices = available_ports()
    candidates = [
        device
        for device in devices
        if "usbserial" in device.lower() or "usbmodem" in device.lower()
    ]
    candidates.sort(key=lambda device: (not device.startswith("/dev/cu."), device))
    if not candidates:
        raise RuntimeError("No USB serial sensor was found")
    return candidates[0]


def read_exact(connection, count: int, timeout_seconds: float = 2.0):
    data = bytearray()
    deadline = time.monotonic() + timeout_seconds
    while len(data) < count:
        chunk = connection.read(count - len(data))
        if chunk:
            data.extend(chunk)
        elif time.monotonic() >= deadline:
            raise TimeoutError("Serial response timed out")
    return bytes(data)


def request_point(connection, row: int, column: int):
    connection.write(bytes((ord("p"), row, column)))
    connection.flush()

    window = bytearray()
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        value = connection.read(1)
        if not value:
            continue
        window.extend(value)
        if len(window) > 2:
            del window[0]
        if bytes(window) == b"\xA5\x5A":
            break
    else:
        raise TimeoutError("Point response header was not received")

    response_row, response_column, sample, checksum = read_exact(connection, 4)
    expected = 0xA5 ^ 0x5A ^ response_row ^ response_column ^ sample
    if checksum != expected:
        raise RuntimeError("Point response checksum error")
    if (response_row, response_column) != (row, column):
        raise RuntimeError("Point response address mismatch")
    return sample


def scan_points():
    return [
        (
            PHYSICAL_PIN_MAP[row] - 1,
            PHYSICAL_PIN_MAP[(row + cyclic_offset) % ROWS] - 1,
        )
        for row in range(ROWS)
        for cyclic_offset in range(1, COLUMNS + 1)
    ]


def signal_from_history(value: float, history: deque[float]):
    if len(history) < 4:
        return 0.0

    baseline = statistics.median(history)
    threshold = max(0.12, baseline * 0.15)
    full_drop = max(baseline * 0.50, threshold + baseline * 0.10)
    pressure_drop = baseline - value

    if pressure_drop <= threshold:
        return 0.0

    return max(
        0.0,
        min(1.0, (pressure_drop - threshold) / (full_drop - threshold)),
    )


class SensorEngine(threading.Thread):
    def __init__(self, state: SharedState):
        super().__init__(daemon=True)
        self.state = state
        self.stop_event = threading.Event()
        self.serial_connection = None
        self.histories = [deque(maxlen=24) for _ in range(SENSOR_COUNT)]
        self.last_serial_values = [0.0] * SENSOR_COUNT
        self.last_signal_change_at = time.monotonic()
        self.auto_clear_armed = False

    def stop(self):
        self.stop_event.set()
        self.close_serial()

    def close_serial(self):
        if self.serial_connection is not None:
            try:
                self.serial_connection.close()
            except Exception:
                pass
            self.serial_connection = None

    def reset_calibration(self):
        for history in self.histories:
            history.clear()

    def reset_auto_clear_tracking(self):
        self.last_serial_values = [0.0] * SENSOR_COUNT
        self.last_signal_change_at = time.monotonic()
        self.auto_clear_armed = False

    def update_simulation(self, start_time: float):
        elapsed = time.monotonic() - start_time
        center_row = (elapsed * 0.55) % ROWS
        center_column = 3.5 + math.sin(elapsed * 0.42) * 2.6
        second_row = (center_row + 5.0) % ROWS
        second_column = 3.5 + math.cos(elapsed * 0.31) * 2.2
        values = []

        for row in range(ROWS):
            for column in range(COLUMNS):
                row_distance = min(
                    abs(row - center_row),
                    ROWS - abs(row - center_row),
                )
                second_row_distance = min(
                    abs(row - second_row),
                    ROWS - abs(row - second_row),
                )
                first = math.exp(
                    -(row_distance**2 / 2.8 + (column - center_column) ** 2 / 2.1)
                )
                second = 0.62 * math.exp(
                    -(second_row_distance**2 / 2.0 + (column - second_column) ** 2 / 3.0)
                )
                pulse = 0.82 + 0.18 * math.sin(elapsed * 2.2)
                values.append(min(1.0, max(first * pulse, second)))

        with self.state.lock:
            self.state.values = values
            self.state.raw_volts = [VREF * (1.0 - value * 0.55) for value in values]
            self.state.sequence += 1
            self.state.connected = True
            self.state.port = None
            self.state.error = None
            self.state.updated_at = time.time()

    def update_playback(self, frames, frame_index):
        values, voltages = frames[frame_index % len(frames)]
        with self.state.lock:
            self.state.values = list(values)
            self.state.raw_volts = list(voltages)
            self.state.sequence += 1
            self.state.connected = True
            self.state.port = self.state.requested_dataset
            self.state.error = None
            self.state.updated_at = time.time()
            self.state.playback_index = frame_index
            self.state.playback_total = len(frames)

    def connect_serial(self, requested_port: str | None):
        if serial is None:
            raise RuntimeError("pyserial is not installed")
        port = choose_port(requested_port)
        connection = serial.Serial(port, BAUD_RATE, timeout=0.05)
        time.sleep(2.0)
        connection.reset_input_buffer()
        connection.reset_output_buffer()
        self.serial_connection = connection
        self.reset_calibration()
        self.reset_auto_clear_tracking()
        with self.state.lock:
            self.state.connected = True
            self.state.port = port
            self.state.error = None

    def update_serial(self):
        points = scan_points()
        samples = [0.0] * SENSOR_COUNT
        values = [0.0] * SENSOR_COUNT

        for sensor_index, (row, column) in enumerate(points):
            if self.stop_event.is_set():
                return
            sample = request_point(self.serial_connection, row, column)
            voltage = sample * (VREF / 255.0)
            samples[sensor_index] = voltage
            history = self.histories[sensor_index]
            signal = signal_from_history(voltage, history)
            values[sensor_index] = signal
            if signal < 0.05:
                history.append(voltage)

        now = time.monotonic()
        maximum_signal = max(values, default=0.0)
        maximum_change = max(
            (abs(value - previous) for value, previous in zip(values, self.last_serial_values)),
            default=0.0,
        )
        with self.state.lock:
            auto_clear_enabled = self.state.auto_clear_enabled

        auto_cleared = False
        if not auto_clear_enabled or maximum_signal < AUTO_CLEAR_SIGNAL_THRESHOLD:
            self.auto_clear_armed = False
            self.last_signal_change_at = now
        elif not self.auto_clear_armed:
            self.auto_clear_armed = True
            self.last_signal_change_at = now
        elif maximum_change >= AUTO_CLEAR_CHANGE_EPSILON:
            self.last_signal_change_at = now
        elif now - self.last_signal_change_at >= AUTO_CLEAR_IDLE_SECONDS:
            self.reset_calibration()
            values = [0.0] * SENSOR_COUNT
            self.auto_clear_armed = False
            self.last_signal_change_at = now
            auto_cleared = True
        self.last_serial_values = list(values)

        with self.state.lock:
            if self.state.calibrate_requested:
                self.reset_calibration()
                self.state.calibrate_requested = False
            self.state.values = values
            self.state.raw_volts = samples
            self.state.sequence += 1
            self.state.connected = True
            self.state.error = None
            self.state.updated_at = time.time()
            if auto_cleared:
                self.state.auto_clear_count += 1
                self.state.last_auto_cleared_at = self.state.updated_at

    def run(self):
        simulation_start = time.monotonic()
        last_mode = None
        last_dataset = None
        playback_frames = None
        playback_index = 0

        while not self.stop_event.is_set():
            with self.state.lock:
                mode = self.state.mode
                requested_port = self.state.requested_port
                requested_dataset = self.state.requested_dataset
                calibrate = self.state.calibrate_requested

            if calibrate and mode == "simulation":
                with self.state.lock:
                    self.state.calibrate_requested = False

            if mode != last_mode or (mode == "playback" and requested_dataset != last_dataset):
                self.close_serial()
                simulation_start = time.monotonic()
                playback_frames = None
                playback_index = 0
                last_mode = mode
                last_dataset = requested_dataset

            if mode == "simulation":
                self.update_simulation(simulation_start)
                self.stop_event.wait(1.0 / 15.0)
                continue

            if mode == "playback":
                try:
                    if playback_frames is None:
                        playback_frames = load_playback_frames(requested_dataset)
                        with self.state.lock:
                            self.state.playback_total = len(playback_frames)
                    with self.state.lock:
                        seek_requested = self.state.playback_seek_requested
                        playing = self.state.playback_playing
                        self.state.playback_seek_requested = None
                    if seek_requested is not None:
                        playback_index = min(len(playback_frames) - 1, max(0, seek_requested))
                    if playing or seek_requested is not None:
                        self.update_playback(playback_frames, playback_index)
                    if playing:
                        playback_index = (playback_index + 1) % len(playback_frames)
                    self.stop_event.wait(1.0 / PLAYBACK_FPS)
                except Exception as error:
                    with self.state.lock:
                        self.state.connected = False
                        self.state.error = str(error)
                        self.state.updated_at = time.time()
                    self.stop_event.wait(2.0)
                continue

            try:
                if self.serial_connection is None:
                    self.connect_serial(requested_port)
                self.update_serial()
            except Exception as error:
                self.close_serial()
                with self.state.lock:
                    self.state.connected = False
                    self.state.port = None
                    self.state.error = str(error)
                    self.state.updated_at = time.time()
                self.stop_event.wait(2.0)


state = SharedState()
engine = SensorEngine(state)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    engine.start()
    yield
    engine.stop()
    engine.join(timeout=3.0)


app = FastAPI(title="Tactile 3D Dashboard", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
async def status():
    payload = state.snapshot()
    payload["ports"] = available_ports()
    payload.pop("values", None)
    payload.pop("rawVolts", None)
    return payload


@app.get("/api/ports")
async def ports():
    return {"ports": available_ports()}


@app.get("/api/playback-datasets")
async def playback_datasets():
    return {
        "datasets": [
            {"id": dataset_id, "label": PLAYBACK_LABELS[dataset_id]}
            for dataset_id in PLAYBACK_DATASETS
        ]
    }


@app.post("/api/playback-datasets/upload")
async def upload_playback_dataset(request: Request, filename: str):
    original_name = Path(filename).name.strip()
    if not original_name or Path(original_name).suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Choose a CSV file")

    safe_stem = re.sub(r"[^\w.-]+", "_", Path(original_name).stem).strip("._")[:80]
    safe_stem = safe_stem or "recording"
    dataset_id = f"upload_{time.time_ns()}__{safe_stem}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPLOAD_DIR / f"{dataset_id}.csv"
    temporary = UPLOAD_DIR / f".{dataset_id}.uploading"
    total_bytes = 0

    try:
        with temporary.open("wb") as handle:
            async for chunk in request.stream():
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="CSV must be 100 MB or smaller")
                handle.write(chunk)
        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="The selected CSV is empty")
        try:
            rows, valid_rows, frames = inspect_playback_file(temporary)
        except (UnicodeDecodeError, ValueError, csv.Error) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()

    label = f"Uploaded · {Path(original_name).stem}"
    PLAYBACK_DATASETS[dataset_id] = destination
    PLAYBACK_LABELS[dataset_id] = label
    return {
        "id": dataset_id,
        "label": label,
        "rows": rows,
        "validRows": valid_rows,
        "frames": frames,
        "sizeBytes": total_bytes,
    }


@app.get("/api/playback-preview/{dataset}")
async def playback_preview(dataset: str):
    path = PLAYBACK_DATASETS.get(dataset)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Playback dataset was not found")

    rows = []
    total_rows = 0
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            total_rows += 1
            if len(rows) < 5:
                rows.append({
                    "scanIndex": row.get("scan_index"),
                    "sensor": f"R{row.get('sensor_row')} · P{row.get('point_in_row')}",
                    "voltage": row.get("raw_voltage_v"),
                    "signal": row.get("signal_0_to_1"),
                })

    return {
        "id": dataset,
        "label": PLAYBACK_LABELS[dataset],
        "rows": total_rows,
        "frames": total_rows // SENSOR_COUNT,
        "sample": rows,
    }


@app.post("/api/mode")
async def set_mode(request: ModeRequest):
    if request.mode == "serial" and serial is None:
        raise HTTPException(status_code=500, detail="pyserial is not installed")
    if request.mode == "playback" and request.dataset not in PLAYBACK_DATASETS:
        raise HTTPException(status_code=400, detail="Choose a playback dataset")
    state.set_mode(request.mode, request.port, request.dataset)
    return {"ok": True, "mode": request.mode, "port": request.port, "dataset": request.dataset}


@app.post("/api/playback/control")
async def control_playback(request: PlaybackControlRequest):
    if state.mode != "playback":
        raise HTTPException(status_code=409, detail="Recorded data is not active")
    state.set_playback_control(request.frame_index, request.playing)
    return {
        "ok": True,
        "frameIndex": state.playback_index,
        "playing": state.playback_playing,
    }


@app.post("/api/calibrate")
async def calibrate():
    state.request_calibration()
    return {"ok": True}


@app.post("/api/auto-clear")
async def set_auto_clear(request: AutoClearRequest):
    state.set_auto_clear(request.enabled)
    return {
        "ok": True,
        "enabled": request.enabled,
        "idleSeconds": AUTO_CLEAR_IDLE_SECONDS,
    }


@app.post("/api/model/reload")
async def reload_model():
    rhinocode = Path("/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode")
    exporter = ROOT / "export_grasshopper_model.py"
    if not rhinocode.exists():
        raise HTTPException(status_code=500, detail="Rhino 8 rhinocode was not found")

    process = await asyncio.create_subprocess_exec(
        str(rhinocode),
        "script",
        str(exporter),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    message = output.decode("utf-8", errors="replace").strip()

    if process.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=message or "Open Rhino and tactile/1.gh before reloading",
        )

    return {"ok": True, "message": message or "Grasshopper model exported"}


@app.websocket("/ws")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(state.snapshot())
            await asyncio.sleep(1.0 / 15.0)
    except (WebSocketDisconnect, RuntimeError):
        return


@app.get("/")
async def index():
    index_path = DIST / "index.html"
    if not index_path.exists():
        raise HTTPException(
            status_code=503,
            detail="Frontend is not built. Run npm install && npm run build in web/.",
        )
    return FileResponse(index_path)


if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
