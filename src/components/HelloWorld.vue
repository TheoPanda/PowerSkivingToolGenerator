<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { ElMessage } from 'element-plus'
import { fetchHello } from '@/api/index'
import MainPanel from './MainPanel.vue'

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
const panelCollapsed = ref<boolean>(false)

// ---- 登录 ----
const loggedIn = ref<boolean>(false)
const welcomeLeaving = ref<boolean>(false)
const paramPanelReady = ref<boolean>(false)
const username = ref<string>('')
const password = ref<string>('')
const loginError = ref<string>('')
const loginLoading = ref<boolean>(false)

let targetModelScale = 3.0       // 欢迎界面 3×
let baseScale = 1.0              // 登录后的基准缩放
let panelExpanded = false        // 主面板展开状态
let targetOffsetX = 0            // 面板展开时微右移
const ANIM_DURATION = 650               // 总动画时长 ms

function cancelApp(): void {
  window.electronAPI?.closeWindow()
}

function doLogin(): void {
  loginError.value = ''
  if (username.value === 'ZYW' && password.value === '260101') {
    loginLoading.value = true
    welcomeLeaving.value = true
    targetModelScale = 1.0
    window.dispatchEvent(new CustomEvent('app:login-success'))
    setTimeout(() => {
      loggedIn.value = true
      setTimeout(() => {
        paramPanelReady.value = true
      }, 200)
    }, 500)
  } else {
    loginError.value = '用户名或密码错误'
    password.value = ''
  }
}

// ---- 面板拖动 ----
const panelX = ref<number>(16)
const panelY = ref<number>(16)
const dragging = ref<boolean>(false)
let dragStartX = 0
let dragStartY = 0
let dragStartPanelX = 0
let dragStartPanelY = 0

