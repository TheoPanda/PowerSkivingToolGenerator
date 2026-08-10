/**
 * useSvgViewport.ts — SVG 视口缩放/平移/复位的深模块
 *
 * 两个绘图组件（ToothProfileSvg / GearOutlineSvg）曾经各自实现几乎逐字符一致的
 * viewBox 缩放/平移/复位逻辑（~50 行重复）。此处收拢为一个组合式模块：
 * 小接口 = { viewBox, onWheel, startPan, zoomAt, reset }，实现藏住
 * 鼠标坐标→viewBox 换算、拖拽平移、中心缩放、复位。
 *
 * 深度：调用方（组件 + 测试）从一个小接口获得整块视口行为；算法只在模块内维护。
 */
import { ref, type Ref } from 'vue'

/** SVG 视口模块的接口：viewBox 是唯一状态，其余为事件处理与动作. */
export interface SvgViewport {
  /** [minX, minY, width, height]，与 SVG viewBox 绑定. */
  viewBox: Ref<[number, number, number, number]>
  /** 滚轮缩放（以鼠标为中心，1.1 倍步进；ctrl 让位浏览器）. */
  onWheel: (e: WheelEvent) => void
  /** 拖拽平移（window 级监听，释放自动清理）. */
  startPan: (e: MouseEvent) => void
  /** 中心锚点缩放（factor<1 放大，>1 缩小）. */
  zoomAt: (factor: number) => void
  /** 复位到初始 viewBox. */
  reset: () => void
}

const ZOOM_STEP = 1.1

export function useSvgViewport(initial: [number, number, number, number]): SvgViewport {
  const viewBox = ref<[number, number, number, number]>([...initial])

  function onWheel(e: WheelEvent): void {
    if (e.ctrlKey) return // 保留浏览器 ctrl 缩放行为
    e.preventDefault()
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
    const sx = (e.clientX - rect.left) / rect.width // 0..1
    const sy = (e.clientY - rect.top) / rect.height
    const [minX, minY, w, h] = viewBox.value
    const scale = e.deltaY < 0 ? 1 / ZOOM_STEP : ZOOM_STEP // 上滚放大
    const nw = w * scale
    const nh = h * scale
    // 保持鼠标指向的用户坐标不动
    const ux = minX + sx * w
    const uy = minY + sy * h
    viewBox.value = [ux - sx * nw, uy - sy * nh, nw, nh]
  }

  function startPan(e: MouseEvent): void {
    const target = e.currentTarget as HTMLElement
    let lastX = e.clientX
    let lastY = e.clientY
    const onMove = (ev: MouseEvent): void => {
      ev.preventDefault()
      const rect = target.getBoundingClientRect()
      const [minX, minY, w, h] = viewBox.value
      // 换算：屏幕像素位移 → viewBox 单位
      const dx = ((ev.clientX - lastX) / rect.width) * w
      const dy = ((ev.clientY - lastY) / rect.height) * h
      lastX = ev.clientX
      lastY = ev.clientY
      viewBox.value = [minX - dx, minY - dy, w, h]
    }
    const onUp = (): void => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  function zoomAt(factor: number): void {
    const [minX, minY, w, h] = viewBox.value
    const nw = w * factor
    const nh = h * factor
    viewBox.value = [minX + (w - nw) / 2, minY + (h - nh) / 2, nw, nh]
  }

  function reset(): void {
    viewBox.value = [...initial]
  }

  return { viewBox, onWheel, startPan, zoomAt, reset }
}
