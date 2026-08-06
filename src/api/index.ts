/**
 * 后端 HTTP 请求封装
 * 前后端通信统一使用 HTTP，以便未来迁移至 Web 端
 */

const BASE_URL: string = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:5199'

interface HelloResponse {
  message: string
  status: string
  framework: string
  version: string
  python_version: string
  timestamp: string
}

interface HealthResponse {
  status: string
}

/** 前端 gearParams 数据类型 (与 MainPanel reactive 对齐). */
export interface GearParamsInput {
  profile_type: string
  k_io: number
  m_n: number | null
  z_w: number | null
  β_w: number
  j_w: number
  b_w: number | null
  toothMethod: string
  x_w: number
  W_k: number | null
  k_teeth: number | null
  M: number | null
  d_p: number | null
  α_n: number
  h_an: number
  c_n: number
  ρ_f: number
}

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

/** POST /api/workpiece/generate 响应类型. */
export interface WorkpieceResponse {
  result: WorkpieceResult
  model_glb_base64: string
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

export async function fetchHello(): Promise<HelloResponse> {
  return request<HelloResponse>('/api/hello')
}

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health')
}

/**
 * 提交齿轮参数并获取 GLB 模型.
 * 将前端 camelCase 映射到后端 snake_case.
 */
export async function fetchWorkpiece(params: GearParamsInput): Promise<WorkpieceResponse> {
  const payload: Record<string, unknown> = {
    profile_type: params.profile_type,
    k_io: params.k_io,
    m_n: params.m_n,
    z_w: params.z_w,
    beta_w_deg: params.β_w,
    j_w: params.j_w,
    b_w: params.b_w,
    tooth_method: params.toothMethod,
    x_w: params.x_w,
    W_k: params.W_k,
    k_teeth: params.k_teeth,
    M: params.M,
    d_p: params.d_p,
    alpha_n_deg: params.α_n,
    h_an: params.h_an,
    c_n: params.c_n,
    rho_f: params.ρ_f,
  }

  return request<WorkpieceResponse>('/api/workpiece/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
