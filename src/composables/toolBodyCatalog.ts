/**
 * toolBodyCatalog.ts — K-3.2 刀体结构手册标准表（ADR-021 表驱动的前端只读副本）
 *
 * 数据单源 = docs/specs/2026-08-31-tool-body-design.md（REF-7 袁哲俊《齿轮刀具设计》
 * 插齿刀标准化数据，GB/T 6081 口径；键槽深 = GB/T 6132 / ISO 240:2016 最近档，W16 已销）。
 * 与 backend/core/envelope/tool_body.py 的 _SEGMENTS/_KEYWAY_DEPTH 注释互指
 * （layerPalette/theme.css 先例）——改表必须两端 + 规格文档三处同步。
 *
 * 对档规则（ADR-021 ⑤）：内孔**向下取档**（≤2·r_pt 的最大档，低于 φ40 钳制 φ40 档）
 * ——孔小顶多重配刀杆、孔大刀体裂，安全侧。
 */

/** 手册档位（公称分度圆 φ → 可选内孔 / 标准厚度系列 [mm]）. */
export interface ToolBodySegment {
  dia: number
  bores: number[]
  thickness: number[]
}

/** 盘形插齿刀档位表（碗形 φ50→孔 20 不入：装夹范围不含碗形）. */
export const TOOL_BODY_SEGMENTS: readonly ToolBodySegment[] = [
  { dia: 40, bores: [15.875], thickness: [10, 12] },
  { dia: 63, bores: [31.743], thickness: [10, 12] },
  { dia: 75, bores: [31.743], thickness: [15, 17, 20] },
  { dia: 100, bores: [31.743, 44.443], thickness: [18, 22, 24] },
  { dia: 125, bores: [31.743, 44.443, 44.45], thickness: [30] },
  { dia: 160, bores: [88.9], thickness: [35] },
  { dia: 200, bores: [101.6], thickness: [40] },
]

/** 键槽宽按（档 × 模数段）[mm]——REF-7 结构尺寸表行段（段界取模数间隙中点）. */
const KEYWAY_B_BY_DIA: ReadonlyArray<{ dia: number; mUp: number; b: number }> = [
  { dia: 40, mUp: 0.65, b: 6 },
  { dia: 40, mUp: Infinity, b: 7 },
  { dia: 63, mUp: 0.65, b: 6 },
  { dia: 63, mUp: Infinity, b: 7 },
  { dia: 75, mUp: Infinity, b: 10 },
  { dia: 100, mUp: 1.6, b: 10 },
  { dia: 100, mUp: Infinity, b: 12 },
  { dia: 125, mUp: Infinity, b: 13 },
  { dia: 160, mUp: Infinity, b: 18 },
  { dia: 200, mUp: Infinity, b: 20 },
]

/** 图纸 4035100343（碗型斜齿车齿刀）锚定的键槽宽——优先于手册表（31.743 孔 → 14）. */
const KEYWAY_WIDTH_BY_BORE: Readonly<Record<number, number>> = {
  31.743: 14,
}

/** 键槽深（孔侧）[mm]——图纸锚定（31.743→6.0）优先，其余 GB/T 6132 / ISO 240:2016 最近档（W16 已销）. */
const KEYWAY_DEPTH_BY_BORE: Readonly<Record<number, number>> = {
  15.875: 1.7,
  31.743: 6.0,
  44.443: 3.5,
  44.45: 3.5,
  88.9: 5.5,
  101.6: 7.0,
}

/** 向下取档：≤dPt 的最大公称分度圆档；低于最小档钳制 φ40 档（安全侧，ADR-021 ⑤）. */
export function selectToolBodySegment(dPt: number): ToolBodySegment {
  let seg = TOOL_BODY_SEGMENTS[0]
  for (const cand of TOOL_BODY_SEGMENTS) {
    if (cand.dia <= dPt) seg = cand
  }
  return seg
}

/** 键槽宽自动带出（图纸锚定孔径优先，否则档 × 模数段）[mm]. */
export function toolBodyKeywayB(seg: ToolBodySegment, mN: number, dBore?: number): number {
  if (dBore !== undefined) {
    const hit = KEYWAY_WIDTH_BY_BORE[dBore]
    if (hit !== undefined) return hit
  }
  let b = KEYWAY_B_BY_DIA[KEYWAY_B_BY_DIA.length - 1].b
  for (const row of KEYWAY_B_BY_DIA) {
    if (row.dia === seg.dia && mN <= row.mUp) {
      b = row.b
      break
    }
  }
  return b
}

/** 键槽深（GB/T 6132 最近档）[mm]；非系列孔径 → null（后端会硬拒）. */
export function toolBodyKeywayDepth(dBore: number): number | null {
  const hit = KEYWAY_DEPTH_BY_BORE[dBore]
  return hit === undefined ? null : hit
}

/** 默认厚度 = 档内标准系列中 ≥L 的最小值 [mm]；全档 <L → null（软警口径）. */
export function toolBodyDefaultThickness(seg: ToolBodySegment, L: number): number | null {
  for (const b of seg.thickness) {
    if (b >= L) return b
  }
  return null
}

/**
 * 内孔可行性预过滤（Q10：前端下拉预过滤 + 后端 400 二道闸）——
 * 孔缘（带键槽时含键槽底 r_bore+t₁）< r_root 方可入选。rRoot=null（估算不可用）
 * 时不过滤（后端仍是权威闸门）。
 */
export function filterBoresByRoot(
  seg: ToolBodySegment,
  rRoot: number | null,
  keywayT1: number | null,
): number[] {
  if (rRoot === null) return [...seg.bores]
  return seg.bores.filter((b) => b / 2 + (keywayT1 ?? 0) < rRoot)
}
