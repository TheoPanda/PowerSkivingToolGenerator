<script setup lang="ts">
/**
 * LayerPanel.vue — 画布右侧「图层」列表面板
 *
 * - 10 语义图层各一行：色块 + 名称（点击聚焦）+ 眼睛开关（显隐）+ 功能按钮 + 透明度滑条
 * - 表头四列（图层/可见/功能/透明度）与行 grid 同模板严格对齐（列含义明示）
 * - 标题栏：可见计数徽章 + 一键全显/全隐（全显兼重置透明度与视图，原「全部显示」语义）
 * - Alt+点击眼睛 = 独显该层（再次操作恢复全部可见；不动透明度）
 * - 拖动松手贴边吸附（与 ResultPanel 同规格：四边 50px 阈值，左/右/上/下各留边距）
 * - 显隐/透明度的权威源在 useLayers() 单例（PRD §5.5 上提）：本组件只读 state + 派发动作，
 *   并把 inject 到的 viewport 登记进去（晚于状态出现的实例也能补上全量同步）
 */
import { inject, reactive, ref, computed, watch, onMounted, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import { LAYER_IDS, LAYER_VISUALS, MATERIAL_PRESETS, type LayerId, type LayerReadyDetail } from '../three/layerPalette'
import { GEAR_VIEWPORT_KEY, type GearViewport } from '../three/gearViewport'
import { useLayers } from '../composables/useLayers'
import { setInterferenceVisible } from '../composables/useInterferenceLegend'
import { PANEL_MARGIN, SNAP_TOP, SNAP_THRESHOLD, RIGHT_COLUMN_TOP } from './panelLayout'
import { installGlassRefraction } from './liquidGlass'

const viewportRef = inject<Ref<GearViewport | null>>(GEAR_VIEWPORT_KEY, ref(null))

// ── 图层权威状态 + 动作（useLayers 单例；本组件不再持有可见性真值） ──
const layers = useLayers()
/** 眼睛开关读的显隐表（state.visible 的响应式引用）. */
const visible = layers.state.visible
/** 滑条读的透明度表. */
const opacity = layers.state.opacity

// viewport 由 MainView 在 onMounted 创建，晚于本组件 setup → 监听注入值非空即登记
watch(viewportRef, (vp: GearViewport | null): void => {
  layers.registerViewport(vp)
}, { immediate: true })

// ── 面板拖拽（仅标题栏；位置 localStorage 记忆；默认右对齐视图切换面板下方） ──
// 264px：四列 grid（名称 1fr + 可见 26 + 功能 42 + 透明度 58）需比共用浮层面板宽一档，
// 不复用 --float-panel-width（ResultPanel/SimulationPanel 维持 248px）
const PANEL_W = 264
const HEADER_H = 34   // .lp-header 高度
const EDGE = 8
const POS_KEY = 'pst.layer-panel.pos'

// ── 贴边吸附（panelLayout 共享常量：左/右/下 = PANEL_MARGIN，上 = 标题栏下留同边距）──
const SNAP_LEFT = PANEL_MARGIN // 左贴：与 MainPanel 左缘对齐（left:24px，注释互指）
const SNAP_RIGHT = PANEL_MARGIN // 右贴：与右上角视图切换面板右缘对齐（right:24px，注释互指）
const SNAP_BOTTOM = PANEL_MARGIN // 下贴：底边距

/** 面板根元素（贴边吸附取实际高度）. */
const panelEl = ref<HTMLElement | null>(null)
/** 默认位置：右缘与右上角视图切换面板对齐（right 24px = PANEL_MARGIN，panelLayout 互指），
 * 位于其正下方（y = RIGHT_COLUMN_TOP：ViewCube 底 + 8，两坐标系差 40px 已计入）. */
function defaultPos(): { x: number; y: number } {
  return { x: window.innerWidth - PANEL_W - PANEL_MARGIN, y: RIGHT_COLUMN_TOP }
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
// 持久化旧值（更早版本坐标/最大化时存的大 x）加载即 clamp 纠正
const _initPos = loadPos()
const panelPos = reactive<{ x: number; y: number }>({ x: clampX(_initPos.x), y: clampY(_initPos.y) })

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
  snapToEdge() // 先吸附再持久化（存最终位置）
  try { localStorage.setItem(POS_KEY, JSON.stringify(panelPos)) } catch { /* 忽略写入失败 */ }
}
function clampX(x: number): number {
  // 右边界留 PANEL_MARGIN（24）：与视图/结果面板右缘对齐（EDGE=8 会差 16px，
  // localStorage 旧值触发 clamp 时用户可见错位）
  return Math.min(Math.max(EDGE, x), Math.max(EDGE, window.innerWidth - PANEL_W - PANEL_MARGIN))
}
function clampY(y: number): number {
  // 下限 RIGHT_COLUMN_TOP：面板与 ViewCube 同贴右列，y 过低会盖住它（resize 联动防回归）
  return Math.min(
    Math.max(RIGHT_COLUMN_TOP, y),
    Math.max(RIGHT_COLUMN_TOP, window.innerHeight - HEADER_H - EDGE),
  )
}

/** 释放时贴边吸附：左/右/上/下任一在阈值内即贴齐对应边（保留边距，与 ResultPanel 同规格）. */
function snapToEdge(): void {
  const w = window.innerWidth
  const h = window.innerHeight
  const panelH = panelEl.value?.offsetHeight ?? HEADER_H
  let { x, y } = panelPos
  if (x <= SNAP_LEFT + SNAP_THRESHOLD) x = SNAP_LEFT
  else if (w - (x + PANEL_W) <= SNAP_RIGHT + SNAP_THRESHOLD) x = w - PANEL_W - SNAP_RIGHT
  if (y <= SNAP_TOP + SNAP_THRESHOLD) y = SNAP_TOP
  else if (h - (y + panelH) <= SNAP_BOTTOM + SNAP_THRESHOLD) y = h - panelH - SNAP_BOTTOM
  panelPos.x = x
  panelPos.y = y
}

// 窗口 resize → 保持右/下对齐（面板右缘、底缘距窗口边不变），随窗口尺寸联动
let prevW = window.innerWidth
let prevH = window.innerHeight
function onResize(): void {
  const dw = window.innerWidth - prevW
  const dh = window.innerHeight - prevH
  panelPos.x = clampX(panelPos.x + dw)
  panelPos.y = clampY(panelPos.y + dh)
  prevW = window.innerWidth
  prevH = window.innerHeight
}

/** 工件视图模式：实体（false）/ 透明线框（true）. */
const workpieceWireframe = ref<boolean>(false)

/** 可见层数（徽章「n/总」）. */
const visibleCount = computed<number>(() => LAYER_IDS.filter((id) => visible[id]).length)

function toggleVisible(id: LayerId, e: MouseEvent): void {
  if (e.altKey) {
    layers.soloLayer(id)
    return
  }
  layers.setLayerVisible(id, !visible[id])
}

function changeOpacity(id: LayerId, v: number): void {
  layers.setLayerOpacity(id, v)
}

function focusLayer(id: LayerId): void {
  layers.focusLayer(id)
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

/** 全显（原「全部显示」）：图层显隐+透明度回默认走 useLayers，工件实体视图 + 干涉样式复位留在本组件. */
function showAll(): void {
  layers.showAll()
  // 工件视图一并回到实体；干涉样式/图例一并复位
  workpieceWireframe.value = false
  viewportRef.value?.setWorkpieceView('solid')
  if (conjugateGearInterference.value) {
    conjugateGearInterference.value = false
    viewportRef.value?.setConjugateGearInterference(false)
    setInterferenceVisible(false)
  }
}

/** 全隐：仅显隐批量关闭（透明度/视图样式保留，恢复显示时不丢用户调整）. */
function hideAll(): void {
  layers.hideAll()
}

/** 触发运动仿真：派发事件由 WorkpieceViewer 处理（它持有请求参数）. */
function startSimulation(): void {
  window.dispatchEvent(new CustomEvent('gear:request-simulation'))
}

/** 图层重新生成（重新点「开始包络」→ gear:layer-ready）→ 重置该层为默认可见/默认透明度（权威源在 useLayers）. */
function onLayerReady(e: Event): void {
  const detail = (e as CustomEvent).detail as LayerReadyDetail
  layers.markLayerReady(detail.id)
}

onMounted(() => {
  window.addEventListener('gear:layer-ready', onLayerReady)
  window.addEventListener('resize', onResize)
  if (panelEl.value) {
    installGlassRefraction(panelEl.value, 'layer-panel')
    // 持久化旧值精调：loadPos 时的 clampY 只保证顶栏在窗内（无实际高度），
    // 最大化时代存的 y 在小窗口里会把面板大半沉到窗底外 → 露一条「消失」
    const h = panelEl.value.offsetHeight
    if (h > 0 && panelPos.y + h > window.innerHeight - EDGE) {
      panelPos.y = clampY(window.innerHeight - h - EDGE)
    }
  }
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

/** 滑条进度可视化：品牌色填充到当前值（Chromium 原生 range 不带进度，用渐变背景模拟）. */
function sliderBg(id: LayerId): { background: string } {
  const pct = Math.round(opacity[id] * 100)
  return {
    background: `linear-gradient(90deg, var(--brand-blue, #0060a0) ${pct}%, rgba(0, 0, 0, 0.18) ${pct}%)`,
  }
}
</script>

<template>
  <div ref="panelEl" class="layer-panel glass-panel liquid-glass" :style="{ left: panelPos.x + 'px', top: panelPos.y + 'px' }">
    <div class="lp-header" @mousedown="onHeaderDown">
      <div class="lp-title-wrap">
        <span class="lp-title">图层</span>
        <span
          class="lp-badge"
          :class="{ zero: visibleCount === 0 }"
          data-test="layer-visible-count"
          :title="`可见图层 ${visibleCount} / ${LAYER_IDS.length}`"
        >{{ visibleCount }}/{{ LAYER_IDS.length }}</span>
      </div>
      <div class="lp-actions">
        <button
          class="lp-icon-btn"
          type="button"
          data-test="layer-show-all"
          title="全部显示（透明度与视图一并重置为默认）"
          @click="showAll"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </button>
        <button
          class="lp-icon-btn"
          type="button"
          data-test="layer-show-none"
          title="全部隐藏（透明度与视图样式保留）"
          @click="hideAll"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" />
            <circle cx="12" cy="12" r="3" />
            <line x1="4" y1="4" x2="20" y2="20" />
          </svg>
        </button>
      </div>
    </div>
    <div class="lp-colhead" data-test="layer-colhead">
      <span class="lp-ch lp-ch-name">图层</span>
      <span class="lp-ch">可见</span>
      <span class="lp-ch">功能</span>
      <span class="lp-ch">透明度</span>
    </div>
    <div class="lp-list">
      <div
        v-for="id in LAYER_IDS"
        :key="id"
        class="lp-row"
        :class="{ 'is-hidden': !visible[id] }"
        :data-test="`layer-row-${id}`"
      >
        <div class="lp-name-cell">
          <span
            class="lp-swatch"
            :class="{ 'lp-swatch-spectrum': id === 'sweptCloud' }"
            :style="id === 'sweptCloud' ? spectrumSwatchStyle() : { background: colorOf(id) }"
          ></span>
          <span class="lp-name" :title="`聚焦 ${LAYER_VISUALS[id].label}`" @click="focusLayer(id)">
            {{ LAYER_VISUALS[id].label }}
          </span>
        </div>
        <button
          class="lp-eye"
          :class="{ off: !visible[id] }"
          type="button"
          :title="visible[id] ? '隐藏（Alt+点击：仅显示此层）' : '显示（Alt+点击：仅显示此层）'"
          :data-test="`layer-eye-${id}`"
          @click="toggleVisible(id, $event)"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" />
            <circle cx="12" cy="12" r="3" />
            <line v-if="!visible[id]" x1="4" y1="4" x2="20" y2="20" />
          </svg>
        </button>
        <div class="lp-func-cell">
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
        </div>
        <input
          class="lp-slider"
          type="range"
          min="0"
          max="1"
          step="0.05"
          :value="opacity[id]"
          :style="sliderBg(id)"
          :data-test="`layer-opacity-${id}`"
          :title="`透明度 ${Math.round(opacity[id] * 100)}%`"
          @input="changeOpacity(id, ($event.target as HTMLInputElement).valueAsNumber)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.layer-panel {
  position: fixed;
  /* 独立宽度：比共用 --float-panel-width（248px）宽一档，容纳四列 grid。
     玻璃风格由 glass-panel/liquid-glass 基类承担（theme.css，v6 定稿） */
  width: 264px;
  z-index: 16;
  overflow: hidden;
}
.lp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 34px;
  padding: 0 8px 0 12px;
  border-bottom: 1px solid var(--glass-divider);
  background: var(--glass-header);
  cursor: grab;
  user-select: none;
}
.lp-header:active {
  cursor: grabbing;
}
.lp-title-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}
.lp-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
/* 可见计数徽章：n/总；全隐时淡红警示 */
.lp-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 9px;
  background: rgba(0, 96, 160, 0.12);
  color: var(--brand-blue, #0060a0);
  font-variant-numeric: tabular-nums;
  line-height: 1.4;
}
.lp-badge.zero {
  background: rgba(200, 48, 48, 0.14);
  color: #c83030;
}
.lp-actions {
  display: flex;
  gap: 2px;
}
.lp-icon-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--brand-text-secondary, #5c6b7a);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, transform 0.1s ease;
}
.lp-icon-btn:hover {
  background: rgba(0, 96, 160, 0.12);
  color: var(--brand-blue, #0060a0);
}
.lp-icon-btn:active {
  transform: scale(0.92);
}
/* ── 表头 + 行共用四列 grid（严格对齐：名称 1fr / 可见 26 / 功能 42 / 透明度 58）── */
.lp-colhead,
.lp-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 26px 42px 58px;
  column-gap: 6px;
  align-items: center;
}
.lp-colhead {
  padding: 4px 10px 4px 20px; /* 左 20px = 面板 padding 4 + 色块 10 + gap 6，与名称文字起点对齐 */
  border-bottom: 1px solid var(--glass-divider);
  background: var(--glass-header);
}
.lp-ch {
  font-size: 10px;
  font-weight: 500;
  color: var(--brand-text-secondary, #5c6b7a);
  letter-spacing: 1px;
  text-align: center;
  user-select: none;
}
.lp-ch-name {
  text-align: left;
}
.lp-list {
  display: flex;
  flex-direction: column;
  padding: 6px 8px 10px;
}
.lp-row {
  height: 30px;
  padding: 0 4px;
  border-radius: 6px;
  transition: background 0.12s ease;
}
.lp-row:hover {
  background: rgba(0, 96, 160, 0.08);
}
/* 隐藏层整行变淡（视觉状态一眼可辨） */
.lp-row.is-hidden .lp-name,
.lp-row.is-hidden .lp-swatch {
  opacity: 0.42;
}
.lp-name-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
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
  min-width: 0;
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
  justify-self: center;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: var(--brand-text-secondary, #5c6b7a);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease, color 0.15s ease;
}
.lp-eye:hover {
  background: rgba(0, 96, 160, 0.1);
  color: var(--brand-blue, #0060a0);
}
.lp-eye.off {
  opacity: 0.4;
}
.lp-func-cell {
  display: flex;
  justify-content: center;
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
/* 透明度滑条：自定义轨道 + 品牌色进度（background 由 :style 渐变注入）+ 圆形拇指 */
.lp-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 58px;
  height: 4px;
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}
.lp-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid var(--brand-blue, #0060a0);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  transition: transform 0.12s ease;
}
.lp-slider::-webkit-slider-thumb:hover {
  transform: scale(1.18);
}
.lp-slider::-moz-range-thumb {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid var(--brand-blue, #0060a0);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}
</style>