function startDrag(e: MouseEvent): void {
  if (panelCollapsed.value) return
  dragging.value = true
  dragStartX = e.clientX
  dragStartY = e.clientY
  dragStartPanelX = panelX.value
  dragStartPanelY = panelY.value
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(e: MouseEvent): void {
  if (!dragging.value) return
  const dx = e.clientX - dragStartX
  const dy = e.clientY - dragStartY
  panelX.value = Math.max(0, dragStartPanelX + dx)
  panelY.value = Math.max(0, dragStartPanelY + dy)
}

function stopDrag(): void {
  dragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
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

let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let controls: OrbitControls | null = null
let rootGroup: THREE.Group | null = null    // 最外层：纯平移
let tiltGroup: THREE.Group | null = null    // 45° 静态倾斜
let spinGroup: THREE.Group | null = null     // 持续自旋
let modelGroup: THREE.Group | null = null    // 内层：Z-up 修正
let animationId: number | null = null
let spinAngle = 0
const diagonalAxis = new THREE.Vector3(1, 0.35, 0).normalize()  // 左上→右下
const verticalAxis = new THREE.Vector3(0, 1, 0)                // 上下
let currentSpinAxis = verticalAxis.clone()
let targetSpinAxis = verticalAxis.clone()
let spinSpeed = 0.006          // 欢迎界面转速
let userInteracted = false

function initThreeJs(): void {
  if (!viewportRef.value) return

  const width: number = viewportRef.value.clientWidth
  const height: number = viewportRef.value.clientHeight

  // 渲染器
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.2
  viewportRef.value.appendChild(renderer.domElement)

  // 场景
  scene = new THREE.Scene()

  // 环境贴图
  const pmremGenerator = new THREE.PMREMGenerator(renderer)
  const envScene = new THREE.Scene()

  const envGeo = new THREE.SphereGeometry(50, 32, 32)
  const envMat = new THREE.MeshBasicMaterial({ color: 0xd5cfc6, side: THREE.BackSide })
  envScene.add(new THREE.Mesh(envGeo, envMat))

  const envTopGeo = new THREE.PlaneGeometry(40, 40)
  const envTop = new THREE.Mesh(envTopGeo, new THREE.MeshBasicMaterial({ color: 0xfaf8f5 }))
  envTop.rotation.x = -Math.PI / 2
  envTop.position.y = 25
  envScene.add(envTop)

  const lightBlocks = [
    { color: 0xfffaf5, pos: [20, 15, 10], size: [8, 4] },
    { color: 0xfffaf5, pos: [-15, 10, -20], size: [6, 3] },
    { color: 0xf5f0e8, pos: [0, 5, -25], size: [10, 5] },
  ]
  for (const b of lightBlocks) {
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(b.size[0], b.size[1]),
      new THREE.MeshBasicMaterial({ color: b.color }),
    )
    m.position.set(b.pos[0], b.pos[1], b.pos[2])
    m.lookAt(0, 0, 0)
    envScene.add(m)
  }

  scene.environment = pmremGenerator.fromScene(envScene, 0.04).texture
  scene.background = new THREE.Color(0xebeff3)  // 冷灰白 — 精密工业感
  envScene.clear()

  // 相机
  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100)
  camera.position.set(4, 2.5, 6)
  camera.lookAt(0, 0.5, 0)

  // 轨道控制器 —— 鼠标旋转/缩放/平移
  controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 0.5, 0)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.autoRotate = false              // 模型自旋由 spinGroup 控制
  controls.minDistance = 5
  controls.maxDistance = 200
  controls.maxPolarAngle = Math.PI * 0.7
  controls.enabled = false              // 登录期间禁用
  controls.update()

  // 用户首次操作后停止自动旋转
  function stopAutoRotate(): void {
    userInteracted = true
    if (controls) controls.autoRotate = false
    controls?.removeEventListener('start', stopAutoRotate)
  }
  controls.addEventListener('start', stopAutoRotate)

  // 登录后启用交互
  setTimeout(() => {
    controls!.enabled = true
  }, 1200)

  // 三点布光
  const keyLight = new THREE.DirectionalLight(0xffeedd, 4.5)
  keyLight.position.set(8, 12, 4)
  keyLight.castShadow = true
  keyLight.shadow.mapSize.width = 2048
  keyLight.shadow.mapSize.height = 2048
  keyLight.shadow.camera.near = 0.5
  keyLight.shadow.camera.far = 50
  keyLight.shadow.camera.left = -10
  keyLight.shadow.camera.right = 10
  keyLight.shadow.camera.top = 10
  keyLight.shadow.camera.bottom = -10
  keyLight.shadow.bias = -0.0001
  keyLight.shadow.normalBias = 0.02
  scene.add(keyLight)

  const fillLight = new THREE.DirectionalLight(0xfff5eb, 1.8)
  fillLight.position.set(-4, 3, -2)
  scene.add(fillLight)

  const rimLight = new THREE.DirectionalLight(0xffffff, 2.5)
  rimLight.position.set(0, 1, -6)
  scene.add(rimLight)

  const bounceLight = new THREE.DirectionalLight(0x998877, 1.2)
  bounceLight.position.set(0, -1, 2)
  scene.add(bounceLight)

  // ---- 加载滚刀模型 (STL) ----
  const carbideMaterial = new THREE.MeshStandardMaterial({
    color: 0x5a5854,
    roughness: 0.28,
    metalness: 0.97,
  })

  const stlLoader = new STLLoader()
  stlLoader.load(
    '/hob.stl',
    (geometry: THREE.BufferGeometry) => {
      // 居中模型
      geometry.computeBoundingBox()
      const bbox = geometry.boundingBox!
      const cx = (bbox.max.x + bbox.min.x) / 2
      const cy = (bbox.max.y + bbox.min.y) / 2
      const cz = (bbox.max.z + bbox.min.z) / 2
      geometry.translate(-cx, -cy, -cz)

      // 包围盒尺寸 → 适配相机距离 + 裁剪面
      const size = new THREE.Vector3()
      bbox.getSize(size)
      const maxDim = Math.max(size.x, size.y, size.z)
      const dist = maxDim * 2.2

      // 更新相机裁剪面——防止大模型被裁切
      camera!.near = dist * 0.001
      camera!.far = dist * 10
      camera!.updateProjectionMatrix()

      const mesh = new THREE.Mesh(geometry, carbideMaterial)
      mesh.castShadow = true
      mesh.receiveShadow = true

      modelGroup = new THREE.Group()
      modelGroup.add(mesh)
      modelGroup.rotation.x = -Math.PI / 2  // Z-up → Y-up
      modelGroup.scale.setScalar(3.0)

      spinGroup = new THREE.Group()
      spinGroup.add(modelGroup)

      tiltGroup = new THREE.Group()
      tiltGroup.add(spinGroup)
      tiltGroup.rotateOnWorldAxis(new THREE.Vector3(0, 0, 1), Math.PI / 4)

      rootGroup = new THREE.Group()
      rootGroup.add(tiltGroup)
      scene!.add(rootGroup)

      // 相机适配模型大小
      controls!.target.set(0, 0, 0)
      camera!.position.set(dist * 0.6, dist * 0.5, dist * 0.7)
      controls!.update()

      modelLoaded.value = true
    },
    (xhr: ProgressEvent) => {
      if (xhr.lengthComputable) {
        modelLoadProgress.value = Math.round((xhr.loaded / xhr.total) * 100)
      }
    },
    (err: unknown) => {
      console.error('STL 加载失败:', err)
      modelLoaded.value = true
    },
  )


  // 动画
  function animate(): void {
    animationId = requestAnimationFrame(animate)

    // 模型缩放平滑过渡
    if (modelGroup) {
      const diff = targetModelScale - modelGroup.scale.x
      if (Math.abs(diff) > 0.001) modelGroup.scale.setScalar(modelGroup.scale.x + diff * 0.06)
    }

    // 模型右移（面板展开时）
    if (rootGroup) {
      const diff = targetOffsetX - rootGroup.position.x
      if (Math.abs(diff) > 0.05) rootGroup.position.x += diff * 0.08
    }

    // 模型自旋（绕旋转轴累积旋转）
    if (spinGroup && !userInteracted) {
      currentSpinAxis.lerp(targetSpinAxis, 0.02)
      if (loggedIn) {
        spinSpeed += (0.002 - spinSpeed) * 0.03
      }
      spinGroup.rotateOnWorldAxis(currentSpinAxis, spinSpeed)
    }

    controls?.update()
    if (renderer && scene && camera) renderer.render(scene, camera)
  }
  animate()
}

