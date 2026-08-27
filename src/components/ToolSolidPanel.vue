<script setup lang="ts">
/**
 * ToolSolidPanel.vue — 步骤3「刀具几何体」（TO-5 / PRD §4 表单骨架、§5 数据流契约）
 *
 * 三档披露表单（分组照抄设计书 §3.2 参数字典交互方式列）：
 *   ① 必填（平铺）：tool_type[锁 T7/T15] / z_t / β_t / j_t(segmented ±1) / rake_type[锁 W5] / L
 *   ② 可默认（默认收起，折叠态徽标显示当前值）：γ₀=5° / α₀=8°[注 W2 基线] / n_L=16 / flank_method[锁 T15]
 *   ③ 导出量（只读折叠，reactive 即时刷新）：Σ / a / r_pt / L_tp(导程) / p_z=L_tp/z_t
 *
 * 数据流契约（ADR-020）：
 *   - 零数值继承：刀具输入是自己的独立实例（useToolParams 每次 reactive 独立），
 *     只从 inject(gearParamsKey) 读工件参数做「校验区间联动 + 导出量联动」，绝不回写/预填
 *   - 手动生成（Q2-a）：toToolPayload 快照 vs 上次成功快照 → 不一致即按钮高亮「有待应用的变更」；
 *     请求期间禁用；错误就地展示（request() 统一抛 Error(message)，message 即仓库
 *     `{error, code}` JSON 契约里的 error 字段）
 *   - 成功替换 toolRing 图层：与 WorkpieceViewer.dispatchLayer 同一通道（window
 *     gear:layer-ready），MainView.addLayer 覆盖同 id 图层、LayerPanel.markLayerReady 重置可见性
 *   - 过期徽标（Q10-b）：监听工件生成成功事件 gear:model-ready（MainPanel.onModelReady 派发；
 *     注意与图层通道 gear:layer-ready 语义不同）→ 面板横幅 + useLayers.state.stale.toolRing
 *     （LayerPanel 圆点共用真值）。不强隐旧图，重新生成交给用户决定
 */
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import {
  fetchEnvelopeToolRing,
  type FlankRequest,
  type ToolRingResponse,
} from '../api'
import { gearParamsKey, toPayload } from '../composables/useGearParams'
import {
  LOCKED_FLANK_METHOD,
  LOCKED_FLANK_METHOD_NOTE,
  LOCKED_RAKE_TYPE,
  LOCKED_RAKE_TYPE_NOTE,
  LOCKED_TOOL_TYPE,
  LOCKED_TOOL_TYPE_NOTE,
  toToolPayload,
  useToolParams,
} from '../composables/useToolParams'
import {
  computeToolExportQuantities,
  type ExportWorkpieceContext,
} from '../composables/toolSolidExports'
import {
  TOOL_FIELD_RULES,
  collectHardErrors,
  validateToolField,
  type ToolFieldIssue,
  type ToolValidatableField,
} from '../composables/toolSolidValidation'
import { useLayers } from '../composables/useLayers'
import type { LayerId, LayerReadyDetail } from '../three/layerPalette'

// ── 工件参数注入：与 WorkpieceViewer 同一取数途径（MainPanel provide，inject 键相同） ──
const gearParams = inject(gearParamsKey)
if (!gearParams) {
  throw new Error('ToolSolidPanel: 必须在 MainPanel 中使用 (provide gearParams)')
}

// ── 刀具参数（本面板独立实例；schema/默认值/wire 映射全部来自 useToolParams 单一来源） ──
const toolParams = useToolParams()

// ── 过期标记写入 useLayers 单例（横幅与 LayerPanel 圆点共用同一真值，不另立状态） ──
const layers = useLayers()
const STALE_LAYER: LayerId = 'toolRing'

/** 锁定项常量的展示映射（模板用；理由文案含缺口编号，PRD §7 未销项引用纪律）. */
const lockedNotes = {
  tool_type: { value: LOCKED_TOOL_TYPE, note: LOCKED_TOOL_TYPE_NOTE },
  rake_type: { value: LOCKED_RAKE_TYPE, note: LOCKED_RAKE_TYPE_NOTE },
  flank_method: { value: LOCKED_FLANK_METHOD, note: LOCKED_FLANK_METHOD_NOTE },
} as const

