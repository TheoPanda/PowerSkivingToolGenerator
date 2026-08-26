<script setup lang="ts">
/**
 * SimulationPanel.vue — 反向包络运动仿真控制面板
 *
 * 拖拽浮窗，提供：播放/暂停（乒乓）、重置、速度选择、φ_t 滑条、单齿/全齿切换。
 * 动画数据由 WorkpieceViewer 请求后通过 openSimulation() 传入。
 */
import { inject, reactive, ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import { GEAR_VIEWPORT_KEY, type GearViewport } from '../three/gearViewport'
import {
  simState, currentPhiTDeg, angleRange, sectionAvailable, sectionZmm,
  togglePlay, resetPhi, setPhi, setSpeed, toggleGearMode, toggleSpectrumMode,
  toggleSectionMode, setSectionIz, closeSimulation,
} from '../composables/useSimulation'
import { PANEL_MARGIN, RIGHT_COLUMN_TOP } from './panelLayout'
import { installGlassRefraction } from './liquidGlass'

const viewportRef = inject<Ref<GearViewport | null>>(GEAR_VIEWPORT_KEY, ref(null))

// ── 面板拖拽（复用 LayerPanel 模式；默认位于图层面板下方，避免遮盖其标题栏） ──
const PANEL_W = 248
const HEADER_H = 34
const EDGE = 8
const POS_KEY = 'pst.sim-panel.pos'
/** 面板根元素（液态玻璃折射安装点）. */
const panelEl = ref<HTMLElement | null>(null)
/** 默认位置：右对齐视图面板（右缘统一边距），图层面板正下方
 * （图层面板底 ≈ RIGHT_COLUMN_TOP 218 + 高 ~378 → 596，留 8px 间隙）. */
function defaultPos(): { x: number; y: number } {
  return { x: window.innerWidth - PANEL_W - PANEL_MARGIN, y: 604 }
}
function loadPos(): { x: number; y: number } {
  try {
    const raw = localStorage.getItem(POS_KEY)
    if (raw) {
      const p = JSON.parse(raw) as { x: number; y: number }
      if (typeof p?.x === 'number' && typeof p?.y === 'number') return p
    }
  } catch { /* ignore */ }
  return defaultPos()
}
// reactive 包装（同 LayerPanel）：否则 :style 绑定不响应拖拽坐标更新，面板视觉上不可拖。
// 持久化旧值加载即 clamp（y 下限 RIGHT_COLUMN_TOP：右列面板不得盖住视图切换面板）
const _initPos = loadPos()
const panelPos = reactive<{ x: number; y: number }>({
  x: clamp(_initPos.x, EDGE, window.innerWidth - PANEL_W - PANEL_MARGIN),
  y: clamp(_initPos.y, RIGHT_COLUMN_TOP, window.innerHeight - HEADER_H - EDGE),
})

let dragging = false
let lastX = 0
let lastY = 0
function onHeaderDown(e: MouseEvent): void {
  if ((e.target as HTMLElement).closest('button')) return
  dragging = true
  lastX = e.clientX
  lastY = e.clientY
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
  document.body.style.userSelect = 'none'
}
function onMove(e: MouseEvent): void {
  if (!dragging) return
  panelPos.x = clamp(panelPos.x + e.clientX - lastX, EDGE, window.innerWidth - PANEL_W - PANEL_MARGIN)
  panelPos.y = clamp(panelPos.y + e.clientY - lastY, RIGHT_COLUMN_TOP, window.innerHeight - HEADER_H - EDGE)
  lastX = e.clientX
  lastY = e.clientY
}
function onUp(): void {
  dragging = false
  window.removeEventListener('mousemove', onMove)
  window.removeEventListener('mouseup', onUp)
  document.body.style.userSelect = ''
  try { localStorage.setItem(POS_KEY, JSON.stringify(panelPos)) } catch { /* ignore */ }
}
function clamp(v: number, lo: number, hi: number): number {
  return Math.min(Math.max(lo, v), hi)
}

// 窗口 resize
let prevW = window.innerWidth
function onResize(): void {
  panelPos.x = clamp(panelPos.x + (window.innerWidth - prevW), EDGE, window.innerWidth - PANEL_W - PANEL_MARGIN)
  prevW = window.innerWidth
}

// ── 滑条拖拽（φ_t 角度域 ±span，1° 步进）→ 同步到 viewport ──────────
function onSliderInput(e: Event): void {
  const deg = (e.target as HTMLInputElement).valueAsNumber
  setPhi(deg)
  if (simState.spectrumMode) {
    viewportRef.value?.setSpectrumReveal(simState.phiDeg)
  } else {
    viewportRef.value?.setAnimPhi(simState.phiDeg)
  }
}

// ── 播放/暂停 → 同步到 viewport ──────────────────────────────────────
function onTogglePlay(): void {
  togglePlay()
  viewportRef.value?.setAnimPlaying(simState.playing)
}

// ── 速度切换 ──────────────────────────────────────────────────────────
const SPEEDS = [0.5, 1, 2, 4]
function cycleSpeed(): void {
  const idx = SPEEDS.indexOf(simState.speed)
  const next = SPEEDS[(idx + 1) % SPEEDS.length]
  setSpeed(next)
  viewportRef.value?.setAnimSpeed(next)
}

// ── 单齿/全齿 ────────────────────────────────────────────────────────
function onToggleGearMode(): void {
  toggleGearMode()
  viewportRef.value?.setAnimGearMode(simState.gearMode)
}

// ── 截面切片（沿齿向选廓线平面）──────────────────────────────────────
function onToggleSection(): void {
  toggleSectionMode()
  viewportRef.value?.setAnimSection(simState.sectionMode ? simState.sectionIz : null)
}

function onSectionInput(e: Event): void {
  const v = (e.target as HTMLInputElement).valueAsNumber
  setSectionIz(v)
  if (simState.sectionMode) viewportRef.value?.setAnimSection(v)
}

// ── 光谱/动画切换 ────────────────────────────────────────────────────
function onToggleSpectrumMode(): void {
  toggleSpectrumMode()
  viewportRef.value?.setSpectrumMode(simState.spectrumMode)
  if (!simState.spectrumMode) {
    // 切回动画模式时，同步当前 φ 到 viewport
    viewportRef.value?.setAnimPhi(simState.phiDeg)
  }
}

// ── 关闭 ─────────────────────────────────────────────────────────────
function onClose(): void {
  viewportRef.value?.clearAnimMesh()
  closeSimulation()
}

// ── 重置 ─────────────────────────────────────────────────────────────
function onReset(): void {
  resetPhi()
  if (simState.spectrumMode) {
    viewportRef.value?.setSpectrumReveal(simState.phiDeg)
  } else {
    viewportRef.value?.setAnimPhi(simState.phiDeg)
  }
  viewportRef.value?.setAnimPlaying(false)
}

onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))

