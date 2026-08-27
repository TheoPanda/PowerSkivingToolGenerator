/**
 * useToolParams.ts — 刀具参数（ToolParams）单一模块（TO-2 / PRD §3.1-6）
 *
 * 此前刀具参数表单在 WorkpieceViewer.vue 内联 reactive，payload 组装散在
 * runEnvelope 三处（tool 段 / rake_type / resharpening+tool_type+flank_method），
 * 与后端 pydantic Field 双份并存。此处收拢为唯一 schema：
 * 类型 + 默认值 + 到后端 wire 格式的映射 —— 表单、步骤2/3 面板、API 客户端都从此派生。
 *
 * 默认值唯一权威＝backend/core/envelope/router.py 的 pydantic Field
 * （ToolParams L36-43 / ResharpenParams L490 / RakeRequest L512 / FlankRequest L512）；
 * 唯 j_t 后端默认 +1，前端按算例1 内齿轮取 −1 显式传参覆盖（左旋 → Σ=+15°）。
 *
 * 锁定项常量供三档披露表单的「显示但锁死」控件与 TO-5 复用；
 * 理由文案一律带缺口编号并保持「待销项后开放」措辞（PRD §7 未销项引用纪律）。
 * δ（轴倾角）/ z_off（轴向偏移）刻意不建字段：后端 schema 本无此字段，
 * 且依赖 T15（圆锥变位族 K-2.14 / 轴向偏移法 K-2.17）。
 */
import { reactive } from 'vue'

// ── 选项字面量联合（与 src/api/index.ts 同名 wire 类型形状一致，结构化兼容免 cast） ──

/** 刀型选项：v1 仅 cylindrical 可用（conical 二期，T7/T15 锁定）. */
export type ToolTypeChoice = 'cylindrical' | 'conical'

/** 前刀面形式选项：仅 plane 可用（equation 未实现；cone 系 W5 未决分支）. */
export type RakeTypeChoice = 'plane' | 'equation' | 'cone'

/** 后刀面算法选项：仅 helical_lead 可用（axial_offset 二期，T15 锁定）. */
export type FlankMethodChoice = 'helical_lead' | 'axial_offset'

/**
 * 刀具参数表单 schema（10 字段；camelCase 领域名，wire 映射见 toToolPayload）.
 *
 * 不叫 ToolParams：该名已被 src/api/index.ts 的 wire 接口占用，避免双义。
 */
export interface ToolParamsState {
  z_t: number        // 刀具齿数（前端无 pydantic 默认可抄——必填字段，锚算例1 工件 z_w=82）
  beta_t: number     // 刀具螺旋角 β_t [°]（必填，锚算例1 =15）
  j_t: number        // 刀具旋向 ±1（pydantic 默认 +1；此处按算例1 显式传 −1）
  gamma_0: number    // 设计前角 γ₀ [°]（K-2.1 前刀面输入）
  alpha_0: number    // 顶刃后角 α₀ [°]（K-2.18 径向重磨分量）
  rake_type: RakeTypeChoice          // 前刀面形式（锁定 plane，W5）
  tool_type: ToolTypeChoice          // 刀型（锁定 cylindrical，T7/T15）
  flank_method: FlankMethodChoice    // 后刀面算法（锁定 helical_lead，T15）
  L: number          // 刀齿轴向长度（总重磨量）[mm]
  n_L: number        // 重磨等分数（后刀面扫掠截面数）
}

// ── 锁定项元数据（TO-5 三档披露表单复用；文案带缺口编号，PRD §7 纪律） ──

/** 锁定刀型：圆柱型。锥形第三分支未回读 [13] let-off 细节（T7），且依赖 K-2.14 变位族（T15），待销项后开放。 */
export const LOCKED_TOOL_TYPE: ToolTypeChoice = 'cylindrical'
export const LOCKED_TOOL_TYPE_NOTE =
  '锥形刀依赖 T7/T15（let-off 细节未回读 / K-2.14 变位族未实现），待销项后开放'

