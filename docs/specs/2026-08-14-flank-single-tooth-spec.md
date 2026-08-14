# 后刀面 + 单齿预览（子 PRD-4）实现 Spec

**日期**：2026-08-14
**父 PRD**：`../prds/2026-08-13-envelope-calculation-prd.md` → `envelope/04-flank-single-tooth.md`
**状态**：待实现
**来源**：后刀面/单齿 grilling（grill-with-docs，13 决策全 A）+ 设计书第 4.4/6/7 章 + 算例2 Δa_i 回归向量

## Problem Statement

模块①（工件）、子 PRD-1（多图层）、子 PRD-2（离散刃形）、子 PRD-3（前刀面）已交付。「反向包络」三件套只剩 ②c 后刀面——刀具用钝后要磨前刀面、刀刃逐层后退，「**重磨后刀刃的集合**」这块还没实现。本子 PRD 落地 K-2.18/2.19 分截面包络生成后刀面，并按 K-3.1 把前刀面 + 后刀面 + 刃形拼成**单齿预览**，让用户目检「三件套闭合」。

## Solution

新建 `flank.py`（K-2.18 Δa_i + K-2.19 分截面刃形 + 三角网连片拟合）+ `single_tooth.py`（三件套叠加）。注册 flank / single-tooth 端点。前端加重磨参数（L / n_L）+ 后刀面 / 单齿图层。验收靠算例2 Δa_i golden + 拟合残差 + 目检。

## User Stories

1. 作为车齿刀设计人员，我希望输入总重磨量 L 和等分数 n_L 后，看到后刀面（翡翠绿半透明面）叠加，理解「重磨后刀刃的集合」这一动态概念。
2. 作为车齿刀设计人员，我希望后刀面是「分截面刃形按重磨次序拟合」的面，而不是一个静态背面，从而目检重磨后刃形的保持性。
3. 作为车齿刀设计人员，我希望看到单齿预览（前刀面 + 后刀面 + 刃形三件套）叠加，目检三件套是否围成一颗齿。
4. 作为车齿刀设计人员，我希望诊断条显示截面拟合残差，判断后刀面拟合质量是否可接受。
5. 作为车齿刀设计人员，我希望后刀面 / 单齿图层能独立显隐、调透明度，与扫掠点云 / 前刀面 / 刃形互不遮挡。
6. 作为开发者，我希望 K-2.18 Δa_i 是纯 Python 纯数学、可入 CI，且**兼容内外齿轮**（a_i = a − k_io·Δa_i）。
7. 作为开发者，我希望回归测试以算例2（内齿轮）Δa_i golden 为锚点，外齿轮方向标注为推导、不当硬锚点。
8. 作为开发者，我希望单齿预览是「三件套非实体叠加」，不越级做闭合流形实体（留模块③）。
9. 作为开发者，我希望后刀面 / 单齿响应带 `source` 标记（「离散临时，待解析覆盖」），前端能提示「预览级」。

## Implementation Decisions

### 验收哲学（继承 ADR-019）
- Δa_i 是**闭式解析**（Δa_i = ΔL_i·tan α₀），无迭代、无笔误风险，可设紧容差；但外齿轮方向（a_i = a − Δa_i）是**推导、文献未发表**（T14），只能当「推导」落地、不当硬锚点。拟合残差 < 离散点间距一半是第 7 章行 16 的**推导设定**（⚠️ 待实现校准回填）。

### 算法管线一：K-2.18 重磨截面中心距（新建 flank.py，纯数学）
- **K-2.18**：`Δa_i = ΔL_i·tan(α₀)`，总重磨量 L 等分 n_L 份，`ΔL_i = i·L/n_L`（i = 1..n_L）。
- **中心距方向（k_io 感知）**：`a_i = a − k_io·Δa_i`
  - 内齿轮（k_io=−1）：`a_i = a + Δa_i`（刀具磨薄 → 等效半径减小 → 中心距增大，设计书 §4.4.3 符号说明 + 算例2 验证）。
  - 外齿轮（k_io=+1）：`a_i = a − Δa_i`（刀具磨薄 → r_pt 减小 → a = r_pw + r_pt 减小），**推导、文献未发表**（T14），注释标注未销项。
- α₀ 是**后角**（非前角 γ₀），来自组B 刀具参数（算例2 α₀=8°，tan8°=0.140541）。
- 算例2（内齿轮）golden（L=2mm / n_L=4 / a=6.7938）：

  | i | ΔL_i [mm] | Δa_i [mm] | a_i [mm] |
  |---|---|---|---|
  | 1 | 0.50 | 0.07027 | 6.86407 |
  | 2 | 1.00 | 0.14054 | 6.93434 |
  | 3 | 1.50 | 0.21081 | 7.00461 |
  | 4 | 2.00 | 0.28108 | 7.07488 |

### 算法管线二：K-2.19 分截面刃形 + 三角网连片拟合
- **K-2.19 分截面包络**：对每个 `a_i` 重跑 ②b 离散包络（K-2.9~2.11，即 `generate_envelope_cloud` + `extract_edge`），得各截面刃形。
- **拟合 = 三角网连片**（非 B 样条/高阶扫掠面）：`前刀面刃形 + 各截面刃形` 按「距前刀面由近及远」顺序，相邻截面刃形的对应点连三角网（与扫掠点云 mesh 连片同构）。
- **刃形来源**：本期后刀面基于 ②b **离散刃形**（z=0 内边界，临时占位），非 K-2.8 解析刃形；解析刃形的后刀面待子 PRD-5 落地后对接。

