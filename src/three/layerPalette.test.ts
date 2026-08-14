/**
 * layerPalette 纯数据单测 — 不依赖 Three.js，验证图层 id / 配色 / 默认值单源一致.
 */
import { describe, it, expect } from 'vitest'
import { MATERIAL_PRESETS, LAYER_VISUALS, LAYER_IDS } from './layerPalette'

describe('layerPalette 纯数据', () => {
  it('7 个语义图层 id 齐全且顺序固定', () => {
    expect(LAYER_IDS).toEqual(['workpiece', 'swept_cloud', 'rake', 'edge', 'flank', 'singleTooth', 'conjugate'])
  })

  it('每个图层 id 都有视觉定义且 id 自洽', () => {
    for (const id of LAYER_IDS) {
      expect(LAYER_VISUALS[id]).toBeTruthy()
      expect(LAYER_VISUALS[id].id).toBe(id)
    }
  })

  it('每个视觉定义引用的材质预设都存在', () => {
    for (const id of LAYER_IDS) {
      const visual = LAYER_VISUALS[id]
      expect(MATERIAL_PRESETS[visual.materialPreset]).toBeTruthy()
    }
  })

  it('扫掠点云品牌蓝 + 前/后刀面/刃线用区分色（非主题蓝、非黑）', () => {
    expect(MATERIAL_PRESETS.swept_cloud.color).toBe(0x0060a0) // 品牌蓝 #0060A0
    expect(MATERIAL_PRESETS.rake.color).toBe(0xe8963a) // 琥珀橙
    expect(MATERIAL_PRESETS.flank.color).toBe(0x3aa06a) // 翡翠绿
    expect(MATERIAL_PRESETS.edge.color).toBe(0xe05050) // 珊瑚红（非黑）
    expect(MATERIAL_PRESETS.conjugate.color).toBe(0x00a8cc) // 产形面青色
  })

  it('产形面默认半透明 + 双面', () => {
    expect(LAYER_VISUALS.conjugate.defaultOpacity).toBe(0.5)
    expect(MATERIAL_PRESETS.conjugate.transparent).toBe(true)
    expect(LAYER_VISUALS.conjugate.doubleSide).toBe(true)
  })

  it('工件默认不透明（保持模块① 零回归）', () => {
    expect(LAYER_VISUALS.workpiece.defaultOpacity).toBe(1.0)
    expect(MATERIAL_PRESETS.steel.transparent).toBe(false)
  })

  it('三个面（扫掠点云/前刀面/后刀面）默认半透明', () => {
    expect(LAYER_VISUALS.swept_cloud.defaultOpacity).toBe(0.35)
    expect(LAYER_VISUALS.rake.defaultOpacity).toBe(0.45)
    expect(LAYER_VISUALS.flank.defaultOpacity).toBe(0.5)
    expect(MATERIAL_PRESETS.swept_cloud.transparent).toBe(true)
    expect(MATERIAL_PRESETS.rake.transparent).toBe(true)
    expect(MATERIAL_PRESETS.flank.transparent).toBe(true)
  })
})
