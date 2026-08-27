/**
 * toolSolidValidation — 单元测试（PRD §5.2 区间规则注册表）
 *
 * 断言矩阵：红错（硬非法，禁用生成按钮）vs 黄警（建议性，不阻断）两档分类，
 * 含边界值；tier 字段声明「静态 vs 工件依赖」——工件依赖项必须吃 z_w 派生区间。
 */
import { describe, it, expect } from 'vitest'
import {
  TOOL_FIELD_RULES,
  validateToolField,
  collectHardErrors,
  isToolParamsSubmittable,
  RECOMMENDED_ZT_RATIO,
  TYPICAL_BETA_T_RANGE,
  type ToolWorkpieceContext,
} from './toolSolidValidation'
import { createToolParams } from './useToolParams'

const W: ToolWorkpieceContext = { z_w: 82 } // 算例1：推荐区间 [41, 54.94]

describe('toolSolidValidation — 注册表结构', () => {
  it('字段覆盖必填+可默认两组的可输入项（锁定三项不进注册表）', () => {
    expect(Object.keys(TOOL_FIELD_RULES).sort()).toEqual(
      ['z_t', 'beta_t', 'gamma_0', 'alpha_0', 'L', 'n_L'].sort(),
    )
  })

  it('tier 分档：工件依赖={z_t, β_t}，其余静态（PRD §5.2 两档）', () => {
    expect(TOOL_FIELD_RULES.z_t.tier).toBe('workpiece')
    expect(TOOL_FIELD_RULES.beta_t.tier).toBe('workpiece')
    for (const f of ['gamma_0', 'alpha_0', 'L', 'n_L'] as const) {
      expect(TOOL_FIELD_RULES[f].tier).toBe('static')
    }
  })
})

describe('toolSolidValidation — z_t（工件依赖档）', () => {
  it('正整数且落在 [0.5,0.67]·z_w 内 → 无 issue（边界含端点）', () => {
    expect(validateToolField('z_t', createToolParams(), W)).toBeNull() // 默认 41 = 0.5×82
    const lo = Math.round(RECOMMENDED_ZT_RATIO.lo * 82)
    const hi = RECOMMENDED_ZT_RATIO.hi * 82
    expect(validateToolField('z_t', { ...createToolParams(), z_t: lo }, W)).toBeNull()
    // 上界取整后仍 ≤ 0.67·z_w 的连续上界
    expect(validateToolField('z_t', { ...createToolParams(), z_t: Math.floor(hi) }, W)).toBeNull()
  })

  it('越出推荐区间 → 黄警且文案带当前 z_w 动态数值（Q9-B 即时联动）', () => {
    const issue = validateToolField('z_t', { ...createToolParams(), z_t: 70 }, W)
    expect(issue?.level).toBe('warn')
    if (issue?.level === 'warn') {
      expect(issue.message).toContain('41')
      expect(issue.message).toContain('54.9') // 0.67×82=54.94 → 一位小数显示，不虚构取整
      expect(issue.message).toContain('82')
    }
    // 低侧越界同样黄警
    expect(validateToolField('z_t', { ...createToolParams(), z_t: 30 }, W)?.level).toBe('warn')
  })

  it('区间随工件参数即时刷新：改 z_w 后同一 z_t 的警告数字变化', () => {
    const issue = validateToolField('z_t', { ...createToolParams(), z_t: 41 }, { z_w: 100 })
    expect(issue?.level).toBe('warn')
    if (issue?.level === 'warn') expect(issue.message).toContain('50')
  })

  it('工件未定（z_w=null）→ 不给黄警只做硬校验（区间不可知不等于违规）', () => {
    expect(validateToolField('z_t', { ...createToolParams(), z_t: 999 }, { z_w: null })).toBeNull()
    expect(
      validateToolField('z_t', { ...createToolParams(), z_t: 0 }, { z_w: null })?.level,
    ).toBe('error')
  })

  it('硬非法：非整数 / z_t<1 → 红错（与 pydantic ge=1 对齐）', () => {
    expect(validateToolField('z_t', { ...createToolParams(), z_t: 0 }, W)?.level).toBe('error')
    expect(validateToolField('z_t', { ...createToolParams(), z_t: -3 }, W)?.level).toBe('error')
    expect(validateToolField('z_t', { ...createToolParams(), z_t: 41.5 }, W)?.level).toBe('error')
    expect(validateToolField('z_t', { ...createToolParams(), z_t: Number.NaN }, W)?.level).toBe(
      'error',
    )
  })
})

