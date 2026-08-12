# 内齿轮工件几何（k_io=−1）— 设计规格

**日期**：2026-08-12
**状态**：已实现（直齿 T01–T04 完成；**内斜齿 v2 2026-08-12 完成**，见 §11 + ADR-017）
**需求来源**：grilling——「待加工齿轮板块还有一块内容没有设计——内齿轮设计。现在还只能设计外齿轮。现在实现内齿轮设计的模块。」；「现在补足内斜齿轮的工作。」

## 1. 目标

在「待加工齿轮」板块（步骤1 参数表单 + 步骤2 工件 3D 生成 + 规格窗口）实现**内齿轮工件几何**（`k_io=−1`）：参数 → 3D **环形实体**（外边界 `d_rim` + 内齿孔）GLB → 规格窗口（单齿廓/整体轮廓/参数表）。

**范围限定**：内齿轮**自身几何层**。内齿轮车齿加工的中心距/传动比语义（设计书 U9/K-1.5/K-1.6：`a = r_pw + k_io·r_pt`、`i = −k_io·z_w/z_t`）与啮合副干涉留待模块②（未来步骤3）。

**核心约束**：
1. **外齿轮零变化**：`k_io=1` 时输出与现状逐点一致（golden 回归护栏）。现有外齿轮测试全部保持绿。
2. **权威源纪律**：内齿轮几何公式设计书未覆盖（T13「待整理」）→ 采纳 **ISO 21771 / AGMA 2002-D19 / GB/T 3374.1-2010 负齿数模型**约定，以 ADR-015 显式记录销 T13 部分；依据研究文档 `docs/research/内齿轮工件几何.md`。
3. **同源一致**：同一 `GearParams`、同一次计算，2D/3D 误差 ±0.0001mm（与既有约定一致）。
4. **不引入非标准齿廓**：`d_a < d_b` 低齿数情形**阻塞**（诚实 400 + 用户提示），不做 FreeCAD 式直段近似。

## 2. 决策树（grilling 结论 Q1–Q9）

| 决策点 | 结论 |
|--------|------|
| 范围 | 待加工齿轮板块内齿轮工件几何；k_io 语义留待模块② |
| Q1/Q9 齿圈外径 | 新增 `d_rim` 参数（`k_io=−1` 时「基本」区显示）；可选；有效值钳制到 `d_f + 2·m_n` 下限（轮缘厚 1×m_n/侧，避免 `d_rim=d_f` 退化环无法剖分）；规格表 inputs 增行 |
| Q2 齿厚方式 | 内齿支持 `x_w` + `M`；`W_k` 内齿禁用（灰置）——依据：内齿 W_k 定义差一个基节 + 工程上难测；**不按「外齿轮公式翻 x」实现**（研究已否决该写法） |
| Q3 齿顶/齿根修饰 | 内齿 v1 整区灰置（锐齿顶 + 锐齿根，`rho_f_actual=0`） |
| Q4 斜齿 | **内斜齿 v2 已支持**（ADR-017，2026-08-12 销「仅直齿」）；`β_w>0` 构建扭转齿孔实体；前端解除灰置/自动归零 |
| Q5 变位 x 约定 | ISO 负齿数模型（+x 内齿变厚）：`s_t=π·m_t/2+2x·m_n·tanα_t`，`d_a=z·m_t−2(h_an+x)m_n`，`d_f=z·m_t+2(h_an+c_n−x)m_n`；**全齿高不变量 `h=(d_f−d_a)/2=2h_an+c_n` 加断言** |
| Q6 验收锚点 | 自洽数学 + 不变量断言 + `M` 正反解往返 + 轮廓/面积回归；外齿 golden 全绿 |
| Q7 研究文档 | ✅ `docs/research/内齿轮工件几何.md`（作为 ADR-015 依据） |
| Q8 低齿数 | `d_a < d_b` 时阻塞 400 + 用户提示「内齿轮齿顶圆低于基圆，渐开线无法到达齿顶——请增大齿数/减小齿顶高/增大压力角」 |

## 3. 组件与模块架构

