/**
 * ToolSolidPanel — 组件测试（TO-5）
 *
 * 断言：三档披露分组存在与默认开合、锁定项 disabled + 缺口编号 tooltip、
 *       dirty 高亮切换（快照对比）、请求 pending 禁用、错误就地展示、过期徽标时序。
 * 规则本体（黄警/红错分类矩阵）在 toolSolidValidation.test.ts；导出量公式 golden 在
 * toolSolidExports.test.ts —— 这里只测组件接线。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { nextTick, reactive, type ComponentPublicInstance } from 'vue'
import ToolSolidPanel from './ToolSolidPanel.vue'
import * as api from '../api'
import { resetLayersState, useLayers } from '../composables/useLayers'
import { resetToolStaleState } from '../composables/useToolStale'
import { gearParamsKey, type GearParams } from '../composables/useGearParams'

type PanelInstance = ComponentPublicInstance & {
  expandedSections: { required: boolean; optional: boolean; derived: boolean }
  toggleSection: (key: 'required' | 'optional' | 'derived') => void
  pendingChanges: boolean
  workpieceStale: boolean
  staleBannerVisible: boolean
  generateError: string | null
}

const MOCK_TOOL_RING: api.ToolRingResponse = {
  layer: { id: 'toolRing', glb_base64: 'Z2xURg==' },
  coord_frame: 'T',
  source: '模块③ B 方案 v2',
  meta: {
    r_limit_mm: 40.45, root_radius_mm: 36.2, root_offset_mm: 4.24,
    arch_spread_deg: 5.7, pitch_z_mm: 24.276, loop_points: 130,
    n_sections: 5, volume_mm3: 45.6, z_t: 41,
  },
}

/** 与 MainPanel provide 的算例1 默认工件一致（z_w=82 → z_t 推荐区间 ≈41~54.9）. */
function defaultParams(): GearParams {
  return {
    profile_type: 'involute',
    k_io: -1,
    m_n: 2.0,
    z_w: 82,
    β_w: 0,
    j_w: 1,
    b_w: 20,
    toothMethod: 'x_w',
    x_w: 0,
    W_k: null,
    k_teeth: null,
    M: null,
    d_p: null,
    d_rim: null,
    α_n: 20,
    h_an: 1,
    c_n: 0.25,
    ρ_f: 0.38,
    rho_tip: 0,
    root_fillet: true,
    tip_mode: 'none',
    chamfer_tip: 0,
  }
}

function mountPanel(overrides?: Partial<GearParams>): VueWrapper<PanelInstance> {
  const gearParams = reactive<GearParams>({ ...defaultParams(), ...overrides })
  return mount(ToolSolidPanel, {
    global: {
      provide: { [gearParamsKey]: gearParams },
    },
  }) as VueWrapper<PanelInstance>
}

/** 必填组内的 number 输入序（模板顺序）：z_t / β_t / L。锁定 select 与 segmented 不在其列. */
function requiredInputsOf(wrapper: VueWrapper<PanelInstance>): ReturnType<VueWrapper['findAll']> {
  return wrapper.findAll('.glass-collapse')[0].findAll('input')
}

function collectLayerReadyIds(): { ids: string[]; detach: () => void } {
  const ids: string[] = []
  const handler = (e: Event): void => { ids.push(((e as CustomEvent).detail as { id: string }).id) }
  window.addEventListener('gear:layer-ready', handler)
  return { ids, detach: (): void => window.removeEventListener('gear:layer-ready', handler) }
}

beforeEach(() => {
  resetLayersState()
  resetToolStaleState() // 过期态势真值在模块级单例（评审 A1），逐用例隔离
})