// 液态玻璃折射：v-if 打开时元素才出现 → watch open 后 nextTick 安装（重开尺寸同则跳过）
watch(() => simState.open, async (open) => {
  if (!open) return
  await nextTick()
  if (panelEl.value) installGlassRefraction(panelEl.value, 'sim-panel')
})
</script>

<template>
  <div
    v-if="simState.open"
    ref="panelEl"
    class="sim-panel glass-panel liquid-glass"
    :style="{ left: panelPos.x + 'px', top: panelPos.y + 'px' }"
    data-test="simulation-panel"
  >
    <div class="sp-header" title="按住标题栏拖动移动" @mousedown="onHeaderDown">
      <span class="sp-title">仿真动画</span>
      <button class="sp-close" type="button" data-test="sim-close" @click="onClose">✕</button>
    </div>

    <div class="sp-body">
      <!-- 动画/光谱模式切换 -->
      <div class="sp-row sp-mode-row">
        <button
          class="sp-mode-btn"
          :class="{ active: !simState.spectrumMode }"
          type="button"
          data-test="sim-mode-anim"
          @click="simState.spectrumMode && onToggleSpectrumMode()"
        >动画</button>
        <button
          class="sp-mode-btn"
          :class="{ active: simState.spectrumMode }"
          type="button"
          data-test="sim-mode-spectrum"
          @click="!simState.spectrumMode && onToggleSpectrumMode()"
        >光谱</button>
      </div>

      <!-- 播放控件 -->
      <div class="sp-row sp-controls">
        <button
          class="sp-btn"
          type="button"
          :title="simState.playing ? '暂停' : '播放'"
          data-test="sim-play"
          @click="onTogglePlay"
        >
          <svg v-if="!simState.playing" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <polygon points="6,4 20,12 6,20" />
          </svg>
          <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <rect x="5" y="4" width="5" height="16" />
            <rect x="14" y="4" width="5" height="16" />
          </svg>
        </button>
        <button class="sp-btn" type="button" title="重置" data-test="sim-reset" @click="onReset">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="1 4 1 10 7 10" />
            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
          </svg>
        </button>
        <button class="sp-speed" type="button" title="切换速度" data-test="sim-speed" @click="cycleSpeed">
          {{ simState.speed }}x
        </button>
      </div>

      <!-- φ_t 滑条（角度域 ±span、1° 步进；合成模式 span=360°） -->
      <div class="sp-row sp-slider-row">
        <span class="sp-label">φ_t</span>
        <input
          class="sp-slider"
          type="range"
          :min="angleRange.min"
          :max="angleRange.max"
          step="1"
          :value="simState.phiDeg"
          data-test="sim-slider"
          @input="onSliderInput"
        />
        <span class="sp-value">{{ currentPhiTDeg.toFixed(1) }}°</span>
      </div>

      <!-- 单齿/全齿 -->
      <div class="sp-row sp-mode-row">
        <button
          class="sp-mode-btn"
          :class="{ active: simState.gearMode === 'single' }"
          type="button"
          data-test="sim-mode-single"
          @click="simState.gearMode !== 'single' && onToggleGearMode()"
        >单齿</button>
        <button
          class="sp-mode-btn"
          :class="{ active: simState.gearMode === 'full' }"
          type="button"
          data-test="sim-mode-full"
          @click="simState.gearMode !== 'full' && onToggleGearMode()"
        >全齿</button>
      </div>

      <!-- 截面切片：沿齿向选廓线平面（后端 anim 元数据可用时显示） -->
      <div v-if="sectionAvailable" class="sp-row sp-section-row">
        <button
          class="sp-mode-btn sp-section-btn"
          :class="{ active: simState.sectionMode }"
          type="button"
          title="沿齿向选廓线平面（截面模式下仿真只作用于该层齿廓）"
          data-test="sim-section-toggle"
          @click="onToggleSection"
        >截面</button>
        <input
          v-if="simState.sectionMode"
          class="sp-slider"
          type="range"
          min="0"
          :max="Math.max(0, (simState.animData?.layer_zs?.length ?? 1) - 1)"
          step="1"
          :value="simState.sectionIz"
          data-test="sim-section-slider"
          @input="onSectionInput"
        />
        <span v-if="simState.sectionMode" class="sp-value" data-test="sim-section-z">
          z={{ sectionZmm !== null ? sectionZmm.toFixed(1) : '?' }}mm
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sim-panel {
  position: fixed;
  width: var(--float-panel-width, 248px);
  z-index: 16;
  overflow: hidden;
  /* 玻璃风格由 glass-panel/liquid-glass 基类承担（theme.css，v6 定稿） */
}
.sp-header {
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
.sp-header:active { cursor: grabbing; }
.sp-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.sp-close {
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--brand-text, #1a2332);
  font-size: 13px;
  cursor: pointer;
  padding: 2px 6px;
  line-height: 1;
}
.sp-close:hover { background: rgba(0, 0, 0, 0.08); }

.sp-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 10px 10px;
}
.sp-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 播放控件 */
.sp-controls { gap: 4px; }
.sp-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 26px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.5);
  color: var(--brand-text, #1a2332);
  cursor: pointer;
}
.sp-btn:hover { background: rgba(0, 96, 160, 0.1); }
.sp-btn:active { background: rgba(0, 96, 160, 0.2); }

