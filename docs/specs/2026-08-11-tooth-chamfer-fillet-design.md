# 齿顶倒角/圆角 + 齿根圆角开关 — 设计规格

**日期**：2026-08-11
**状态**：已设计（grilling 交互访谈确认，待实现）
**需求来源**：交互访谈（grilling）——「面板上齿顶倒角/齿顶圆角的勾选、切换及输入，齿根圆角的勾选及输入；后端调用 OCCT 完成建模的倒角/圆角操作；前端模型及 2D 端面显示；风格与 UI 协调；谨守架构防线」

## 1. 目标

在步骤1 齿轮参数面板新增「齿顶/齿根修饰」板块，控制齿顶与齿根的轮廓修饰：

- **齿顶处理**：三态分段控件 `[无|倒角|圆角]` + 各自数值输入（系数 × mₙ）。
- **齿根圆角**：勾选开关（默认开 = 0.38）+ 数值输入。
- **建模路径**：解析几何落在共享 `profile.py::_tooth_open_segments`（与 `solve_root_fillet` 同构）；OCCT 照常 `MakeFace → Prism/ThruSections` 建实体、`BRepMesh` 剖分出 GLB。**后端仍调用 OCCT 完成建模**——倒角/圆角轮廓本身是解析几何，与现有齿根圆角同一套路。
- **显示**：3D GLB 与 2D 端面（单齿廓 / 整体轮廓 / 规格表）**同源**更新。
- **超限行为**：自动收敛到可容纳上限 + 信息色软提示「已取最接近请求值」，不硬错、不无声。

**核心约束**：
1. **默认参数零变化**：`tip_mode=none` + `root_fillet=true` + `rho_tip=0` 时输出与现状**逐点一致**（abs=1e-12）。默认路径代码字面不动，仅在激活模式插入新段。
2. **同源一致**：同一 `GearParams`、同一次计算，2D/3D 误差 ±0.0001mm；前端不重算任何几何（ADR-010）。
3. **定义平面 = 端面（transverse）**：与现有全部齿廓数学（K-1.1/K-1.13）一致；斜齿放样逐截面自动携带。
4. **齿顶倒角/倒圆不在设计书参数字典**（ADR-013 缺口）→ 落地即正式扩展权威源之外，需写 **ADR-014** 显式记录，并保默认零变化优先。

## 2. 决策树（grilling 结论）

| 决策点 | 结论 |
|--------|------|
| 建模路径 | 解析式落 `_tooth_open_segments`（销 ADR-013）；OCCT 仍建实体+剖分 |
| 交互形态 | 三态分段控件 `[无\|倒角\|圆角]`（`glass-segmented` 模式），互斥、各自输入框 |
| 圆角值 | 复用 `rho_tip`（系数 × mₙ，已有字段） |
| 倒角值 | 新字段 `chamfer_tip`（系数 × mₙ，45° 沿齿面量取） |
| 齿根开关 | `root_fillet: bool` 默认 true=0.38（零变化）；取消=锐齿根（径向线回退兜底）；仅圆角、复用 `rho_f` |
| 触发时机 | 新参数组响应式 watch + 防抖 ~300ms 自动重生成；不动 m_n/z_w 等原有参数 |
| 面板布局 | 新折叠板块「齿顶/齿根修饰」；`ρ_f` 从「高级」移入 |
| 倒角定义 | 相对齿面 45°，尺寸沿齿面量取 c·mₙ（构造唯一）；角度固定 45° |
| 定义平面 | 端面 transverse |
| 超限行为 | 自动收敛到可容纳上限 + 回报实际值 |
| 软提示 | 实际≠请求时面板内联信息色提示「已取最接近请求值」；相等时隐藏 |
| 契约 | `tip_mode:"none"\|"chamfer"\|"round"`、`chamfer_tip`、`rho_tip`（已有）、`root_fillet:bool`(默认 true，独立开关，不 overload rho_f=0) |
| 记录 | ADR-014「齿顶倒角/圆角产品扩展」 |

## 3. 组件与模块架构

```
后端 (Python；几何在 profile.py 纯数学可进 CI，OCCT 仅在 builder/exporter)
backend/core/workpiece/
├── models.py      # GearParams + tip_mode/chamfer_tip/root_fillet + __post_init__ 校验
├── profile.py     # _tooth_open_segments 移除 ADR-013 门禁；新增 tip round / tip chamfer 段
├── spec.py        # INPUT_ITEMS/OUTPUT_ITEM_SPECS + annotations 适配 tip_mode/chamfer_actual
├── router.py      # GearParamsRequest + 新字段 + to_gear_params 透传
└── tests/
    ├── test_workpiece.py  # 齿顶圆角双切 / 倒角构造 / 齿根开关
    ├── test_exporter.py   # 零变化回归 + GLB 段数/几何
    ├── test_spec.py       # 一致性 + 收敛回报
    └── test_api.py        # 契约 + 错误

前端 (Vue) — 改动集中在步骤1 面板 + 2D 标注
src/
├── composables/useGearParams.ts   # 新字段 + toPayload + 收敛实际值共享 store
├── api/spec-types.ts              # 契约类型同步
├── components/
│   ├── GearParamsPanel.vue        # 新增「齿顶/齿根修饰」板块 + 三态控件 + 软提示
│   ├── WorkpieceViewer.vue        # （生成链已存在，防抖 watch 触发点）
│   └── ToothProfileSvg.vue        # 标注随 tip_mode 切换
```

