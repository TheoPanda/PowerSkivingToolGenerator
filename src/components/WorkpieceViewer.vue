<script setup lang="ts">
import { ref, inject, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchWorkpiece } from '../api'
import { gearParamsKey } from '../composables/useGearParams'
import { setWorkpieceResult } from '../composables/useWorkpieceState'

// ── Inject gearParams from MainPanel（类型化键） ──
const gearParams = inject(gearParamsKey)
if (!gearParams) throw new Error('WorkpieceViewer: gearParams not provided')

// ── State ──
const generating = ref<boolean>(false)
const glbBase64 = ref<string | null>(null)
const error = ref<string | null>(null)

// ── Events ──
const emit = defineEmits<{
  'model-ready': [glbBase64: string]
}>()

// ── Auto-generate on mount ──
onMounted(() => {
  generate()
})

// ── Generate ──
// 结果/spec 写入全局单例（useWorkpieceState），由独立 ResultPanel 消费展示；
// 生成期间不清空旧结果（面板保持上次有效值，新结果到达时自动更新并唤起面板）。
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
</script>

<template>
  <div class="workpiece-viewer">
    <!-- 加载状态 -->
    <div v-if="generating" class="generating-hint">
      <span class="spinner"></span>
      正在生成齿轮模型...
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-msg">
      {{ error }}
      <button class="glass-btn retry-btn" @click="generate">重试</button>
    </div>

    <!-- 计算结果摘要与「查看齿轮规格」已移入独立 ResultPanel（全局单例消费） -->
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
</style>
