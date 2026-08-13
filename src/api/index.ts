/**
 * 后端 HTTP 请求封装
 * 前后端通信统一使用 HTTP，以便未来迁移至 Web 端
 */
import { toPayload, type GearParams, type WorkpieceRequestPayload } from '../composables/useGearParams'
import type { LayerId } from '../three/layerPalette'

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
    const error: { error?: string; code?: number } = await response.json()
    throw new Error(error.error || `HTTP ${response.status}`)
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

/** 获取包络占位演示图层（产形面/刃形/后刀面）的 GLB. */
export async function fetchEnvelopeDemo(): Promise<EnvelopeDemoResponse> {
  return request<EnvelopeDemoResponse>('/api/envelope/demo', { method: 'POST' })
}

// ── 子 PRD-2 离散包络 ──────────────────────────────────────────────

/** 刀具参数（组B 子集）— generatrix/edge 共用. */
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

/** 离散包络请求体（generatrix / edge 共用）. */
export interface EnvelopeRequest {
  workpiece: WorkpieceRequestPayload
  tool: ToolParams
  discretization?: DiscretizationParams
}

/** 产形面响应（POST /api/envelope/generatrix）. */
export interface GeneratrixResponse {
  layer: { id: 'generatrix'; glb_base64: string }
  coord_frame: string
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
}

/** 产形面：工件齿槽点云经运动包络 → 三角网 GLB. */
export async function fetchEnvelopeGeneratrix(params: EnvelopeRequest): Promise<GeneratrixResponse> {
  return request<GeneratrixResponse>('/api/envelope/generatrix', {
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
