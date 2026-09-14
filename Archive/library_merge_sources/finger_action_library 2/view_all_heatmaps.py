#!/usr/bin/env python3
"""Select and browse every reviewed finger and robot-arm action heatmap."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time
import tkinter as tk
from tkinter import ttk
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
import numpy as np


LIBRARY_DIR = Path(__file__).resolve().parent
SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ACTION_DISPLAY = {
    "front_touch": ("FRONT TOUCH", "#2563EB"),
    "back_touch": ("BACK TOUCH", "#EA580C"),
    "grasp": ("GRASP", "#16A34A"),
}
DISPLAY_FRAME_S = 0.05


@dataclass(frozen=True)
class Entry:
    dataset: str
    display_name: str
    path: Path
    kind: str
    action_id: str = ""
    action_type: str = ""
    confidence: str = ""


def column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference).group()
    result = 0
    for letter in letters:
        result = result * 26 + ord(letter) - 64
    return result - 1


def workbook_sheet_names(archive: ZipFile) -> list[str]:
    root = ET.fromstring(archive.read("xl/workbook.xml"))
    return [item.attrib["name"] for item in root.find(f"{SHEET_NS}sheets")]


def read_sheet(archive: ZipFile, sheet_name: str) -> list[list[str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
    namespaces = {"m": SHEET_NS[1:-1], "r": REL_NS}
    sheet = next(
        item
        for item in workbook.find("m:sheets", namespaces)
        if item.attrib["name"] == sheet_name
    )
    target = targets[sheet.attrib[f"{{{REL_NS}}}id"]]
    target = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
    root = ET.fromstring(archive.read(target))
    rows = []
    for row in root.findall(f".//{SHEET_NS}row"):
        cells = {}
        for cell in row.findall(f"{SHEET_NS}c"):
            number = cell.find(f"{SHEET_NS}v")
            inline = cell.find(f"{SHEET_NS}is/{SHEET_NS}t")
            cells[column_index(cell.attrib["r"])] = (
                inline.text or ""
                if inline is not None
                else number.text
                if number is not None
                else ""
            )
        rows.append([cells.get(index, "") for index in range(max(cells, default=-1) + 1)])
    return rows


def number(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def metadata_dict(rows: list[list[str]]) -> dict[str, str]:
    return {str(row[0]): str(row[1]) for row in rows if len(row) >= 2 and row[0]}


def discover_entries() -> dict[str, list[Entry]]:
    result: dict[str, list[Entry]] = {}

    thirty_dataset = "30-point recordings → sparse 6×6"
    thirty_path = (
        LIBRARY_DIR
        / "30point_recordings_18node_sparse"
        / "finger_actions_18node_6x6_sparse.xlsx"
    )
    thirty_entries = []
    with ZipFile(thirty_path) as archive:
        index_rows = read_sheet(archive, "Action Index")
    headers = index_rows[0]
    positions = {name: headers.index(name) for name in headers}
    for row in index_rows[1:]:
        action_id = row[positions["action_id"]]
        action_type = row[positions["action_type"]]
        confidence = row[positions["confidence"]]
        source = row[positions["source_file"]]
        display = f"{action_id} | {action_type} | {confidence} | {source}"
        thirty_entries.append(
            Entry(thirty_dataset, display, thirty_path, "30_combined", action_id, action_type, confidence)
        )
    result[thirty_dataset] = thirty_entries

    for dataset, relative, kind in (
        ("18-point → sparse 6×6", "18point_6x6_sparse/segments", "18_segment"),
        ("96-point → 12×8", "96point_12x8/segments", "96_segment"),
        ("Robot arm 132-node → 11×12", "robot_arm_132node/segments", "132_segment"),
    ):
        entries = []
        for path in sorted((LIBRARY_DIR / relative).glob("*.xlsx")):
            match = re.match(r"^([A-Z]\d+)_(front_touch|back_touch|grasp)_", path.name)
            action_id, action_type = match.groups() if match else ("", "unknown")
            entries.append(Entry(dataset, f"{action_id} | {action_type} | {path.name}", path, kind, action_id, action_type))
        result[dataset] = entries
    return result


def column_slot(logical_row: int, column: int) -> int:
    """Row in the dense 3x6 layout: the node's order inside its own column."""
    slot = (logical_row - column) % 6
    if slot > 2:
        raise ValueError(
            f"Row {logical_row + 1} is not part of column {column + 1}"
        )
    return slot


