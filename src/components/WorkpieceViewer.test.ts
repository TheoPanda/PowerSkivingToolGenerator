/**
 * WorkpieceViewer — 集成测试
 * 断言：生成成功后结果/spec 写入全局单例（ResultPanel 消费）；
 *       步骤2 内不再渲染结果区与「查看齿轮规格」按钮（已移入独立面板）。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import WorkpieceViewer from './WorkpieceViewer.vue'
import * as api from '../api'
import { workpieceState, revealResultPanel } from '../composables/useWorkpieceState'
import type { GearParams } from '../composables/useGearParams'
import { mockSpec } from './__spec-mock'

function defaultParams(): GearParams {
  return {
    profile_type: 'involute',
    k_io: -1,
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
  const toothMeta = {
    r_limit_mm: 40.4463,
    root_radius_mm: 36.2017,
    root_offset_mm: 4.2446,
    arch_spread_deg: 5.7,
    pitch_z_mm: 1.59,
    loop_points: 130,
    n_sections: 5,
    volume_mm3: 45.6,
  }
  const mockTooth: api.SingleToothResponse = {
    layer: { id: 'singleTooth', glb_base64: 'Z2xURg==' },
    coord_frame: 'T',
    source: '模块③ B 方案 v2（开放轮廓 + 径向偏置 + 圆弧闭合实体）',
    meta: toothMeta,
  }
  const mockToolRing: api.ToolRingResponse = {
    layer: { id: 'toolRing', glb_base64: 'Z2xURg==' },
    body_layer: { id: 'toolBody', glb_base64: 'Zm9v' },
    body_description: {
      loop: { cut_radius: 40.45, bore_radius: 15.8715, keyway: null },
      rake_plane: { A: 0.0872, B: 0, C: 0.9962, const: -3.7 },
      profile: { type: 'cylinder' as const, od_mm: 80.89, length_mm: 15 },
      boolean_def: { union: ['tooth_ring'], cut: ['bore_cylinder'] },
      grade: 'preview',
      segment_dia: 75,
      thickness_is_standard: true,
      warnings: [],
    },
    coord_frame: 'T',
    source: '模块③ B 方案 v2（整环阵列，齿距线相位闭合）',
    meta: { ...toothMeta, z_t: 41 },
  }
  const mockAnalytic: api.AnalyticResponse = {
    layer: { id: 'edge', glb_base64: 'Z2xURg==' },
    coord_frame: 'T',
    source: '解析（K-2.8）',
    point_count: 100,
    cross_check: { max_delta_um: 0.5, pass: true },
  }
  const mockConjugate: api.ConjugateResponse = {
    layer: { id: 'conjugate', glb_base64: 'Z2xURg==' },
    coord_frame: 'T',
    coverage_report: { total_points: 200, found: 200, uncovered: 0, coverage_ratio: 1.0, pass: true },
    install: { a: 39.55, sigma_deg: 15.0 },
  }
  const mockConjugateGear: api.ConjugateGearResponse = {
    layer: { id: 'conjugateGear', glb_base64: 'Z2xURg==' },
    coord_frame: 'T',
    coverage_report: { total_points: 200, found: 200, uncovered: 0, coverage_ratio: 1.0, pass: true },
    install: { a: 39.55, sigma_deg: 15.0 },
  }
  const mockToothFlank: api.ToothFlankResponse = {
    layer: { id: 'toothFlank', glb_base64: 'Z2xURg==' },
    coord_frame: 'W',
    coverage_report: { total_points: 200, found: 200, uncovered: 0, coverage_ratio: 1.0, pass: true },
    grid: { n: 200, n_z: 21, arrow_count: 132 },
    install: { a: 39.55, sigma_deg: 15.0 },
  }

  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'fetchWorkpiece').mockResolvedValue(mockResponse)
    vi.spyOn(api, 'fetchEnvelopeCapability').mockResolvedValue({
      capability: { supports_edge: true, supports_flank: true, supports_single_tooth: true, supports_tool_ring: true, supports_analytic: true },
    })
    vi.spyOn(api, 'fetchEnvelopeEdge').mockResolvedValue(mockEdge)
    vi.spyOn(api, 'fetchEnvelopeRake').mockResolvedValue(mockRake)
    vi.spyOn(api, 'fetchEnvelopeFlank').mockResolvedValue(mockFlank)
    vi.spyOn(api, 'fetchEnvelopeSingleTooth').mockResolvedValue(mockTooth)
    vi.spyOn(api, 'fetchEnvelopeToolRing').mockResolvedValue(mockToolRing)
    vi.spyOn(api, 'fetchEnvelopeAnalytic').mockResolvedValue(mockAnalytic)
    vi.spyOn(api, 'fetchEnvelopeConjugate').mockResolvedValue(mockConjugate)
    vi.spyOn(api, 'fetchEnvelopeConjugateGear').mockResolvedValue(mockConjugateGear)
    vi.spyOn(api, 'fetchEnvelopeToothFlank').mockResolvedValue(mockToothFlank)
    workpieceState.result = null
    workpieceState.spec = null
    workpieceState.open = false
    workpieceState.revealed = false
    workpieceState.collapsed = false
    workpieceState.pos = { x: 24, y: 64 }
  })

  it('点「开始包络」→ 依次派发刃形、产形面、等效产形齿轮、内齿轮齿面、前刀面、后刀面、单齿、整环八图层 + 诊断条显示', async () => {
    const wrapper = mountViewer()
    await nextTick()
    await nextTick()

    const layers: string[] = []
    const handler = (e: Event): void => {
      layers.push((e as CustomEvent).detail.id as string)
    }
    window.addEventListener('gear:layer-ready', handler)

    await wrapper.find('button[data-test="run-envelope"]').trigger('click')
    await flushPromises()
    await nextTick()

    window.removeEventListener('gear:layer-ready', handler)
    expect(layers).toEqual(['edge', 'conjugate', 'conjugateGear', 'toothFlank', 'rake', 'flank', 'singleTooth', 'toolRing'])
    expect(wrapper.find('[data-test="diagnostic-strip"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('ffα')
    expect(wrapper.text()).toContain('覆盖')
  })

  it('ffα 超限时诊断条标失败态', async () => {
    vi.spyOn(api, 'fetchEnvelopeEdge').mockResolvedValue({
      ...mockEdge,
      ffa_um: 1.5,
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
    await flushPromises()
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
    // 链条含 toothFlank 诊断层等多个 await：flushPromises 排空微任务（nextTick 已不够）
    await flushPromises()
    await nextTick()

    expect(api.fetchEnvelopeFlank).toHaveBeenCalledWith(
      expect.objectContaining({ tool_type: 'cylindrical', flank_method: 'helical_lead' }),
    )
  })

  it('斜齿工件（β_w≠0）：全族图层（刃形 K-2.8b + 第二批实体建模）；仅解析路线跳过', async () => {
    // 斜齿 → 全族解锁（2026-08-25 第二批：后刀面/单齿/整环 B 方案 v2 同构管线）；
    // 解析（消元法仅直齿）仍跳过
    vi.spyOn(api, 'fetchEnvelopeCapability').mockResolvedValue({
      capability: { supports_edge: true, supports_flank: true, supports_single_tooth: true, supports_tool_ring: true, supports_analytic: false },
    })
    vi.spyOn(api, 'fetchEnvelopeEdge').mockResolvedValue({
      ...mockEdge,
      ffa_um: null,  // 斜齿不做 ffα 闭环（诊断条显示 —）
      residual_stats: { max_plane_um: 0.5, max_surface_um: 1.2, n_check: 28, pass: true },
    })
    const gearParams = reactive<GearParams>({ ...defaultParams(), β_w: 19 })
    const wrapper = mount(WorkpieceViewer, {
      global: {
        provide: { gearParams },
        stubs: { ElMessage: true },
      },
    })
    await nextTick()
    await nextTick()

    await wrapper.find('button[data-test="run-envelope"]').trigger('click')
    await flushPromises()
    await nextTick()

    // 刃形（数值求交）+ 产形面族/前刀面/内齿轮齿面诊断层 + 第二批实体三件
    expect(api.fetchEnvelopeEdge).toHaveBeenCalled()
    expect(api.fetchEnvelopeConjugate).toHaveBeenCalled()
    expect(api.fetchEnvelopeConjugateGear).toHaveBeenCalled()
    expect(api.fetchEnvelopeRake).toHaveBeenCalled()
    expect(api.fetchEnvelopeToothFlank).toHaveBeenCalled()
    expect(api.fetchEnvelopeFlank).toHaveBeenCalled()
    expect(api.fetchEnvelopeSingleTooth).toHaveBeenCalled()
    expect(api.fetchEnvelopeToolRing).toHaveBeenCalled()
    // 解析（消元法仅直齿）跳过
    expect(api.fetchEnvelopeAnalytic).not.toHaveBeenCalled()
    // 诊断条：ffa null 时仍显示（—），通过条件只看覆盖
    expect(wrapper.find('[data-test="diagnostic-strip"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('—')
  })
})
