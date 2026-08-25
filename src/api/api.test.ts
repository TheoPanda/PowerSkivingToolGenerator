/**
 * fetchWorkpiece API 客户端测试
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchWorkpiece, fetchEnvelopeEdge, fetchEnvelopeRake, fetchEnvelopeConjugateGear, fetchEnvelopeToolRing, fetchEnvelopeToothFlank } from './index'
import { toPayload, type GearParams } from '../composables/useGearParams'

const mockParams: GearParams = {
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

const mockResponse = {
  result: {
    d_a: 107.5,
    d_f: 96.25,
    r_b: 48.164,
    r_pw: 51.25,
    m_t: 2.5,
    alpha_t_deg: 20.0,
    z_w: 41,
  },
  model_glb_base64: 'Z2xURg==',
  spec: {
    params: { inputs: [], outputs: [] },
    single_tooth: { segments: [], center_line: { from_angle_deg: 0, to_angle_deg: 0 }, pitch_line: { r: 0 }, annotations: {
      tooth_thickness: { value: 0 }, circular_pitch: { value: 0 }, tip_fillet: { value: 0 }, root_fillet: { value: 0 }, addendum: { value: 0 }, dedendum: { value: 0 }, whole_depth: { value: 0 },
    } },
    outline: { points: [], teeth: [], circles: { tip_radius: 0, root_radius: 0, pitch_radius: 0 } },
  },
}

describe('fetchWorkpiece', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('sends POST to /api/workpiece/generate with correct body', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    })

    await fetchWorkpiece(mockParams)

    expect(global.fetch).toHaveBeenCalledTimes(1)
    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]

    expect(url).toContain('/api/workpiece/generate')
    expect(options.method).toBe('POST')

    const body: Record<string, unknown> = JSON.parse(options.body as string)
    // 验证字段映射: camelCase → snake_case
    expect(body.m_n).toBe(2.5)
    expect(body.z_w).toBe(41)
    expect(body.beta_w_deg).toBe(0)
    // rho_tip 透传
    expect(body.rho_tip).toBe(0)
  })

  it('returns typed response on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    })

    const result = await fetchWorkpiece(mockParams)
    expect(result.result.d_a).toBe(107.5)
    expect(result.model_glb_base64).toBe('Z2xURg==')
    expect(result.result.z_w).toBe(41)
  })

  it('throws on HTTP error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ error: '模数 m_n 必须大于 0', code: 400 }),
    })

    await expect(fetchWorkpiece(mockParams)).rejects.toThrow('模数 m_n 必须大于 0')
  })

  it('解析 FastAPI 的 detail 错误结构', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: { error: '刃形为空（外齿轮前刀面符号 T14 未销项）', code: 400 } }),
    })

    await expect(fetchWorkpiece(mockParams)).rejects.toThrow('刃形为空（外齿轮前刀面符号 T14 未销项）')
  })
})

describe('fetchEnvelope（子 PRD-2 离散包络）', () => {
  const tool = { z_t: 41, beta_t_deg: 15, j_t: -1, gamma_0_deg: 5, alpha_0_deg: 8 }

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('fetchEnvelopeEdge 返回覆盖报告与 ffα', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        layer: { id: 'edge', glb_base64: '' },
        coord_frame: 'T',
        coverage_report: { total_points: 200, uncovered: [], coverage_ratio: 1.0, pass: true },
        ffa_um: 0.05,
        segments_meta: [],
      }),
    })

    const resp = await fetchEnvelopeEdge({ workpiece: toPayload(mockParams), tool })
    expect(resp.layer.id).toBe('edge')
    expect(resp.coverage_report.pass).toBe(true)
    expect(resp.ffa_um).toBe(0.05)
  })

  it('fetchEnvelopeRake 发送 rake_type 并返回系数 + 法矢', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        layer: { id: 'rake', glb_base64: '' },
        coord_frame: 'T',
        plane: { A: 0.087156, B: 0.257834, C: 0.962250, const: -3.7002 },
        p_ref: [42.455, 0.0, 0.0],
        n_rake: [0.087156, 0.257834, 0.962250],
      }),
    })

    const resp = await fetchEnvelopeRake({ workpiece: toPayload(mockParams), tool, rake_type: 'plane' })

    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toContain('/api/envelope/rake')
    const body: Record<string, unknown> = JSON.parse(options.body as string)
    expect(body.rake_type).toBe('plane')
    expect(resp.layer.id).toBe('rake')
    expect(resp.plane.A).toBe(0.087156)
    expect(resp.n_rake[2]).toBe(0.962250)
  })

  it('fetchEnvelopeConjugateGear 发送到 /api/envelope/conjugate_gear 并返回 conjugateGear 图层', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        layer: { id: 'conjugateGear', glb_base64: '' },
        coord_frame: 'T',
        coverage_report: { total_points: 200, found: 200, uncovered: 0, coverage_ratio: 1.0, pass: true },
        install: { a: 39.55, sigma_deg: 15.0 },
      }),
    })

    const resp = await fetchEnvelopeConjugateGear({ workpiece: toPayload(mockParams), tool })

    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toContain('/api/envelope/conjugate_gear')
    expect(options.method).toBe('POST')
    expect(resp.layer.id).toBe('conjugateGear')
    expect(resp.coverage_report.pass).toBe(true)
  })

  it('fetchEnvelopeToothFlank 发送到 /api/envelope/tooth_flank 并返回 toothFlank 图层（W 系）', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        layer: { id: 'toothFlank', glb_base64: '' },
        coord_frame: 'W',
        coverage_report: { total_points: 200, found: 200, uncovered: 0, coverage_ratio: 1.0, pass: true },
        grid: { n: 200, n_z: 21, arrow_count: 132 },
        install: { a: 39.55, sigma_deg: 15.0 },
      }),
    })

    const resp = await fetchEnvelopeToothFlank({ workpiece: toPayload(mockParams), tool })

    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toContain('/api/envelope/tooth_flank')
    expect(options.method).toBe('POST')
    expect(resp.layer.id).toBe('toothFlank')
    expect(resp.coord_frame).toBe('W')
    expect(resp.grid.arrow_count).toBeGreaterThan(0)
  })

  it('fetchEnvelopeToolRing 发送到 /api/envelope/tool_ring 并返回 toolRing 图层与 B 方案元数据', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        layer: { id: 'toolRing', glb_base64: '' },
        coord_frame: 'T',
        source: '模块③ B 方案 v2（整环阵列，齿距线相位闭合）',
        meta: {
          r_limit_mm: 40.4463,
          root_radius_mm: 36.2017,
          root_offset_mm: 4.2446,
          arch_spread_deg: 5.7,
          pitch_z_mm: 1.59,
          loop_points: 130,
          n_sections: 5,
          volume_mm3: 45.6,
          z_t: 41,
        },
      }),
    })

    const resp = await fetchEnvelopeToolRing({ workpiece: toPayload(mockParams), tool })

    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toContain('/api/envelope/tool_ring')
    expect(options.method).toBe('POST')
    expect(resp.layer.id).toBe('toolRing')
    expect(resp.meta.root_radius_mm).toBeCloseTo(36.2017, 3)
    expect(resp.meta.z_t).toBe(41)
  })
})