/** 折叠状态：必填平铺展开，可默认/导出量默认收起（PRD §4 三档披露）. */
const expandedSections = ref<{ required: boolean; optional: boolean; derived: boolean }>({
  required: true,
  optional: false,
  derived: false,
})

type SectionKey = keyof typeof expandedSections.value

function toggleSection(section: SectionKey): void {
  expandedSections.value[section] = !expandedSections.value[section]
}

// ── 校验联动（PRD §5.2）────────────────────────────────────────
// 区间规则注册表在 toolSolidValidation.ts；这里只负责把「已触碰字段」与即时求值接起来：
//   黄警遵循 GearParamsPanel 的 @blur 节奏（blur 后才浮现）；
//   红错即时可见（按钮灰掉时用户必须看得到原因）；
//   文案数字来自注册表对当前 gearParams 的即时求值 → 改工件 → 区间文字立即变（Q9-B）。
const touchedFields = ref<Set<ToolValidatableField>>(new Set())

/** 当前是否应显示某字段的提示（undefined 表示无提示，模板里不渲染）. */
function issueOf(field: ToolValidatableField): ToolFieldIssue | undefined {
  const issue: ToolFieldIssue | null = validateToolField(field, toolParams, {
    z_w: gearParams!.z_w,
  })
  if (issue === null) return undefined
  if (issue.level === 'warn' && !touchedFields.value.has(field)) return undefined
  return issue
}

/** 字段级校验入口（@blur 触发；规则本体在 toolSolidValidation 注册表）. */
function validateField(field: ToolValidatableField): void {
  touchedFields.value.add(field)
}

/** 该字段是否工件依赖档（界面上打「随工件联动」小标签）. */
function isWorkpieceTier(field: ToolValidatableField): boolean {
  return TOOL_FIELD_RULES[field].tier === 'workpiece'
}

/** 是否有硬非法字段（阻断生成；黄警不在此列）. */
const hardErrors = computed<ToolValidatableField[]>(() =>
  collectHardErrors(toolParams, { z_w: gearParams!.z_w }),
)

// ── 工件会话依赖（只读投影；缺参时禁用生成而非代填） ──
const workpieceReady = computed<boolean>(() => {
  const p = gearParams!
  return (
    p.m_n !== null && Number.isFinite(p.m_n) && p.m_n > 0 &&
    p.z_w !== null && Number.isInteger(p.z_w) && p.z_w >= 1 &&
    p.b_w !== null && Number.isFinite(p.b_w) && p.b_w > 0
  )
})

// ── 导出量联动（PRD §5.3）：公式逐条抄写自 process_plan.py / tooth_solid.py，见 toolSolidExports ──
const exported = computed(() =>
  computeToolExportQuantities(toolParams, {
    z_w: gearParams!.z_w,
    m_n: gearParams!.m_n,
    beta_w_deg: gearParams!.β_w,
    j_w: gearParams!.j_w,
    k_io: gearParams!.k_io,
  } satisfies ExportWorkpieceContext),
)

/** 数值格式化：null → 「—」，其余按位数截断（mm 三位 / ° 两位）. */
function fmtNum(value: number | null, digits: number): string {
  if (value === null || !Number.isFinite(value)) return '—'
  return value.toFixed(digits)
}

// ── 待应用变更（Q2-a：快照对比高亮，非自动重生成） ──
/** 上一次成功生成时的 wire 快照（JSON 序列化）；null = 本面板尚未生成过整环. */
const lastAppliedSnapshot = ref<string | null>(null)

/** 当前表单对应的请求载荷快照（reactive：任一字段改动即重算）. */
function snapshotOf(payload: unknown): string {
  return JSON.stringify(payload)
}

const pendingChanges = computed<boolean>(
  () => lastAppliedSnapshot.value !== snapshotOf(toToolPayload(toolParams)),
)

// ── 过期徽标（Q10-b / PRD §5.4）──────────────────────────────
/** 工件重生成后置真（gear:model-ready）；整环重生成成功即清除. */
const workpieceStale = ref<boolean>(false)

/** 横幅仅在「本面板已生成过整环」之后才有意义——之前不存在任何会被过期的刀具，
 * 引导由按钮的「有待应用的变更」承担（mount 即收到首帧 gear:model-ready 不算过期）。 */