```
后端 (Python；几何在 profile.py/models.py 纯数学可进 CI，OCCT 仅在 builder/exporter)
backend/core/workpiece/
├── models.py      # k_io 感知 d_a/d_f + d_rim 字段 + __post_init__ 校验（内齿约束）
├── profile.py     # 内齿齿廓：材料外侧、齿顶/齿根弧方向翻转、锐顶+锐根
├── builder.py     # 内齿环形实体：MakeFace(外圈 d_rim).Add(内齿廓为孔)→Prism；斜齿守卫
├── exporter.py    # _extract_boundary_cycle 返回全部边界环；双边界侧壁（外壁+内齿壁）
├── spec.py        # 内齿 d_a/d_f 语义、d_rim inputs 行、outline 加 rim 圆
├── router.py      # GearParamsRequest + d_rim + k_io 校验错误 400
└── tests/
    ├── test_workpiece.py  # 内齿公式不变量 / 齿廓形状 / 校验错误
    ├── test_exporter.py   # 环形 mesh 闭合/流形 + 外齿回归
    ├── test_spec.py       # 内齿规格语义 + 一致性
    ├── test_api.py        # 契约 + d_rim/错误
    └── test_models.py     # M 内齿往返 + 全齿高不变量

前端 (Vue) — 集中在步骤1 面板 + 类型
src/
├── composables/useGearParams.ts   # + d_rim 字段/载荷/默认
├── api/spec-types.ts              # 契约类型同步（spec-types 若含 d_rim）
└── components/
    └── GearParamsPanel.vue        # 内齿模式：d_rim 输入、W_k 灰置、修饰区灰置、β 禁用、自动重置、d_p 占位
```

## 4. 几何定义

### 4.1 符号约定（ISO 负齿数模型，Q5）

内齿轮材料位于齿面**外侧（环侧）**，齿顶为小径、齿根为大径：

```
s_t = π·m_t/2 + 2·x_w·m_n·tan(α_t)        # 分度圆齿厚，+x 内齿变厚（与外齿轮同式）
d_a = z·m_t − 2·(h_an + x_w)·m_n          # 齿顶小径
d_f = z·m_t + 2·(h_an + c_n − x_w)·m_n    # 齿根大径
```

**全齿高不变量（实现必加断言）**：`h = (d_f − d_a)/2 = 2·h_an + c_n`，与 `x_w` 无关。实现若使该式随 x 漂移即符号写反（研究给出的物理硬判据）。

### 4.2 齿廓构造（profile.py，Q5/Q3）

- 内齿齿廓为**同一渐开线族**（同一基圆），但齿面自齿顶（小径）延伸至齿根（大径），材料在齿面外侧。
- **手性互补**（ADR-016）：内齿齿槽 = 外齿齿形，故左齿面用镜像模板、右齿面用原模板，放置角 ∓(half − inv(α_t))；齿宽半角 ψ(r)=half−inv(α_t)+inv(α_r)，向齿根（大径）变宽。研究④「渐开线齿面形状不变」仅指曲线族相同，手性搭配须互补——首版实现照搬外齿模板致截面锯齿，已修正。
- **无修饰**（Q3）：锐齿顶 + 锐齿根，无齿根圆角、无齿顶圆角/倒角 → 内齿不调用 `solve_root_fillet` / tip 处理。

### 4.3 环形实体（builder.py，Q1）

内齿轮实体 = **环形**：外边界 = 有效齿圈外径 `effective_rim_diameter() = max(d_rim, d_f + 2·m_n)`（缺省取 `d_f + 2·m_n`，Q9），内边界 = 内齿廓（齿顶小径处的齿形孔）。`MakeFace(外圈 wire)` + `.Add(内齿廓 wire)` 成带孔 face → `Prism`。⚠️ 内齿廓 wire 需**拓扑 REVERSED** 才被 OCCT 识别为孔（非几何顺序，T02 探针）。斜齿内齿守卫（`k_io=−1 ∧ β_w>0 → 400`，Q4）。

### 4.4 可行性约束（Q8 + 研究③）

