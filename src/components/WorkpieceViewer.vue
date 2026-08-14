<script setup lang="ts">
/**
 * WorkpieceViewer.vue — 步骤2：工件齿轮生成 + 包络计算
 *
 * - 挂载即调用 fetchWorkpiece 生成齿轮 GLB（模块①，结果/spec 写全局单例）
 * - 「包络计算」区块：输入刀具参数 → 依次调 swept_cloud / edge / rake 端点
 *   （子 PRD-2 离散包络 + 子 PRD-3 前刀面），经 gear:layer-ready 事件叠加
 *   扫掠点云 / 刃形 / 前刀面三图层
 * - 诊断条显示 ffα 与覆盖判据（成功绿勾 / 失败红叉）
 */
import { ref, inject, onMounted, onUnmounted, reactive, computed, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchWorkpiece,
  fetchEnvelopeSweptCloud,
  fetchEnvelopeEdge,
  fetchEnvelopeRake,
  fetchEnvelopeFlank,
  fetchEnvelopeSingleTooth,
  fetchEnvelopeAnalytic,
  type CoverageReport,
  type CrossCheckResult,
} from '../api'
import type { LayerReadyDetail, SweptCloudMotion } from '../three/layerPalette'
import { GEAR_VIEWPORT_KEY, type GearViewport } from '../three/gearViewport'
import { gearParamsKey, toPayload } from '../composables/useGearParams'
import { setWorkpieceResult } from '../composables/useWorkpieceState'

// ── 从 MainPanel 注入 gearParams（类型化键） ──
const gearParams = inject(gearParamsKey)
if (!gearParams) throw new Error('WorkpieceViewer: gearParams not provided')

// ── 从 MainView 注入 3D 视口（扫掠点云揭示/面网切换） ──
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
  alpha_0: 8,     // 后角（子 PRD-4 后刀面 K-2.18 重磨方向输入）
  rake_type: 'plane',  // 前刀面形式（v1 仅 plane；equation/cone 灰置）
  L: 2,           // 总重磨量 [mm]（子 PRD-4 后刀面）
  n_L: 4,         // 重磨等分数（子 PRD-4 后刀面）
})
const envelopeRunning = ref<boolean>(false)
const envelopeError = ref<string | null>(null)
const ffaUm = ref<number | null>(null)
const coverageReport = ref<CoverageReport | null>(null)
const useAnalytic = ref<boolean>(false)         // 解析路线对拍（可选，覆盖离散刃形）
const crossCheck = ref<CrossCheckResult | null>(null)

// ── 扫掠点云可视化（面/网切换 + 揭示滑块 + 播放） ──
const sweptMotion = ref<SweptCloudMotion | null>(null)
const revealF = ref<number>(1.0) // 揭示分数 0..1（默认满显）
const sweptCloudMode = ref<'surface' | 'net'>('surface')
const playing = ref<boolean>(false)

/** 扫掠范围半角 θ（°），缺省 40（与后端默认一致）. */
const thetaRange = computed<number>(() => sweptMotion.value?.theta_range_deg ?? 40.0)

/** 滑块值 = φ_t 角度（°），双向映射到 revealF. */
const sliderPhiT = computed<number>({
  get: (): number => (2 * revealF.value - 1) * thetaRange.value,
  set: (v: number): void => {
    if (playing.value) stopPlay()
    revealF.value = (v + thetaRange.value) / (2 * thetaRange.value)
    viewportRef.value?.setSweptCloudReveal(revealF.value)
  },
})

/** 进度百分比（滑块旁展示）. */
const progressPercent = computed<number>(() => Math.round(revealF.value * 100))

let playRafId: number | null = null

/** 播放：从当前揭示分数单向扫到 1.0（约 3s），逐帧设 reveal. */
function play(): void {
  if (playing.value || sweptMotion.value === null) return
  playing.value = true
  const startF = revealF.value
  const startTime = performance.now()
  const duration = 3000
  const step = (now: number): void => {
    const t = Math.min(1, (now - startTime) / duration)
    const f = startF + (1 - startF) * t
    revealF.value = f
    viewportRef.value?.setSweptCloudReveal(f)
    if (t < 1) {
      playRafId = requestAnimationFrame(step)
    } else {
      playing.value = false
    }
  }
  playRafId = requestAnimationFrame(step)
}

