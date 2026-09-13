# Finger / Arm / Robot Arm — Direct Action Dataset

本目录只包含当前要求的三个电路。每个电路各保留一个清楚的 `front_touch`、`back_touch` 和 `grab`，共 9 个动作。

| Circuit | Direct heatmap | Front touch | Back touch | Grab |
|---|---:|---|---|---|
| Finger | 3×6 / 18 nodes | E015 | E008 | E007 |
| Arm | 12×8 / 96 nodes | E025 | E022 | E009 |
| Robot arm | 11×12 / 132 nodes | R003 | R007 | R004 |

旧的 30-point 文件是 Finger 电路的早期采集来源，不再作为第四个电路显示。旧电路和未选动作的来源文件没有删除或修改，只是不放进这个分享目录。

## Viewer

在本目录运行：

```bash
python3 view_direct_actions.py
```

Viewer 按旧程序的结构重新实现：

- `Circuit` 下拉框切换 Finger / Arm / Robot arm。
- `Action` 下拉框切换 front touch / back touch / grab。
- `◀ Action`、`Action ▶` 前后切换动作。
- `◀ Frame`、`Frame ▶` 或键盘左右键切换 frame。
- 打开动作时先显示峰值帧，便于立即检查空间图样。
- `Play from baseline` 总是从第一个 baseline frame 开始播放，到最后一个接近 baseline 的 frame 自动停止。
- 慢速扫描只在 viewer 内插值到约 20 FPS；Excel 中的原始测量 frame 不变。
- `Show values` 显示每个格子的 Signal 百分比或电压。

## Baseline-to-baseline clips

重新挑选动作时要求 Signal 首帧和尾帧接近 0，同时保留清楚的中间峰值。当前 9 个动作的 `Signal Combined` 首帧均为 0；尾帧为 0，或仅保留相对峰值很小的原始残余。

Robot arm 的原 recorder Signal 为空，因此使用 Raw Data 两端线性 baseline 重恢复中间接触；它的首尾恢复 Signal 均为 0。Finger 和 Arm 同时保留以前程序使用的原始 Signal，并与 Raw 恢复结果逐节点取最大值：

```text
Signal Combined = max(Signal Original, Signal Raw Restored)
```

## 无 Mapping 格式

每个 Excel 的前五列是时间和来源 frame 信息，后面是行优先排列的 `N001...`：

```python
heatmaps = df.filter(regex=r"^N\d+$").to_numpy().reshape(-1, rows, columns)
```

- Finger：直接 `reshape(-1, 3, 6)`。
- Arm：直接 `reshape(-1, 12, 8)`。
- Robot arm：直接 `reshape(-1, 11, 12)`。

每个动作文件包含 `Raw Data`、`Baseline Fixed`、`Signal Original`、`Signal Raw Restored`、`Signal Combined`、`Pressure Drop V` 和 `Info`。完整文件索引见 `action_index.xlsx`。
