/**
 * toolSolidExports.ts — 步骤3 导出量的前端轻量复刻（TO-5 / PRD §5.3、§4 导出折叠组）
 *
 * 纯函数模块（无响应式状态），公式**逐条抄写自后端实现函数**，禁止凭记忆写
 * （评审 S2：锚函数名不锚行号——后端重构挪行不失准；改公式必须同步本模块）：
 *   K-1.4  Σ = j_w·β_w − j_t·β_t
 *          ← process_plan.compute_process_plan（rad 内算，返回前转 °）
 *   m_t / r_pw：m_t = m_n/cosβ_w，r_pw = m_t·z_w/2 ← 同函数的 r_pw/m_t 段
 *   K-1.6  r_pt = r_pw·z_t·cosβ_w/(z_w·cosβ_t)   ← 同函数
 *   K-1.5  a = r_pw + k_io·r_pt                  ← 同函数
 *          —— k_io 分支以实际代码为准：内齿轮 k_io=−1 → a = r_pw − r_pt（相减）
 *   K-2.15 L_tp = z_t·π·m_n/sinβ_t；sinβ→0 发散返回 Infinity
 *          ← tooth_solid.helical_lead_mm
 *   （p_z=L_tp/z_t 不再展示：2026-08-27 勘误——整环为同相位周向阵列、无错位，
 *     单独展示「错位步距」会误导用户以为齿真的沿 Z 错开该距离，#34 事故根源）
 *
 * 单位纪律 U12：界面显示 °/mm —— 本模块入参出参一律 度/mm，不出现 rad 泄漏。
 * 失效退化对齐后端：Σ≈0 后端 raise「Σ=0」（process_plan.compute_process_plan）→ 前端置 null 不展示；
 * 导程发散后端序列化为 null（router flank 端点 lead_pitch 注释）→ 前端 lead_mm=null。
 */
import type { ToolParamsState } from './useToolParams'

/** sinβ 低于此值视为直齿（与 tooth_solid._SIN_BETA_EPS 同值）. */
export const SIN_BETA_EPS = 1e-12

/** Σ 视为零的容差（对齐 process_plan.compute_process_plan 的 abs(sigma) < 1e-12 判定，rad）. */
const SIGMA_ZERO_EPS = 1e-12

/** 工件侧只读上下文 = inject(gearParamsKey) 的投影（ADR-020① 零数值继承不受影响：
 * 只读工件参数派生导出量，从不回写、也不预填刀具表单）。字段名与 GearParams 一致。 */
export interface ExportWorkpieceContext {
  /** 工件齿数. */
  z_w: number | null
  /** 法向模数 [mm]. */
  m_n: number | null
  /** 工件螺旋角 [°]（U7 数值恒≥0）. */
  beta_w_deg: number
  /** 工件旋向 +1/−1（β_w=0 时占位 +1）. */
  j_w: number
  /** 内/外齿系数（−1 内齿 / +1 外齿）. */
  k_io: number
}

/** 导出量快照（null = 该项当前不可算，界面显示 —）. */
export interface ToolExportQuantities {
  /** 轴交角 Σ [°]（有符号 U8；Σ≈0 → null，与后端拒绝一致）. */
  sigma_deg: number | null
  /** 刀具节圆半径 r_pt [mm]. */
  r_pt_mm: number | null
  /** 安装中心距 a [mm]（U9，内齿轮 = r_pw − r_pt）. */
  a_mm: number | null
  /** 螺旋导程 L_tp [mm]；β_t=0 发散 → null. */
  lead_mm: number | null
}

/**
 * K-1.4 轴交角 Σ = j_w·β_w − j_t·β_t [°]（有符号，U8；
 * process_plan.compute_process_plan 同式，度↔弧度换算仅在本函数内部往返，不出模块）.
 */
export function k14SigmaDeg(
  beta_w_deg: number,
  beta_t_deg: number,
  j_w: number,
  j_t: number,
): number {
  const rad = j_w * (beta_w_deg * Math.PI) / 180 - j_t * (beta_t_deg * Math.PI) / 180
  return (rad * 180) / Math.PI
}

/** K-1.6 刀具节圆半径 r_pt = r_pw·z_t·cosβ_w/(z_w·cosβ_t) [mm]（r_pw 已知时）.
 * 出处：process_plan.compute_process_plan / 设计书 §3.4 [11] 式(5).
 * 模块内私有——外部一律走 k16ToolPitchRadiusMm（从 m_n 直达），避免暴露半截入口。 */
function toolPitchRadiusFromRpwMm(
  r_pw_mm: number,
  z_w: number,
  z_t: number,
  beta_w_deg: number,
  beta_t_deg: number,
): number {
  const cosW = Math.cos(beta_w_deg * Math.PI / 180)
  const cosT = Math.cos(beta_t_deg * Math.PI / 180)
  return (r_pw_mm * z_t * cosW) / (z_w * cosT)
}

