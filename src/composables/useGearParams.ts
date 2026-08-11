/**
 * useGearParams.ts — 工件齿轮参数（GearParams）单一模块
 *
 * 齿轮参数此前在 MainPanel reactive / GearParamsPanel interface / api 类型三处各定义一次，
 * 且 rho_tip 静默失配（MainPanel/GearParamsPanel 缺字段 → 运行时 undefined → 后端吃默认 0）。
 * 此处收拢为唯一 schema：类型 + 默认值 + 到后端 wire 格式的映射。
 * 表单、provide、消费、API 客户端都从此模块派生 —— 一个 interface，一个默认值表。
 *
 * gearParamsKey 以字符串值 'gearParams' 作为 InjectionKey（类型化），
 * 与既有的字符串键 provide/inject 兼容，同时让 TS 校验两侧形状。
 */
import type { InjectionKey } from 'vue'

/** 齿轮参数（18 字段，含 rho_tip；toothMethod 收窄为字面量联合）. */
export interface GearParams {
  profile_type: string
  k_io: number
  m_n: number | null
  z_w: number | null
  β_w: number
  j_w: number
  b_w: number | null
  toothMethod: 'x_w' | 'W_k' | 'M'
  x_w: number
  W_k: number | null
  k_teeth: number | null
  M: number | null
  d_p: number | null
  α_n: number
  h_an: number
  c_n: number
  ρ_f: number
  rho_tip: number
  root_fillet: boolean
}

/** 提供给后端的 wire 载荷（snake_case，与 POST /api/workpiece/generate 请求体对齐）. */
export interface WorkpieceRequestPayload {
  profile_type: string
  k_io: number
  m_n: number | null
  z_w: number | null
  beta_w_deg: number
  j_w: number
  b_w: number | null
  tooth_method: string
  x_w: number
  W_k: number | null
  k_teeth: number | null
  M: number | null
  d_p: number | null
  alpha_n_deg: number
  h_an: number
  c_n: number
  rho_f: number
  rho_tip: number
  root_fillet: boolean
}

/** 默认参数（含 rho_tip = 0 锐角齿顶，与 ADR-013 一致；m_n/z_w/b_w 待用户填写为 null）. */
export function createGearParams(): GearParams {
  return {
    profile_type: 'involute',
    k_io: 1,
    m_n: null,
    z_w: null,
    β_w: 0,
    j_w: 1,
    b_w: null,
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
    rho_tip: 0,
    root_fillet: true,
  }
}

/** provide/inject 用类型化键（值为字符串，兼容既有字符串键用法）. */
export const gearParamsKey: InjectionKey<GearParams> = 'gearParams' as unknown as InjectionKey<GearParams>

/** camelCase 领域参数 → snake_case 后端载荷. */
export function toPayload(p: GearParams): WorkpieceRequestPayload {
  return {
    profile_type: p.profile_type,
    k_io: p.k_io,
    m_n: p.m_n,
    z_w: p.z_w,
    beta_w_deg: p.β_w,
    j_w: p.j_w,
    b_w: p.b_w,
    tooth_method: p.toothMethod,
    x_w: p.x_w,
    W_k: p.W_k,
    k_teeth: p.k_teeth,
    M: p.M,
    d_p: p.d_p,
    alpha_n_deg: p.α_n,
    h_an: p.h_an,
    c_n: p.c_n,
    rho_f: p.ρ_f,
    rho_tip: p.rho_tip,
    root_fillet: p.root_fillet,
  }
}
