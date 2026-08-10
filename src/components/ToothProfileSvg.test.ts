/**
 * ToothProfileSvg — 单元测试
 * 断言：7 项 ISO 尺寸标注渲染、齿廓 path / 中心线 / 分度线存在且线型正确、
 *       齿顶圆浅灰虚线、平行弧端实心点、高度尺寸平行左齿中分线。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ToothProfileSvg from './ToothProfileSvg.vue'
import { mockSpec } from './__spec-mock'
import type { SingleToothSpec } from '../api'

describe('ToothProfileSvg', () => {
  it('渲染 7 项 ISO 尺寸标注（data-role）', () => {
    const wrapper = mount(ToothProfileSvg, {
      props: { singleTooth: mockSpec().single_tooth },
    })
    const groups = wrapper.findAll('.annotation-g')
    const roles = groups.map((g) => g.attributes('data-role')).sort()
    expect(roles).toEqual(
      [
        'tooth_thickness',
        'circular_pitch',
        'tip_fillet',
        'root_fillet',
        'addendum',
        'dedendum',
        'whole_depth',
      ].sort(),
    )
  })

  it('渲染齿廓 outline path', () => {
    const wrapper = mount(ToothProfileSvg, {
      props: { singleTooth: mockSpec().single_tooth },
    })
    const profile = wrapper.find('.profile-outline')
    expect(profile.exists()).toBe(true)
    expect(profile.attributes('d')?.startsWith('M ')).toBe(true)
  })

  it('中心线、左齿中分线、分度线线型可区分（分度线为点画线）', () => {
    const wrapper = mount(ToothProfileSvg, {
      props: { singleTooth: mockSpec().single_tooth },
    })
    const center = wrapper.find('.center-line')
    const left = wrapper.find('.left-center-line')
    const pitch = wrapper.find('.pitch-line')
    expect(center.attributes('stroke-dasharray')).toBe('16 4 2 4')
    expect(left.attributes('stroke-dasharray')).toBe('16 4 2 4')
    expect(pitch.attributes('stroke-dasharray')).toBe('14 4 2 4')
    expect(center.attributes('stroke-dasharray')).not.toBe(pitch.attributes('stroke-dasharray'))
  })

  it('齿顶圆为浅灰虚线，跨三齿一整条', () => {
    const wrapper = mount(ToothProfileSvg, {
      props: { singleTooth: mockSpec().single_tooth },
    })
    const tip = wrapper.find('.tip-circle')
    expect(tip.exists()).toBe(true)
    expect(tip.attributes('stroke')).toBe('#C6CDD4')
    expect(tip.attributes('stroke-dasharray')).toBe('8 5')
    expect(tip.attributes('d')).toContain('L') // 曲线（非单段直线）
  })

  it('平行弧标注（齿厚/齿距）端部有实心点；高度重合线有隔断点', () => {
    const wrapper = mount(ToothProfileSvg, {
      props: { singleTooth: mockSpec().single_tooth },
    })
    const roles: Record<string, number> = {}
    for (const g of wrapper.findAll('.annotation-g')) {
      roles[g.attributes('data-role') ?? ''] = g.findAll('circle.dim-dot').length
    }
    expect(roles.tooth_thickness).toBe(2)
    expect(roles.circular_pitch).toBe(2)
    expect(roles.addendum).toBe(2)
    expect(roles.dedendum).toBe(2)
    // 齿全高两端也有实心点标明起止
    expect(roles.whole_depth).toBe(2)
  })
})

/** 实尺度 mock：m=2.5, z=41 齿廓（齿顶 53.75 / 齿根 48.125 / 分度 51.25）. */
function realSpec(): SingleToothSpec {
  return {
    segments: [
      {
        type: 'polyline',
        points: [
          [48.125, 0],
          [49.5, -1.2],
          [51.25, -1.96],
          [53.75, -2.2],
          [53.75, 2.2],
          [51.25, 1.96],
          [49.5, 1.2],
          [48.125, 0],
        ],
      },
    ],
    center_line: { from_angle_deg: -90, to_angle_deg: 90 },
    pitch_line: { r: 51.25 },
    annotations: {
      tooth_thickness: { value: 3.927 },
      circular_pitch: { value: 7.854 },
      tip_fillet: { value: 0 },
      root_fillet: { value: 0.95 },
      addendum: { value: 2.5 },
      dedendum: { value: 3.125 },
      whole_depth: { value: 5.625 },
    },
  }
}

