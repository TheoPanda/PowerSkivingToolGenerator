# 前刀面定义（子 PRD-3）实现 Spec

**日期**：2026-08-14
**父 PRD**：`../prds/2026-08-13-envelope-calculation-prd.md` → `envelope/03-rake-face.md`
**状态**：待实现
**来源**：前刀面 grilling（grill-with-docs，10 决策全 A）+ 设计书第 2/3/4/6/8 章 + 算例1 系数分解核对

## Problem Statement

模块① 交付工件齿轮；子 PRD-1 交付多图层视口 + 非实体导出；子 PRD-2 交付离散包络（扫掠点云 + 刃形，**不经前刀面**）。至此「反向包络」三件套（②a 前刀面 / ②b 刃形 / ②c 后刀面）还缺 ②a 前刀面。前刀面是**独立设计输入**（用户选前角 γ₀，非共轭派生物，设计书 §4.2.1），是单齿闭合（K-3.1，子 PRD-4）的前置。本子 PRD 落地 K-2.1 平面前刀面：用户给定前角后，系统算出前刀面隐式方程 F(x,y,z)=0 与法矢场 n_rake，在视口以琥珀橙半透明平面 + 法矢箭头叠加，并以算例1 系数吻合自证。

## Solution

新建 `rake.py` 实现 K-2.1（[23] 式3.4 产形轮法），在产形轮固连系 S₁（≡ 刀具动系 T）中装配平面前刀面；输出 `RakeSurface{F, n_rake, coeff}`。注册 `rake` 端点。前端加前角参数区 + rake 图层（平面片 + 法矢箭头）。验收靠算例1 系数 golden + 单位法向不变量 + 可视化目检。

## User Stories

1. 作为车齿刀设计人员，我希望在步骤2 输入前角 γ₀ 后，看到前刀面（琥珀橙半透明平面）叠加到视口，理解刀刃前斜面的方位。
2. 作为车齿刀设计人员，我希望看到前刀面**法矢箭头**，直观确认 n_rake 的方向。
3. 作为车齿刀设计人员，我希望 rake_type 只有「平面」可选，「方程」「锥面」灰置禁用，避免误选未实现的锥面前刀面（W5 未销项）。
4. 作为车齿刀设计人员，我希望 γ₀ 默认 5°（参数字典），无需每次手动填。
5. 作为开发者，我希望 K-2.1 系数装配是**纯 Python 纯数学**、可入 CI，不依赖 OCCT。
6. 作为开发者，我希望回归测试以算例1 前刀面系数为 golden 常量，并断言单位法向不变量。

## Implementation Decisions

### 验收哲学（继承 ADR-019，但本子 PRD 可设紧容差）
- 文献值（含设计书复算）是参考基准、非硬门禁。但算例1 前刀面系数是**闭式解析三角值**（sinγ、cosγ·sinβ₁、cosγ·cosβ₁），无迭代、无「中心距符号」这类笔误风险，故 golden 可设**紧容差 1e-6**——这是「参数级精确回归」，不同于算例2 的「自洽/参数级参考基准」。

### 算法：K-2.1 平面前刀面（产形轮法）
- 公式（[23] 式3.4，在产形轮固连系 S₁ ≡ 刀具动系 T）：
  `F(x,y,z) = (x − r₁)·sinγ + y·cosγ·sinβ₁ + z·cosγ·cosβ₁ = 0`
- 系数装配（纯函数，输入 γ₀[°]/β_t[°]/r_pt，内部转 rad）：
  - `A = sinγ`
  - `B = cosγ·sinβ₁`
  - `C = cosγ·cosβ₁`
  - `const = −A·r₁ = −r₁·sinγ`
  - 其中 `γ = γ₀`（设计前角）、`β₁ = β_t`（产形轮螺旋角 = 刀具螺旋角）、`r₁ = r_pt`（产形轮分度圆半径 = 刀具分度圆半径）。
