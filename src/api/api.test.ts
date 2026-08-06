/**
 * fetchWorkpiece API 客户端测试
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchWorkpiece, type GearParamsInput } from './index'

const mockParams: GearParamsInput = {
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
  α_n: 20,
  h_an: 1,
  c_n: 0.25,
  ρ_f: 0.38,
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
})