/** 锁定前刀面形式：平面。[14] 式(2) ±/∓ 符号分支未决（W5 → K-2.4 锥面前刀面），待销项后开放。 */
export const LOCKED_RAKE_TYPE: RakeTypeChoice = 'plane'
export const LOCKED_RAKE_TYPE_NOTE =
  '锥面前刀面的 ±/∓ 符号分支未决（W5），待销项后开放'

/** 锁定后刀面算法：螺旋导程法。轴向偏移法 K-2.17 属 T15（需产形面链与 z_off 字段），待销项后开放。 */
export const LOCKED_FLANK_METHOD: FlankMethodChoice = 'helical_lead'
export const LOCKED_FLANK_METHOD_NOTE =
  '轴向偏移法属 T15（K-2.17 / z_off 字段均缺），待销项后开放'

/**
 * 默认参数 = 算例1 全套基线，唯 α₀=8 出自算例2（表1）；
 * 算例1 文献值 6° 系 W2 反推假设输入，正文确认待做，故维持 pydantic 同值的 8。
 */
export function createToolParams(): ToolParamsState {
  return {
    z_t: 41,               // 匹配算例1 内齿轮 z_w=82（z_w/z_t=2）；端到端 demo 基线
    beta_t: 15,            // Σ=β_w+β_t=0+15（K-1.4 内齿轮旋向相反规则）
    j_t: -1,               // 左旋（内齿轮旋向相反 → Σ 取正）
    gamma_0: 5,            // = pydantic gamma_0_deg 5.0
    alpha_0: 8,            // = pydantic alpha_0_deg 8.0（基线出处=算例2；算例1 的 6° 见 W2）
    rake_type: LOCKED_RAKE_TYPE,
    tool_type: LOCKED_TOOL_TYPE,
    flank_method: LOCKED_FLANK_METHOD,
    L: 20,                 // = ResharpenParams.L 20.0：≈工件齿宽量级，过小实体呈薄片
    n_L: 16,               // = ResharpenParams.n_L 16：间距 20/16=1.25mm
  }
}

// ── wire 形状（snake_case，与 POST /api/envelope/* 请求体对齐） ──

/** 刀具段 wire 载荷（ToolParams / RakeRequest.tool / FlankRequest.tool 共用）. */
export interface ToolWireParams {
  z_t: number
  beta_t_deg: number
  j_t: number
  gamma_0_deg: number
  alpha_0_deg: number
}

/** 重磨段 wire 载荷（ResharpenParams）. */
export interface ResharpenWireParams {
  L: number
  n_L: number
}

/**
 * toToolPayload 输出：组件把各分片放到对应请求体的原嵌套位 ——
 * EnvelopeRequest.tool ← tool；RakeRequest.rake_type ← rake_type；
 * FlankRequest.{resharpening, tool_type, flank_method} ← 同名字段。
 */
export interface ToolWirePayload {
  tool: ToolWireParams
  rake_type: RakeTypeChoice
  resharpening: ResharpenWireParams
  tool_type: ToolTypeChoice
  flank_method: FlankMethodChoice
}

/** 组件本地状态便捷入口：每次独立实例（步骤2/3 各持己态，零数值继承见 ADR-020）。 */
export function useToolParams(): ToolParamsState {
  return reactive<ToolParamsState>(createToolParams())
}

/** 领域参数 → snake_case 后端载荷（β_t/γ₀/α₀ 度数直传，界面 °/内核 rad 换算在后端 U12）. */
export function toToolPayload(p: ToolParamsState): ToolWirePayload {
  return {
    tool: {
      z_t: p.z_t,
      beta_t_deg: p.beta_t,
      j_t: p.j_t,
      gamma_0_deg: p.gamma_0,
      alpha_0_deg: p.alpha_0,
    },
    rake_type: p.rake_type,
    resharpening: { L: p.L, n_L: p.n_L },
    tool_type: p.tool_type,
    flank_method: p.flank_method,
  }
}
