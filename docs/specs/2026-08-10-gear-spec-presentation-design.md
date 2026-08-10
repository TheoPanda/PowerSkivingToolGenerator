# 齿轮规格呈现窗口 — 设计规格

**日期**：2026-08-10
**状态**：已实现（2026-08-10 修订：独立窗口 + annotations 契约）
**需求来源**：`backend/requirements for gear spec.md`（齿轮规格呈现功能模块需求文档）

## 1. 目标

生成待加工齿轮后，用户通过一个独立的 Electron 窗口（BrowserWindow）直观核对齿轮规格：

- **左上 · 单齿廓图**：端面单齿廓（齿廓线/中心线/分度线，ISO 线型区分），标注 7 项尺寸：齿厚、齿距、齿顶圆角、齿根圆角、齿顶高、齿底高、齿全高。
- **左下 · 齿轮2D整体轮廓图**：全齿圈轮廓 + 齿顶圆/齿根圆/分度圆，支持缩放、平移、悬停某齿高亮 + tooltip 齿序号。
- **右侧 · 参数规格表**：全量只读清单（输入 + 解算结果），行选中 + 复制。

**核心约束**：表格数值、单齿廓标注、整体轮廓三者的几何**必须同源**——全部由后端 `POST /api/workpiece/generate` 用**同一 `GearParams` 实例、同一次计算**产生，验收误差 ±0.0001mm。前端**不重算任何几何**。

**设计书对齐**：spec 的 2D 几何只消费 `profile.py` 权威输出（`single_tooth_segments` / `sample_profile_points`），参数数值只消费 `models.py` 方法（`tip_diameter` / `compute_tooth_thickness` 等），与 3D GLB 属同一齿形数学。

## 2. 组件与模块架构

```
后端 (Python，spec.py 纯数学无 OCCT，可进 CI)
backend/core/workpiece/
├── models.py      # GearParams + rho_tip（齿顶倒圆系数，默认 0）
├── profile.py     # _tooth_open_segments 共享段实现齿顶倒圆（默认 0 零变化）
├── spec.py        # 新增 build_spec(p) — 参数表 + 单齿廓 + 整体轮廓序列化
├── router.py      # GearParamsRequest + rho_tip；WorkpieceResponse + spec
└── tests/
    ├── test_spec.py   # 新增 — 纯数学一致性/定标回归
    └── test_api.py    # 扩充 — spec 契约

前端 (Vue/SVG) + Electron 独立窗口
spec.html + src/spec-window.ts        # 齿轮规格独立窗口入口（BrowserWindow 加载）
src/
├── api/index.ts                      # Spec 类型 + WorkpieceResponse.spec + rho_tip + AnnotationEntry
├── components/
│   ├── SpecWindowRoot.vue            # 独立窗口根组件（左图右表，IPC 收 spec:data）
│   ├── ToothProfileSvg.vue           # 单齿廓 + ISO 标注（消费 annotations.value）
│   ├── GearOutlineSvg.vue            # 整体轮廓 + 缩放/平移/悬停
│   ├── SpecTable.vue                 # 规格表 + 复制
│   ├── dimension.ts                  # ISO 尺寸标注工具集
│   └── WorkpieceViewer.vue           # 「查看齿轮规格」→ electronAPI.openSpecWindow
electron/
├── main.ts                           # spec:open 建/聚焦独立窗口 + spec:data 推送
└── preload.ts                        # openSpecWindow / getSpecData / onSpecData
vite.config.ts                        # 多页入口 index.html + spec.html
```

## 3. 数据流

```
GearParamsPanel (步骤1) → MainPanel reactive gearParams
    ↓ inject
WorkpieceViewer (步骤2) → fetchWorkpiece(gearParams)   [onMounted 自动生成]
    ↓ HTTP POST /api/workpiece/generate
backend: p = req.to_gear_params()
    ├── build_gear_model(p) → GLB base64
    └── build_spec(p)       → spec（同一 p，保证 ±0.0001mm 一致性）
    ↓ HTTP response { result, model_glb_base64, spec }
WorkpieceViewer ← 存 spec 到 ref
    ↓ 点击「查看齿轮规格」
electronAPI.openSpecWindow(spec) → ipcRenderer.invoke('spec:open')
    ↓ 主进程新建/聚焦独立 BrowserWindow 加载 spec.html
    ↓ did-finish-load → webContents.send('spec:data', spec)（SpecWindowRoot 兜底 getSpecData）
SpecWindowRoot ← spec
    ├── ToothProfileSvg  ← spec.single_tooth
    ├── GearOutlineSvg   ← spec.outline
    └── SpecTable        ← spec.params
```

