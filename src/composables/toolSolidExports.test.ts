/**
 * toolSolidExports — 单元测试（导出量前端复刻，PRD §5.3）
 *
 * golden 全部取自后端实现/后端测试：
 *   - 算例1：backend/core/envelope/tests/test_process_plan.py TestExample1
 *     （Σ=15°、r_pw=82、r_pt≈42.4463 精确值、a=r_pw−r_pt≈39.5537）
 *   - L_tp：与 WorkpieceViewer.test.ts mockFlank.lead_pitch=995.33 同源一致，
 *     及 backend/core/envelope/tooth_solid.py 的 helical_lead_mm 公式
 *   （p_z 断言已于 2026-08-27 勘误回退时删除——整环无错位，见 PRD §3.1-5 勘误注记）
 *   - 斜齿工件：test_process_plan.py TestHelicalWorkpiece（β_w=19/z_w=38/z_t=21/m_n=1.25/β_t=2）
 */
import { describe, it, expect } from 'vitest'
import {
  k14SigmaDeg,
  k16ToolPitchRadiusMm,
  k15CenterDistanceMm,
  k215HelicalLeadMm,
  computeToolExportQuantities,
  SIN_BETA_EPS,
  type ExportWorkpieceContext,
} from './toolSolidExports'
import { createToolParams } from './useToolParams'

/** 工件上下文 = MainPanel inject(gearParamsKey) 的只读投影（字段名对齐 GearParams）. */
const EX1_WORKPIECE: ExportWorkpieceContext = {
  z_w: 82,
  m_n: 2.0,
  beta_w_deg: 0,
  j_w: 1,
  k_io: -1,
}

describe('toolSolidExports — K-1.x 单公式', () => {
  it('K-1.4 Σ = j_w·β_w − j_t·β_t（算例1 = +15°；U12 界面 °）', () => {
    // j_w=+1（右旋工件）/j_t=−1（左旋刀具）→ 内齿轮旋向相反相加
    expect(k14SigmaDeg(0, 15, 1, -1)).toBeCloseTo(15.0, 9)
    expect(k14SigmaDeg(0, 15, 1, 1)).toBeCloseTo(-15.0, 9)
    expect(k14SigmaDeg(19, 2, 1, -1)).toBeCloseTo(21.0, 9) // 后端同例（TestHelicalWorkpiece）
  })

  it('K-1.6 r_pt = r_pw·z_t·cosβ_w/(z_w·cosβ_t)：算例1 = 41/cos15° ≈ 42.4463 mm', () => {
    expect(k16ToolPitchRadiusMm(82, 41, 2.0, 0, 15)).toBeCloseTo(42.446323396813405, 9)
    // m_n 变化按比例传导（分度圆定义）
    expect(k16ToolPitchRadiusMm(102, 68, 0.399635, 0, 15)).toBeCloseTo(
      (0.399635 * 102 / 2) * 68 * Math.cos(0) / (102 * Math.cos(15 * Math.PI / 180)),
      12,
    )
  })

  it('K-1.5 a = r_pw + k_io·r_pt：内齿轮 k_io=−1 分支为减法（以 process_plan.py 实际代码为准）', () => {
    const aInternal = k15CenterDistanceMm(82, 42.446323396813405, -1)
    expect(aInternal).toBeCloseTo(39.553676603186595, 9)
    // 外齿轮 k_io=+1 → 相加（同一行代码的另一半分支）
    expect(k15CenterDistanceMm(30, 20, 1)).toBeCloseTo(50, 12)
    // 斜齿内齿组合：a = r_pw − r_pt（TestHelicalWorkpiece 同构断言）
    const betaW = 19 * Math.PI / 180
    const betaT = 2 * Math.PI / 180
    const rpw = (1.25 / Math.cos(betaW)) * 38 / 2
    const rpt = rpw * 21 * Math.cos(betaW) / (38 * Math.cos(betaT))
    expect(k15CenterDistanceMm(rpw, rpt, -1)).toBeCloseTo(rpw - rpt, 12)
  })

  it('K-2.15 L_tp = z_t·π·m_n/sinβ_t（算例1 = 995.3309 mm）', () => {
    expect(k215HelicalLeadMm(2.0, 41, 15)).toBeCloseTo(995.3309173686231, 6)
    // 直齿退化：sinβ→0 发散返回 Infinity（tooth_solid.helical_lead_mm）
    expect(k215HelicalLeadMm(2.0, 41, 0)).toBe(Number.POSITIVE_INFINITY)
    expect(SIN_BETA_EPS).toBe(1e-12) // 与 tooth_solid._SIN_BETA_EPS 同值
  })
})