def numeric_matrix(rows: list[list[str]], start_col: int, count: int) -> np.ndarray:
    return np.array(
        [[number(row[index]) if index < len(row) else np.nan for index in range(start_col, start_col + count)] for row in rows],
        dtype=float,
    )


def load_30(entry: Entry) -> dict:
    sheet_name = {"front_touch": "Front Touch", "back_touch": "Back Touch", "grasp": "Grasp"}[entry.action_type]
    with ZipFile(entry.path) as archive:
        rows = read_sheet(archive, sheet_name)
        selected = [row for row in rows[1:] if row and row[0] == entry.action_id]
        index_rows = read_sheet(archive, "Action Index")
    header = rows[0]
    flat = numeric_matrix(selected, 9, 18)
    signal = np.full((len(flat), 3, 6), np.nan, dtype=float)
    labels = np.full((3, 6), "", dtype=object)
    for point_index, label in enumerate(header[9:27]):
        match = re.fullmatch(r"C(\d+)R(\d+)", label)
        if not match:
            raise ValueError(f"Invalid sparse McKibben label: {label}")
        column, row = (int(value) - 1 for value in match.groups())
        slot = column_slot(row, column)
        signal[:, slot, column] = flat[:, point_index]
        labels[slot, column] = label
    index_header = index_rows[0]
    index_row = next(row for row in index_rows[1:] if row[0] == entry.action_id)
    metadata = {key: index_row[index] for index, key in enumerate(index_header) if index < len(index_row)}
    return {
        "entry": entry,
        "raw": None,
        "baseline": None,
        "signal": signal,
        "labels": labels,
        "action_time": [number(row[7]) for row in selected],
        "source_time": [number(row[6]) for row in selected],
        "metadata": metadata,
    }


def load_segment(entry: Entry) -> dict:
    with ZipFile(entry.path) as archive:
        raw_rows = read_sheet(archive, "Raw Data")
        metadata = metadata_dict(read_sheet(archive, "Metadata"))
        if entry.kind == "18_segment":
            signal_rows = read_sheet(archive, "Signal")
            delta_rows = read_sheet(archive, "Delta")
            mapping_rows = read_sheet(archive, "Mapping")
            headers = raw_rows[0]
            mapping = [
                (int(float(row[0])) - 1, int(float(row[1])) - 1, row[2])
                for row in mapping_rows[1:]
                if len(row) >= 3 and row[0]
            ]

            def sparse(rows, fill_value):
                result = np.full((len(rows) - 1, 3, 6), fill_value, dtype=float)
                for column, logical_row, node in mapping:
                    source_index = headers.index(node)
                    result[:, column_slot(logical_row, column), column] = [
                        number(row[source_index]) for row in rows[1:]
                    ]
                return result

            raw_data = sparse(raw_rows, np.nan)
            delta_data = sparse(delta_rows, np.nan)
            baseline_data = raw_data - delta_data
            signal_data = sparse(signal_rows, np.nan)
            labels = np.full((3, 6), "", dtype=object)
            for column, logical_row, node in mapping:
                labels[column_slot(logical_row, column), column] = node
        elif entry.kind == "96_segment":
            raw_data = numeric_matrix(raw_rows[1:], 5, 96).reshape(-1, 12, 8)
            baseline_data = numeric_matrix(
                read_sheet(archive, "Baseline")[1:], 5, 96
            ).reshape(-1, 12, 8)
            signal_data = numeric_matrix(
                read_sheet(archive, "Signal Cleaned")[1:], 5, 96
            ).reshape(-1, 12, 8)
            labels = np.array(raw_rows[0][5:101], dtype=object).reshape(12, 8)
        else:
            raw_data = numeric_matrix(raw_rows[1:], 5, 132).reshape(-1, 12, 11).transpose(0, 2, 1)
            baseline_data = numeric_matrix(
                read_sheet(archive, "Baseline")[1:], 5, 132
            ).reshape(-1, 12, 11).transpose(0, 2, 1)
            signal_data = numeric_matrix(
                read_sheet(archive, "Signal Reconstructed")[1:], 5, 132
            ).reshape(-1, 12, 11).transpose(0, 2, 1)
            labels = np.array(raw_rows[0][5:137], dtype=object).reshape(12, 11).T
    return {
        "entry": entry,
        "raw": raw_data,
        "baseline": baseline_data,
        "signal": signal_data,
        "labels": labels,
        "action_time": [number(row[2]) for row in raw_rows[1:]],
        "source_time": [number(row[1]) for row in raw_rows[1:]],
        "metadata": metadata,
    }


