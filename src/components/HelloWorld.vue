<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
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

// ---- 登录 ----
const loggedIn = ref<boolean>(false)
const welcomeLeaving = ref<boolean>(false)
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

let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let controls: OrbitControls | null = null
let rootGroup: THREE.Group | null = null    // 最外层：纯平移
let tiltGroup: THREE.Group | null = null    // 45° 静态倾斜
let spinGroup: THREE.Group | null = null     // 持续自旋
let modelGroup: THREE.Group | null = null    // 内层：Z-up 修正
let steelMaterial: THREE.MeshStandardMaterial | null = null    // 不锈钢 PBR 材质 (齿轮)
let carbideMaterial: THREE.MeshStandardMaterial | null = null  // 硬质合金 PBR 材质 (刀具)
let animationId: number | null = null
let spinAngle = 0
const diagonalAxis = new THREE.Vector3(1, 0.35, 0).normalize()  // 左上→右下
const verticalAxis = new THREE.Vector3(0, 1, 0)                // 上下
let currentSpinAxis = verticalAxis.clone()
let targetSpinAxis = verticalAxis.clone()
let spinSpeed = 0.006          // 欢迎界面转速
let userInteracted = false
let renderRequested = true     // on-demand 渲染标志: 无变化时跳过 render

function requestRender(): void {
  renderRequested = true
}

// ---- 渲染模式 (实体 / X-Ray 线框) ----
type RenderMode = 'solid' | 'xray'

const renderMode = ref<RenderMode>('solid')
let flatMaterial: THREE.MeshBasicMaterial | null = null      // 线框模式: 单一色实体 (工程图纸)
let edgeMaterial: THREE.LineBasicMaterial | null = null      // 线框模式: 深色边缘线
const BG_SOLID = new THREE.Color(0xebeff3)                   // 实体模式背景
const BG_XRAY = new THREE.Color(0xffffff)                    // 线框模式背景 (图纸白底)

function initThreeJs(): void {
  if (!viewportRef.value) return

  const width: number = viewportRef.value.clientWidth
  const height: number = viewportRef.value.clientHeight

  // 渲染器
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap   // PCFSoft 对集成显卡过重
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
  // on-demand 渲染: 交互/相机阻尼变化时请求重绘
  controls.addEventListener('start', () => { requestRender() })
  controls.addEventListener('change', () => { requestRender() })
  controls.addEventListener('start', stopAutoRotate)

  // 登录后启用交互
  setTimeout(() => {
    controls!.enabled = true
  }, 1200)

  // 三点布光
  const keyLight = new THREE.DirectionalLight(0xffeedd, 4.5)
  keyLight.position.set(8, 12, 4)
  keyLight.castShadow = true
  keyLight.shadow.mapSize.width = 1024
  keyLight.shadow.mapSize.height = 1024
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

  // ---- 刀具材质 — 硬质合金 ----
  carbideMaterial = new THREE.MeshStandardMaterial({
    color: 0x5a5854,        // 硬质合金深灰褐
    roughness: 0.28,
    metalness: 0.97,
  })

  // ---- 齿轮材质 — 不锈钢 ----
  steelMaterial = new THREE.MeshStandardMaterial({
    color: 0x9a9aa0,        // 不锈钢亮银灰 (冷调)
    roughness: 0.32,
    metalness: 0.98,
  })

  // ---- 线框模式 (工程图纸): 单一色实体 + 深色边缘线 ----
  flatMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff })   // 纯白, 无光照
  edgeMaterial = new THREE.LineBasicMaterial({ color: 0x1f2937 })   // 深灰蓝线

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

      // 缩放范围随模型尺寸适配——避免大模型被固定 maxDistance 卡住无法缩小
      controls!.minDistance = dist * 0.05
      controls!.maxDistance = dist * 10

      const mat: THREE.MeshStandardMaterial = carbideMaterial!
      const mesh = new THREE.Mesh(geometry, mat)
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
      requestRender()
      applyRenderMode(renderMode.value)
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


  // 动画 (on-demand: 模型静止且相机不动时跳过 render, 让 GPU 空闲)
  function animate(): void {
    animationId = requestAnimationFrame(animate)

    let sceneDirty = false

    // 模型缩放平滑过渡
    if (modelGroup) {
      const diff = targetModelScale - modelGroup.scale.x
      if (Math.abs(diff) > 0.001) {
        modelGroup.scale.setScalar(modelGroup.scale.x + diff * 0.06)
        sceneDirty = true
      }
    }

    // 模型右移（面板展开时）
    if (rootGroup) {
      const diff = targetOffsetX - rootGroup.position.x
      if (Math.abs(diff) > 0.05) {
        rootGroup.position.x += diff * 0.08
        sceneDirty = true
      }
    }

    // 模型自旋（绕旋转轴累积旋转）
    if (spinGroup && !userInteracted) {
      currentSpinAxis.lerp(targetSpinAxis, 0.02)
      if (loggedIn) {
        spinSpeed += (0.002 - spinSpeed) * 0.03
      }
      spinGroup.rotateOnWorldAxis(currentSpinAxis, spinSpeed)
      sceneDirty = true
    }

    controls?.update()

    // 仅在模型/相机有变化时重绘
    if (renderer && scene && camera && (renderRequested || sceneDirty)) {
      renderRequested = false
      renderer.render(scene, camera)
    }
  }
  animate()
}

