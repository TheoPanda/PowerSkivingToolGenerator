/**
 * 后端 HTTP 请求封装
 * 前后端通信统一使用 HTTP，以便未来迁移至 Web 端
 */
import { toPayload, type GearParams, type WorkpieceRequestPayload } from '../composables/useGearParams'
import type { LayerId, EnvelopeInstall } from '../three/layerPalette'

const BASE_URL: string = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:5199'

/** 后端 WorkpieceResult 返回类型. */
export interface WorkpieceResult {
  d_a: number
  d_f: number
  r_b: number
  r_pw: number
  m_t: number
  alpha_t_deg: number
  z_w: number
}

// 齿轮规格 spec 类型统一来自 spec-types.ts（纯类型，渲染/主进程/preload 三方共享，架构审查 C5）
import type { SpecPayload } from './spec-types'
export * from './spec-types'

/** POST /api/workpiece/generate 响应类型. */
export interface WorkpieceResponse {
  result: WorkpieceResult
  model_glb_base64: string
  spec: SpecPayload
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url: string = `${BASE_URL}${endpoint}`
  const response: Response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  })

  if (!response.ok) {
    // FastAPI HTTPException → { detail: { error, code } }；兼容直接 { error, code }
    const body = (await response.json().catch(() => ({}))) as {
      detail?: { error?: string; code?: number }
      error?: string
    }
    const message: string = body.detail?.error ?? body.error ?? `HTTP ${response.status}`
    throw new Error(message)
  }

  return response.json() as Promise<T>
}

/**
 * 提交齿轮参数并获取 GLB 模型.
 * camelCase→snake_case 映射由 useGearParams 模块的 toPayload 统一负责（单一 schema 源）。
 */
export async function fetchWorkpiece(params: GearParams): Promise<WorkpieceResponse> {
  return request<WorkpieceResponse>('/api/workpiece/generate', {
    method: 'POST',
    body: JSON.stringify(toPayload(params)),
  })
}

// ── 子 PRD-2 离散包络 ──────────────────────────────────────────────

/** 刀具参数（组B 子集）— 包络端点共用. */
export interface ToolParams {
  z_t: number
  beta_t_deg: number
  j_t: number
  gamma_0_deg: number
  alpha_0_deg: number
}

/** 离散参数（可缺省，后端默认 n=200/m=181/θ=±40°/n_z=21）. */
export interface DiscretizationParams {
  n?: number
  m?: number
  theta_range_deg?: number
  n_z?: number
}

/** 离散包络请求体（edge / conjugate / rake 等共用）. */
export interface EnvelopeRequest {
  workpiece: WorkpieceRequestPayload
  tool: ToolParams
  discretization?: DiscretizationParams
  include_anim?: boolean
  m_anim?: number
  anim_theta_range_deg?: number
}

/** 能力查询结果：哪些派生几何可用（后端单一权威，替代前端 isHelical 镜像）. */
export interface Capability {
  supports_edge: boolean
  supports_flank: boolean
  supports_single_tooth: boolean
  supports_tool_ring: boolean
  /** 解析路线（消元法仅直齿；斜齿刃形走数值求交 K-2.8b，analytic 端点仍限直齿）. */
  supports_analytic: boolean
}

/** 能力查询响应（POST /api/envelope/capability）. */
export interface CapabilityResponse {
  capability: Capability
}