def load_entry(entry: Entry) -> dict:
    data = load_30(entry) if entry.kind == "30_combined" else load_segment(entry)
    return resample_for_display(data)


def interpolate_array(values: np.ndarray, old_time: np.ndarray, new_time: np.ndarray) -> np.ndarray:
    flat = values.reshape(len(values), -1)
    result = np.full((len(new_time), flat.shape[1]), np.nan, dtype=float)
    for column in range(flat.shape[1]):
        valid = np.isfinite(flat[:, column])
        if np.count_nonzero(valid) == 1:
            result[:, column] = flat[valid, column][0]
        elif np.count_nonzero(valid) >= 2:
            result[:, column] = np.interp(
                new_time, old_time[valid], flat[valid, column]
            )
    return result.reshape((len(new_time), *values.shape[1:]))


def resample_for_display(data: dict) -> dict:
    """Interpolate slow clips to about 20 FPS without changing source files."""
    old_time = np.asarray(data["action_time"], dtype=float)
    data["original_frame_count"] = len(old_time)
    data["original_frame_s"] = (
        float(np.median(np.diff(old_time))) if len(old_time) > 1 else 0.0
    )
    data["display_interpolated"] = False
    if len(old_time) < 2:
        return data
    duration = float(old_time[-1] - old_time[0] + data["original_frame_s"])
    frame_count = max(2, int(round(duration / DISPLAY_FRAME_S)))
    new_time = old_time[0] + np.arange(frame_count, dtype=float) * DISPLAY_FRAME_S
    for key in ("raw", "baseline", "signal"):
        if data[key] is not None:
            data[key] = interpolate_array(data[key], old_time, new_time)
    source_start = float(data["source_time"][0])
    data["source_time"] = (source_start + new_time - old_time[0]).tolist()
    data["action_time"] = new_time.tolist()
    data["display_interpolated"] = bool(
        frame_count != len(old_time)
        or not np.isclose(data["original_frame_s"], DISPLAY_FRAME_S, atol=0.001)
    )
    data["display_resampled_20fps"] = True
    return data


