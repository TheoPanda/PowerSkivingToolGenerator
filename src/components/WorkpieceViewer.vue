<script setup lang="ts">
/**
 * WorkpieceViewer.vue — 步骤2：工件齿轮生成 + 包络计算
 *
 * - 挂载即调用 fetchWorkpiece 生成齿轮 GLB（模块①，结果/spec 写全局单例）
 * - 「包络计算」区块：输入刀具参数 → 依次调 edge / conjugate / conjugateGear /
 *   rake / flank / singleTooth 端点（共轭法），经 gear:layer-ready 事件叠加图层
 * - 诊断条显示 ffα 与覆盖判据（成功绿勾 / 失败红叉）
 */
import { ref, inject, onMounted, reactive, computed, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchWorkpiece,
  fetchEnvelopeEdge,
  fetchEnvelopeRake,
  fetchEnvelopeFlank,
  fetchEnvelopeSingleTooth,
  fetchEnvelopeAnalytic,
  fetchEnvelopeConjugate,
  fetchEnvelopeConjugateGear,
  fetchEnvelopeInterference,
  type CoverageReport,
  type CrossCheckResult,
} from '../api'
import type { LayerReadyDetail } from '../three/layerPalette'
import { GEAR_VIEWPORT_KEY, type GearViewport } from '../three/gearViewport'
import { gearParamsKey, toPayload } from '../composables/useGearParams'
import { setWorkpieceResult } from '../composables/useWorkpieceState'

// ── 从 MainPanel 注入 gearParams（类型化键） ──
const gearParams = inject(gearParamsKey)
if (!gearParams) throw new Error('WorkpieceViewer: gearParams not provided')

// ── 从 MainView 注入 3D 视口（安装变换/坐标轴） ──
const viewportRef = inject<Ref<GearViewport | null>>(GEAR_VIEWPORT_KEY, ref(null))

// ── 工件生成状态 ──
const generating = ref<boolean>(false)
const glbBase64 = ref<string | null>(null)
const error = ref<string | null>(null)

// ── 包络计算状态 ──
const toolParams = reactive({
  z_t: 41,        // 默认匹配算例1 内齿轮 z_w=82（端到端 demo）
  beta_t: 15,
  j_t: -1,        // 左旋 → Σ=+15°（内齿轮旋向相反）
  gamma_0: 5,     // 前角（子 PRD-3 前刀面 K-2.1 输入）
  alpha_0: 8,     // 顶刃后角 α₀（圆锥刀专用；圆柱刀螺旋导程法 α₀=0 构造性后角，不参与）
  rake_type: 'plane',  // 前刀面形式（v1 仅 plane；equation/cone 灰置）
  tool_type: 'cylindrical',     // 刀型：圆柱（圆锥二期）
  flank_method: 'helical_lead', // 后刀面算法：螺旋导程法（轴向偏移法二期）
  L: 2,           // 总重磨量 [mm]（子 PRD-4 后刀面）
  n_L: 4,         // 重磨等分数（子 PRD-4 后刀面）
})
const envelopeRunning = ref<boolean>(false)
const envelopeError = ref<string | null>(null)
const ffaUm = ref<number | null>(null)
const coverageReport = ref<CoverageReport | null>(null)
const useAnalytic = ref<boolean>(false)         // 解析路线对拍（可选，覆盖离散刃形）
const crossCheck = ref<CrossCheckResult | null>(null)

/** 覆盖率百分比（诊断条展示）. */
const coveragePercent = computed<number | null>(() => {
  if (!coverageReport.value) return null
  return Math.round(coverageReport.value.coverage_ratio * 100)
})

/** 诊断条总体通过（覆盖 100% 且 ffα 闭包残差 < 1μm）.

 * ffα 现为「正反闭包自证」残差（链可逆性数值误差，m=181 插值 ~0.1μm 量级），
 * 非设计书 K-2.13 正向包络误差（后者留 K-4.1）。阈值 <1μm 与后端
 * test_segments_structure 的「数值自洽误差量级」一致。
 */
