<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchHello } from '@/api/index'
import MainPanel from './MainPanel.vue'
import ResultPanel from './ResultPanel.vue'
import { revealResultPanel } from '../composables/useWorkpieceState'
import { createGearViewport, type GearViewport, type RenderMode } from '../three/GearViewport'

// ---- 后端状态 ----
interface BackendInfo {
  message: string
  status: string
  framework: string
  version: string
  python_version: string
  timestamp: string
}

const backendInfo = ref<BackendInfo | null>(null)
const backendError = ref<string | null>(null)
const loading = ref<boolean>(false)

// ---- 登录 ----
const loggedIn = ref<boolean>(false)
const welcomeLeaving = ref<boolean>(false)
const username = ref<string>('')
const password = ref<string>('')
const loginError = ref<string>('')
const loginLoading = ref<boolean>(false)

const baseScale = 1.0              // 登录后的基准缩放

function cancelApp(): void {
  window.electronAPI?.closeWindow()
}

function doLogin(): void {
  loginError.value = ''
  if (username.value === 'ZYW' && password.value === '260101') {
    loginLoading.value = true
    welcomeLeaving.value = true
    gearViewport?.setModelLayout({ scale: 1.0 })
    window.dispatchEvent(new CustomEvent('app:login-success'))
    setTimeout(() => {
      loggedIn.value = true
      gearViewport?.setLoggedIn(true)
      }, 500)
  } else {
    loginError.value = '用户名或密码错误'
    password.value = ''
  }
}

async function callBackend(): Promise<void> {
  loading.value = true
  backendError.value = null
  try {
    backendInfo.value = await fetchHello()
    ElMessage.success('后端通信成功!')
  } catch (err) {
    const message: string = err instanceof Error ? err.message : '未知错误'
    backendError.value = message
    ElMessage.error(`后端通信失败: ${message}`)
  } finally {
    loading.value = false
  }
}

// ---- Three.js  ----
const viewportRef = ref<HTMLDivElement | null>(null)
const modelLoaded = ref<boolean>(false)
const modelLoadProgress = ref<number>(0)

/** 渲染模式（实体 / 线框图纸）——由 GearViewport 模块驱动，供按钮绑定. */
const renderMode = ref<RenderMode>('solid')
let gearViewport: GearViewport | null = null

function applyRenderMode(mode: RenderMode): void {
  gearViewport?.setRenderMode(mode)
}

function onResize(): void {
  gearViewport?.resize()
}

/** 主面板展开/收起 → 模型缩放/右移联动. */
function onPanelToggle(e: Event): void {
  const detail = (e as CustomEvent).detail as boolean
  gearViewport?.setModelLayout({
    scale: detail ? baseScale : baseScale * 1.6,
    offsetX: detail ? 20 : 0,
  })
}

/** 齿轮 GLB 就绪 → 交给视口加载. */
function onGearModelReady(e: Event): void {
  const glbBase64: string = (e as CustomEvent).detail as string
  gearViewport?.loadGear(glbBase64)
}

onMounted(() => {
  if (viewportRef.value) {
    gearViewport = createGearViewport({
      container: viewportRef.value,
      modelLoaded,
      modelLoadProgress,
      renderMode,
      onGearDisplayed: () => revealResultPanel(),
    })
  }
  window.addEventListener('resize', onResize)
  window.addEventListener('panel:toggle', onPanelToggle)
  window.addEventListener('gear:model-ready', onGearModelReady)
  callBackend()
})

onUnmounted(() => {
  gearViewport?.dispose()
  gearViewport = null
  window.removeEventListener('resize', onResize)
  window.removeEventListener('panel:toggle', onPanelToggle)
  window.removeEventListener('gear:model-ready', onGearModelReady)
})
</script>

