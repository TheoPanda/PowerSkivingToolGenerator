<script setup lang="ts">
/**
 * App.vue — 应用根组件（Electron 主窗口外壳）
 *
 * - 自绘标题栏（登录后经 app:login-success 事件滑入）+ 窗口最小化/最大化/关闭控件
 * - 挂载主视图 MainView（全屏 3D 工作区：登录 + 面板 + 结果）
 */
import { ref, onMounted, onUnmounted } from 'vue'
import MainView from './components/MainView.vue'

const showHeader = ref<boolean>(false)
const isMaximized = ref<boolean>(false)

function onLoginSuccess(): void {
  showHeader.value = true
}

onMounted(async () => {
  window.addEventListener('app:login-success', onLoginSuccess)
  if (window.electronAPI) {
    isMaximized.value = await window.electronAPI.isMaximized()
    window.electronAPI.onMaximizeChange((maximized: boolean) => {
      isMaximized.value = maximized
    })
  }
})

onUnmounted(() => {
  window.removeEventListener('app:login-success', onLoginSuccess)
})

function minimizeWin(): void {
  window.electronAPI?.minimizeWindow()
}

async function maximizeWin(): Promise<void> {
  await window.electronAPI?.maximizeWindow()
}

function closeWin(): void {
  window.electronAPI?.closeWindow()
}
</script>

<template>
  <div class="app-container">
    <el-container>
      <el-header v-if="showHeader" class="app-header" :class="{ visible: showHeader }">
        <img src="/logo.png" alt="Logo" class="header-logo" />
        <div class="window-controls">
          <button class="win-btn" @click="minimizeWin" title="最小化">
            <svg width="12" height="12"><rect y="5.5" width="12" height="1" fill="currentColor"/></svg>
          </button>
          <button class="win-btn" @click="maximizeWin" :title="isMaximized ? '还原' : '最大化'">
            <svg v-if="!isMaximized" width="12" height="12"><rect x="1" y="1" width="10" height="10" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>
            <svg v-else width="12" height="12"><rect x="3" y="0" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.2"/><rect x="0" y="3" width="8" height="8" fill="white" stroke="currentColor" stroke-width="1.2"/></svg>
          </button>
          <button class="win-btn win-btn-close" @click="closeWin" title="关闭">
            <svg width="12" height="12"><line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.3"/><line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.3"/></svg>
          </button>
        </div>
      </el-header>
      <el-main class="app-main">
        <MainView />
      </el-main>
    </el-container>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.app-container {
  height: 100vh;
  overflow: hidden;
}

.el-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* ======== 顶部标题栏——登录后平滑滑入 ======== */
.app-header {
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px;
  height: 40px;
  flex-shrink: 0;
  -webkit-app-region: drag;
  user-select: none;
  border-bottom: 1px solid var(--brand-border);
  overflow: visible;

  /* 初始隐藏 → 登录后滑入 */
  transform: translateY(-100%);
  opacity: 0;
  transition: transform 0.55s cubic-bezier(0.22, 0.61, 0.36, 1),
              opacity 0.45s ease;
}

.app-header.visible {
  transform: translateY(0);
  opacity: 1;
}

.header-logo {
  height: 28px;
  width: auto;
  -webkit-app-region: no-drag;
}

/* ======== 自绘窗口控件 ======== */
.window-controls {
  display: flex;
  -webkit-app-region: no-drag;
}

.win-btn {
  width: 40px;
  height: 30px;
  border: none;
  background: transparent;
  color: #555;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: background 0.15s;
}

.win-btn:hover {
  background: #e8e8e8;
}

.win-btn-close:hover {
  background: #e81123;
  color: white;
}

/* ======== 主内容区 ======== */
.app-main {
  flex: 1;
  padding: 0;
  overflow: hidden;
  position: relative;
}

/* ======== Element Plus 主题覆盖 ======== */
.el-button--primary {
  --el-button-bg-color: var(--brand-blue);
  --el-button-border-color: var(--brand-blue);
  --el-button-hover-bg-color: var(--brand-blue-light);
  --el-button-hover-border-color: var(--brand-blue-light);
}

.el-card {
  border-color: var(--brand-border);
}

.el-tag--success {
  --el-tag-bg-color: #E8F5E9;
  --el-tag-text-color: #2E7D32;
}
</style>