- **单位法向不变量**：`|(A,B,C)| = √(sin²γ + cos²γ·(sin²β₁ + cos²β₁)) = 1` 恒成立（构造保证），作为不变量断言。
- **过点 P_ref**：平面过 `(r₁, 0, 0)`（产形面分度圆在 z=0 参考面的点），`const` 由其展开。P_ref 是**派生量**、非用户字段。
- 算例1 数值实例（γ=5°、β₁=15°、r₁=42.455）：A=0.087156、B=0.257834、C=0.962250、const=−3.7002。
- **坐标系**：K-2.1 的 [23] 下标「S₁=刀具」≡ U4 刀具动系 T（同名同体、无变换）；代码/契约统一用「T」标签，不引「S₁」裸名，只在注释桥接一次（[23] 1=刀具 ≠ [14] 1=工件，设计书 §2 自标歧义）。

### 数据契约
- 输入 `RakeSpec{rake_type, γ₀}` + `ToolDraft{β_t, z_t, …}` + r_pt（取自 ProcessPlan）。
- 输出 `RakeSurface{coeff=(A,B,C,const), n_rake, P_ref}`，坐标 T。
  - `n_rake = ∇F/|∇F| = (A,B,C)`（单位，**不额外翻号**）；「指向刀体 vs 切屑」方向语义留给子 PRD-5 K-2.8 消费时定。
- rake_type 取值：v1 仅「平面」；「方程」（K-2.3）、「锥面」（K-2.4）→ `raise NotImplementedError` 骨架占位，**字段不预留**（YAGNI，等真实现时再加 S_R/P/cone_angle）。

### 端点设计（独立算、无状态）
- `POST /api/envelope/rake`，独立计算、不缓存（对齐 ADR-018「每阶段独立 GLB、无跨阶段攒状态」）。
- 请求体（复用现有 `GearParamsRequest` + `ToolParams`，`tool.gamma_0_deg` 从「保留位」转正为本子 PRD 的 γ₀ 输入；`alpha_0_deg` 仍保留位）：
  ```json
  {
    "workpiece": { "k_io": -1, "m_n": 2.0, "z_w": 82, "beta_w_deg": 0.0, "j_w": 1,
                   "alpha_n_deg": 20.0, "h_an": 1.0, "c_n": 0.25, "x_w": 0.0, "b_w": 20.0 },
    "tool": { "z_t": 68, "beta_t_deg": 15.0, "j_t": -1, "gamma_0_deg": 5.0, "alpha_0_deg": 8.0 },
    "rake_type": "plane"
  }
  ```
  - `rake_type` 默认 `"plane"`、仅此一值，其余 400（`{ "error": "未实现", "code": 400 }`）。
  - 不需要离散参数（discretization）——K-2.1 是闭式装配，无离散量。
- 响应体：
  ```json
  {
    "layer": { "id": "rake", "glb_base64": "..." },
    "coord_frame": "T",
    "plane": { "A": 0.087156, "B": 0.257834, "C": 0.962250, "const": -3.7002 },
    "p_ref": [42.455, 0.0, 0.0],
    "n_rake": [0.087156, 0.257834, 0.962250]
  }
  ```
  - GLB 内含**两个 primitive**：平面片（mesh，layer_id=`rake`）+ 法矢箭头（line，layer_id=`rake.normal`）。
- 错误契约 `{ "error": "描述", "code": 400 }`；模型传输仅 glTF/GLB；坐标标签随数据传递（`coord_frame: "T"`）。

