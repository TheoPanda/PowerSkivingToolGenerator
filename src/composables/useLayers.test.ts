/**
 * useLayers — 单元测试
 *
 * 断言：登记 viewport 全量应用（晚注册兜底）/ markLayerReady 重置默认可见 /
 *       hideAllExcept 预设的一次性语义与收敛式幂等 / 视口未登记安全跳过。
 * 算法脱离组件 DOM：viewport 用记录调用的 mock，直接对模块接口测试。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useLayers, resetLayersState } from './useLayers'
import { LAYER_IDS, LAYER_VISUALS, type LayerId } from '../three/layerPalette'
import type { GearViewport } from '../three/gearViewport'

/** 步骤3 图层预设的唯一保留层（与 MainPanel 的 watch 同值）. */
const TOOL_RING: LayerId = 'toolRing'

/** 可记录调用序列的 viewport mock（只关心显隐/透明度两个通道）. */
interface RecordingViewport {
  vp: GearViewport
  visibleCalls: Array<{ id: LayerId; value: boolean }>
  opacityCalls: Array<{ id: LayerId; value: number }>
}

function recordingViewport(): RecordingViewport {
  const rec: RecordingViewport = {
    vp: null as unknown as GearViewport,
    visibleCalls: [],
    opacityCalls: [],
  }
  rec.vp = {
    setLayerVisible: (id: LayerId, value: boolean): void => { rec.visibleCalls.push({ id, value }) },
    setLayerOpacity: (id: LayerId, value: number): void => { rec.opacityCalls.push({ id, value }) },
  } as unknown as GearViewport
  return rec
}

/** 某图层收到的显隐指令序列. */
function visibilityOf(rec: RecordingViewport, id: LayerId): boolean[] {
  return rec.visibleCalls.filter((c) => c.id === id).map((c) => c.value)
}

/** 登记完成即清空调用记录（登记本身会全量下发一次，别混进后续动作的断言）. */
function resetCalls(rec: RecordingViewport): void {
  rec.visibleCalls.length = 0
  rec.opacityCalls.length = 0
}

