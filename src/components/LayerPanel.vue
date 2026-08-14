<script setup lang="ts">
/**
 * LayerPanel.vue — 画布右侧「图层」列表面板
 *
 * - 6 语义图层各一行：色块 + 名称（点击聚焦）+ 眼睛开关（显隐）+ 透明度滑条
 * - 顶部「全部显示」一键回到叠加
 * - 图层定义来自 layerPalette（单源）；操作经 inject 的 gearViewport 实例下发
 */
import { inject, reactive, ref, onMounted, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import { LAYER_IDS, LAYER_VISUALS, MATERIAL_PRESETS, type LayerId, type LayerReadyDetail } from '../three/layerPalette'
import { GEAR_VIEWPORT_KEY, type GearViewport } from '../three/gearViewport'

const viewportRef = inject<Ref<GearViewport | null>>(GEAR_VIEWPORT_KEY, ref(null))

/** 图层显隐状态（初始全显示）. */
const visible = reactive<Record<LayerId, boolean>>(
  Object.fromEntries(LAYER_IDS.map((id) => [id, true])) as Record<LayerId, boolean>,
)
/** 图层透明度状态（初始从 palette 默认）. */
const opacity = reactive<Record<LayerId, number>>(
  Object.fromEntries(LAYER_IDS.map((id) => [id, LAYER_VISUALS[id].defaultOpacity])) as Record<LayerId, number>,
)
/** 工件视图模式：实体（false）/ 透明线框（true）. */
const workpieceWireframe = ref<boolean>(false)

function toggleVisible(id: LayerId): void {
  visible[id] = !visible[id]
  viewportRef.value?.setLayerVisible(id, visible[id])
}

function changeOpacity(id: LayerId, v: number): void {
  opacity[id] = v
  viewportRef.value?.setLayerOpacity(id, v)
}

function focusLayer(id: LayerId): void {
  viewportRef.value?.focusLayer(id)
}

/** 工件透明线框切换：实体 ↔ 透明线框. */
function toggleWorkpieceWireframe(): void {
  workpieceWireframe.value = !workpieceWireframe.value
  viewportRef.value?.setWorkpieceView(workpieceWireframe.value ? 'wireframe' : 'solid')
}

function showAll(): void {
  for (const id of LAYER_IDS) {
    visible[id] = true
    opacity[id] = LAYER_VISUALS[id].defaultOpacity
    viewportRef.value?.setLayerVisible(id, true)
    viewportRef.value?.setLayerOpacity(id, LAYER_VISUALS[id].defaultOpacity)
  }
  // 工件视图一并回到实体
  workpieceWireframe.value = false
  viewportRef.value?.setWorkpieceView('solid')
}

/** 图层重新生成（重新点「开始包络」→ gear:layer-ready）→ 重置该层显隐/透明度为默认（图层默认显示）. */
function onLayerReady(e: Event): void {
  const detail = (e as CustomEvent).detail as LayerReadyDetail
  visible[detail.id] = true
  opacity[detail.id] = LAYER_VISUALS[detail.id].defaultOpacity
}

onMounted(() => {
  window.addEventListener('gear:layer-ready', onLayerReady)
})

onUnmounted(() => {
  window.removeEventListener('gear:layer-ready', onLayerReady)
})

/** 图层色块颜色（hex 字符串，供 CSS 使用）. */
function colorOf(id: LayerId): string {
  const def = MATERIAL_PRESETS[LAYER_VISUALS[id].materialPreset]
  return `#${def.color.toString(16).padStart(6, '0')}`
}
</script>

<template>
  <div class="layer-panel">
    <div class="lp-header">
      <span class="lp-title">图层</span>
      <button class="lp-show-all" type="button" data-test="layer-show-all" @click="showAll">全部显示</button>
    </div>
    <div class="lp-list">
      <div v-for="id in LAYER_IDS" :key="id" class="lp-row" :data-test="`layer-row-${id}`">
        <span class="lp-swatch" :style="{ background: colorOf(id) }"></span>
        <span class="lp-name" :title="`聚焦 ${LAYER_VISUALS[id].label}`" @click="focusLayer(id)">
          {{ LAYER_VISUALS[id].label }}
        </span>
        <button
          class="lp-eye"
          :class="{ off: !visible[id] }"
          type="button"
          :title="visible[id] ? '隐藏' : '显示'"
          :data-test="`layer-eye-${id}`"
          @click="toggleVisible(id)"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" />
            <circle cx="12" cy="12" r="3" />
            <line v-if="!visible[id]" x1="4" y1="4" x2="20" y2="20" />
          </svg>
        </button>
        <button
          v-if="id === 'workpiece'"
          class="lp-wire"
          :class="{ active: workpieceWireframe }"
          type="button"
          :title="workpieceWireframe ? '切回实体' : '透明线框'"
          :data-test="`layer-wire-${id}`"
          @click="toggleWorkpieceWireframe"
        >线框</button>
        <input
          class="lp-slider"
          type="range"
          min="0"
          max="1"
          step="0.05"
          :value="opacity[id]"
          :data-test="`layer-opacity-${id}`"
          @input="changeOpacity(id, ($event.target as HTMLInputElement).valueAsNumber)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.layer-panel {
  position: fixed;
  top: 72px;
  right: 16px;
  width: 216px;
  z-index: 16;
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border: 1px solid var(--glass-border);
  border-radius: var(--glass-radius);
  box-shadow: var(--glass-shadow);
  overflow: hidden;
  color: var(--brand-text, #1a2332);
}
.lp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 34px;
  padding: 0 8px 0 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.35);
  background: rgba(255, 255, 255, 0.26);
}
.lp-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.lp-show-all {
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--brand-blue, #0060a0);
  font-size: 11px;
  cursor: pointer;
  padding: 3px 8px;
}
.lp-show-all:hover {
  background: rgba(0, 96, 160, 0.1);
}
.lp-list {
  display: flex;
  flex-direction: column;
  padding: 6px 8px 10px;
}
.lp-row {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 30px;
}
.lp-swatch {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  flex: none;
  border: 1px solid rgba(0, 0, 0, 0.12);
}
.lp-name {
  flex: 1;
  font-size: 12px;
  color: var(--brand-text, #1a2332);
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lp-name:hover {
  color: var(--brand-blue, #0060a0);
}
.lp-eye {
  width: 24px;
  height: 24px;
  flex: none;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: var(--brand-text-secondary, #5c6b7a);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.lp-eye:hover {
  background: rgba(0, 96, 160, 0.1);
  color: var(--brand-blue, #0060a0);
}
.lp-eye.off {
  opacity: 0.4;
}
.lp-wire {
  flex: none;
  height: 22px;
  padding: 0 6px;
  border: 1px solid var(--brand-border, rgba(0, 0, 0, 0.12));
  border-radius: 5px;
  background: transparent;
  color: var(--brand-text-secondary, #5c6b7a);
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
}
.lp-wire:hover {
  background: rgba(0, 96, 160, 0.1);
  color: var(--brand-blue, #0060a0);
}
.lp-wire.active {
  background: var(--brand-blue, #0060a0);
  color: #fff;
  border-color: var(--brand-blue, #0060a0);
}
.lp-slider {
  width: 52px;
  flex: none;
  accent-color: var(--brand-blue, #0060a0);
}
</style>
