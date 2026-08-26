<script setup lang="ts">
/**
 * ViewCube.vue — 右上角视图控制面板
 *
 * 实体/线框渲染模式切换（与 MainView 合并而来）+ 6 个标准视图按钮（Z-up CAD 坐标系）
 * + Home 恢复默认视角。视图按钮带等轴立方体图标：可见三面（顶/前/右）高亮对应面，
 * 隐藏三面（底/后/左）叠加方位箭头示意。
 */
import { inject, ref, onMounted, type Ref } from 'vue'
import { GEAR_VIEWPORT_KEY, type GearViewport, type StandardView, type RenderMode } from '../three/gearViewport'
import { installGlassRefraction } from './liquidGlass'

const viewportRef = inject<Ref<GearViewport | null>>(GEAR_VIEWPORT_KEY, ref(null))

/** 面板根元素（液态玻璃折射安装点）. */
const panelEl = ref<HTMLElement | null>(null)

onMounted(() => {
  if (panelEl.value) installGlassRefraction(panelEl.value, 'view-switcher', { bezel: 18, strength: 10 })
})

/** 实体/线框模式（MainView 持有并传入；切换经 emit 回 MainView 下发 viewport）. */
const props = defineProps<{ renderMode: RenderMode }>()
const emit = defineEmits<{ (e: 'set-render-mode', mode: RenderMode): void }>()

/** 等轴立方体顶点（16×16 viewBox）. */
const CUBE = {
  top: '8,2 2.8,5.2 8,8.4 13.2,5.2',
  front: '2.8,5.2 2.8,11.6 8,14.8 8,8.4',
  right: '13.2,5.2 8,8.4 8,14.8 13.2,11.6',
  edges: 'M8 2 L2.8 5.2 L2.8 11.6 L8 14.8 L13.2 11.6 L13.2 5.2 Z M2.8 5.2 L8 8.4 L13.2 5.2 M8 8.4 L8 14.8',
}

/** 6 个标准视图：可见面高亮（faces）或方位箭头（arrow）. */
const VIEWS: Array<{
  view: StandardView
  label: string
  title: string
  faces?: string[]
  arrow?: 'down' | 'left' | 'rotate'
}> = [
  { view: 'top', label: '顶', title: '顶视图（俯视 +Z）', faces: [CUBE.top] },
  { view: 'bottom', label: '底', title: '底视图（仰视 −Z）', arrow: 'down' },
  { view: 'front', label: '前', title: '前视图（从 −Y 看）', faces: [CUBE.front] },
  { view: 'back', label: '后', title: '后视图（从 +Y 看）', arrow: 'rotate' },
  { view: 'left', label: '左', title: '左视图（从 −X 看）', arrow: 'left' },
  { view: 'right', label: '右', title: '右视图（从 +X 看）', faces: [CUBE.right] },
]

/** 方位箭头 path（叠加在立方体上，白底描边保证与线框分离）. */
const ARROW_PATH: Record<'down' | 'left' | 'rotate', string> = {
  down: 'M8 4.5 V11 M5.2 8.6 L8 11.4 L10.8 8.6',
  left: 'M11.5 7.7 H4.5 M7.3 4.9 L4.5 7.7 L7.3 10.5',
  rotate: 'M12 5 A4.4 4.4 0 1 0 12.6 10.2',
}

function onSwitch(view: StandardView): void {
  viewportRef.value?.setStandardView(view)
}

function onHome(): void {
  viewportRef.value?.resetView()
}
</script>