// ── 渲染模式切换: 实体 ↔ 遮挡线框 (不透明实体 + 亮色边缘线) ──
function applyRenderMode(mode: RenderMode): void {
  renderMode.value = mode
  if (!scene || !edgeMaterial || !flatMaterial) return

  const edge = edgeMaterial
  const flat = flatMaterial

  scene.background = mode === 'xray' ? BG_XRAY : BG_SOLID

  scene.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return

    // 记录实体材质 (首次切换时)
    if (!child.userData.solidMaterial) {
      child.userData.solidMaterial = child.material
    }

    // 移除旧边缘线
    if (child.userData.edgeLine) {
      child.remove(child.userData.edgeLine)
      child.userData.edgeLine.geometry?.dispose()
      child.userData.edgeLine = null
    }

    if (mode === 'xray') {
      // 单一色实体 (无 PBR 渲染效果) + 深色边缘线框; 被实体遮挡的边自然隐藏
      child.material = flat
      const edges = new THREE.EdgesGeometry(child.geometry, 30)
      const line = new THREE.LineSegments(edges, edge)
      line.renderOrder = 2
      child.add(line)
      child.userData.edgeLine = line
    } else {
      child.material = child.userData.solidMaterial as THREE.Material
    }
  })

  requestRender()
}

function disposeThreeJs(): void {
  if (animationId !== null) { cancelAnimationFrame(animationId); animationId = null }
  if (controls) { controls.dispose(); controls = null }
  if (renderer) { renderer.dispose(); renderer = null }
  if (scene) { scene.clear(); scene = null }
  rootGroup = null; tiltGroup = null; spinGroup = null; modelGroup = null; camera = null
  if (flatMaterial) { flatMaterial.dispose(); flatMaterial = null }
  if (edgeMaterial) { edgeMaterial.dispose(); edgeMaterial = null }
}

function handleResize(): void {
  if (!viewportRef.value || !camera || !renderer) return
  const w = viewportRef.value.clientWidth
  const h = viewportRef.value.clientHeight
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  renderer.setSize(w, h)
  requestRender()
}

function onPanelToggle(e: Event): void {
  const detail = (e as CustomEvent).detail as boolean
  panelExpanded = detail
  targetModelScale = detail ? baseScale : baseScale * 1.6
  targetOffsetX = detail ? 20 : 0
}

// ── 齿轮 GLB 加载 ──
function loadGearModel(glbBase64: string): void {
  if (!scene) return

  // 解码 base64 → GLB binary
  const binaryStr: string = atob(glbBase64)
  const bytes: Uint8Array = new Uint8Array(binaryStr.length)
  for (let i = 0; i < binaryStr.length; i++) {
    bytes[i] = binaryStr.charCodeAt(i)
  }

  const gltfLoader = new GLTFLoader()
  gltfLoader.parse(bytes.buffer, '', (gltf) => {
    const mesh: THREE.Group = gltf.scene

    // 应用 PBR 材质
    mesh.traverse((child: THREE.Object3D) => {
      if (child instanceof THREE.Mesh && steelMaterial) {
        child.material = steelMaterial
        child.castShadow = true
        child.receiveShadow = true
      }
    })

    // 移除旧模型 (hob)
    if (rootGroup && scene) {
      scene.remove(rootGroup)
      disposeGroup(rootGroup)
    }

    // 计算包围盒
    const box = new THREE.Box3().setFromObject(mesh)
    const size = new THREE.Vector3()
    box.getSize(size)
    const maxDim = Math.max(size.x, size.y, size.z)
    const dist = maxDim * 2.2

    // 居中
    const cx = (box.max.x + box.min.x) / 2
    const cy = (box.max.y + box.min.y) / 2
    const cz = (box.max.z + box.min.z) / 2

    modelGroup = new THREE.Group()
    mesh.position.set(-cx, -cy, -cz)
    modelGroup.add(mesh)
    modelGroup.rotation.x = -Math.PI / 2  // Z-up → Y-up
    modelGroup.scale.setScalar(1.0)

    spinGroup = new THREE.Group()
    spinGroup.add(modelGroup)

    tiltGroup = new THREE.Group()
    tiltGroup.add(spinGroup)
    tiltGroup.rotateOnWorldAxis(new THREE.Vector3(0, 0, 1), Math.PI / 4)

    rootGroup = new THREE.Group()
    rootGroup.add(tiltGroup)
    if (scene) scene.add(rootGroup)

    // 相机适配
    controls!.target.set(0, 0, 0)
    camera!.position.set(dist * 0.6, dist * 0.5, dist * 0.7)
    camera!.near = dist * 0.001
    camera!.far = dist * 10
    camera!.updateProjectionMatrix()

    // 缩放范围随模型尺寸适配——允许大齿轮缩到很小看全整体
    controls!.minDistance = dist * 0.05
    controls!.maxDistance = dist * 10
    controls!.update()

    modelLoaded.value = true
    requestRender()
    applyRenderMode(renderMode.value)
  }, (err: unknown) => {
    console.error('GLB 加载失败:', err)
  })
}

function disposeGroup(group: THREE.Group): void {
  group.traverse((child: THREE.Object3D) => {
    if (child instanceof THREE.Mesh) {
      child.geometry.dispose()
      if (Array.isArray(child.material)) {
        child.material.forEach((m: THREE.Material) => m.dispose())
      } else if (child.material instanceof THREE.Material) {
        child.material.dispose()
      }
    } else if (child instanceof THREE.LineSegments) {
      // 每个 mesh 独立的 EdgesGeometry; edgeMaterial 共享, 由 disposeThreeJs 统一释放
      child.geometry.dispose()
    }
  })
}

function onGearModelReady(e: Event): void {
  const glbBase64: string = (e as CustomEvent).detail as string
  loadGearModel(glbBase64)
}

onMounted(() => {
  initThreeJs()
  window.addEventListener('resize', handleResize)
  window.addEventListener('panel:toggle', onPanelToggle)
  window.addEventListener('gear:model-ready', onGearModelReady)
  callBackend()
})

onUnmounted(() => {
  disposeThreeJs()
  window.removeEventListener('resize', handleResize)
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
