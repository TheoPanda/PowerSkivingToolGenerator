# 子 PRD-1：3D 视口多图层基础设施

**父 PRD**：`../2026-08-13-envelope-calculation-prd.md`
**状态**：待评审
**依赖**：无（可最先开工）
**类型**：横切前置（前端 + 后端导出）

## 1. 目标

把 `src/three/gearViewport.ts` 从「单模型替换」重构为「命名图层集（LayerSet）」，使模块② 的产形面 / 前刀面 / 刃形 / 后刀面 / 单齿能叠加在工件齿轮上展示；同时后端 exporter 新增「曲面片 / 点云 / 空间曲线 → GLB」非实体导出路径。

**硬性约束（用户明确要求）**：不得破坏模块① 已交付成果。工件齿轮 3D 生成（`loadGear` 路径、`WorkpieceViewer`、规格窗口）**零回归**，现有前端测试全绿。注：`gearViewport` 唯一消费者是 `MainView.vue`（经 `gear:model-ready` 事件），零回归门禁聚焦 `MainView`；`WorkpieceViewer` 只 emit 不碰视口，零改动自然满足。

## 2. 范围

**做**：
- `gearViewport` 多图层接口：`addLayer`（主入口）/ `loadLayers`（批量便捷）/ `removeLayer` / `clearLayers` / `setLayerVisible` / `setLayerOpacity` / `focusLayer`；图层数据经 window 事件 `gear:layer-ready`（与 `gear:model-ready` 并列）送达视口。
- 新增 `src/three/layerPalette.ts`（`LayerId` 类型 + 配色/材质常量，纯数据源可单测；与 `theme.css` 同名色注释互指，非运行时联动）。
- 后端 exporter 非实体导出：开放曲面片（三角网格 + `doubleSide`）、空间曲线（`LineSegments`/`LINE_STRIP`，有序顶点）、点云（`Points` 或三角化）——落 `backend/core/common/gltf_export.py` 泛化 `export_geometry_glb`。
- GLB `node.name` 写入 `LayerId`，**仅作调试标签**；图层识别由前端 `addLayer` 显式传入的 id 驱动，与 `node.name` 解耦。
- `loadGear` 降级为「清空非工件层 + 加载工件层」的薄适配层（`WorkpieceViewer.vue` 零改动）。

**做（本子 PRD 正式交付）**：
- 图层列表交互（`LayerPanel`）：眼睛显隐 + 点名字聚焦 + 顶部「全部显示」，浮画布右侧；本子 PRD 用占位假数据填充，接真数据时只换形状不换交互。

**不做**：
- 任何包络算法（K-2.x 留子 PRD-2/3/4/5）。
- 真实包络数据接入（本子 PRD 用占位假数据）。

## 3. 数据契约

```ts
// layerPalette.ts
type LayerId = 'workpiece' | 'generatrix' | 'rake' | 'edge' | 'flank' | 'singleTooth'

interface LayerSpec {
  id: LayerId
  kind: 'mesh' | 'line' | 'points'
  glbBase64?: string
  opacity: number
  materialPreset: 'steel' | 'carbide' | 'generatrix' | 'rake' | 'edge'
  doubleSide?: boolean
}
```

材质预设（对齐父 PRD §5.5）：`steel` 浅灰钢（工件）、`carbide` 硬质合金深灰（后刀面/单齿）、`generatrix` 品牌蓝 #0060A0 半透明、`rake` 冰蓝 #E8F0F8 半透明、`edge` 深色 #1f2937 高亮曲线。

## 4. 交互与视觉（骨架）

- 本子 PRD 用 mock 图层（如两个不同色曲面 + 一条曲线）验证 `addLayer` / 显隐 / 透明度 / 聚焦能力，不接真实包络数据。
- 聚焦动画：其余层 opacity→0.12，camera 向该层 bbox 中心插值 500ms（品牌缓动 `cubic-bezier(0.22,0.61,0.36,1)`）。

## 5. 验收标准

1. **零回归（硬性门禁）**：现有前端 Vitest 全绿；`WorkpieceViewer` 生成工件 GLB 流程不变、规格窗口不变。
2. 多图层能力单测：`addLayer` 后场景含 N 个独立 group；`setLayerVisible` 正确显隐；`setLayerOpacity` 不串改其它层（材质 `.clone()` 验证）。
3. 非实体 GLB 往返：exporter 产曲线 GLB → 前端加载为 `LineSegments`；曲面片 GLB → 半透明 `Mesh`，`doubleSide` 生效。
4. `dispose` 无泄漏：多图层增删后 dispose，无残留 geometry/material（呼应架构审查 C3 遗留）。

## 6. 缺口与风险

- Three.js `linewidth` 在 WebGL2 普遍被忽略，刃形曲线可能发虚 → 需 ribbon（法向细带）兜底或接受 1px 折线，本子 PRD 用 mock 曲线验证。
- 半透明多层叠加深度伪影 → `renderOrder` + `depthWrite=false` 调参，真实算例目检留后续子 PRD。
- 材质共享陷阱 → 每层 `material.clone()` 防串改。

## 7. 文件变更

| 文件 | 操作 |
|---|---|
| `src/three/gearViewport.ts` | 重构（多图层） |
| `src/three/layerPalette.ts` | 新增 |
| `backend/core/common/gltf_export.py` | 新增（泛化 `export_geometry_glb` 非实体导出） |
| `src/components/MainView.vue` | 修改（监听 `gear:layer-ready` 分发 addLayer） |
| 相关单测 | 新增/修改 |