/** 另一真实规格：m=3, z=30（回退路径，不同几何）——验证中低齿数布局. */
function realSpec2(): SingleToothSpec {
  const m = 3
  const z = 30
  const pitch = (m * z) / 2
  const rTip = pitch + m
  const rRoot = pitch - 1.25 * m
  const sT = (Math.PI * m) / 2
  const pitchY = sT / 2
  const tipY = (sT * (rTip / pitch)) / 2
  return {
    segments: [
      {
        type: 'polyline',
        points: [
          [rRoot, 0],
          [rRoot + 2, -1.3],
          [pitch, -pitchY],
          [rTip - 1, -tipY],
          [rTip, -tipY],
          [rTip, tipY],
          [rTip - 1, tipY],
          [pitch, pitchY],
          [rRoot + 2, 1.3],
          [rRoot, 0],
        ],
      },
    ],
    center_line: { from_angle_deg: -90, to_angle_deg: 90 },
    pitch_line: { r: pitch },
    annotations: {
      tooth_thickness: { value: sT },
      circular_pitch: { value: Math.PI * m },
      tip_fillet: { value: 0 },
      root_fillet: { value: 0.4 * m },
      addendum: { value: m },
      dedendum: { value: 1.25 * m },
      whole_depth: { value: 2.25 * m },
    },
  }
}

interface Box {
  x1: number
  x2: number
  y1: number
  y2: number
}
function intersects(a: Box, b: Box): boolean {
  return !(a.x2 < b.x1 || a.x1 > b.x2 || a.y2 < b.y1 || a.y1 > b.y2)
}
function textBox(x: number, y: number, anchor: string | undefined, label: string): Box {
  const w = label.split('').reduce((acc, ch) => acc + (ch.charCodeAt(0) > 255 ? 12 : 6.5), 0)
  let x1 = 0
  let x2 = 0
  if (anchor === 'end') {
    x1 = x - w
    x2 = x
  } else if (anchor === 'start') {
    x1 = x
    x2 = x + w
  } else {
    x1 = x - w / 2
    x2 = x + w / 2
  }
  return { x1, x2, y1: y - 12, y2: y }
}

/** 左侧高度尺寸（须在左余量，不穿齿形区）；圆角尺寸（靠近中齿，须在中齿中分线右侧）. */
const LEFT_DIMS = ['whole_depth', 'addendum', 'dedendum']

