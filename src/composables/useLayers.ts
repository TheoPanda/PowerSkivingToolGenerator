/**
 * useLayers.ts — 图层显隐/透明度的权威源（模块级单例，同 useInterferenceLegend 模式）
 *
 * 原先散在 LayerPanel 组件局部 reactive 里的 visible/opacity 上提到这里（PRD §5.5 /
 * ADR-020③）：LayerPanel 退化为纯视图（读 state + 派发动作），任何面板都能发图层指令，
 * 例如 MainPanel 进入步骤3 的「仅留 toolRing」预设。
 *
 * 状态流向（单向）：
 *   写入口 = 本模块的动作函数（唯一改 state 的地方）
 *   应用端 = viewport（registerViewport 登记时全量同步一次，之后每次动作下发增量；
 *             viewport 不回写状态，gear:layer-ready 重生成由消费方转成 markLayerReady
 *             动作进入本模块）
 *
 * 下发纪律分两档：
 *   - 手势路径（眼睛/滑条/独显/全显/全隐）：无条件照发 —— 与原 LayerPanel 行为逐字等价，
 *     不做去重（回归红线）。
 *   - 机器路径（hideAllExcept 预设 / markLayerReady）：收敛式下发 —— 与当前状态相同的层
 *     不再发，保证重复触发幂等（连续切入步骤3 第二次起零视口调用）。
 *
 * 除此之外还代管一份纯状态位 stale（TO-5 过期徽标，PRD §5.4）：不下发视口、不改显隐，
 * 只让「面板横幅」与「图层名旁圆点」共用同一真值。
 */
import { reactive } from 'vue'
import { LAYER_IDS, LAYER_VISUALS, type LayerId } from '../three/layerPalette'
import type { GearViewport } from '../three/gearViewport'

/** 图层状态表：visible 初始全显、opacity 取 palette 默认（与原 LayerPanel 局部初值一致）. */
export interface LayersState {
  /** 各层显隐（true=显示）. */
  visible: Record<LayerId, boolean>
  /** 各层透明度 [0..1]. */
  opacity: Record<LayerId, number>
  /**
   * 内容过期标记（TO-5 / PRD §5.4）：工件重生成后该层几何仍基于旧工件参数。
   * 稀疏表——仅被显式标记过的层有条目；toolRing 由 ToolSolidPanel 写入
   * （面板横幅 + LayerPanel 图层名旁过期圆点共用同一真值，无第二份状态）。
   */
  stale: Partial<Record<LayerId, boolean>>
}

function createLayersState(): LayersState {
  return {
    visible: Object.fromEntries(LAYER_IDS.map((id) => [id, true])) as Record<LayerId, boolean>,
    opacity: Object.fromEntries(
      LAYER_IDS.map((id) => [id, LAYER_VISUALS[id].defaultOpacity]),
    ) as Record<LayerId, number>,
    stale: {},
  }
}

/** 单例状态（跨组件共享；无 pinia，仓库无 store 惯例不引入）. */
const state = reactive<LayersState>(createLayersState())

/** 登记的 viewport 引用（晚注册安全：MainView 在 onMounted 才创建实例）. */
let viewport: GearViewport | null = null

/** 写状态 + 无条件下发（手势路径的统一出口；viewport 未登记则只落状态）. */
function pushVisible(id: LayerId, value: boolean): void {
  state.visible[id] = value
  if (viewport) viewport.setLayerVisible(id, value)
}

/** composable 对外接口（state 只读引用 + 动作集）. */
export interface UseLayersApi {
  /** 图层状态（响应式；模板直接读）. */
  state: LayersState
  /** 登记 viewport 并把当前状态同步一次（传 null 解除登记，用于测试/卸载）. */
  registerViewport: (vp: GearViewport | null) => void
  /** 单层显隐. */
  setLayerVisible: (id: LayerId, value: boolean) => void
  /** 单层透明度. */
  setLayerOpacity: (id: LayerId, value: number) => void
  /** 聚焦单层（相机过渡 + 其余层淡出，视口侧能力透传）. */
  focusLayer: (id: LayerId) => void
  /** Alt+点击眼睛：独显该层；已是独显态则恢复全部可见（不动透明度）. */
  soloLayer: (id: LayerId) => void
  /** 该层是否处于独显态（该层可见且其余全隐）. */
  isSolo: (id: LayerId) => boolean
  /** 「全部显示」的图层部分：全部可见 + 透明度回默认（视图样式复位仍由面板负责）. */
  showAll: () => void
  /** 全隐：仅批量关闭显隐（透明度保留，恢复显示时不丢用户调整）. */
  hideAll: () => void
  /** 图层重生成重置默认可见（gear:layer-ready 的既有行为走这里）. */
  markLayerReady: (id: LayerId) => void
  /** 预设指令：仅留 keep 可见（收敛式幂等；viewport 未登记整条跳过）. */
  hideAllExcept: (keep: LayerId) => void
  /** 过期标记写入（PRD §5.4：工件重生成 → toolRing 基于旧工件参数；重生成该层即清除）. */
  setLayerStale: (id: LayerId, stale: boolean) => void
}

