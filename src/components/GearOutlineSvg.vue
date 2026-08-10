<script setup lang="ts">
/**
 * GearOutlineSvg.vue — 齿轮2D整体轮廓 + 缩放/平移/悬停
 *
 * 消费 spec.outline（teeth 每齿闭合点列 / circles 三圆）。
 * 白底 SVG：
 *   - teeth 每齿一个闭合 path（fill=none，pointer-events=all），悬停高亮 + tooltip 齿序号
 *   - 齿顶圆/齿根圆 细实线，分度圆 点划线
 *   - 缩放平移 = 更新 viewBox（滚轮 1.1 倍 / 拖拽 cx cy / 按钮）
 *   - 初始化按 circles.tip_radius 算 bbox + 5% 边距
 */
import { ref, computed } from 'vue'
import type { OutlineSpec, Point2 } from '../api'
import { useSvgViewport } from '../composables/useSvgViewport'

const props = defineProps<{
  outline: OutlineSpec
}>()

/** 悬停齿序号（1-based），null 表示无. */
const hoveredTooth = ref<number | null>(null)
/** tooltip 位置（用户坐标内）. */
const tipPos = ref<{ x: number; y: number }>({ x: 0, y: 0 })

/** 初始化 viewBox：局部视图——仅最右端齿廓 + 右侧四尺寸值列（突出直径标注）. */
function initialViewBox(): [number, number, number, number] {
  const r = props.outline.circles.tip_radius
  const x0 = r * 0.55
  const yHalf = r * 0.42
  const lx = r * 1.35
  const labelHalf = r * 0.26
  return [x0, -yHalf, lx + labelHalf - x0, 2 * yHalf]
}

/** 视口缩放/平移/复位：来自 useSvgViewport 深模块（与 ToothProfileSvg 共享）. */
const { viewBox, onWheel, startPan, zoomAt, reset } = useSvgViewport(initialViewBox())

/** 四圆标注（齿顶/分度/基/齿根圆，直径自上而下排列），最右端引线 + 起始实心点. */
const circleLabels = computed(() => {
  const c = props.outline.circles
  const fs = c.tip_radius * 0.05
  const lx = c.tip_radius * 1.35
  const dotR = fs * 0.45
  // 从上到下按直径降序：齿顶 → 分度 → 基 → 齿根
  const rows = [0.32, 0.11, -0.11, -0.32]
  const entries = [
    { key: 'tip', r: c.tip_radius, label: `齿顶圆 φ${(2 * c.tip_radius).toFixed(1)}`, color: '#4080C0' },
    { key: 'pitch', r: c.pitch_radius, label: `分度圆 φ${(2 * c.pitch_radius).toFixed(1)}`, color: '#7A8B99' },
    { key: 'base', r: c.base_radius, label: `基圆 φ${(2 * c.base_radius).toFixed(1)}`, color: '#B8C2CC' },
    { key: 'root', r: c.root_radius, label: `齿根圆 φ${(2 * c.root_radius).toFixed(1)}`, color: '#A0AAB4' },
  ]
  return entries.map((en, i) => {
    const y = rows[i] * c.tip_radius
    // 圆上对应行高处的点（引线起点，实心点落位）
    const u = Math.min(1, Math.max(-1, y / en.r))
    const ang = Math.asin(u)
    const start: Point2 = [en.r * Math.cos(ang), y]
    const end: Point2 = [lx, y]
    return { ...en, fs, dotR, start, end }
  })
})

/** 每齿闭合 path d. */
const toothPaths = computed<string[]>(() =>
  props.outline.teeth.map((pts) => {
    if (pts.length === 0) return ''
    let d = `M ${pts[0][0].toFixed(4)} ${pts[0][1].toFixed(4)}`
    for (let i = 1; i < pts.length; i++) {
      d += ` L ${pts[i][0].toFixed(4)} ${pts[i][1].toFixed(4)}`
    }
    return d + ' Z'
  }),
)

/** 用户坐标 → 屏幕(SVG 视口) 坐标. 用于定位 tooltip. */
function userToScreen(p: Point2): { x: number; y: number } {
  // 假设 svg 宽高与 viewBox 成比例（1:1），tooltip 用百分比偏移更稳
  const [minX, minY, w, h] = viewBox.value
  return {
    x: ((p[0] - minX) / w) * 100,
    y: ((p[1] - minY) / h) * 100,
  }
}

/** 按钮平移（缩放/复位来自 useSvgViewport）. */
function panLeft(): void {
  const [minX, minY, w] = viewBox.value
  viewBox.value = [minX - w * 0.1, minY, w, viewBox.value[3]]
}
function panRight(): void {
  const [minX, minY, w, h] = viewBox.value
  viewBox.value = [minX + w * 0.1, minY, w, h]
}
function panUp(): void {
  const [, minY, w, h] = viewBox.value
  viewBox.value = [viewBox.value[0], minY - h * 0.1, w, h]
}
function panDown(): void {
  const [, minY, w, h] = viewBox.value
  viewBox.value = [viewBox.value[0], minY + h * 0.1, w, h]
}

/** 悬停高亮 + tooltip. */
function onToothEnter(i: number, _e: MouseEvent, pts: Point2[]): void {
  hoveredTooth.value = i + 1
  const cx = pts[Math.floor(pts.length / 2)]
  const screen = userToScreen(cx)
  tipPos.value = {
    x: screen.x,
    y: screen.y,
  }
}
function onToothLeave(): void {
  hoveredTooth.value = null
}
</script>