describe('ToothProfileSvg 布局不变量（数值断言，替代目测）', () => {
  const cases = [
    { name: '实尺度 m2.5/z41', spec: realSpec() },
    { name: '实尺度 m3/z30', spec: realSpec2() },
  ]
  for (const { name, spec } of cases) {
    it(`${name}：标注在画布内、高度尺寸在左余量、圆角尺寸在中齿右侧、文字互不重叠`, () => {
      const wrapper = mount(ToothProfileSvg, { props: { singleTooth: spec } })
      const groups = wrapper.findAll('.annotation-g')
      expect(groups.length).toBe(7)
      const toothBox: Box = { x1: 150, x2: 690, y1: 60, y2: 340 }
      const centerX = Number(wrapper.find('.center-line').attributes('x1'))
      const textBoxes: Box[] = []
      for (const g of groups) {
        const role = g.attributes('data-role') ?? ''
        const line = g.find('line')
        const arc = g.find('path.dim-arc')
        const text = g.find('text')
        const isArc = arc.exists()
        const tx = Number(text.attributes('x'))
        const ty = Number(text.attributes('y'))
        const anchor = text.attributes('text-anchor') ?? undefined
        const label = text.text() ?? ''
        if (isArc) {
          // 弧线标注（齿厚/齿距平行弧）：坐标在画布内
          const b = coordBounds(arc.attributes('d') ?? '')
          for (const v of [b.minX, b.maxX]) {
            expect(v).toBeGreaterThanOrEqual(0)
            expect(v).toBeLessThanOrEqual(760)
          }
          for (const v of [b.minY, b.maxY]) {
            expect(v).toBeGreaterThanOrEqual(0)
            expect(v).toBeLessThanOrEqual(360)
          }
        } else {
          const lx1 = Number(line.attributes('x1'))
          const ly1 = Number(line.attributes('y1'))
          const lx2 = Number(line.attributes('x2'))
          const ly2 = Number(line.attributes('y2'))
          for (const v of [lx1, lx2, ly1, ly2]) {
            expect(v).toBeGreaterThanOrEqual(0)
            expect(v).toBeLessThanOrEqual(760)
          }
          for (const v of [ly1, ly2]) {
            expect(v).toBeGreaterThanOrEqual(0)
            expect(v).toBeLessThanOrEqual(360)
          }
          const lineBox: Box = {
            x1: Math.min(lx1, lx2),
            x2: Math.max(lx1, lx2),
            y1: Math.min(ly1, ly2),
            y2: Math.max(ly1, ly2),
          }
          if (LEFT_DIMS.includes(role)) {
            // 高度尺寸：左余量，不穿齿形区
            expect(intersects(lineBox, toothBox)).toBe(false)
          } else {
            // 圆角尺寸：靠近中间齿 → 中分线右侧
            expect(lineBox.x1).toBeGreaterThan(centerX)
          }
        }
        // 文字在画布内
        expect(tx).toBeGreaterThanOrEqual(0)
        expect(tx).toBeLessThanOrEqual(760)
        expect(ty).toBeGreaterThanOrEqual(0)
        expect(ty).toBeLessThanOrEqual(360)
        const tb = textBox(tx, ty, anchor, label)
        if (LEFT_DIMS.includes(role)) expect(intersects(tb, toothBox)).toBe(false)
        textBoxes.push(tb)
      }
      for (let i = 0; i < textBoxes.length; i++) {
        for (let j = i + 1; j < textBoxes.length; j++) {
          expect(intersects(textBoxes[i], textBoxes[j])).toBe(false)
        }
      }
    })
  }

  it('分度线为 1 条连贯点画线曲线（跨三齿，非 3 段分离）', () => {
    const wrapper = mount(ToothProfileSvg, { props: { singleTooth: realSpec() } })
    const lines = wrapper.findAll('.pitch-line')
    expect(lines.length).toBe(1)
    const d = lines[0].attributes('d') ?? ''
    expect(d).toContain('L')
    expect(lines[0].attributes('stroke-dasharray')).toBe('14 4 2 4')
    // 连贯：d 以 M 开头、无 M 中断（除首外无新 M）
    const mCount = d.match(/M/g)?.length ?? 0
    expect(mCount).toBe(1)
  })
})

