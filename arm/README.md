# Robot-arm current-display CSV

This folder contains the current viewer's `Contact Voltage` playback data for
RB004, RB003, and RB001, in that order. Values are ADC voltage in volts (V),
not normalized percentages.

## Files

- `RB004_axial_column_contact_voltage_display.csv`
- `RB003_pinch_end_contact_voltage_display.csv`
- `RB001_palm_grab_contact_voltage_display.csv`
- `RB004_RB003_RB001_contact_voltage_display_combined.csv`

The combined file concatenates the same rows in the order RB004, RB003, RB001.

## Columns

- `display_frame_1based`: displayed frame number, starting at 1 for each action.
- `display_time_s`: elapsed playback time in seconds.
- `action_id`, `action_type`: action identification.
- `active_node_count`: number of displayed contact nodes in that frame.
- `N001` through `N132`: displayed contact voltage in volts.

An empty node cell means that the current viewer draws that node black in the
selected frame: the restored signal is not above 0.005 V, its fixed baseline is
below 1.50 V, or its voltage is invalid. Empty cells are not zero volts.

## Playback equivalence

- Frame interval: 0.05 s (20 FPS), interpolated exactly as the current viewer.
- Pressing lowers voltage; lower non-empty voltage indicates stronger contact.
- RB004 uses the current viewer's cumulative minimum raw voltage at active nodes,
  which preserves the completed axial column during playback.
- RB003 is shifted upward by one crossing level in the displayed coordinate system.
- RB004 is vertically flipped in the displayed coordinate system.
- Node columns are already `N001`–`N132`; no wiring-map conversion is required.

Generated from the three direct-view workbooks in
`tactile_actions_raw_restored_direct_view/robot_arm_11x12/segments/` by
`ESP32 reader/tools/grip/export_current_robot_arm_display_csv.py`.
