/**
 * dimension.ts — ISO 尺寸标注最小工具集
 *
 * 提供尺寸标注所需的 SVG 元素描述（箭头 marker / 文字格式化）。
 * 箭头 marker 的 id 必须可前缀化，保证窗口内多张 SVG 并存时唯一。
 *
 * 设计书对齐：标注数值全部来自 spec（与 params.outputs 同源，前端不重算几何）。
 */

/**
 * 生成可前缀化且窗口内唯一的箭头 marker id.
 * marker 指向一个「指向右方」的等边箭头三角形，配合 orient="auto-start-reverse" 两端自动朝向.
 */
export function arrowMarkerId(prefix: string): string {
  return `${prefix}-arrow`
}

/** 构造箭头的 <marker> 定义字符串（细实线填充）. */
export function arrowMarkerDefinition(markerId: string): string {
  return (
    `<marker id="${markerId}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" ` +
    `markerHeight="7" orient="auto-start-reverse">` +
    `<path d="M9,5 L0,0 L1.6,5 L0,10 Z" fill="currentColor"></path>` +
    `</marker>`
  )
}

/** 构造完整 <defs> 块（可挂在任意白底 svg 的 <defs> 内） */
export function dimensionDefs(prefix: string): string {
  return `<defs>${arrowMarkerDefinition(arrowMarkerId(prefix))}</defs>`
}

/**
 * 以数值 + 单位（可选）格式化标注文字，保留合理小数位.
 * @param value 数值（mm）
 * @param decimals 小数位
 * @param unit 单位后缀，默认 mm
 */
export function formatDim(value: number, decimals: number = 2, unit: string = 'mm'): string {
  return `${value.toFixed(decimals)}${unit}`
}