| 约束 | 规则 | 行为 |
|---|---|---|
| 齿顶 ≥ 基圆 | `d_a ≥ d_b`（渐开线有效齿廓存在条件，标准 20°、x=0 参考 z≥34） | 违反 → 400 + 用户提示（Q8） |
| 齿顶宽 > 0 | 内齿齿顶弦厚 > 0（两齿面在齿顶处不交叉） | 违反 → 400 |
| 齿圈外径 | 有效值钳制 `max(d_rim, d_f + 2·m_n)`（Q9 避免退化环） | 无 400，自动钳制并回报有效值 |
| 螺旋角 | 内齿仅直齿，`β_w = 0` | 违反 → 400（前端已灰置） |
| 齿厚重叠 | `s_t < π·m_t`（与现状同判据，内齿物理同样成立） | 违反 → 400 |
| 齿厚方式 | 内齿仅 `x_w`/`M`，`W_k` 禁用 | `W_k` → 400（前端已灰置） |

## 5. API 契约

### `POST /api/workpiece/generate`（扩展）

请求 `GearParamsRequest` 新增：

```jsonc
{
  // ...既有字段不变
  "k_io": -1,        // 内齿
  "d_rim": null      // 齿圈外径 [mm]，可选；有效值钳制 ≥ d_f + 2·m_n (Q9)
}
```

响应（200）结构不变。`result` 的 `d_a`（内齿为小径）/`d_f`（内齿为大径）语义随 `k_io`。`spec.params.inputs` 新增 `d_rim` 行（内齿）；`spec.outline.circles` 新增 `rim_radius`（内齿）。

错误契约 `{ "error": ..., "code": 400 }` 不变；内齿校验失败均 400（非 500）。

### 参数注册三处同步

1. `models.py` — `GearParams.d_rim: float | None` + `__post_init__` 内齿校验。
2. `router.py` — `GearParamsRequest.d_rim: Optional[float]` + `to_gear_params()` 透传。
3. `spec.py` — `INPUT_ITEMS` + `d_rim` 行（内齿）；`outline` + `rim_radius`。

前端 `useGearParams.ts` 同步 `d_rim` 字段/载荷/默认。

## 6. 前端行为（GearParamsPanel.vue）

`k_io=−1` 时：
- **「基本」区**：显示「齿圈外径 d_rim」输入（占位「缺省 = 齿根圆」）；`β_w` + 旋向灰置（若切到内齿前 `β_w≠0`，自动归零 + 一行提示「内齿 v1 暂不支持斜齿」）。
- **「齿厚」区**：「公法线」按钮灰置（保留 变位/跨棒距）；`M` 模式 `d_p` 占位 `≈1.44×m_n`（外齿保持 `≈1.68×m_t`）。
- **「齿顶/齿根修饰」区**：整区灰置 + 提示「内齿 v1 暂不支持修饰」。
- **自动重置**：切外齿→内齿时，若 `toothMethod=W_k` → 重置 `x_w`；`tip_mode≠none` → 重置 `none`；`β_w≠0` → 归零。均伴随一行提示。

## 7. 缺口与边界

- **T13 部分销项**：采纳 ISO 变位约定销「齿厚符号待整理」；**W_k 内齿仍不实现**（研究确认内齿 W_k 定义差一个基节、工程上难测 → 不作为主计量输入）。
- **内齿 v1 不做**：齿顶/齿根修饰（Q3，内斜齿同）、啮合副干涉约束（需配对齿轮输入，留模块②）。**内斜齿（Q4）已于 2026-08-12 销项**（ADR-017，§11）。
- **M 奇偶区分**：沿用偶数齿公式简化（与现状外齿一致），已知简化并记录。
- **d_p 内齿推荐值 1.44×m_n**：medium confidence（Machinery's Handbook 规则换算），作为前端占位；实际值按齿面接触点由设计人员确定。
- **设计书权威性**：内齿轮几何公式设计书未覆盖（T13），本规格以 ISO 约定为准并 ADR 记录；与设计书后续章节冲突时以设计书为准（若其补订）。

## 8. 测试策略

