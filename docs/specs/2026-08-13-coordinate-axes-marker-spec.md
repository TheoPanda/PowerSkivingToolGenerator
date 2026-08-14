# 坐标轴 X/Y/Z 标注 + 旋转方向动态标记 Spec

**日期**：2026-08-13
**父 PRD**：`../prds/envelope/02-discrete-envelope.md`（对子 PRD-2 的 W/T 坐标轴做美观增强）
**状态**：已实现
**来源**：grilling 访谈（10 决策，两轮收敛）

## Problem Statement

子 PRD-2 已为包络计算叠加 W（工件系，原点）与 T（刀具系，偏移中心距 a、倾斜轴交角 Σ）两套坐标轴，但它们是**三根裸色线**（X 红 / Y 绿 / Z 蓝），存在两个判断障碍：① 用户无法一眼确认**每根轴对应哪个字母、属于哪套坐标系**；② 两套轴各自绕 Z 的**旋转方向（工件/刀具相对转动）无法在静态图上表达**。本 spec 给坐标轴补两项能力：**X/Y/Z 文字标注（带 W/T 前缀）**与**绕 Z 轴连续旋转的方向指针**，让坐标系既可读、又示意运动。

## Solution

坐标轴从「三根裸线」升级为「三根轴线 + 三个文字 Sprite + 一个 Z 轴旋转指针」的集合：

- **文字标注**：Canvas 画布生成文字贴图 → `THREE.Sprite`（始终面向相机、屏幕大小恒定），内容为 `X_W/Y_W/Z_W`、`X_T/Y_T/Z_T`，颜色跟轴一致，贴在轴末端略超出。
- **旋转指针**：挂在 Z 轴尖端的**圆弧箭头**（270° 圆环管弧身 + 末端切向箭头锥体），琥珀色 `#FF9500`，由渲染循环匀速驱动 `rotation.z` 递增，**W 逆时针（+Z）、T 顺时针（−Z）**，示意两轴各自的旋转方向。

⚠️ **边界（务必澄清）**：这是**「示意」**，**不是「运动仿真」**。指针匀速转动（≈1 圈/2 秒）只为表达"这根轴在转、朝这个方向转"，**不反映真实转速比** ω_t/ω_w = z_w/z_t（真实转速由扫掠点云揭示滑块表达），也不与 3D 齿轮实体的旋转同步（视口内齿轮是静态模型，运动是后端预计算的）。

## User Stories

1. 作为车齿刀设计人员，我希望坐标轴带 X/Y/Z 字母与 W/T 前缀，一眼看出每根轴的方向和它属于工件系还是刀具系。
2. 作为车齿刀设计人员，我希望看到绕 Z 轴旋转的方向示意，判断工件与刀具的相对转动关系。
3. 作为开发者，我希望标注与指针全部是纯前端 Three.js 产物（无新依赖、不动后端），且随坐标轴生命周期增删、dispose 无泄漏。

## Implementation Decisions

### 视觉决策（grilling 锁定）

| # | 决策 | 结论 |
|---|---|---|
| Q1 | 生命周期 | 保持现状——标注与指针随现有坐标轴出现（`setEnvelopeInstall` 后），包络前不显示 |
| Q2 | 标注范围 | W / T 两套轴都加 X/Y/Z |
| Q3 | 文字技术 | Canvas `THREE.Sprite`（始终面向相机、屏幕大小恒定、零新依赖） |
| Q4 | W/T 区分 | **前缀** `X_W/Y_W/Z_W`、`X_T/Y_T/Z_T` |
| Q5 | 旋转标记形态 | **连续旋转的圆弧箭头**（绕 Z 轴不停转，圆弧圈住 Z 轴） |
| Q6 | 旋转方向 | 按真实运动链：W 逆时针（+Z，对应 `Rot_z(φ_w)`）、T 顺时针（−Z，对应 `Rot_z(−φ_t)`） |
| Q7 | 标注色/位 | 跟轴同色（X 红 / Y 绿 / Z 蓝）、贴轴末端略超出（偏移 10mm） |
| Q8 | 遮挡 | 全部允许遮挡（正常深度 `depthTest=true`，不做穿透） |
| Q9 | 转速 | 两轴同速匀速（≈1 圈/2 秒，ω=π rad/s），不反映真实 ω 比 |
| Q10 | 指针形态/色 | 270° 圆环管弧身（`TubeGeometry`，绕 Z 轴）+ 末端切向箭头锥体（指向扫掠方向）；琥珀色 `#FF9500` |

### 几何结构

单套坐标轴（`makeAxisTriad(length, prefix)`，`prefix ∈ {'W','T'}`）含：