describe('useLayers', () => {
  beforeEach(() => {
    resetLayersState()
  })

  it('registerViewport 登记时把当前状态全量应用一次（晚注册兜底）', () => {
    const layers = useLayers()
    // 视口尚未登记也先落状态（MainPanel 指令可能早于面板挂载）
    layers.setLayerVisible('rake', false)
    const rec = recordingViewport()
    layers.registerViewport(rec.vp)
    // 10 层各恰好一条显隐指令：rake=false，其余=true
    expect(rec.visibleCalls).toHaveLength(LAYER_IDS.length)
    for (const id of LAYER_IDS) {
      expect(visibilityOf(rec, id)).toEqual([id === 'rake' ? false : true])
    }
  })

  it('registerViewport 只补发偏离 palette 默认值的透明度（不打扰新建材质）', () => {
    const layers = useLayers()
    layers.setLayerOpacity('conjugate', 0.25)
    layers.setLayerOpacity('workpiece', 0.4)
    const rec = recordingViewport()
    layers.registerViewport(rec.vp)
    const touchedIds = rec.opacityCalls.map((c) => c.id).sort()
    expect(touchedIds).toEqual(['conjugate', 'workpiece'])
    expect(rec.opacityCalls.find((c) => c.id === 'conjugate')?.value).toBe(0.25)
  })

  it('markLayerReady 重置该层为默认可见 + 默认透明度（由隐转显才下发）', () => {
    const layers = useLayers()
    const rec = recordingViewport()
    layers.registerViewport(rec.vp)
    layers.setLayerVisible('edge', false)
    layers.setLayerOpacity('edge', 0.3)
    resetCalls(rec)

    layers.markLayerReady('edge')

    expect(layers.state.visible.edge).toBe(true)
    expect(layers.state.opacity.edge).toBe(LAYER_VISUALS.edge.defaultOpacity)
    expect(visibilityOf(rec, 'edge')).toEqual([true]) // 视口侧若未重建，这里兜底拨回可见
    expect(rec.opacityCalls).toHaveLength(0) // 透明度不主动下发（addLayer 重建材质即默认）
  })

  it('markLayerReady 本就可见的层重生成时不打扰视口（与原行为逐字等价）', () => {
    const layers = useLayers()
    const rec = recordingViewport()
    layers.registerViewport(rec.vp)
    resetCalls(rec)

    layers.markLayerReady('sweptCloud')

    expect(layers.state.visible.sweptCloud).toBe(true)
    expect(rec.visibleCalls).toHaveLength(0)
  })

  it('hideAllExcept 仅留指定层可见（workpiece 一并收拢），已收敛层不重复下发', () => {
    const layers = useLayers()
    const rec = recordingViewport()
    layers.registerViewport(rec.vp)
    resetCalls(rec)

    layers.hideAllExcept(TOOL_RING)

    expect(layers.state.visible[TOOL_RING]).toBe(true)
    for (const id of LAYER_IDS) {
      if (id === TOOL_RING) continue
      expect(layers.state.visible[id]).toBe(false)
      expect(visibilityOf(rec, id)).toEqual([false])
    }
    // toolRing 初始就可见 → 状态已收敛，不发冗余指令
    expect(visibilityOf(rec, TOOL_RING)).toEqual([])
  })

  it('预设是一次性指令不是常驻守卫：手动重开的层不被自动关闭', () => {
    const layers = useLayers()
    const rec = recordingViewport()
    layers.registerViewport(rec.vp)
    resetCalls(rec)
    layers.hideAllExcept(TOOL_RING)

    layers.setLayerVisible('workpiece', true)
    layers.markLayerReady('conjugateGear') // 与预设无关的动作也不得牵连关闭

    expect(layers.state.visible.workpiece).toBe(true)
    expect(visibilityOf(rec, 'workpiece').at(-1)).toBe(true)
    expect(layers.state.visible.conjugateGear).toBe(true)
  })

  it('切走再切回步骤3 → 再次预设会重新收拢手动重开的层（每次进入都执行）', () => {
    const layers = useLayers()
    const rec = recordingViewport()
    layers.registerViewport(rec.vp)
    resetCalls(rec)
    layers.hideAllExcept(TOOL_RING)
    layers.setLayerVisible('flank', true) // 用户在步骤3 里手动开了一层

    layers.hideAllExcept(TOOL_RING) // 模拟离开后再次切入

    expect(layers.state.visible.flank).toBe(false)
    // 手动重开下发 true，再切入预设收回 false（每次进入都执行）
    expect(visibilityOf(rec, 'flank')).toEqual([false, true, false])
  })

  it('连续多次 hideAllExcept 幂等：收敛后零视口调用、状态不变', () => {
    const layers = useLayers()
    const rec = recordingViewport()
    layers.registerViewport(rec.vp)
    layers.hideAllExcept(TOOL_RING)
    const callsAfterFirst = rec.visibleCalls.length
    const stateSnapshot = JSON.stringify(layers.state.visible)

    layers.hideAllExcept(TOOL_RING)
    layers.hideAllExcept(TOOL_RING)

    expect(rec.visibleCalls).toHaveLength(callsAfterFirst)
    expect(JSON.stringify(layers.state.visible)).toBe(stateSnapshot)
  })

  it('showAll 全部可见并回默认透明度（既有「全部显示」语义不回归）', () => {
    const layers = useLayers()
    const rec = recordingViewport()
    layers.registerViewport(rec.vp)
    layers.hideAllExcept(TOOL_RING)
    layers.setLayerOpacity('singleTooth', 0.15)
    resetCalls(rec)

    layers.showAll()

    for (const id of LAYER_IDS) {
      expect(layers.state.visible[id]).toBe(true)
      expect(layers.state.opacity[id]).toBe(LAYER_VISUALS[id].defaultOpacity)
      expect(visibilityOf(rec, id)).toEqual([true]) // 手势路径无条件下发（不因已收敛而省略）
    }
  })

  it('Alt 独显语义经 composable 保留：独显后再次独显恢复全部可见', () => {
    const layers = useLayers()
    const rec = recordingViewport()
    layers.registerViewport(rec.vp)

    layers.soloLayer('rake')
    expect(layers.state.visible.rake).toBe(true)
    for (const id of LAYER_IDS) {
      if (id !== 'rake') expect(layers.state.visible[id]).toBe(false)
    }

    layers.soloLayer('rake') // 已是独显态 → 恢复全部
    for (const id of LAYER_IDS) expect(layers.state.visible[id]).toBe(true)
  })

  it('viewport 未登记时 hideAllExcept 安全跳过（不落半截状态）', () => {
    const layers = useLayers()
    layers.registerViewport(null)

    expect(() => layers.hideAllExcept(TOOL_RING)).not.toThrow()

    for (const id of LAYER_IDS) expect(layers.state.visible[id]).toBe(true)
  })

  describe('setLayerStale — 过期标记（TO-5 / PRD §5.4）', () => {
    it('标记后写入 state.stale 稀疏表，清除即移除条目；显隐/视口均不受牵连（不强隐旧图）', () => {
      const layers = useLayers()
      const rec = recordingViewport()
      layers.registerViewport(rec.vp)
      resetCalls(rec)

      layers.setLayerStale(TOOL_RING, true)
      expect(layers.state.stale[TOOL_RING]).toBe(true)
      layers.setLayerStale(TOOL_RING, false)
      expect(TOOL_RING in layers.state.stale).toBe(false)

      // 过期位是纯状态：不下发任何视口指令、不改可见性
      expect(rec.visibleCalls).toHaveLength(0)
      expect(layers.state.visible[TOOL_RING]).toBe(true)
    })

    it('各层独立：toolRing 的过期不影响其它层条目', () => {
      const layers = useLayers()
      layers.setLayerStale('rake', true)
      layers.setLayerStale(TOOL_RING, true)
      expect(Object.keys(layers.state.stale).sort()).toEqual(['rake', 'toolRing'].sort())
    })

    it('resetLayersState 连同过期位一起复位（用例间隔离）', () => {
      const layers = useLayers()
      layers.setLayerStale(TOOL_RING, true)
      resetLayersState()
      expect(useLayers().state.stale).toEqual({})
    })
  })
})