function disposeThreeJs(): void {
  if (animationId !== null) { cancelAnimationFrame(animationId); animationId = null }
  if (controls) { controls.dispose(); controls = null }
  if (renderer) { renderer.dispose(); renderer = null }
  if (scene) { scene.clear(); scene = null }
  rootGroup = null; tiltGroup = null; spinGroup = null; modelGroup = null; camera = null
}

function handleResize(): void {
  if (!viewportRef.value || !camera || !renderer) return
  const w = viewportRef.value.clientWidth
  const h = viewportRef.value.clientHeight
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  renderer.setSize(w, h)
}

function onPanelToggle(e: Event): void {
  const detail = (e as CustomEvent).detail as boolean
  panelExpanded = detail
  targetModelScale = detail ? baseScale : baseScale * 1.6
  targetOffsetX = detail ? 20 : 0
}

onMounted(() => {
  initThreeJs()
  window.addEventListener('resize', handleResize)
  window.addEventListener('panel:toggle', onPanelToggle)
  callBackend()
})

onUnmounted(() => {
  disposeThreeJs()
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('panel:toggle', onPanelToggle)
})
</script>

<template>
  <div class="viewport">
    <!-- 全屏 3D 画布 -->
    <div ref="viewportRef" class="canvas-fullscreen"></div>

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

    <!-- 模型加载进度 -->
    <div v-if="!modelLoaded" class="loading-overlay">
      <div class="loading-card">
        <span class="loading-spinner"></span>
        <span class="loading-text">加载滚刀模型… {{ modelLoadProgress }}%</span>
      </div>
    </div>

    <!-- 玻璃悬浮参数面板（登录后显示） -->
    <div
      v-if="loggedIn"
      class="glass-panel"
      :class="{ collapsed: panelCollapsed, dragging: dragging, visible: paramPanelReady }"
      :style="{ left: panelX + 'px', top: panelY + 'px' }"
    >
      <div class="glass-panel-inner">
        <!-- 折叠按钮 -->
        <button class="collapse-btn" @click="panelCollapsed = !panelCollapsed" :title="panelCollapsed ? '展开面板' : '收起面板'">
          {{ panelCollapsed ? '◀' : '▶' }}
        </button>

        <template v-if="!panelCollapsed">
          <!-- 标题（可拖动把手） -->
          <div class="panel-title" @mousedown="startDrag">⋮⋮ 参数面板</div>

          <!-- 后端状态 -->
          <div class="panel-section">
            <div class="section-label">
              后端通信
              <span class="dot" :class="backendInfo ? 'ok' : backendError ? 'err' : 'wait'"></span>
            </div>
            <div v-if="backendInfo" class="section-body">
              <div class="kv"><span>框架</span><span>{{ backendInfo.framework }}</span></div>
              <div class="kv"><span>API</span><span>{{ backendInfo.version }}</span></div>
              <div class="kv"><span>Python</span><span>{{ backendInfo.python_version }}</span></div>
            </div>
            <div v-else-if="backendError" class="section-body">
              <el-alert :title="backendError" type="error" show-icon :closable="false" />
            </div>
            <el-button size="small" :loading="loading" @click="callBackend" style="width:100%;margin-top:6px">
              {{ loading ? '连接中…' : '重新连接' }}
            </el-button>
          </div>

          <!-- 渲染参数 -->
          <div class="panel-section">
            <div class="section-label">渲染参数</div>
            <div class="section-body">
              <div class="kv"><span>材质</span><span>硬质合金 WC-Co</span></div>
              <div class="kv"><span>粗糙度</span><span>0.28</span></div>
              <div class="kv"><span>金属度</span><span>0.97</span></div>
              <div class="kv"><span>照明</span><span>三点布光</span></div>
            </div>
          </div>

          <!-- 技术栈 -->
          <div class="panel-section">
            <div class="section-label">技术栈</div>
            <div class="stack-list">
              <span class="stack-tag">Vue 3</span>
              <span class="stack-tag">TypeScript</span>
              <span class="stack-tag">Vite</span>
              <span class="stack-tag">Element Plus</span>
              <span class="stack-tag">Three.js</span>
              <span class="stack-tag">FastAPI</span>
              <span class="stack-tag">Electron</span>
            </div>
          </div>
        </template>
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