<template>
  <div class="viewport">
    <!-- 全屏 3D 画布 -->
    <div ref="viewportRef" class="canvas-fullscreen"></div>

    <!-- 渲染模式切换 (右上角) -->
    <div class="render-toggle">
      <button
        class="render-toggle-btn"
        :class="{ active: renderMode === 'solid' }"
        @click="applyRenderMode('solid')"
      >实体</button>
      <button
        class="render-toggle-btn"
        :class="{ active: renderMode === 'xray' }"
        @click="applyRenderMode('xray')"
      >线框</button>
    </div>

    <!-- 欢迎界面 -->
    <div v-if="!loggedIn" class="welcome-overlay" :class="{ leaving: welcomeLeaving }">
      <div class="welcome-card" :class="{ leaving: welcomeLeaving }">
        <img src="/logo.png" alt="Logo" class="welcome-logo" />
        <div class="welcome-form">
          <input
            v-model="username"
            type="text"
            placeholder="用户名"
            class="welcome-input"
            :disabled="welcomeLeaving"
            @keyup.enter="doLogin"
          />
          <input
            v-model="password"
            type="password"
            placeholder="密码"
            class="welcome-input"
            :disabled="welcomeLeaving"
            @keyup.enter="doLogin"
          />
          <p v-if="loginError" class="login-error">{{ loginError }}</p>
          <button
            class="welcome-btn"
            :disabled="welcomeLeaving || loginLoading"
            @click="doLogin"
          >
            {{ loginLoading ? '验证中…' : '登 录' }}
          </button>
          <button
            class="welcome-cancel-btn"
            :disabled="welcomeLeaving"
            @click="cancelApp"
          >
            取 消
          </button>
        </div>
      </div>
    </div>

    <!-- 主功能面板（文件+步骤导航） -->
    <MainPanel v-if="loggedIn" />

    <!-- 独立可拖拽「计算结果」面板（全局结果单例消费；登录后可出现） -->
    <ResultPanel v-if="loggedIn" />

    <!-- 模型加载进度 -->
    <div v-if="!modelLoaded" class="loading-overlay">
      <div class="loading-card">
        <span class="loading-spinner"></span>
        <span class="loading-text">加载滚刀模型… {{ modelLoadProgress }}%</span>
      </div>
    </div>

  </div>
</template>

<style scoped>
/* ======== 全屏 3D ======== */
.viewport {
  position: relative;
  width: 100%;
  height: 100%;
}

.canvas-fullscreen {
  position: absolute;
  inset: 0;
}

/* ======== 渲染模式切换 (右上角) ======== */
.render-toggle {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 12;
  display: flex;
  gap: 2px;
  padding: 3px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 9px;
  border: 1px solid var(--brand-border);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
}

.render-toggle-btn {
  padding: 5px 12px;
  font-size: 12px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--brand-text-secondary);
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.render-toggle-btn:hover {
  background: rgba(0, 96, 160, 0.08);
}

.render-toggle-btn.active {
  background: var(--brand-blue);
  color: #fff;
}

/* ======== 欢迎界面 ======== */
.welcome-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
  transition: opacity 0.5s ease, visibility 0.5s;
}

.welcome-overlay.leaving {
  opacity: 0;
  pointer-events: none;
}

.welcome-card {
  width: 320px;
  padding: 28px 28px;
  border-radius: 18px;
  text-align: center;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(28px) saturate(180%);
  -webkit-backdrop-filter: blur(28px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow:
    0 8px 40px rgba(0, 64, 128, 0.10),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
  transition: transform 0.45s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.45s cubic-bezier(0.4, 0, 0.2, 1);
}

.welcome-card.leaving {
  transform: scale(0.85);
  opacity: 0;
}

.welcome-logo {
  height: 40px;
  width: auto;
  margin-bottom: 14px;
}

.welcome-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--brand-text);
  letter-spacing: 1px;
  margin-bottom: 4px;
}

.welcome-subtitle {
  font-size: 11px;
  color: var(--brand-text-secondary);
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-bottom: 22px;
}

.welcome-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.welcome-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--brand-border);
  border-radius: 8px;
  font-size: 13px;
  color: var(--brand-text);
  background: rgba(255, 255, 255, 0.6);
  outline: none;
  transition: border 0.2s, box-shadow 0.2s;
}

.welcome-input:focus {
  border-color: var(--brand-blue);
  box-shadow: 0 0 0 3px rgba(0, 96, 160, 0.1);
}

.welcome-input::placeholder {
  color: var(--brand-text-disabled);
}

.login-error {
  color: var(--brand-danger);
  font-size: 13px;
  margin: -4px 0;
}

.welcome-btn {
  width: 100%;
  padding: 10px;
  border: none;
  border-radius: 8px;
  background: var(--brand-blue);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 4px;
  transition: background 0.2s, transform 0.15s;
}

.welcome-btn:hover {
  background: var(--brand-blue-light);
}

.welcome-btn:active {
  transform: scale(0.98);
}

.welcome-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.welcome-cancel-btn {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--brand-border);
  border-radius: 8px;
  background: transparent;
  color: var(--brand-text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  letter-spacing: 4px;
  transition: background 0.15s, color 0.15s;
}

.welcome-cancel-btn:hover {
  background: rgba(0, 0, 0, 0.04);
  color: var(--brand-text);
}

.welcome-cancel-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ======== 模型加载覆盖层 ======== */
.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(235, 239, 243, 0.7);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 5;
}

.loading-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 28px;
  background: rgba(0, 96, 160, 0.08);
  backdrop-filter: blur(12px);
  border-radius: 14px;
  border: 1px solid rgba(0, 96, 160, 0.12);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--brand-border);
  border-top-color: var(--brand-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 14px;
  color: var(--brand-text);
  font-weight: 500;
}

</style>