const envelopePassed = computed<boolean>(() => {
  if (ffaUm.value === null || coverageReport.value === null) return false
  return ffaUm.value < 1.0 && coverageReport.value.pass
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
function dispatchLayer(id: 'edge' | 'rake' | 'flank' | 'singleTooth' | 'conjugate' | 'conjugateGear' | 'interference', glbBase64: string): void {
  const detail: LayerReadyDetail = { id, glbBase64 }
  window.dispatchEvent(new CustomEvent('gear:layer-ready', { detail }))
}

// ── 包络计算（共轭法：刃形 → 产形面 → 后刀面） ──
async function runEnvelope(): Promise<void> {
  if (gearParams!.m_n === null || gearParams!.z_w === null) {
    ElMessage.warning('请先在步骤1 填写法向模数 m_n 与工件齿数 z_w')
    return
  }
  if (generating.value || glbBase64.value === null) {
    ElMessage.warning('请先生成工件齿轮模型，再开始包络计算')
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
      // discretization 缺省 → 后端默认 n=200/m=181/NR=200/θ=±40°
    }

    // 刃形（先叠加）+ 诊断 + 安装变换（刀具系 T → 工件系 W）+ 画 W/T 坐标轴
    const edgeResp = await fetchEnvelopeEdge(req)
    dispatchLayer('edge', edgeResp.layer.glb_base64)
    ffaUm.value = edgeResp.ffa_um
    coverageReport.value = edgeResp.coverage_report
    viewportRef.value?.setEnvelopeInstall(edgeResp.install.a, edgeResp.install.sigma_deg)

    // 产形面（共轭面，K-2.6 数值啮合）：刃形 = 产形面 ∩ 前刀面，随后叠加
    const conjugateResp = await fetchEnvelopeConjugate(req)
    dispatchLayer('conjugate', conjugateResp.layer.glb_base64)

    // 等效产形齿轮：单齿槽产形面阵列 z_t 份 + 齿顶/齿根回转面（完整齿轮全貌）
    const conjugateGearResp = await fetchEnvelopeConjugateGear(req)
    dispatchLayer('conjugateGear', conjugateGearResp.layer.glb_base64)

    // 干涉热力图：产形面符号距离着色（红=干涉/白=相切/蓝=间隙）
    const interferenceResp = await fetchEnvelopeInterference(req)
    dispatchLayer('interference', interferenceResp.layer.glb_base64)

    // 解析路线（子 PRD-5，可选）：K-2.8 解析刃形（二分精化，与离散同法）覆盖刃形图层 + 双路线互检
    if (useAnalytic.value) {
      const analyticResp = await fetchEnvelopeAnalytic(req)
      dispatchLayer('edge', analyticResp.layer.glb_base64)
      crossCheck.value = analyticResp.cross_check
    }

    // 前刀面（子 PRD-3，后叠加）：γ₀ → 平面前刀面 + 法矢箭头
    const rakeResp = await fetchEnvelopeRake({
      workpiece: req.workpiece,
      tool: req.tool,
      rake_type: toolParams.rake_type as 'plane',
    })
    dispatchLayer('rake', rakeResp.layer.glb_base64)

    // 后刀面 + 单齿预览（子 PRD-4）：L/n_L 重磨 → 后刀面 + 单齿三件套
    const flankReq = {
      workpiece: req.workpiece,
      tool: req.tool,
      resharpening: { L: toolParams.L, n_L: toolParams.n_L },
      tool_type: toolParams.tool_type as 'cylindrical' | 'conical',
      flank_method: toolParams.flank_method as 'helical_lead' | 'axial_offset',
    }
    const flankResp = await fetchEnvelopeFlank(flankReq)
    dispatchLayer('flank', flankResp.layer.glb_base64)
    const toothResp = await fetchEnvelopeSingleTooth(flankReq)
    dispatchLayer('singleTooth', toothResp.layer.glb_base64)

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
        <label class="param-field">
          <span class="param-label">刀型</span>
          <select v-model="toolParams.tool_type" class="glass-input" data-test="tool-tool_type">
            <option value="cylindrical">圆柱型</option>
            <option value="conical" disabled>圆锥型（二期）</option>
          </select>
        </label>
        <label class="param-field">
          <span class="param-label">前角 γ₀ (°)</span>
          <input v-model.number="toolParams.gamma_0" type="number" class="glass-input" data-test="tool-gamma_0" />
        </label>
        <label v-if="toolParams.tool_type === 'conical'" class="param-field">
          <span class="param-label">顶刃后角 α₀ (°)</span>
          <input v-model.number="toolParams.alpha_0" type="number" class="glass-input" data-test="tool-alpha_0" />
        </label>
        <label class="param-field">
          <span class="param-label">前刀面形式</span>
          <select v-model="toolParams.rake_type" class="glass-input" data-test="tool-rake_type">
            <option value="plane">平面</option>
            <option value="equation" disabled>方程（未实现）</option>
            <option value="cone" disabled>锥面（未实现）</option>
          </select>
        </label>
        <label class="param-field">
          <span class="param-label">后刀面算法</span>
          <select v-model="toolParams.flank_method" class="glass-input" data-test="tool-flank_method">
            <option value="helical_lead">螺旋导程法</option>
            <option value="axial_offset" disabled>轴向偏移法（二期）</option>
          </select>
        </label>
        <label class="param-field">
          <span class="param-label">总重磨量 L (mm)</span>
          <input v-model.number="toolParams.L" type="number" class="glass-input" data-test="tool-L" />
        </label>
        <label class="param-field">
          <span class="param-label">重磨等分数 n_L</span>
          <input v-model.number="toolParams.n_L" type="number" class="glass-input" data-test="tool-n_L" />
        </label>
        <label class="param-field">
          <span class="param-label">解析路线对拍（覆盖离散）</span>
          <input v-model="useAnalytic" type="checkbox" class="glass-input" data-test="use-analytic" />
        </label>
      </div>

      <button
        class="glass-btn"
        type="button"
        data-test="run-envelope"
        :disabled="envelopeRunning || generating || glbBase64 === null"
        @click="runEnvelope"
      >
        {{ envelopeRunning ? '包络计算中…' : '开始包络' }}
      </button>
      <div v-if="glbBase64 === null && !generating" class="envelope-hint">
        请先生成工件齿轮模型，再开始包络计算
      </div>

      <div v-if="envelopeError" class="error-msg">{{ envelopeError }}</div>

      <!-- 诊断条：ffα + 覆盖判据 -->
      <div v-if="ffaUm !== null" class="diagnostic-strip" :class="{ failed: !envelopePassed }" data-test="diagnostic-strip">
        <span class="diag-item" :class="ffaUm < 1.0 ? 'ok' : 'bad'">
          <span class="diag-dot"></span>
          ffα = {{ ffaUm.toFixed(3) }} μm
        </span>
        <span class="diag-item" :class="coverageReport?.pass ? 'ok' : 'bad'">
          <span class="diag-dot"></span>
          覆盖 {{ coveragePercent ?? '—' }}%
        </span>
        <span v-if="crossCheck !== null" class="diag-item" :class="crossCheck.pass ? 'ok' : 'bad'">
          <span class="diag-dot"></span>
          互检 max|Δ| = {{ crossCheck.max_delta_um.toFixed(3) }} μm
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

.envelope-hint {
  color: var(--brand-text-secondary, #5C6B7A);
  font-size: 12px;
  text-align: center;
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
