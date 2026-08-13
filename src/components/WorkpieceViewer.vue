<script setup lang="ts">
/**
 * WorkpieceViewer.vue — 步骤2：工件齿轮生成 + 包络计算
 *
 * - 挂载即调用 fetchWorkpiece 生成齿轮 GLB（模块①，结果/spec 写全局单例）
 * - 「包络计算」区块：输入刀具参数 → 依次调 generatrix / edge 端点（子 PRD-2
 *   离散包络），经 gear:layer-ready 事件叠加产形面 / 刃形两图层
 * - 诊断条显示 ffα 与覆盖判据（成功绿勾 / 失败红叉）
 */
import { ref, inject, onMounted, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchWorkpiece,
  fetchEnvelopeGeneratrix,
  fetchEnvelopeEdge,
  type CoverageReport,
} from '../api'
import type { LayerReadyDetail } from '../three/layerPalette'
import { gearParamsKey, toPayload } from '../composables/useGearParams'
import { setWorkpieceResult } from '../composables/useWorkpieceState'

// ── 从 MainPanel 注入 gearParams（类型化键） ──
const gearParams = inject(gearParamsKey)
if (!gearParams) throw new Error('WorkpieceViewer: gearParams not provided')

// ── 工件生成状态 ──
const generating = ref<boolean>(false)
const glbBase64 = ref<string | null>(null)
const error = ref<string | null>(null)

// ── 包络计算状态 ──
const toolParams = reactive({
  z_t: 41,        // 默认匹配算例1 内齿轮 z_w=82（端到端 demo）
  beta_t: 15,
  j_t: -1,        // 左旋 → Σ=+15°（内齿轮旋向相反）
  gamma_0: 5,     // 前角（保留位，MVP 忽略）
  alpha_0: 8,     // 后角（保留位，MVP 忽略）
})
const envelopeRunning = ref<boolean>(false)
const envelopeError = ref<string | null>(null)
const ffaUm = ref<number | null>(null)
const coverageReport = ref<CoverageReport | null>(null)

/** 覆盖率百分比（诊断条展示）. */
const coveragePercent = computed<number | null>(() => {
  if (!coverageReport.value) return null
  return Math.round(coverageReport.value.coverage_ratio * 100)
})

/** 诊断条总体通过（ffα < 0.1μm 且覆盖 100%）. */
const envelopePassed = computed<boolean>(() => {
  if (ffaUm.value === null || coverageReport.value === null) return false
  return ffaUm.value < 0.1 && coverageReport.value.pass
})

// ── 事件 ──
const emit = defineEmits<{
  'model-ready': [glbBase64: string]
}>()

// ── 挂载时自动生成 ──
onMounted(() => {
  generate()
})

// ── 工件生成（模块①） ──
async function generate(): Promise<void> {
  generating.value = true
  error.value = null

  try {
    const response = await fetchWorkpiece(gearParams!)
    glbBase64.value = response.model_glb_base64
    setWorkpieceResult(response.result, response.spec)
    emit('model-ready', response.model_glb_base64)
    ElMessage.success('齿轮模型已生成')
  } catch (e: unknown) {
    const msg: string = e instanceof Error ? e.message : '生成失败'
    error.value = msg
    ElMessage.error(msg)
  } finally {
    generating.value = false
  }
}

// ── 派发包络图层到视口（经 gear:layer-ready 事件） ──
function dispatchLayer(id: 'generatrix' | 'edge', glbBase64: string): void {
  const detail: LayerReadyDetail = { id, glbBase64 }
  window.dispatchEvent(new CustomEvent('gear:layer-ready', { detail }))
}

// ── 包络计算（子 PRD-2 离散包络：产形面 → 刃形） ──
async function runEnvelope(): Promise<void> {
  if (gearParams!.m_n === null || gearParams!.z_w === null) {
    ElMessage.warning('请先在步骤1 填写法向模数 m_n 与工件齿数 z_w')
    return
  }
  envelopeRunning.value = true
  envelopeError.value = null
  ffaUm.value = null
  coverageReport.value = null

  try {
    const req = {
      workpiece: toPayload(gearParams!),
      tool: {
        z_t: toolParams.z_t,
        beta_t_deg: toolParams.beta_t,
        j_t: toolParams.j_t,
        gamma_0_deg: toolParams.gamma_0,
        alpha_0_deg: toolParams.alpha_0,
      },
      // discretization 缺省 → 后端默认 n=200/m=181/NR=200/θ=±20°
    }

    // 产形面（先叠加）
    const gen = await fetchEnvelopeGeneratrix(req)
    dispatchLayer('generatrix', gen.layer.glb_base64)

    // 刃形（后叠加）+ 诊断
    const edgeResp = await fetchEnvelopeEdge(req)
    dispatchLayer('edge', edgeResp.layer.glb_base64)
    ffaUm.value = edgeResp.ffa_um
    coverageReport.value = edgeResp.coverage_report

    ElMessage.success('包络计算完成')
  } catch (e: unknown) {
    const msg: string = e instanceof Error ? e.message : '包络计算失败'
    envelopeError.value = msg
    ElMessage.error(msg)
  } finally {
    envelopeRunning.value = false
  }
}
</script>

