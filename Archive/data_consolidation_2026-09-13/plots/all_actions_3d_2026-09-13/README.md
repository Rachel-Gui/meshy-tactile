# 全部动作的固定视角 3D heatmaps

共 60 张 4800 × 3000 PNG，600 DPI；按 finger（28）、robot_arm（3）、human_arm（29）分类。index.html 可浏览，index.csv / provenance.json 记录对应文件、采样帧号与时间。

选帧：仅使用 XLSX 原始采样时刻，读取与前端一致的处理信号。每个传感器及其 5 个空间最近的已映射测点构成局部邻域；选取局部平均响应最大的一帧，并以全场响应总和、较早时间依次打破平局。这是本批次“最密集”的操作定义。

使用前端当前 GH 导出的原始三角网格（包含 Robot arm 5 mm 和 Finger 3 mm 两端条带）。Human arm 每组 8 通道反序，Finger 使用前端原生 18→30 映射，Robot arm 使用 132 个 workbook 节点顺序。平滑与前端相同：max(value × smoothstep(1-distance/radius))，radius 分别为 25/3/10 mm，gain=1，threshold=0；统一 0–1 thermal 色标，无逐图拉伸。

所有图片正交相机 elev=22°、azim=-65°、roll=0°；模型尺寸适配画布，不更改模型朝向。图片由科学绘图器用前端网格重绘，非仪表盘 UI 截屏；三角面使用顶点场值平均着色，没有前端光照造成的信号颜色明暗变化。固定视角可能遮住背面热点，图中保留完整模型，不为单条数据旋转。

Robot arm 使用 Signal Reconstructed（原 Signal Recorded 全零），前后物理安装方向仍待校准；Finger 是几何显示映射，未代表物理接线校准。不同设备的归一化响应不是跨设备校准压力。原始缺失值记录为 null，仅渲染时不贡献场值；未映射的 Finger 交点无独立信号。