## 4. API 契约

### `POST /api/workpiece/generate`（扩展）

请求：`GearParamsRequest` 新增 `"rho_tip": 0.0`（齿顶倒圆系数，`ge=0`），其余不变。

响应（200）新增顶层字段 `spec`：

```jsonc
{
  "result": { "d_a": 107.5, "d_f": 96.25, "r_b": 48.164, "r_pw": 51.25, "m_t": 2.5, "alpha_t_deg": 20.0, "z_w": 41 },
  "model_glb_base64": "AAAA...",
  "spec": {
    "params": { "inputs": [...], "outputs": [...] },
    "single_tooth": { "segments": [...], "center_line": {...}, "pitch_line": {...}, "annotations": {...} },
    "outline": { "points": [...], "teeth": [...], "circles": {...} }
  }
}
```

### spec.params — 参数规格表（全量只读）

`inputs` 每项 `{key, label, symbol, value, unit}`（约 13 项）：`m_n` 法向模数 / `z_w` 工件齿数 / `alpha_n_deg` 法向压力角 / `beta_w_deg` 螺旋角 / `x_w` 变位系数 / `j_w` 旋向 / `b_w` 齿宽 / `k_io` 内外齿 / `h_an` 顶高系数 / `c_n` 顶隙系数 / `rho_f` 齿根圆角系数 / `rho_tip` 齿顶倒圆系数 / `tooth_method` 齿厚方式。

`outputs` 每项同上（约 14 项，来源全部是 `GearParams` 现有方法，**不二次实现**）：

| key | 含义 | 来源 |
|---|---|---|
| `d_pw` | 分度圆直径 | `2·pitch_radius()` |
| `d_a` | 齿顶圆直径 | `tip_diameter()` |
| `d_f` | 齿根圆直径 | `root_diameter()` |
| `d_b` | 基圆直径 | `2·base_radius()` |
| `m_t` / `alpha_t_deg` | 端面模数/端面压力角 | `to_transverse()` |
| `s_t` | 分度圆弧齿厚 | `compute_tooth_thickness()` |
| `s_n` | 法向齿厚 | `s_t·cos(β_w)` |
| `p_t` | 端面齿距 | `π·m_t` |
| `h_a` | 齿顶高 | `h_an·m_n` |
| `h_f` | 齿底高 | `(h_an+c_n)·m_n` |
| `h` | 齿全高 | `h_a + h_f` |
| `rho_f_actual` | 齿根圆角半径 | `rho_f·m_n` |
| `rho_tip_actual` | 齿顶倒圆半径 | `rho_tip·m_n` |

### spec.single_tooth — 单齿廓 + 标注

- `segments`：`single_tooth_segments(p)` 序列化。`Arc` → `{"type":"arc","radius","a0","a1","center":[x,y],"clockwise"}`（a0/a1 为 rad，后端已 unwrap 为短弧；`clockwise=true`→CW 凹角，SVG `sweep=0`）；`Polyline` → `{"type":"polyline","points":[[x,y],...]}`。SVG 段：arc→`M`+`A`（`large-arc=0`），polyline→`L` 序列。
- `neighborhood`：`neighborhood_segments(p, 3)` 序列化——以目标齿为中心的**连续三齿开放链**（三齿连成一体，齿根过渡圆角按 ISO 53 ρ\*_f·m_n 已含），前端渲染主路径。
- `center_line`：`{from_angle_deg, to_angle_deg}`（过齿中心与原点，点划线）。
- `pitch_line`：`{r}`（分度线半径，点划线）。
- `annotations`：7 项，每项为**对象** `{value, label?, symbol?, r?, a0_deg?, a1_deg?, center?}`，`value` 与 `params.outputs` **同源**（±0.0001mm），其余为几何定位。前端经 `.value` 消费（2026-08-10 契约对齐修复）。键：`tooth_thickness`(s_t)、`circular_pitch`(p_t)、`tip_fillet`(ρ_tip)、`root_fillet`(ρ_f)、`addendum`(h_a)、`dedendum`(h_f)、`whole_depth`(h)。

