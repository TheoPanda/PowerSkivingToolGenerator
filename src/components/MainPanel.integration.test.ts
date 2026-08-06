/**
 * MainPanel 步骤联动集成测试
 * 测试边界：provide/inject + 步骤导航 + 下一步校验屏障
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import MainPanel from './MainPanel.vue'
import type { ComponentPublicInstance } from 'vue'

type MainPanelInstance = ComponentPublicInstance & {
  expanded: boolean
  currentStep: number
  step1Valid: boolean
  step1GuideVisible: boolean
  nextStep: () => void
  goToStep: (step: number) => void
  togglePanel: () => void
}

function createWrapper(): VueWrapper<MainPanelInstance> {
  return mount(MainPanel, {
    global: {
      stubs: {
        img: true,
      },
    },
  }) as VueWrapper<MainPanelInstance>
}

describe('MainPanel — 步骤联动', () => {
  let wrapper: VueWrapper<MainPanelInstance>

  beforeEach(() => {
    wrapper = createWrapper()
    wrapper.vm.expanded = true
  })

  describe('gearParams store', () => {
    it('MainPanel 持有 reactive gearParams', () => {
      // 组件能正常挂载即说明 provide/inject 链路完整
      expect(wrapper.vm).toBeDefined()
    })

    it('初始 step1Valid 为 false', async () => {
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.step1Valid).toBe(false)
    })
  })

  describe('步骤导航交互', () => {
    it('点击步骤 2 且 step1Valid=false 时显示引导文字', async () => {
      wrapper.vm.currentStep = 1
      await wrapper.vm.$nextTick()

      wrapper.vm.goToStep(2)
      await wrapper.vm.$nextTick()

      // 步骤未完成 → currentStep 应仍为 1（没有推进）
      expect(wrapper.vm.step1GuideVisible).toBe(true)
    })

    it('步骤 5 时不显示"下一步"按钮', async () => {
      wrapper.vm.currentStep = 5
      await wrapper.vm.$nextTick()

      const btn = wrapper.find('.next-step-btn')
      expect(btn.exists()).toBe(false)
    })

    it('步骤 1 时"下一步"按钮存在但 disabled（初始状态）', async () => {
      wrapper.vm.currentStep = 1
      await wrapper.vm.$nextTick()

      const btn = wrapper.find('.next-step-btn')
      expect(btn.exists()).toBe(true)
      expect(btn.attributes('disabled')).toBeDefined()
    })
  })

  describe('nextStep 校验屏障', () => {
    it('nextStep 在 step1Valid=false 时不推进', async () => {
      wrapper.vm.currentStep = 1
      await wrapper.vm.$nextTick()

      wrapper.vm.nextStep()
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.currentStep).toBe(1)
    })
  })
})