### 可视化：平面片 + 法矢箭头
- **平面片**：平面 F=0 为无限，渲染为有限矩形片。取平面内两正交切向 u、v（u = normalize(n × ẑ)，n∥ẑ 时退化为 u=(1,0,0)；v = n × u），以 P_ref 为中心生成矩形，径向半宽 ≈ 1.2·r_pt、轴向半宽 = 默认 10mm 占位（模块③ 有真实齿面宽后对齐），`doubleSide` 半透明。
- **法矢箭头**：从 P_ref 沿 n_rake 画一条线段（长度 ≈ 0.2·r_pt），复用坐标轴标注 spec（`2026-08-13-coordinate-axes-marker-spec.md`）的箭头/指针画法；`layer_id='rake.normal'` 与平面片区分。
- **图层配色**：rake 琥珀橙 #E8963A 半透明 α≈0.45（`layerPalette.ts` 单源）。

### 前端交互
- 步骤2「包络解算」参数区加 γ₀（默认 5°）+ rake_type（下拉仅「平面」；「方程」「锥面」disabled + 提示「未实现」）。
- 驱动顺序：点「开始包络」→ 依次 swept_cloud、edge（子 PRD-2）、rake（本子 PRD）→ 经 `gear:layer-ready` 事件叠加。

## Testing Decisions

- **纯数学 pytest CI（不依赖 OCCT）**：`build_plane_rake(gamma_deg, beta_t_deg, r_pt) -> (A,B,C,const)` 纯函数，直接单测。
- **golden 系数回归（参考基准，紧容差）**：算例1 A=0.087156 / B=0.257834 / C=0.962250（6 位小数，容差 1e-6）/ const=−3.7002（4 位小数、派生量 −A·r₁ 会放大 A 的舍入，容差放宽 1e-4）。闭式三角值、无笔误风险，可比算例2 更紧。
- **单位法向不变量**：`|(A,B,C)|=1` 断言（构造保证，非逐点数值对拍）。
- **端点集成**：`TestClient` 调 rake 端点，验 GLB magic、`coord_frame='T'`、`node.name='rake'`、`plane`/`n_rake` 字段存在且与 golden 一致（沿用子 PRD-2 端点测试模式）。
- **图层叠加验收**：rake 图层经 `gear:layer-ready` 叠加、可独立开关显隐（对齐子 PRD-2 验收第 5 条模式）。
- **零回归门禁**：子 PRD-1 多图层/非实体导出、子 PRD-2 离散包络保持全绿。
- **人工目检**：法矢箭头方向与系数符号一致（对齐 ADR-019「可视化即验收手段」）。

## Out of Scope

- K-2.3 通用方程 + 特征点（[25] S_R+P）、K-2.4 锥面前刀面（W5）、K-2.2 变换构造（[11] 圆柱刀 z_off）、K-2.5 法矢旋转链。
- K-2.8 刃形交线（前刀面 ∩ 生成面，子 PRD-5 解析路线）——本子 PRD 的前刀面**不与刃形求交**。
- 楔角校核（γ₀+α₀ < 90°−15°，模块④ K-2.21 工作角度）。
- 后刀面 + 单齿预览（子 PRD-4）。
- 法矢方向语义（刀体/切屑）——移交子 PRD-5 消费时定。

## Further Notes

- 权威源对齐：坐标标签随数据传递（前刀面在刀具动系 T，响应带 `coord_frame`）；内部 rad / 接口 °；变量名 w/t；模型传输仅 glTF/GLB。
- 缺口纪律：W5（锥面 ±/∓）skeleton + assert；K-2.3/K-2.4 字段 YAGNI 不预留。
- S₁≡T 桥接：K-2.1 的 [23] 下标「1=刀具」与 [14] 下标「1=工件」语义不同（设计书 §2 自标歧义），代码只认 U4 的 T，注释桥接一次即可。
- 上游依赖：复用子 PRD-1 的 `export_geometry_glb`（平面 mesh、箭头 line）与 `gear:layer-ready` 事件链路；复用子 PRD-2 的 `compute_process_plan`（取 r_pt）与 `GearParamsRequest`/`ToolParams`。
- 共享文件单一负责人：`envelope/router.py` 为跨子 PRD 共享文件，本子 PRD 注册 rake 端点，最终由最后合并的子 PRD 收口。