| 层 | 文件 | 依赖 | 内容 |
|----|------|------|------|
| 零变化回归 | `test_exporter.py` / `test_workpiece.py` 扩充 | 无 OCCT 可跑 | `k_io=1` 与现状逐点一致（golden 护栏） |
| 内齿公式 | `test_models.py` | 无 OCCT | `d_a<d_f`、`d_a=z·m−2(h_an+x)m`、`d_f=z·m+2(h_an+c_n−x)m`、**全齿高不变量随 x 不漂移** |
| M 往返 | `test_models.py` | 无 OCCT | 内齿 `x_w→M→x_w` 收敛（跨棒距内齿公式 `cosα_M=d_b/(M+d_p)`） |
| 齿廓形状 | `test_workpiece.py` | 无 OCCT | 内齿齿顶弧为小径、齿根弧为大径、锐顶锐根、材料外侧 |
| 环形实体 | `test_workpiece.py` / `test_exporter.py` | OCCT | 带孔 face 面积≈环形面积；mesh 双边界闭合/流形 |
| 校验错误 | `test_workpiece.py` / `test_api.py` | TestClient | `d_rim<d_f`、`d_a<d_b`、`β_w>0`、`W_k` → 400 |
| 既有测试 | — | — | 外齿轮全部测试保持绿 |
| 前端组件 | `GearParamsPanel` 单测 | mock + Vitest | 内齿模式：d_rim 显示、W_k 灰置、修饰灰置、β 禁用、自动重置、d_p 占位 |

## 9. 交付分阶段（每阶段独立验收）

1. **① 后端几何 + 回归**：`models.py` k_io 感知 d_a/d_f + `profile.py` 内齿齿廓 + 全齿高不变量断言 + 纯 Python 单测。门禁：外齿 golden 全绿 + 内齿不变量绿。
2. **② 环形实体 + exporter**：`builder.py` 带孔 face + `exporter.py` 双边界侧壁 + OCCT 集成测试（面积/闭合/流形）。
3. **③ 契约三处注册 + API**：models/router/spec + `d_rim` + `test_api.py` 内齿错误契约。
4. **④ 前端 + 规格窗口**：`useGearParams` + `GearParamsPanel` 内齿模式 + `spec.py` 内齿规格语义 + 前端单测。
5. **⑤ 文档 + ADR**：ADR-015 + 本文档 + `CONTEXT.md` 词汇/记录。

## 10. 文件变更清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `backend/core/workpiece/models.py` | 修改 | `GearParams.d_rim` + k_io 感知 `tip_radius/root_radius/tip_diameter/root_diameter` + 内齿校验 + 全齿高不变量 |
| `backend/core/workpiece/profile.py` | 修改 | 内齿齿廓（材料外侧、弧方向翻转、锐顶锐根） |
| `backend/core/workpiece/builder.py` | 修改 | 内齿环形实体（带孔 face → Prism）；斜齿守卫 |
| `backend/core/workpiece/exporter.py` | 修改 | `_extract_boundary_cycle` 多环 + 双边界侧壁 |
| `backend/core/workpiece/spec.py` | 修改 | 内齿 d_a/d_f 语义、`d_rim` inputs 行、outline `rim_radius` |
| `backend/core/workpiece/router.py` | 修改 | `d_rim` + k_io 校验错误 |
| `backend/core/workpiece/tests/*.py` | 修改/新增 | 内齿公式/往返/形状/环形/mesh/校验/回归 |
| `src/composables/useGearParams.ts` | 修改 | `d_rim` 字段/载荷/默认 |
| `src/api/spec-types.ts` | 修改 | 契约类型同步 |
| `src/components/GearParamsPanel.vue` | 修改 | 内齿模式（d_rim、灰置、自动重置、d_p 占位） |
| `CONTEXT.md` | 修改 | ADR-015 + 内齿轮/d_rim 词汇 |
| `docs/specs/2026-08-12-internal-gear-design.md` | 新增 | 本文档 |
| `docs/research/内齿轮工件几何.md` | 新增 | 研究依据（已落盘） |

## 11. 内斜齿 v2（ADR-017，2026-08-12 销 Q4「仅直齿」）

### 11.1 几何事实