### spec.outline — 整体轮廓

- `points`：`sample_profile_points(p)` 连续全齿圈点列（供测试比对）。
- `teeth`：按 `2π/z_w` 相位切分的**每齿闭合点列** `[[[x,y],...], ...]`（供悬停高亮，避免前端从 10k 点重分割）。
- `circles`：`{tip_radius, root_radius, pitch_radius}`。
- 规模：102 齿 ≈ 10k 点 ≈ 200–400KB JSON，GLB 已有 1–3MB，无害。

## 5. 后端实现

### 5.1 GearParams 扩展（models.py）

`rho_tip: float = 0.0`，`__post_init__` 校验 `>= 0`。**默认 0 → 锐角齿顶，与现 3D 网格完全一致，`TestCrossRepresentationConsistency` 不受影响。**

### 5.2 齿顶倒圆（profile.py）

在共享段 `_tooth_open_segments`（被 `tooth_segments` 与 `single_tooth_segments` 共用）实现：`ρ*_tip>0` 时把齿顶弧替换为「左/右倒圆弧 + 齿顶弧」，双切求解与 `solve_root_fillet` 对称；`ρ*_tip=0` 走现路径零变化。**3D mesh 与步骤1表单本次不改**——默认 0 时 2D spec 与 3D GLB 天然一致；`>0` 是预留能力（同一函数已就绪，2D/3D 若需同时启用只差一处调用）。

### 5.3 spec.py（新建，纯 Python）

`build_spec(p)` 从同一 `GearParams` 产出 spec 字典，只调用 `profile.py`/`models.py` 权威函数，不做任何二次计算。分段函数：`arc_to_dict` / `polyline_to_dict` / `segments_to_dict` / `single_tooth_spec` / `outline_spec` / `params_table` / `build_spec`。

### 5.4 router.py

`GearParamsRequest.rho_tip`（`Field(0.0, ge=0.0)`）→ `to_gear_params()` 透传；`WorkpieceResponse.spec: dict`；`generate_workpiece` 用同一 `p` 调 `build_spec(p)` 并入响应。

## 6. 前端组件行为

### 齿轮规格独立窗口（spec.html + SpecWindowRoot.vue）

Electron 主进程 `spec:open` IPC 新建/聚焦独立 `BrowserWindow`（原生边框、可拖到第二显示器），加载 `spec.html`；`did-finish-load` 后 `webContents.send('spec:data', spec)` 推送数据，SpecWindowRoot 经 `onSpecData`（+ `getSpecData` 兜底拉取）接收。「左图右表」flex 布局：左上单齿廓 / 左下整体轮廓 / 右侧规格表。复用 `theme.css` `--brand-*`，绘图区白底。主窗口关闭时联动关闭该窗口。

### ToothProfileSvg.vue（单齿廓：三齿连成一体 + 分度圆弧 + ISO 标注 + 缩放平移）

固定像素画布 760×360；**主路径 = spec.single_tooth.neighborhood（后端连续三齿开放链，三齿连成一体，齿根过渡圆角按 ISO 53 ρ\*_f 已含）**；**分度线为分度圆弧（曲线，随齿轮曲率，每齿一段）**；无 neighborhood 时回退为目标齿 + 旋转邻齿。`vector-effect="non-scaling-stroke"` 线宽/文字缩放不变量；支持滚轮缩放 + 拖拽平移 + 按钮复位。`dimension.ts` 叠加 7 项标注（上条带：齿厚/齿距；左条带：齿全高/齿顶高/齿底高；右条带：两圆角）。齿厚/齿距标注与规格表同源。

### GearOutlineSvg.vue（整体轮廓 + 交互）

