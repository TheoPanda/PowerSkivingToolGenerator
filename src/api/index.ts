/**
 * 后端 HTTP 请求封装
 * 前后端通信统一使用 HTTP，以便未来迁移至 Web 端
 */
import { toPayload, type GearParams, type WorkpieceRequestPayload } from '../composables/useGearParams'
import type { LayerId, SweptCloudMotion, EnvelopeInstall } from '../three/layerPalette'

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

/** 刀具参数（组B 子集）— swept_cloud/edge 共用. */
export interface ToolParams {
  z_t: number
  beta_t_deg: number
  j_t: number
  gamma_0_deg: number
  alpha_0_deg: number
}

/** 离散参数（可缺省，后端默认 n=200/m=181/NR=200/θ=±20°）. */
export interface DiscretizationParams {
  n?: number
  m?: number
  NR?: number
  theta_range_deg?: number
}

/** 离散包络请求体（swept_cloud / edge 共用）. */
export interface EnvelopeRequest {
  workpiece: WorkpieceRequestPayload
  tool: ToolParams
  discretization?: DiscretizationParams
}

/** 扫掠点云响应（POST /api/envelope/swept_cloud）. */
export interface SweptCloudResponse {
  layer: { id: 'swept_cloud'; glb_base64: string }
  coord_frame: string
  motion: SweptCloudMotion
  install: EnvelopeInstall
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

/** 扫掠点云：工件齿槽点云经运动包络 → 三角网 GLB. */
export async function fetchEnvelopeSweptCloud(params: EnvelopeRequest): Promise<SweptCloudResponse> {
  return request<SweptCloudResponse>('/api/envelope/swept_cloud', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/** 刃形：点云投影 → 内边界提取 → 覆盖 + ffα → 刃形多段 GLB. */
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

/** 后刀面/单齿请求体. */
export interface FlankRequest {
  workpiece: WorkpieceRequestPayload
  tool: ToolParams
  resharpening?: ResharpenParams
  discretization?: DiscretizationParams
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

/** 解析刃形：逐点求轨迹 ∩ 前刀面 → 解析刃形 GLB + 双路线互检. */
export async function fetchEnvelopeAnalytic(params: EnvelopeRequest): Promise<AnalyticResponse> {
  return request<AnalyticResponse>('/api/envelope/analytic', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}