<template>
  <div ref="panelEl" class="view-switcher glass-panel-sm liquid-glass" data-test="view-cube">
    <!-- 实体/线框渲染模式（原 MainView 右上角切换，并入本面板） -->
    <div class="vs-modes">
      <button
        class="vs-mode-btn"
        :class="{ active: props.renderMode === 'solid' }"
        type="button"
        data-test="vs-mode-solid"
        @click="emit('set-render-mode', 'solid')"
      >
        <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
          <path d="M8 2 L13.5 5 V11 L8 14 L2.5 11 V5 Z" fill="rgba(0,96,160,0.85)" stroke="none" />
        </svg>
        实体
      </button>
      <button
        class="vs-mode-btn"
        :class="{ active: props.renderMode === 'xray' }"
        type="button"
        data-test="vs-mode-xray"
        @click="emit('set-render-mode', 'xray')"
      >
        <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
          <path
            d="M8 2 L13.5 5 V11 L8 14 L2.5 11 V5 Z M2.5 5 L8 8 L13.5 5 M8 8 V14"
            fill="none" stroke="currentColor" stroke-width="1.2"
          />
        </svg>
        线框
      </button>
    </div>

    <!-- Home 恢复默认视角 -->
    <button
      class="vs-home"
      type="button"
      title="恢复默认视角"
      data-test="vc-home"
      @click="onHome"
    >
      <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
        <path
          d="M2.8 8.2 L8 3.4 L13.2 8.2 M4.4 7.4 V12.6 H11.6 V7.4"
          fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
        />
      </svg>
      默认视角
    </button>

    <!-- 6 标准视图（上下/前后/左右 三对分组） -->
    <div class="vs-grid">
      <button
        v-for="item in VIEWS"
        :key="item.view"
        class="vs-btn"
        type="button"
        :title="item.title"
        :data-test="`vc-face-${item.view}`"
        @click="onSwitch(item.view)"
      >
        <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
          <!-- 高亮面（可见方向） -->
          <polygon
            v-for="(f, fi) in item.faces ?? []"
            :key="fi"
            :points="f"
            fill="rgba(0,96,160,0.82)"
          />
          <!-- 立方体线框 -->
          <path :d="CUBE.edges" fill="none" stroke="rgba(26,35,50,0.75)" stroke-width="1" stroke-linejoin="round" />
          <!-- 方位箭头（隐藏方向：白底 halo + 品牌蓝） -->
          <template v-if="item.arrow">
            <path :d="ARROW_PATH[item.arrow]" fill="none" stroke="#fff" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round" />
            <path :d="ARROW_PATH[item.arrow]" fill="none" stroke="#0060a0" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
            <polygon
              v-if="item.arrow === 'rotate'"
              points="12,2.4 13.1,6.6 9,5.6"
              fill="#0060a0" stroke="#fff" stroke-width="0.8"
            />
          </template>
        </svg>
        <span class="vs-label">{{ item.label }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.view-switcher {
  position: absolute;
  top: 12px;
  /* right 与浮动面板贴边/ MainPanel 左缘统一 24px（panelLayout.ts PANEL_MARGIN 注释互指）。
     玻璃风格由 glass-panel-sm/liquid-glass 基类承担（theme.css，v6 定稿） */
  right: 24px;
  z-index: 12;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 5px;
  user-select: none;
}

/* 实体/线框分段（玻璃内嵌子块） */
.vs-modes {
  display: flex;
  gap: 2px;
  padding: 2px;
  border-radius: 7px;
  background: var(--glass-block);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.30);
}
.vs-mode-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 24px;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: var(--brand-text-secondary, #5c6b7a);
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.vs-mode-btn:hover { background: rgba(0, 96, 160, 0.1); }
.vs-mode-btn.active {
  background: var(--brand-blue, #0060a0);
  color: #fff;
}

/* Home */
.vs-home {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  height: 24px;
  border: 1px solid var(--glass-block-border);
  border-radius: 6px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.40) 0%, rgba(255, 255, 255, 0.20) 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.45);
  color: var(--brand-text, #1a2332);
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s;
}
.vs-home:hover { background: rgba(0, 96, 160, 0.1); }

/* 3 行 × 2 列视图网格 */
.vs-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 3px;
}
.vs-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 26px;
  border: 1px solid transparent;
  border-radius: 5px;
  background: transparent;
  color: var(--brand-text, #1a2332);
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  padding: 0 8px 0 4px;
  font-family: inherit;
}
.vs-btn:hover {
  background: rgba(0, 96, 160, 0.12);
  border-color: rgba(0, 96, 160, 0.3);
}
.vs-btn:active {
  background: rgba(0, 96, 160, 0.2);
}
.vs-label { line-height: 1; }
</style>
