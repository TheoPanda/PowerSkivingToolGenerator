<script setup lang="ts">
import { ref, reactive, provide, onMounted } from 'vue'
import GearParamsPanel from './GearParamsPanel.vue'

// ---- gearParams store ----
const gearParams = reactive({
  profile_type: 'involute' as string,
  k_io: 1,
  m_n: null as number | null,
  z_w: null as number | null,
  β_w: 0,
  j_w: 1,
  b_w: null as number | null,
  toothMethod: 'x_w' as string,
  x_w: 0,
  W_k: null as number | null,
  k_teeth: null as number | null,
  M: null as number | null,
  d_p: null as number | null,
  α_n: 20,
  h_an: 1,
  c_n: 0.25,
  ρ_f: 0.38,
})

provide('gearParams', gearParams)

// ---- 面板状态 ----
const expanded = ref<boolean>(false)

onMounted(() => {
  window.dispatchEvent(new CustomEvent('panel:toggle', { detail: false }))
})

function togglePanel(): void {
  expanded.value = !expanded.value
  window.dispatchEvent(new CustomEvent('panel:toggle', { detail: expanded.value }))
}

// ---- 步骤导航 ----
const steps = [
  { id: 1, label: '待加工齿轮', icon: '⚙️' },
  { id: 2, label: '包络计算', icon: '📐' },
  { id: 3, label: '刀具几何体', icon: '🔩' },
  { id: 4, label: '仿真验证', icon: '▶️' },
  { id: 5, label: '工艺文件', icon: '📋' },
]
const currentStep = ref<number>(1)

// ---- 步骤完成判定 ----
const step1Valid = ref<boolean>(false)

function onStep1ValidChange(isValid: boolean): void {
  step1Valid.value = isValid
}

// ---- 引导提示 ----
const step1GuideVisible = ref<boolean>(false)

function goToStep(step: number): void {
  if (step > 1 && !step1Valid.value) {
    step1GuideVisible.value = true
    setTimeout(() => { step1GuideVisible.value = false }, 3000)
    return
  }
  step1GuideVisible.value = false
  currentStep.value = step
}

function nextStep(): void {
  if (currentStep.value === 1 && !step1Valid.value) {
    step1GuideVisible.value = true
    setTimeout(() => { step1GuideVisible.value = false }, 3000)
    return
  }
  if (currentStep.value < 5) {
    currentStep.value++
  }
}

defineExpose({ expanded, currentStep, step1Valid, step1GuideVisible, nextStep, goToStep, togglePanel })
</script>

<template>
  <div class="main-panel-shell" :class="{ open: expanded }">
    <!-- 面板内容 -->
    <div class="panel-body">
      <!-- 文件操作栏 -->
      <div class="panel-block file-bar">
        <button class="file-btn" title="新建项目">
          <svg width="14" height="14" viewBox="0 0 16 16"><rect x="1" y="1" width="14" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.2"/><line x1="8" y1="4" x2="8" y2="12" stroke="currentColor" stroke-width="1.2"/><line x1="4" y1="8" x2="12" y2="8" stroke="currentColor" stroke-width="1.2"/></svg>
        </button>
        <button class="file-btn" title="打开项目">
          <svg width="14" height="14" viewBox="0 0 16 16"><path d="M2 4l3-2h6l3 2v9a1 1 0 01-1 1H3a1 1 0 01-1-1V4z" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>
        </button>
        <button class="file-btn" title="另存为">
          <svg width="14" height="14" viewBox="0 0 16 16"><path d="M2 13V3a1 1 0 011-1h7l4 4v7a1 1 0 01-1 1H3a1 1 0 01-1-1z" fill="none" stroke="currentColor" stroke-width="1.2"/><line x1="8" y1="7" x2="8" y2="12" stroke="currentColor" stroke-width="1.2"/><line x1="5" y1="10" x2="11" y2="10" stroke="currentColor" stroke-width="1.2"/></svg>
        </button>
        <span class="file-divider"></span>
        <span class="project-name">未命名项目</span>
      </div>

      <div class="panel-divider"></div>

      <!-- 步骤导航 -->
      <div class="panel-block step-nav">
        <div
          v-for="(step, i) in steps"
          :key="step.id"
          class="step-item"
          :class="{
            active: currentStep === step.id,
            done: currentStep > step.id,
          }"
          @click="goToStep(step.id)"
        >
          <div class="step-node">
            <span v-if="currentStep > step.id" class="step-check">✓</span>
            <span v-else class="step-num">{{ step.id }}</span>
          </div>
          <div class="step-info">
            <span class="step-label">{{ step.label }}</span>
          </div>
        </div>
      </div>

      <div class="panel-divider"></div>

      <!-- 引导提示 -->
      <div class="step-guide" :class="{ visible: step1GuideVisible }">
        请先完成齿轮参数设置，这是后续计算的基础 🙂
      </div>

      <div class="step-body glass-scroll">

        <!-- 步骤1 — GearParamsPanel -->
        <div v-if="currentStep === 1">
          <GearParamsPanel @valid-change="onStep1ValidChange" />
        </div>

        <!-- 步骤 2~5 占位 -->
        <div v-else class="step-placeholder">
          <span class="placeholder-icon">{{ steps[currentStep - 1]?.icon || '📋' }}</span>
          <span class="placeholder-title">{{ steps[currentStep - 1]?.label || '' }}</span>
          <span class="placeholder-hint">即将推出</span>
        </div>
      </div>

      <!-- "下一步"按钮 -->
      <button
        v-if="currentStep < 5"
        class="glass-btn next-step-btn"
        :disabled="currentStep === 1 && !step1Valid"
        style="width: 100%; margin-top: 8px;"
        @click="nextStep"
      >
        下一步
      </button>
    </div>

    <!-- 圆形按钮 -->
    <button class="toggle-btn" :class="{ spun: expanded }" @click="togglePanel">
      <img src="/logo.png" alt="" class="toggle-logo" />
    </button>
  </div>
