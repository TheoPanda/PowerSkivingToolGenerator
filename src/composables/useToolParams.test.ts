/**
 * useToolParams — 单元测试
 * 断言：单一 schema 的完整性 —— 默认值覆盖全部字段且与后端 pydantic Field 同值
 *       （backend/core/envelope/router.py 为默认值唯一权威）；
 *       toToolPayload 的 wire 映射与改造前 WorkpieceViewer.runEnvelope 手工组装的
 *       请求体逐字段等价（golden 内联快照，TO-2 等价验收）。
 */
import { describe, it, expect } from 'vitest'
import {
  createToolParams,
  useToolParams,
  toToolPayload,
  LOCKED_TOOL_TYPE,
  LOCKED_TOOL_TYPE_NOTE,
  LOCKED_RAKE_TYPE,
  LOCKED_RAKE_TYPE_NOTE,
  LOCKED_FLANK_METHOD,
  LOCKED_FLANK_METHOD_NOTE,
  rakeTypeToWire,
  type ToolParamsState,
} from './useToolParams'

/**
 * 改造前请求体形状的 golden 快照（2026-08-27 重构前，逐字段手工抄录自
 * WorkpieceViewer.vue 旧版 runEnvelope：L176-182 / L237-241 / L247-253）：
 * - EnvelopeRequest.tool（capability / edge / conjugate / conjugateGear /
 *   tooth_flank / analytic 共用）
 * - RakeRequest.rake_type
 * - FlankRequest.resharpening / tool_type / flank_method
 */
const GOLDEN_WIRE = {
  tool: {
    z_t: 41,
    beta_t_deg: 15,
    j_t: -1,
    gamma_0_deg: 5,
    alpha_0_deg: 8,
  },
  rake_type: 'plane',
  resharpening: { L: 20, n_L: 16 },
  tool_body: { mounting: 'bore', d_bore: null, keyway_b: null, keyway_t1: null, B_body: null },
  tool_type: 'cylindrical',
  flank_method: 'helical_lead',
} as const

