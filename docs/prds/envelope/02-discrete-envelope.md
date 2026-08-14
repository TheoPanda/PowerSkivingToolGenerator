# 子 PRD-2：②b 离散包络（扫掠点云 + 刃形）

**父 PRD**：`../2026-08-13-envelope-calculation-prd.md`
**状态**：待评审
**依赖**：子 PRD-1（多图层基础设施）

## 1. 目标

实现模块②b 离散包络路线（K-2.9~K-2.13），由工件齿廓点云经运动包络 → 投影 → 内边界提取，产出**扫掠点云（扫掠点云）**与**刃形（有序点列）**两个可视化对象，并在 3D 视口叠加展示。

## 2. 范围

**做**：
- K-0.5 运动链复合变换（补齐 `transforms.py`）。
- K-1.4~1.8 工艺方案（Σ/a/r_pt/同步关系），落 `envelope/process_plan.py`。
- K-2.9 运动包络点云、K-2.10 投影 z=0、K-2.11 内边界提取（[25] 径向圆环法，NR=200）。
- K-2.12 覆盖判据、K-2.13 双向包络复算 ffα（正向包络函数落 `envelope`，为 K-4.1 雏形，模块④正式化时复用）。
- 离散参数默认 n=200 / m=181 / NR=200 / θ_range=±20°（第3章 §3.5）。

**不做**：解析路线（子 PRD-5）、前刀面（子 PRD-3，离散刃形不经过前刀面）、后刀面（子 PRD-4）。

## 3. 数据契约

- **输入**：工件廓形点云（复用 `profile.py::sample_profile_points`）+ ProcessPlan（Σ/a/r_pt/同步关系，K-1.4~1.8，由 `envelope/process_plan.py` 构造）。
- **输出**：`SweptCloud{扫掠点云 ⋃cloud_j, 坐标 T}` + `EdgeCurve{segments[] 有序多段, coverage_report}`（本子 PRD 产出**离散刃形**，不经前刀面，由投影 → 内边界提取直接得；与子 PRD-3/5 的「前刀面刃形交线 K-2.8」是两条不同派生路径，最终以 auto 推荐路线写入 `LayerId='edge'`）。
- **关键**：`EdgeCurve.segments[]` 每段必须**有序**并携带连续性标记（左右刃形各一段，段间 `continuity` 标记不连续），否则前端「逐点生长动画」无法落地。

## 4. 交互与视觉

- 扫掠点云图层：`materialPreset: 'swept_cloud'`（品牌蓝半透明，默认 α≈0.35 由 layerPalette.ts 单源定义），**三角化半透明网面**（非散点，以便目检相切/折叠）。
- 刃形图层：`materialPreset: 'edge'`（珊瑚红高亮 `LineSegments`，多段），逐点生长动画（`drawRange`，各段各自生长）。
- 刀具参数输入：前端**最小参数区**（z_t/β_t/γ₀/α₀，默认=算例2 值），位于步骤2「包络解算」，风格与现有步骤条一致。
- 离散参数（n/m/NR/θ_range）不暴露 UI，后端默认；诊断条无失败补救按钮（留后续子 PRD）。
- 诊断条：ffα（<0.1μm）、覆盖判据（100%），仅显示数值 + 成功/失败状态。
- 扫掠点云图层「面 / 网」两档切换 + 蓝→红光谱顶点色 + φ_t 动画条（拖动/播放揭示生成过程），详见 spec `docs/specs/2026-08-13-swept_cloud-visualization-spec.md`。
- W/T 坐标轴加 X/Y/Z 文字标注（W/T 前缀）+ Z 轴旋转方向指针（示意工件逆时针/刀具顺时针转动），详见 spec `docs/specs/2026-08-13-coordinate-axes-marker-spec.md`。

## 5. 验收标准

1. ffα < 0.1μm（K-2.13 双向包络复算自证）。
2. 覆盖判据 100%（K-2.12，每离散点对应一刀形点）。
3. 算例2 自洽 + 矩阵 + 单点轨迹回归（设计书 testdata `ex2_discrete.json` 作**参考基准**，合理容差；超差先查文献笔误 C2/C3/W13 而非判 bug，正确性以 K-2.13 自证闭环 + 几何不变量为主）。
4. 算例3 参数自洽 + Σ 翻号规则（设计书 `ex3_jia2019_cases.json`，同上）。
5. 扫掠点云 / 刃形在视口正确叠加、可开关。
6. 可视化目检：扫掠点云三角网面无折叠、刃形只相切无重合（人工，对应「可视化即验收手段」）。
7. 扫掠点云目视化增强：面/网切换、光谱蓝→红标运动起止、动画条逐行揭示、蓝起始线 + 移动前缘线随光谱（详见 spec `2026-08-13-swept_cloud-visualization-spec.md`）。

## 6. 缺口与风险

- T3（[21] 离散参数 n/m/k/L/n_L 未发表）→ 算例2 为**自洽/参数级回归**，非点级文献对拍（PRD 需明确此预期）。
- T5/T6（刃形坐标无文献锚点）→ 用 K-2.13 自复算闭环替代。
- T11（刃形不连续弧长阈值未给）→ 按点间距统计定标，留 calibration 开关。
- T2（s_d 判定表）→ β_w=0 时 s_d=0 占位。

## 7. 文件变更

| 文件 | 操作 |
|---|---|
| `backend/core/common/transforms.py` | 修改（补 K-0.5 运动链） |
| `backend/core/envelope/process_plan.py` | 新增（K-1.4~1.8 工艺方案） |
| `backend/core/envelope/swept_cloud.py` | 新增 |
| `backend/core/envelope/edge.py` | 新增 |
| `backend/core/common/gltf_export.py` | 修改（复用 export_geometry_glb 导出点云/曲线） |
| `backend/core/envelope/router.py` | 修改（注册 swept_cloud/edge 端点，跨子 PRD 共享文件统一收口） |
| `backend/core/envelope/tests/*` | 新增 |

## 8. 变更履历

| # | 日期 | 来源 | 变更 |
|---|---|---|---|
| 1 | 2026-08-13 | 扫掠点云目视化 grilling | 扫掠点云升级为「带点的网 + 蓝→红光谱 + 动画条」，16 决策详见 spec `2026-08-13-swept_cloud-visualization-spec.md` |
| 2 | 2026-08-13 | 坐标轴美观 grilling | W/T 坐标轴加 X/Y/Z 标注 + Z 轴旋转方向指针，10 决策详见 spec `2026-08-13-coordinate-axes-marker-spec.md` |
