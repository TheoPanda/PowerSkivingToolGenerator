/**
 * InterferenceLegend 组件测试 — 后端权威图例数据渲染（渐变条/刻度/参考灰/过切摘要）.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import InterferenceLegend from './InterferenceLegend.vue'
import { interferenceState, setInterferenceStats, setInterferenceVisible } from '../composables/useInterferenceLegend'
import type { InterferenceStats } from '../api'

/** 与后端 interference.py legend 结构一致的样例数据. */
function fakeStats(minD: number): InterferenceStats {
  return {
    n_interference: 11,
    n_contact_band: 1200,
    n_clearance: 300,
    n_reference: 94,
    min_d_mm: minD,
    clamp_mm: 0.5,
    legend: {
      stops: [
        { t: 0.0, color: [0.888, 0.174, 0.064] },
        { t: 0.25, color: [0.933, 0.356, 0.032] },
        { t: 0.4, color: [1.0, 0.55, 0.0] },
        { t: 0.5, color: [0.1, 0.8, 0.15] },
        { t: 0.6, color: [1.0, 0.75, 0.0] },
        { t: 0.75, color: [0.15, 0.75, 0.2] },
        { t: 1.0, color: [0.12, 0.25, 0.75] },
      ],
      ticks_mm: [-0.5, -0.1, 0.0, 0.1, 0.5],
      reference_color: [0.62, 0.62, 0.66],
    },
  }
}

beforeEach(() => {
  setInterferenceStats(undefined)
  setInterferenceVisible(false)
})

describe('InterferenceLegend 图例', () => {
  it('未激活或无数据时不渲染', () => {
    setInterferenceVisible(true)
    expect(mount(InterferenceLegend).find('[data-test="interference-legend"]').exists()).toBe(false)
    setInterferenceStats(fakeStats(0.2))
    setInterferenceVisible(false)
    expect(mount(InterferenceLegend).find('[data-test="interference-legend"]').exists()).toBe(false)
  })

  it('激活时渲染渐变条（后端 stops → linear-gradient）+ 5 刻度 + 参考灰', () => {
    setInterferenceStats(fakeStats(0.2))
    setInterferenceVisible(true)
    const wrapper = mount(InterferenceLegend)
    expect(wrapper.find('[data-test="interference-legend"]').exists()).toBe(true)
    const bar = wrapper.find('[data-test="interference-legend-bar"]')
    expect(bar.exists()).toBe(true)
    const bg = (bar.element as HTMLElement).style.background
    expect(bg).toContain('linear-gradient')
    expect(bg).toContain('rgb(226, 44, 16)') // t=0 深红 (0.888,0.174,0.064)×255
    expect(bg).toContain('rgb(31, 64, 191)') // t=1 蓝 (0.12,0.25,0.75)×255
    // 刻度：0 居中（(0−(−0.5))/1.0 = 50%），±0.5 在两端
    const ticks = wrapper.findAll('.if-tick')
    expect(ticks.length).toBe(5)
    expect(ticks[2].text()).toBe('0')
    expect(ticks[0].text()).toBe('-0.50')
    // 参考灰 + 齿宽外文字
    expect(wrapper.text()).toContain('齿宽外参考')
    // 语义区段
    expect(wrapper.text()).toContain('过切')
    expect(wrapper.text()).toContain('间隙')
  })

  it('过切摘要：min_d<0 红字「最深过切」，≥0 绿字「无过切」', () => {
    setInterferenceStats(fakeStats(-0.12))
    setInterferenceVisible(true)
    let wrapper = mount(InterferenceLegend)
    const summary = wrapper.find('[data-test="interference-legend-min"]')
    expect(summary.text()).toContain('最深过切')
    expect(summary.text()).toContain('-0.12')
    expect(summary.classes()).toContain('danger')

    setInterferenceStats(fakeStats(0.05))
    wrapper = mount(InterferenceLegend)
    const ok = wrapper.find('[data-test="interference-legend-min"]')
    expect(ok.text()).toBe('无过切')
    expect(ok.classes()).not.toContain('danger')
    expect(interferenceState.stats?.min_d_mm).toBeCloseTo(0.05)
  })
})
