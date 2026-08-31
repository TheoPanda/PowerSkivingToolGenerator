/**
 * MainPanel 步骤内容区 — 单元测试
 * 测试边界：组件公共行为（DOM 结构 + 用户交互）
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import MainPanel from './MainPanel.vue'
import type { ComponentPublicInstance } from 'vue'
import { resetLayersState, useLayers } from '../composables/useLayers'

type MainPanelInstance = ComponentPublicInstance & {
  expanded: boolean
  currentStep: number
  togglePanel: () => void
}

function createWrapper(): VueWrapper<MainPanelInstance> {
  return mount(MainPanel, {
    global: {
      stubs: {
        img: true,
        WorkpieceViewer: true,  // stub to avoid API call on mount
      },
    },
  }) as VueWrapper<MainPanelInstance>
}

describe('MainPanel — 步骤内容区', () => {
  let wrapper: VueWrapper<MainPanelInstance>

  beforeEach(() => {
    resetLayersState() // 图层预设用例与其它用例互不串场
    wrapper = createWrapper()
  })

  describe('步骤内容区 (step-body)', () => {
    it('面板展开后 .step-body 存在且可滚动', async () => {
      // 初始为展开 (expanded: true)
      wrapper.vm.expanded = true
      await wrapper.vm.$nextTick()

      const body = wrapper.find('.step-body')
      expect(body.exists()).toBe(true)
    })

    it('面板展开后渲染当前步骤内容', async () => {
      wrapper.vm.expanded = true
      wrapper.vm.currentStep = 1
      await wrapper.vm.$nextTick()

      const body = wrapper.find('.step-body')
      expect(body.exists()).toBe(true)
    })

    it('currentStep=2 时渲染步骤2内容 (非占位)', async () => {
      wrapper.vm.expanded = true
      wrapper.vm.currentStep = 2
      await wrapper.vm.$nextTick()

      const body = wrapper.find('.step-body')
      // 步骤2 不应显示占位文字
      expect(body.text()).not.toContain('即将推出')
    })

    it('currentStep=3 时渲染 ToolSolidPanel（占位「即将推出」退役，TO-5）', async () => {
      wrapper.vm.expanded = true
      wrapper.vm.currentStep = 3
      await wrapper.vm.$nextTick()

      const body = wrapper.find('.step-body')
      expect(body.text()).toContain('必填')
      expect(body.text()).toContain('生成完整刀具体')
      // 步骤3 不再是占位页
      expect(body.text()).not.toContain('即将推出')
    })

    it('currentStep=3 时也执行「仅留 toolRing+toolBody」图层预设（ADR-021 修订；每次进入都执行）', async () => {
      // useLayers 预设需要已登记 viewport（未登记整条跳过）——登记最小 stub
      const layers = useLayers()
      layers.registerViewport({ setLayerVisible: (): void => undefined, setLayerOpacity: (): void => undefined } as never)
      wrapper.vm.expanded = true
      wrapper.vm.currentStep = 2
      await wrapper.vm.$nextTick()
      layers.setLayerVisible('workpiece', true)

      wrapper.vm.currentStep = 3
      await wrapper.vm.$nextTick()

      expect(layers.state.visible.toolRing).toBe(true)
      expect(layers.state.visible.toolBody).toBe(true) // 刀体与齿圈拼成完整刀（ADR-021）
      expect(layers.state.visible.workpiece).toBe(false)
    })

    it('currentStep=4 时显示步骤 4 占位', async () => {
      wrapper.vm.expanded = true
      wrapper.vm.currentStep = 4
      await wrapper.vm.$nextTick()

      const body = wrapper.find('.step-body')
      expect(body.text()).toContain('仿真验证')
      expect(body.text()).toContain('即将推出')
    })

    it('currentStep=5 时显示步骤 5 占位', async () => {
      wrapper.vm.expanded = true
      wrapper.vm.currentStep = 5
      await wrapper.vm.$nextTick()

      const body = wrapper.find('.step-body')
      expect(body.text()).toContain('工艺文件')
      expect(body.text()).toContain('即将推出')
    })
  })

  describe('"下一步"按钮', () => {
    it('面板展开且步骤 1 时按钮存在', async () => {
      wrapper.vm.expanded = true
      wrapper.vm.currentStep = 1
      await wrapper.vm.$nextTick()

      const btn = wrapper.find('.next-step-btn')
      expect(btn.exists()).toBe(true)
    })

    it('步骤 5 时不显示"下一步"按钮', async () => {
      wrapper.vm.expanded = true
      wrapper.vm.currentStep = 5
      await wrapper.vm.$nextTick()

      const btn = wrapper.find('.next-step-btn')
      expect(btn.exists()).toBe(false)
    })
  })
})