</template>

<style scoped>
.main-panel-shell {
  position: absolute;
  bottom: 24px;
  left: 24px;
  z-index: 15;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  perspective: 600px;
}

/* ======== 面板主体 ======== */
.panel-body {
  width: 320px;
  max-height: 0;
  overflow: hidden auto;
  opacity: 0;
  transform: translateY(20px) scale(0.95);
  transform-origin: bottom left;
  transition:
    max-height 0.45s cubic-bezier(0.22, 0.61, 0.36, 1),
    opacity 0.35s ease,
    transform 0.45s cubic-bezier(0.22, 0.61, 0.36, 1);
  margin-bottom: 10px;

  /* 冷白色玻璃质感 */
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  box-shadow:
    0 8px 32px rgba(0, 64, 128, 0.08),
    0 2px 8px rgba(0, 0, 0, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
  padding: 12px;
}

.main-panel-shell.open .panel-body {
  max-height: calc(100vh - 170px);
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* ======== 文件操作栏（紧凑） ======== */
.file-bar {
  display: flex;
  align-items: center;
  gap: 4px;
}

.file-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 6px;
  cursor: pointer;
  color: var(--brand-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
}

.file-btn:hover {
  background: rgba(0, 96, 160, 0.1);
  color: var(--brand-blue);
}

.file-divider {
  width: 1px;
  height: 14px;
  background: var(--brand-border);
  margin: 0 2px;
}

.project-name {
  font-size: 12px;
  color: var(--brand-text-secondary);
  font-weight: 500;
}

/* ======== 分割线 ======== */
.panel-divider {
  height: 1px;
  background: var(--brand-border-light);
  margin: 10px 0;
}

/* ======== 步骤导航（紧凑纵向，无连接线） ======== */
.step-nav {
  display: flex;
  gap: 4px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 6px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.step-item:hover {
  background: rgba(0, 96, 160, 0.04);
}

.step-item.active {
  background: rgba(0, 96, 160, 0.08);
}

/* 步骤节点（圆点） */
.step-node {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
  transition: all 0.3s;

  border: 1.5px solid var(--brand-border);
  color: var(--brand-text-secondary);
  background: rgba(255, 255, 255, 0.6);
}

.step-item.active .step-node {
  border-color: var(--brand-blue);
  background: var(--brand-blue);
  color: white;
  box-shadow: 0 0 8px rgba(0, 96, 160, 0.25);
}

.step-item.done .step-node {
  border-color: var(--brand-blue);
  background: var(--brand-blue);
  color: white;
}

.step-num {
  line-height: 1;
}

.step-check {
  font-size: 9px;
  line-height: 1;
}

/* 步骤标签 */
.step-info {
  display: flex;
  align-items: center;
}

.step-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--brand-text-secondary);
  transition: color 0.2s;
  white-space: nowrap;
}

.step-item.active .step-label {
  color: var(--brand-text);
  font-weight: 600;
}

.step-item.done .step-label {
  color: var(--brand-text);
}

/* ======== 圆形切换按钮 ======== */
.toggle-btn {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.6);
  background: linear-gradient(135deg, #ffffff 0%, #e8ecf0 100%);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
  transform-style: preserve-3d;
  transition: transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1),
              box-shadow 0.3s;

  box-shadow:
    0 4px 16px rgba(0, 64, 128, 0.12),
    0 1px 3px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.8),
    inset 0 -2px 4px rgba(0, 0, 0, 0.06);
}

.toggle-btn:hover {
  box-shadow:
    0 6px 24px rgba(0, 64, 128, 0.18),
    0 2px 6px rgba(0, 0, 0, 0.10),
    inset 0 1px 0 rgba(255, 255, 255, 0.8),
    inset 0 -2px 4px rgba(0, 0, 0, 0.06);
}

.toggle-btn.spun {
  transform: rotateY(180deg);
}

.toggle-logo {
  width: 32px;
  height: 32px;
  object-fit: contain;
}

/* ======== 步骤内容区 ======== */
.step-body {
  flex: 1;
  min-height: 0;
}

/* ======== 占位内容 ======== */
.step-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px 16px;
  gap: 6px;
}

.placeholder-icon {
  font-size: 24px;
  opacity: 0.4;
}

.placeholder-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-text);
}

.placeholder-hint {
  font-size: 10px;
  color: var(--brand-text-secondary);
}

/* ======== 引导提示 + 脉冲动画 ======== */
.step-guide {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  font-size: 11px;
  color: var(--brand-blue);
  text-align: center;
  padding: 0 6px;
  transition: max-height 0.35s cubic-bezier(0.22, 0.61, 0.36, 1),
              opacity 0.3s ease,
              padding 0.3s ease;
}

.step-guide.visible {
  max-height: 26px;
  opacity: 1;
  padding: 4px 6px;
  animation: guide-pulse 0.3s ease-in-out;
}

@keyframes guide-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.02); }
}
</style>
