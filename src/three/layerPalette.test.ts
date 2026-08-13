/**
 * layerPalette 纯数据单测 — 不依赖 Three.js，验证图层 id / 配色 / 默认值单源一致.
 */
import { describe, it, expect } from 'vitest'
import { MATERIAL_PRESETS, LAYER_VISUALS, LAYER_IDS } from './layerPalette'

describe('layerPalette 纯数据', () => {
  it('6 个语义图层 id 齐全且顺序固定', () => {
    expect(LAYER_IDS).toEqual(['workpiece', 'generatrix', 'rake', 'edge', 'flank', 'singleTooth'])
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

  it('品牌蓝 / 冰蓝 / 深色与 theme.css 同名色一致', () => {
    expect(MATERIAL_PRESETS.generatrix.color).toBe(0x0060a0) // --brand-blue #0060A0
    expect(MATERIAL_PRESETS.rake.color).toBe(0xe8f0f8) // 冰蓝 #E8F0F8
    expect(MATERIAL_PRESETS.edge.color).toBe(0x1f2937) // 深色 #1f2937
  })

  it('工件默认不透明（保持模块① 零回归）', () => {
    expect(LAYER_VISUALS.workpiece.defaultOpacity).toBe(1.0)
    expect(MATERIAL_PRESETS.steel.transparent).toBe(false)
  })

  it('包络层（产形面/前刀面）默认半透明', () => {
    expect(LAYER_VISUALS.generatrix.defaultOpacity).toBe(0.35)
    expect(LAYER_VISUALS.rake.defaultOpacity).toBe(0.45)
    expect(MATERIAL_PRESETS.generatrix.transparent).toBe(true)
    expect(MATERIAL_PRESETS.rake.transparent).toBe(true)
  })
})