describe('ToothProfileSvg 缩放平移', () => {
  function getRect(rect: { left: number; top: number; width: number; height: number }) {
    return () =>
      ({
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

  it('滚轮缩放更新 viewBox（缩小后可见区域变大）', async () => {
    const wrapper = mount(ToothProfileSvg, { props: { singleTooth: mockSpec().single_tooth } })
    const svg = wrapper.find('.tooth-svg')
    const before = (svg.attributes('viewBox') ?? '').split(' ').map(Number)
    svg.element.getBoundingClientRect = getRect({ left: 0, top: 0, width: 100, height: 100 })
    const wheel = new WheelEvent('wheel', {
      deltaY: 120,
      clientX: 50,
      clientY: 50,
      bubbles: true,
      cancelable: true,
    })
    svg.element.dispatchEvent(wheel)
    await nextTick()
    const after = (svg.attributes('viewBox') ?? '').split(' ').map(Number)
    expect(after[2]).toBeGreaterThan(before[2])
    expect(after[3]).toBeGreaterThan(before[3])
  })

  it('拖拽平移更新 viewBox', async () => {
    const wrapper = mount(ToothProfileSvg, { props: { singleTooth: mockSpec().single_tooth } })
    const svg = wrapper.find('.tooth-svg')
    const before = (svg.attributes('viewBox') ?? '').split(' ').map(Number)
    svg.element.getBoundingClientRect = getRect({ left: 0, top: 0, width: 100, height: 100 })
    svg.element.dispatchEvent(new MouseEvent('mousedown', { clientX: 50, clientY: 50, bubbles: true }))
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 60, clientY: 50, bubbles: true }))
    window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    await nextTick()
    const after = (svg.attributes('viewBox') ?? '').split(' ').map(Number)
    expect(after[0]).toBeLessThan(before[0])
  })

  it('复位按钮 → viewBox 回到整张画布', async () => {
    const wrapper = mount(ToothProfileSvg, { props: { singleTooth: mockSpec().single_tooth } })
    await wrapper.find('.ctl-btn[title="放大"]').trigger('click')
    await nextTick()
    await wrapper.find('.ctl-btn[title="复位"]').trigger('click')
    await nextTick()
    expect(wrapper.find('.tooth-svg').attributes('viewBox')).toBe('0 0 760 360')
  })

  it('渲染连接齿廓（neighborhood 三齿一体）；无 neighborhood 时回退为目标+邻齿', () => {
    const wrapper = mount(ToothProfileSvg, { props: { singleTooth: mockSpec().single_tooth } })
    // mock 含 neighborhood → 渲染连接主路径，无独立邻齿
    expect(wrapper.find('.profile-outline').exists()).toBe(true)
    expect(wrapper.findAll('.neighbor-outline').length).toBe(0)
    // 回退：无 neighborhood → 目标 + 2 邻齿（浅灰）
    const without: SingleToothSpec = { ...mockSpec().single_tooth, neighborhood: undefined }
    const fb = mount(ToothProfileSvg, { props: { singleTooth: without } })
    expect(fb.findAll('.neighbor-outline').length).toBe(2)
    expect(fb.find('.profile-outline').exists()).toBe(true)
  })

  it('齿廓坐标在齿形区内（根圆闭合弧按短弧采样，不撑成整圆）', () => {
    const wrapper = mount(ToothProfileSvg, { props: { singleTooth: mockSpec().single_tooth } })
    for (const sel of ['.profile-outline', '.neighbor-outline']) {
      const el = wrapper.find(sel)
      if (!el.exists()) continue
      const b = coordBounds(el.attributes('d') ?? '')
      expect(b.minX).toBeGreaterThanOrEqual(140)
      expect(b.maxX).toBeLessThanOrEqual(700)
      expect(b.minY).toBeGreaterThanOrEqual(50)
      expect(b.maxY).toBeLessThanOrEqual(350)
    }
  })

  it('齿廓 path 含圆弧段（arc 端点经旋转修正）', () => {
    const wrapper = mount(ToothProfileSvg, { props: { singleTooth: mockSpec().single_tooth } })
    const d = wrapper.find('.profile-outline').attributes('d') ?? ''
    expect(d).toContain('A ')
  })
})

/** 解析 SVG path d 的坐标范围（M/L 取 2 个、A 取末 2 个，忽略半径/旋转/标志）. */
function coordBounds(d: string): { minX: number; maxX: number; minY: number; maxY: number } {
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  const re = /([MLAZ])|(-?\d+(?:\.\d+)?)/g
  let cmd = ''
  let pending: number[] = []
  let m: RegExpExecArray | null
  while ((m = re.exec(d))) {
    if (m[1]) {
      cmd = m[1]
      pending = []
      continue
    }
    pending.push(Number(m[2]))
    if ((cmd === 'M' || cmd === 'L') && pending.length === 2) {
      const [x, y] = pending
      if (x < minX) minX = x
      if (x > maxX) maxX = x
      if (y < minY) minY = y
      if (y > maxY) maxY = y
      pending = []
    } else if (cmd === 'A' && pending.length === 7) {
      const x = pending[5]
      const y = pending[6]
      if (x < minX) minX = x
      if (x > maxX) maxX = x
      if (y < minY) minY = y
      if (y > maxY) maxY = y
      pending = []
    }
  }
  return { minX, maxX, minY, maxY }
}
