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

/** 包络占位演示图层（子 PRD-1 多图层能力验证）. */
export interface EnvelopeDemoLayer {
  id: LayerId
  glb_base64: string
}

export interface EnvelopeDemoResponse {
  layers: EnvelopeDemoLayer[]
}

/** 获取包络占位演示图层（扫掠点云/刃形/后刀面）的 GLB. */
export async function fetchEnvelopeDemo(): Promise<EnvelopeDemoResponse> {
  return request<EnvelopeDemoResponse>('/api/envelope/demo', { method: 'POST' })
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

/** 离散参数（可缺省，后端默认 n=200/m=181/NR=200/θ=±40°/n_z=21）. */
export interface DiscretizationParams {
  n?: number
  m?: number
  NR?: number
  theta_range_deg?: number
  n_z?: number
}

/** 离散包络请求体（edge / conjugate / rake 等共用）. */
export interface EnvelopeRequest {
  workpiece: WorkpieceRequestPayload
  tool: ToolParams
  discretization?: DiscretizationParams
}

/** 覆盖判据报告（K-2.12）. */
export interface CoverageReport {
  total_points: number
  uncovered: { profile_idx: number; radius: number }[]
  coverage_ratio: number
  pass: boolean
}

/** 刃形响应（POST /api/envelope/edge）. */
export interface EdgeResponse {
  layer: { id: 'edge'; glb_base64: string }
  coord_frame: string
  coverage_report: CoverageReport
  ffa_um: number
  segments_meta: { count: number; continuity: string }[]
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

/** 后刀面/单齿请求体. */
export interface FlankRequest {
  workpiece: WorkpieceRequestPayload
  tool: ToolParams
  resharpening?: ResharpenParams
  discretization?: DiscretizationParams
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
  lead_pitch: number
  resharpen_schedule: ResharpenStep[]
}

/** 单齿响应（POST /api/envelope/single_tooth）. */
export interface SingleToothResponse {
  layer: { id: 'singleTooth'; glb_base64: string }
  coord_frame: string
  source: string
}

/** 后刀面：前刀面刃形 + 分截面刃形 → 三角网后刀面 GLB. */
export async function fetchEnvelopeFlank(params: FlankRequest): Promise<FlankResponse> {
  return request<FlankResponse>('/api/envelope/flank', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/** 单齿预览：前刀面 + 后刀面 + 刃形三件套非实体 GLB. */
export async function fetchEnvelopeSingleTooth(params: FlankRequest): Promise<SingleToothResponse> {
  return request<SingleToothResponse>('/api/envelope/single_tooth', {
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

/** 产形面响应（POST /api/envelope/conjugate）. */
export interface ConjugateResponse {
  layer: { id: 'conjugate'; glb_base64: string }
  coord_frame: string
  coverage_report: ConjugateCoverageReport
  install: EnvelopeInstall
}

/** 产形面：数值啮合方程（n·v=0）→ 共轭面三角网 GLB. */
export async function fetchEnvelopeConjugate(params: EnvelopeRequest): Promise<ConjugateResponse> {
  return request<ConjugateResponse>('/api/envelope/conjugate', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/** 等效产形齿轮响应（POST /api/envelope/conjugate_gear）. */
export interface ConjugateGearResponse {
  layer: { id: 'conjugateGear'; glb_base64: string }
  coord_frame: string
  coverage_report: ConjugateCoverageReport
  install: EnvelopeInstall
}

/** 等效产形齿轮：单齿槽产形面阵列 z_t 份 + 齿顶/齿根回转面 → GLB. */
export async function fetchEnvelopeConjugateGear(params: EnvelopeRequest): Promise<ConjugateGearResponse> {
  return request<ConjugateGearResponse>('/api/envelope/conjugate_gear', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/** 干涉热力图响应（POST /api/envelope/interference）. */
export interface InterferenceResponse {
  layer: { id: 'interference'; glb_base64: string }
  coord_frame: string
  coverage_report: ConjugateCoverageReport
  install: EnvelopeInstall
  clamp_mm: number
}

/** 干涉热力图：产形面符号距离着色（红=干涉/白=相切/蓝=间隙）→ GLB. */
export async function fetchEnvelopeInterference(params: EnvelopeRequest): Promise<InterferenceResponse> {
  return request<InterferenceResponse>('/api/envelope/interference', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}
