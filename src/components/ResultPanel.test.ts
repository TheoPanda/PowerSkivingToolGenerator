/**
 * ResultPanel — 单元测试
 * 断言：无结果不渲染 / 生成后待模型显示（reveal）才弹出 / 渲染 6 行 + 规格按钮 /
 *       收起 / 关闭+胶囊唤出 / 标题栏拖动更新位置 / 四向贴边吸附 / 查看规格经 IPC 打开独立窗口。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import ResultPanel from './ResultPanel.vue'
import {
  workpieceState,
  movePanel,
  setWorkpieceResult,
  revealResultPanel,
} from '../composables/useWorkpieceState'
import { mockSpec } from './__spec-mock'
import type { WorkpieceResult } from '../api'

const RESULT: WorkpieceResult = {
  d_a: 107.5,
  d_f: 96.25,
  r_b: 48.164,
  r_pw: 51.25,
  m_t: 2.5,
  alpha_t_deg: 20,
  z_w: 41,
}

function resetState(): void {
  workpieceState.result = null
  workpieceState.spec = null
  workpieceState.open = false
  workpieceState.revealed = false
  workpieceState.collapsed = false
  workpieceState.pos = { x: 24, y: 64 }
}

/** 模拟完整流程：生成结果 → 模型显示完成 → 面板唤出. */
function generatedAndRevealed(): void {
  setWorkpieceResult(RESULT, mockSpec())
  revealResultPanel()
}

async function releaseDrag(wrapper: VueWrapper): Promise<void> {
  await wrapper.find('.rp-header').trigger('mousedown', { clientX: 0, clientY: 0 })
  window.dispatchEvent(new MouseEvent('mouseup'))
  await nextTick()
}

