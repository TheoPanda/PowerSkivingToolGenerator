<script setup lang="ts">
/**
 * InterferenceLegend.vue — 干涉热力图图例（视口底部浮层）
 *
 * 等效产形齿轮「干涉」样式激活时显示：颜色-接触对应关系。
 * 渐变条 stops / 刻度 mm / 参考灰全部来自后端 interference_stats.legend
 * （单一权威源，前端不复制色阶公式）；pointer-events:none 不遮挡 3D 交互。
 */
import { computed, ref, watch, nextTick } from 'vue'
import { interferenceState } from '../composables/useInterferenceLegend'
import { installGlassRefraction } from './liquidGlass'

/** 图例根元素（液态玻璃折射安装点）. */
const legendEl = ref<HTMLElement | null>(null)

/** v-if 条件渲染 → 显示时 nextTick 安装（重显尺寸同则跳过）. */
watch(() => interferenceState.visible, async (v) => {
  if (!v) return
  await nextTick()
  if (legendEl.value) installGlassRefraction(legendEl.value, 'if-legend', { bezel: 20, strength: 12 })
})

/** 渐变条 CSS（stops t∈[0,1] → linear-gradient 位置）. */
const gradientCss = computed<string>(() => {
  const stops = interferenceState.stats?.legend?.stops
  if (!stops || stops.length === 0) return 'linear-gradient(90deg, #888, #ccc)'
  const seg = stops.map(
    (s) => `rgb(${Math.round(s.color[0] * 255)}, ${Math.round(s.color[1] * 255)}, ${Math.round(s.color[2] * 255)}) ${(s.t * 100).toFixed(1)}%`,
  )
  return `linear-gradient(90deg, ${seg.join(', ')})`
})

/** 刻度位置（d=−clamp→+clamp 均匀 → 位置 0..100%）. */
const ticks = computed<Array<{ pos: string; label: string }>>(() => {
  const t = interferenceState.stats?.legend?.ticks_mm
  if (!t || t.length !== 5) return []
  // 刻度 d ∈ [−clamp, +clamp] 线性映射到渐变条 0..100%
  const lo = t[0]
  const hi = t[4]
  return t.map((d) => ({
    pos: `${(((d - lo) / (hi - lo)) * 100).toFixed(1)}%`,
    label: d === 0 ? '0' : (d > 0 ? '+' : '') + d.toFixed(2),
  }))
})

/** 参考灰色块. */
const referenceCss = computed<string>(() => {
  const c = interferenceState.stats?.legend?.reference_color
  if (!c) return 'rgb(158, 158, 168)'
  return `rgb(${Math.round(c[0] * 255)}, ${Math.round(c[1] * 255)}, ${Math.round(c[2] * 255)})`
})

/** 最深侵入摘要（<0 = 过切深度，工程警示；≥0 = 无过切）. */
const minDSummary = computed<{ text: string; danger: boolean } | null>(() => {
  const d = interferenceState.stats?.min_d_mm
  if (d == null) return null
  return d < -1e-6
    ? { text: `最深过切 ${d.toFixed(2)} mm`, danger: true }
    : { text: '无过切', danger: false }
})
</script>

<template>
  <div
    v-if="interferenceState.visible && interferenceState.stats"
    ref="legendEl"
    class="if-legend glass-panel-sm liquid-glass"
    data-test="interference-legend"
  >
    <div class="if-title">
      干涉热力图
      <span
        v-if="minDSummary"
        class="if-summary"
        :class="{ danger: minDSummary.danger }"
        data-test="interference-legend-min"
      >{{ minDSummary.text }}</span>
    </div>

    <div class="if-body">
      <div class="if-bar-wrap">
        <div class="if-bar" :style="{ background: gradientCss }" data-test="interference-legend-bar"></div>
        <div class="if-ticks">
          <span
            v-for="(tk, i) in ticks"
            :key="i"
            class="if-tick"
            :style="{ left: tk.pos }"
          >{{ tk.label }}</span>
        </div>
        <div class="if-zones">
          <span class="if-zone">过切（侵入材料）</span>
          <span class="if-zone">临界 · 接触</span>
          <span class="if-zone">间隙</span>
        </div>
      </div>

      <div class="if-ref">
        <span class="if-ref-swatch" :style="{ background: referenceCss }"></span>
        齿宽外参考
      </div>
    </div>

    <div class="if-unit">符号距离 d [mm]：红 = 顶点侵入工件材料（过切）· 绿 = 相切接触 · 蓝 = 间隙</div>
  </div>
</template>

<style scoped>
.if-legend {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 12;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 8px 12px 7px;
  /* 玻璃风格由 glass-panel-sm/liquid-glass 基类承担（theme.css，v6 定稿） */
  user-select: none;
  pointer-events: none; /* 图例纯展示，不遮挡 3D 视口交互 */
}
.if-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: var(--brand-text, #1a2332);
}
.if-summary {
  font-size: 11px;
  font-weight: 500;
  color: #2e7d32; /* GO 绿：无过切 */
}
.if-summary.danger {
  color: #c62828; /* 警示红：存在过切 */
}

.if-body {
  display: flex;
  align-items: stretch;
  gap: 10px;
}
.if-bar-wrap {
  width: 300px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.if-bar {
  height: 12px;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.15);
}
.if-ticks {
  position: relative;
  height: 12px;
  font-size: 9px;
  color: var(--brand-text-secondary, #5c6b7a);
  font-variant-numeric: tabular-nums;
}
.if-tick {
  position: absolute;
  transform: translateX(-50%);
  white-space: nowrap;
}
.if-tick::before {
  content: '';
  position: absolute;
  top: -3px;
  left: 50%;
  width: 1px;
  height: 3px;
  background: rgba(0, 0, 0, 0.35);
}
.if-zones {
  display: flex;
  font-size: 9.5px;
  color: var(--brand-text-secondary, #5c6b7a);
}
.if-zones .if-zone:nth-child(1) { width: 30%; text-align: left; }
.if-zones .if-zone:nth-child(2) { width: 20%; text-align: center; }
.if-zones .if-zone:nth-child(3) { width: 50%; text-align: right; }

.if-ref {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  font-size: 9.5px;
  color: var(--brand-text-secondary, #5c6b7a);
  width: 56px;
}
.if-ref-swatch {
  width: 100%;
  height: 12px;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.15);
}

.if-unit {
  font-size: 9.5px;
  color: var(--brand-text-secondary, #5c6b7a);
}
</style>
