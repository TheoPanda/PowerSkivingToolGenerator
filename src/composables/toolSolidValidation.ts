/**
 * toolSolidValidation.ts — 步骤3 刀具参数的区间规则注册表（TO-5 / PRD §5.2 校验联动）
 *
 * 两档语义（PRD §5.2）：
 *   - warn  = 黄色建议性警告：推荐/典型区间越界，不阻断提交（生成按钮仍可用）
 *   - error = 硬非法：与后端 pydantic Field 的硬约束同源（z_t ge=1 整数、β_t ge=0、
 *             L gt=0、n_L ge=1），红错并禁用「生成完整刀具体」按钮
 *
 * tier 分档：
 *   - workpiece = 工件依赖项：区间由 inject(gearParamsKey) 派生即时联动（Q9-B 裁决；
 *     ADR-020① 零数值继承不受影响——只读工件参数算区间，从不回写、从不预填刀具值）。
 *   - static    = 静态项：只对自身取值判定，不碰工件会话。
 *
 * 文案权源纪律（PRD §7）：区间数字全部来自设计书第3章 参数字典 §3.2 典型范围列或
 * 后端 pydantic 硬约束；W15 属「工程默认值（非文献）：楔角最小阈值、角度工艺窗口」，
 * 未销项——凡引用 W15 的文案必须保持「文献典型值/建议参考」措辞，不得宣称工艺安全边界。
 */
import type { ToolParamsState } from './useToolParams'

/** 校验级别：warn=黄警（建议性）/ error=红错（阻断）. */
export type ToolFieldIssueLevel = 'warn' | 'error'

/** 单字段单条校验结论. */
export interface ToolFieldIssue {
  level: ToolFieldIssueLevel
  /** 展示给用户的中文文案（含数值与出处/缺口编号引用）. */
  message: string
}

/** 可校验字段 = 必填+可默认两组中带自由输入的项；tool_type/rake_type/flank_method 已锁定，无自由度。 */
export type ToolValidatableField =
  | 'z_t'
  | 'beta_t'
  | 'gamma_0'
  | 'alpha_0'
  | 'L'
  | 'n_L'

/** 工件依赖档的取数上下文：ToolSolidPanel 以 inject(gearParamsKey) 投影传入.
 * z_w 为 null 表示工件参数尚未填写 → 区间不可知，不做黄警（只做硬校验）。 */
export interface ToolWorkpieceContext {
  z_w: number | null
}

/** 单字段规则声明. */
export interface ToolFieldRule {
  /** 是否工件依赖档（PRD §5.2 两档；面板据此在界面上标注「随工件联动」）. */
  tier: 'workpiece' | 'static'
  /** 纯函数：返回首个命中的 issue 或 null（调用方无需再分类）。 */
  check(params: ToolParamsState, workpiece: ToolWorkpieceContext | null): ToolFieldIssue | null
}

// ── 区间常量（设计书第3章 §3.2 典型范围列；供界面占位/文案复用） ──

/** z_t 推荐比区间：z_t/z_w ≈ 0.5~0.67（§3.2「文献算例：41/82、68/102」）. */
export const RECOMMENDED_ZT_RATIO: { lo: number; hi: number } = { lo: 0.5, hi: 0.67 }

/** β_t 典型区间 [°]（§3.2「10~20；算例1=15，算例2=15」）. */
export const TYPICAL_BETA_T_RANGE: { lo: number; hi: number } = { lo: 10, hi: 20 }

/** n_L 建议下限（§3.2「≥5」，[21] 步骤(6)；过粗截面呈折面棱线——仅建议非硬约束）. */
const NL_SUGGESTED_MIN = 5

/** 工件齿数合法（用于决定是否展示工件依赖区间）的门槛：正整数. */
function usableZW(z_w: number | null): boolean {
  return z_w !== null && Number.isFinite(z_w) && Number.isInteger(z_w) && z_w >= 1
}

/** 区间格式化（黄警文案统一两位有效显示，避免 54.940000000000005 这类浮点尾巴）. */
function fmtRange(lo: number, hi: number): string {
  const round = (v: number): string => (Number.isInteger(v) ? String(v) : v.toFixed(1))
  return `${round(lo)}~${round(hi)}`
}

/**
 * 区间规则注册表（字段名 → 规则；纯数据 + 纯函数，可整体单测）.
 */