<template>
  <div class="workpiece-viewer">
    <!-- 工件生成加载状态 -->
    <div v-if="generating" class="generating-hint">
      <span class="spinner"></span>
      正在生成齿轮模型...
    </div>

    <!-- 工件生成错误 -->
    <div v-if="error" class="error-msg">
      {{ error }}
      <button class="glass-btn retry-btn" @click="generate">重试</button>
    </div>

    <!-- 包络计算（子 PRD-2 离散包络） -->
    <div class="envelope-section">
      <div class="section-title">包络计算</div>

      <div class="tool-params">
        <label class="param-field">
          <span class="param-label">刀具齿数 z_t</span>
          <input v-model.number="toolParams.z_t" type="number" class="glass-input" data-test="tool-z_t" />
        </label>
        <label class="param-field">
          <span class="param-label">刀具螺旋角 β_t (°)</span>
          <input v-model.number="toolParams.beta_t" type="number" class="glass-input" data-test="tool-beta_t" />
        </label>
        <label class="param-field">
          <span class="param-label">刀具旋向 j_t</span>
          <select v-model.number="toolParams.j_t" class="glass-input" data-test="tool-j_t">
            <option :value="-1">左旋 (−1)</option>
            <option :value="1">右旋 (+1)</option>
          </select>
        </label>
      </div>

      <button
        class="glass-btn"
        type="button"
        data-test="run-envelope"
        :disabled="envelopeRunning"
        @click="runEnvelope"
      >
        {{ envelopeRunning ? '包络计算中…' : '开始包络' }}
      </button>

      <div v-if="envelopeError" class="error-msg">{{ envelopeError }}</div>

      <!-- 诊断条：ffα + 覆盖判据 -->
      <div v-if="ffaUm !== null" class="diagnostic-strip" :class="{ failed: !envelopePassed }" data-test="diagnostic-strip">
        <span class="diag-item" :class="ffaUm < 0.1 ? 'ok' : 'bad'">
          <span class="diag-dot"></span>
          ffα = {{ ffaUm.toFixed(3) }} μm
        </span>
        <span class="diag-item" :class="coverageReport?.pass ? 'ok' : 'bad'">
          <span class="diag-dot"></span>
          覆盖 {{ coveragePercent ?? '—' }}%
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workpiece-viewer {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.generating-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 13px;
  color: var(--brand-text-secondary, #5C6B7A);
  padding: 8px 0;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-msg {
  color: var(--brand-danger, #C0392B);
  font-size: 12px;
  text-align: center;
}

.retry-btn {
  margin-left: 8px;
  padding: 2px 10px;
  font-size: 12px;
}

.envelope-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 4px;
  border-top: 1px solid var(--glass-border, rgba(255,255,255,0.2));
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-text, #1f2937);
}

.tool-params {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.param-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.param-label {
  font-size: 12px;
  color: var(--brand-text-secondary, #5C6B7A);
  white-space: nowrap;
}

.glass-input {
  width: 120px;
  padding: 6px 10px;
  border: 1px solid var(--brand-border, rgba(0,0,0,0.12));
  border-radius: 8px;
  font-size: 13px;
  color: var(--brand-text, #1f2937);
  background: rgba(255, 255, 255, 0.6);
  outline: none;
}

.diagnostic-strip {
  display: flex;
  gap: 16px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(0, 160, 90, 0.10);
  border: 1px solid rgba(0, 160, 90, 0.25);
}

.diagnostic-strip.failed {
  background: rgba(192, 57, 43, 0.10);
  border-color: rgba(192, 57, 43, 0.25);
}

.diag-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #1d7a4f;
}

.diag-item.bad {
  color: #C0392B;
}

.diag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #2ecc71;
}

.diag-item.bad .diag-dot {
  background: #e74c3c;
}
</style>
