/**
 * dimension.ts — ISO 尺寸标注最小工具集
 *
 * 提供尺寸标注所需的 SVG 元素描述（延伸线 / 尺寸线 / 箭头 marker / 文字）。
 * 返回结构化的 SVG 元素描述（type + 属性），由调用组件直接渲染为 <line> / <path> / <text>。
 * 箭头 marker 的 id 必须可前缀化，保证窗口内多张 SVG 并存时唯一。
 *
 * 设计书对齐：标注数值全部来自 spec（与 params.outputs 同源，前端不重算几何）。
 */

/** 等角直角三角形箭头 marker 描述的 ref（供注入一次到 <defs>）. */
export interface ArrowMarker {
  id: string
  definition: string
}

/** 尺寸线 + 两端箭头的描述（扩展线另行独立提供）. */
export interface DimensionLine {
  type: 'dimension-line'
  x1: number
  y1: number
  x2: number
  y2: number
  markerStart: string
  markerEnd: string
}

/** 延伸线（引出线/辅助线，细实线）. */
export interface ExtensionLine {
  type: 'extension-line'
  x1: number
  y1: number
  x2: number
  y2: number
}

/** 标注文字（细实线文字，可带前缀/单位后缀）. */
export interface DimensionText {
  type: 'dimension-text'
  x: number
  y: number
  label: string
}

/** 单个尺寸标注的完整描述：延伸线 + 尺寸线 + 文字. */
export interface Dimension {
  extensionA: ExtensionLine
  extensionB: ExtensionLine
  line: DimensionLine
  text: DimensionText
}

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

/**
 * 构造延伸线（引出线/辅助线，细实线）.
 * @param x1 y1 x2 y2 线段两端（用户坐标）
 */
export function makeExtensionLine(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): ExtensionLine {
  return { type: 'extension-line', x1, y1, x2, y2 }
}

/**
 * 构造带两端箭头的尺寸线.
 */
export function makeDimensionLine(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  markerId: string,
): DimensionLine {
  return {
    type: 'dimension-line',
    x1,
    y1,
    x2,
    y2,
    markerStart: `url(#${markerId})`,
    markerEnd: `url(#${markerId})`,
  }
}

/**
 * 构造标注文字，position 为文字锚点（默认水平居中在 x 处）.
 */
export function makeDimensionText(x: number, y: number, label: string): DimensionText {
  return { type: 'dimension-text', x, y, label }
}