白底 `<svg>`。`teeth` 每齿一个闭合 `<path>`（`fill="none"`，`pointer-events:all`），悬停高亮 + tooltip 齿序号；**四圆：齿顶圆/齿根圆细实线、分度圆点划线、基圆浅色点线，并标注 齿顶圆/齿根圆/分度圆/基圆 直径（引线 + 文字，右侧条带，`outline.circles.base_radius` 由后端提供）**。**缩放平移 = 更新 `viewBox`**（滚轮、拖拽、按钮），`vector-effect="non-scaling-stroke"` 线宽不变量。初始视口右侧预留标注条带。

### SpecTable.vue（规格表）

只读 `el-table`，分「输入参数 / 解算结果」两组；行选中 + 「复制」按钮 → `navigator.clipboard.writeText` 输出 Tab 分隔文本（`参数名\t值` 每行）；表头 `el-tooltip` 解释计算依据（来源 = 设计书第3章参数字典，前端静态词条表）。

### WorkpieceViewer.vue（修改）

`generate()` 成功时存 `response.spec` 到 `spec` ref；`.result-summary` 内加「查看齿轮规格」`glass-btn` → `electronAPI.openSpecWindow(spec)`（IPC 打开独立窗口）；非 Electron 环境给出警告。

## 7. 缺口与边界

- **ADR-013（齿顶倒圆缺口，写入 CONTEXT.md）**：设计书第3章参数字典只定义齿根圆角系数 ρ\*_f，**无齿顶倒圆系数**；当前齿形为锐角齿顶。本功能新增 `rho_tip` 默认 0（锐角，与现 3D 一致）；`>0` 为预留能力，记缺口项，**不得当已验证公式使用**。
- **内齿轮 `k_io=-1`（边界项）**：`tip_radius()` 现无条件 `+h_an·m_n`，内齿几何是否真正内齿化待确认。spec 与 3D 继承同一现有实现，本功能不扩展不修复，一致性优先。

## 8. 测试策略

| 层 | 文件 | 依赖 | 内容 |
|----|------|------|------|
| 后端纯数学 | `test_spec.py`（新增） | 无 OCCT，CI 可跑 | spec 几何一致性（segments 还原闭合多边形鞋带面积 vs `sample_profile_points`，`rel<1e-6`）；标注数值==模型计算（`abs=1e-4` 对应 ±0.0001mm）；`params.outputs`==`GearParams` 方法（`abs=1e-9`）；定标算例1（m=2.5,z=41,β=0,x=0）d_a=107.5、s_t=π·m_t/2；**`rho_tip=0` 与旧实现逐点一致（`abs=1e-12`）** |
| 后端 API | `test_api.py`（扩充） | FastAPI TestClient | 响应含非空 `spec.params.outputs` / `spec.single_tooth.segments` / `spec.outline.teeth` |
| 前端组件 | `SpecWindowRoot/ToothProfileSvg/GearOutlineSvg/SpecTable.test.ts` | mock spec + Vitest | 等待态→收 spec 后渲染、7 项标注、每齿 path 数、缩放/悬停、复制格式 |
| 前端集成 | `WorkpieceViewer.test.ts`（扩充） | mock api | 按钮点击 → electronAPI.openSpecWindow(spec) |