describe('toolSolidValidation — β_t（工件依赖档）', () => {
  it('[10,20]° 含端点无 issue；端点外 0.5° 内仍典型（浮点边界）', () => {
    expect(validateToolField('beta_t', { ...createToolParams(), beta_t: 10 }, W)).toBeNull()
    expect(validateToolField('beta_t', { ...createToolParams(), beta_t: 20 }, W)).toBeNull()
    expect(TYPICAL_BETA_T_RANGE).toEqual({ lo: 10, hi: 20 })
  })

  it('越典型区间 → 黄警文案注明文献典型值 + W15 非工艺安全边界（PRD §7 纪律）', () => {
    for (const v of [0, 5, 25, 40]) {
      const issue = validateToolField('beta_t', { ...createToolParams(), beta_t: v }, W)
      expect(issue?.level).toBe('warn')
      if (issue?.level === 'warn') {
        expect(issue.message).toContain('W15')
        expect(issue.message).not.toContain('安全边界成立')
      }
    }
  })

  it('负角 / NaN → 红错（pydantic ge=0、U7 数值恒≥0）', () => {
    expect(validateToolField('beta_t', { ...createToolParams(), beta_t: -1 }, W)?.level).toBe(
      'error',
    )
    expect(
      validateToolField('beta_t', { ...createToolParams(), beta_t: Number.NaN }, W)?.level,
    ).toBe('error')
  })
})

describe('toolSolidValidation — 静态档', () => {
  it('γ₀/α₀：有限数值即通过，NaN/Infinity 红错（无区间断言权源）', () => {
    expect(validateToolField('gamma_0', createToolParams(), null)).toBeNull()
    expect(validateToolField('alpha_0', createToolParams(), null)).toBeNull()
    expect(validateToolField('gamma_0', { ...createToolParams(), gamma_0: Number.NaN }, null)?.level).toBe('error')
    expect(validateToolField('alpha_0', { ...createToolParams(), alpha_0: Infinity }, null)?.level).toBe('error')
  })

  it('L：≤0 红错（pydantic gt=0）；正值放行（「按刀体设计」无文献区间）', () => {
    expect(validateToolField('L', { ...createToolParams(), L: 0 }, null)?.level).toBe('error')
    expect(validateToolField('L', { ...createToolParams(), L: -2 }, null)?.level).toBe('error')
    expect(validateToolField('L', { ...createToolParams(), L: 20 }, null)).toBeNull()
  })

  it('n_L：<1 或非整数红错（ge=1）；1~4 给黄警（设计书 §3.2 典型 ≥5）', () => {
    expect(validateToolField('n_L', { ...createToolParams(), n_L: 16 }, null)).toBeNull()
    expect(validateToolField('n_L', { ...createToolParams(), n_L: 0 }, null)?.level).toBe('error')
    expect(validateToolField('n_L', { ...createToolParams(), n_L: 2.5 }, null)?.level).toBe('error')
    const warn = validateToolField('n_L', { ...createToolParams(), n_L: 3 }, null)
    expect(warn?.level).toBe('warn')
    if (warn?.level === 'warn') expect(warn.message).toContain('5')
  })
})

describe('toolSolidValidation — 聚合门禁', () => {
  it('collectHardErrors 返回全部红错字段名（多字段同时违法逐一列出）', () => {
    const params = { ...createToolParams(), z_t: 0, L: -1, n_L: 0.5 }
    expect(collectHardErrors(params, W).sort()).toEqual(['L', 'n_L', 'z_t'].sort())
    expect(collectHardErrors(createToolParams(), W)).toEqual([])
  })

  it('isToolParamsSubmittable：默认参数可提交（开箱生成 AC）；存在任一红错即 false', () => {
    expect(isToolParamsSubmittable(createToolParams(), W)).toBe(true)
    expect(isToolParamsSubmittable({ ...createToolParams(), L: 0 }, W)).toBe(false)
    // 黄警不阻断
    expect(isToolParamsSubmittable({ ...createToolParams(), beta_t: 25 }, W)).toBe(true)
  })
})