/** composable 入口：返回同一个单例状态与动作集（每组件调用不产生局部拷贝）. */
export function useLayers(): UseLayersApi {
  return {
    state,
    registerViewport,
    setLayerVisible,
    setLayerOpacity,
    focusLayer,
    soloLayer,
    isSolo,
    showAll,
    hideAll,
    markLayerReady,
    hideAllExcept,
    setLayerStale,
  }
}

/** 登记 viewport 并把当前状态应用一次（晚注册兜底）.
 * 显隐全量发（半截状态不可见错乱）；透明度只补发偏离 palette 默认的层——
 * 新建材质本就是默认值，全量覆写会强转 transparent=true 扰动渲染排序. */
function registerViewport(vp: GearViewport | null): void {
  viewport = vp
  if (!vp) return
  for (const id of LAYER_IDS) {
    vp.setLayerVisible(id, state.visible[id])
    if (state.opacity[id] !== LAYER_VISUALS[id].defaultOpacity) {
      vp.setLayerOpacity(id, state.opacity[id])
    }
  }
}

/** 单层显隐. */
function setLayerVisible(id: LayerId, value: boolean): void {
  pushVisible(id, value)
}

/** 单层透明度. */
function setLayerOpacity(id: LayerId, value: number): void {
  state.opacity[id] = value
  if (viewport) viewport.setLayerOpacity(id, value)
}

/** 聚焦单层（纯视口能力，不改权威状态）. */
function focusLayer(id: LayerId): void {
  if (!viewport) return
  viewport.focusLayer(id)
}

/** 该层是否独显态（该层可见且其余全隐）. */
function isSolo(id: LayerId): boolean {
  return state.visible[id] && LAYER_IDS.every((x) => x === id || !state.visible[x])
}

/** 独显该层（Alt+点击眼睛）；已是独显态则恢复全部可见（不动透明度）. */
function soloLayer(id: LayerId): void {
  const restore = isSolo(id)
  for (const x of LAYER_IDS) {
    pushVisible(x, restore ? true : x === id)
  }
}

/** 「全部显示」的图层部分（视图样式/干涉复位仍由 LayerPanel 负责）. */
function showAll(): void {
  for (const id of LAYER_IDS) {
    pushVisible(id, true)
    setLayerOpacity(id, LAYER_VISUALS[id].defaultOpacity)
  }
}

/** 全隐：仅批量关闭显隐（透明度保留）. */
function hideAll(): void {
  for (const id of LAYER_IDS) {
    pushVisible(id, false)
  }
}

/** 图层重生成（重新点「开始包络」→ gear:layer-ready）：重置该层为默认可见 + 默认透明度.
 * 由隐转显才对视口补一条 true（原本就可见时视口侧 addLayer 已重建为可见组，不打扰）。 */
function markLayerReady(id: LayerId): void {
  const wasHidden = !state.visible[id]
  state.visible[id] = true
  state.opacity[id] = LAYER_VISUALS[id].defaultOpacity
  if (wasHidden && viewport) viewport.setLayerVisible(id, true)
}

/** 步骤3 图层预设（PRD §5.5 / ADR-020③）：仅留 keep 可见，其余收拢.
 * 收敛式下发：与当前状态一致的层不发 → 连续触发幂等（第二次起零调用）；
 * 视口未登记时整条跳过（连状态也不动，避免晚注册时落进半截预设）.
 * 不锁死、离开不复原：用户可随时手动开任一层，那是下一次手势路径的事。 */
function hideAllExcept(keep: LayerId): void {
  if (!viewport) return
  for (const id of LAYER_IDS) {
    const value = id === keep
    if (state.visible[id] === value) continue
    pushVisible(id, value)
  }
}

/** 内容过期标记写入：纯状态位，不碰视口也不碰显隐（不强隐旧图是 PRD §5.4 的明确裁决）.
 * toolRing 重生成成功时调用方以 setLayerStale(id, false) 清除。 */
function setLayerStale(id: LayerId, stale: boolean): void {
  if (stale) {
    state.stale[id] = true
    return
  }
  delete state.stale[id]
}

/** 恢复初值（仅供单元测试隔离用；生产代码不得调用）. */
export function resetLayersState(): void {
  Object.assign(state, createLayersState())
}
