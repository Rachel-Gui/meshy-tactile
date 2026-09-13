#!/usr/bin/env python3
"""Browse mapping-free finger, arm, and robot-arm action workbooks."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import time
import tkinter as tk
from tkinter import messagebox, ttk
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np


ROOT = Path(__file__).resolve().parent
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DISPLAY_FRAME_S = 0.05
LAYERS = (
    "Signal Combined", "Signal Original", "Signal Raw Restored",
    "Pressure Drop V", "Raw Data", "Baseline Fixed",
)
CIRCUITS = (
    ("Finger · 18 nodes · 3×6", "finger_3x6"),
    ("Arm · 96 nodes · 12×8", "arm_12x8"),
    ("Robot arm · 132 nodes · 11×12", "robot_arm_11x12"),
)
ACTION_STYLE = {
    "front_touch": ("FRONT TOUCH", "#2563EB"),
    "back_touch": ("BACK TOUCH", "#EA580C"),
    "grab": ("GRAB", "#16A34A"),
}
ACTION_ORDER = {"front_touch": 0, "back_touch": 1, "grab": 2}


def column_index(reference: str) -> int:
    match = re.match(r"[A-Za-z]+", reference)
    value = 0
    for character in (match.group(0).upper() if match else "A"):
        value = value * 26 + ord(character) - 64
    return value - 1


def cell_value(cell: ET.Element, shared: list[str]):
    kind = cell.attrib.get("t", "")
    if kind == "inlineStr":
        return "".join(item.text or "" for item in cell.findall(f".//{{{SHEET_NS}}}t"))
    value = cell.find(f"{{{SHEET_NS}}}v")
    if value is None or value.text is None:
        return ""
    if kind == "s":
        return shared[int(value.text)]
    try:
        number = float(value.text)
        return int(number) if number.is_integer() else number
    except ValueError:
        return value.text


def read_workbook(path: Path) -> dict[str, list[list[object]]]:
    with ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(text.text or "" for text in item.findall(f".//{{{SHEET_NS}}}t"))
                for item in root.findall(f"{{{SHEET_NS}}}si")
            ]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relations.findall(f"{{{PKG_REL_NS}}}Relationship")
        }
        tables = {}
        for sheet in workbook.findall(f".//{{{SHEET_NS}}}sheet"):
            target = targets[sheet.attrib[f"{{{REL_NS}}}id"]]
            sheet_path = target.lstrip("/") if target.startswith("/") else str(PurePosixPath("xl") / target)
            root = ET.fromstring(archive.read(sheet_path))
            rows = []
            for row in root.findall(f".//{{{SHEET_NS}}}row"):
                values = {
                    column_index(cell.attrib.get("r", "A1")): cell_value(cell, shared)
                    for cell in row.findall(f"{{{SHEET_NS}}}c")
                }
                rows.append([values.get(index, "") for index in range(max(values, default=-1) + 1)])
            tables[sheet.attrib["name"]] = rows
        return tables


def as_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def interpolate_layers(layers: dict[str, np.ndarray], old_time: np.ndarray):
    """Match the old viewer: interpolate slow scans to a smooth 20 FPS view."""
    if len(old_time) < 2 or not np.all(np.isfinite(old_time)):
        return layers, old_time, False
    old_time = old_time - old_time[0]
    if old_time[-1] <= DISPLAY_FRAME_S * 1.5:
        return layers, old_time, False
    new_time = np.arange(0.0, old_time[-1] + DISPLAY_FRAME_S * 0.5, DISPLAY_FRAME_S)
    result = {}
    for name, values in layers.items():
        flat = values.reshape(len(values), -1)
        restored = np.empty((len(new_time), flat.shape[1]), dtype=float)
        for column in range(flat.shape[1]):
            restored[:, column] = np.interp(new_time, old_time, flat[:, column])
        result[name] = restored.reshape(len(new_time), *values.shape[1:])
    return result, new_time, True


def load_action(path: Path) -> dict:
    tables = read_workbook(path)
    info = {str(row[0]): row[1] for row in tables["Info"] if len(row) >= 2}
    rows = int(float(info["heatmap_rows"]))
    columns = int(float(info["heatmap_columns"]))
    count = rows * columns
    layers = {}
    for name in LAYERS:
        layers[name] = np.array(
            [[as_float(value) for value in row[5:5 + count]] for row in tables[name][1:]],
            dtype=float,
        ).reshape(-1, rows, columns)
    raw_rows = tables["Raw Data"]
    elapsed = np.array([as_float(row[2]) for row in raw_rows[1:]], dtype=float)
    measured_frames = len(elapsed)
    layers, elapsed, interpolated = interpolate_layers(layers, elapsed)
    strength = np.nansum(layers["Signal Combined"], axis=(1, 2))
    return {
        "path": path, "info": info, "rows": rows, "columns": columns,
        "layers": layers, "elapsed": elapsed,
        "peak_frame": int(np.nanargmax(strength)) if len(strength) else 0,
        "measured_frames": measured_frames,
        "interpolated": interpolated,
    }


def action_label(path: Path) -> str:
    match = re.match(r"([A-Z]\d+)_(front_touch|back_touch|grab)_", path.name)
    if not match:
        return path.name
    action_id, action_type = match.groups()
    return f"{action_id}  |  {action_type.replace('_', ' ')}"


def action_sort_key(path: Path):
    match = re.match(r"[A-Z]\d+_(front_touch|back_touch|grab)_", path.name)
    return (ACTION_ORDER.get(match.group(1), 99) if match else 99, path.name)


class ActionBrowser:
    def __init__(self, root: tk.Tk, initial: Path | None = None):
        self.root = root
        self.files_by_circuit = {
            label: sorted(
                (ROOT / directory / "segments").glob("*_direct.xlsx"),
                key=action_sort_key,
            )
            for label, directory in CIRCUITS
        }
        self.files: list[Path] = []
        self.data = None
        self.frame = 0
        self.playing = False
        self.first_play = True
        self.scale_updating = False
        self.play_started = 0.0
        self.play_origin = 0
        self.colorbar = None
        self.values_visible = True

        root.title("Tactile Actions · Finger / Arm / Robot Arm")
        root.geometry("1280x900")
        controls = ttk.Frame(root, padding=8)
        controls.pack(fill="x")
        ttk.Label(controls, text="Circuit").grid(row=0, column=0, sticky="w")
        self.circuit_box = ttk.Combobox(
            controls, state="readonly", width=34,
            values=[label for label, _directory in CIRCUITS],
        )
        self.circuit_box.grid(row=0, column=1, padx=(5, 14), sticky="ew")
        ttk.Label(controls, text="Action").grid(row=0, column=2, sticky="w")
        self.action_box = ttk.Combobox(controls, state="readonly", width=42)
        self.action_box.grid(row=0, column=3, padx=5, sticky="ew")
        ttk.Label(controls, text="Layer").grid(row=0, column=4, padx=(14, 0))
        self.layer_box = ttk.Combobox(controls, state="readonly", values=LAYERS, width=23)
        self.layer_box.grid(row=0, column=5, padx=5)
        self.layer_box.current(0)
        controls.columnconfigure(3, weight=1)

        ttk.Button(controls, text="◀ Action", command=lambda: self.change_action(-1)).grid(row=1, column=0, pady=7)
        ttk.Button(controls, text="Action ▶", command=lambda: self.change_action(1)).grid(row=1, column=1, pady=7)
        ttk.Button(controls, text="◀ Frame", command=lambda: self.change_frame(-1)).grid(row=1, column=2, pady=7)
        self.play_button = ttk.Button(controls, text="Play from baseline", command=self.toggle_play)
        self.play_button.grid(row=1, column=3, pady=7, sticky="w")
        ttk.Button(controls, text="Frame ▶", command=lambda: self.change_frame(1)).grid(row=1, column=3, padx=(150, 0), pady=7, sticky="w")
        ttk.Button(controls, text="Peak frame", command=self.show_peak).grid(row=1, column=4, pady=7)
        self.show_values_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Show values", variable=self.show_values_var, command=self.toggle_values).grid(row=1, column=5)

        self.action_badge = tk.Label(
            controls, text="CURRENT ACTION\n—", font=("Arial", 14, "bold"),
            foreground="white", background="#64748B", relief=tk.GROOVE,
            borderwidth=3, width=17, pady=4,
        )
        self.action_badge.grid(row=2, column=0, columnspan=2, pady=(2, 4), sticky="w")
        self.status = ttk.Label(controls, text="")
        self.status.grid(row=2, column=2, columnspan=4, padx=8, sticky="w")

        self.figure = Figure(figsize=(11.5, 7.0), dpi=100)
        self.axis = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=root)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8)
        self.frame_scale = tk.Scale(
            root, from_=0, to=1, orient=tk.HORIZONTAL,
            showvalue=False, command=self.on_scale,
        )
        self.frame_scale.pack(fill="x", padx=10, pady=(0, 8))

        self.circuit_box.bind("<<ComboboxSelected>>", self.on_circuit)
        self.action_box.bind("<<ComboboxSelected>>", self.on_action)
        self.layer_box.bind("<<ComboboxSelected>>", lambda _event: self.draw())
        root.bind("<Left>", lambda _event: self.change_frame(-1))
        root.bind("<Right>", lambda _event: self.change_frame(1))
        root.bind("<Prior>", lambda _event: self.change_action(-1))
        root.bind("<Next>", lambda _event: self.change_action(1))
        root.bind("<space>", lambda _event: self.toggle_play())

        initial_circuit = 0
        initial_action = 0
        if initial is not None:
            for circuit_index, (label, _directory) in enumerate(CIRCUITS):
                candidates = self.files_by_circuit[label]
                if initial in candidates:
                    initial_circuit = circuit_index
                    initial_action = candidates.index(initial)
                    break
        self.circuit_box.current(initial_circuit)
        self.on_circuit(action_index=initial_action)
        self.root.after(30, self.timer_tick)

    def on_circuit(self, _event=None, action_index=0):
        self.stop_playback()
        self.files = self.files_by_circuit[self.circuit_box.get()]
        self.action_box.configure(values=[action_label(path) for path in self.files])
        if not self.files:
            self.action_box.set("")
            return
        self.action_box.current(min(action_index, len(self.files) - 1))
        self.on_action()

    def on_action(self, _event=None):
        if not self.files or self.action_box.current() < 0:
            return
        self.stop_playback()
        try:
            self.data = load_action(self.files[self.action_box.current()])
        except Exception as error:
            messagebox.showerror("Cannot open action", str(error))
            return
        self.frame = self.data["peak_frame"]
        self.first_play = True
        self.frame_scale.configure(to=max(0, len(self.data["elapsed"]) - 1))
        self.update_scale()
        action_type = str(self.data["info"]["action_type"])
        label, color = ACTION_STYLE.get(action_type, (action_type.upper(), "#64748B"))
        self.action_badge.configure(text=f"CURRENT ACTION\n{label}", background=color)
        self.draw()

    def stop_playback(self):
        self.playing = False
        if hasattr(self, "play_button"):
            self.play_button.configure(text="Play from baseline")

    def change_action(self, step: int):
        if not self.files:
            return
        self.action_box.current((self.action_box.current() + step) % len(self.files))
        self.on_action()

    def change_frame(self, step: int):
        if self.data is None:
            return
        self.stop_playback()
        self.first_play = False
        self.frame = (self.frame + step) % len(self.data["elapsed"])
        self.update_scale()
        self.draw()

    def show_peak(self):
        if self.data is None:
            return
        self.stop_playback()
        self.frame = self.data["peak_frame"]
        self.update_scale()
        self.draw()

    def on_scale(self, value):
        if self.scale_updating or self.data is None:
            return
        self.stop_playback()
        self.first_play = False
        self.frame = min(int(round(float(value))), len(self.data["elapsed"]) - 1)
        self.draw()

    def update_scale(self):
        self.scale_updating = True
        self.frame_scale.set(self.frame)
        self.scale_updating = False

    def toggle_values(self):
        self.values_visible = self.show_values_var.get()
        self.draw()

    def toggle_play(self):
        if self.data is None:
            return
        self.playing = not self.playing
        if self.playing:
            if self.first_play:
                self.frame = 0
                self.first_play = False
                self.update_scale()
            self.play_origin = self.frame
            self.play_started = time.monotonic()
            self.play_button.configure(text="Pause")
            self.draw()
        else:
            self.play_button.configure(text="Play")

    def timer_tick(self):
        if self.playing and self.data is not None:
            total = len(self.data["elapsed"])
            target = self.play_origin + int((time.monotonic() - self.play_started) / DISPLAY_FRAME_S)
            if target >= total:
                self.stop_playback()
                self.frame = total - 1
                self.update_scale()
                self.draw()
            elif target != self.frame:
                self.frame = target
                self.update_scale()
                self.draw()
        self.root.after(20, self.timer_tick)

    def limits(self, layer: str, values: np.ndarray):
        if layer.startswith("Signal "):
            return 0.0, 1.0, "inferno"
        finite = values[np.isfinite(values)]
        if not len(finite):
            return 0.0, 1.0, "viridis"
        if layer == "Pressure Drop V":
            return 0.0, max(0.05, float(np.nanpercentile(finite, 99))), "inferno"
        low, high = np.nanpercentile(finite, (1, 99))
        return float(low), float(high if high > low else low + 1e-6), "viridis"

    def draw(self):
        if self.data is None:
            return
        layer = self.layer_box.get()
        values = self.data["layers"][layer]
        matrix = values[self.frame]
        vmin, vmax, cmap_name = self.limits(layer, values)
        if self.colorbar is not None:
            self.colorbar.remove()
            self.colorbar = None
        self.axis.clear()
        image = self.axis.imshow(matrix, vmin=vmin, vmax=vmax, cmap=cmap_name, aspect="equal", origin="upper")
        self.colorbar = self.figure.colorbar(image, ax=self.axis, fraction=0.046, pad=0.04)
        rows, columns = matrix.shape
        self.axis.set_xticks(range(columns), range(1, columns + 1))
        self.axis.set_yticks(range(rows), range(1, rows + 1))
        self.axis.set_xticks(np.arange(-0.5, columns, 1), minor=True)
        self.axis.set_yticks(np.arange(-0.5, rows, 1), minor=True)
        self.axis.grid(which="minor", color="white", linewidth=1.0, alpha=0.7)
        self.axis.tick_params(which="minor", bottom=False, left=False)
        self.axis.set_xlabel("Column")
        self.axis.set_ylabel("Row")
        if self.values_visible:
            font_size = 10 if matrix.size <= 24 else 6 if matrix.size <= 100 else 5
            for row in range(rows):
                for column in range(columns):
                    value = matrix[row, column]
                    text = f"{value * 100:.0f}%" if layer.startswith("Signal ") else f"{value:.2f}"
                    threshold = 0.52 if layer.startswith("Signal ") else (vmin + vmax) / 2
                    self.axis.text(column, row, text, ha="center", va="center", fontsize=font_size, color="black" if value >= threshold else "white")
        info = self.data["info"]
        self.axis.set_title(
            f"{self.circuit_box.get()} · {info['action_id']} · {str(info['action_type']).replace('_', ' ')}\n{layer}",
            fontsize=13,
        )
        elapsed = self.data["elapsed"][self.frame]
        peak_note = " · PEAK" if self.frame == self.data["peak_frame"] else ""
        interpolation_note = (
            f" · smoothed from {self.data['measured_frames']} measured frames"
            if self.data["interpolated"] else ""
        )
        self.status.configure(
            text=f"Action {self.action_box.current() + 1}/{len(self.files)} · Frame {self.frame + 1}/{len(values)} · t={elapsed:.3f}s{peak_note}{interpolation_note}"
        )
        self.canvas.draw_idle()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", nargs="?", type=Path)
    args = parser.parse_args()
    initial = args.xlsx.resolve() if args.xlsx else None
    root = tk.Tk()
    ActionBrowser(root, initial)
    root.mainloop()


if __name__ == "__main__":
    main()