function stopPlay(): void {
  if (playRafId !== null) {
    cancelAnimationFrame(playRafId)
    playRafId = null
  }
  playing.value = false
}

/** 面 / 网两档切换（同步到视口）. */
function onModeChange(mode: 'surface' | 'net'): void {
  sweptCloudMode.value = mode
  viewportRef.value?.setSweptCloudMode(mode)
}

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

onUnmounted(() => {
  stopPlay()
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
function dispatchLayer(id: 'swept_cloud' | 'edge' | 'rake' | 'flank' | 'singleTooth', glbBase64: string, motion?: SweptCloudMotion): void {
  const detail: LayerReadyDetail = { id, glbBase64, motion }
  window.dispatchEvent(new CustomEvent('gear:layer-ready', { detail }))
}

// ── 包络计算（子 PRD-2 离散包络：扫掠点云 → 刃形） ──
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
  sweptMotion.value = null
  stopPlay()

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

    // 扫掠点云（先叠加）：记录 motion、重置揭示/档位
    const gen = await fetchEnvelopeSweptCloud(req)
    sweptMotion.value = gen.motion
    revealF.value = 1.0
    sweptCloudMode.value = 'surface'
    // 设置安装变换（刀具系 T → 工件系 W）+ 画 W/T 坐标轴
    viewportRef.value?.setEnvelopeInstall(gen.install.a, gen.install.sigma_deg)
    dispatchLayer('swept_cloud', gen.layer.glb_base64, gen.motion)

    // 刃形（后叠加）+ 诊断
    const edgeResp = await fetchEnvelopeEdge(req)
    dispatchLayer('edge', edgeResp.layer.glb_base64)
    ffaUm.value = edgeResp.ffa_um
    coverageReport.value = edgeResp.coverage_report

    // 解析路线（子 PRD-5，可选）：K-2.8 解析刃形覆盖离散刃形 + 双路线互检
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
          <span class="param-label">前角 γ₀ (°)</span>
          <input v-model.number="toolParams.gamma_0" type="number" class="glass-input" data-test="tool-gamma_0" />
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

      <!-- 扫掠点云显示控制：面/网切换 + φ_t 揭示滑块 + 播放 -->
      <div v-if="sweptMotion !== null" class="swept_cloud-controls" data-test="swept_cloud-controls">
        <div class="mode-toggle">
          <button
            class="glass-btn mode-btn"
            :class="{ active: sweptCloudMode === 'surface' }"
            type="button"
            data-test="mode-surface"
            @click="onModeChange('surface')"
          >面</button>
          <button
            class="glass-btn mode-btn"
            :class="{ active: sweptCloudMode === 'net' }"
            type="button"
            data-test="mode-net"
            @click="onModeChange('net')"
          >网+点</button>
        </div>

        <div class="reveal-row">
          <input
            class="reveal-slider"
            type="range"
            :min="-thetaRange"
            :max="thetaRange"
            step="0.1"
            v-model.number="sliderPhiT"
            data-test="reveal-slider"
          />
          <span class="reveal-label" data-test="reveal-label">φ_t = {{ sliderPhiT.toFixed(1) }}°（{{ progressPercent }}%）</span>
          <button
            class="glass-btn play-btn"
            type="button"
            data-test="reveal-play"
            :disabled="playing"
            @click="play"
          >{{ playing ? '播放中…' : '播放' }}</button>
        </div>
      </div>

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

.swept_cloud-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0;
  border-top: 1px dashed var(--glass-border, rgba(255,255,255,0.2));
}

.mode-toggle {
  display: flex;
  gap: 6px;
}

.mode-btn {
  flex: 1;
  padding: 4px 0;
  font-size: 12px;
  opacity: 0.7;
}

.mode-btn.active {
  opacity: 1;
  background: #0060A0;
  color: #fff;
  border-color: #0060A0;
}

.reveal-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.reveal-slider {
  flex: 1;
  min-width: 0;
}

.reveal-label {
  font-size: 11px;
  color: var(--brand-text-secondary, #5C6B7A);
  white-space: nowrap;
}

.play-btn {
  padding: 4px 10px;
  font-size: 12px;
}
</style>