describe('useToolParams — 单一 schema', () => {
  it('默认值覆盖全部字段（15 字段含 K-3.2 刀体五项；δ/z_off 按 T15/schema 缺口刻意不建字段）', () => {
    const p: ToolParamsState = createToolParams()
    expect(Object.keys(p).sort()).toEqual(
      ['z_t', 'beta_t', 'j_t', 'gamma_0', 'alpha_0', 'rake_type', 'tool_type', 'flank_method', 'L', 'n_L',
       'body_mounting', 'body_d_bore', 'body_keyway_b', 'body_keyway_t1', 'body_B'].sort(),
    )
    // 数值档：锚算例1（z_t=41 ⇔ 工件 z_w=82 / β_t=15 / γ₀=5）；α₀=8 基线出处=算例2，
    // 算例1 文献值 6° 系 W2 假设输入、正文确认待做 —— 默认维持 pydantic 同值的 8。
    expect(p.z_t).toBe(41)
    expect(p.beta_t).toBe(15)
    expect(p.j_t).toBe(-1)
    expect(p.gamma_0).toBe(5)
    expect(p.alpha_0).toBe(8)
    // 重磨档：ResharpenParams L=20.0 / n_L=16 同值
    expect(p.L).toBe(20)
    expect(p.n_L).toBe(16)
    // 锁定项取值 = 对应锁定常量（单一来源）
    expect(p.tool_type).toBe(LOCKED_TOOL_TYPE)
    expect(p.rake_type).toBe(LOCKED_RAKE_TYPE)
    expect(p.flank_method).toBe(LOCKED_FLANK_METHOD)
    // 刀体档（ADR-021）：默认 bore + 全 null = 对档表自动带出
    expect(p.body_mounting).toBe('bore')
    expect(p.body_d_bore).toBeNull()
    expect(p.body_keyway_b).toBeNull()
    expect(p.body_keyway_t1).toBeNull()
    expect(p.body_B).toBeNull()
  })

  it('toToolPayload 输出与改造前请求体逐字段等价（golden 全量快照；tool_body=ADR-021 新增段）', () => {
    expect(toToolPayload(createToolParams())).toEqual({
      tool: GOLDEN_WIRE.tool,
      rake_type: GOLDEN_WIRE.rake_type,
      resharpening: GOLDEN_WIRE.resharpening,
      tool_body: GOLDEN_WIRE.tool_body,
      tool_type: GOLDEN_WIRE.tool_type,
      flank_method: GOLDEN_WIRE.flank_method,
    })
  })

  it('toToolPayload 字段改名映射（beta_t→beta_t_deg 等），改值可观测穿透', () => {
    const wire = toToolPayload({
      ...createToolParams(),
      z_t: 33,
      beta_t: 18,
      j_t: 1,
      gamma_0: 7,
      alpha_0: 10,
      L: 30,
      n_L: 20,
    })
    expect(wire.tool).toEqual({ z_t: 33, beta_t_deg: 18, j_t: 1, gamma_0_deg: 7, alpha_0_deg: 10 })
    expect(wire.resharpening).toEqual({ L: 30, n_L: 20 })
    expect(wire.rake_type).toBe('plane')
    expect(wire.tool_type).toBe('cylindrical')
    expect(wire.flank_method).toBe('helical_lead')
  })

  it('wire 键序与既有报文一致（JSON.stringify 序列化序不变）', () => {
    const w = toToolPayload(createToolParams())
    expect(Object.keys(w)).toEqual(['tool', 'rake_type', 'resharpening', 'tool_body', 'tool_type', 'flank_method'])
    expect(Object.keys(w.tool)).toEqual(['z_t', 'beta_t_deg', 'j_t', 'gamma_0_deg', 'alpha_0_deg'])
    expect(Object.keys(w.resharpening)).toEqual(['L', 'n_L'])
    expect(Object.keys(w.tool_body)).toEqual(['mounting', 'd_bore', 'keyway_b', 'keyway_t1', 'B_body'])
  })

  it('按组件同构展开组装三端点请求体，键集与取值均等价（workpiece 段归 useGearParams）', () => {
    const p = { ...createToolParams(), beta_t: 12 } // 非默认值也须原样穿透
    const w = toToolPayload(p)

    // EnvelopeRequest（capability/edge/conjugate/conjugateGear/tooth_flank/analytic）
    const req = { workpiece: {} as Record<string, unknown>, tool: w.tool }
    expect(req.tool).toEqual({ ...GOLDEN_WIRE.tool, beta_t_deg: 12 })

    // RakeRequest
    const rakeReq = { workpiece: req.workpiece, tool: req.tool, rake_type: w.rake_type }
    expect(rakeReq).toEqual({
      workpiece: {},
      tool: { ...GOLDEN_WIRE.tool, beta_t_deg: 12 },
      rake_type: GOLDEN_WIRE.rake_type,
    })

    // FlankRequest（flank / single_tooth / tool_ring 共用）
    const flankReq = {
      workpiece: req.workpiece,
      tool: req.tool,
      resharpening: w.resharpening,
      tool_type: w.tool_type,
      flank_method: w.flank_method,
    }
    expect(flankReq).toEqual({
      workpiece: {},
      tool: { ...GOLDEN_WIRE.tool, beta_t_deg: 12 },
      resharpening: GOLDEN_WIRE.resharpening,
      tool_type: GOLDEN_WIRE.tool_type,
      flank_method: GOLDEN_WIRE.flank_method,
    })
  })
})

describe('useToolParams — 锁定项元数据（#36 复用）', () => {
  it('三常量取值正确且理由文案带缺口编号、「待销项后开放」措辞', () => {
    expect(LOCKED_TOOL_TYPE).toBe('cylindrical')
    expect(LOCKED_RAKE_TYPE).toBe('plane')
    expect(LOCKED_FLANK_METHOD).toBe('helical_lead')

    for (const note of [LOCKED_TOOL_TYPE_NOTE, LOCKED_RAKE_TYPE_NOTE, LOCKED_FLANK_METHOD_NOTE]) {
      expect(note).toContain('待销项后开放') // PRD §7 纪律：未销项不得当已验证陈述
    }
    expect(LOCKED_TOOL_TYPE_NOTE).toContain('T7')
    expect(LOCKED_TOOL_TYPE_NOTE).toContain('T15')
    expect(LOCKED_RAKE_TYPE_NOTE).toContain('W5')
    expect(LOCKED_FLANK_METHOD_NOTE).toContain('T15')
  })

  it('useToolParams() 每次返回独立实例（步骤2/3 各持己态，互不串扰）', () => {
    const a = useToolParams()
    const b = useToolParams()
    a.z_t = 99
    expect(b.z_t).toBe(41)
    expect(a.z_t).toBe(99)
  })
})

describe('rakeTypeToWire — RakeRequest.rake_type 收窄映射（评审 S4）', () => {
  it("唯一开放分支 'plane' 原样透传", () => {
    expect(rakeTypeToWire('plane')).toBe('plane')
  })

  it('W5 锁定期内未开放分支运行时抛错（调用方禁用 as 断言后的守卫）', () => {
    for (const v of ['cone', 'equation'] as const) {
      expect(() => rakeTypeToWire(v)).toThrow(/W5/)
    }
  })
})
