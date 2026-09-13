# 当前数据：2026-09-13 Direct Action Dataset

当前使用 new 导入的 9 个动作，每类正面触摸、背面触摸、抓握各一个。

- Finger：`finger/action_library/18point_6x6_sparse/segments`，E015 / E008 / E007，18 点。
- Human arm：`human_arm/action_library/96point_12x8/segments`，E025 / E022 / E009，96 点。
- Robot arm：`robot_arm/action_library/robot_arm_132node/segments`，R003 / R007 / R004，132 点。

总索引 `action_index.xlsx`。主信号为 `Signal Combined`；前端导出程序 `python3 web/tools/export_action_library.py`，随后 `npm --prefix web run build`。桌面查看器运行 `python3 tools/viewers/view_all_heatmaps.py`。

旧动作库、旧前端 JSON 和旧导出/查看程序保存在 `Archive/data_before_direct_2026-09-13`。`new` 保留为导入来源。此前生成的 60 张图片基于旧数据，不代表当前 9 条数据。