export const TOOL_FIELD_RULES: Record<ToolValidatableField, ToolFieldRule> = {
  // ── 工件依赖档 ─────────────────────────────────────────────────
  z_t: {
    tier: 'workpiece',
    check(params, w) {
      const z_t = params.z_t
      if (!Number.isInteger(z_t) || !Number.isFinite(z_t) || z_t < 1) {
        // pydantic ToolParams.z_t: int ≥ 1
        return { level: 'error', message: '刀具齿数必须为正整数' }
      }
      if (!usableZW(w?.z_w ?? null)) return null // 工件未定 → 区间不可知不算违规
      const zw = w!.z_w as number
      const lo = RECOMMENDED_ZT_RATIO.lo * zw
      const hi = RECOMMENDED_ZT_RATIO.hi * zw
      if (z_t < lo || z_t > hi) {
        return {
          level: 'warn',
          message:
            `设计书推荐 z_t ≈ ${fmtRange(lo, hi)}（≈0.5~0.67×z_w=${zw}）；` +
            '仅供斟酌，不影响生成',
        }
      }
      return null
    },
  },
  beta_t: {
    // 评审 C2 修正：β_t 归静态档——[10,20]° 是设计书文献典型值，与工件参数无关；
    // 与工件侧的 Σ 耦合按 Q9-C 落位「导出量」组展示（W15 工艺窗口未销项，刻意不设校验约束）
    tier: 'static',
    check(params) {
      const b = params.beta_t
      if (!Number.isFinite(b) || b < 0) {
        // pydantic beta_t_deg ≥ 0；U7 螺旋角数值恒≥0（旋向由 j_t 携带）
        return { level: 'error', message: '刀具螺旋角必须 ≥ 0°（U7：旋向由 j_t 表达）' }
      }
      const { lo, hi } = TYPICAL_BETA_T_RANGE
      if (b < lo || b > hi) {
        return {
          level: 'warn',
          message:
            `β_t 典型 ${lo}~${hi}°（设计书 §3.2 文献典型值）；楔角/角度工艺窗口属 W15 ` +
            '工程默认值未销项，不作工艺安全边界断言',
        }
      }
      return null
    },
  },
  // ── 静态档 ─────────────────────────────────────────────────────
  gamma_0: {
    tier: 'static',
    check(params) {
      if (!Number.isFinite(params.gamma_0)) {
        return { level: 'error', message: '设计前角 γ₀ 必须为有限数值' }
      }
      return null // 设计书 §3.2 仅给默认 5°，无区间断言权源 → 不造黄警
    },
  },
  alpha_0: {
    tier: 'static',
    check(params) {
      if (!Number.isFinite(params.alpha_0)) {
        return { level: 'error', message: '顶刃后角 α₀ 必须为有限数值' }
      }
      return null // α₀ 基线本身是 W2 待销项（6° vs 8°），更无依据设区间
    },
  },
  L: {
    tier: 'static',
    check(params) {
      if (!Number.isFinite(params.L) || params.L <= 0) {
        // pydantic ResharpenParams.L: float > 0
        return { level: 'error', message: '刀齿轴向长度 L 必须 > 0 mm' }
      }
      return null // 「按刀体设计」（§3.2）无文献区间
    },
  },
  n_L: {
    tier: 'static',
    check(params) {
      const n = params.n_L
      if (!Number.isInteger(n) || !Number.isFinite(n) || n < 1) {
        // pydantic n_L: int ≥ 1
        return { level: 'error', message: '重磨等分数 n_L 必须为正整数' }
      }
      if (n < NL_SUGGESTED_MIN) {
        return {
          level: 'warn',
          message: `截面过疏呈折面棱线：n_L 建议 ≥ ${NL_SUGGESTED_MIN}（设计书 §3.2 / [21] 步骤(6)）`,
        }
      }
      return null
    },
  },
}

/** 单字段校验入口（工具面板 validateField @blur 与提交门禁共用同一注册表，无双份规则）. */
export function validateToolField(
  field: ToolValidatableField,
  params: ToolParamsState,
  workpiece: ToolWorkpieceContext | null,
): ToolFieldIssue | null {
  return TOOL_FIELD_RULES[field].check(params, workpiece)
}

/** 全部可校验字段的 issue 一览（每字段至多一条：规则内按 硬非法→建议 顺序短路）.
 * 模块内私有——对外只暴露 validateToolField / collectHardErrors / isToolParamsSubmittable。 */
function evaluateAllFields(
  params: ToolParamsState,
  workpiece: ToolWorkpieceContext | null,
): Record<ToolValidatableField, ToolFieldIssue | null> {
  const result = {} as Record<ToolValidatableField, ToolFieldIssue | null>
  for (const field of Object.keys(TOOL_FIELD_RULES) as ToolValidatableField[]) {
    result[field] = TOOL_FIELD_RULES[field].check(params, workpiece)
  }
  return result
}

/** 红错字段清单（面板用它禁用生成按钮 + 决定哪些错误提示即时可见）. */
export function collectHardErrors(
  params: ToolParamsState,
  workpiece: ToolWorkpieceContext | null,
): ToolValidatableField[] {
  const all = evaluateAllFields(params, workpiece)
  return (Object.keys(all) as ToolValidatableField[]).filter(
    (f) => all[f]?.level === 'error',
  )
}

/** 提交门禁：无任何红错即可生成（黄警只展示不阻断 —— PRD §5.2）. */
export function isToolParamsSubmittable(
  params: ToolParamsState,
  workpiece: ToolWorkpieceContext | null,
): boolean {
  return collectHardErrors(params, workpiece).length === 0
}