describe('ToolSolidPanel — 三档披露表单（PRD §4 骨架）', () => {
  it('三组 .glass-collapse 存在且标题为 必填/可默认/导出量，默认：必填展开、其余收起', () => {
    const wrapper = mountPanel()
    const collapses = wrapper.findAll('.glass-collapse')
    expect(collapses).toHaveLength(3)
    expect(
      collapses.map((c) => c.find('.glass-collapse-header').text()),
    ).toEqual([
      expect.stringContaining('必填'),
      expect.stringContaining('可默认'),
      expect.stringContaining('导出量'),
    ])
    const sections = wrapper.vm.expandedSections
    expect(sections.required).toBe(true)
    expect(sections.optional).toBe(false)
    expect(sections.derived).toBe(false)
  })

  it('可默认组收起态徽标显示当前默认值（γ₀=5° / α₀=8° / n_L=16 / 螺旋导程法）', async () => {
    const wrapper = mountPanel()
    const badge = wrapper.find('[data-test="optional-defaults-badge"]')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('γ₀ 5°')
    expect(badge.text()).toContain('α₀ 8°')
    expect(badge.text()).toContain('n_L 16')
    expect(badge.text()).toContain('螺旋导程法')

    // 展开后徽标让位给字段本体
    wrapper.vm.toggleSection('optional')
    await nextTick()
    expect(wrapper.find('[data-test="optional-defaults-badge"]').exists()).toBe(false)
  })

  it('可默认组「一律有值」：收起不丢数据，字段输入框带默认值 5 / 8 / 16', async () => {
    const wrapper = mountPanel()
    wrapper.vm.toggleSection('optional')
    await nextTick()
    // 折叠只靠 CSS max-height 收起，DOM 一直存在 —— 断言值而非可见性
    const inputs = wrapper.findAll('.glass-collapse')[1].findAll('input')
    expect((inputs[0].element as HTMLInputElement).value).toBe('5')   // γ₀
    expect((inputs[1].element as HTMLInputElement).value).toBe('8')   // α₀
    expect((inputs[2].element as HTMLInputElement).value).toBe('16')  // n_L
  })

  it('j_t 用 segmented ±1 表达且点击写回参数（U7：β 数值恒正、旋向由 j_t 携带）', async () => {
    const wrapper = mountPanel()
    const neg = wrapper.find('[data-test="tool-j-t-neg"]')
    const pos = wrapper.find('[data-test="tool-j-t-pos"]')
    expect(neg.classes()).toContain('active') // 默认 −1（算例1 左旋）
    expect(pos.classes()).not.toContain('active')
    await pos.trigger('click')
    expect(pos.classes()).toContain('active')
    expect(neg.classes()).not.toContain('active')
  })
})

describe('ToolSolidPanel — 锁定项 + 缺口编号 tooltip（PRD §7 纪律）', () => {
  it('三个锁定 select 均 disabled 且 tooltip 带对应缺口编号与「待销项后开放」措辞', () => {
    const wrapper = mountPanel()
    for (const [sel, gaps] of [
      ['tool-tool_type', ['T7', 'T15']],
      ['tool-rake_type', ['W5']],
      ['tool-flank_method', ['T15']],
    ] as Array<[string, string[]]>) {
      const el = wrapper.find(`select[data-test="${sel}"]`)
      expect(el.exists()).toBe(true)
      expect(el.attributes('disabled')).toBeDefined()
      const title = el.attributes('title') ?? ''
      for (const gap of gaps) expect(title).toContain(gap)
      expect(title).toContain('待销项后开放')
    }
  })

  it('α₀ 行角标注明基线出处=算例2 与 W2 待销项（Q11-b 否决对齐文献 6°）', () => {
    const wrapper = mountPanel()
    const note = wrapper.find('[data-test="alpha-0-note"]')
    expect(note.exists()).toBe(true)
    const title = note.attributes('title') ?? ''
    expect(title).toContain('算例2')
    expect(title).toContain('W2')
  })
})