- **3 根轴线**：`THREE.Line`（X 红 `0xff4444` / Y 绿 `0x44cc44` / Z 蓝 `0x4488ff`），长 `length`。
- **3 个标注 Sprite**：`sprite.name = 'axis-label-{X|Y|Z}_{W|T}'`，位置 = 轴方向 × `(length + 10mm)`；`SpriteMaterial.map` = Canvas 生成的 `CanvasTexture`。
- **1 个旋转指针组**：`group.name = 'rotation-pointer-{W|T}'`，位置 = `(0, 0, length)`（Z 轴尖端），含弧身（`TubeGeometry` + `CircularArcCurve`，270° 圆环管，W 逆时针/T 顺时针）+ 末端箭头锥体（`ConeGeometry`，切向指向扫掠方向）。

### 旋转驱动（渲染循环钩子）

- 模块级 `rotationPointers: Array<{ group, dir }>`（`dir = W:+1 / T:−1`）登记指针，`makeAxisTriad` 创建时 push。
- `animate()` 内新增分支：当 `rotationPointers.length > 0` 时，按 `performance.now()` 差值算 `dt`，逐指针 `group.rotation.z += dir × π × dt`，并置 `sceneDirty = true`。
- **T 系指针正确绕倾斜后的 Z 轴转**：指针组是 T 轴 triad（父级 `rotation.x = Σ`）的子级，其局部 `rotation.z` 天然绕 T 的倾斜 Z 轴。
- **无坐标轴（包络前）零开销**：`rotationPointers` 为空，不进分支，保持 on-demand 渲染。
- `clearRotationPointers()`（清空数组 + 复位 `lastPointerTime=0` 防时间戳跳变）在 `drawCoordinateAxes` 重建前 / `clearLayers` / `dispose` 三处调用。

### 内存释放

`disposeGroup` 新增 `THREE.Sprite` 分支：释放 `material.map`（`CanvasTexture`）与 `material`。指针臂/箭头是 `Mesh`，走既有 Mesh 分支释放 geometry/material。

## Testing Decisions

- **前端（vitest + fake renderer）**：`setEnvelopeInstall` 后，lastScene 内存在 6 个命名 Sprite（`axis-label-X_W`…`axis-label-Z_T`）与 2 个命名旋转指针组（`rotation-pointer-W/T`，二者独立）；旋转指针含 2 个 Mesh（臂 + 箭头）；`dispose` 后标注与指针从场景清除。
- **Canvas 依赖隔离**：`makeTextSprite` 对 `canvas.getContext('2d')` 做 `try/catch` + null 守卫（jsdom 无 canvas 包会抛 "Not implemented"），退化返回空标注占位；测试用 `vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)` 静音噪声，只断言结构不测文字渲染细节。
- **零回归门禁**：子 PRD-1 多图层、子 PRD-2 扫掠点云/刃形、既有 `setEnvelopeInstall 不抛错` 全绿。

## Out of Scope

- **运动仿真**：不反映真实转速比、不与齿轮实体旋转同步（真实运动由揭示滑块 + 后端运动链表达）。
- 指针/标注的显隐开关、转速/颜色 UI 可调（保持常量，需要再暴露）。
- 坐标轴独立于包络常显（Q1 已定为跟随包络生命周期）。
- 文字随距离缩放（Sprite 屏幕大小恒定，正是本 spec 诉求）。

## Further Notes

- **旋转方向来源**：`backend/core/common/transforms.py` 运动链 `r^(T) = Rot_z(−φ_t)·…·Rot_z(φ_w)·r^(W)` → 工件 +φ_w（逆时针）、刀具 −φ_t（顺时针）。指针方向是该链瞬时正方向的**示意**，不随内外齿轮（k_io）动态翻转。
- **文件单一负责人**：`src/three/gearViewport.ts` 为 3D 深模块，本增强全部落其中（`makeTextSprite` / `makeRotationPointer` / `makeAxisTriad` / `drawCoordinateAxes` / `animate` / `disposeGroup`）。
- **ADR-019 延续**：标注与指针纯可视化，不改变包络正确性判据（ffα 自证闭环 + 几何不变量 + 目检）。

## 变更履历

| # | 日期 | 来源 | 变更 |
|---|---|---|---|
| 1 | 2026-08-13 | grilling Q1~Q4 | 坐标轴加 X/Y/Z 标注，W/T 前缀、Canvas Sprite、贴轴末端 |
| 2 | 2026-08-13 | grilling Q5/Q6/Q9/Q10 | Z 轴旋转指针（圆弧箭头、琥珀色、同速匀速、W 逆/T 顺） |
| 3 | 2026-08-13 | grilling Q7/Q8 | 标注跟轴同色、允许遮挡（正常深度） |
| 4 | 2026-08-13 | 用户反馈修正 | 旋转指针由「径向直臂+折弯箭头」改为「圆弧箭头」（270° 圆环管弧身 + 末端切向箭头锥体，绕圆弧中心旋转） |
