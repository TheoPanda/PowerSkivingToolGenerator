/**
 * useGearParams — 单元测试
 * 断言：单一 schema 的完整性 —— 默认值含全部字段（含 rho_tip，防静默失配）、
 *       toPayload 的 camelCase→snake_case 映射与后端请求体对齐。
 */
import { describe, it, expect } from 'vitest'
import { createGearParams, toPayload, gearParamsKey } from './useGearParams'

describe('useGearParams — 单一 schema', () => {
  it('默认值覆盖全部 18 字段（含 rho_tip，修复静默失配）', () => {
    const p = createGearParams()
    const keys = Object.keys(p).sort()
    expect(keys).toEqual(
      [
        'profile_type',
        'k_io',
        'm_n',
        'z_w',
        'β_w',
        'j_w',
        'b_w',
        'toothMethod',
        'x_w',
        'W_k',
        'k_teeth',
        'M',
        'd_p',
        'α_n',
        'h_an',
        'c_n',
        'ρ_f',
        'rho_tip',
        'root_fillet',
      ].sort(),
    )
    expect(p.rho_tip).toBe(0) // ADR-013 锐角齿顶默认
    expect(p.root_fillet).toBe(true) // ADR-014 齿根圆角默认开
    expect(p.toothMethod).toBe('x_w')
  })

  it('toPayload 把 camelCase 映射为 snake_case 并与后端请求体对齐', () => {
    const p = createGearParams()
    const wire = toPayload({ ...p, m_n: 2.5, z_w: 41, b_w: 20, β_w: 15, α_n: 20.5, ρ_f: 0.4 })
    expect(wire).toEqual({
      profile_type: 'involute',
      k_io: 1,
      m_n: 2.5,
      z_w: 41,
      beta_w_deg: 15,
      j_w: 1,
      b_w: 20,
      tooth_method: 'x_w',
      x_w: 0,
      W_k: null,
      k_teeth: null,
      M: null,
      d_p: null,
      alpha_n_deg: 20.5,
      h_an: 1,
      c_n: 0.25,
      rho_f: 0.4,
      rho_tip: 0,
      root_fillet: true,
    })
  })

  it('gearParamsKey 为类型化 InjectionKey（值兼容字符串键）', () => {
    expect(gearParamsKey).toBe('gearParams')
  })
})