- 斜齿轮各 z 截面为彼此**旋转副本**；**圆旋转仍是同一圆** → 内斜齿外 rim 天然保持直圆柱（mesh 中 rim 顶点位置不变），仅内齿孔（齿面/齿槽）绕轴扭转。
- 扭转量 `θ(z) = j_w·z·tan(β_w)/r_pw`（与既有外斜齿同一公式，G4 锚定）。
- **Q8 (d_a≥d_b) β 感知**：β 增大 → `α_t` 增大 → `cos α_t` 减小 → `d_b` 相对 `d_a` 变小 → **最小齿数阈值下移**。量化（20°、x=0）：β=0° z≥34；β=30° z≥23；z=28 在 β=0 阻塞、β=30 放行（G10）。因此 Q8 提示**不加**「减小螺旋角」（减小 β 反而收紧）。

### 11.2 实体构造（Boolean Cut，spike 实证）

```
1) 预形   = 全圆柱 [d_rim]（Prism，直）
2) 齿孔   = ThruSections 扭转 gear_profile（单闭合 wire/截面, Solid=True,
            θ(z) 逐截面旋转, n_involute=8 / 截面数 min(n_slices,4) 粗放样控速）
3) Cut    = BRepAlgoAPI_Cut(全圆柱, 齿孔实体)  ← 单工具布尔
4) cap_face = 端面环形 face（外 rim + 内齿廓孔 REVERSED）供 exporter mesh
```

- **渲染 mesh 程序化、精确**（exporter 自 cap_face + helical_sections 放样，与外斜齿同构）；solid 供体积/STEP/校验，粗放样体积误差 <0.1%（G7 基准解析体积，rel 5e-3）。
- 备选 gap-cut（环形预形 `[d_rim→d_a]` − 复合 z_w 齿槽实体 `tooth_gap_segments`）spike 亦鲁棒但复合工具 BOP 成本更高（z=41 n_inv=40 达 100s）；回退方案（全圆柱 − 复合[直孔+齿槽]）碎裂成 69 solids，**弃用**。
- 性能：solid 布尔构建 5–25s ∝ z（交互可接受；未来可懒构建/异步，router 只用 GLB mesh）。`tooth_gap_segments`（齿槽廓形）仍保留——与 `single_tooth_segments`（齿形）互补铺满 `[d_a, d_f]` 环带，作为纯数学不变量与备选构造依据。

### 11.3 计量与前端

- **M 沿用直齿近似** `cosα_M = d_b/(M + d_p)`（与既有外斜齿一致）；真斜齿 over-balls（基圆螺旋角 `β_b`、虚拟量棒径 `d_pt=d_p/cosβ_b`、`z_v=z/cos³β`）留档后续 ADR。
- `W_k` 仍禁用、齿顶/齿根修饰仍禁用、`d_rim` 钳制沿用（ADR-015）。
- 前端：解除 β_w 灰置、删除「切内齿时 β 归零」自动重置、internalNotice 文案改「内齿轮：直齿/斜齿均支持；W_k 与齿顶/齿根修饰暂不开放」、旋向选择器随 β>0 正常显示。

### 11.4 验收门禁（新增，G3–G10）

| # | 不变量 | 判据 |
|---|--------|------|
| G3 | rim 直线性 | 侧壁顶点最大半径恒为 d_rim/2，不随 z 漂移 |
| G4 | 扭转正确性 | 齿顶带顶点去扭相位 `φ=(角度−θ(z)) mod (2π/z)` 聚集 |
| G5 | mesh 闭合/流形 | 每条焊边恰被 2 个三角形共享 |
| G6 | 内孔法向 | 内齿孔侧壁法向朝孔心（负径向） |
| G7 | 体积 | solid 体积 ≈ (π(r_rim²−r_a²) − z_w·gap_area)·b_w（解析，rel 5e-3） |
| G8 | 跨表示一致 | spec 2D 齿廓点与 3D mesh 端面 (z=0) 顶点距离 < 0.6mm |
| G9 | 极限组合 | 低齿数高β（z=28/β=30）、高β宽齿宽（β=30/b_w=40）构建有效 + 体积≈解析 |
| G10 | Q8 β 感知 | z=28 β=0 阻塞 / β=30 放行；d_a≥d_b 边界两侧正确 |