## 9. 文件变更清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `backend/core/workpiece/models.py` | 修改 | `GearParams.rho_tip` + 校验 |
| `backend/core/workpiece/profile.py` | 修改 | `_tooth_open_segments` 齿顶倒圆（默认 0 零变化） |
| `backend/core/workpiece/spec.py` | 新增 | `build_spec` + 序列化 |
| `backend/core/workpiece/router.py` | 修改 | `rho_tip` + `spec` 响应字段 |
| `backend/core/workpiece/tests/test_spec.py` | 新增 | 一致性/定标/回归 |
| `backend/core/workpiece/tests/test_api.py` | 扩充 | spec 契约 |
| `CONTEXT.md` | 修改 | ADR-013 齿顶倒圆缺口 |
| `src/api/index.ts` | 修改 | Spec 类型 + `rho_tip` 映射 + AnnotationEntry 对象 |
| `spec.html` | 新增 | 齿轮规格独立窗口入口页 |
| `src/spec-window.ts` | 新增 | 独立窗口入口（挂载 SpecWindowRoot） |
| `src/components/SpecWindowRoot.vue` | 新增 | 独立窗口根组件（左图右表，IPC 收数据） |
| `src/components/ToothProfileSvg.vue` | 新增 | 单齿廓 + ISO 标注（消费 annotations.value） |
| `src/components/GearOutlineSvg.vue` | 新增 | 整体轮廓 + 缩放/平移/悬停 |
| `src/components/SpecTable.vue` | 新增 | 规格表 + 复制 |
| `src/components/dimension.ts` | 新增 | ISO 标注工具集 |
| `src/components/WorkpieceViewer.vue` | 修改 | 按钮 → electronAPI.openSpecWindow（移除覆盖层） |
| `electron/main.ts` | 修改 | spec:open 建/聚焦独立窗口 + spec:data 推送 |
| `electron/preload.ts` | 修改 | openSpecWindow / getSpecData / onSpecData |
| `src/env.d.ts` | 修改 | electronAPI 类型扩展 |
| `vite.config.ts` | 修改 | 多页入口 index.html + spec.html |
| `docs/specs/2026-08-10-gear-spec-presentation-design.md` | 修改 | 本设计规格书（独立窗口 + annotations 契约修订） |

## 10. 不做的

- 规格窗口为 Electron 独立 BrowserWindow（经 IPC 传 spec 数据），非 DOM 覆盖层
- 不新增独立 spec 端点、不在前端重算任何几何
- 生成成功后**不自动弹出**（手动按钮）
- 规格表**只读**，不可编辑、不触发重新生成
- 不改 3D mesh（齿顶倒圆默认 0 不变）、不改步骤1表单
- `rho_tip>0` 仅规格层呈现，不做 3D 同步倒圆（预留）
- 不做悬停跨图/联 3D 高亮
- 不引入 Pinia / 新依赖（SVG 手写，无 d3/konva）
- 不修复内齿轮 `k_io=-1` 既有几何问题

## 11. 验收标准

| 需求文档验收 | 实现落点 |
|---|---|
| 左图右表、无重叠遮挡 | `SpecWindowRoot.vue` flex 布局（独立窗口） |
| 线条区分明显、符合 ISO（实线/点划线） | 齿廓粗实线 / 分度线·中心线点划线（不同 dash 区分） |
| 单齿廓清晰展示 7 项规定参数 | `annotations` 7 项 → `dimension.ts` 尺寸线/箭头/文字 |
| 2D 轮廓缩放/平移无失真 | `viewBox` 更新（文字不随缩放变粗） |
| 悬停某齿高亮反馈 | 每齿 `<path>` + tooltip 齿序号 |
| 参数表支持选中/复制 | `SpecTable.vue` 行选中 + Tab 分隔复制 |
| 表中数值 = 图中标注 = 后台解算（±0.0001mm） | 全部同源同一 `GearParams` 计算；后端 `abs=1e-4` 断言 |
| 界面风格与主程序一致 | 复用 `--brand-*` + `glass-*`，绘图区白底 |

手动验证：`npm run dev:electron`（后端 5199 需重启加载新代码；Electron 主进程改动需重启应用）→ 步骤1填参 → 步骤2自动生成 → 点「查看齿轮规格」→ **弹出独立窗口**，核对单齿廓 7 项标注、整体轮廓缩放/平移/悬停、规格表复制、数值一致性（如 m=1, z=32 → d_a=34 mm）。默认 `rho_tip=0` 时 3D 外观与之前完全一致。

## 12. 变更履历

