/**
 * gearViewport.ts — 齿轮 3D 视口的深模块（多图层）
 *
 * 从「单模型替换」重构为「命名图层集」：工件齿轮作为 workpiece 参考基准层，
 * 模块② 的产形面/前刀面/刃形/后刀面/单齿各自叠加为独立图层（子 PRD-1）。
 * 接口：loadGear（降级为工件层加载）/ addLayer / removeLayer / clearLayers /
 *       setLayerVisible / setLayerOpacity / focusLayer / setRenderMode /
 *       setLoggedIn / setModelLayout / resize / dispose
 *
 * 场景层级：rootGroup(平移) → tiltGroup(45°倾) → spinGroup(自旋)
 *          → worldGroup(Z-up 修正 + 缩放) → layerGroups[LayerId]
 * 图层数据经 window 事件 gear:layer-ready（与 gear:model-ready 并列）送达，
 * 由消费者（MainView）监听后调 addLayer（本模块不监听事件）。
 *
 * 渲染器经 rendererFactory 注入（测试用 fake，默认真实 WebGLRenderer）。
 */
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import type { Ref } from 'vue'
import {
  LAYER_VISUALS,
  MATERIAL_PRESETS,
  type LayerId,
  type LayerVisual,
} from './layerPalette'

export type RenderMode = 'solid' | 'xray'

export interface GearViewportOptions {
  /** 挂载容器（canvas 被 append 进这里）. */
  container: HTMLElement
  /** 模型加载完成标志（模块驱动）. */
  modelLoaded: Ref<boolean>
  /** STL 加载进度（模块驱动）. */
  modelLoadProgress: Ref<number>
  /** 渲染模式（模块驱动；主视图按钮绑定）. */
  renderMode: Ref<RenderMode>
  /** 齿轮 GLB 显示完成后回调（用于唤出结果面板等）. */
  onGearDisplayed: () => void
  /** 渲染器工厂（测试注入 fake，缺省用真实 WebGLRenderer）. */
  rendererFactory?: () => THREE.WebGLRenderer
}

export interface GearViewport {
  /** 加载工件齿轮 GLB（降级：清空非工件层 + 加载 workpiece 层）并适配相机. */
  loadGear: (glbBase64: string) => void
  /** 增量叠加一个图层（按 LayerId 从 palette 取材质/样式）. */
  addLayer: (id: LayerId, glbBase64: string) => void
  /** 删除一个图层（保留工件基准层）. */
  removeLayer: (id: LayerId) => void
  /** 清空所有非工件层. */
  clearLayers: () => void
  /** 单层显隐. */
  setLayerVisible: (id: LayerId, visible: boolean) => void
  /** 单层透明度（本层独立材质，不串改其它层）. */
  setLayerOpacity: (id: LayerId, opacity: number) => void
  /** 聚焦单层（其余层淡至 0.12 + 相机过渡到该层中心）. */
  focusLayer: (id: LayerId) => void
  /** 切换渲染模式（实体 / 线框）. */
  setRenderMode: (mode: RenderMode) => void
  /** 登录状态（影响自旋速度）. */
  setLoggedIn: (v: boolean) => void
  /** 设置模型目标缩放 / 右移（面板展开联动；字段可选，缺省不改）. */
  setModelLayout: (layout: { scale?: number; offsetX?: number }) => void
  /** 容器尺寸变化时重设渲染器/相机. */
  resize: () => void
  /** 释放 Three.js 资源. */
  dispose: () => void
}

/** provide/inject 键：gearViewport 实例（MainView provide，LayerPanel inject）. */
export const GEAR_VIEWPORT_KEY = 'gearViewport' as const

/** 按图层视觉定义 + child 类型创建独立材质实例（每层独立，防串改）；不匹配返回 null. */
function createLayerMaterial(visual: LayerVisual, child: THREE.Object3D): THREE.Material | null {
  const def = MATERIAL_PRESETS[visual.materialPreset]
  if (visual.kind === 'mesh' && child instanceof THREE.Mesh) {
    return new THREE.MeshStandardMaterial({
      color: def.color,
      roughness: def.roughness,
      metalness: def.metalness,
      transparent: def.transparent,
      opacity: def.opacity,
      side: visual.doubleSide ? THREE.DoubleSide : THREE.FrontSide,
    })
  }
  if (visual.kind === 'line' && (child instanceof THREE.Line || child instanceof THREE.LineSegments)) {
    return new THREE.LineBasicMaterial({ color: def.color })
  }
  if (visual.kind === 'points' && child instanceof THREE.Points) {
    return new THREE.PointsMaterial({ color: def.color, size: 0.5 })
  }
  return null
}

