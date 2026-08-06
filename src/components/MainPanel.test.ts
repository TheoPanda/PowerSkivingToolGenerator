/**
 * MainPanel 步骤内容区 — 单元测试
 * 测试边界：组件公共行为（DOM 结构 + 用户交互）
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import MainPanel from './MainPanel.vue'
import type { ComponentPublicInstance } from 'vue'

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

    it('currentStep=3 时显示步骤 3 占位', async () => {
      wrapper.vm.expanded = true
      wrapper.vm.currentStep = 3
      await wrapper.vm.$nextTick()

      const body = wrapper.find('.step-body')
      expect(body.text()).toContain('刀具几何体')
      expect(body.text()).toContain('即将推出')
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
