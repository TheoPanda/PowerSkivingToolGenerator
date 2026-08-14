# 扫掠点云目视化增强 Spec

**日期**：2026-08-13
**父 PRD**：`../prds/2026-08-13-envelope-calculation-prd.md` → `envelope/02-discrete-envelope.md`（对已实现的子 PRD-2 扫掠点云做可视化增强）
**状态**：待实现
**来源**：grilling 访谈（16 决策，含「运动-时间揭示 vs 仿真」边界澄清）

## Problem Statement

子 PRD-2 已交付扫掠点云（品牌蓝半透明实心三角网面）与刃形（珊瑚红逐点生长曲线）。但当前扫掠点云是**单一静态实心面**，用户无法据此判断三件事：① 扫掠的**采样分辨率与网格连通性**（有没有折叠/自交，藏在实心面之下）；② 扫掠的**运动相位**（面上哪一块对应运动起点、哪块对应终点）；③ 扫掠的**生成过程**（面是如何随运动逐步「长出来」的）。本 spec 给扫掠点云补三项可视化能力，让用户能目检判断：**带点的网（线框+网格点）、蓝→红光谱（标运动起止）、动画条（拖动/播放揭示生成过程）**。

## Solution

扫掠点云从「单一实心面」升级为「单一 `swept_cloud` 图层内的多 primitive 集合」，并新增一条「运动-时间揭示」交互：

- **几何**：实心光谱面 + 三角网线框（灰）+ 网格点（光谱），经「面 / 网」两档互斥切换。
- **光谱**：jet 彩虹（蓝→青→绿→黄→红），蓝=运动起点 φ_t=−θ、红=终点 φ_t=+θ，用 glTF `COLOR_0` 顶点色编码。
- **起止齿廓**：固定蓝起始线（φ_t=−θ 第一扫掠位 `cloud[0]`）+ 移动前缘线（当前 φ_t 行，整线单色=当前光谱色）。
- **动画条**：φ_t 滑块 + 进度% + 播放按钮，逐行揭示（drawRange）扫掠点云生成过程。

⚠️ **边界（务必澄清）**：这是**「揭示」（reveal）**，**不是「运动仿真」**。扫掠点云是**静态预计算的 m×n 扫掠点云**，动画条只是按 φ_t 顺序逐步把它「揭示」出来；不做刀具实体旋转、不做正向包络实时重算、不引入绝对角速度/墙钟时间。算法以**刀具转角 φ_t 为运动参数**（φ_w = φ_t/ω_ratio 同步），若刀具匀速转则 φ_t=ω_t·t，角度与时间只差常数比例——故 φ_t 即这根扫掠的「运动时钟」。

## User Stories

1. 作为车齿刀设计人员，我希望扫掠点云能切成「面」与「网+点」两档，以便在「看整体形状」和「看采样网格/折叠」之间切换。
2. 作为车齿刀设计人员，我希望扫掠点云按蓝→红光谱着色，一眼看出哪块是运动起点、哪块是终点、扫掠方向如何。
3. 作为车齿刀设计人员，我希望拖动（或播放）动画条，从运动起点逐步「长」出扫掠点云，判断扫掠过程是否连续、有无突变。
4. 作为车齿刀设计人员，我希望一条蓝线始终标着「运动开始那一刻采集的齿廓」，一条随滑块移动的前缘线标着「当前进度对应的齿廓」，两线都随光谱走。
5. 作为开发者，我希望光谱/线框/网格点/起止齿廓全部是**后端纯数学产出 + 顶点色编码**，前端只做「有 color 属性就用顶点色」的渲染，可入 CI。

## Implementation Decisions

### 视觉决策（grilling 锁定）