## 4. 几何定义（profile.py）

### 4.1 齿顶圆角 (round)

双切圆角：切齿面（渐开线）+ 切齿顶弧，半径 `ρ*_tip·m_n`，**与 `solve_root_fillet` 对称**。在 `_tooth_open_segments` 中把单段尖角齿顶弧替换为「左倒圆弧 + 齿顶弧 + 右倒圆弧」。`ρ*_tip=0` 或 `tip_mode≠round` 走原路径**零变化**。

### 4.2 齿顶倒角 (chamfer)

相对齿面 45° 构造：
1. 从尖角沿渐开线齿面向内量 `c·m_n` 得切点 `P_f`；
2. 过 `P_f` 画与齿面切线成 **45°** 的直线；
3. 该直线与齿顶弧交于 `P_t`；倒角段 = `P_f → P_t` 直线。

齿顶弧缩短为两切点之间。**构造唯一确定**。角度固定 45°，只输入尺寸系数。

### 4.3 齿根圆角 (root)

复用现有 `solve_root_fillet`。`root_fillet=false` 时**跳过求解**，走现有径向线回退路径（`r_b > r_f` 无圆角态）。

### 4.4 超限收敛

请求系数超过齿顶弧可容纳上限 → 收敛到**最大可行值**；输出项回报实际值（`rho_tip_actual` / `chamfer_actual`）。与 ADR-011「双切无解回退径向线（诚实占位）」同一哲学。

## 5. API 契约

### `POST /api/workpiece/generate`（扩展）

请求 `GearParamsRequest` 新增：

```jsonc
{
  // ...既有字段不变
  "tip_mode": "none",        // "none" | "chamfer" | "round"
  "chamfer_tip": 0.0,        // 倒角尺寸系数 ×m_n，ge=0
  "rho_tip": 0.0,            // 已有：圆角半径系数 ×m_n，ge=0
  "root_fillet": true        // 齿根圆角开关
}
```

响应（200）不变结构，`spec.params.outputs` 新增 `chamfer_actual`（实际收敛倒角尺寸 ×m_n）；`rho_tip_actual` 既有（实际收敛圆角半径 ×m_n）。`spec.single_tooth.annotations.tip_fillet` 语义随 `tip_mode`：`round`→圆角半径，`chamfer`→倒角尺寸（配合 45°），`none`→不显示。

### 参数注册三处同步

1. `models.py` — `GearParams` 字段 + `__post_init__` 校验（`chamfer_tip ≥ 0`；`tip_mode ∈ {none,chamfer,round}`）。
2. `router.py` — `GearParamsRequest` Pydantic 字段 + `to_gear_params()` 透传。
3. `spec.py` — `INPUT_ITEMS` / `OUTPUT_ITEM_SPECS` / `annotations`。

前端 `spec-types.ts` 同步契约类型。错误契约 `{ "error": ..., "code": 400 }` 不变。

## 6. 前端行为

### 6.1 「齿顶/齿根修饰」板块（GearParamsPanel.vue）

- 新增 `glass-collapse` 折叠板块，`ρ_f` 从「高级」板块移入。
- 齿顶处理：`glass-segmented` 三态控件 `[无|倒角|圆角]`，选中态显示对应数值输入（`chamfer_tip` / `rho_tip`），互斥。
- 齿根：勾选（默认开）+ `rho_f` 数值输入。

### 6.2 自动重生成（T01 裁决：导航式，Q4-A）

实现时发现 MainPanel 用 `v-if` 按步骤挂载：`GearParamsPanel`（步骤1）与 `WorkpieceViewer`（步骤2）**永不同时挂载**，`WorkpieceViewer` 在**挂载时**用最新参数重新生成。故每次进入步骤2 已用最新参数生成——「勾选改动 → 模型反映」由导航式重生成自然满足。**不写防抖 watch（当前导航下为死代码）**。若后续需要真·实时预览（面板常驻 + 生成逻辑提升到 MainPanel/共享 composable），另立票。

### 6.3 收敛软提示