/** 能力查询：β_w + k_io 派生哪些派生几何可用（刃形/后刀面/单齿），发请求前调用. */
export async function fetchEnvelopeCapability(params: EnvelopeRequest): Promise<CapabilityResponse> {
  return request<CapabilityResponse>('/api/envelope/capability', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/** 覆盖判据报告（K-2.12）. */
export interface CoverageReport {
  total_points: number
  uncovered: { profile_idx: number; radius: number }[]
  coverage_ratio: number
  pass: boolean
}

/** 斜齿刃形双残差（数值求交 K-2.8b 验收：贴前刀面 + 贴产形面，<5μm）. */
export interface EdgeResidualStats {
  max_plane_um: number
  max_surface_um: number
  n_check: number
  pass: boolean
}

/** 刃形响应（POST /api/envelope/edge）. */
export interface EdgeResponse {
  layer: { id: 'edge'; glb_base64: string }
  coord_frame: string
  coverage_report: CoverageReport
  /** 直齿 ffα 闭环 [μm]；斜齿不做 ffα（第二批范围外）→ null */
  ffa_um: number | null
  /** 斜齿双残差（直齿 null）. */
  residual_stats?: EdgeResidualStats | null
  segments_meta: { count: number; continuity: string }[]
  /** 刃形闭合环是否已附齿底构造段（B 方案 v2：延伸/偏置/谷底弧，橙色线）. */
  closed_loop?: boolean
  install: EnvelopeInstall
}

/** 刃形：产形面 ∩ 前刀面（共轭法，K-2.8）→ 覆盖 + ffα → 刃形多段 GLB. */
export async function fetchEnvelopeEdge(params: EnvelopeRequest): Promise<EdgeResponse> {
  return request<EdgeResponse>('/api/envelope/edge', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

// ── 子 PRD-3 前刀面 ──────────────────────────────────────────────

/** 前刀面系数（K-2.1 输出）. */
export interface PlaneCoeff {
  A: number
  B: number
  C: number
  const: number
}

/** 前刀面请求体（rake 端点）. */
export interface RakeRequest {
  workpiece: WorkpieceRequestPayload
  tool: ToolParams
  rake_type: 'plane'
}

/** 前刀面响应（POST /api/envelope/rake）. */
export interface RakeResponse {
  layer: { id: 'rake'; glb_base64: string }
  coord_frame: string
  plane: PlaneCoeff
  p_ref: [number, number, number]
  n_rake: [number, number, number]
}

/** 前刀面：γ₀/β_t/r_pt → 平面前刀面 + 法矢箭头 GLB. */
export async function fetchEnvelopeRake(params: RakeRequest): Promise<RakeResponse> {
  return request<RakeResponse>('/api/envelope/rake', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

// ── 子 PRD-4 后刀面 + 单齿预览 ─────────────────────────────────────

/** 重磨参数（K-2.18 输入）. */
export interface ResharpenParams {
  L: number
  n_L: number
}

/** 刀型：圆柱 / 圆锥（圆锥二期）. */
export type ToolType = 'cylindrical' | 'conical'

/** 后刀面算法：螺旋导程法 / 轴向偏移法（轴向偏移二期）. */
export type FlankMethod = 'helical_lead' | 'axial_offset'

/** B 方案 v7 齿根参数（模块③ K-3.1 预览级）. */
export interface HubParams {
  root_offset_ratio: number
  n_arc: number
  n_ext: number
  n_off: number
}

/** 后刀面/单齿请求体. */
export interface FlankRequest {
  workpiece: WorkpieceRequestPayload
  tool: ToolParams
  resharpening?: ResharpenParams
  discretization?: DiscretizationParams
  hub?: HubParams
  tool_type?: ToolType
  flank_method?: FlankMethod
}

/** 重磨截面（K-2.18 输出）. */
export interface ResharpenStep {
  i: number
  dL: number
  da: number
  a_i: number
}

/** 后刀面响应（POST /api/envelope/flank）. */
export interface FlankResponse {
  layer: { id: 'flank'; glb_base64: string }
  coord_frame: string
  source: string
  flank_method: string
  lead_pitch: number | null
  resharpen_schedule: ResharpenStep[]
}

/** B 方案 v2 闭合实体元数据（极限圆/偏置谷底等，规格窗口/调试用）. */
export interface ToothSolidMeta {
  r_limit_mm: number
  root_radius_mm: number
  root_offset_mm: number
  arch_spread_deg: number
  pitch_z_mm: number
  loop_points: number
  n_sections: number
  volume_mm3: number
  z_t?: number
}

/** 单齿响应（POST /api/envelope/single_tooth）. */
export interface SingleToothResponse {
  layer: { id: 'singleTooth'; glb_base64: string }
  coord_frame: string
  source: string
  meta: ToothSolidMeta
}

/** 整环刀具响应（POST /api/envelope/tool_ring）. */
export interface ToolRingResponse {
  layer: { id: 'toolRing'; glb_base64: string }
  coord_frame: string
  source: string
  /** TO-3 起 meta 新增实际施加的相邻齿轴向错位步距（带符号：p_z×j_t；直齿=0）. */
  meta: ToothSolidMeta & { z_t: number }
}

/** 后刀面：前刀面刃形 + 分截面刃形 → 三角网后刀面 GLB. */
export async function fetchEnvelopeFlank(params: FlankRequest): Promise<FlankResponse> {
  return request<FlankResponse>('/api/envelope/flank', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/** 单齿预览：半齿底闭合实体（B 方案）GLB. */
export async function fetchEnvelopeSingleTooth(params: FlankRequest): Promise<SingleToothResponse> {
  return request<SingleToothResponse>('/api/envelope/single_tooth', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/** 整环刀具：单齿闭合实体阵列 z_t 份 + 齿底填缝带 GLB. */
export async function fetchEnvelopeToolRing(params: FlankRequest): Promise<ToolRingResponse> {
  return request<ToolRingResponse>('/api/envelope/tool_ring', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

// ── 子 PRD-5 解析路线 ──────────────────────────────────────────────

/** 双路线互检结果（第5章 §5.5）. */
export interface CrossCheckResult {
  max_delta_um: number
  pass: boolean
}

/** 解析刃形响应（POST /api/envelope/analytic）. */
export interface AnalyticResponse {
  layer: { id: 'edge'; glb_base64: string }
  coord_frame: string
  source: string
  point_count: number
  cross_check: CrossCheckResult
}

/** 解析刃形：逐点二分 h(φ)=0（产形面 ∩ 前刀面消元）→ 解析刃形 GLB + 双路线互检. */
export async function fetchEnvelopeAnalytic(params: EnvelopeRequest): Promise<AnalyticResponse> {
  return request<AnalyticResponse>('/api/envelope/analytic', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/** 产形面（共轭面）覆盖判据报告（K-2.6）. */
export interface ConjugateCoverageReport {
  total_points: number
  found: number
  uncovered: number
  coverage_ratio: number
  pass: boolean
}

/** 动画单帧数据. */
export interface AnimFrame {
  phi_t_deg: number
  positions: number[]
}

/** 动画数据包（include_anim=true 时返回）. */
export interface AnimData {
  frames: AnimFrame[]
  indices: number[]
  mesh_indices: number[]
  n_vertices: number
  theta_range_deg: number
  /** K-0.5 链同步比 ω_t/ω_w = z_w/z_t（恒正）：存在时前端可按链矩阵实时合成任意 φ（滑条 ±360°）. */
  omega_ratio?: number
  /** 每层廓形点数 n（顶点行主序 iz·n + iu，iz = indices//n_profile 定层号）. */
  n_profile?: number
  /** 各轴向层的 W 系 z 坐标 [mm]（与 n_z 层一一对应；缺省时前端不可切截面）. */
  layer_zs?: number[]
}

/** 产形面响应（POST /api/envelope/conjugate）. */
export interface ConjugateResponse {
  layer: { id: 'conjugate'; glb_base64: string }
  coord_frame: string
  coverage_report: ConjugateCoverageReport
  install: EnvelopeInstall
  anim?: AnimData
}

/** 产形面：数值啮合方程（n·v=0）→ 共轭面三角网 GLB. */
export async function fetchEnvelopeConjugate(params: EnvelopeRequest): Promise<ConjugateResponse> {
  return request<ConjugateResponse>('/api/envelope/conjugate', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/** 产形面 + 动画帧数据. */
export async function fetchConjugateAnim(params: EnvelopeRequest): Promise<ConjugateResponse> {
  return request<ConjugateResponse>('/api/envelope/conjugate', {
    method: 'POST',
    body: JSON.stringify({ ...params, include_anim: true }),
  })
}

/** 内齿轮齿面网格元数据（参与求解的齿面网格，W 系）. */
export interface ToothFlankGrid {
  n: number        // 廓形点数
  n_z: number      // 轴向层数
  arrow_count: number  // 法向箭头数（抽稀后）
}

/** 内齿轮齿面响应（POST /api/envelope/tooth_flank）. */
export interface ToothFlankResponse {
  layer: { id: 'toothFlank'; glb_base64: string }
  coord_frame: string
  coverage_report: ConjugateCoverageReport
  grid: ToothFlankGrid
  install: EnvelopeInstall
}

/** 内齿轮齿面：参与求解的工件齿面网格（离散点 + 法向箭头，参与=洋红紫/被修剪=暗灰）→ GLB（坐标 W）. */
export async function fetchEnvelopeToothFlank(params: EnvelopeRequest): Promise<ToothFlankResponse> {
  return request<ToothFlankResponse>('/api/envelope/tooth_flank', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/** 干涉热力图图例渐变采样点（t ∈ [0,1] 为渐变条位置，−clamp→+clamp）. */
export interface LegendStop {
  t: number
  color: [number, number, number]
}

/** 干涉统计 + 图例权威数据（后端 interference.py 单一来源，前端不复制色阶公式）. */
export interface InterferenceStats {
  n_interference: number
  n_contact_band: number
  n_clearance: number
  n_reference: number
  /** 最深侵入符号距离 [mm]（<0 = 过切深度）. */
  min_d_mm: number
  clamp_mm?: number
  /** 图例：渐变 stops + 关键刻度 [mm] + 齿宽外参考灰. */
  legend?: {
    stops: LegendStop[]
    ticks_mm: number[]
    reference_color: [number, number, number]
  }
}

/** 等效产形齿轮响应（POST /api/envelope/conjugate_gear）. */
export interface ConjugateGearResponse {
  layer: { id: 'conjugateGear'; glb_base64: string }
  coord_frame: string
  coverage_report: ConjugateCoverageReport
  interference_stats?: InterferenceStats
  install: EnvelopeInstall
}

/** 等效产形齿轮：单齿槽产形面阵列 z_t 份 + 齿顶/齿根回转面 → GLB（带符号距离顶点色，前端可切干涉样式）. */
export async function fetchEnvelopeConjugateGear(params: EnvelopeRequest): Promise<ConjugateGearResponse> {
  return request<ConjugateGearResponse>('/api/envelope/conjugate_gear', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}
