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
  const mockGen: api.GeneratrixResponse = {
    layer: { id: 'generatrix', glb_base64: 'Z2xURg==' },
    coord_frame: 'T',
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
  }

  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'fetchWorkpiece').mockResolvedValue(mockResponse)
    vi.spyOn(api, 'fetchEnvelopeGeneratrix').mockResolvedValue(mockGen)
    vi.spyOn(api, 'fetchEnvelopeEdge').mockResolvedValue(mockEdge)
    workpieceState.result = null
    workpieceState.spec = null
    workpieceState.open = false
    workpieceState.revealed = false
    workpieceState.collapsed = false
    workpieceState.pos = { x: 24, y: 64 }
  })

  it('点「开始包络」→ 依次派发产形面、刃形两图层 + 诊断条显示', async () => {
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
    expect(layers).toEqual(['generatrix', 'edge'])
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
})
