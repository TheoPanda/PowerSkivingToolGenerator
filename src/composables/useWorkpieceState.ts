/**
 * useWorkpieceState.ts — 工件生成结果 + 结果面板状态的全局单例
 *
 * WorkpieceViewer 生成后写入（setWorkpieceResult），ResultPanel 消费，
 * 跨组件共享同一份 result / spec，避免 prop 层层传递。
 * 面板位置持久化到 localStorage，重启后保持。
 */
import { reactive } from 'vue'
import type { SpecPayload, WorkpieceResult } from '../api'

/** localStorage 键：结果面板位置. */
const POS_KEY = 'pst.result-panel.pos'
/** 默认位置：窗口左上（内容区：标题栏 40px 下 + 24px 边距，与 MainPanel 左缘对齐）. */
const DEFAULT_POS = { x: 24, y: 64 }

function loadPos(): { x: number; y: number } {
  try {
    const raw = localStorage.getItem(POS_KEY)
    if (raw) {
      const p = JSON.parse(raw) as { x: number; y: number }
      if (typeof p?.x === 'number' && typeof p?.y === 'number') return p
    }
  } catch {
    /* 忽略损坏数据 */
  }
  return { ...DEFAULT_POS }
}

export interface WorkpieceState {
  /** 最近一次生成的齿轮结果（null = 尚未生成）. */
  result: WorkpieceResult | null
  /** 与结果同源的 spec（供查看齿轮规格窗口使用）. */
  spec: SpecPayload | null
  /** 结果面板是否打开. */
  open: boolean
  /** 当前结果的面板是否已随模型显示而唤出过（关闭后据此显示唤起胶囊）. */
  revealed: boolean
  /** 面板是否收起为标题栏. */
  collapsed: boolean
  /** 面板左上角位置（px，窗口内容区坐标）. */
  pos: { x: number; y: number }
}

/** 全局结果单例. */
export const workpieceState: WorkpieceState = reactive<WorkpieceState>({
  result: null,
  spec: null,
  open: false,
  revealed: false,
  collapsed: false,
  pos: loadPos(),
})

/**
 * 写入一次新的生成结果。
 * 面板不立即打开——待 3D 模型生成并显示完成后由 revealResultPanel() 唤出（Q：点击「下一步」后弹出）。
 */
export function setWorkpieceResult(result: WorkpieceResult, spec: SpecPayload): void {
  workpieceState.result = result
  workpieceState.spec = spec
  workpieceState.open = false
  workpieceState.revealed = false
  workpieceState.collapsed = false
}

/** 齿轮模型显示完成后调用：唤起结果面板（若已有结果）. */
export function revealResultPanel(): void {
  if (!workpieceState.result) return
  workpieceState.open = true
  workpieceState.revealed = true
  workpieceState.collapsed = false
}

/** 更新面板位置并持久化到 localStorage. */
export function movePanel(pos: { x: number; y: number }): void {
  workpieceState.pos = { ...pos }
  try {
    localStorage.setItem(POS_KEY, JSON.stringify(workpieceState.pos))
  } catch {
    /* ignore */
  }
}
