/**
 * LayerPanel 组件测试 — provide/inject 接口（注入 fake viewport，测图层行/显隐/聚焦/透明度/全部显示）.
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import * as THREE from 'three'
import LayerPanel from './LayerPanel.vue'
import { GEAR_VIEWPORT_KEY, type GearViewport } from '../three/gearViewport'
import { LAYER_IDS } from '../three/layerPalette'
import { interferenceState, setInterferenceVisible } from '../composables/useInterferenceLegend'

function fakeViewport(): GearViewport {
  return {
    loadGear: vi.fn(),
    addLayer: vi.fn(),
    setEnvelopeInstall: vi.fn(),
    removeLayer: vi.fn(),
    clearLayers: vi.fn(),
    setLayerVisible: vi.fn(),
    setLayerOpacity: vi.fn(),
    focusLayer: vi.fn(),
    setRenderMode: vi.fn(),
    setWorkpieceView: vi.fn(),
    setConjugateGearInterference: vi.fn(),
    setLoggedIn: vi.fn(),
    setModelLayout: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    loadAnimMesh: vi.fn(),
    setAnimPhi: vi.fn(),
    setAnimPlaying: vi.fn(),
    setAnimSpeed: vi.fn(),
    setAnimGearMode: vi.fn(),
    setAnimSection: vi.fn(),
    setSpectrumMode: vi.fn(),
    setSpectrumReveal: vi.fn(),
    clearAnimMesh: vi.fn(),
    getViewInfo: vi.fn(() => ({ center: new THREE.Vector3(), distance: 10 })),
    setStandardView: vi.fn(),
    resetView: vi.fn(),
    getViewCubeRotation: vi.fn(() => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]),
  }
}

function mountPanel(viewport: GearViewport = fakeViewport()) {
  return mount(LayerPanel, {
    global: {
      provide: {
        [GEAR_VIEWPORT_KEY]: ref(viewport),
      },
    },
  })
}

describe('LayerPanel 图层列表', () => {
  it('渲染 7 个图层行', () => {
    const wrapper = mountPanel()
    for (const id of LAYER_IDS) {
      expect(wrapper.find(`[data-test="layer-row-${id}"]`).exists()).toBe(true)
    }
  })

  it('眼睛开关触发 setLayerVisible（toggle 为 false）', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    await wrapper.find('[data-test="layer-eye-rake"]').trigger('click')
    expect(vp.setLayerVisible).toHaveBeenCalledWith('rake', false)
  })

  it('内齿轮齿面行渲染 + 眼睛开关触发 setLayerVisible', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    expect(wrapper.find('[data-test="layer-row-toothFlank"]').exists()).toBe(true)
    await wrapper.find('[data-test="layer-eye-toothFlank"]').trigger('click')
    expect(vp.setLayerVisible).toHaveBeenCalledWith('toothFlank', false)
  })

  it('点名称触发 focusLayer', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    await wrapper.findAll('.lp-name')[0].trigger('click') // 第一个 = workpiece
    expect(vp.focusLayer).toHaveBeenCalledWith('workpiece')
  })

  it('透明度滑条触发 setLayerOpacity', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    await wrapper.find('[data-test="layer-opacity-rake"]').setValue('0.5')
    expect(vp.setLayerOpacity).toHaveBeenCalledWith('rake', 0.5)
  })

  it('全部显示对每个图层 setLayerVisible(true)', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    await wrapper.find('[data-test="layer-show-all"]').trigger('click')
    for (const id of LAYER_IDS) {
      expect(vp.setLayerVisible).toHaveBeenCalledWith(id, true)
    }
  })

  it('工件「线框」按钮切换透明线框（实体 ↔ 线框）', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    const btn = wrapper.find('[data-test="layer-wire-workpiece"]')
    expect(btn.exists()).toBe(true)
    // 初始实体 → 点击切到透明线框
    await btn.trigger('click')
    expect(vp.setWorkpieceView).toHaveBeenCalledWith('wireframe')
    // 再点切回实体
    await btn.trigger('click')
    expect(vp.setWorkpieceView).toHaveBeenCalledWith('solid')
  })

  it('等效产形齿轮「干涉」按钮切换样式（单色 ↔ 干涉热力图）+ 图例联动', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    const btn = wrapper.find('[data-test="layer-interference-conjugateGear"]')
    expect(btn.exists()).toBe(true)
    setInterferenceVisible(false)
    // 初始单色 → 点击切到干涉热力图（图例显示）
    await btn.trigger('click')
    expect(vp.setConjugateGearInterference).toHaveBeenCalledWith(true)
    expect(interferenceState.visible).toBe(true)
    // 再点切回单色（图例隐藏）
    await btn.trigger('click')
    expect(vp.setConjugateGearInterference).toHaveBeenCalledWith(false)
    expect(interferenceState.visible).toBe(false)
  })

  it('全部显示把工件视图一并重置为实体', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    await wrapper.find('[data-test="layer-wire-workpiece"]').trigger('click') // 切到线框
    expect(vp.setWorkpieceView).toHaveBeenCalledWith('wireframe')
    await wrapper.find('[data-test="layer-show-all"]').trigger('click')
    expect(vp.setWorkpieceView).toHaveBeenCalledWith('solid')
  })

  it('gear:layer-ready 事件把对应图层重置为可见（重新包络后联动）', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    // 先隐藏 rake
    await wrapper.find('[data-test="layer-eye-rake"]').trigger('click')
    expect(wrapper.find('[data-test="layer-eye-rake"]').classes()).toContain('off')
    // 重新包络 → dispatch gear:layer-ready
    window.dispatchEvent(new CustomEvent('gear:layer-ready', { detail: { id: 'rake', glbBase64: 'x' } }))
    await nextTick()
    expect(wrapper.find('[data-test="layer-eye-rake"]').classes()).not.toContain('off')
  })

  it('扫掠点云行「仿真」按钮派发 gear:request-simulation（产形面行不再有仿真按钮）', async () => {
    const spy = vi.fn()
    window.addEventListener('gear:request-simulation', spy)
    const wrapper = mountPanel()
    expect(wrapper.find('[data-test="layer-sim-sweptCloud"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="layer-sim-conjugate"]').exists()).toBe(false)
    await wrapper.find('[data-test="layer-sim-sweptCloud"]').trigger('click')
    expect(spy).toHaveBeenCalledTimes(1)
    window.removeEventListener('gear:request-simulation', spy)
  })
})
