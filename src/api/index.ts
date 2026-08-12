/**
 * 后端 HTTP 请求封装
 * 前后端通信统一使用 HTTP，以便未来迁移至 Web 端
 */
import { toPayload, type GearParams } from '../composables/useGearParams'

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
