/**
 * useToolStale.ts — 步骤3 过期徽标的会话级真值（模块级单例；评审 A1 修复配套）
 *
 * 为什么不是面板局部 ref：ToolSolidPanel 走 v-if 挂载（MainPanel 步骤切换即卸载），
 * 若 gear:model-ready 监听挂在组件生命周期里，「步骤3 生成 → 回步骤2 重生成工件 → 再进步骤3」
 * 这条路径上事件落在监听真空期，横幅/圆点静默失效——PRD §5.4「工件 generate() 成功即为
 * 过期信号」的契约被架空。真值上提后：
 *   - window 监听模块级懒安装一次、装上不拆 —— 事件永不漏接（跨挂载/跨卸载）；
 *   - workpieceStale / hasGeneratedOnce 跨挂载存续，重进面板时态势如实呈现；
 *   - 图层列表圆点经 useLayers.setLayerStale(TOOL_RING_ID) 共用同一真值（无第二份状态）。
 *
 * 横幅语义维持 #36 定案：hasGeneratedOnce=false（本面板从未生成过整环）时不弹横幅，
 * 引导交给按钮「有待应用的变更」高亮——不存在可被过期的刀具，就不喊「刀具基于旧工件参数」。
 */
import { computed, reactive } from 'vue'
import { TOOL_RING_ID } from '../three/layerPalette'
import { useLayers } from './useLayers'

/** 会话级过期态势. */
interface ToolStaleState {
  /** 工件重生成后为 true；本面板整环重建成功即回 false. */
  workpieceStale: boolean
  /** 本面板是否至少成功生成过一次整环（横幅前置门槛，见文件头说明）. */
  hasGeneratedOnce: boolean
}

const state = reactive<ToolStaleState>({ workpieceStale: false, hasGeneratedOnce: false })

let listenerInstalled = false

/** 懒安装 window 监听：首次 useToolStale() 时装上，之后常驻（卸载面板不拆）. */
function ensureModelReadyListener(): void {
  if (listenerInstalled) return
  listenerInstalled = true
  window.addEventListener('gear:model-ready', (): void => {
    state.workpieceStale = true
    useLayers().setLayerStale(TOOL_RING_ID, true)
  })
}

/** 整环重建成功：清过期位 + 记「生成过」（generate() 成功路径专用入口）. */
function markToolRingGenerated(): void {
  state.workpieceStale = false
  state.hasGeneratedOnce = true
  useLayers().setLayerStale(TOOL_RING_ID, false)
}

/** 横幅可见性（PRD §5.4 + 「无可指对象不喊过期」引导裁决）. */
const bannerVisible = computed<boolean>(() => state.workpieceStale && state.hasGeneratedOnce)

/** composable 对外接口（单例状态只读引用 + 动作集）. */
export interface UseToolStaleApi {
  state: typeof state
  /** 面板横幅是否显示（响应式）. */
  bannerVisible: typeof bannerVisible
  /** 整环重建成功的统一收口（清过期 + 记快照门槛）. */
  markToolRingGenerated: () => void
}

export function useToolStale(): UseToolStaleApi {
  ensureModelReadyListener()
  return { state, bannerVisible, markToolRingGenerated }
}

/** 测试隔离复位（生产代码不得调用）；图层圆点一并清除. */
export function resetToolStaleState(): void {
  state.workpieceStale = false
  state.hasGeneratedOnce = false
  useLayers().setLayerStale(TOOL_RING_ID, false)
}
