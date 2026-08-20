"""FastAPI backend for the local tactile 3D dashboard."""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
import math
from pathlib import Path
import statistics
import threading
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
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
VREF = 3.3
PHYSICAL_PIN_MAP = (1, 3, 5, 7, 2, 4, 6, 8, 10, 12, 14, 16)


class ModeRequest(BaseModel):
    mode: Literal["simulation", "serial"]
    port: str | None = None


class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = "simulation"
        self.requested_port: str | None = None
        self.connected = True
        self.port: str | None = None
        self.error: str | None = None
        self.sequence = 0
        self.values = [0.0] * SENSOR_COUNT
        self.raw_volts = [0.0] * SENSOR_COUNT
        self.updated_at = time.time()
        self.calibrate_requested = False

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
            }

    def set_mode(self, mode: str, port: str | None):
        with self.lock:
            self.mode = mode
            self.requested_port = port
            self.connected = mode == "simulation"
            self.port = None
            self.error = None

    def request_calibration(self):
        with self.lock:
            self.calibrate_requested = True


def available_ports():
    if list_ports is None:
        return []
    return [item.device for item in list_ports.comports()]


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

    def run(self):
        simulation_start = time.monotonic()
        last_mode = None

        while not self.stop_event.is_set():
            with self.state.lock:
                mode = self.state.mode
                requested_port = self.state.requested_port
                calibrate = self.state.calibrate_requested

            if calibrate and mode == "simulation":
                with self.state.lock:
                    self.state.calibrate_requested = False

            if mode != last_mode:
                self.close_serial()
                simulation_start = time.monotonic()
                last_mode = mode

            if mode == "simulation":
                self.update_simulation(simulation_start)
                self.stop_event.wait(1.0 / 15.0)
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


@app.post("/api/mode")
async def set_mode(request: ModeRequest):
    if request.mode == "serial" and serial is None:
        raise HTTPException(status_code=500, detail="pyserial is not installed")
    state.set_mode(request.mode, request.port)
    return {"ok": True, "mode": request.mode, "port": request.port}


@app.post("/api/calibrate")
async def calibrate():
    state.request_calibration()
    return {"ok": True}


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