/* ======== 玻璃悬浮面板 ======== */
.glass-panel {
  position: absolute;
  width: 300px;
  max-height: calc(100% - 32px);
  overflow: hidden;
  border-radius: 18px;

  /* 蓝色玻璃质感 */
  background: rgba(0, 96, 160, 0.09);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(0, 96, 160, 0.16);
  box-shadow:
    0 4px 24px rgba(0, 64, 128, 0.06),
    0 1px 4px rgba(0, 64, 128, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.5);
  transition: width 0.3s ease, box-shadow 0.2s, transform 0.45s cubic-bezier(0.34, 1.56, 0.64, 1),
              opacity 0.35s ease;
  z-index: 10;
  user-select: none;

  /* 初始隐藏 → 登录后弹出 */
  transform: scale(0.85);
  opacity: 0;
}

.glass-panel.visible {
  transform: scale(1);
  opacity: 1;
}

.glass-panel.collapsed {
  width: 44px;
}

.glass-panel.dragging {
  box-shadow:
    0 12px 40px rgba(0, 64, 128, 0.12),
    0 2px 8px rgba(0, 64, 128, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.5);
  transition: width 0.3s ease;
}

.glass-panel-inner {
  padding: 16px;
  overflow-y: auto;
  max-height: calc(100vh - 130px);
  position: relative;
}

.collapsed .glass-panel-inner {
  padding: 12px 8px;
  overflow: hidden;
}

/* 折叠按钮 */
.collapse-btn {
  position: absolute;
  top: 12px;
  right: 8px;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 1px solid rgba(0, 96, 160, 0.15);
  background: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--brand-text-secondary);
  transition: all 0.2s;
}

.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.9);
  border-color: rgba(0, 0, 0, 0.15);
}

.collapsed .collapse-btn {
  position: static;
  margin: 0 auto;
}

/* 面板标题 — 可拖动把手 */
.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-text);
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  letter-spacing: 0.3px;
  cursor: grab;
  transition: color 0.15s;
}

.panel-title:active {
  cursor: grabbing;
  color: var(--brand-blue);
}

/* 区块 */
.panel-section {
  margin-bottom: 14px;
}

.panel-section:last-child {
  margin-bottom: 0;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--brand-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 状态小圆点 */
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}
.dot.ok   { background: var(--brand-success); box-shadow: 0 0 4px rgba(46,125,50,0.4); }
.dot.err  { background: var(--brand-danger); }
.dot.wait { background: #B0B8C0; }

.section-body {
  font-size: 12px;
}

/* 键值对 */
.kv {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  font-size: 12px;
}
.kv span:first-child {
  color: var(--brand-text-secondary);
}
.kv span:last-child {
  color: var(--brand-text);
  font-weight: 500;
}

/* 技术栈标签 */
.stack-list {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.stack-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 8px;
  background: rgba(0, 96, 160, 0.08);
  color: var(--brand-blue);
  font-weight: 500;
  letter-spacing: 0.2px;
}
</style>
