# 子 PRD-2：②b 离散包络（产形面 + 刃形）

**父 PRD**：`../2026-08-13-envelope-calculation-prd.md`
**状态**：待评审
**依赖**：子 PRD-1（多图层基础设施）

## 1. 目标

实现模块②b 离散包络路线（K-2.9~K-2.13），由工件齿廓点云经运动包络 → 投影 → 内边界提取，产出**产形面（扫掠点云）**与**刃形（有序点列）**两个可视化对象，并在 3D 视口叠加展示。

## 2. 范围

**做**：
- K-0.5 运动链复合变换（补齐 `transforms.py`）。
- K-2.9 运动包络点云、K-2.10 投影 z=0、K-2.11 内边界提取（[25] 径向圆环法，NR=200）。
- K-2.12 覆盖判据、K-2.13 双向包络复算 ffα。
- 离散参数默认 n=200 / m=181 / NR=200 / θ_range=±20°（第3章 §3.5）。

**不做**：解析路线（子 PRD-5）、前刀面（子 PRD-3，离散刃形不经过前刀面）、后刀面（子 PRD-4）。

## 3. 数据契约

- **输入**：工件廓形点云（复用 `profile.py::sample_profile_points`）+ ProcessPlan（Σ/a/r_pt/同步关系，K-1.4~1.8 需补）。
- **输出**：`GeneratrixSurface{扫掠点云 ⋃cloud_j, 坐标 T}` + `EdgeCurve{pts[] 有序, coverage_report}`（本子 PRD 产出**离散刃形**，不经前刀面，由投影 → 内边界提取直接得；与子 PRD-3/5 的「前刀面刃形交线 K-2.8」是两条不同派生路径，最终以 auto 推荐路线写入 `LayerId='edge'`）。
- **关键**：`EdgeCurve.pts[]` 必须**有序**并携带连续性标记，否则前端「逐点生长动画」无法落地。

## 4. 交互与视觉

- 产形面图层：`materialPreset: 'generatrix'`（品牌蓝半透明，默认 α≈0.35 由 layerPalette.ts 单源定义），点云或三角化。
- 刃形图层：`materialPreset: 'edge'`（深色高亮 `LineSegments`），逐点生长动画（`drawRange`）。
- 诊断条：ffα（<0.1μm）、覆盖判据（100%）。

## 5. 验收标准

1. ffα < 0.1μm（K-2.13 双向包络复算自证）。
2. 覆盖判据 100%（K-2.12，每离散点对应一刀形点）。
3. 算例2 自洽 + 矩阵 + 单点轨迹回归（设计书 testdata `ex2_discrete.json` 对照；后端回归基准以硬编码 golden 常量落地，见 ADR-007）。
4. 算例3 参数自洽 + Σ 翻号规则（设计书 `ex3_jia2019_cases.json`，同上）。
5. 产形面 / 刃形在视口正确叠加、可开关。

## 6. 缺口与风险

- T3（[21] 离散参数 n/m/k/L/n_L 未发表）→ 算例2 为**自洽/参数级回归**，非点级文献对拍（PRD 需明确此预期）。
- T5/T6（刃形坐标无文献锚点）→ 用 K-2.13 自复算闭环替代。
- T11（刃形不连续弧长阈值未给）→ 按点间距统计定标，留 calibration 开关。
- T2（s_d 判定表）→ β_w=0 时 s_d=0 占位。

## 7. 文件变更

| 文件 | 操作 |
|---|---|
| `backend/core/common/transforms.py` | 修改（补 K-0.5 运动链） |
| `backend/core/envelope/gen_surface.py` | 新增 |
| `backend/core/envelope/edge.py` | 新增 |
| `backend/core/common/gltf_export.py` | 修改（复用 export_geometry_glb 导出点云/曲线） |
| `backend/core/envelope/router.py` | 修改（注册 generatrix/edge 端点，跨子 PRD 共享文件统一收口） |
| `backend/core/envelope/tests/*` | 新增 |
