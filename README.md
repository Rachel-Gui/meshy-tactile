> 当前数据已于 2026-09-13 更新为 9 个 Direct 动作，详见 [CURRENT_DATASET.md](CURRENT_DATASET.md)。旧数据已归档；下文历史数据数量以该说明为准。

# Tactile 工作目录

## 当前项目

| 路径 | 用途 |
|---|---|
| `web/` | 3D 网页与本地 FastAPI 服务，启动方式见 [web/README.md](web/README.md) |
| `finger/recordings/` | 原始采集 CSV/XLSX，原始采集存档，当前网页播放使用动作库 |
| `finger/` 下的 `.ino` | 手指传感器固件；与根目录固件内容不同，分别保留 |
| `finger/action_library/` | Finger：28 个完整动作，18 节点 |
| `human_arm/` | Human arm：29 个 96 点动作、原始录制和热力图 |
| `robot_arm/` | Robot arm：3 个 132 节点动作、32 mm 模型说明及论文图 |
| `uploaded_playback_data/` | 后端上传目录（此前上传已归档；当前前端上传仅保留在标签页） |
| `icra2026_tactile_sleeve/` | 论文源文件与插图 |
| `models/tactile/` | Arm/Ring 的 Rhino 与 Grasshopper 模型：`1.3dm`、`1.gh`、`ring.gh` |
| `models/robot_arm/` | 机器人手臂的 Rhino、STEP 和 3MF 文件 |
| `models/experiments/` | 实验 CAD 文件：`cello test.dxf` |
| `firmware/` | ESP32 A2 采集固件 |
| `tools/viewers/` | Python 采集/实时查看主程序，以及 96 点和 12×12 布局入口 |
| `Archive/` | 明确被替代的旧数据、旧模型、历史脚本及验证记录 |

播放整理后的动作：

```bash
python3 tools/viewers/view_all_heatmaps.py
```

## 整理规则（2026-09-11）

- 原始录制集中保存，不按日期删除唯一数据。
- 删除副本前逐字节 SHA-256 核对，保留路径记录在 Archive 的清单中。
- `web/dist/` 是本地服务使用的构建结果，其中动作库 JSON 和静态资源副本属于必要部署产物。
- `.git`、环境配置与已有未提交修改保留；此次未提交 Git commit。
- 归档说明见 [Archive/README.md](Archive/README.md)。

## 模型和采集工具（2026-09-12 整理）

在 Rhino/Grasshopper 中打开 `models/tactile/1.gh`（Arm）或
`models/tactile/ring.gh`（Ring）。网页导出与验证脚本已使用新路径。

从项目根目录启动 96 点实时查看器：

```bash
python3 tools/viewers/tactile_cyclic_96points_viewer.py
```

12×12 入口为 `tools/viewers/tactile_mapped_12x12_viewer.py`；两个入口依赖
同目录中的 `tactile_full_scan_viewer.py`。固件位于
`firmware/downloaded_tactilesensor_a2.ino`。

此次只移动分类，没有删除文件或修改模型内容。11 个文件的新旧路径及
内容校验值见 `Archive/organization_manifest_2026-09-12.json`。

## 动作库合并（2026-09-12）

两个动作库及历史动作存档已按 human_arm、robot_arm、finger 合并。完整动作共 60 个，精选清单共 12 个；不同裁剪版本保留于各数据集 archive/。94 个逐字节相同的 XLSX 副本已合并。移动时的完整校验与路径映射见 `Archive/data_merge_2026-09-12.json`。旧说明和播放器版本保留于 `Archive/library_merge_sources/`。网页现支持全部 60 个动作，包括 Robot arm 的 132 节点数据。

Robot arm 新模型：`models/robot_arm/robot_arm_132_32mm.gh` / `.3dm`，长 250 mm、两端直径 32 mm。前端入口：http://127.0.0.1:8001/?model=robot 。