describe('ToolSolidPanel — 校验联动（PRD §5.2）', () => {
  it('z_t 越出推荐区间：blur 后黄警（含区间数字），不阻断生成按钮', async () => {
    const wrapper = mountPanel()
    const zt = requiredInputsOf(wrapper)[0]
    await zt.setValue(70)
    await zt.trigger('blur')
    await nextTick()

    const warn = wrapper.findAll('.glass-field-hint.warn').find((h) => h.text().includes('41'))
    expect(warn).toBeTruthy()
    if (warn) expect(warn.text()).toContain('54.9') // 0.67×82 即时派生（Q9-B）
    expect(wrapper.find('button[data-test="generate-tool-ring"]').attributes('disabled')).toBeUndefined()
  })

  it('硬非法（L≤0）：红错即时可见（无需 blur）、按钮禁用', async () => {
    const wrapper = mountPanel()
    await requiredInputsOf(wrapper)[2].setValue(0)
    await nextTick()

    const errHint = wrapper.findAll('.glass-field-hint').find((h) => h.text().includes('L 必须 > 0'))
    expect(errHint).toBeTruthy()
    expect(wrapper.find('button[data-test="generate-tool-ring"]').attributes('disabled')).toBeDefined()
  })

  it('黄警只在 blur 后浮现（沿用 GearParamsPanel @blur 节奏，不抢戏）', async () => {
    const wrapper = mountPanel()
    await requiredInputsOf(wrapper)[1].setValue(25) // 不 blur
    await nextTick()
    expect(wrapper.findAll('.glass-field-hint.warn')).toHaveLength(0)

    const bt = requiredInputsOf(wrapper)[1]
    await bt.trigger('blur')
    await nextTick()
    const warn = wrapper.findAll('.glass-field-hint.warn').find((h) => h.text().includes('10~20'))
    expect(warn).toBeTruthy()
    if (warn) expect(warn.text()).toContain('W15')
  })

  it('改工件齿数 → 已浮现的区间警告文字即时刷新（Q9-B 裁决）', async () => {
    const gearParams = reactive<GearParams>(defaultParams())
    const wrapper = mount(ToolSolidPanel, {
      global: { provide: { [gearParamsKey]: gearParams } },
    }) as VueWrapper<PanelInstance>

    const zt = requiredInputsOf(wrapper)[0]
    await zt.setValue(48)          // 对 z_w=82 属区间内
    await zt.trigger('blur')
    await nextTick()
    expect(wrapper.findAll('.glass-field-hint.warn')).toHaveLength(0)

    gearParams.z_w = 100           // 新区间 50~67 → 48 变低侧越界，无需再触碰字段
    await nextTick()
    const warn = wrapper.findAll('.glass-field-hint.warn').find((h) => h.text().includes('50'))
    expect(warn).toBeTruthy()
  })

  it('AC 开箱即可生成：默认参数无红错、按钮可用', () => {
    const wrapper = mountPanel()
    expect(wrapper.find('button[data-test="generate-tool-ring"]').attributes('disabled')).toBeUndefined()
  })

  it('工件缺参（m_n=null）→ 禁用并提示先完成步骤1（不代填任何数值）', () => {
    const wrapper = mountPanel({ m_n: null })
    expect(wrapper.find('[data-test="workpiece-missing-hint"]').exists()).toBe(true)
    expect(wrapper.find('button[data-test="generate-tool-ring"]').attributes('disabled')).toBeDefined()
  })
})

describe('ToolSolidPanel — 手动生成 + 图层替换（Q2-a）', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'fetchEnvelopeToolRing').mockResolvedValue(MOCK_TOOL_RING)
  })

  it('点生成 → 调 tool_ring 端点（携带 wire 三分片）→ 派发 toolRing 图层事件 + 清 dirty 高亮', async () => {
    const { ids, detach } = collectLayerReadyIds()
    try {
      const wrapper = mountPanel()
      expect(wrapper.vm.pendingChanges).toBe(true) // 尚未成功生成过整环

      await wrapper.find('button[data-test="generate-tool-ring"]').trigger('click')
      await flushPromises()
      await nextTick()

      expect(api.fetchEnvelopeToolRing).toHaveBeenCalledTimes(1)
      expect(vi.mocked(api.fetchEnvelopeToolRing).mock.calls[0][0]).toMatchObject({
        tool_type: 'cylindrical',
        flank_method: 'helical_lead',
        resharpening: { L: 20, n_L: 16 },
        tool: { z_t: 41, beta_t_deg: 15, j_t: -1, gamma_0_deg: 5, alpha_0_deg: 8 },
      })
      // 与 WorkpieceViewer.dispatchLayer 同一通道（MainView.addLayer 替换同 id 层）
      expect(ids).toEqual(['toolRing'])
      expect(wrapper.vm.pendingChanges).toBe(false)
      expect(wrapper.find('[data-test="pending-hint"]').exists()).toBe(false)
    } finally {
      detach()
    }
  })

  it('生成后改动任一刀具字段 → dirty 高亮回来（快照对比，不自动重生成）', async () => {
    const wrapper = mountPanel()
    await wrapper.find('button[data-test="generate-tool-ring"]').trigger('click')
    await flushPromises()
    expect(wrapper.vm.pendingChanges).toBe(false)

    await requiredInputsOf(wrapper)[0].setValue(33)
    await nextTick()
    expect(wrapper.vm.pendingChanges).toBe(true)
    expect(wrapper.find('button[data-test="generate-tool-ring"]').classes()).toContain('dirty')
    expect(wrapper.find('[data-test="pending-hint"]').text()).toContain('有待应用的变更')
  })

  it('请求期间禁用防连击，结束后恢复可用', async () => {
    let release!: (v: api.ToolRingResponse) => void
    vi.spyOn(api, 'fetchEnvelopeToolRing').mockReturnValue(
      new Promise<api.ToolRingResponse>((resolve) => { release = resolve }),
    )
    const wrapper = mountPanel()
    const btn = wrapper.find('button[data-test="generate-tool-ring"]')
    await btn.trigger('click')
    await nextTick()
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.text()).toContain('生成中')

    release(MOCK_TOOL_RING)
    await flushPromises()
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('失败就地展示仓库契约 error 文案；dirty 与过期位都不被清除', async () => {
    vi.spyOn(api, 'fetchEnvelopeToolRing').mockRejectedValue(
      new Error('Σ=0：刮齿需轴交角提供切削速度分量'),
    )
    const layers = useLayers()
    layers.setLayerStale('toolRing', true)
    const wrapper = mountPanel()

    await wrapper.find('button[data-test="generate-tool-ring"]').trigger('click')
    await flushPromises()

    const errBox = wrapper.find('[data-test="generate-error"]')
    expect(errBox.exists()).toBe(true)
    expect(errBox.text()).toContain('Σ=0')
    expect(wrapper.vm.generateError).toContain('Σ=0')
    expect(wrapper.vm.pendingChanges).toBe(true) // 快照未刷新
    expect(layers.state.stale.toolRing).toBe(true) // 未成功替换 → 圆点保留
  })
})

