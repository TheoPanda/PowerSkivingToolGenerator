/**
 * LayerPanel 组件测试 — provide/inject 接口（注入 fake viewport，测图层行/显隐/聚焦/透明度/全部显示）.
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import LayerPanel from './LayerPanel.vue'
import { GEAR_VIEWPORT_KEY, type GearViewport } from '../three/gearViewport'
import { LAYER_IDS } from '../three/layerPalette'

function fakeViewport(): GearViewport {
  return {
    loadGear: vi.fn(),
    addLayer: vi.fn(),
    setSweptCloudReveal: vi.fn(),
    setSweptCloudMode: vi.fn(),
    setEnvelopeInstall: vi.fn(),
    removeLayer: vi.fn(),
    clearLayers: vi.fn(),
    setLayerVisible: vi.fn(),
    setLayerOpacity: vi.fn(),
    focusLayer: vi.fn(),
    setRenderMode: vi.fn(),
    setLoggedIn: vi.fn(),
    setModelLayout: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
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
  it('渲染 6 个图层行', () => {
    const wrapper = mountPanel()
    for (const id of LAYER_IDS) {
      expect(wrapper.find(`[data-test="layer-row-${id}"]`).exists()).toBe(true)
    }
  })

  it('眼睛开关触发 setLayerVisible（toggle 为 false）', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    await wrapper.find('[data-test="layer-eye-swept_cloud"]').trigger('click')
    expect(vp.setLayerVisible).toHaveBeenCalledWith('swept_cloud', false)
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
    await wrapper.find('[data-test="layer-opacity-swept_cloud"]').setValue('0.5')
    expect(vp.setLayerOpacity).toHaveBeenCalledWith('swept_cloud', 0.5)
  })

  it('全部显示对每个图层 setLayerVisible(true)', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    await wrapper.find('[data-test="layer-show-all"]').trigger('click')
    for (const id of LAYER_IDS) {
      expect(vp.setLayerVisible).toHaveBeenCalledWith(id, true)
    }
  })

  it('gear:layer-ready 事件把对应图层重置为可见（重新包络后联动）', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    // 先隐藏 swept_cloud
    await wrapper.find('[data-test="layer-eye-swept_cloud"]').trigger('click')
    expect(wrapper.find('[data-test="layer-eye-swept_cloud"]').classes()).toContain('off')
    // 重新包络 → dispatch gear:layer-ready
    window.dispatchEvent(new CustomEvent('gear:layer-ready', { detail: { id: 'swept_cloud', glbBase64: 'x' } }))
    await nextTick()
    expect(wrapper.find('[data-test="layer-eye-swept_cloud"]').classes()).not.toContain('off')
  })
})