class HeatmapBrowser:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Tactile action heatmap library")
        self.entries = discover_entries()
        self.current_entries: list[Entry] = []
        self.data = None
        self.frame = 0
        self.playing = False
        self.scale_updating = False
        self.play_origin = 0
        self.play_started = 0.0
        self.panels = []
        self.limits = (0.0, 1.0)
        self.background = None
        self.background_size = None
        self.values_visible = True

        controls = ttk.Frame(root, padding=8)
        controls.pack(fill=tk.X)
        ttk.Label(controls, text="Dataset:").grid(row=0, column=0, sticky="w")
        self.dataset = ttk.Combobox(controls, state="readonly", width=30, values=list(self.entries))
        self.dataset.grid(row=0, column=1, padx=(4, 12), sticky="ew")
        ttk.Label(controls, text="Action/file:").grid(row=0, column=2, sticky="w")
        self.action = ttk.Combobox(controls, state="readonly", width=82)
        self.action.grid(row=0, column=3, columnspan=5, padx=4, sticky="ew")
        controls.columnconfigure(3, weight=1)

        ttk.Button(controls, text="◀ Action", command=lambda: self.change_action(-1)).grid(row=1, column=0, pady=7)
        ttk.Button(controls, text="Action ▶", command=lambda: self.change_action(1)).grid(row=1, column=1, pady=7)
        ttk.Button(controls, text="◀ Frame", command=lambda: self.change_frame(-1)).grid(row=1, column=2, pady=7)
        self.play_button = ttk.Button(controls, text="Play", command=self.toggle_play)
        self.play_button.grid(row=1, column=3, pady=7, sticky="w")
        ttk.Button(controls, text="Frame ▶", command=lambda: self.change_frame(1)).grid(row=1, column=4, pady=7)
        self.frame_scale = tk.Scale(controls, from_=0, to=1, orient=tk.HORIZONTAL, showvalue=False, command=self.on_scale)
        self.frame_scale.grid(row=1, column=5, columnspan=2, padx=8, sticky="ew")
        controls.columnconfigure(5, weight=1)
        self.show_values_var = tk.BooleanVar(value=self.values_visible)
        ttk.Checkbutton(
            controls,
            text="Show values",
            variable=self.show_values_var,
            command=self.on_toggle_values,
        ).grid(row=1, column=8, padx=(10, 0), pady=7, sticky="w")
        self.action_type_box = tk.Label(
            controls,
            text="CURRENT ACTION\n—",
            font=("Arial", 15, "bold"),
            foreground="white",
            background="#64748B",
            relief=tk.GROOVE,
            borderwidth=3,
            padx=16,
            pady=5,
            width=16,
        )
        self.action_type_box.grid(row=1, column=7, padx=(10, 0), pady=3, sticky="e")
        self.status = ttk.Label(controls, text="")
        self.status.grid(row=2, column=0, columnspan=8, sticky="ew")

        self.figure = Figure(figsize=(15, 7.7), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.dataset.bind("<<ComboboxSelected>>", self.on_dataset)
        self.action.bind("<<ComboboxSelected>>", self.on_action)
        root.bind("<Left>", lambda _event: self.change_frame(-1))
        root.bind("<Right>", lambda _event: self.change_frame(1))
        root.bind("<Prior>", lambda _event: self.change_action(-1))
        root.bind("<Next>", lambda _event: self.change_action(1))
        root.bind("<space>", lambda _event: self.toggle_play())
        self.dataset.current(0)
        self.on_dataset()
        self.root.after(50, self.timer_tick)

    def on_dataset(self, _event=None):
        self.current_entries = self.entries[self.dataset.get()]
        self.action["values"] = [entry.display_name for entry in self.current_entries]
        self.action.current(0)
        self.on_action()

    def on_action(self, _event=None):
        if not self.current_entries:
            return
        self.playing = False
        self.play_button.configure(text="Play")
        self.frame = 0
        self.data = load_entry(self.current_entries[self.action.current()])
        self.frame_scale.configure(to=max(0, len(self.data["signal"]) - 1))
        action_type = self.data["metadata"].get(
            "action_type", self.data["entry"].action_type
        )
        english_name, color = ACTION_DISPLAY.get(action_type, (action_type.upper() if action_type else "UNKNOWN", "#64748B"))
        self.action_type_box.configure(
            text=f"CURRENT ACTION\n{english_name}",
            background=color,
        )
        self.build_panels()
        self.redraw()

    def change_action(self, step: int):
        if not self.current_entries:
            return
        self.action.current((self.action.current() + step) % len(self.current_entries))
        self.on_action()

    def change_frame(self, step: int):
        if self.data is None:
            return
        self.frame = (self.frame + step) % len(self.data["signal"])
        self.anchor_playback()
        self.repaint()

    def on_scale(self, value):
        if self.scale_updating or self.data is None:
            return
        self.frame = min(int(round(float(value))), len(self.data["signal"]) - 1)
        self.anchor_playback()
        self.repaint(update_scale=False)

    def repaint(self, update_scale=True):
        """Route to whichever draw path matches the image/grid animated flags.

        redraw() does a normal full draw, which matplotlib skips animated
        artists during; blit_frame() is the only path that still shows them
        while a clip is playing. Using redraw() unconditionally here made the
        grid lines and cell values vanish whenever a frame button or the
        slider was used mid-playback.
        """
        if self.playing:
            self.blit_frame(update_scale)
        else:
            self.redraw(update_scale)

    def anchor_playback(self):
        """Restart the playback clock from the frame currently on screen."""
        self.play_origin = self.frame
        self.play_started = time.monotonic()

    def toggle_play(self):
        self.playing = not self.playing
        self.play_button.configure(text="Pause" if self.playing else "Play")
        self.sync_animated()
        self.background = None
        self.anchor_playback()
        if self.playing:
            self.blit_frame()
        else:
            self.redraw()

    def sync_animated(self):
        """Match each artist's animated flag to how it will next be drawn.

        A paused frame uses a normal draw(), which matplotlib skips
        animated=True artists during; a playing frame uses blit_frame(),
        which excludes animated artists from the cached background and
        repaints them itself every tick. Values only need this treatment
        while they are actually shown -- when hidden they are not drawn
        either way, so leaving their animated flag alone avoids pointless
        work on all of them every time playback starts or stops.
        """
        for _key, _signal_panel, image, grid, texts in self.panels:
            image.set_animated(self.playing)
            grid.set_animated(self.playing)
            if self.values_visible:
                for text_row in texts:
                    for text_item in text_row:
                        text_item.set_animated(self.playing)

    def on_toggle_values(self):
        self.values_visible = self.show_values_var.get()
        for _key, _signal_panel, _image, _grid, texts in self.panels:
            for text_row in texts:
                for text_item in text_row:
                    text_item.set_visible(self.values_visible)
                    # Animated only matters while visible; drop it when
                    # hiding so a later un-hide starts from a clean state.
                    text_item.set_animated(self.values_visible and self.playing)
        self.background = None
        self.repaint()

    def timer_tick(self):
        # Follow the wall clock rather than counting ticks: a heavy layout such
        # as the 12x8 grid then plays at its real speed and drops frames it
        # cannot draw in time, instead of stretching the clip out.
        if self.playing and self.data is not None:
            total = len(self.data["signal"])
            elapsed = time.monotonic() - self.play_started
            target = (self.play_origin + int(elapsed / DISPLAY_FRAME_S)) % total
            if target != self.frame:
                self.frame = target
                self.blit_frame()
        self.root.after(16, self.timer_tick)

    def value_range(self):
        """Voltage limits for the whole clip.

        A per-frame percentile made the colour scale jump around during
        playback and left frames incomparable; one range per action fixes the
        scale and lets the background be cached for blitting.
        """
        data = self.data
        if data["raw"] is None:
            return 0.0, 1.0
        finite = np.concatenate(
            [
                data["raw"][np.isfinite(data["raw"])],
                data["baseline"][np.isfinite(data["baseline"])],
            ]
        )
        if not finite.size:
            return 0.0, 1.0
        low, high = np.percentile(finite, (3, 97))
        if high - low < 0.15:
            low, high = low - 0.075, high + 0.075
        return max(0.0, float(low)), float(high)

    def build_panels(self):
        """Lay out axes, images, cell labels and colorbars once per action.

        Rebuilding these every frame kept the 12x8 layout near 2 FPS, far below
        the 20 FPS the playback timer asks for.
        """
        data = self.data
        panels = []
        if data["raw"] is not None:
            panels.append(("Raw Data", "raw", "turbo_r"))
            panels.append(("Dynamic Baseline", "baseline", "turbo_r"))
        panels.append(("Signal Cleaned", "signal", "turbo"))
        rows, cols = data["signal"].shape[1:]
        low, high = self.value_range()

        self.figure.clear()
        self.background = None
        axes = self.figure.subplots(1, len(panels), squeeze=False)[0]
        self.panels = []
        font_size = 4.5 if rows * cols >= 90 else 7.0
        # Own the cell borders instead of using axis.grid: as a single artist
        # they can be re-drawn over a blitted background.
        segments = [
            [(x, -0.5), (x, rows - 0.5)] for x in np.arange(-0.5, cols, 1)
        ] + [[(-0.5, y), (cols - 0.5, y)] for y in np.arange(-0.5, rows, 1)]
        for axis, (title, key, cmap) in zip(axes, panels):
            signal_panel = key == "signal"
            image = axis.imshow(
                np.full((rows, cols), np.nan),
                cmap=cmap,
                vmin=0.0 if signal_panel else low,
                vmax=1.0 if signal_panel else high,
                aspect="auto",
            )
            grid = LineCollection(
                segments, colors="white", linewidths=0.4, alpha=0.45, zorder=2
            )
            axis.add_collection(grid)
            axis.set_title(title)
            axis.set_xticks(range(cols), labels=range(1, cols + 1))
            axis.set_yticks(range(rows), labels=range(1, rows + 1))
            axis.set_xlabel("McKibben column" if rows == 3 else "Heatmap column")
            axis.set_ylabel("Node in column" if rows == 3 else "Heatmap row")
            texts = [
                [
                    axis.text(
                        col, row, "", ha="center", va="center", fontsize=font_size,
                        zorder=3, visible=self.values_visible,
                    )
                    for col in range(cols)
                ]
                for row in range(rows)
            ]
            self.figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
            self.panels.append((key, signal_panel, image, grid, texts))

        metadata = data["metadata"]
        self.figure.suptitle(
            f"{data['entry'].dataset}   {metadata.get('action_id', data['entry'].action_id)}   "
            f"{metadata.get('action_type', data['entry'].action_type)}   "
            f"confidence={metadata.get('confidence', data['entry'].confidence)}\n{data['entry'].path.name}",
            fontsize=12,
        )
        self.figure.tight_layout(rect=(0, 0, 1, 0.92))

    def animated_artists(self):
        for _key, _signal_panel, image, grid, texts in self.panels:
            yield image
            yield grid
            if self.values_visible:
                for text_row in texts:
                    yield from text_row

    def set_frame_data(self):
        data = self.data
        frame = self.frame
        labels = data["labels"]
        low, high = self.limits
        for _key, signal_panel, image, _grid, texts in self.panels:
            matrix = data[_key][frame]
            image.set_data(matrix)
            if not self.values_visible:
                continue
            threshold = 0.5 if signal_panel else (low + high) / 2
            for row, text_row in enumerate(texts):
                for col, text_item in enumerate(text_row):
                    value = matrix[row, col]
                    label = labels[row, col]
                    if not np.isfinite(value):
                        text_item.set_text(f"{label}\n—")
                    elif signal_panel:
                        text_item.set_text(f"{label}\n{value * 100:.0f}%")
                    else:
                        text_item.set_text(f"{label}\n{value:.2f}")
                    text_item.set_color(
                        "black"
                        if np.isfinite(value) and value >= threshold
                        else "white"
                    )

    def update_status(self, update_scale=True):
        data = self.data
        frame = self.frame
        interpolation_note = (
            f"    fixed 20 FPS display from {data['original_frame_count']} measured frames "
            f"(original Δt≈{data['original_frame_s']:.3f}s)"
        )
        self.status.configure(
            text=(
                f"action {self.action.current() + 1}/{len(self.current_entries)}    "
                f"display frame {frame + 1}/{len(data['signal'])}    "
                f"action t={data['action_time'][frame]:.3f}s    source t={data['source_time'][frame]:.3f}s"
                f"{interpolation_note}"
            )
        )
        if update_scale:
            self.scale_updating = True
            self.frame_scale.set(frame)
            self.scale_updating = False

    def redraw(self, update_scale=True):
        """Full repaint, used whenever playback is not running."""
        self.limits = self.value_range()
        self.set_frame_data()
        self.update_status(update_scale)
        self.canvas.draw_idle()

    def blit_frame(self, update_scale=True):
        """Repaint only the heatmaps over a cached background."""
        canvas = self.canvas
        size = canvas.get_width_height()
        if self.background is None or size != self.background_size:
            canvas.draw()
            self.background = canvas.copy_from_bbox(self.figure.bbox)
            self.background_size = size
        self.set_frame_data()
        canvas.restore_region(self.background)
        for artist in self.animated_artists():
            artist.axes.draw_artist(artist)
        canvas.blit(self.figure.bbox)
        self.update_status(update_scale)
def main() -> int:
    root = tk.Tk()
    root.geometry("1600x930")
    HeatmapBrowser(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
