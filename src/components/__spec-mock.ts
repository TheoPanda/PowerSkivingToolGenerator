/**
 * __spec-mock.ts — 齿轮规格窗口组件测试的 mock spec 契约数据.
 * 仅用于 Vitest；不参与生产构建（位于 components/ 但不被 import 于业务代码）。
 * 遵循 SpecPayload 契约：params / single_tooth / outline.
 */
import type { SpecPayload } from '../api'

/** 构造确定性 mock spec（约 z=4 齿，便于数 path）. */
export function mockSpec(): SpecPayload {
  // 简化齿廓：一个 polyline 闭合 + 一个 arc（模拟齿顶圆角）
  return {
    params: {
      inputs: [
        { key: 'm_n', label: '法向模数', symbol: 'mn', value: 2.5, unit: 'mm' },
        { key: 'z_w', label: '工件齿数', symbol: 'zw', value: 4, unit: '' },
        { key: 'alpha_n_deg', label: '法向压力角', symbol: 'αn', value: 20, unit: '°' },
        { key: 'rho_tip', label: '齿顶倒圆系数', symbol: 'ρ*tip', value: 0, unit: '' },
      ],
      outputs: [
        { key: 'd_a', label: '齿顶圆直径', symbol: 'da', value: 107.5, unit: 'mm' },
        { key: 'd_f', label: '齿根圆直径', symbol: 'df', value: 96.25, unit: 'mm' },
        { key: 's_t', label: '分度圆弧齿厚', symbol: 'st', value: 3.927, unit: 'mm' },
      ],
    },
    single_tooth: {
      segments: [
        { type: 'polyline', points: [[50, 20], [50, -20], [44, -22], [44, 22], [50, 20]] },
        {
          type: 'arc',
          radius: 3,
          a0: 0,
          a1: Math.PI,
          center: [48, 0],
          clockwise: true,
        },
      ],
      // 连续三齿（开放链，三齿连成一体）——渲染主路径用
      neighborhood: [
        {
          type: 'polyline',
          points: [
            [44, 22],
            [50, 20],
            [50, -20],
            [44, -22],
            [38, -20],
            [38, 20],
            [44, 22],
          ],
        },
        {
          type: 'arc',
          radius: 3,
          a0: 0,
          a1: Math.PI,
          center: [48, 0],
          clockwise: true,
        },
      ],
      center_line: { from_angle_deg: -90, to_angle_deg: 90 },
      pitch_line: { r: 44 },
      annotations: {
        tooth_thickness: { value: 3.927, label: '齿厚', symbol: 's_t' },
        circular_pitch: { value: 7.854, label: '齿距', symbol: 'p_t' },
        tip_fillet: { value: 0.38, label: '齿顶倒圆', symbol: 'ρ_tip' },
        root_fillet: { value: 0, label: '齿根倒圆', symbol: 'ρ_f' },
        addendum: { value: 2.5, label: '齿顶高', symbol: 'h_a' },
        dedendum: { value: 3.125, label: '齿底高', symbol: 'h_f' },
        whole_depth: { value: 5.625, label: '齿全高', symbol: 'h' },
      },
    },
    outline: {
      points: [
        [50, 0],
        [46, 5],
        [42, 0],
      ],
      teeth: [
        [[50, 0], [46, 5], [42, 0], [50, 0]],
        [[-50, 0], [-46, -5], [-42, 0], [-50, 0]],
      ],
      circles: { tip_radius: 50, root_radius: 42, pitch_radius: 44, base_radius: 40 },
    },
  }
}