### 数据契约
- **输入**（端点请求，**补正 PRD 4 §3 的不足**）：完整工件参数 + 刀具参数 + L + n_L + α₀。
  - ⚠️ 设计书 §4.4.2 写 `INPUT EdgeCurve, RakeSurface, tool_type, L, n_L`，但 K-2.19 要对每个 a_i **重跑整个 ②b**，必须拿到工件/刀具完整参数才能重算——所以后刀面端点复用子 PRD-2 的 `EnvelopeRequest`（workpiece + tool + discretization）+ 额外 `L`/`n_L`，**不能只收 EdgeCurve**。
- **输出** `FlankSurface{section_edges[], flank_mesh, resharpen_schedule a_i[]}` + 单齿三件套 GLB，均带 `source` 标记（「离散临时，待解析覆盖」）。

### 单齿预览 = 三件套非实体叠加（闭合流形留模块③）
- 单齿 = 前刀面片 + 后刀面片 + 刃形（三件套，各为独立 GLB primitive）**叠加**，硬质合金着色。
- **不做闭合流形实体**：不封边、不加齿顶/齿根端盖、不缝 BRep。验收降级为「三件套目视闭合」。
- 单齿层 `singleTooth` 沿用 `layerPalette.ts` 的 `carbide` 预设（硬质合金 0x5a5854）。

### 端点设计（独立算、无状态）
- `POST /api/envelope/flank` 与 `POST /api/envelope/single_tooth`，独立计算、不缓存（对齐 ADR-018）。
- flank 请求体 = 子 PRD-2 `EnvelopeRequest`（workpiece + tool + discretization）+ `resharpen: { L: 2.0, n_L: 4 }`；α₀ 取自 `tool.alpha_0_deg`。
- flank 响应：
  ```json
  { "layer": { "id": "flank", "glb_base64": "..." }, "coord_frame": "T",
    "source": "离散临时，待解析覆盖",
    "resharpen_schedule": [{ "i": 1, "dL": 0.5, "da": 0.07027, "a_i": 6.86407 }, "..."],
    "fit_residual_mm": 0.003 }
  ```
- single_tooth 响应：三件套 GLB（`layer.id = 'singleTooth'`，含前刀面/后刀面/刃形三个 primitive），`source = 模块③预览`。
- 错误契约 `{ "error": "描述", "code": 400 }`；坐标标签随数据传递（`coord_frame: "T"`）。

### 前端交互
- 步骤2「包络解算」参数区加 L（总重磨量，默认 2mm）+ n_L（等分数，默认 4）。
- 驱动顺序：点「开始包络」→ swept_cloud → edge → rake（子 PRD-2/3）→ flank → single_tooth（本子 PRD）。
- 后刀面图层：翡翠绿 #3AA06A 半透明（`layerPalette.ts` 的 `flank` 预设）。
- 单齿图层：硬质合金实心（`carbide` 预设）+ 前端「模块③预览」提示（读 `source`）。
- 诊断条：截面拟合残差（< 离散点间距一半）。

## Testing Decisions

- **纯数学 pytest CI（不依赖 OCCT）**：`compute_resharpen_schedule(L, n_L, alpha_0_deg, k_io)` 纯函数，直接单测。
- **算例2（内齿轮）Δa_i golden 回归**：0.07027 / 0.14054 / 0.21081 / 0.28108（L=2 / n_L=4 / α₀=8°），容差 1e-5（闭式三角值、紧容差）；外齿轮方向（a_i = a − Δa_i）单测断言符号方向、不设文献硬锚点。
- **拟合残差不变量**：各截面刃形与前刀面刃形拟合残差 < 离散点间距一半（第 7 章行 16，⚠️ 推导设定）。
- **端点集成**：TestClient 调 flank / single_tooth 端点，验 GLB magic、coord_frame='T'、source 标记、resharpen_schedule 字段与 golden 一致（沿用子 PRD-2 端点测试模式）。
- **图层叠加验收**：flank / singleTooth 图层经 `gear:layer-ready` 叠加、可独立开关显隐。
- **零回归门禁**：子 PRD-1/2/3 已交付的多图层 / 离散包络 / 前刀面保持全绿。
- **人工目检**：后刀面翡翠绿面与扫掠点云 / 前刀面 / 刃形明显区分；单齿三件套目视闭合（对齐 ADR-019「可视化即验收手段」）。

## Out of Scope

- 变位族法 K-2.14（锥刀，W5 缓行）、圆柱刀导程法 K-2.15/16（二期可选）、圆柱刀轴向偏移法 K-2.17（二期可选）。
- 单齿周向阵列成完整刀具（模块③ 正式交付）。
- 闭合流形实体（前刀面 + 后刀面封边 + 齿顶/齿根端盖 + BRep 缝合，模块③ K-3.1）。
- 解析刃形（K-2.8）的后刀面——待子 PRD-5 落地后对接覆盖。
- 斜齿工件（β_w≠0，MVP 禁用，继承父 PRD）。

## Further Notes

- 权威源对齐：坐标标签随数据传递（后刀面/单齿在刀具动系 T）；内部 rad / 接口 °；变量名 w/t；模型传输仅 glTF/GLB。
- 缺口纪律：T3（L/n_L 未发表 → 用第6章推导示例 L=2/n_L=4 + 工程默认）；外齿轮 Δa_i 方向推导未销项（T14 已入设计书第 8 章）；单齿预览越级模块③ → 后端 `source` 溯源 + 前端显式标注双保险。
- 上游依赖：复用子 PRD-1 的 `export_geometry_glb`（曲面片/曲线）、子 PRD-2 的 `generate_envelope_cloud`/`extract_edge`（分截面重算）、`compute_process_plan`（r_pt）、子 PRD-3 的 `RakeSurface`（前刀面片）。
- 共享文件单一负责人：`envelope/router.py`、`common/gltf_export.py` 为跨子 PRD 共享文件，本子 PRD 注册 flank/single-tooth 端点，最终由最后合并的子 PRD 收口。