describe('ResultPanel', () => {
  beforeEach(() => {
    resetState()
    vi.restoreAllMocks()
  })

  it('无结果时既不渲染面板也不渲染胶囊', () => {
    const wrapper = mount(ResultPanel)
    expect(wrapper.find('.result-panel').exists()).toBe(false)
    expect(wrapper.find('.result-capsule').exists()).toBe(false)
  })

  it('生成完成但模型未显示 → 面板不弹出（等待 reveal）', () => {
    setWorkpieceResult(RESULT, mockSpec())
    const wrapper = mount(ResultPanel)
    expect(workpieceState.open).toBe(false)
    expect(workpieceState.revealed).toBe(false)
    expect(wrapper.find('.result-panel').exists()).toBe(false)
    expect(wrapper.find('.result-capsule').exists()).toBe(false)
  })

  it('模型显示完成（reveal）→ 渲染标题 + 6 行摘要 + 查看齿轮规格按钮', () => {
    generatedAndRevealed()
    const wrapper = mount(ResultPanel)
    expect(wrapper.find('.result-panel').exists()).toBe(true)
    expect(wrapper.find('.rp-title').text()).toContain('计算结果')
    const rows = wrapper.findAll('.result-row')
    expect(rows.length).toBe(6)
    expect(rows[0].text()).toContain('齿顶圆')
    expect(rows[0].text()).toContain('107.50')
    expect(rows[5].text()).toContain('α_t')
    expect(wrapper.find('button[data-test="view-spec"]').text()).toContain('查看齿轮规格')
  })

  it('收起 → 身体区隐藏、按钮变 ▲；再点恢复', async () => {
    generatedAndRevealed()
    const wrapper = mount(ResultPanel)
    const collapseBtn = wrapper.find('button[title="收起"]')
    await collapseBtn.trigger('click')
    expect(workpieceState.collapsed).toBe(true)
    expect(wrapper.find('.rp-body').exists()).toBe(false)
    expect(wrapper.find('button[title="收起"]').text()).toBe('▲')
    await wrapper.find('button[title="收起"]').trigger('click')
    expect(workpieceState.collapsed).toBe(false)
    expect(wrapper.find('.rp-body').exists()).toBe(true)
  })

  it('关闭 → 面板消失、原位显示胶囊；点击胶囊重新打开', async () => {
    generatedAndRevealed()
    const wrapper = mount(ResultPanel)
    await wrapper.find('button[title="关闭"]').trigger('click')
    expect(workpieceState.open).toBe(false)
    expect(wrapper.find('.result-panel').exists()).toBe(false)
    const capsule = wrapper.find('.result-capsule')
    expect(capsule.exists()).toBe(true)
    expect(capsule.text()).toContain('计算结果')
    await capsule.trigger('click')
    expect(workpieceState.open).toBe(true)
    expect(workpieceState.collapsed).toBe(false)
    expect(wrapper.find('.result-panel').exists()).toBe(true)
  })

  it('拖动标题栏 → 位置更新（远离吸附区时不被吸附）', async () => {
    generatedAndRevealed()
    const wrapper = mount(ResultPanel)
    const header = wrapper.find('.rp-header')
    header.trigger('mousedown', { clientX: 100, clientY: 100 })
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 300, clientY: 250 }))
    window.dispatchEvent(new MouseEvent('mouseup'))
    await nextTick()
    // 默认 (24,64) + (200,150) = (224,214)，不在任何吸附阈值内
    expect(workpieceState.pos).toEqual({ x: 224, y: 214 })
    const style = wrapper.find('.result-panel').attributes('style') ?? ''
    expect(style).toContain('left: 224px')
    expect(style).toContain('top: 214px')
  })

  it('贴边吸附：左贴与 MainPanel 左缘对齐（24px）', async () => {
    generatedAndRevealed()
    const wrapper = mount(ResultPanel)
    movePanel({ x: 40, y: 400 })
    await releaseDrag(wrapper)
    expect(workpieceState.pos.x).toBe(24)
    expect(workpieceState.pos.y).toBe(400)
  })

  it('贴边吸附：右贴与左同边距（24px）', async () => {
    generatedAndRevealed()
    const wrapper = mount(ResultPanel)
    movePanel({ x: 650, y: 400 })
    await releaseDrag(wrapper)
    expect(workpieceState.pos.x).toBe(window.innerWidth - 320 - 24)
    expect(workpieceState.pos.y).toBe(400)
  })

  it('贴边吸附：上贴保持合理边距（标题栏 40px 下 + 24px）', async () => {
    generatedAndRevealed()
    const wrapper = mount(ResultPanel)
    movePanel({ x: 300, y: 90 })
    await releaseDrag(wrapper)
    expect(workpieceState.pos.y).toBe(64)
    expect(workpieceState.pos.x).toBe(300)
  })

  it('贴边吸附：下贴保持底边距 24px', async () => {
    generatedAndRevealed()
    const wrapper = mount(ResultPanel)
    // mock 面板实际高度（jsdom 无布局，offsetHeight=0）
    Object.defineProperty(wrapper.find('.result-panel').element, 'offsetHeight', {
      value: 220,
      configurable: true,
    })
    movePanel({ x: 300, y: 700 })
    await releaseDrag(wrapper)
    expect(workpieceState.pos.y).toBe(window.innerHeight - 220 - 24)
    expect(workpieceState.pos.x).toBe(300)
  })

  it('拖动受窗口边界限制（越界拖动 + 吸附后仍在窗口内）', async () => {
    generatedAndRevealed()
    const wrapper = mount(ResultPanel)
    Object.defineProperty(wrapper.find('.result-panel').element, 'offsetHeight', {
      value: 220,
      configurable: true,
    })
    const header = wrapper.find('.rp-header')
    header.trigger('mousedown', { clientX: 0, clientY: 0 })
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 100000, clientY: 100000 }))
    window.dispatchEvent(new MouseEvent('mouseup'))
    await nextTick()
    const { x, y } = workpieceState.pos
    expect(x).toBeGreaterThanOrEqual(0)
    expect(x + 320).toBeLessThanOrEqual(window.innerWidth)
    expect(y).toBeGreaterThanOrEqual(0)
    expect(y + 220).toBeLessThanOrEqual(window.innerHeight)
  })

  it('点击「查看齿轮规格」→ 经 IPC 打开独立窗口（spec 深拷贝）', async () => {
    generatedAndRevealed()
    const wrapper = mount(ResultPanel)
    const openSpecWindow = vi.mocked(window.electronAPI!.openSpecWindow)
    await wrapper.find('button[data-test="view-spec"]').trigger('click')
    expect(openSpecWindow).toHaveBeenCalledTimes(1)
    expect(openSpecWindow).toHaveBeenCalledWith(mockSpec())
  })
})