<template>
  <div class="gear-outline">
    <div class="outline-controls">
      <button class="ctl-btn" title="放大" @click="zoomAt(0.9)">＋</button>
      <button class="ctl-btn" title="缩小" @click="zoomAt(1 / 0.9)">－</button>
      <button class="ctl-btn" title="复位" @click="reset">⤾</button>
      <span class="ctl-sep"></span>
      <button class="ctl-btn" title="左移" @click="panLeft">←</button>
      <button class="ctl-btn" title="右移" @click="panRight">→</button>
      <button class="ctl-btn" title="上移" @click="panUp">↑</button>
      <button class="ctl-btn" title="下移" @click="panDown">↓</button>
    </div>
    <svg
      class="outline-svg"
      :viewBox="viewBox.join(' ')"
      width="100%"
      height="100%"
      xmlns="http://www.w3.org/2000/svg"
      @wheel="onWheel"
      @mousedown="startPan"
    >
      <rect x="-100000" y="-100000" width="200000" height="200000" fill="#ffffff"></rect>
      <!-- 齿圈轮廓：每齿一个闭合 path -->
      <g class="teeth-group">
        <path
          v-for="(d, i) in toothPaths"
          :key="i"
          :d="d"
          class="tooth-path"
          :class="{ 'tooth-hover': hoveredTooth === i + 1 }"
          fill="none"
          stroke="#C4CCD4"
          stroke-width="1.2"
          vector-effect="non-scaling-stroke"
          pointer-events="all"
          :data-tooth="i + 1"
          @mouseenter="onToothEnter(i, $event, outline.teeth[i])"
          @mouseleave="onToothLeave"
        ></path>
      </g>
      <!-- 四圆（齿顶/齿根/分度/基）全部实线 -->
      <circle
        :r="outline.circles.tip_radius"
        cx="0"
        cy="0"
        class="circle-tip"
        fill="none"
        stroke="#4080C0"
        stroke-width="0.8"
        vector-effect="non-scaling-stroke"
      ></circle>
      <circle
        :r="outline.circles.root_radius"
        cx="0"
        cy="0"
        class="circle-root"
        fill="none"
        stroke="#A0AAB4"
        stroke-width="0.8"
        vector-effect="non-scaling-stroke"
      ></circle>
      <circle
        :r="outline.circles.pitch_radius"
        cx="0"
        cy="0"
        class="circle-pitch"
        fill="none"
        stroke="#7A8B99"
        stroke-width="0.8"
        vector-effect="non-scaling-stroke"
      ></circle>
      <circle
        :r="outline.circles.base_radius"
        cx="0"
        cy="0"
        class="circle-base"
        fill="none"
        stroke="#B8C2CC"
        stroke-width="0.8"
        vector-effect="non-scaling-stroke"
      ></circle>
      <!-- 四圆标注（引线 + 文字） -->
      <g class="circle-labels">
        <g v-for="l in circleLabels" :key="l.key" class="circle-label" :data-label="l.key">
          <!-- 引线起始：实心点（落于所在圆上） -->
          <circle
            class="leader-dot"
            :cx="l.start[0]"
            :cy="l.start[1]"
            :r="l.dotR"
            :fill="l.color"
            stroke="none"
          ></circle>
          <line
            :x1="l.start[0]"
            :y1="l.start[1]"
            :x2="l.end[0]"
            :y2="l.end[1]"
            :stroke="l.color"
            stroke-width="0.8"
            vector-effect="non-scaling-stroke"
          ></line>
          <text :x="l.end[0]" :y="l.end[1]" text-anchor="middle" :fill="l.color" :font-size="l.fs">
            {{ l.label }}
          </text>
        </g>
      </g>
    </svg>
    <!-- tooltip：HTML 覆盖层（百分比定位，避免 SVG 坐标系混用） -->
    <div
      v-if="hoveredTooth !== null"
      class="tooth-tooltip"
      :style="{ left: tipPos.x + '%', top: tipPos.y + '%' }"
    >
      齿 {{ hoveredTooth }}
    </div>
    <div class="outline-hint">拖拽平移 · 滚轮缩放 · 悬停查看齿序号</div>
  </div>
</template>

<style scoped>
.gear-outline {
  position: relative;
  width: 100%;
  height: 100%;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
}
.outline-controls {
  position: absolute;
  top: 6px;
  left: 6px;
  z-index: 3;
  display: flex;
  gap: 3px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--brand-border-light, #e4e9ef);
  border-radius: 6px;
  padding: 2px 4px;
}
.ctl-btn {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--brand-text, #1a2332);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
}
.ctl-btn:hover {
  background: rgba(0, 96, 160, 0.1);
  color: var(--brand-blue, #0060a0);
}
.ctl-sep {
  width: 1px;
  background: var(--brand-border-light, #e4e9ef);
  margin: 2px 1px;
}
.outline-svg {
  display: block;
  cursor: grab;
}
.outline-svg:active {
  cursor: grabbing;
}
.tooth-path {
  transition: stroke 0.12s;
}
.tooth-path:hover {
  stroke: var(--brand-blue, #0060a0);
  stroke-width: 1.6;
}
.tooth-hover {
  stroke: var(--brand-blue, #0060a0);
  stroke-width: 1.6;
  filter: drop-shadow(0 0 4px rgba(0, 96, 160, 0.4));
}
.outline-hint {
  position: absolute;
  bottom: 6px;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 10px;
  color: var(--brand-text-disabled, #a0aab4);
  pointer-events: none;
}
.tooth-tooltip {
  position: absolute;
  transform: translate(-50%, -150%);
  background: #004080;
  color: #ffffff;
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 4px;
  pointer-events: none;
  white-space: nowrap;
  z-index: 4;
}
</style>
