# Arm 上下交错编织试作版

沿原模型的两组中心曲线重建 24 根条带，每根条带在 8 个原交叉位置按上/下交替起伏。两组曲线在同一交叉点的高度相反。

## 文件

- `human_arm_woven.3dm`：26 个独立闭合网格（24 根条带、2 个端环），以及原来的 96 个参考传感点。单位 mm。
- `human_arm_woven.gh`：独立的 Grasshopper 几何试作定义，含 `WeaveLift`、`StripThickness`、`StripWidth` 滑块。
- `human_arm_woven.obj`：通用网格模型，按条带/端环分别命名，单位 mm。
- `arm-woven-preview.png`、`arm-woven-detail.png`：两组条带以蓝色和金色区分，方便检查交替遮挡。颜色仅用于说明。
- `svg/`：六个正交视图与三维斜视图，透明背景。
- `validation.json`：当前参数下的闭合、相交和交替顺序检查结果。

## 当前参数与验证

条带宽 4 mm，厚 0.4 mm，上下偏移 ±0.8 mm，交叉中心表面间隙约 1.2 mm；采用平滑起伏连接。端环轴向宽度仍为 5 mm，径向厚度改为 2 mm 以连接两层条带。

Rhino 检查：24 根条带均为闭合网格，每根条带的 8 个高度符号均交替；全部 276 对条带之间 MeshMeshFast 检查未检测到相交。

这是几何试作版。端环与条带在连接处相接/相交，尚未布尔合并为单一制造实体。原传感点保持原来的参考位置，未移动到起伏表面；原实时热图及 `web/public/assets/model.json` 未替换。这个独立 GH 的 Sensor Heatmap 组件当前生成静态编织网格，未接回实时着色。

视图方向沿用项目：front/back 为 -X/+X 端面，left/right 为 -Y/+Y 长侧面，top/bottom 为 +Z/-Z。各视图独立适配画布。

原模型 `models/tactile/1.gh` 保留。编织版保存于 `models/tactile/human_arm_woven.gh` 和 `models/tactile/human_arm_woven.3dm`。