const staleBannerVisible = computed<boolean>(
  () => workpieceStale.value && lastAppliedSnapshot.value !== null,
)

function onWorkpieceModelReady(): void {
  workpieceStale.value = true
  layers.setLayerStale(STALE_LAYER, true)
}

onMounted(() => {
  window.addEventListener('gear:model-ready', onWorkpieceModelReady)
})

onUnmounted(() => {
  window.removeEventListener('gear:model-ready', onWorkpieceModelReady)
})

// ── 手动生成（PRD §3.1-2：一键 tool_ring 链路，结果替换 toolRing 图层旧内容） ──
const generating = ref<boolean>(false)
const generateError = ref<string | null>(null)

const canGenerate = computed<boolean>(
  () => workpieceReady.value && hardErrors.value.length === 0 && !generating.value,
)

async function generate(): Promise<void> {
  if (!canGenerate.value) return
  generating.value = true
  generateError.value = null
  try {
    const toolWire = toToolPayload(toolParams)
    const req: FlankRequest = {
      workpiece: toPayload(gearParams!),
      tool: toolWire.tool,
      resharpening: toolWire.resharpening,
      tool_type: toolWire.tool_type,       // T7/T15 锁定 cylindrical
      flank_method: toolWire.flank_method, // T15 锁定 helical_lead
    }
    const resp: ToolRingResponse = await fetchEnvelopeToolRing(req)

    // 图层替换走既有通道：MainView 收 gear:layer-ready 后 addLayer 同 id 覆盖旧内容，
    // LayerPanel 同步 markLayerReady；detail 形状 = layerPalette.LayerReadyDetail
    const detail: LayerReadyDetail = { id: STALE_LAYER, glbBase64: resp.layer.glb_base64 }
    window.dispatchEvent(new CustomEvent('gear:layer-ready', { detail }))

    // 成功：刷新快照（清除「有待应用的变更」高亮）+ 清除过期徽标（该层已基于当前工件参数重建）
    lastAppliedSnapshot.value = snapshotOf(toToolPayload(toolParams))
    workpieceStale.value = false
    layers.setLayerStale(STALE_LAYER, false)
  } catch (e: unknown) {
    // request() 已把 { error, code } 拆成 Error.message —— 就地展示（仓库既有消费惯例）
    generateError.value = e instanceof Error ? e.message : '整环生成失败'
  } finally {
    generating.value = false
  }
}

// 测试/调试探针（与 GearParamsPanel defineExpose 惯例一致）
defineExpose({
  expandedSections,
  pendingChanges,
  workpieceStale,
  staleBannerVisible,
  generateError,
  generate,
  toggleSection,
})
</script>

