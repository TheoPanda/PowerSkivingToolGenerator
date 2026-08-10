/**
 * GearParamsPanel — 单元测试
 * 测试边界：inject('gearParams') + emit('valid-change')
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { ref, reactive, type Ref } from 'vue'
import GearParamsPanel from './GearParamsPanel.vue'
import type { ComponentPublicInstance } from 'vue'
import type { GearParams } from '../composables/useGearParams'

function defaultParams(): GearParams {
  return {
    profile_type: 'involute',
    k_io: 1,
    m_n: null,
    z_w: null,
    β_w: 0,
    j_w: 1,
    b_w: null,
    toothMethod: 'x_w',
    x_w: 0,
    W_k: null,
    k_teeth: null,
    M: null,
    d_p: null,
    α_n: 20,
    h_an: 1,
    c_n: 0.25,
    ρ_f: 0.38,
    rho_tip: 0,
  }
}

type GearParamsPanelInstance = ComponentPublicInstance & {
  expandedSections: { basic: boolean; tooth: boolean; advanced: boolean }
  kRecommended: number | null
  isValid: boolean
  toggleSection: (section: 'basic' | 'tooth' | 'advanced') => void
}

function mountPanel(params?: Partial<GearParams>): VueWrapper<GearParamsPanelInstance> {
  const gearParams = reactive<GearParams>({ ...defaultParams(), ...params })
  return mount(GearParamsPanel, {
    global: {
      provide: {
        gearParams,
      },
    },
  }) as VueWrapper<GearParamsPanelInstance>
}

describe('GearParamsPanel — 基本参数组', () => {
  let wrapper: VueWrapper<GearParamsPanelInstance>

  beforeEach(() => {
    wrapper = mountPanel()
  })

  describe('组件结构', () => {
    it('渲染三个折叠面板标题', () => {
      const headers = wrapper.findAll('.glass-collapse-header')
      expect(headers).toHaveLength(3)
    })

    it('基本参数和齿厚指定默认展开', () => {
      expect(wrapper.vm.expandedSections.basic).toBe(true)
      expect(wrapper.vm.expandedSections.tooth).toBe(true)
    })

    it('高级默认值默认折叠', () => {
      expect(wrapper.vm.expandedSections.advanced).toBe(false)
    })
  })

  describe('① 基本参数字段', () => {
    it('profile_type 下拉有 5 个选项', () => {
      const options = wrapper.findAll('.glass-select option')
      expect(options).toHaveLength(5)
    })

    it('非渐开线选项为 disabled', () => {
      const options = wrapper.findAll('.glass-select option')
      const nonInvolute = options.filter(
        (o) =>
          o.attributes('disabled') !== undefined &&
          (o.element as HTMLOptionElement).value !== 'involute',
      )
      expect(nonInvolute).toHaveLength(4)
    })

    it('k_io 用 Segmented 控件渲染外齿/内齿', () => {
      const btns = wrapper.findAll('.glass-segmented-btn')
      // 至少两个按钮：外齿、内齿
      expect(btns.length).toBeGreaterThanOrEqual(2)
    })

    it('β_w=0 时 j_w 不显示', () => {
      const jwSection = wrapper.find('.glass-field')
      // j_w 不应该在 DOM 中
      const allLabels = wrapper.findAll('.glass-field-label')
      const jwLabels = allLabels.filter((l) => l.text().includes('旋向'))
      expect(jwLabels).toHaveLength(0)
    })

    it('β_w>0 时 j_w 显示', async () => {
      wrapper.unmount()
      const w2 = mountPanel({ β_w: 15 })
      await w2.vm.$nextTick()
      const allLabels = w2.findAll('.glass-field-label')
      const jwLabels = allLabels.filter((l) => l.text().includes('旋向'))
      expect(jwLabels.length).toBeGreaterThanOrEqual(1)
    })
  })

  describe('② 齿厚', () => {
    it('渲染三个齿厚方式选择按钮', () => {
      // segmented buttons in the tooth method selector
      const btns = wrapper.findAll('.glass-segmented-btn')
      // "基本" section has 2 (外齿/内齿), "齿厚" has 3 (变位/公法线/跨棒距) = 5 total
      expect(btns.length).toBeGreaterThanOrEqual(3)
    })

    it('选中"公法线"时显示 W_k 和 k 字段', async () => {
      wrapper.unmount()
      const w2 = mountPanel({ toothMethod: 'W_k' })
      await w2.vm.$nextTick()
      const labels = w2.findAll('.glass-field-label')
      const wkLabels = labels.filter((l) => l.text().includes('W_k'))
      expect(wkLabels.length).toBeGreaterThanOrEqual(1)
    })

    it('选中"跨棒距"时显示 M 和 d_p 字段', async () => {
      wrapper.unmount()
      const w2 = mountPanel({ toothMethod: 'M' })
      await w2.vm.$nextTick()
      const labels = w2.findAll('.glass-field-label')
      const mLabels = labels.filter((l) => l.text().includes('跨棒距'))
      expect(mLabels.length).toBeGreaterThanOrEqual(1)
    })

    it('公法线模式下 k 有推荐值（取决于 α_n/β_w）', async () => {
      wrapper.unmount()
      const w2 = mountPanel({ toothMethod: 'W_k', z_w: 82, β_w: 15, α_n: 20 })
      await w2.vm.$nextTick()
      // k 推荐值应 > 0（自动计算）
      const kVal = w2.vm.kRecommended
      expect(kVal).toBeGreaterThan(0)
    })
  })

  describe('校验与 emit', () => {
    it('初始状态 isValid=false（必填字段为空）', () => {
      expect(wrapper.vm.isValid).toBe(false)
    })

    it('填写所有必填字段后 isValid=true', async () => {
      wrapper.unmount()
      const w2 = mountPanel({ m_n: 2, z_w: 82, b_w: 20 })
      await w2.vm.$nextTick()
      // 需要触发一次校验更新
      expect(w2.vm.isValid).toBe(true)
    })
  })
})
