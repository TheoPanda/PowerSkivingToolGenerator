/**
 * panelLayout.ts — 浮动面板贴边吸附共享常量（纯数据）
 *
 * 统一边距 PANEL_MARGIN = 24px：贴边吸附（LayerPanel / ResultPanel）的左/右/下三边、
 * MainPanel 左缘（left:24px）、MainView 右上角视图切换面板右缘（ViewCube right:24px）
 * 共用同一值；上边 = 自绘标题栏(40px) + PANEL_MARGIN——视觉上四边边距一致。
 *
 * CSS 侧（MainPanel left / ViewCube right）为纯样式无法引用 TS 常量，注释互指
 * （与 ADR-018「layerPalette ↔ theme.css 同名色互指」同模式）；改值时三处同步。
 */

/** 贴边吸附统一边距 [px]（左/右/下吸附位 + MainPanel 左缘 + 视图面板右缘）. */
export const PANEL_MARGIN = 24

/** App.vue 自绘标题栏高度 [px]（上边吸附需让出）. */
export const TITLE_BAR_H = 40

/** 贴边吸附上边位 = 标题栏下方再留统一边距（视觉边距与左/右/下一致）. */
export const SNAP_TOP = TITLE_BAR_H + PANEL_MARGIN

/** 贴边吸附触发阈值 [px]（距边沿多少 px 内松手吸附）. */
export const SNAP_THRESHOLD = 50

/** 右列浮动面板 y 下限 [px]：视图切换面板底 + 8px 间隙（标题栏 40 + ViewCube
 * top 12 + 高 ~158 + 8）。LayerPanel/SimulationPanel 贴右缘时与 ViewCube 同列，
 * y 低于此值即遮挡它（最大化→缩小后 resize 联动曾把 y 掉到顶部）。
 * ViewCube 内容增删时同步此值。 */
export const RIGHT_COLUMN_TOP = 218