| # | 日期 | 来源 | 变更 |
|---|------|------|------|
| 1 | 2026-08-10 | Grill R1Q1 | 窗口形态 = 全屏 DOM 玻璃覆盖层（非 Electron 第二窗口） |
| 2 | 2026-08-10 | Grill R1Q2 | 数据管线 = 扩展 generate 响应新增 spec（同一实例一次计算） |
| 3 | 2026-08-10 | Grill R1Q3 | 2D 渲染 = 全部 SVG |
| 4 | 2026-08-10 | Grill R1Q4 | 规格表 = 只读展示 |
| 5 | 2026-08-10 | Grill R2Q1 | 触发 = 手动「查看齿轮规格」按钮（不自动弹） |
| 6 | 2026-08-10 | Grill R2Q2 | 齿顶圆角 = 新增 ρ\*_tip 参数（补设计书，缺口项） |
| 7 | 2026-08-10 | Grill R2Q3 | 高亮联动 = 轮廓内高亮 + tooltip 齿序号（不跨图/联 3D） |
| 8 | 2026-08-10 | Grill R2Q4 | 图纸底色 = 白底 + ISO 线型 |
| 9 | 2026-08-10 | Grill R3Q1 | ρ\*_tip 落地 = 仅规格层，默认 0 锐角，3D/步骤1表单不动 |
| 10 | 2026-08-10 | Grill R3Q2 | 规格表字段 = 全量清单（输入~13 + 输出~14） |
| 11 | 2026-08-10 | 工程默认 | 单齿廓取端面截面 |
| 12 | 2026-08-10 | 工程默认 | 齿厚/齿距标注与规格表同源（s_t / p_t） |
| 13 | 2026-08-10 | 工程默认 | 表头 tooltip 来源 = 设计书第3章参数字典 |
| 14 | 2026-08-10 | 工程默认 | 复制格式 = Tab 分隔文本 |
| 15 | 2026-08-10 | 契约修复 | annotations 每项定为对象 {value, ...几何定位}，前端经 `.value` 消费（后端按规格书本就输出对象） |
| 16 | 2026-08-10 | 需求变更 | 规格窗口从 DOM 覆盖层改为 Electron 独立 BrowserWindow（IPC spec:open / spec:data / spec:getData） |
| 17 | 2026-08-10 | 修复 | 单齿廓 arc 端点未叠加旋转角 `rot` 导致齿廓破碎 → `arcPointLocal` 修正 |
| 18 | 2026-08-10 | 需求变更 | 单齿廓图增加缩放/平移/复位（与整体轮廓一致的 viewBox 交互） |
| 19 | 2026-08-10 | 修复 | IPC 传 spec 前 JSON 深拷贝（ref reactive Proxy 无法被 structuredClone） |
| 20 | 2026-08-10 | 优化 | 单齿廓绘制目标齿 + 左右邻齿（浅灰细线，±2π/z_w 派生），分度线横贯三齿簇 |
| 21 | 2026-08-10 | 优化 | 单齿廓视图以三齿簇为中心填满、字号调小（原点不在齿轮中心） |
| 22 | 2026-08-10 | 优化 | 整体轮廓新增基圆（outline.circles.base_radius）并标注 齿顶/齿根/分度/基圆 四圆直径 |
| 23 | 2026-08-10 | 修复 | 分度线改为只在三齿处各画一小段（不画完整横线，避免贯穿标注/间隙） |
| 24 | 2026-08-10 | 修复 | 单齿廓尺寸重叠：中心线限于齿形区（不再贯穿齿厚标注）；右条带加宽避免箭头贴邻齿 |
| 25 | 2026-08-10 | 修复 | 单齿廓根圆闭合弧按**短弧**采样（后端 a0=4°→a1=356° 实为 8° 短弧；按全跨度采样会把包围盒/邻齿撑成整圆、压缩齿形） |
| 26 | 2026-08-10 | 优化 | 分度线改为**分度圆弧**（曲线，随齿轮曲率，每齿一段） |
| 27 | 2026-08-10 | 优化 | 三齿连成一体：后端新增 `neighborhood_segments(p,3)` 连续开放链（含 ISO 53 齿根过渡圆角 ρ\*_f），前端渲染为连接主路径 |
| 28 | 2026-08-10 | 修复 | 齿顶/齿根圆角标注颠倒：`rootY`/`tipY` 赋反（bbox.minY 为齿顶、maxY 为齿根），已交换 |
| 29 | 2026-08-10 | 优化 | 单齿廓标注重排：高度为径向尺寸（齿全高外侧、齿底高/齿顶高内侧，就近标注）；齿厚/齿距改为**沿分度圆弧线**的曲线标注（文字置顶部条带就近对齐） |
