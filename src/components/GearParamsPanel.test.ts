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
import { workpieceState } from '../composables/useWorkpieceState'
import type { SpecPayload } from '../api'

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
    d_rim: null,
    α_n: 20,
    h_an: 1,
    c_n: 0.25,
    ρ_f: 0.38,
    rho_tip: 0,
    root_fillet: true,
    tip_mode: 'none',
    chamfer_tip: 0,
  }
}

type GearParamsPanelInstance = ComponentPublicInstance & {
  expandedSections: { basic: boolean; tooth: boolean; advanced: boolean; decoration: boolean }
  kRecommended: number | null
  isValid: boolean
  internalMode: boolean
  internalNotice: string | null
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
    it('渲染四个折叠面板标题（含「齿顶/齿根修饰」）', () => {
      const headers = wrapper.findAll('.glass-collapse-header')
      expect(headers).toHaveLength(4)
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

  describe('④ 齿顶处理三态 + 收敛提示', () => {
    it('渲染 无/倒角/圆角 三态分段控件', () => {
      const btns = wrapper.findAll('.glass-segmented-btn').map((b) => b.text())
      expect(btns).toContain('无')
      expect(btns).toContain('倒角')
      expect(btns).toContain('圆角')
    })

    it('默认无模式: 圆角/倒角输入均不显示', () => {
      const labels = wrapper.findAll('.glass-field-label').map((l) => l.text())
      expect(labels.some((t) => t.includes('齿顶圆角系数'))).toBe(false)
      expect(labels.some((t) => t.includes('齿顶倒角系数'))).toBe(false)
    })

    it('选「圆角」显示 rho_tip 输入', async () => {
      wrapper.unmount()
      const w2 = mountPanel({ tip_mode: 'round' })
      await w2.vm.$nextTick()
      const labels = w2.findAll('.glass-field-label').map((l) => l.text())
      expect(labels.some((t) => t.includes('齿顶圆角系数'))).toBe(true)
    })

    it('选「倒角」显示 chamfer_tip 输入', async () => {
      wrapper.unmount()
      const w2 = mountPanel({ tip_mode: 'chamfer' })
      await w2.vm.$nextTick()
      const labels = w2.findAll('.glass-field-label').map((l) => l.text())
      expect(labels.some((t) => t.includes('齿顶倒角系数'))).toBe(true)
    })

    it('收敛软提示: actual < 请求时显示, 相等时隐藏', async () => {
      // 全局 spec: rho_tip_actual=0.5mm (m_n=2.5 → 系数 0.2)
      workpieceState.spec = {
        params: {
          inputs: [],
          outputs: [{ key: 'rho_tip_actual', value: 0.5, label: '', symbol: '', unit: '' }],
        },
        single_tooth: {} as SpecPayload['single_tooth'],
        outline: {} as SpecPayload['outline'],
      } as SpecPayload
      try {
        wrapper.unmount()
        // 请求 0.3 (> actual 0.2) → 收敛提示显示
        const wConv = mountPanel({ tip_mode: 'round', m_n: 2.5, rho_tip: 0.3 })
        await wConv.vm.$nextTick()
        const convHint = wConv.findAll('.glass-field-hint').find((h) => h.text().includes('已取最接近请求值'))
        expect(convHint).toBeTruthy()
        // 请求 0.2 (== actual) → 隐藏
        wConv.unmount()
        const wEq = mountPanel({ tip_mode: 'round', m_n: 2.5, rho_tip: 0.2 })
        await wEq.vm.$nextTick()
        const eqHint = wEq.findAll('.glass-field-hint').find((h) => h.text().includes('已取最接近请求值'))
        expect(eqHint).toBeFalsy()
      } finally {
        workpieceState.spec = null
      }
    })

    it('倒角收敛软提示: actual < 请求时显示', async () => {
      workpieceState.spec = {
        params: {
          inputs: [],
          outputs: [{ key: 'chamfer_actual', value: 0.3, label: '', symbol: '', unit: '' }],
        },
        single_tooth: {} as SpecPayload['single_tooth'],
        outline: {} as SpecPayload['outline'],
      } as SpecPayload
      try {
        wrapper.unmount()
        // 请求 0.5×2.5=1.25mm > actual 0.3mm → 收敛提示显示
        const w = mountPanel({ tip_mode: 'chamfer', m_n: 2.5, chamfer_tip: 0.5 })
        await w.vm.$nextTick()
        const hint = w.findAll('.glass-field-hint').find((h) => h.text().includes('已取最接近请求值'))
        expect(hint).toBeTruthy()
      } finally {
        workpieceState.spec = null
      }
    })
  })

  describe('④ 齿顶/齿根修饰', () => {
    it('齿根圆角勾选与 store.root_fillet 双向绑定', async () => {
      const gearParams = reactive<GearParams>({ ...defaultParams(), root_fillet: true })
      const w = mount(GearParamsPanel, { global: { provide: { gearParams } } })
      const checkbox = w.find('input[type="checkbox"]')
      expect(checkbox.exists()).toBe(true)
      expect((checkbox.element as HTMLInputElement).checked).toBe(true)
      await checkbox.setValue(false)
      expect(gearParams.root_fillet).toBe(false)
      await checkbox.setValue(true)
      expect(gearParams.root_fillet).toBe(true)
    })

    it('ρ*_f 输入在新板块内（已从「高级」移入）', () => {
      const labels = wrapper.findAll('.glass-field-label')
      const rfLabels = labels.filter((l) => l.text().includes('齿根圆角系数'))
      expect(rfLabels.length).toBeGreaterThanOrEqual(1)
    })

    it('取消勾选后 ρ*_f 输入隐藏（条件显示）', async () => {
      wrapper.unmount()
      const w2 = mountPanel({ root_fillet: false })
      await w2.vm.$nextTick()
      const labels = w2.findAll('.glass-field-label')
      const rfLabels = labels.filter((l) => l.text().includes('齿根圆角系数'))
      expect(rfLabels).toHaveLength(0)
    })
  })

  describe('内齿轮模式 (k_io=−1, T04)', () => {
    it('内齿时显示「齿圈外径 d_rim」输入, 外齿时不显示', async () => {
      const w = mountPanel({ k_io: -1, m_n: 2, z_w: 82, b_w: 20 })
      await w.vm.$nextTick()
      const labels = w.findAll('.glass-field-label').map((l) => l.text())
      expect(labels.some((t) => t.includes('齿圈外径'))).toBe(true)
      w.unmount()
      const wExt = mountPanel({ k_io: 1, m_n: 2, z_w: 82, b_w: 20 })
      await wExt.vm.$nextTick()
      const extLabels = wExt.findAll('.glass-field-label').map((l) => l.text())
      expect(extLabels.some((t) => t.includes('齿圈外径'))).toBe(false)
    })

    it('内齿时公法线按钮灰置 (disabled)', async () => {
      const w = mountPanel({ k_io: -1, m_n: 2, z_w: 82, b_w: 20 })
      await w.vm.$nextTick()
      const wkBtn = w.findAll('.glass-segmented-btn').find((b) => b.text() === '公法线')
      expect(wkBtn).toBeTruthy()
      expect(wkBtn!.attributes('disabled')).toBeDefined()
    })

    it('外→内切换自动重置冲突值 (W_k→x_w, tip_mode→none; β_w 保留 — ADR-017 内斜齿)', async () => {
      const gearParams = reactive<GearParams>({
        ...defaultParams(), m_n: 2, z_w: 82, b_w: 20,
        toothMethod: 'W_k', β_w: 15, tip_mode: 'round', k_io: 1,
      })
      const w = mount(GearParamsPanel, { global: { provide: { gearParams } } })
      gearParams.k_io = -1
      await w.vm.$nextTick()
      expect(gearParams.toothMethod).toBe('x_w')
      expect(gearParams.β_w).toBe(15)  // 内斜齿已支持, 不归零 (ADR-017)
      expect(gearParams.tip_mode).toBe('none')
      expect((w.vm as GearParamsPanelInstance).internalNotice).toBeTruthy()
    })

    it('内齿时 β_w 输入可编辑 (ADR-017 内斜齿), 无 disabled', async () => {
      const w = mountPanel({ k_io: -1, m_n: 2, z_w: 82, b_w: 20, β_w: 0 })
      await w.vm.$nextTick()
      const betaInput = w.findAll('input[type="number"]').find(
        (i) => i.attributes('aria-label') === 'β_w',
      )
      expect(betaInput).toBeTruthy()
      expect(betaInput!.attributes('disabled')).toBeUndefined()
    })

    it('内斜齿 (k_io=−1, β_w>0) 显示旋向选择器', async () => {
      const w = mountPanel({ k_io: -1, m_n: 2, z_w: 82, b_w: 20, β_w: 15 })
      await w.vm.$nextTick()
      const allLabels = w.findAll('.glass-field-label')
      expect(allLabels.some((l) => l.text().includes('旋向'))).toBe(true)
    })

    it('内齿时「齿顶/齿根修饰」区灰置 (显示提示, 无控件)', async () => {
      const w = mountPanel({ k_io: -1, m_n: 2, z_w: 82, b_w: 20 })
      await w.vm.$nextTick()
      const hint = w.findAll('.glass-field-hint').find((h) => h.text().includes('内齿'))
      expect(hint).toBeTruthy()
      const checkbox = w.find('input[type="checkbox"]')
      expect(checkbox.exists()).toBe(false)
    })

    it('M 模式 d_p 占位: 内齿 ≈1.44×mₙ, 外齿 ≈1.68×mₜ', async () => {
      const wInt = mountPanel({ k_io: -1, toothMethod: 'M', m_n: 2, z_w: 82, b_w: 20 })
      await wInt.vm.$nextTick()
      const dPInt = wInt.findAll('input').find((i) => (i.attributes('placeholder') || '').includes('1.44'))
      expect(dPInt).toBeTruthy()
      wInt.unmount()
      const wExt = mountPanel({ k_io: 1, toothMethod: 'M', m_n: 2, z_w: 82, b_w: 20 })
      await wExt.vm.$nextTick()
      const dPExt = wExt.findAll('input').find((i) => (i.attributes('placeholder') || '').includes('1.68'))
      expect(dPExt).toBeTruthy()
    })
  })
})
