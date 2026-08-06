<script setup lang="ts">
import { ref, inject } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchWorkpiece, type WorkpieceResult, type GearParamsInput } from '../api'

// ── Inject gearParams from MainPanel ──
const gearParams = inject<GearParamsInput>('gearParams')
if (!gearParams) throw new Error('WorkpieceViewer: gearParams not provided')

// ── State ──
const generating = ref<boolean>(false)
const result = ref<WorkpieceResult | null>(null)
const glbBase64 = ref<string | null>(null)
const error = ref<string | null>(null)

// ── Events ──
const emit = defineEmits<{
  'model-ready': [glbBase64: string]
}>()

// ── Generate ──
async function generate(): Promise<void> {
  generating.value = true
  error.value = null
  result.value = null

  try {
    const response = await fetchWorkpiece(gearParams!)
    result.value = response.result
    glbBase64.value = response.model_glb_base64
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
</script>

<template>
  <div class="workpiece-viewer">
    <!-- 生成按钮 -->
    <button
      class="glass-btn generate-btn"
      :disabled="generating"
      :class="{ loading: generating }"
      @click="generate"
    >
      <span v-if="generating" class="spinner"></span>
      {{ generating ? '正在生成...' : '生成齿轮' }}
    </button>

    <!-- 错误提示 -->
    <div v-if="error" class="error-msg">
      {{ error }}
      <button class="glass-btn retry-btn" @click="generate">重试</button>
    </div>

    <!-- 计算结果摘要 -->
    <div v-if="result" class="result-summary panel-block">
      <div class="result-title">计算结果</div>
      <div class="result-table">
        <div class="result-row">
          <span class="result-label">齿顶圆 d_a</span>
          <span class="result-value">{{ result.d_a.toFixed(2) }} mm</span>
        </div>
        <div class="result-row">
          <span class="result-label">齿根圆 d_f</span>
          <span class="result-value">{{ result.d_f.toFixed(2) }} mm</span>
        </div>
        <div class="result-row">
          <span class="result-label">基圆半径 r_b</span>
          <span class="result-value">{{ result.r_b.toFixed(3) }} mm</span>
        </div>
        <div class="result-row">
          <span class="result-label">节圆半径 r_pw</span>
          <span class="result-value">{{ result.r_pw.toFixed(3) }} mm</span>
        </div>
        <div class="result-row">
          <span class="result-label">端面模数 m_t</span>
          <span class="result-value">{{ result.m_t.toFixed(3) }} mm</span>
        </div>
        <div class="result-row">
          <span class="result-label">端面压力角 α_t</span>
          <span class="result-value">{{ result.alpha_t_deg.toFixed(2) }}°</span>
        </div>
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

.generate-btn {
  width: 100%;
  padding: 10px 0;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.generate-btn.loading {
  opacity: 0.7;
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

.result-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-text, #1A2332);
  margin-bottom: 10px;
}

.result-table {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.result-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-label {
  font-size: 12px;
  color: var(--brand-text-secondary, #5C6B7A);
}

.result-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--brand-text, #1A2332);
  font-variant-numeric: tabular-nums;
}
</style>
