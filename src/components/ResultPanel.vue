<script setup lang="ts">
/**
 * ResultPanel.vue — 独立可拖拽「计算结果」面板
 *
 * - 承载 WorkpieceViewer 生成后的结果摘要 + 「查看齿轮规格」入口（原步骤2 内内容移出）
 * - 默认位窗口左上（左缘与 MainPanel 对齐，宽 320px）；仅标题栏可拖动，位置 localStorage 记忆
 * - 状态来自全局单例 useWorkpieceState；关闭后于原位显示「计算结果」胶囊，点击重开
 * - 收起（▼）成标题栏一条，仍可拖动
 */
import { computed, ref } from 'vue'
import { workpieceState, movePanel } from '../composables/useWorkpieceState'
import type { SpecPayload } from '../api'

const PANEL_W = 320
const HEADER_H = 36
const EDGE = 8

// ── 贴边吸附常量 ──
const SNAP_LEFT = 24 // 左贴：与 MainPanel 左缘对齐（MainPanel left:24px）
const SNAP_RIGHT = 24 // 右贴：与左同边距
const SNAP_TOP = 64 // 上贴：自绘标题栏(40px)下 + 24px 合理边距
const SNAP_BOTTOM = 24 // 下贴：底边距
const SNAP_THRESHOLD = 50 // 距离边沿多少 px 内触发吸附

/** 面板根元素（用于底部吸附取实际高度）. */
const panelEl = ref<HTMLElement | null>(null)

interface ResultRow {
  label: string
  value: string
}
/** 结果摘要 6 行（与后端 WorkpieceResult 同源）. */
const resultRows = computed<ResultRow[]>(() => {
  const r = workpieceState.result
  if (!r) return []
  return [
    { label: '齿顶圆 d_a', value: `${r.d_a.toFixed(2)} mm` },
    { label: '齿根圆 d_f', value: `${r.d_f.toFixed(2)} mm` },
    { label: '基圆半径 r_b', value: `${r.r_b.toFixed(3)} mm` },
    { label: '节圆半径 r_pw', value: `${r.r_pw.toFixed(3)} mm` },
    { label: '端面模数 m_t', value: `${r.m_t.toFixed(3)} mm` },
    { label: '端面压力角 α_t', value: `${r.alpha_t_deg.toFixed(2)}°` },
  ]
})

/** 身体区最大高度：随面板顶部位置自适应，保证不超出窗口底部，且不超过 60vh. */
const bodyStyle = computed<Record<string, string>>(() => ({
  'max-height': `min(60vh, calc(100vh - ${workpieceState.pos.y}px - ${HEADER_H}px - 16px))`,
}))

/** 拖动：仅标题栏；边界限制在窗口内；位置写入单例并持久化. */
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
  const nx = clampX(workpieceState.pos.x + dx)
  const ny = clampY(workpieceState.pos.y + dy)
  movePanel({ x: nx, y: ny })
}
function onWindowUp(): void {
  dragging = false
  window.removeEventListener('mousemove', onWindowMove)
  window.removeEventListener('mouseup', onWindowUp)
  document.body.style.userSelect = ''
  snapToEdge()
}
function clampX(x: number): number {
  return Math.min(Math.max(EDGE, x), Math.max(EDGE, window.innerWidth - PANEL_W - EDGE))
}
function clampY(y: number): number {
  return Math.min(Math.max(EDGE, y), Math.max(EDGE, window.innerHeight - HEADER_H - EDGE))
}

/** 释放时贴边吸附：左/右/上/下任一在阈值内即贴齐对应边（保留边距）. */
function snapToEdge(): void {
  const w = window.innerWidth
  const h = window.innerHeight
  const panelH = panelEl.value?.offsetHeight ?? HEADER_H
  let { x, y } = workpieceState.pos
  if (x <= SNAP_LEFT + SNAP_THRESHOLD) x = SNAP_LEFT
  else if (w - (x + PANEL_W) <= SNAP_RIGHT + SNAP_THRESHOLD) x = w - PANEL_W - SNAP_RIGHT
  if (y <= SNAP_TOP + SNAP_THRESHOLD) y = SNAP_TOP
  else if (h - (y + panelH) <= SNAP_BOTTOM + SNAP_THRESHOLD) y = h - panelH - SNAP_BOTTOM
  if (x !== workpieceState.pos.x || y !== workpieceState.pos.y) {
    movePanel({ x, y })
  }
}

