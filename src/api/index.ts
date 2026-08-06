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