describe('ToolSolidPanel — 过期徽标时序（Q10-b / PRD §5.4）', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'fetchEnvelopeToolRing').mockResolvedValue(MOCK_TOOL_RING)
  })

  function dispatchModelReady(): void {
    // MainPanel.onModelReady 的转发事件（WorkpieceViewer emit 'model-ready' → window 通道）
    window.dispatchEvent(new CustomEvent('gear:model-ready', { detail: 'Z2xURg==' }))
  }

  it('首帧自动生成也会派发 gear:model-ready：未生成本面板刀具前只见按钮高亮、不弹过期横幅', async () => {
    const wrapper = mountPanel()
    dispatchModelReady()
    await nextTick()

    expect(wrapper.vm.workpieceStale).toBe(true)
    expect(useLayers().state.stale.toolRing).toBe(true) // 图层圆点即刻反映旧件重生成
    expect(wrapper.vm.staleBannerVisible).toBe(false)   // 但「刀具基于旧工件参数」尚无可指对象
    expect(wrapper.find('[data-test="stale-banner"]').exists()).toBe(false)
    expect(wrapper.find('button[data-test="generate-tool-ring"]').classes()).toContain('dirty')
  })

  it('生成本面板整环后工件再变 → 面板横幅亮起 + useLayers 过期位点亮（图层列表圆点共用真值）', async () => {
    const wrapper = mountPanel()
    await wrapper.find('button[data-test="generate-tool-ring"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="stale-banner"]').exists()).toBe(false)
    expect(useLayers().state.stale.toolRing).toBeUndefined()

    dispatchModelReady()
    await nextTick()
    expect(wrapper.find('[data-test="stale-banner"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="stale-banner"]').text()).toContain('工件已变更')
    expect(useLayers().state.stale.toolRing).toBe(true)
  })

  it('过期态势下重新生成 → 横幅熄灭、过期圆点同步消失、dirty 清零', async () => {
    const wrapper = mountPanel()
    dispatchModelReady()
    await wrapper.find('button[data-test="generate-tool-ring"]').trigger('click')
    await flushPromises()

    dispatchModelReady() // 再次变更工件 → 横幅复现
    await nextTick()
    expect(wrapper.find('[data-test="stale-banner"]').exists()).toBe(true)

    await wrapper.find('button[data-test="generate-tool-ring"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="stale-banner"]').exists()).toBe(false)
    expect('toolRing' in useLayers().state.stale).toBe(false)
    expect(wrapper.vm.pendingChanges).toBe(false)
  })

  it('评审 A1 回归：卸载期间发生的工件重生成，重进面板仍如实亮横幅（监听跨挂载常驻）', async () => {
    // 第一挂载：成功生成整环（hasGeneratedOnce=true，过期门槛就绪）
    const w1 = mountPanel()
    await w1.find('button[data-test="generate-tool-ring"]').trigger('click')
    await flushPromises()
    w1.unmount()

    // 面板不在场时工件重生成——旧实现里这正是监听真空期，事件被静默漏接
    dispatchModelReady()
    await nextTick()

    // 重进步骤3：单例状态存续 → 横幅立即呈现过期态势
    const w2 = mountPanel()
    await nextTick()
    expect(w2.vm.workpieceStale).toBe(true)
    expect(w2.vm.staleBannerVisible).toBe(true)
    expect(w2.find('[data-test="stale-banner"]').text()).toContain('工件已变更')
    expect(useLayers().state.stale.toolRing).toBe(true)
  })
})