- 实际 ≠ 请求时：输入框下方出现**信息色** `glass-field-hint`（非 error 红）：「已取最接近请求值 X」（X 为实际收敛值）。
- 请求 = 实际时：**不显示**（零干扰）。
- 回灌路径：`spec.params.outputs` 的实际值经**共享 store** 回灌到面板（面板只读写参数 store，不碰 API，守架构防线）。

### 6.4 2D 标注适配

`ToothProfileSvg` 的齿顶标注随 `tip_mode`：`齿顶R` ↔ `齿顶倒角 C×45°` ↔ 无。规格表 `inputs` 含新参数、`outputs` 含 `chamfer_actual` / `rho_tip_actual`。

## 7. 缺口与边界

- **ADR-013 销项**：本功能落地即 resolve（原缺口记录迁移/更新至 ADR-014）。
- **斜齿（β≠0）**：段级几何逐截面携带，ThruSections 放样正常，无特殊处理。
- **内齿轮 `k_io=-1`**：沿用现状，不扩展不修复（同既有约定）。
- **`rho_f=0` 现状语义未定义**：不 overload 为「关闭」；开关用独立 `root_fillet` 布尔。

## 8. 测试策略

| 层 | 文件 | 依赖 | 内容 |
|----|------|------|------|
| 零变化回归 | `test_exporter.py` / `test_workpiece.py` 扩充 | 无 OCCT 可跑 | `tip_mode=none + root_fillet=true + rho_tip=0` 与旧实现逐点一致（abs=1e-12） |
| 齿顶圆角 | `test_workpiece.py` | 无 OCCT | 双切切点 G1 连续；`rho_tip=0` 零变化 |
| 齿顶倒角 | `test_workpiece.py` | 无 OCCT | 沿齿面量取 c·m_n、与齿面切线 45°、交齿顶弧；构造唯一性 |
| 超限收敛 | `test_spec.py` | 无 OCCT | 请求超上限收敛到最大可行值，`*_actual` 回报实际 |
| 齿根开关 | `test_workpiece.py` | 无 OCCT | `root_fillet=false` 段数/几何正确（无圆角态） |
| 斜齿 | `test_exporter.py` | OCCT 集成 | β≠0 逐截面携带倒角/圆角，放样正常 |
| 既有测试 | — | — | `TestRootFillet`/`TestProfileShape`/`TestVolumeAndBounds`/`TestCrossRepresentationConsistency` 默认参数下保持绿 |
| 契约 | `test_api.py` | TestClient | 新字段透传、spec 输出、错误契约不变 |
| 前端组件 | `GearParamsPanel`/`ToothProfileSvg` 单测 | mock spec + Vitest | 三态控件、互斥输入、软提示显隐、标注切换 |

## 9. 交付分阶段（对冲「不顺利」，每阶段独立验收）

1. **① 后端几何 + 回归**：`profile.py` 倒角/圆角 + 零变化回归 + 新几何单测（纯 Python，可独立验证）。门禁：默认参数全绿。
2. **② 契约三处注册 + API 测试**：models/router/spec + `spec-types.ts` + `test_api.py`。
3. **③ 前端面板 / watch / 重生成**：「齿顶/齿根修饰」板块 + 三态控件 + 防抖 watch + 软提示。
4. **④ 2D 标注 + 规格表 + ADR-014**：标注适配 + 规格表 + CONTEXT.md ADR 记录。

## 10. 文件变更清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `backend/core/workpiece/profile.py` | 修改 | `_tooth_open_segments` 移除 ADR-013 门禁，齿顶圆角/倒角段 |
| `backend/core/workpiece/models.py` | 修改 | `GearParams` + `tip_mode`/`chamfer_tip`/`root_fillet` + 校验 |
| `backend/core/workpiece/router.py` | 修改 | `GearParamsRequest` + `to_gear_params` |
| `backend/core/workpiece/spec.py` | 修改 | `INPUT_ITEMS`/`OUTPUT_ITEM_SPECS` + `chamfer_actual` + annotations |
| `backend/core/workpiece/tests/*.py` | 修改/新增 | 零变化回归、几何、收敛、契约 |
| `src/composables/useGearParams.ts` | 修改 | 新字段 + `toPayload` + 收敛实际值 store |
| `src/api/spec-types.ts` | 修改 | 契约类型同步 |
| `src/components/GearParamsPanel.vue` | 修改 | 「齿顶/齿根修饰」板块 + 三态控件 + 软提示 |
| `src/components/WorkpieceViewer.vue` | 修改 | 防抖 watch 触发重生成 |
| `src/components/ToothProfileSvg.vue` | 修改 | 齿顶标注随 `tip_mode` 切换 |
| `CONTEXT.md` | 修改 | ADR-014 记录 + ADR-013 销项 |
| `docs/specs/2026-08-11-tooth-chamfer-fillet-design.md` | 新增 | 本文档 |
