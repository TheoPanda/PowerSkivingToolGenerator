# 子 PRD-4：②c 后刀面 + 单齿预览

**父 PRD**：`../2026-08-13-envelope-calculation-prd.md`
**状态**：待评审
**依赖**：子 PRD-2（刃形）+ 子 PRD-3（前刀面）

## 1. 目标

实现模块②c 后刀面生成（分截面包络 K-2.18/2.19），产出 `FlankSurface`（重磨刃形族拟合面）；并按 K-3.1 闭合成**单齿预览**（前刀面 + 后刀面 + 刃形）。

## 2. 范围

**做**：
- K-2.18 Δa_i（重磨截面中心距变动量）、K-2.19 分截面重算刃形 + 拟合后刀面。
- 单齿预览（三件套闭合，标注 source=模块③ 预览，硬质合金材质）。

**不做**：变位族法 K-2.14（锥刀，W5 缓行）、圆柱刀导程法 K-2.15/16（二期可选）、圆柱刀轴向偏移法 K-2.17（二期可选）、单齿周向阵列成完整刀具（模块③ 正式交付）。

> ⚠️ **刃形来源**：本期后刀面基于 ②b **离散刃形**（投影 z=0 + 内边界，非 K-2.8 解析刃形）。K-2.18/2.19 是设计书 §4.4 的「D. 重磨集成（全刀型叠加）」——A/B/C 三种工具型专属 let-off（K-2.14 / K-2.15~16 / K-2.17）均二期，解析刃形的后刀面待子 PRD-5 落地后对接。

## 3. 数据契约

- **输入**：`EdgeCurve` + `RakeSurface` + `tool_type` + `L` + `n_L`。
- **输出**：`FlankSurface{section_edges[], flank_fit, resharpen_schedule a_i[]}` + 单齿 GLB。

## 4. 交互与视觉

- 后刀面图层：翡翠绿 `#3AA06A` 冷色半透明面（配色单源 `layerPalette` 的 `flank` 预设，可选颜色面，与扫掠点云/前刀面明显区分），α≈0.5。
- 单齿图层：硬质合金 `carbideMaterial` 实心（用户确认材质），标注 source=模块③ 预览。
- 诊断条：截面拟合残差（< 离散点间距一半）。

## 5. 验收标准

1. 截面拟合残差 < 离散点间距一半（第7章行16）。
2. 算例2 Δa_i 轨迹回归（0.07027 / 0.14054 / 0.21081 / 0.28108，L=2mm / n_L=4；**硬编码 golden 常量**落地，不接 testdata，与父 PRD A4 同步修正）。
3. 单齿 GLB 闭合流形、可预览、硬质合金材质。

## 6. 缺口与风险

- T3（L/n_L 未发表）→ 用第6章推导示例 L=2 / n_L=4 + 工程默认。
- 单齿预览越级模块③ → 后端溯源 `source=模块③预览` + 前端显式标注，双保险。

## 7. 文件变更

| 文件 | 操作 |
|---|---|
| `backend/core/envelope/flank.py` | 新增 |
| `backend/core/envelope/single_tooth.py` | 新增 |
| `backend/core/envelope/router.py` | 修改（注册 flank/single-tooth 端点） |
| `backend/core/common/gltf_export.py` | 修改（复用 export_geometry_glb 导出后刀面曲面片；单齿实体沿用现有实体 GLB 导出） |
| `backend/core/envelope/tests/*` | 新增 |