function toggleCollapse(): void {
  workpieceState.collapsed = !workpieceState.collapsed
}
function closePanel(): void {
  workpieceState.open = false
}
function reopen(): void {
  workpieceState.open = true
  workpieceState.collapsed = false
}

/** 打开齿轮规格独立窗口（与 WorkpieceViewer 原逻辑一致：JSON 深拷贝避开 reactive Proxy）. */
function openSpecWindow(): void {
  const spec = workpieceState.spec
  if (!spec) return
  if (window.electronAPI) {
    void window.electronAPI.openSpecWindow(JSON.parse(JSON.stringify(spec)) as SpecPayload)
  }
}
</script>

<template>
  <!-- 关闭后的唤起胶囊（原位，需已随模型显示唤出过） -->
  <button
    v-if="!workpieceState.open && workpieceState.revealed"
    class="result-capsule"
    :style="{ left: workpieceState.pos.x + 'px', top: workpieceState.pos.y + 'px' }"
    @click="reopen"
  >计算结果</button>

  <!-- 结果面板 -->
  <div
    v-else-if="workpieceState.open"
    ref="panelEl"
    class="result-panel"
    :class="{ 'is-collapsed': workpieceState.collapsed }"
    :style="{ left: workpieceState.pos.x + 'px', top: workpieceState.pos.y + 'px' }"
  >
    <div class="rp-header" @mousedown="onHeaderDown">
      <span class="rp-title">计算结果</span>
      <span class="rp-spacer"></span>
      <button class="rp-btn" title="收起" @click.stop="toggleCollapse">
        {{ workpieceState.collapsed ? '▲' : '▼' }}
      </button>
      <button class="rp-btn" title="关闭" @click.stop="closePanel">×</button>
    </div>

    <div v-if="!workpieceState.collapsed" class="rp-body" :style="bodyStyle">
      <div class="result-table">
        <div v-for="row in resultRows" :key="row.label" class="result-row">
          <span class="result-label">{{ row.label }}</span>
          <span class="result-value">{{ row.value }}</span>
        </div>
      </div>
      <div class="result-actions">
        <button class="glass-btn spec-view-btn" type="button" data-test="view-spec" @click="openSpecWindow">
          查看齿轮规格
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.result-panel {
  position: fixed;
  width: 320px;
  z-index: 16;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid var(--brand-border-light, #e4e9ef);
  border-radius: 12px;
  box-shadow: var(--brand-shadow-md, 0 2px 8px rgba(0, 64, 128, 0.12));
  overflow: hidden;
  color: var(--brand-text, #1a2332);
}
.rp-header {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 8px 0 12px;
  cursor: grab;
  user-select: none;
  border-bottom: 1px solid var(--brand-border-light, #e4e9ef);
  background: rgba(255, 255, 255, 0.55);
}
.rp-header:active {
  cursor: grabbing;
}
.rp-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-text, #1a2332);
  letter-spacing: 0.5px;
}
.rp-spacer {
  flex: 1;
}
.rp-btn {
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--brand-text-secondary, #5c6b7a);
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
}
.rp-btn:hover {
  background: rgba(0, 96, 160, 0.12);
  color: var(--brand-blue, #0060a0);
}
.rp-body {
  padding: 12px;
  overflow-y: auto;
  overflow-x: hidden;
}
.result-table {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.result-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.result-label {
  font-size: 12px;
  color: var(--brand-text-secondary, #5c6b7a);
}
.result-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--brand-text, #1a2332);
  font-variant-numeric: tabular-nums;
}
.result-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.spec-view-btn {
  padding: 6px 16px;
  font-size: 12px;
}
.is-collapsed .rp-body {
  display: none;
}
/* 唤起胶囊：整体白色，蓝色仅在悬停（交互特征）时出现 */
.result-capsule {
  position: fixed;
  z-index: 16;
  padding: 6px 12px;
  border: 1px solid var(--brand-border-light, #e4e9ef);
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: var(--brand-text, #1a2332);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: var(--brand-shadow-sm, 0 1px 4px rgba(0, 64, 128, 0.14));
  cursor: pointer;
  transition: color 0.15s var(--brand-transition-smooth, cubic-bezier(0.22, 0.61, 0.36, 1)),
              transform 0.15s var(--brand-transition-smooth, cubic-bezier(0.22, 0.61, 0.36, 1));
}
.result-capsule:hover {
  color: var(--brand-blue, #0060a0);
  border-color: var(--brand-blue-light, #4080c0);
  transform: translateY(-1px);
}
</style>
