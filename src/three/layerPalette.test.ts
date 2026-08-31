/**
 * layerPalette 纯数据单测 — 不依赖 Three.js，验证图层 id / 配色 / 默认值单源一致.
 */
import { describe, it, expect } from 'vitest'
import { MATERIAL_PRESETS, LAYER_VISUALS, LAYER_IDS } from './layerPalette'

describe('layerPalette 纯数据', () => {
  it('11 个语义图层 id 齐全且顺序固定（刀体紧随刀具整环，ADR-021）', () => {
    expect(LAYER_IDS).toEqual(['workpiece', 'toothFlank', 'conjugate', 'conjugateGear', 'rake', 'edge', 'flank', 'singleTooth', 'toolRing', 'toolBody', 'sweptCloud'])
  })

  it('刀体图层默认不透明、单面、硬质合金（用户指定，与单齿同材质；ADR-021）', () => {
    expect(LAYER_VISUALS.toolBody.label).toBe('刀体')
    expect(LAYER_VISUALS.toolBody.defaultOpacity).toBe(1.0)
    expect(LAYER_VISUALS.toolBody.doubleSide).toBe(false)
    expect(LAYER_VISUALS.toolBody.materialPreset).toBe('carbide')
    expect(MATERIAL_PRESETS.carbide.color).toBe(0x5a5854)
    expect(MATERIAL_PRESETS.carbide.transparent).toBe(false)
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

  it('前/后刀面/刃线用区分色（非主题蓝、非黑）', () => {
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

  it('等效产形齿轮默认半透明 + 双面 + 靛蓝（GLB 带符号距离顶点色，前端「干涉」切换样式）', () => {
    expect(LAYER_VISUALS.conjugateGear.defaultOpacity).toBe(0.45)
    expect(MATERIAL_PRESETS.conjugateGear.transparent).toBe(true)
    expect(LAYER_VISUALS.conjugateGear.doubleSide).toBe(true)
    expect(MATERIAL_PRESETS.conjugateGear.color).toBe(0x2a6fbf)
  })

  it('工件默认不透明（保持模块① 零回归）', () => {
    expect(LAYER_VISUALS.workpiece.defaultOpacity).toBe(1.0)
    expect(MATERIAL_PRESETS.steel.transparent).toBe(false)
  })

  it('前刀面/后刀面默认半透明', () => {
    expect(LAYER_VISUALS.rake.defaultOpacity).toBe(0.45)
    expect(LAYER_VISUALS.flank.defaultOpacity).toBe(0.5)
    expect(MATERIAL_PRESETS.rake.transparent).toBe(true)
    expect(MATERIAL_PRESETS.flank.transparent).toBe(true)
  })

  it('扫掠点云图层（运动仿真）默认半透明 + 双面 + jet 起点蓝色块', () => {
    expect(LAYER_VISUALS.sweptCloud.label).toBe('扫掠点云')
    expect(LAYER_VISUALS.sweptCloud.defaultOpacity).toBe(0.85)
    expect(LAYER_VISUALS.sweptCloud.doubleSide).toBe(true)
    expect(MATERIAL_PRESETS.spectrum.transparent).toBe(true)
    expect(MATERIAL_PRESETS.spectrum.color).toBe(0x3050c8) // 加深版 jet(0) 蓝
  })

  it('内齿轮齿面：points 种类 + 洋红紫 + 屏幕空间固定像素点（防世界单位点连成条带）', () => {
    expect(LAYER_VISUALS.toothFlank.label).toBe('内齿轮齿面')
    expect(LAYER_VISUALS.toothFlank.kind).toBe('points')
    expect(LAYER_VISUALS.toothFlank.pointSize).toBe(4) // 4px 屏幕空间
    expect(LAYER_VISUALS.toothFlank.pointSizeAttenuation).toBe(false)
    expect(MATERIAL_PRESETS.toothFlank.color).toBe(0xc05ab0) // 洋红紫 #C05AB0
    expect(MATERIAL_PRESETS.toothFlank.transparent).toBe(false)
  })

  it('内齿轮齿面色与其余图层色全部互异（GLB 顶点色为主，preset 色兜底）', () => {
    const others = LAYER_IDS.filter((id) => id !== 'toothFlank').map((id) => MATERIAL_PRESETS[LAYER_VISUALS[id].materialPreset].color)
    const c = MATERIAL_PRESETS.toothFlank.color
    expect(others).not.toContain(c)
  })
})
