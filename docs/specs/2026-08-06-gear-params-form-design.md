# 步骤1"待加工齿轮"参数表单 — 设计规格

**日期**：2026-08-06
**状态**：已批准（grill 完成，待实现）

## 1. 目标

在 MainPanel 的 5 步工作流中实现第 1 步"待加工齿轮"的参数输入表单。用户在此填写工件参数（设计书第3章 组A），完成后推进到步骤2。

## 2. 组件架构

```
MainPanel.vue（改造）
├── 文件栏（已有）
├── 步骤导航（已有）
└── 步骤内容区（新增 .step-body）
    └── GearParamsPanel.vue（新建）
        ├── ① 基本参数（默认展开）
        ├── ② 齿厚指定（默认展开）
        └── ③ 高级默认值（默认折叠）
```

`GearParamsPanel.vue` 是纯展示组件，不直接操作全局状态。表单数据通过 `v-model` 绑定到 MainPanel 持有的 `reactive` store。

## 3. 字段定义

### 3.1 ① 基本参数（`default-open`）

| 字段 | 控件 | 类型 | 默认值 |
|---|---|---|---|
| profile_type | 下拉选择（5 选项，非渐开线 disabled） | `'involute' \| 'arc' \| 'cycloid' \| 'modified' \| 'pointcloud'` | `'involute'` |
| k_io | Segmented 切换 | `1`（外齿）\| `-1`（内齿） | `1` |
| m_n | 数字输入 | number, >0, step 0.1 | — |
| z_w | 整数输入 | integer, ≥1 | — |
| β_w | 滑块 + 数字输入 | number, [0, 45] | `0` |
| j_w | 条件显示（β_w>0 时）| `1`（右旋）\| `-1`（左旋）| `1` |
| b_w | 数字输入 | number, >0 | — |

### 3.2 ② 齿厚指定（`default-open`）

三选一 Radio，选中态展示对应输入：

- **变位系数 x_w**：数字输入，范围 [-1, +1]，step 0.01，默认 0
- **公法线 W_k**：W_k（mm）+ 跨齿数 k（整数，可自动推荐 `k≈z_w·α_t/180°+0.5`；k 实时联动——α_n/β_w 变化→自动重算）
- **跨棒距 M**：M（mm）+ 量棒径 d_p（mm，常用 ≈1.68m_t）

### 3.3 ③ 高级默认值（`default-collapsed`）

| 字段 | 默认值 | 控件 |
|---|---|---|
| α_n（法向压力角）| 20° | 数字输入，可覆盖 |
| h*_an（齿顶高系数）| 1 | 数字输入，可覆盖 |
| c*_n（顶隙系数）| 0.25 | 数字输入，可覆盖 |
| ρ*_f（齿根圆角半径系数）| 0.38 | 数字输入，可覆盖 |

## 4. 视觉规范

### 4.1 共用样式（写入 `theme.css`）

新增变量：
```css
--brand-input-bg: rgba(255,255,255,0.65);
--brand-glass-bg: rgba(255,255,255,0.5);
--brand-glass-border: rgba(255,255,255,0.5);
```

### 4.2 组件风格

- 输入框：半透明白底 + 品牌蓝边框 @12% + focus 蓝外发光
- 折叠面板：无背景色，左侧 2px 竖线指示展开态，hover 微蓝底
- Segmented：品牌蓝选中态 / 透明灰未选中
- Radio：品牌蓝圆点
- 按钮：品牌蓝 #0060A0，圆角 8px
- 过渡：`cubic-bezier(0.22, 0.61, 0.36, 1)` 统一

### 4.3 面板整体

复用 MainPanel 现有 `.panel-body` 的玻璃质感（`backdrop-filter: blur(24px)` + 半透白底 + 圆角 16px），面板宽度保持 280px。

## 5. 数据流

```
MainPanel.vue
  └─ reactive<GearParams> 持有表单数据
  └─ provide('gearParams', data)
  └─ computed step1Valid: boolean

GearParamsPanel.vue
  └─ inject('gearParams')
  └─ emit('valid-change', isValid)
```

本阶段不引入 Pinia，用 provide/inject 传递。

## 6. 校验规则

| 校验 | 规则 | 触发 | 显示 |
|---|---|---|---|
| m_n | > 0 | blur | 红色边框 + 行内提示 |
| z_w | ≥ 1, 整数 | blur | 红色边框 + 行内提示 |
| b_w | > 0 | blur | 红色边框 + 行内提示 |
| β_w | 滑块范围 [0,45] | 实时 | 滑块限制 |
| 齿厚三选一 | 至少一个已填 | next-click | 面板顶部轻提示 |
| z_t/z_w（后续） | 比例警告 | 输入 z_t 后 | 黄色提示（不阻塞）|

## 7. 步骤导航联动

- 步骤1 必填项全部合法 → 步骤节点变绿 ✓ → 底部"下一步"按钮可用
- 用户点击步骤2~5 但步骤1未完成 → 步骤1面板轻微脉冲动画 + 顶部引导文字："请先完成齿轮参数设置，这是后续计算的基础 🙂"
- 不做弹出阻断，用内联引导

## 8. 文件变更清单

| 文件 | 操作 | 内容 |
|---|---|---|
| `src/components/GearParamsPanel.vue` | 新增 | 三组折叠参数面板 |
| `src/components/MainPanel.vue` | 改造 | 新增 `.step-body` + 引用 GearParamsPanel + reactive store + 下一步按钮 |
| `src/assets/theme.css` | 改造 | 新增表单组件基类（.glass-input, .glass-segmented, .glass-collapse 等）|

## 9. 变更履历

| # | 日期 | 来源 | 变更 |
|---|---|---|---|
| 1 | 2026-08-06 | Grill Q1 | profile_type 下拉全部展示，非渐开线类型 disabled（灰掉）|
| 2 | 2026-08-06 | Grill Q2 | "下一步"先全量校验再跳转，不通过留在步骤1 |
| 3 | 2026-08-06 | Grill Q3 | 高级默认值：展开后直接可编辑，默认值预填 |
| 4 | 2026-08-06 | Grill Q4 | 面板保持 280px，step-body overflow-y:auto |
| 5 | 2026-08-06 | Grill Q5 | 步骤2~5 显示占位（图标+名称+"即将推出"）|
| 6 | 2026-08-06 | Grill Q6 | x_w 范围 [-1,+1]，step 0.01 |
| 7 | 2026-08-06 | Grill Q7 | d_aw/d_fw 不在步骤1展示，留后端计算后展示 |
| 8 | 2026-08-06 | Grill Q8 | 跨齿数 k：实时联动（α_n/β_w 变化→k 自动重算）|
| 9 | 2026-08-06 | Grill Q9 | 步骤内容区放在步骤导航下方，步骤导航始终可见 |
| 10 | 2026-08-06 | Grill Q10 | 步骤完成判定：实时自动（全部合法→立即变绿）|
| 11 | 2026-08-06 | Grill Q11 | 步骤间切换：数据保留（reactive store 在 MainPanel 生命周期内）|

## 10. 不做的

- 不引入 Pinia（留到多步骤数据共享需求明确时）
- 不实现后端 API（本次仅前端表单）
- 组B（刀具初选）/组C（工艺参数）留到步骤2/3
- 齿厚反解计算（K-1.11/K-1.14）留到后端实现
