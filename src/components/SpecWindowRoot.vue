<script setup lang="ts">
/**
 * SpecWindowRoot.vue — 齿轮规格独立窗口根组件
 *
 * 挂载于 spec.html（独立 BrowserWindow）。规格数据由主进程经 IPC 传入：
 *   - 订阅推送 onSpecData（主进程 did-finish-load 后 webContents.send）
 *   - 兜底拉取 getSpecData（避免加载时序竞态）
 * 「左图右表」：左上单齿廓 / 左下整体轮廓 / 右侧规格表。
 */
import { ref, onMounted } from 'vue'
import type { SpecPayload } from '../api'
import ToothProfileSvg from './ToothProfileSvg.vue'
import GearOutlineSvg from './GearOutlineSvg.vue'
import SpecTable from './SpecTable.vue'

const spec = ref<SpecPayload | null>(null)
const error = ref<string | null>(null)

function applySpec(data: SpecPayload): void {
  spec.value = data
}

onMounted(() => {
  const api = window.electronAPI
  if (!api) {
    error.value = 'electronAPI 不可用（非 Electron 环境）'
    return
  }
  api.getSpecData().then((data) => {
    if (data) applySpec(data)
  })
  api.onSpecData((data) => applySpec(data))
})
</script>

<template>
  <div class="spec-window-root">
    <div v-if="spec" class="spec-body">
      <div class="spec-drawings">
        <div class="drawing-panel">
          <div class="drawing-label">单齿廓</div>
          <ToothProfileSvg :singleTooth="spec.single_tooth" />
        </div>
        <div class="drawing-panel">
          <div class="drawing-label">整体轮廓</div>
          <GearOutlineSvg :outline="spec.outline" />
        </div>
      </div>
      <div class="spec-table-panel">
        <SpecTable :params="spec.params" />
      </div>
    </div>

    <div v-else class="spec-loading">
      <p v-if="error" class="spec-error">{{ error }}</p>
      <p v-else class="spec-waiting">等待齿轮规格数据…</p>
    </div>
  </div>
</template>

<style scoped>
.spec-window-root {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--brand-bg-page, #f2f5f8);
}
.spec-body {
  flex: 1;
  display: flex;
  gap: 14px;
  padding: 14px;
  min-height: 0;
}
.spec-drawings {
  flex: 1 1 55%;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}
.drawing-panel {
  flex: 1 1 50%;
  position: relative;
  background: #ffffff;
  border-radius: 10px;
  overflow: hidden;
}
.drawing-label {
  position: absolute;
  top: 6px;
  left: 8px;
  z-index: 2;
  font-size: 11px;
  font-weight: 600;
  color: var(--brand-blue, #0060a0);
  background: rgba(255, 255, 255, 0.85);
  padding: 2px 8px;
  border-radius: 4px;
}
.spec-table-panel {
  flex: 0 0 42%;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 10px;
  color: var(--brand-text, #1a2332);
  overflow: auto;
}
.spec-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--brand-text-secondary, #5c6b7a);
}
.spec-error {
  color: var(--brand-danger, #e5533d);
}
</style>