| # | 决策 | 结论 |
|---|---|---|
| 1 | 扫掠点云形态 | **三合一**：实心面 + 三角网线框 + 网格点 |
| 2 | 显示切换 | segmented「面 / 网」**两档互斥**：①「面」=实心光谱面；②「网+点」=线框+网格点。默认「面」，控件放「包络计算」区块 |
| 3 | 线框类型 | **三角网线框**（含对角线 = 实际三角面片边），最能暴露折叠/自交 |
| 4 | 线框颜色 | **中性深灰 `#1f2937`**（只表达连通性，不抢光谱） |
| 5 | 光谱插值 | **jet 彩虹**（蓝→青→绿→黄→红），蓝=φ_t=−θ 起点、红=φ_t=+θ 终点 |
| 6 | 光谱承载 | 实心面=光谱；网格点=光谱（网+点档时点扛运动相位）；线框=中性灰 |
| 7 | 蓝起始线 | `cloud[0]`（φ_t=−θ 第一扫掠位），色=光谱蓝端 `#00007F`，**始终可见**（起点锚点） |
| 8 | 动画条轴 | **φ_t（°）**，范围 −θ..+θ，旁显示进度 %（如 `φ_t=+5.0°（62.5%）`）；不引入假的时间尺度 |
| 9 | 动画条语义 | **揭示 + 前缘线**：逐行 drawRange 揭示扫掠点云（面/点/线框随动、跟随面/网档）；一条前缘齿廓线随动 |
| 10 | 前缘线颜色 | 整线**单色 = 当前 φ_t 的光谱色**（拖到哪变哪档色） |
| 11 | 播放 | **单向**从当前值扫到 +θ 停，约 3s；默认停在**满（+θ，完整面，=现状视觉）** |
| 12 | 与刃形关系 | **独立**：滑块只驱动扫掠点云，刃形保持现有「自动一次性生长」 |
| 13 | 颜色编码 | **统一 COLOR_0 顶点色**（面/点/线框）；前端按 `hasAttribute('color')` 开 `vertexColors` |
| 14 | 图层模型 | 仍**一个 `swept_cloud` 图层**多 primitive，图层面板一行 |
| 15 | 采样密度 | 保持 `n=200 / m=181`，点大小/线框粗细前端可调 |
| 16 | 生长动画 | **不扩展**到面/点/线框/蓝线；保留刃形现有生长 |

### 数据契约：swept_cloud GLB 结构

扫掠点云图层 GLB 内按序含 **3 个 primitive**（`node.name` 带角色后缀，仅调试标签；图层身份仍由 `addLayer(id, …)` 显式传）：

| # | kind | 内容 | 顶点色 COLOR_0 |
|---|---|---|---|
| 1 | `mesh`（TRIANGLES） | 实心三角网面（positions + indices + normals） | 光谱 jet（按 φ_t 行） |
| 2 | `points`（POINTS） | m×n 网格顶点（positions，无 indices） | 光谱 jet（按 φ_t 行） |
| 3 | `lines`（LINES + indices） | 三角网线框段（灰） | 常量灰 `#1f2937` |

- **蓝起始线 + 移动前缘线不占后端 primitive**：二者是前端从已加载 mesh positions（行优先 m×n）逐行取点构建的 `THREE.Line`——蓝起始线=第 0 行（常量蓝材质），移动前缘线=第 k 行（动态 `material.color`=jet(f)）。这是「COLOR_0 统一」的合理例外：动态色随滑块变，无需进 GLB。
- **顶点色 ramp**：`jet(t)`，t = i/(m−1)，i = φ_t 行索引。t=0 → `(0,0,0.5)`（≈`#00007F`，与蓝起始线一致）；t=1 → `(1,0,0)` 红。纯 Python 分段线性实现（无新依赖）。

### 端点契约变更（`POST /api/envelope/swept_cloud`）

响应新增 `motion` 元数据（供前端映射滑块→行号、行取点、逐行揭示；**零重算**）：

```json
{
  "layer": { "id": "swept_cloud", "glb_base64": "..." },
  "coord_frame": "T",
  "motion": {
    "n": 200,
    "m": 181,
    "theta_range_deg": 20.0,
    "surface_indices_per_row": 2400,
    "points_vertices_per_row": 200,
    "wireframe_indices_per_row": 2388
  }
}
```

- `surface_indices_per_row = (n−1)×6`；`points_vertices_per_row = n`；`wireframe_indices_per_row = 12×(n−1)`（线框=三角片边、**含重复共享边**、与 `mesh_indices` 同序，故每条共享边画两遍、视觉无差但 reveal 与面严格对齐）。
- 三个 `*_per_row` 由后端算好下发，前端不做网格布局推导（延续「前端 dumb、后端自包含」）。

### 前端揭示（drawRange）语义

滑块 φ_t ∈ [−θ,+θ] → 归一化 f=(φ_t+θ)/(2θ) ∈ [0,1] → 前缘行 `k = round(f·(m−1))`：

- **实心面**：`mesh.setDrawRange(0, k × surface_indices_per_row)`（行 0..k−1 的三角片）。
- **网格点**：`points.setDrawRange(0, (k+1) × points_vertices_per_row)`（行 0..k 的顶点）。
- **线框**：`wireframe.setDrawRange(0, k × wireframe_indices_per_row)`。
- **前缘线**：第 k 行齿廓，整线颜色 = `jet(f)`。
- 边界：f=0 → 仅见第 0 行点 + 前缘线（蓝，与蓝起始线重合）；f=1 → 完整面（=现状视觉），前缘线在红端。

### 前端「面 / 网」切换

- 两档**互斥显示**扫掠点云图层内的子元素：`面` → 只显示实心 mesh；`网+点` → 只显示线框 + 网格点。
- **蓝起始线 + 移动前缘线在两档都显示**（它们是齿廓标记，独立于面/网格式）。
- 切换只改子元素 `visible`，不改材质、不重建几何、不影响 reveal 进度（`setLayerReveal` 对两档各自作用的子元素生效）。

