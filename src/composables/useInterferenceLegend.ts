/**
 * 干涉热力图图例状态（模块级单例，同 useSimulation 模式）.
 *
 * 等效产形齿轮「干涉」样式的颜色-接触对应关系提示：
 * - stats 由 WorkpieceViewer 从 conjugate_gear 响应写入（后端权威图例数据）
 * - visible 由 LayerPanel「干涉」按钮驱动（样式切换联动）
 * - InterferenceLegend 组件消费（v-if=visible && stats）
 */
import { reactive } from 'vue'
import type { InterferenceStats } from '../api'

export const interferenceState = reactive<{
  /** 图例是否显示（干涉热力图样式激活时）. */
  visible: boolean
  /** 后端图例数据 + 统计（每次包络计算刷新）. */
  stats: InterferenceStats | null
}>({
  visible: false,
  stats: null,
})

/** 写入图例数据（WorkpieceViewer 收到 conjugate_gear 响应时）. */
export function setInterferenceStats(stats: InterferenceStats | undefined): void {
  interferenceState.stats = stats ?? null
}

/** 图例显隐（LayerPanel 干涉样式切换联动）. */
export function setInterferenceVisible(visible: boolean): void {
  interferenceState.visible = visible
}
