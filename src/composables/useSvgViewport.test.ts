/**
 * useSvgViewport — 单元测试
 * 断言：中心缩放 / 复位 / 滚轮以鼠标为中心缩放 / 拖拽平移。
 * 算法脱离组件 DOM，直接对模块接口测试。
 */
import { describe, it, expect } from 'vitest'
import { useSvgViewport } from './useSvgViewport'

function rectEl(width = 100, height = 100): HTMLElement {
  return {
    getBoundingClientRect: () =>
      ({ left: 0, top: 0, width, height }) as DOMRect,
  } as HTMLElement
}

describe('useSvgViewport', () => {
  it('zoomAt 中心锚点缩放', () => {
    const vp = useSvgViewport([0, 0, 100, 100])
    vp.zoomAt(0.9)
    expect(vp.viewBox.value).toEqual([5, 5, 90, 90])
  })

  it('reset 回到初始 viewBox', () => {
    const vp = useSvgViewport([0, 0, 100, 100])
    vp.zoomAt(0.5)
    expect(vp.viewBox.value[2]).toBe(50)
    vp.reset()
    expect(vp.viewBox.value).toEqual([0, 0, 100, 100])
  })

  it('onWheel 以鼠标为中心缩放（上滚放大、下滚缩小）', () => {
    const vp = useSvgViewport([0, 0, 100, 100])
    const el = rectEl()
    vp.onWheel({
      currentTarget: el,
      clientX: 50,
      clientY: 50,
      deltaY: 120,
      ctrlKey: false,
      preventDefault: () => {},
    } as unknown as WheelEvent)
    // 下滚 → scale 1.1，鼠标指向的用户坐标保持不动
    const v = vp.viewBox.value
    expect(v[0]).toBeCloseTo(-5)
    expect(v[1]).toBeCloseTo(-5)
    expect(v[2]).toBeCloseTo(110)
    expect(v[3]).toBeCloseTo(110)
  })

  it('onWheel 忽略 ctrl 键（让位浏览器缩放）', () => {
    const vp = useSvgViewport([0, 0, 100, 100])
    let prevented = false
    vp.onWheel({
      currentTarget: rectEl(),
      clientX: 50,
      clientY: 50,
      deltaY: 120,
      ctrlKey: true,
      preventDefault: () => {
        prevented = true
      },
    } as unknown as WheelEvent)
    expect(prevented).toBe(false)
    expect(vp.viewBox.value).toEqual([0, 0, 100, 100])
  })

  it('startPan 拖拽平移（窗口级监听）', () => {
    const vp = useSvgViewport([0, 0, 100, 100])
    vp.startPan({ currentTarget: rectEl(), clientX: 50, clientY: 50 } as unknown as MouseEvent)
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 60, clientY: 50 }))
    window.dispatchEvent(new MouseEvent('mouseup'))
    // 右移 10px → 内容右移，viewBox 左边界减小
    expect(vp.viewBox.value[0]).toBe(-10)
    expect(vp.viewBox.value[1]).toBe(0)
  })
})