### 前端材质（多 primitive 逐子赋值）

`mountLayer` 从「整层一个 kind」改为「按 child 类型 + 是否带 color 属性」逐子赋材质：

- `Mesh` + `hasAttribute('color')` → `MeshStandardMaterial({ vertexColors: true, color: 0xffffff, transparent: true, opacity: 0.35, side: DoubleSide })`（opacity/doubleSide 取 layerPalette 的 swept_cloud 预设）。
- `Points` + `hasAttribute('color')` → `PointsMaterial({ vertexColors: true, color: 0xffffff, size: 0.5 })`。
- `Line`/`LineSegments` + `hasAttribute('color')` → `LineBasicMaterial({ vertexColors: true, color: 0xffffff })`。
- **无 color 属性** → 回退现有 palette 材质（零回归：工件/刃形/演示图层走此路）。

## Testing Decisions

- **纯数学进 pytest CI**：光谱 ramp `jet(t)` 端点（t=0 → 蓝、t=1 → 红）与中段过绿（t=0.5 绿分量主导）；线框索引数 = 12(m−1)(n−1)（三角片边、含重复共享边）；`surface_indices_per_row`/`points_vertices_per_row`/`wireframe_indices_per_row` 公式正确。
- **GLB 契约（纯 Python，无 OCCT）**：`export_geometry_glb` 带 `colors` 时 accessor 含 `COLOR_0`（VEC3/float，count=顶点数）；`kind="lines"` primitive mode=1（LINES）且带 indices；`node.name` 角色后缀。
- **端点集成**：`TestClient` 调 swept_cloud，验 GLB magic、`coord_frame='T'`、`motion` 元数据字段存在且值正确、GLB 内 mesh/points/lines 三个 primitive。
- **前端（vitest + fake renderer）**：`mountLayer` 对多 primitive（Mesh/Points/LineSegments）逐子赋材质，`hasAttribute('color')` 守卫（无 color 回退 palette）；`setLayerReveal` 设 drawRange；「面/网」切换子元素显隐；前缘线颜色随 f 更新。沿用现有 mock GLTFLoader（无 color 属性 → 走回退路径，保证既有测试零回归）。
- **零回归门禁**：子 PRD-1 多图层/非实体导出/图层列表交互、子 PRD-2 扫掠点云/刃形叠加全绿。

## Out of Scope

- **运动仿真**（刀具实体旋转、正向包络实时重算、绝对角速度/墙钟时间）——模块④ K-4.1，另立子 PRD。
- 解析共轭路线（子 PRD-5）、前刀面（子 PRD-3）、后刀面（子 PRD-4）——不变。
- 扫掠点云逐点「生长动画」扩展（本 spec 用 reveal 滑块取代，刃形生长保持现状）。
- 离散参数 n/m/NR/θ_range 暴露 UI（仍后端默认）。
- 线框粗细（WebGL 线宽恒 1px，不额外处理）；点大小如需调属前端常量。

## Further Notes

- **坐标标签**：所有几何仍在刀具动系 T，响应带 `coord_frame: "T"`。
- **共享文件单一负责人**：`common/gltf_export.py`、`envelope/router.py`、`envelope/swept_cloud.py` 为跨子 PRD 共享，本增强「修改」之，最终由最后合并的子 PRD 收口。
- **ADR-019 延续**：本增强全部是可视化手段，不改变包络算法的正确性判据（ffα 自证闭环 + 几何不变量 + 目检）；「光谱/网/动画条」都是让「目检」这一步更可判。

## 变更履历

| # | 日期 | 来源 | 变更 |
|---|---|---|---|
| 1 | 2026-08-13 | grilling Q1 | 扫掠点云三合一 + 「面/网」两档互斥切换 |
| 2 | 2026-08-13 | grilling Q2 | 光谱 jet 彩虹、蓝=起点红=终点 |
| 3 | 2026-08-13 | grilling Q3/Q11/Q17 | 蓝起始线=cloud[0]、色=光谱蓝端、始终可见 |
| 4 | 2026-08-13 | grilling Q4 | 统一 COLOR_0 顶点色编码 |
| 5 | 2026-08-13 | grilling Q5 | 单一 swept_cloud 图层多 primitive |
| 6 | 2026-08-13 | grilling Q6 | 保持 n=200/m=181 |
| 7 | 2026-08-13 | grilling Q8/Q9 | 三角网线框 + 中性深灰 #1f2937 |
| 8 | 2026-08-13 | grilling Q12/Q13/Q14/Q16 | 动画条=φ_t 揭示 + 前缘线、播放、独立于刃形 |
| 9 | 2026-08-13 | grilling Q18/Q19 | 前缘线单色随光谱、单向播放 |