describe('toolSolidExports — 聚合导出量（reactive 即时刷新的数据源）', () => {
  it('算例1 默认参数（z_t=41/m_n=2）全量命中后端 golden', () => {
    const q = computeToolExportQuantities(createToolParams(), EX1_WORKPIECE)
    expect(q.sigma_deg).toBeCloseTo(15.0, 9)
    expect(q.r_pt_mm).toBeCloseTo(42.446323396813405, 9)
    expect(q.a_mm).toBeCloseTo(39.553676603186595, 9)
    expect(q.lead_mm).toBeCloseTo(995.3309173686231, 6)
  })

  it('斜齿工件（Tsai 2023 同例）：Σ=21°、内齿轮 a 为减法分支', () => {
    const q = computeToolExportQuantities(
      { ...createToolParams(), z_t: 21, beta_t: 2 },
      { z_w: 38, m_n: 1.25, beta_w_deg: 19, j_w: 1, k_io: -1 },
    )
    expect(q.sigma_deg).toBeCloseTo(21.0, 9)
    const rpw = (1.25 / Math.cos(19 * Math.PI / 180)) * 38 / 2
    const rpt = rpw * 21 * Math.cos(19 * Math.PI / 180) / (38 * Math.cos(2 * Math.PI / 180))
    expect(q.r_pt_mm).toBeCloseTo(rpt, 12)
    expect(q.a_mm).toBeCloseTo(rpw - rpt, 12)
  })

  it('直齿刀具 β_t=0：lead_mm=null（与后端 router 序列化 inf→null 同型）', () => {
    const q = computeToolExportQuantities(
      { ...createToolParams(), beta_t: 0 },
      EX1_WORKPIECE,
    )
    expect(q.lead_mm).toBeNull()
    expect(q.sigma_deg).toBeNull() // β_t=0 且 β_w=0 → Σ=0 后端拒绝（刮齿需轴交角），前端不展示数值
  })

  it('工件侧缺参（z_w/m_n 为 null 或非法）→ 节圆/中心距置 null，不抛异常', () => {
    for (const w of [
      { ...EX1_WORKPIECE, z_w: null },
      { ...EX1_WORKPIECE, m_n: null },
      { ...EX1_WORKPIECE, z_w: 0 },
      { ...EX1_WORKPIECE, m_n: -1 },
      { ...EX1_WORKPIECE, z_w: Number.NaN },
    ] as ExportWorkpieceContext[]) {
      const q = computeToolExportQuantities(createToolParams(), w)
      expect(q.r_pt_mm).toBeNull()
      expect(q.a_mm).toBeNull()
      expect(q.sigma_deg).not.toBeNull() // Σ 与 z_w/m_n 无关仍可显示
    }
  })

  it('硬非法输入防御（z_t<1 / β_t<0 / m_n≤0）：一律降级为 null/0 而非 NaN 泄漏到界面', () => {
    const q1 = computeToolExportQuantities({ ...createToolParams(), z_t: 0 }, EX1_WORKPIECE)
    expect(q1.r_pt_mm).toBeNull()
    expect(q1.lead_mm).toBeNull()

    const q2 = computeToolExportQuantities({ ...createToolParams(), beta_t: -5 }, EX1_WORKPIECE)
    expect(q2.r_pt_mm).toBeNull()
    expect(q2.lead_mm).toBeNull()

    const q3 = computeToolExportQuantities(
      createToolParams(),
      { ...EX1_WORKPIECE, m_n: Number.NaN },
    )
    expect(q3.r_pt_mm).toBeNull()
    expect(q3.a_mm).toBeNull()
  })
})