<template>
  <div class="tool-solid-panel">
    <!-- ⚠ 过期横幅（PRD §5.4：工件已变更 → 刀具基于旧工件参数；不强隐旧图） -->
    <div v-if="staleBannerVisible" class="stale-banner" data-test="stale-banner">
      ⚠ 工件已变更，刀具基于旧工件参数
    </div>

    <!-- ── ① 必填（平铺）── -->
    <div class="glass-collapse" :class="{ expanded: expandedSections.required }">
      <button class="glass-collapse-header" @click="toggleSection('required')">
        必填
        <span v-if="pendingChanges && expandedSections.required" class="collapse-badge dirty-badge" data-test="dirty-badge">
          有待应用的变更
        </span>
        <span class="glass-collapse-arrow">▶</span>
      </button>
      <div class="glass-collapse-content">
        <div class="collapse-inner">

          <!-- 刀型（锁定 cylindrical；T7/T15 缺口依据见 useToolParams 锁定常量） -->
          <div class="glass-field">
            <label class="glass-field-label">刀型</label>
            <select
              v-model="toolParams.tool_type"
              class="glass-select"
              data-test="tool-tool_type"
              :title="lockedNotes.tool_type.note"
              disabled
            >
              <option :value="lockedNotes.tool_type.value">圆柱型</option>
              <option value="conical" disabled>圆锥型（二期）</option>
            </select>
          </div>

          <!-- 刀具齿数（工件依赖校验档） -->
          <div class="glass-field">
            <label class="glass-field-label">
              刀具齿数 z_t <span v-if="isWorkpieceTier('z_t')" class="tier-tag" title="校验档位=工件依赖：推荐区间由工件齿数 z_w 即时派生">随工件</span>
            </label>
            <input
              v-model.number="toolParams.z_t"
              type="number"
              step="1"
              min="1"
              class="glass-input"
              :class="{ error: issueOf('z_t')?.level === 'error' }"
              @blur="validateField('z_t')"
            />
          </div>
          <p
            v-if="issueOf('z_t')"
            class="glass-field-hint"
            :class="{ warn: issueOf('z_t')!.level === 'warn' }"
          >{{ issueOf('z_t')!.message }}</p>

          <!-- 刀具螺旋角（工件依赖校验档）U12：界面 ° -->
          <div class="glass-field">
            <label class="glass-field-label">
              螺旋角 β_t
              <span v-if="isWorkpieceTier('beta_t')" class="tier-tag" title="校验档位=工件依赖（PRD §5.2）：区间随工件参数联动">随工件</span>
            </label>
            <input
              v-model.number="toolParams.beta_t"
              type="number"
              step="0.5"
              min="0"
              class="glass-input"
              :class="{ error: issueOf('beta_t')?.level === 'error' }"
              @blur="validateField('beta_t')"
            />
            <span class="unit-suffix">°</span>
          </div>
          <p
            v-if="issueOf('beta_t')"
            class="glass-field-hint"
            :class="{ warn: issueOf('beta_t')!.level === 'warn' }"
          >{{ issueOf('beta_t')!.message }}</p>

          <!-- 旋向 segmented ±1（U7：旋向独立于 β 数值携带） -->
          <div class="glass-field">
            <label class="glass-field-label">旋向 j_t</label>
            <div class="glass-segmented">
              <button
                class="glass-segmented-btn"
                :class="{ active: toolParams.j_t === -1 }"
                data-test="tool-j-t-neg"
                @click="toolParams.j_t = -1"
              >左旋 (−1)</button>
              <button
                class="glass-segmented-btn"
                :class="{ active: toolParams.j_t === 1 }"
                data-test="tool-j-t-pos"
                @click="toolParams.j_t = 1"
              >右旋 (+1)</button>
            </div>
          </div>

          <!-- 前刀面形式（锁定 plane；W5 锥面 ±/∓ 分支未决） -->
          <div class="glass-field">
            <label class="glass-field-label">前刀面形式</label>
            <select
              v-model="toolParams.rake_type"
              class="glass-select"
              data-test="tool-rake_type"
              :title="lockedNotes.rake_type.note"
              disabled
            >
              <option :value="lockedNotes.rake_type.value">平面</option>
              <option value="cone" disabled>锥面（未实现）</option>
              <option value="equation" disabled>方程（未实现）</option>
            </select>
          </div>

          <!-- 刀齿轴向长度 = 总重磨量（pydantic ResharpenParams.L > 0） -->
          <div class="glass-field">
            <label class="glass-field-label">刀齿长度 L</label>
            <input
              v-model.number="toolParams.L"
              type="number"
              step="1"
              min="0.1"
              class="glass-input"
              :class="{ error: issueOf('L')?.level === 'error' }"
              @blur="validateField('L')"
            />
            <span class="unit-suffix">mm</span>
          </div>
          <p
            v-if="issueOf('L')"
            class="glass-field-hint"
            :class="{ warn: issueOf('L')!.level === 'warn' }"
          >{{ issueOf('L')!.message }}</p>

        </div>
      </div>
    </div>

    <!-- ── ② 可默认（默认收起；折叠态徽标显示当前值——披露视觉位，不是空表单等待填写） ── -->
    <div class="glass-collapse" :class="{ expanded: expandedSections.optional }">
      <button class="glass-collapse-header" @click="toggleSection('optional')">
        可默认
        <span v-if="!expandedSections.optional" class="collapse-badge" data-test="optional-defaults-badge">
          γ₀ {{ toolParams.gamma_0 }}° · α₀ {{ toolParams.alpha_0 }}° · n_L {{ toolParams.n_L }} · 螺旋导程法
        </span>
        <span class="glass-collapse-arrow">▶</span>
      </button>
      <div class="glass-collapse-content">
        <div class="collapse-inner">

          <!-- 设计前角（K-2.1 前刀面输入；设计书 §3.2 默认 5°） -->
          <div class="glass-field">
            <label class="glass-field-label">前角 γ₀</label>
            <input
              v-model.number="toolParams.gamma_0"
              type="number"
              step="0.5"
              class="glass-input"
              :class="{ error: issueOf('gamma_0')?.level === 'error' }"
              @blur="validateField('gamma_0')"
            />
            <span class="unit-suffix">°</span>
          </div>

          <!-- 顶刃后角：默认 8 出自算例2 表1；算例1 的 6° 系 W2 反推假设（正文确认待做，勿当定论） -->
          <div class="glass-field">
            <label class="glass-field-label">
              后角 α₀
              <span
                data-test="alpha-0-note"
                class="tier-tag note-marker"
                title="8° 基线出处=算例2；算例1 的 6° 属 W2 反推假设待销项"
              >i</span>
            </label>
            <input
              v-model.number="toolParams.alpha_0"
              type="number"
              step="0.5"
              class="glass-input"
              :class="{ error: issueOf('alpha_0')?.level === 'error' }"
              @blur="validateField('alpha_0')"
            />
            <span class="unit-suffix">°</span>
          </div>

          <!-- 重磨等分数（设计书 §3.2 典型 ≥5 → n_L&lt;5 给黄警） -->
          <div class="glass-field">
            <label class="glass-field-label">重磨等分 n_L</label>
            <input
              v-model.number="toolParams.n_L"
              type="number"
              step="1"
              min="1"
              class="glass-input"
              :class="{ error: issueOf('n_L')?.level === 'error' }"
              @blur="validateField('n_L')"
            />
          </div>
          <p
            v-if="issueOf('n_L')"
            class="glass-field-hint"
            :class="{ warn: issueOf('n_L')!.level === 'warn' }"
          >{{ issueOf('n_L')!.message }}</p>

          <!-- 后刀面算法（锁定 helical_lead；T15：轴向偏移法 K-2.17 / z_off 字段均缺） -->
          <div class="glass-field">
            <label class="glass-field-label">后刀面算法</label>
            <select
              v-model="toolParams.flank_method"
              class="glass-select"
              data-test="tool-flank_method"
              :title="lockedNotes.flank_method.note"
              disabled
            >
              <option :value="lockedNotes.flank_method.value">螺旋导程法</option>
              <option value="axial_offset" disabled>轴向偏移法（二期）</option>
            </select>
          </div>

        </div>
      </div>
    </div>

    <!-- ── ③ 导出量（只读折叠；随工件+刀具参数 reactive 即时刷新，公式出处见 toolSolidExports.ts） ── -->
    <div class="glass-collapse" :class="{ expanded: expandedSections.derived }">
      <button class="glass-collapse-header" @click="toggleSection('derived')">
        导出量
        <span v-if="!expandedSections.derived" class="collapse-badge" data-test="derived-sigma-badge">
          Σ {{ fmtNum(exported.sigma_deg, 2) }}°
        </span>
        <span class="glass-collapse-arrow">▶</span>
      </button>
      <div class="glass-collapse-content">
        <div class="collapse-inner derived-grid">
          <div class="derived-row">
            <span class="derived-name">轴交角 Σ</span>
            <span class="derived-value" data-test="exp-sigma">{{ fmtNum(exported.sigma_deg, 2) }} °</span>
            <span class="derived-src">K-1.4</span>
          </div>
          <div class="derived-row">
            <span class="derived-name">中心距 a</span>
            <span class="derived-value" data-test="exp-a">{{ fmtNum(exported.a_mm, 3) }} mm</span>
            <span class="derived-src">K-1.5/1.6</span>
          </div>
          <div class="derived-row">
            <span class="derived-name">节圆半径 r_pt</span>
            <span class="derived-value" data-test="exp-r-pt">{{ fmtNum(exported.r_pt_mm, 3) }} mm</span>
            <span class="derived-src">K-1.6</span>
          </div>
          <div class="derived-row">
            <span class="derived-name">螺旋导程 L_tp</span>
            <span class="derived-value" data-test="exp-lead">{{ fmtNum(exported.lead_mm, 3) }} mm</span>
            <span class="derived-src">K-2.15</span>
          </div>
          <div class="derived-row">
            <span class="derived-name">错位步距 p_z</span>
            <span class="derived-value" data-test="exp-pitch-z">{{ fmtNum(exported.pitch_z_mm, 3) }} mm</span>
            <span class="derived-src">K-2.15/L_tp÷z_t</span>
          </div>
          <p v-if="!workpieceReady" class="glass-field-hint">先在步骤1 填齐 m_n / z_w / b_w 后节圆与中心距方可联动</p>
        </div>
      </div>
    </div>

    <!-- ── 手动生成（Q2-a：无自动重生成；快照不一致仅高亮，不强隐旧图、不打扰用户） ── -->
    <button
      class="glass-btn generate-btn"
      :class="{ dirty: pendingChanges }"
      type="button"
      data-test="generate-tool-ring"
      :disabled="!canGenerate"
      @click="generate"
    >
      {{ generating ? '生成中…' : '生成完整刀具体' }}
    </button>
    <span v-if="pendingChanges && !generating" class="pending-hint" data-test="pending-hint">有待应用的变更</span>

    <p v-if="!workpieceReady" class="glass-field-hint blocked-hint" data-test="workpiece-missing-hint">
      请先在步骤1 填写模数 m_n、齿数 z_w、齿宽 b_w
    </p>

    <!-- 请求失败就地展示：request() 把仓库契约 { "error", "code" } 的 error 字段拆成 message -->
    <div v-if="generateError" class="generate-error" data-test="generate-error">{{ generateError }}</div>
  </div>
