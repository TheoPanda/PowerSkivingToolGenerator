/**
 * WorkpieceViewer — 集成测试
 * 断言：生成成功后结果/spec 写入全局单例（ResultPanel 消费）；
 *       步骤2 内不再渲染结果区与「查看齿轮规格」按钮（已移入独立面板）。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import WorkpieceViewer from './WorkpieceViewer.vue'
import * as api from '../api'
import { workpieceState, revealResultPanel } from '../composables/useWorkpieceState'
import type { GearParams } from '../composables/useGearParams'
import { mockSpec } from './__spec-mock'

function defaultParams(): GearParams {
  return {
    profile_type: 'involute',
    k_io: 1,
    m_n: 2.5,
    z_w: 41,
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

const mockResponse: api.WorkpieceResponse = {
  result: { d_a: 107.5, d_f: 96.25, r_b: 48.164, r_pw: 51.25, m_t: 2.5, alpha_t_deg: 20, z_w: 41 },
  model_glb_base64: 'Z2xURg==',
  spec: mockSpec(),
}

function mountViewer(): VueWrapper {
  const gearParams = reactive<GearParams>(defaultParams())
  return mount(WorkpieceViewer, {
    global: {
      provide: {
        gearParams,
      },
      stubs: {
        ElMessage: true,
      },
    },
  })
}

describe('WorkpieceViewer — 全局结果状态', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'fetchWorkpiece').mockResolvedValue(mockResponse)
    // 重置全局单例（模块级共享，避免跨用例污染）
    workpieceState.result = null
    workpieceState.spec = null
    workpieceState.open = false
    workpieceState.revealed = false
    workpieceState.collapsed = false
    workpieceState.pos = { x: 24, y: 64 }
  })

  it('生成成功后把 result/spec 写入全局单例（面板待模型显示后再唤起）', async () => {
    const wrapper = mountViewer()
    await nextTick()
    await nextTick()
    expect(workpieceState.result?.d_a).toBe(107.5)
    expect(workpieceState.spec).toEqual(mockSpec())
    // 生成完成仅写入结果，面板不立即打开（等待 3D 模型显示后 reveal）
    expect(workpieceState.open).toBe(false)
    expect(workpieceState.revealed).toBe(false)
    // 模型显示完成 → 唤出面板
    revealResultPanel()
    expect(workpieceState.open).toBe(true)
    expect(workpieceState.revealed).toBe(true)
    expect(workpieceState.collapsed).toBe(false)
    expect(wrapper.emitted('model-ready')).toBeTruthy()
  })

  it('步骤2 内不再渲染结果摘要与「查看齿轮规格」按钮（已移入独立面板）', async () => {
    const wrapper = mountViewer()
    await nextTick()
    await nextTick()
    expect(wrapper.find('.result-summary').exists()).toBe(false)
    expect(wrapper.find('button[data-test="view-spec"]').exists()).toBe(false)
  })
})

describe('WorkpieceViewer — 包络计算（子 PRD-2 离散包络）', () => {
  const mockGen: api.SweptCloudResponse = {
    layer: { id: 'swept_cloud', glb_base64: 'Z2xURg==' },
    coord_frame: 'T',
    motion: { n: 200, m: 181, theta_range_deg: 20.0, surface_indices_per_row: 1194, points_vertices_per_row: 200, wireframe_indices_per_row: 2388 },
    install: { a: 39.55, sigma_deg: 15.0 },
  }
  const mockEdge: api.EdgeResponse = {
    layer: { id: 'edge', glb_base64: 'Z2xURg==' },
    coord_frame: 'T',
    coverage_report: { total_points: 200, uncovered: [], coverage_ratio: 1.0, pass: true },
    ffa_um: 0.05,
    segments_meta: [
      { count: 100, continuity: 'continuous' },
      { count: 100, continuity: 'continuous' },
    ],
    install: { a: 39.55, sigma_deg: 15.0 },
  }
  const mockRake: api.RakeResponse = {
    layer: { id: 'rake', glb_base64: 'Z2xURg==' },
    coord_frame: 'T',
    plane: { A: 0.087156, B: 0.257834, C: 0.962250, const: -3.7002 },
    p_ref: [42.455, 0.0, 0.0],
    n_rake: [0.087156, 0.257834, 0.962250],
  }
  const mockFlank: api.FlankResponse = {
    layer: { id: 'flank', glb_base64: 'Z2xURg==' },
    coord_frame: 'T',
    source: '螺旋导程法（K-2.15/16，圆柱刀）',
    flank_method: 'helical_lead',
    lead_pitch: 995.33,
    resharpen_schedule: [
      { i: 1, dL: 0.5, da: 0, a_i: 39.5537 },
      { i: 2, dL: 1.0, da: 0, a_i: 39.5537 },
    ],
  }
  const mockTooth: api.SingleToothResponse = {
    layer: { id: 'singleTooth', glb_base64: 'Z2xURg==' },
    coord_frame: 'T',
    source: '模块③预览',
  }
  const mockAnalytic: api.AnalyticResponse = {
    layer: { id: 'edge', glb_base64: 'Z2xURg==' },
    coord_frame: 'T',
    source: '解析（K-2.8）',
    point_count: 100,
    cross_check: { max_delta_um: 0.5, pass: true },
  }

  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'fetchWorkpiece').mockResolvedValue(mockResponse)
    vi.spyOn(api, 'fetchEnvelopeSweptCloud').mockResolvedValue(mockGen)
    vi.spyOn(api, 'fetchEnvelopeEdge').mockResolvedValue(mockEdge)
    vi.spyOn(api, 'fetchEnvelopeRake').mockResolvedValue(mockRake)
    vi.spyOn(api, 'fetchEnvelopeFlank').mockResolvedValue(mockFlank)
    vi.spyOn(api, 'fetchEnvelopeSingleTooth').mockResolvedValue(mockTooth)
    vi.spyOn(api, 'fetchEnvelopeAnalytic').mockResolvedValue(mockAnalytic)
    workpieceState.result = null
    workpieceState.spec = null
    workpieceState.open = false
    workpieceState.revealed = false
    workpieceState.collapsed = false
    workpieceState.pos = { x: 24, y: 64 }
  })

  it('点「开始包络」→ 依次派发扫掠点云、刃形、前刀面、后刀面、单齿五图层 + 诊断条显示', async () => {
    const wrapper = mountViewer()
    await nextTick()
    await nextTick()

    const layers: string[] = []
    const handler = (e: Event): void => {
      layers.push((e as CustomEvent).detail.id as string)
    }
    window.addEventListener('gear:layer-ready', handler)

    await wrapper.find('button[data-test="run-envelope"]').trigger('click')
    await nextTick()
    await nextTick()

    window.removeEventListener('gear:layer-ready', handler)
    expect(layers).toEqual(['swept_cloud', 'edge', 'rake', 'flank', 'singleTooth'])
    expect(wrapper.find('[data-test="diagnostic-strip"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('ffα')
    expect(wrapper.text()).toContain('覆盖')
  })

  it('ffα 超限时诊断条标失败态', async () => {
    vi.spyOn(api, 'fetchEnvelopeEdge').mockResolvedValue({
      ...mockEdge,
      ffa_um: 0.5,
      coverage_report: { ...mockEdge.coverage_report, pass: false, coverage_ratio: 0.9 },
    })
    const wrapper = mountViewer()
    await nextTick()
    await nextTick()

    await wrapper.find('button[data-test="run-envelope"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(wrapper.find('[data-test="diagnostic-strip"].failed').exists()).toBe(true)
  })

  it('勾选解析路线对拍 → 调 analytic + 显示互检偏差', async () => {
    const wrapper = mountViewer()
    await nextTick()
    await nextTick()
    await wrapper.find('input[data-test="use-analytic"]').setValue(true)
    await wrapper.find('button[data-test="run-envelope"]').trigger('click')
    await nextTick()
    await nextTick()
    expect(api.fetchEnvelopeAnalytic).toHaveBeenCalled()
    expect(wrapper.text()).toContain('互检')
  })

  it('工件齿轮未生成时「开始包络」按钮禁用', async () => {
    vi.spyOn(api, 'fetchWorkpiece').mockRejectedValue(new Error('生成失败'))
    const wrapper = mountViewer()
    await nextTick()
    await nextTick()

    const btn = wrapper.find('button[data-test="run-envelope"]')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('请先生成工件齿轮模型')
  })

  it('扫掠点云揭示控件在包络后出现 + 事件携带 motion + 默认满显', async () => {
    const wrapper = mountViewer()
    await nextTick()
    await nextTick()

    const details: Array<{ id: string; motion?: unknown }> = []
    const handler = (e: Event): void => {
      const d = (e as CustomEvent).detail as { id: string; motion?: unknown }
      details.push({ id: d.id, motion: d.motion })
    }
    window.addEventListener('gear:layer-ready', handler)

    await wrapper.find('button[data-test="run-envelope"]').trigger('click')
    await nextTick()
    await nextTick()

    window.removeEventListener('gear:layer-ready', handler)

    // 扫掠点云事件携带 motion，刃形不带
    expect(details[0].id).toBe('swept_cloud')
    expect(details[0].motion).toEqual(mockGen.motion)
    expect(details[1].id).toBe('edge')
    expect(details[1].motion).toBeUndefined()

    // 显示控制块 + 面/网切换 + 滑块 + 播放；默认满显（100%）
    expect(wrapper.find('[data-test="swept_cloud-controls"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="mode-surface"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="mode-net"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="reveal-slider"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="reveal-play"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="reveal-label"]').text()).toContain('100%')
  })

  it('面/网切换更新按钮激活态', async () => {
    const wrapper = mountViewer()
    await nextTick()
    await nextTick()
    await wrapper.find('button[data-test="run-envelope"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(wrapper.find('[data-test="mode-surface"]').classes()).toContain('active')
    await wrapper.find('[data-test="mode-net"]').trigger('click')
    await nextTick()
    expect(wrapper.find('[data-test="mode-net"]').classes()).toContain('active')
    expect(wrapper.find('[data-test="mode-surface"]').classes()).not.toContain('active')
  })

  it('刀型/后刀面算法选择器渲染 + α₀ 圆柱刀下不渲染', async () => {
    const wrapper = mountViewer()
    await nextTick()
    await nextTick()

    expect(wrapper.find('[data-test="tool-tool_type"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="tool-flank_method"]').exists()).toBe(true)
    // 圆柱刀（默认）→ α₀ 顶刃后角隐藏（构造性后角 α₀=0）
    expect(wrapper.find('input[data-test="tool-alpha_0"]').exists()).toBe(false)
  })

  it('flankReq 携带 tool_type/flank_method', async () => {
    const wrapper = mountViewer()
    await nextTick()
    await nextTick()

    await wrapper.find('button[data-test="run-envelope"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(api.fetchEnvelopeFlank).toHaveBeenCalledWith(
      expect.objectContaining({ tool_type: 'cylindrical', flank_method: 'helical_lead' }),
    )
  })
})
