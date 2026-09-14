# 历史归档

2026-09-11 整理。归档文件保留原始内容，不作为当前数据入口。

| 目录 | 内容与原因 |
|---|---|
| `legacy_action_data/` | 旧仅按压阶段片段和索引、错误三行坐标映射；被当前动作库替代 |
| `model_backups/` | `1.before-width4.gh`、`ring.before-fix.gh`，修复前模型 |
| `legacy_scripts/` | `ring_model.py` 简化圆柱模型；`sync_strip_widths.py` 已完成的宽度迁移；`verify_ring.py` 使用旧 Windows 绝对路径的历史验证脚本 |
| `validation_reports/` | 修复说明、验证报告、模型预览截图 |

旧脚本和历史文档中的相对路径按原位置保留。不要直接在归档目录执行迁移脚本；如需复用，先检查输入和输出路径。当前导出与验证工具仍在 web 中。

`cleanup_manifest_2026-09-11.json` 记录移动文件的原/新路径、SHA-256，以及删除的 9 份重复 CSV 的保留位置。重复 CSV 共减少 39,167,578 字节（约 37.35 MiB）。没有删除唯一的原始采集数据。

## 当前数据整理（2026-09-13）

`data_before_direct_2026-09-13/` 保存前一版 60 动作。`data_consolidation_2026-09-13/` 集中保存 new 导入副本、旧原始录制、旧图及旧说明；moves.json 记录每个移动文件及 SHA-256。当前唯一入口见 [CURRENT_DATASET.md](../CURRENT_DATASET.md)。
