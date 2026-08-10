/**
 * GearViewport.ts — 齿轮 3D 视口的深模块
 *
 * 将原先 HelloWorld.vue 内 ~430 行的 Three.js 场景生命周期收拢进一个小接口：
 *   loadGear / setRenderMode / setLoggedIn / setModelLayout / resize / dispose
 * HelloWorld（调用者）只负责「把 GLB 交给它、面板/登录联动发信号、渲染模式按钮绑定」，
 * 场景/相机/渲染器/材质/布光/动画循环的细节全部藏于模块实现（架构审查 C3）。
 *
 * 消费者注入三个可观察 ref（modelLoaded / modelLoadProgress / renderMode）供模板绑定，
 * 由模块驱动其值；onGearDisplayed 在齿轮 GLB 显示完成后回调。
 */
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import type { Ref } from 'vue'

export type RenderMode = 'solid' | 'xray'

export interface GearViewportOptions {
  /** 挂载容器（canvas 被 append 进这里）. */
  container: HTMLElement
  /** 模型加载完成标志（模块驱动）. */
  modelLoaded: Ref<boolean>
  /** STL 加载进度（模块驱动）. */
  modelLoadProgress: Ref<number>
  /** 渲染模式（模块驱动；HelloWorld 按钮绑定）. */
  renderMode: Ref<RenderMode>
  /** 齿轮 GLB 显示完成后回调（用于唤出结果面板等）. */
  onGearDisplayed: () => void
}

export interface GearViewport {
  /** 加载齿轮 GLB 并适配相机（内部替换模型组）. */
  loadGear: (glbBase64: string) => void
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

export function createGearViewport(options: GearViewportOptions): GearViewport {
  const { container, modelLoaded, modelLoadProgress, renderMode, onGearDisplayed } = options

  // ── 内部状态（不再泄漏为模块级 let） ──
  let scene: THREE.Scene | null = null
  let camera: THREE.PerspectiveCamera | null = null
  let renderer: THREE.WebGLRenderer | null = null
  let controls: OrbitControls | null = null
  let rootGroup: THREE.Group | null = null // 最外层：纯平移
  let tiltGroup: THREE.Group | null = null // 45° 静态倾斜
  let spinGroup: THREE.Group | null = null // 持续自旋
  let modelGroup: THREE.Group | null = null // 内层：Z-up 修正
  let steelMaterial: THREE.MeshStandardMaterial | null = null // 不锈钢 PBR 材质 (齿轮)
  let carbideMaterial: THREE.MeshStandardMaterial | null = null // 硬质合金 PBR 材质 (刀具)
  let flatMaterial: THREE.MeshBasicMaterial | null = null // 线框模式: 单一色实体
  let edgeMaterial: THREE.LineBasicMaterial | null = null // 线框模式: 深色边缘线
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

  function init(): void {
    const width = container.clientWidth
    const height = container.clientHeight

    renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.2
    container.appendChild(renderer.domElement)

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
    scene.background = new THREE.Color(0xebeff3)
    envScene.clear()

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

    // 材质
    carbideMaterial = new THREE.MeshStandardMaterial({ color: 0x5a5854, roughness: 0.28, metalness: 0.97 })
    steelMaterial = new THREE.MeshStandardMaterial({ color: 0x9a9aa0, roughness: 0.32, metalness: 0.98 })
    flatMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff })
    edgeMaterial = new THREE.LineBasicMaterial({ color: 0x1f2937 })

    // 初始刀具 STL
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
        const mat: THREE.MeshStandardMaterial = carbideMaterial!
        const mesh = new THREE.Mesh(geometry, mat)
        mesh.castShadow = true
        mesh.receiveShadow = true
        modelGroup = new THREE.Group()
        modelGroup.add(mesh)
        modelGroup.rotation.x = -Math.PI / 2
        modelGroup.scale.setScalar(3.0)
        spinGroup = new THREE.Group()
        spinGroup.add(modelGroup)
        tiltGroup = new THREE.Group()
        tiltGroup.add(spinGroup)
        tiltGroup.rotateOnWorldAxis(new THREE.Vector3(0, 0, 1), Math.PI / 4)
        rootGroup = new THREE.Group()
        rootGroup.add(tiltGroup)
        scene!.add(rootGroup)
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
      if (modelGroup) {
        const diff = targetModelScale - modelGroup.scale.x
        if (Math.abs(diff) > 0.001) {
          modelGroup.scale.setScalar(modelGroup.scale.x + diff * 0.06)
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

  // ── 齿轮 GLB 加载 ──
  function loadGear(glbBase64: string): void {
    if (!scene) return
    const binaryStr: string = atob(glbBase64)
    const bytes: Uint8Array = new Uint8Array(binaryStr.length)
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i)
    }
    const gltfLoader = new GLTFLoader()
    gltfLoader.parse(bytes.buffer, '', (gltf) => {
      const mesh: THREE.Group = gltf.scene
      mesh.traverse((child: THREE.Object3D) => {
        if (child instanceof THREE.Mesh && steelMaterial) {
          child.material = steelMaterial
          child.castShadow = true
          child.receiveShadow = true
        }
      })
      if (rootGroup && scene) {
        scene.remove(rootGroup)
        disposeGroup(rootGroup)
      }
      const box = new THREE.Box3().setFromObject(mesh)
      const size = new THREE.Vector3()
      box.getSize(size)
      const maxDim = Math.max(size.x, size.y, size.z)
      const dist = maxDim * 2.2
      const cx = (box.max.x + box.min.x) / 2
      const cy = (box.max.y + box.min.y) / 2
      const cz = (box.max.z + box.min.z) / 2
      modelGroup = new THREE.Group()
      mesh.position.set(-cx, -cy, -cz)
      modelGroup.add(mesh)
      modelGroup.rotation.x = -Math.PI / 2
      modelGroup.scale.setScalar(1.0)
      spinGroup = new THREE.Group()
      spinGroup.add(modelGroup)
      tiltGroup = new THREE.Group()
      tiltGroup.add(spinGroup)
      tiltGroup.rotateOnWorldAxis(new THREE.Vector3(0, 0, 1), Math.PI / 4)
      rootGroup = new THREE.Group()
      rootGroup.add(tiltGroup)
      if (scene) scene.add(rootGroup)
      controls!.target.set(0, 0, 0)
      camera!.position.set(dist * 0.6, dist * 0.5, dist * 0.7)
      camera!.near = dist * 0.001
      camera!.far = dist * 10
      camera!.updateProjectionMatrix()
      controls!.minDistance = dist * 0.05
      controls!.maxDistance = dist * 10
      controls!.update()
      modelLoaded.value = true
      requestRender()
      applyRenderModeInternal(renderMode.value)
      onGearDisplayed()
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
        child.geometry.dispose()
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
    if (renderer) {
      renderer.dispose()
      renderer = null
    }
    if (scene) {
      scene.clear()
      scene = null
    }
    rootGroup = null
    tiltGroup = null
    spinGroup = null
    modelGroup = null
    camera = null
    if (flatMaterial) {
      flatMaterial.dispose()
      flatMaterial = null
    }
    if (edgeMaterial) {
      edgeMaterial.dispose()
      edgeMaterial = null
    }
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
