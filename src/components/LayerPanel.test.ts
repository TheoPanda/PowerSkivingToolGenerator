/**
 * LayerPanel 组件测试 — provide/inject 接口（注入 fake viewport，测图层行/表头/显隐/
 * 聚焦/透明度/一键全显全隐/Alt 独显/可见计数徽章）.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import * as THREE from 'three'
import LayerPanel from './LayerPanel.vue'
import { GEAR_VIEWPORT_KEY, type GearViewport } from '../three/gearViewport'
import { LAYER_IDS } from '../three/layerPalette'
import { interferenceState, setInterferenceVisible } from '../composables/useInterferenceLegend'
// 显隐权威源已上提为模块级单例（PRD §5.5）：用例间复位到默认，避免上个用例的显隐串场
import { resetLayersState } from '../composables/useLayers'

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
  beforeEach(() => {
    resetLayersState()
  })

  it('渲染 10 个图层行', () => {
    const wrapper = mountPanel()
    for (const id of LAYER_IDS) {
      expect(wrapper.find(`[data-test="layer-row-${id}"]`).exists()).toBe(true)
    }
  })

  it('表头四列明示（图层/可见/功能/透明度）', () => {
    const wrapper = mountPanel()
    const head = wrapper.find('[data-test="layer-colhead"]')
    expect(head.exists()).toBe(true)
    const labels = head.findAll('.lp-ch').map((s) => s.text())
    expect(labels).toEqual(['图层', '可见', '功能', '透明度'])
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

  it('全部隐藏对每个图层 setLayerVisible(false)，不动透明度', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    await wrapper.find('[data-test="layer-show-none"]').trigger('click')
    for (const id of LAYER_IDS) {
      expect(vp.setLayerVisible).toHaveBeenCalledWith(id, false)
    }
    expect(vp.setLayerOpacity).not.toHaveBeenCalled()
  })

  it('Alt+点击眼睛独显该层（其余全隐）', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    await wrapper.find('[data-test="layer-eye-edge"]').trigger('click', { altKey: true })
    expect(vp.setLayerVisible).toHaveBeenCalledWith('edge', true)
    for (const id of LAYER_IDS) {
      if (id !== 'edge') {
        expect(vp.setLayerVisible).toHaveBeenCalledWith(id, false)
      }
    }
  })

  it('独显态再次 Alt+点击恢复全部可见', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    // 先独显 edge
    await wrapper.find('[data-test="layer-eye-edge"]').trigger('click', { altKey: true })
    vi.mocked(vp.setLayerVisible).mockClear()
    // 独显态下再 Alt+点击 → 全部恢复可见
    await wrapper.find('[data-test="layer-eye-edge"]').trigger('click', { altKey: true })
    for (const id of LAYER_IDS) {
      expect(vp.setLayerVisible).toHaveBeenCalledWith(id, true)
    }
  })

  it('可见计数徽章随显隐联动（10/10 → 隐藏一层 9/10）', async () => {
    const vp = fakeViewport()
    const wrapper = mountPanel(vp)
    expect(wrapper.find('[data-test="layer-visible-count"]').text()).toBe(`10/${LAYER_IDS.length}`)
    await wrapper.find('[data-test="layer-eye-rake"]').trigger('click')
    expect(wrapper.find('[data-test="layer-visible-count"]').text()).toBe(`9/${LAYER_IDS.length}`)
    // 全隐 → 0/10 且徽章转警示态
    await wrapper.find('[data-test="layer-show-none"]').trigger('click')
    expect(wrapper.find('[data-test="layer-visible-count"]').text()).toBe(`0/${LAYER_IDS.length}`)
    expect(wrapper.find('[data-test="layer-visible-count"]').classes()).toContain('zero')
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

  it('拖动到左缘阈值内松手 → 贴边吸附到左 24px（与 ResultPanel 同规格）', async () => {
    const wrapper = mountPanel()
    // 默认位 x = innerWidth(1024) − 264 − 24(右缘统一边距) = 736；按下标题 → 大位移拖到左缘内
    await wrapper.find('.lp-title').trigger('mousedown', { clientX: 300, clientY: 200, button: 0 })
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: -400, clientY: 205 }))
    window.dispatchEvent(new MouseEvent('mouseup'))
    await nextTick()
    const left = parseFloat((wrapper.find('.layer-panel').element as HTMLElement).style.left)
    expect(left).toBe(24) // SNAP_LEFT
  })

  it('拖到屏幕中部松手 → 不吸附（位置保留）', async () => {
    const wrapper = mountPanel()
    await wrapper.find('.lp-title').trigger('mousedown', { clientX: 300, clientY: 200, button: 0 })
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 100, clientY: 205 })) // x ≈ 548，远离四边
    window.dispatchEvent(new MouseEvent('mouseup'))
    await nextTick()
    const left = parseFloat((wrapper.find('.layer-panel').element as HTMLElement).style.left)
    expect(left).toBe(736 - 200) // clamp 后原位（736 + dx −200 = 536）
  })
})
