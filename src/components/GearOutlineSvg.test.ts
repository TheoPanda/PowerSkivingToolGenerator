/**
 * GearOutlineSvg — 单元测试
 * 断言：每齿一个闭合 path、缩放/平移交互更新 viewBox、悬停高亮 + tooltip 齿序号、三圆存在.
 */
import { describe, it, expect } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import GearOutlineSvg from './GearOutlineSvg.vue'
import { mockSpec } from './__spec-mock'

function mountOutline(): VueWrapper {
  return mount(GearOutlineSvg, {
    props: { outline: mockSpec().outline },
  })
}

describe('GearOutlineSvg', () => {
  it('每齿渲染一个闭合 path（fill=none, pointer-events=all）', () => {
    const wrapper = mountOutline()
    const paths = wrapper.findAll('.tooth-path')
    expect(paths.length).toBe(mockSpec().outline.teeth.length)
    for (const p of paths) {
      expect(p.attributes('d')?.endsWith('Z')).toBe(true)
      expect(p.attributes('fill')).toBe('none')
      expect(p.attributes('pointer-events')).toBe('all')
    }
  })

  it('齿廓淡灰，四圆全部实线（无虚线/点线）', () => {
    const wrapper = mountOutline()
    expect(wrapper.find('.tooth-path').attributes('stroke')).toBe('#C4CCD4')
    for (const sel of ['.circle-tip', '.circle-root', '.circle-pitch', '.circle-base']) {
      const c = wrapper.find(sel)
      expect(c.exists()).toBe(true)
      // 全部实线：无虚线/点线 dasharray
      expect(c.attributes('stroke-dasharray')).toBeUndefined()
    }
  })

  it('标注齿顶圆/分度圆/基圆/齿根圆四圆，直径自上而下排列，引线起始实心点', () => {
    const wrapper = mountOutline()
    const labels = wrapper.findAll('.circle-label')
    expect(labels.length).toBe(4)
    // 自上而下：齿顶 → 分度 → 基 → 齿根（直径降序）
    expect(labels.map((l) => l.attributes('data-label'))).toEqual([
      'tip',
      'pitch',
      'base',
      'root',
    ])
    expect(wrapper.find('.circle-label[data-label="tip"]').text()).toContain('齿顶圆')
    expect(wrapper.find('.circle-label[data-label="root"]').text()).toContain('齿根圆')
    expect(wrapper.find('.circle-label[data-label="pitch"]').text()).toContain('分度圆')
    expect(wrapper.find('.circle-label[data-label="base"]').text()).toContain('基圆')
    // 引线起始实心点（每标注一个）
    const dots = wrapper.findAll('.leader-dot')
    expect(dots.length).toBe(4)
    for (const g of labels) {
      const dot = g.find('.leader-dot')
      expect(dot.exists()).toBe(true)
      const line = g.find('line')
      expect(dot.attributes('cx')).toBe(line.attributes('x1'))
      expect(dot.attributes('cy')).toBe(line.attributes('y1'))
    }
  })

  it('初始视图为局部：仅最右端齿廓，且包含四尺寸值列', () => {
    const wrapper = mountOutline()
    const vb = (wrapper.find('.outline-svg').attributes('viewBox') ?? '').split(' ').map(Number)
    const [minX, , width] = vb
    // 最右端：viewBox 左边界在齿轮中心右侧（局部，不整圈）
    expect(minX).toBeGreaterThan(0)
    expect(width).toBeLessThan(mockSpec().outline.circles.tip_radius * 3)
    // 尺寸值列（lx = 1.35·r_tip）在视口内
    const lx = mockSpec().outline.circles.tip_radius * 1.35
    expect(lx).toBeGreaterThanOrEqual(minX)
    expect(lx).toBeLessThanOrEqual(minX + width)
  })

  it('悬停某齿 → 高亮 + tooltip 齿序号', async () => {
    const wrapper = mountOutline()
    const first = wrapper.find('.tooth-path')
    await first.trigger('mouseenter')
    await nextTick()
    expect(wrapper.exists()).toBe(true)
    // tooltip 组出现
    const tipG = wrapper.find('.tooth-tooltip')
    expect(tipG.exists()).toBe(true)
    // 悬停齿标记 data-tooth
    expect(wrapper.find('.tooth-hover').exists()).toBe(true)
    await wrapper.find('.tooth-path').trigger('mouseleave')
    await nextTick()
    expect(wrapper.find('.tooth-tooltip').exists()).toBe(false)
  })

  it('滚轮缩放更新 viewBox（放大后可见区域变小）', async () => {
    const wrapper = mountOutline()
    const svg = wrapper.find('.outline-svg')
    const before: string = svg.attributes('viewBox') ?? ''
    const parse = (s: string): number[] => s.split(/[\s,]+/).map(Number)
    const [bx, by, bw, bh] = parse(before)
    const rect = { left: 0, top: 0, width: 100, height: 100 }
    svg.element.getBoundingClientRect = vi_getRect(rect)
    const wheel = new WheelEvent('wheel', {
      deltaY: -120,
      clientX: 50,
      clientY: 50,
      bubbles: true,
      cancelable: true,
    })
    svg.element.dispatchEvent(wheel)
    await nextTick()
    const after = svg.attributes('viewBox') ?? ''
    const [ax, ay, aw, ah] = parse(after)
    expect(aw).toBeLessThan(bw)
    expect(ah).toBeLessThan(bh)
    expect(ay).not.toBe(by)
    expect(ax).not.toBe(bx)
  })

  it('按钮缩放更新 viewBox', async () => {
    const wrapper = mountOutline()
    const svg = wrapper.find('.outline-svg')
    const before = (svg.attributes('viewBox') ?? '').split(' ').map(Number)
    const zoomInBtn = wrapper.findAll('.ctl-btn').find((b) => b.text() === '＋')
    expect(zoomInBtn).toBeTruthy()
    await zoomInBtn!.trigger('click')
    await nextTick()
    const after = (svg.attributes('viewBox') ?? '').split(' ').map(Number)
    expect(after[2]).toBeLessThan(before[2])
  })

  it('拖拽平移更新 viewBox（鼠标按下 → 移动 → 释放）', async () => {
    const wrapper = mountOutline()
    const svg = wrapper.find('.outline-svg')
    const before = (svg.attributes('viewBox') ?? '').split(' ').map(Number)
    const rect = { left: 0, top: 0, width: 100, height: 100 }
    svg.element.getBoundingClientRect = vi_getRect(rect)
    const down = new MouseEvent('mousedown', { clientX: 50, clientY: 50, bubbles: true })
    svg.element.dispatchEvent(down)
    const move = new MouseEvent('mousemove', { clientX: 60, clientY: 50, bubbles: true })
    window.dispatchEvent(move)
    const up = new MouseEvent('mouseup', { bubbles: true })
    window.dispatchEvent(up)
    await nextTick()
    const after = (svg.attributes('viewBox') ?? '').split(' ').map(Number)
    // 右移 10px → 内容右移，viewBox 左边界减小
    expect(after[0]).toBeLessThan(before[0])
  })
})

function vi_getRect(rect: { left: number; top: number; width: number; height: number }) {
  return () =>
    ({
      toJSON: () => ({ x: rect.left, y: rect.top, width: rect.width, height: rect.height }),
      x: rect.left,
      y: rect.top,
      left: rect.left,
      top: rect.top,
      right: rect.left + rect.width,
      bottom: rect.top + rect.height,
      width: rect.width,
      height: rect.height,
    }) as DOMRect
}