</template>

<style scoped>
.tool-solid-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.collapse-inner {
  padding: 4px 4px 4px 12px;
}

/* 折叠标题右侧的小徽标（可默认组的当前值 / 必填组的待应用提示） */
.collapse-badge {
  font-size: 10px;
  font-weight: 500;
  color: var(--brand-text-secondary);
  background: rgba(0, 96, 160, 0.08);
  border-radius: 8px;
  padding: 1px 8px;
  margin-left: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 170px;
}

.dirty-badge {
  color: #b25c00;
  background: rgba(230, 126, 34, 0.14);
}

/* 工件依赖小标签 / 说明角标 */
.tier-tag {
  font-size: 9px;
  font-weight: 400;
  color: var(--brand-blue);
  background: rgba(0, 96, 160, 0.10);
  border-radius: 6px;
  padding: 0 4px;
  cursor: help;
}

.note-marker {
  font-style: italic;
  font-weight: 600;
}

.unit-suffix {
  font-size: 10px;
  color: var(--brand-text-secondary);
  flex-shrink: 0;
}

/* 黄警沿用 Glass 视觉语言但取警告橙（区别于 .glass-field-hint 默认的危险红） */
.glass-field-hint.warn {
  color: var(--brand-warning);
}

/* 生成按钮：dirty 时叠加琥珀描边光晕提示「有待应用的变更」，不改基础按钮形状 */
.generate-btn.dirty:not(:disabled) {
  background: var(--brand-blue);
  box-shadow:
    0 0 0 2px rgba(230, 126, 34, 0.55),
    0 2px 10px rgba(230, 126, 34, 0.28);
}

.pending-hint {
  align-self: center;
  font-size: 10px;
  color: var(--brand-warning);
}

.blocked-hint {
  text-align: center;
}

.generate-error {
  color: var(--brand-danger);
  font-size: 11px;
  line-height: 1.4;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(192, 57, 43, 0.08);
  border: 1px solid rgba(192, 57, 43, 0.22);
}

.stale-banner {
  font-size: 11px;
  line-height: 1.45;
  color: #a85900;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(230, 126, 34, 0.14);
  border: 1px solid rgba(230, 126, 34, 0.32);
}

/* 导出量只读行：名称 / 数值 / 公式来源三段式，tabular 数字避免跳动 */
.derived-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.derived-row {
  display: grid;
  grid-template-columns: minmax(84px, auto) 1fr auto;
  column-gap: 8px;
  align-items: baseline;
}

.derived-name {
  font-size: 11px;
  color: var(--brand-text-secondary);
  white-space: nowrap;
}

.derived-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--brand-text);
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.derived-src {
  font-size: 9px;
  color: var(--brand-text-secondary);
  opacity: 0.75;
  white-space: nowrap;
}
</style>
