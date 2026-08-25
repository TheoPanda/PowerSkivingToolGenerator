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
import { setInterferenceVisible } from '../composables/useInterferenceLegend'

const viewportRef = inject<Ref<GearViewport | null>>(GEAR_VIEWPORT_KEY, ref(null))

// ── 面板拖拽（仅标题栏；位置 localStorage 记忆；默认右对齐视图切换面板下方） ──
const PANEL_W = 248
const HEADER_H = 34   // .lp-header 高度
const EDGE = 8
const POS_KEY = 'pst.layer-panel.pos'
/** 默认位置：右缘与右上角视图切换面板对齐（right 12px），位于其下方（视图面板 ≈ 12 + ~150 高 + 间距 ≈ 175px）. */
function defaultPos(): { x: number; y: number } {
  return { x: window.innerWidth - PANEL_W - 12, y: 178 }
}
function loadPos(): { x: number; y: number } {
  try {
    const raw = localStorage.getItem(POS_KEY)
    if (raw) {
      const p = JSON.parse(raw) as { x: number; y: number }
      if (typeof p?.x === 'number' && typeof p?.y === 'number') return p
    }
  } catch { /* 忽略损坏数据 */ }
  return defaultPos()
}
const panelPos = reactive<{ x: number; y: number }>(loadPos())

let dragging = false
let lastX = 0
let lastY = 0
function onHeaderDown(e: MouseEvent): void {
  if ((e.target as HTMLElement).closest('button')) return
  dragging = true
  lastX = e.clientX
  lastY = e.clientY
  window.addEventListener('mousemove', onWindowMove)
  window.addEventListener('mouseup', onWindowUp)
  document.body.style.userSelect = 'none'
}
function onWindowMove(e: MouseEvent): void {
  if (!dragging) return
  const dx = e.clientX - lastX
  const dy = e.clientY - lastY
  lastX = e.clientX
  lastY = e.clientY
  panelPos.x = clampX(panelPos.x + dx)
  panelPos.y = clampY(panelPos.y + dy)
}
function onWindowUp(): void {
  dragging = false
  window.removeEventListener('mousemove', onWindowMove)
  window.removeEventListener('mouseup', onWindowUp)
  document.body.style.userSelect = ''
  try { localStorage.setItem(POS_KEY, JSON.stringify(panelPos)) } catch { /* 忽略写入失败 */ }
}
function clampX(x: number): number {
  return Math.min(Math.max(EDGE, x), Math.max(EDGE, window.innerWidth - PANEL_W - EDGE))
}
function clampY(y: number): number {
  return Math.min(Math.max(EDGE, y), Math.max(EDGE, window.innerHeight - HEADER_H - EDGE))
}

// 窗口 resize → 保持右对齐（面板右缘距窗口右缘不变），随窗口宽度联动
let prevW = window.innerWidth
function onResize(): void {
  const dw = window.innerWidth - prevW
  panelPos.x = clampX(panelPos.x + dw)
  prevW = window.innerWidth
}

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

/** 等效产形齿轮样式切换：靛蓝单色 ↔ 干涉热力图（符号距离顶点色）；图例联动显隐. */
const conjugateGearInterference = ref<boolean>(false)

function toggleConjugateGearInterference(): void {
  conjugateGearInterference.value = !conjugateGearInterference.value
  viewportRef.value?.setConjugateGearInterference(conjugateGearInterference.value)
  setInterferenceVisible(conjugateGearInterference.value)
}

function showAll(): void {
  for (const id of LAYER_IDS) {
    visible[id] = true
    opacity[id] = LAYER_VISUALS[id].defaultOpacity
    viewportRef.value?.setLayerVisible(id, true)
    viewportRef.value?.setLayerOpacity(id, LAYER_VISUALS[id].defaultOpacity)
  }
  // 工件视图一并回到实体；干涉样式/图例一并复位
  workpieceWireframe.value = false
  viewportRef.value?.setWorkpieceView('solid')
  if (conjugateGearInterference.value) {
    conjugateGearInterference.value = false
    viewportRef.value?.setConjugateGearInterference(false)
    setInterferenceVisible(false)
  }
}

/** 触发运动仿真：派发事件由 WorkpieceViewer 处理（它持有请求参数）. */
function startSimulation(): void {
  window.dispatchEvent(new CustomEvent('gear:request-simulation'))
}

/** 图层重新生成（重新点「开始包络」→ gear:layer-ready）→ 重置该层显隐/透明度为默认（图层默认显示）. */
function onLayerReady(e: Event): void {
  const detail = (e as CustomEvent).detail as LayerReadyDetail
  visible[detail.id] = true
  opacity[detail.id] = LAYER_VISUALS[detail.id].defaultOpacity
}

onMounted(() => {
  window.addEventListener('gear:layer-ready', onLayerReady)
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('gear:layer-ready', onLayerReady)
  window.removeEventListener('resize', onResize)
})

/** 图层色块颜色（hex 字符串，供 CSS 使用）. */
function colorOf(id: LayerId): string {
  const def = MATERIAL_PRESETS[LAYER_VISUALS[id].materialPreset]
  return `#${def.color.toString(16).padStart(6, '0')}`
}

/** 扫掠点云色块：jet 光谱渐变（与视口逐帧 jet 着色呼应）. */
function spectrumSwatchStyle(): { background: string } {
  return {
    background: 'linear-gradient(90deg, #3050c8 0%, #30b3b3 25%, #30c830 50%, #c8b330 75%, #c83030 100%)',
  }
}
</script>

<template>
  <div class="layer-panel" :style="{ left: panelPos.x + 'px', top: panelPos.y + 'px' }">
    <div class="lp-header" @mousedown="onHeaderDown">
      <span class="lp-title">图层</span>
      <button class="lp-show-all" type="button" data-test="layer-show-all" @click="showAll">全部显示</button>
    </div>
    <div class="lp-list">
      <div v-for="id in LAYER_IDS" :key="id" class="lp-row" :data-test="`layer-row-${id}`">
        <span
          class="lp-swatch"
          :class="{ 'lp-swatch-spectrum': id === 'sweptCloud' }"
          :style="id === 'sweptCloud' ? spectrumSwatchStyle() : { background: colorOf(id) }"
        ></span>
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
        <button
          v-if="id === 'conjugateGear'"
          class="lp-wire"
          :class="{ active: conjugateGearInterference }"
          type="button"
          :title="conjugateGearInterference ? '切回单色' : '干涉热力图'"
          :data-test="`layer-interference-${id}`"
          @click="toggleConjugateGearInterference"
        >干涉</button>
        <button
          v-if="id === 'sweptCloud'"
          class="lp-wire"
          type="button"
          title="运动仿真（固定刀具系看工件运动）"
          data-test="layer-sim-sweptCloud"
          @click="startSimulation"
        >仿真</button>
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
  width: var(--float-panel-width, 248px);
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
  cursor: grab;
  user-select: none;
}
.lp-header:active {
  cursor: grabbing;
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
/* 扫掠点云色块：jet 渐变，稍宽以呈现光谱 */
.lp-swatch-spectrum {
  width: 16px;
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