export function createGearViewport(options: GearViewportOptions): GearViewport {
  const { container, modelLoaded, modelLoadProgress, renderMode, onGearDisplayed } = options
  const makeRenderer = options.rendererFactory ?? ((): THREE.WebGLRenderer => new THREE.WebGLRenderer({ antialias: true }))

  // ── 内部状态 ──
  let scene: THREE.Scene | null = null
  let camera: THREE.PerspectiveCamera | null = null
  let renderer: THREE.WebGLRenderer | null = null
  let controls: OrbitControls | null = null
  let rootGroup: THREE.Group | null = null // 最外层：纯平移
  let tiltGroup: THREE.Group | null = null // 45° 静态倾斜
  let spinGroup: THREE.Group | null = null // 持续自旋
  let worldGroup: THREE.Group | null = null // Z-up 修正 + 缩放（各图层父级）
  let stlGroup: THREE.Group | null = null // 初始滚刀 STL（登录前装饰，loadGear 时移除）
  let flatMaterial: THREE.MeshBasicMaterial | null = null // 线框模式: 单一色实体
  let edgeMaterial: THREE.LineBasicMaterial | null = null // 线框模式: 深色边缘线
  let environmentTexture: THREE.Texture | null = null // 环境贴图（dispose 补漏）
  let pmremGenerator: THREE.PMREMGenerator | null = null // 环境贴图生成器（dispose 补漏）
  const layerGroups: Partial<Record<LayerId, THREE.Group>> = {} // 各图层 group
  const layerMaterials = new Map<LayerId, THREE.Material[]>() // 每层材质实例（dispose 用）
  let animationId: number | null = null
  const verticalAxis = new THREE.Vector3(0, 1, 0) // 上下
  let currentSpinAxis = verticalAxis.clone()
  let targetSpinAxis = verticalAxis.clone()
  let spinSpeed = 0.006 // 欢迎界面转速
  let userInteracted = false
  let renderRequested = true // on-demand 渲染标志
  const BG_SOLID = new THREE.Color(0xebeff3) // 实体模式背景
  const BG_XRAY = new THREE.Color(0xffffff) // 线框模式背景 (图纸白底)
  // 业务联动目标（经 setter 注入）
  let targetModelScale = 3.0
  let targetOffsetX = 0
  let loggedIn = false
  let focusFrom: THREE.Vector3 | null = null // 聚焦相机过渡起点
  let focusTo: THREE.Vector3 | null = null // 聚焦相机过渡终点
  let focusStart = 0 // 聚焦过渡起始时间戳（ms）

  function requestRender(): void {
    renderRequested = true
  }

  function applyRenderModeInternal(mode: RenderMode): void {
    renderMode.value = mode
    if (!scene || !edgeMaterial || !flatMaterial) return
    const edge = edgeMaterial
    const flat = flatMaterial
    scene.background = mode === 'xray' ? BG_XRAY : BG_SOLID
    scene.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return
      if (!child.userData.solidMaterial) {
        child.userData.solidMaterial = child.material
      }
      if (child.userData.edgeLine) {
        child.remove(child.userData.edgeLine)
        child.userData.edgeLine.geometry?.dispose()
        child.userData.edgeLine = null
      }
      if (mode === 'xray') {
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

  /** 相机适配到给定包围盒（near/far/距离/旋转中心）. */
  function fitCameraToBox(box: THREE.Box3): void {
    if (!camera || !controls) return
    const size = new THREE.Vector3()
    box.getSize(size)
    const maxDim = Math.max(size.x, size.y, size.z)
    const dist = maxDim * 2.2
    const cx = (box.max.x + box.min.x) / 2
    const cy = (box.max.y + box.min.y) / 2
    const cz = (box.max.z + box.min.z) / 2
    camera.near = dist * 0.001
    camera.far = dist * 10
    camera.updateProjectionMatrix()
    controls.minDistance = dist * 0.05
    controls.maxDistance = dist * 10
    controls.target.set(cx, cy, cz)
    controls.update()
  }

  function init(): void {
    const width = container.clientWidth
    const height = container.clientHeight

    renderer = makeRenderer()
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.2
    container.appendChild(renderer.domElement)

    scene = new THREE.Scene()

    // 环境贴图（无 WebGL 环境时跳过，供测试）
    try {
      pmremGenerator = new THREE.PMREMGenerator(renderer)
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
      environmentTexture = pmremGenerator.fromScene(envScene, 0.04).texture
      scene.environment = environmentTexture
      envScene.clear()
    } catch (err) {
      // 无 WebGL 上下文（测试 fake renderer）→ 跳过环境贴图
      environmentTexture = null
    }
    scene.background = new THREE.Color(0xebeff3)

    // 相机
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100)
    camera.position.set(4, 2.5, 6)
    camera.lookAt(0, 0.5, 0)

    // 轨道控制器
    controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(0, 0.5, 0)
    controls.enableDamping = true
    controls.dampingFactor = 0.08
    controls.autoRotate = false
    controls.minDistance = 5
    controls.maxDistance = 200
    controls.maxPolarAngle = Math.PI * 0.7
    controls.enabled = false // 登录期间禁用
    controls.update()

    function stopAutoRotate(): void {
      userInteracted = true
      if (controls) controls.autoRotate = false
      controls?.removeEventListener('start', stopAutoRotate)
    }
    controls.addEventListener('start', () => requestRender())
    controls.addEventListener('change', () => requestRender())
    controls.addEventListener('start', stopAutoRotate)

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

    // 线框辅助材质
    flatMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff })
    edgeMaterial = new THREE.LineBasicMaterial({ color: 0x1f2937 })

    // 场景层级（各图层父级 worldGroup 统一 Z-up 修正 + 缩放）
    rootGroup = new THREE.Group()
    tiltGroup = new THREE.Group()
    spinGroup = new THREE.Group()
    worldGroup = new THREE.Group()
    worldGroup.rotation.x = -Math.PI / 2
    spinGroup.add(worldGroup)
    tiltGroup.add(spinGroup)
    tiltGroup.rotateOnWorldAxis(new THREE.Vector3(0, 0, 1), Math.PI / 4)
    rootGroup.add(tiltGroup)
    scene.add(rootGroup)

    // 初始滚刀 STL（登录前装饰，loadGear 时移除）
    const stlLoader = new STLLoader()
    stlLoader.load(
      '/hob.stl',
      (geometry: THREE.BufferGeometry) => {
        geometry.computeBoundingBox()
        const bbox = geometry.boundingBox!
        const cx = (bbox.max.x + bbox.min.x) / 2
        const cy = (bbox.max.y + bbox.min.y) / 2
        const cz = (bbox.max.z + bbox.min.z) / 2
        geometry.translate(-cx, -cy, -cz)
        const size = new THREE.Vector3()
        bbox.getSize(size)
        const maxDim = Math.max(size.x, size.y, size.z)
        const dist = maxDim * 2.2
        camera!.near = dist * 0.001
        camera!.far = dist * 10
        camera!.updateProjectionMatrix()
        controls!.minDistance = dist * 0.05
        controls!.maxDistance = dist * 10
        const carbide = MATERIAL_PRESETS.carbide
        const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
          color: carbide.color, roughness: carbide.roughness, metalness: carbide.metalness,
        }))
        mesh.castShadow = true
        mesh.receiveShadow = true
        stlGroup = new THREE.Group()
        stlGroup.add(mesh)
        worldGroup!.add(stlGroup)
        controls!.target.set(0, 0, 0)
        camera!.position.set(dist * 0.6, dist * 0.5, dist * 0.7)
        controls!.update()
        modelLoaded.value = true
        requestRender()
        applyRenderModeInternal(renderMode.value)
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

    // 动画（on-demand 渲染）
    function animate(): void {
      animationId = requestAnimationFrame(animate)
      let sceneDirty = false
      if (worldGroup) {
        const diff = targetModelScale - worldGroup.scale.x
        if (Math.abs(diff) > 0.001) {
          worldGroup.scale.setScalar(worldGroup.scale.x + diff * 0.06)
          sceneDirty = true
        }
      }
      if (rootGroup) {
        const diff = targetOffsetX - rootGroup.position.x
        if (Math.abs(diff) > 0.05) {
          rootGroup.position.x += diff * 0.08
          sceneDirty = true
        }
      }
      if (focusTo && controls && focusFrom) {
        const t = Math.min(1, (performance.now() - focusStart) / 500)
        const eased = 1 - Math.pow(1 - t, 3) // easeOutCubic 近似品牌缓动 cubic-bezier(0.22,0.61,0.36,1)
        controls.target.lerpVectors(focusFrom, focusTo, eased)
        if (t >= 1) {
          focusFrom = null
          focusTo = null
        }
        sceneDirty = true
      }
      if (spinGroup && !userInteracted) {
        currentSpinAxis.lerp(targetSpinAxis, 0.02)
        if (loggedIn) {
          spinSpeed += (0.002 - spinSpeed) * 0.03
        }
        spinGroup.rotateOnWorldAxis(currentSpinAxis, spinSpeed)
        sceneDirty = true
      }
      controls?.update()
      if (renderer && scene && camera && (renderRequested || sceneDirty)) {
        renderRequested = false
        renderer.render(scene, camera)
      }
    }
    animate()
  }

  /** 移除一个图层的 group 并释放其材质（不触碰其它层）. */
  function removeLayerGroup(id: LayerId): void {
    const group = layerGroups[id]
    if (group) {
      worldGroup?.remove(group)
      disposeGroup(group)
      delete layerGroups[id]
    }
    const mats = layerMaterials.get(id)
    if (mats) {
      mats.forEach((m) => m.dispose())
      layerMaterials.delete(id)
    }
  }

  /** 把解析好的图层 scene 挂载为命名图层 group（赋材质 + 建 group + 加入 worldGroup）. */
  function mountLayer(id: LayerId, mesh: THREE.Group): void {
    const visual = LAYER_VISUALS[id]
    const mats: THREE.Material[] = []
    mesh.traverse((child: THREE.Object3D) => {
      const mat = createLayerMaterial(visual, child)
      if (!mat) return
      mats.push(mat)
      if (child instanceof THREE.Mesh) {
        child.material = mat
        child.castShadow = true
        child.receiveShadow = true
      } else {
        const obj = child as THREE.Line | THREE.LineSegments | THREE.Points
        obj.material = mat
      }
    })
    removeLayerGroup(id)
    const group = new THREE.Group()
    group.name = id
    group.add(mesh)
    worldGroup!.add(group)
    layerGroups[id] = group
    layerMaterials.set(id, mats)
    requestRender()
    applyRenderModeInternal(renderMode.value)
  }

  // ── 图层 GLB 解码 + 加载 ──
  function parseGlb(glbBase64: string, onLoad: (mesh: THREE.Group) => void): void {
    const binaryStr: string = atob(glbBase64)
    const bytes: Uint8Array = new Uint8Array(binaryStr.length)
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i)
    }
    const gltfLoader = new GLTFLoader()
    gltfLoader.parse(bytes.buffer, '', (gltf) => onLoad(gltf.scene), (err: unknown) => {
      console.error('GLB 加载失败:', err)
    })
  }

  // ── 增量叠加图层 ──
  function addLayer(id: LayerId, glbBase64: string): void {
    if (!scene || !worldGroup) return
    parseGlb(glbBase64, (mesh) => mountLayer(id, mesh))
  }

  // ── 工件齿轮 GLB 加载（降级：清空非工件层 + 加载工件层） ──
  function loadGear(glbBase64: string): void {
    if (!scene) return
    // 清空非工件层 + 移除 STL 装饰
    clearLayers()
    if (stlGroup) {
      worldGroup?.remove(stlGroup)
      disposeGroup(stlGroup)
      stlGroup = null
    }
    parseGlb(glbBase64, (mesh) => {
      mountLayer('workpiece', mesh)
      // 相机适配到工件包围盒
      const box = new THREE.Box3().setFromObject(mesh)
      fitCameraToBox(box)
      modelLoaded.value = true
      onGearDisplayed()
    })
  }

  function removeLayer(id: LayerId): void {
    if (id === 'workpiece') return // 工件基准层不删除
    removeLayerGroup(id)
    requestRender()
  }

  function clearLayers(): void {
    for (const id of Object.keys(layerGroups) as LayerId[]) {
      if (id === 'workpiece') continue
      removeLayerGroup(id)
    }
    requestRender()
  }

  function setLayerVisible(id: LayerId, visible: boolean): void {
    const group = layerGroups[id]
    if (group) group.visible = visible
    requestRender()
  }

  function setLayerOpacity(id: LayerId, opacity: number): void {
    const group = layerGroups[id]
    if (!group) return
    group.traverse((child) => {
      const mat = (child as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined
      if (Array.isArray(mat)) {
        mat.forEach((m) => { m.transparent = true; m.opacity = opacity })
      } else if (mat && 'opacity' in mat) {
        mat.transparent = true
        mat.opacity = opacity
      }
    })
    requestRender()
  }

  function focusLayer(id: LayerId): void {
    const group = layerGroups[id]
    if (!group) return
    // 其余层淡至 0.12，目标层恢复默认
    for (const other of Object.keys(layerGroups) as LayerId[]) {
      if (other === id) {
        setLayerOpacity(other, LAYER_VISUALS[other].defaultOpacity)
      } else {
        setLayerOpacity(other, 0.12)
      }
    }
    // 相机过渡到该层包围盒中心（500ms 品牌缓动）
    const box = new THREE.Box3().setFromObject(group)
    focusFrom = controls ? controls.target.clone() : null
    focusTo = box.getCenter(new THREE.Vector3())
    focusStart = performance.now()
    requestRender()
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
      } else if (child instanceof THREE.LineSegments || child instanceof THREE.Line || child instanceof THREE.Points) {
        child.geometry.dispose()
        const mat = (child as THREE.LineSegments).material
        if (mat instanceof THREE.Material) mat.dispose()
      }
    })
  }

  function dispose(): void {
    if (animationId !== null) {
      cancelAnimationFrame(animationId)
      animationId = null
    }
    if (controls) {
      controls.dispose()
      controls = null
    }
    // 释放各图层 group（含工件）的 geometry/material
    if (worldGroup) {
      disposeGroup(worldGroup)
      worldGroup = null
    }
    layerGroups && Object.keys(layerGroups).forEach((k) => delete layerGroups[k as LayerId])
    layerMaterials.forEach((mats) => mats.forEach((m) => m.dispose()))
    layerMaterials.clear()
    if (flatMaterial) {
      flatMaterial.dispose()
      flatMaterial = null
    }
    if (edgeMaterial) {
      edgeMaterial.dispose()
      edgeMaterial = null
    }
    if (environmentTexture) {
      environmentTexture.dispose()
      environmentTexture = null
    }
    if (pmremGenerator) {
      pmremGenerator.dispose()
      pmremGenerator = null
    }
    if (renderer) {
      renderer.dispose()
      if (renderer.domElement && renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement)
      }
      renderer = null
    }
    if (scene) {
      scene.clear()
      scene = null
    }
    rootGroup = null
    tiltGroup = null
    spinGroup = null
    stlGroup = null
    camera = null
    focusFrom = null
    focusTo = null
  }

  function resize(): void {
    if (!container || !camera || !renderer) return
    const w = container.clientWidth
    const h = container.clientHeight
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
    requestRender()
  }

  init()

  return {
    loadGear,
    addLayer,
    removeLayer,
    clearLayers,
    setLayerVisible,
    setLayerOpacity,
    focusLayer,
    setRenderMode: applyRenderModeInternal,
    setLoggedIn: (v: boolean) => {
      loggedIn = v
    },
    setModelLayout: (layout: { scale?: number; offsetX?: number }) => {
      if (layout.scale !== undefined) targetModelScale = layout.scale
      if (layout.offsetX !== undefined) targetOffsetX = layout.offsetX
    },
    resize,
    dispose,
  }
}