/** K-1.6 变体：从 m_n/z_w/z_t 直达 r_pt（先按 r_pw/m_t 段算 r_pw 再代入上式）[mm].
 * process_plan.compute_process_plan. */
export function k16ToolPitchRadiusMm(
  z_w: number,
  z_t: number,
  m_n: number,
  beta_w_deg: number,
  beta_t_deg: number,
): number {
  const cosW = Math.cos(beta_w_deg * Math.PI / 180)
  // m_t = m_n/cosβ_w；r_pw = m_t·z_w/2（compute_process_plan 的 r_pw/m_t 段）
  const r_pw = (m_n / cosW) * z_w / 2
  return toolPitchRadiusFromRpwMm(r_pw, z_w, z_t, beta_w_deg, beta_t_deg)
}

/** K-1.5 安装中心距 a = r_pw + k_io·r_pt [mm]（k_io=−1 内齿轮 → 相减，以 compute_process_plan 实码为准）. */
export function k15CenterDistanceMm(r_pw_mm: number, r_pt_mm: number, k_io: number): number {
  return r_pw_mm + k_io * r_pt_mm
}

/** K-2.15 螺旋导程 L_tp = z_t·π·m_n/sinβ_t [mm]；|sinβ| ≤ ε 发散返回 Infinity（tooth_solid.helical_lead_mm）. */
export function k215HelicalLeadMm(m_n: number, z_t: number, beta_t_deg: number): number {
  const sinB = Math.sin(beta_t_deg * Math.PI / 180)
  if (Math.abs(sinB) <= SIN_BETA_EPS) return Number.POSITIVE_INFINITY
  return (z_t * m_n * Math.PI) / sinB
}

/** 数值合法性兜底：非法值（NaN/∞/非正）一律 false，避免 NaN 泄漏到只读区. */
function usable(v: number | null, minExclusive: number): boolean {
  return v !== null && Number.isFinite(v) && v > minExclusive
}

/**
 * 聚合计算（ToolSolidPanel 的 reactive computed 数据源）：
 * 工件依赖项（r_pt/a/lead/p_z）在工件缺参或刀具硬非法时降级为 null/0，绝不抛异常；
 * Σ 仅依赖 β/j 四个有符号量（U8/U7），工件缺参仍可显示。
 */
export function computeToolExportQuantities(
  tool: ToolParamsState,
  workpiece: ExportWorkpieceContext | null,
): ToolExportQuantities {
  const result: ToolExportQuantities = {
    sigma_deg: null,
    r_pt_mm: null,
    a_mm: null,
    lead_mm: null,
  }
  const betaT = tool.beta_t

  // ── Σ（K-1.4）：始终可算，但 Σ≈0 与后端同判为失效（刮齿需轴交角提供切削速度分量）──
  const sigma = k14SigmaDeg(workpiece?.beta_w_deg ?? 0, betaT, workpiece?.j_w ?? 1, tool.j_t)
  if (Math.abs(sigma * Math.PI / 180) >= SIGMA_ZERO_EPS && Number.isFinite(sigma)) {
    result.sigma_deg = sigma
  }

  // 工件侧前置门禁：z_w/m_n 合法且 β_t ≥ 0（负角违反 U7，属硬非法输入期防抖）
  const okWorkpiece =
    workpiece !== null &&
    usable(workpiece.z_w, 0) &&
    usable(workpiece.m_n, 0) &&
    betaT >= 0
  const okTool = tool.z_t >= 1
  if (!okWorkpiece || !okTool) return result

  const zW = workpiece!.z_w as number
  const mN = workpiece!.m_n as number
  const cosW = Math.cos(workpiece!.beta_w_deg * Math.PI / 180)
  if (cosW === 0) return result // β_w=90° 退化保护（m_t 发散）

  // K-1.5/K-1.6：r_pt 与 a 成对给出（a 用实际代码分支 r_pw + k_io·r_pt）
  const r_pw = (mN / cosW) * zW / 2            // K-1.6 前置：r_pw/m_t 段
  const r_pt = toolPitchRadiusFromRpwMm(r_pw, zW, tool.z_t, workpiece!.beta_w_deg, betaT) // K-1.6
  const a = k15CenterDistanceMm(r_pw, r_pt, workpiece!.k_io)                              // K-1.5
  if (!Number.isFinite(r_pt)) return result
  result.r_pt_mm = r_pt
  result.a_mm = Number.isFinite(a) ? a : null

  // K-2.15 链：螺旋导程
  const lead = k215HelicalLeadMm(mN, tool.z_t, betaT)
  result.lead_mm = Number.isFinite(lead) ? lead : null
  return result
}