.sp-speed {
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.5);
  color: var(--brand-blue, #0060a0);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  padding: 3px 8px;
  margin-left: auto;
}
.sp-speed:hover { background: rgba(0, 96, 160, 0.1); }

/* 滑条 */
.sp-slider-row { gap: 8px; }
.sp-label {
  font-size: 11px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.5);
  min-width: 20px;
}
.sp-slider {
  flex: 1;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: rgba(0, 0, 0, 0.12);
  border-radius: 2px;
  outline: none;
}
.sp-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--brand-blue, #0060a0);
  cursor: pointer;
}
.sp-value {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  min-width: 40px;
  text-align: right;
}

/* 单齿/全齿切换 + 动画/光谱切换 */
.sp-mode-row { gap: 4px; }
/* 截面切片行：按钮 + 层滑条 + z 值 */
.sp-section-row { gap: 8px; }
.sp-section-btn { flex: none; width: 48px; }
.sp-mode-btn {
  flex: 1;
  height: 26px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.4);
  color: var(--brand-text, #1a2332);
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s;
}
.sp-mode-btn:hover { background: rgba(0, 96, 160, 0.08); }
.sp-mode-btn.active {
  background: var(--brand-blue, #0060a0);
  color: #fff;
  border-color: transparent;
}
</style>
