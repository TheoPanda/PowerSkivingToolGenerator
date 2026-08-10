/**
 * spec-types.ts — 齿轮规格 payload 的纯类型（无运行时代码）
 *
 * 供渲染进程、Electron 主进程、preload 三方共享，让 spec 数据跨 IPC 缝保持类型形状一致
 * （架构审查 C5）。纯类型模块，`import type` 会被完全 elide，不引入运行时耦合。
 */

/** 2D 坐标点 [x, y]. */
export type Point2 = [number, number]

/** 几何圆弧段（SVG 用 A 指令），a0/a1 为弧度、后端已 unwrap 为短弧. */
export interface Arc {
  type: 'arc'
  radius: number
  a0: number
  a1: number
  center: Point2
  /** true = CW（凹角），SVG sweep=0；false = CCW，SVG sweep=1 */
  clockwise: boolean
}

/** 折线段. */
export interface Polyline {
  type: 'polyline'
  points: Point2[]
}

/** 单齿廓 segment 联合类型. */
export type Segment = Arc | Polyline

/** 中心线：过齿中心与原点（角度 deg）. */
export interface CenterLineSpec {
  from_angle_deg: number
  to_angle_deg: number
}

/** 分度线：半径（mm）. */
export interface PitchLineSpec {
  r: number
}

/** 单齿廓 7 项标注的数值条目（value 与 params.outputs 同源 ±0.0001mm；label/symbol 供表格/图纸用）.
 * 弧角/半径等定位几何由前端布局推导，后端只出数值（架构审查 C4）。 */
export interface AnnotationEntry {
  value: number
  label?: string
  symbol?: string
}

/** 单齿廓 7 项标注（每项 {value, label, symbol}）. */
export interface SingleToothAnnotations {
  tooth_thickness: AnnotationEntry
  circular_pitch: AnnotationEntry
  tip_fillet: AnnotationEntry
  root_fillet: AnnotationEntry
  addendum: AnnotationEntry
  dedendum: AnnotationEntry
  whole_depth: AnnotationEntry
}

/** spec.single_tooth = 单齿廓 + 中心线 + 分度线 + 标注. */
export interface SingleToothSpec {
  segments: Segment[]
  /** 以目标齿为中心的连续 n 齿齿廓（开放链，三齿连成一体，含齿根过渡圆角）. */
  neighborhood?: Segment[]
  center_line: CenterLineSpec
  pitch_line: PitchLineSpec
  annotations: SingleToothAnnotations
}

/** 整体轮廓四圆半径（mm）：齿顶/齿根/分度/基圆. */
export interface OutlineCircles {
  tip_radius: number
  root_radius: number
  pitch_radius: number
  base_radius: number
}

/** spec.outline = 全齿圈轮廓点位（含逐齿闭合点列供悬停）. */
export interface OutlineSpec {
  points: Point2[]
  teeth: Point2[][]
  circles: OutlineCircles
}

/** 参数规格表的一行. */
export interface ParamRow {
  key: string
  label: string
  symbol: string
  value: number
  unit: string
}

/** spec.params = 输入参数 + 解算结果两组全量参数字典. */
export interface ParamTableSpec {
  inputs: ParamRow[]
  outputs: ParamRow[]
}

/** POST /api/workpiece/generate 响应中的 spec 顶层契约. */
export interface SpecPayload {
  params: ParamTableSpec
  single_tooth: SingleToothSpec
  outline: OutlineSpec
}
