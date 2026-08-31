/**
 * gearViewport.ts — 齿轮 3D 视口的深模块（多图层）
 *
 * 从「单模型替换」重构为「命名图层集」：工件齿轮作为 workpiece 参考基准层，
 * 模块② 的扫掠点云/前刀面/刃形/后刀面/单齿各自叠加为独立图层（子 PRD-1）。
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

/** 工件视图模式：实体（不透明钢） / 透明线框（透明面 + 深色边线，便于观察内部刀具层）. */
export type WorkpieceViewMode = 'solid' | 'wireframe'

/** 标准视图方向（Z-up CAD 坐标系）. */
export type StandardView = 'top' | 'bottom' | 'front' | 'back' | 'left' | 'right'

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
  /** 设置安装参数（中心距 a + 轴交角 Σ + 刀具旋向 j_t），把刀具系 T 图层变换到工件系 W + 画 W/T 坐标轴. */
  setEnvelopeInstall: (a: number, sigmaDeg: number, j_t?: number) => void
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
  /** 工件视图切换：实体 / 透明线框（透明钢面 + 深色边线，观察内部刀具层）. */
  setWorkpieceView: (mode: WorkpieceViewMode) => void
  /** 等效产形齿轮样式切换：靛蓝单色 / 干涉热力图（符号距离顶点色）. */
  setConjugateGearInterference: (on: boolean) => void
  /** 登录状态（影响自旋速度）. */
  setLoggedIn: (v: boolean) => void
  /** 设置模型目标缩放 / 右移（面板展开联动；字段可选，缺省不改）. */
  setModelLayout: (layout: { scale?: number; offsetX?: number }) => void
  /** 容器尺寸变化时重设渲染器/相机. */
  resize: () => void
  /** 释放 Three.js 资源. */
  dispose: () => void
  /** 加载运动仿真动画数据（齿面网格 + 分度圆；omega_ratio 存在时启用任意 φ 合成）. */
  loadAnimMesh: (
    animData: {
      frames: Array<{ phi_t_deg: number; positions: number[] }>
      indices: number[]
      mesh_indices: number[]
      n_vertices: number
      theta_range_deg: number
      omega_ratio?: number
      n_profile?: number
      layer_zs?: number[]
    },
    pitchRadii: { rpw: number; rpt: number; z_w?: number },
    onFrameUpdate?: (phiDeg: number) => void,
  ) => void
  /** 更新动画到指定 φ_t [deg]（合成模式任意角；回退模式夹到帧网格后插值）. */
  setAnimPhi: (phiDeg: number) => void
  /** 设置播放/暂停. */
  setAnimPlaying: (playing: boolean) => void
  /** 设置播放速度倍率. */
  setAnimSpeed: (speed: number) => void
  /** 切换单齿/全齿. */
  setAnimGearMode: (mode: 'single' | 'full') => void
  /** 截面切片：沿齿向选廓线平面（iz = 轴向层号，null = 恢复全齿面渲染）. */
  setAnimSection: (iz: number | null) => void
  /** 切换光谱扫掠面模式（true=显示所有帧叠加扫掠面，false=恢复逐帧动画）. */
  setSpectrumMode: (on: boolean) => void
  /** 光谱揭示：显示 −span..phiDeg 的采样，当前位置高亮. */
  setSpectrumReveal: (phiDeg: number) => void
  /** 清理动画网格和分度圆. */
  clearAnimMesh: () => void
  /** 获取模型包围盒中心与距离（ViewCube 相机定位用）. */
  getViewInfo: () => { center: THREE.Vector3; distance: number }
  /** 切换到标准视图（带 300ms 过渡动画）. */
  setStandardView: (view: StandardView) => void
  /** 恢复初始视角（Home 按钮用）. */
  resetView: () => void
  /** 获取 ViewCube 旋转矩阵（CSS matrix3d 16 值，每帧由 animate 更新）. */
  getViewCubeRotation: () => number[]
}

/** provide/inject 键：gearViewport 实例（MainView provide，LayerPanel inject）. */
export const GEAR_VIEWPORT_KEY = 'gearViewport' as const

/** 判断几何是否带 COLOR_0 顶点色（GLTFLoader 解析为 geometry.attributes.color）. */
function hasVertexColor(geo: THREE.BufferGeometry): boolean {
  return geo.hasAttribute('color')
}

/** 圆环弧线（旋转指针弧身）：radius 半径、endAngle 扫掠角（正=逆时针、负=顺时针）. */
class CircularArcCurve extends THREE.Curve<THREE.Vector3> {
  constructor(private radius: number, private endAngle: number) {
    super()
  }
  getPoint(t: number, optionalTarget?: THREE.Vector3): THREE.Vector3 {
    const a = t * this.endAngle
    const x = this.radius * Math.cos(a)
    const y = this.radius * Math.sin(a)
    if (optionalTarget) {
      optionalTarget.set(x, y, 0)
      return optionalTarget
    }
    return new THREE.Vector3(x, y, 0)
  }
}

/** 按 child 类型 + 是否带顶点色创建独立材质实例（每子元素独立，防串改）；不匹配返回 null. */
function createLayerMaterial(visual: LayerVisual, child: THREE.Object3D): THREE.Material | null {
  const def = MATERIAL_PRESETS[visual.materialPreset]
  if (child instanceof THREE.Mesh) {
    const geo = child.geometry as THREE.BufferGeometry
    // 顶点色优先（扫掠点云光谱）：白底 + vertexColors；否则走 palette 单色
    if (hasVertexColor(geo)) {
      return new THREE.MeshStandardMaterial({
        color: 0xffffff,
        vertexColors: true,
        roughness: def.roughness,
        metalness: def.metalness,
        transparent: def.transparent,
        opacity: def.opacity,
        side: visual.doubleSide ? THREE.DoubleSide : THREE.FrontSide,
      })
    }
    return new THREE.MeshStandardMaterial({
      color: def.color,
      roughness: def.roughness,
      metalness: def.metalness,
      transparent: def.transparent,
      opacity: def.opacity,
      side: visual.doubleSide ? THREE.DoubleSide : THREE.FrontSide,
      // 共面图层（rake 面片/后刀面 ribbon 与实体帽盖/侧面严格共面）深度推后防 z-fighting
      polygonOffset: visual.polygonOffset === true,
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    })
  }
  if (child instanceof THREE.Line || child instanceof THREE.LineSegments) {
    const geo = child.geometry as THREE.BufferGeometry
    if (hasVertexColor(geo)) {
      return new THREE.LineBasicMaterial({ color: 0xffffff, vertexColors: true })
    }
    return new THREE.LineBasicMaterial({ color: def.color })
  }
  if (child instanceof THREE.Points) {
    const geo = child.geometry as THREE.BufferGeometry
    // 图层可自定义点尺寸与衰减模式（toothFlank：屏幕空间 4px——世界单位点与采样间距不匹配会连成条带）
    const size = visual.pointSize ?? 0.5
    const sizeAttenuation = visual.pointSizeAttenuation ?? true
    if (hasVertexColor(geo)) {
      return new THREE.PointsMaterial({ color: 0xffffff, vertexColors: true, size, sizeAttenuation })
    }
    return new THREE.PointsMaterial({ color: def.color, size, sizeAttenuation })
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
  const growingGeometries = new Map<THREE.BufferGeometry, number>() // 逐点生长动画：geometry → 目标顶点数
  let animationId: number | null = null

  // ── 安装变换 + 坐标轴（刀具系 T ↔ 工件系 W） ──
  const AXIS_LENGTH = 120.0 // 坐标轴基准长度 [mm]（实际 = 0.25×工件包围球半径，整组缩放实现）
  const AXIS_SIZE_RATIO = 0.25 // 目标轴长 / 工件包围球半径（坐标系约为齿轮尺寸的 1/4）
  const AXIS_MIN_LENGTH = 15.0 // 坐标轴长度下限 [mm]（小齿轮仍保持可读）
  const AXIS_MAX_LENGTH = 60.0 // 坐标轴长度上限 [mm]（大齿轮不过分夸张）
  const AXIS_SHAFT_RADIUS = 1.2 // 轴身圆柱半径 [mm]（基准长度下的局部值，随组缩放）
  const AXIS_CONE_RADIUS = 3.0 // 轴端圆锥箭头半径 [mm]（局部值）
  const AXIS_CONE_HEIGHT = 10.0 // 轴端圆锥箭头长度 [mm]（局部值；轴身相应缩短）
  const AXIS_LABEL_OFFSET = 10.0 // 标注文字距轴尖偏移 [mm]
  const AXIS_LABEL_HEIGHT = 14.0 // 标注文字世界高度 [mm]
  const ROTATION_POINTER_RADIUS = 15.0 // 旋转指针圆弧半径 [mm]
  const ROTATION_POINTER_ARC = Math.PI * 1.5 // 圆弧扫掠角 ≈ 270°（留 90° 缺口放箭头）
  const ROTATION_POINTER_COLOR = 0xff9500 // 琥珀色（旋转指针 = 运动示意）
  const ROTATION_POINTER_OMEGA = Math.PI // 旋转指针角速度 ≈ 1 圈/2 秒 [rad/s]
  let rotationPointers: Array<{ group: THREE.Group; dir: 1 | -1 }> = [] // 渲染循环驱动的旋转指针
  let lastPointerTime = 0 // 指针动画上一帧时间戳 [ms]
  let envelopeInstall: { a: number; sigma: number } | null = null // a [mm], sigma [rad]
  let envelopeJt: number = -1 // 刀具旋向 j_t（+1 右旋逆时针 / −1 左旋顺时针，驱动 T 轴旋转指针方向）
  let axesGroup: THREE.Group | null = null // W/T 坐标轴 group

  // ── 运动仿真动画 ──
  let animGroup: THREE.Group | null = null       // 动画齿面 + 分度圆 group
  let animGeometry: THREE.BufferGeometry | null = null
  let animMesh: THREE.Mesh | null = null
  let animFramePositions: Float32Array[] = []     // 每帧 positions（Float32Array）
  let animMeshIndices: Uint32Array | null = null  // 三角网索引（重映射后）
  let animMAnim = 0                               // 总帧数
  let animPlaying = false
  let animFrameFloat = 0                          // 连续帧号（回退插值模式用）
  let animDirection: 1 | -1 = 1
  let animSpeed = 1
  let animLastTime = 0                            // 上一帧时间戳 [ms]
  // ── φ 角度域合成（K-0.5 链）：任意 φ_t 实时合成扫掠位置，帧数据不再限制范围 ──
  const ANIM_SPAN_DEG = 360                       // 合成可用时滑条/播放半程 [deg]
  let animPhiDeg = 0                              // 当前 φ_t [deg]（连续）
  let animSpanDeg = 40                            // 播放/滑条半程 [deg]（合成=360，回退=帧范围）
  let animSynthOk = false                         // 合成自校验通过（失败回退帧插值）
  let animBasePos: Float32Array = new Float32Array(0) // W 系基准点 P_W = M(φ0)^{-1}·frame0
  let animScratch: Float32Array = new Float32Array(0) // 合成/插值单齿顶点暂存（免每帧分配）
  let animChain: { a: number; sigma: number; omega: number } | null = null // 链参数
  let animPhi0 = 0                                // 帧网格 φ 起点 [deg]
  let animPhiStep = 0                             // 帧间 φ 步长 [deg]
  let pitchCirclesGroup: THREE.Group | null = null // 分度圆 group
  // 全齿模式：CPU 侧逐帧旋转，不使用 InstancedMesh
  let fullGearGeometry: THREE.BufferGeometry | null = null
  let fullGearMesh: THREE.Mesh | null = null
  let fullGearIndices: Uint32Array | null = null   // 全齿三角网索引（z_w 份单齿偏移）
  let animZW = 0                                  // 工件齿数（全齿实例化用）
  // 光谱扫掠面模式：所有帧叠加显示 + jet 光谱色
  let spectrumMode = false
  let spectrumMesh: THREE.Group | null = null
  let animGearMode: 'single' | 'full' = 'single' // 当前齿轮模式（动画/光谱共用）
  // ViewCube 视角过渡动画（tilt/spin 立即归零，只动画相机位置）
  let viewTransition: {
    from: THREE.Vector3; to: THREE.Vector3
    upFrom: THREE.Vector3; upTo: THREE.Vector3
    start: number; duration: number
  } | null = null
  let initialCameraPos: THREE.Vector3 | null = null
  let initialCameraUp: THREE.Vector3 | null = null
  let savedMaxPolarAngle: number | null = null // ViewCube 转场期间暂存原始 maxPolarAngle
  let animFrameCallback: ((phiDeg: number) => void) | null = null
  // 扫掠点云图层透明度因子（用户滑条值；与逐帧揭示 opacity 相乘，默认 1 不衰减）
  let sweptCloudOpacityFactor = 1
  // ── 截面切片（沿齿向选廓线平面）：线渲染替代面网格 ──
  let animVertexOrig: Uint32Array = new Uint32Array(0) // mesh 顶点在原始 N 点中的索引（层号 = orig//n_profile）
  let animNProfile = 0                               // 每层廓形点数 n（>0 才可切截面）
  let animLayerZs: number[] = []                     // 各层 W 系 z 坐标 [mm]（UI 显示用）
  let sectionIz: number | null = null                // 当前截面层号（null = 全齿面）
  let sectionSegPairs: number[] = []                 // 层内相邻 iu 线段顶点对（帧顶点序）
  let sectionGroup: THREE.Group | null = null        // 截面动画线容器
  let sectionAnimLine: THREE.LineSegments | null = null   // 单齿廓线（动画模式）
  let sectionAnimGear: THREE.LineSegments | null = null   // 全齿廓线（动画模式）

  /** 清空旋转指针登记（坐标轴重建 / 清层 / dispose 时调用，并复位时间戳防跳变）. */
  function clearRotationPointers(): void {
    rotationPointers = []
    lastPointerTime = 0
  }
  const verticalAxis = new THREE.Vector3(0, 1, 0) // 上下
  let currentSpinAxis = verticalAxis.clone()
  let targetSpinAxis = verticalAxis.clone()
  let spinSpeed = 0.006 // 欢迎界面转速
  let userInteracted = false
  let renderRequested = true // on-demand 渲染标志
  let workpieceViewMode: WorkpieceViewMode = 'solid' // 工件视图模式（实体 / 透明线框）
  let conjugateGearInterference = false // 等效产形齿轮样式（false=靛蓝单色，true=干涉顶点色）
  // 业务联动目标（经 setter 注入）
  let targetModelScale = 3.0
  let targetOffsetX = 0
  let loggedIn = false
  let focusFrom: THREE.Vector3 | null = null // 聚焦相机过渡起点
  let focusTo: THREE.Vector3 | null = null // 聚焦相机过渡终点
  let focusStart = 0 // 聚焦过渡起始时间戳（ms）

  /** 恢复原始 maxPolarAngle（底视图转场放行后调用）. */
  function restoreMaxPolarAngle(): void {
    if (savedMaxPolarAngle !== null && controls) {
      controls.maxPolarAngle = savedMaxPolarAngle
      savedMaxPolarAngle = null
    }
  }

  function requestRender(): void {
    renderRequested = true
  }

  function applyRenderModeInternal(mode: RenderMode): void {
    renderMode.value = mode
    if (!scene || !edgeMaterial || !flatMaterial) return
    const edge = edgeMaterial
    const flat = flatMaterial
    scene.background = null
    container.classList.toggle('vp-xray', mode === 'xray') // 背景渐变切换（theme.css）
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
    // 全局渲染模式改完后，再按工件视图模式修正工件层（透明线框优先于全局实体/线框，只动工件层）
    applyWorkpieceView()
    requestRender()
  }

  /** 把工件层按 workpieceViewMode 应用实体 / 透明线框（透明钢面 + 深色边线，只动工件层）. */
  function applyWorkpieceView(): void {
    const group = layerGroups['workpiece']
    if (!group) return
    group.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return
      // 移除旧线框边线
      if (child.userData.workpieceWireLine) {
        child.remove(child.userData.workpieceWireLine)
        child.userData.workpieceWireLine.geometry?.dispose()
        child.userData.workpieceWireLine = null
      }
      if (workpieceViewMode === 'wireframe') {
        // 首次进入线框：暂存原始实体材质（用于切回）
        if (!child.userData.workpieceSolidMaterial) {
          child.userData.workpieceSolidMaterial = child.material
        }
        const def = MATERIAL_PRESETS.steel
        child.material = new THREE.MeshStandardMaterial({
          color: def.color,
          roughness: def.roughness,
          metalness: def.metalness,
          transparent: true,
          opacity: 0.15,
          side: THREE.DoubleSide,
          depthWrite: false,
        })
        // 空几何（无 position）跳过边线生成（EdgesGeometry 需有效顶点）
        const posAttr = child.geometry.getAttribute('position')
        if (posAttr && posAttr.count > 0) {
          const edges = new THREE.EdgesGeometry(child.geometry, 30)
          const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0x1f2937 }))
          line.renderOrder = 2
          child.add(line)
          child.userData.workpieceWireLine = line
        }
      } else if (child.userData.workpieceSolidMaterial) {
        child.material = child.userData.workpieceSolidMaterial as THREE.Material
        child.userData.workpieceSolidMaterial = undefined
      }
    })
  }

  /** 等效产形齿轮样式：靛蓝单色（忽略顶点色）/ 干涉热力图（符号距离顶点色）. */
  function applyConjugateGearStyle(): void {
    const group = layerGroups['conjugateGear']
    if (!group) return
    const def = MATERIAL_PRESETS.conjugateGear
    group.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return
      if (conjugateGearInterference) {
        child.material = new THREE.MeshStandardMaterial({
          color: 0xffffff,
          vertexColors: true,
          roughness: def.roughness,
          metalness: def.metalness,
          transparent: def.transparent,
          opacity: def.opacity,
          side: THREE.DoubleSide,
        })
      } else {
        child.material = new THREE.MeshStandardMaterial({
          color: def.color,
          roughness: def.roughness,
          metalness: def.metalness,
          transparent: def.transparent,
          opacity: def.opacity,
          side: THREE.DoubleSide,
        })
      }
    })
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
    // 透明清屏：背景走容器 CSS 环境渐变（.vp-ambient，theme.css）——纯色背景下
    // 液态玻璃面板的折射/透出/模糊全部不可见（blur(纯色)=纯色），渐变是玻璃感的载体
    renderer.setClearColor?.(0x000000, 0)
    container.classList.add('vp-ambient')
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
    scene.background = null // 背景由容器 CSS 渐变承担（.vp-ambient），见 init 注释

    // 相机
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100)
    camera.position.set(4, 2.5, 6)
    camera.lookAt(0, 0.5, 0)
    initialCameraPos = camera.position.clone()
    initialCameraUp = camera.up.clone()

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
    // 用户手动轨道交互时恢复 maxPolarAngle（底视图放行后）
    controls.addEventListener('start', () => restoreMaxPolarAngle())

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
      // ViewCube 视角过渡动画（300ms easeOutCubic）
      // tilt/spin 已在 setStandardView 中立即归零，此处只动画相机位置
      if (viewTransition && camera && controls) {
        const t = Math.min(1, (performance.now() - viewTransition.start) / viewTransition.duration)
        const eased = 1 - Math.pow(1 - t, 3)
        camera.position.lerpVectors(viewTransition.from, viewTransition.to, eased)
        // up 向量 180° 翻转时 lerp 会过零崩溃 → 中点处直接 snap
        if (viewTransition.upFrom.dot(viewTransition.upTo) < -0.9) {
          camera.up.copy(t < 0.5 ? viewTransition.upFrom : viewTransition.upTo)
        } else {
          camera.up.lerpVectors(viewTransition.upFrom, viewTransition.upTo, eased)
        }
        camera.lookAt(controls.target)
        if (t >= 1) {
          camera.position.copy(viewTransition.to)
          camera.up.copy(viewTransition.upTo)
          camera.lookAt(controls.target)
          controls.enabled = true
          controls.update()
          viewTransition = null
          // maxPolarAngle 恢复推迟到下次 setStandardView / resetView / 用户手动轨道
        }
        sceneDirty = true
      }
      if (growingGeometries.size > 0) {
        for (const [geo, target] of Array.from(growingGeometries.entries())) {
          const step = Math.max(1, Math.ceil(target / 90)) // ~90 帧 ≈ 1.5s
          const count = Math.min(target, geo.drawRange.count + step)
          geo.setDrawRange(0, count)
          if (count >= target) growingGeometries.delete(geo)
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
      // 坐标轴旋转指针（示意旋转方向）匀速转动：W 逆时针、T 顺时针
      if (rotationPointers.length > 0) {
        const now = performance.now()
        if (lastPointerTime === 0) lastPointerTime = now
        const dt = (now - lastPointerTime) / 1000
        lastPointerTime = now
        for (const p of rotationPointers) {
          p.group.rotation.z += p.dir * ROTATION_POINTER_OMEGA * dt
        }
        sceneDirty = true
      }
      // 运动仿真动画更新（φ 域乒乓，−span → +span 一个单程 = 1s × speed）
      if (animPlaying && animMAnim > 1) {
        const now = performance.now()
        if (animLastTime === 0) animLastTime = now
        const dt = (now - animLastTime) / 1000
        animLastTime = now
        animPhiDeg += animDirection * animSpeed * (2 * animSpanDeg) * dt
        if (animPhiDeg >= animSpanDeg) {
          animPhiDeg = animSpanDeg
          animDirection = -1
        } else if (animPhiDeg <= -animSpanDeg) {
          animPhiDeg = -animSpanDeg
          animDirection = 1
        }
        animFrameFloat = animPhiToFframe(animPhiDeg)

        if (spectrumMode && spectrumMesh) {
          // 光谱模式：驱动揭示进度
          setSpectrumReveal(animPhiDeg)
        } else {
          // 动画/截面模式：按 φ 合成/插值更新
          setAnimPhi(animPhiDeg)
        }
        // 通知外部 φ 更新（同步滑条位置）
        animFrameCallback?.(animPhiDeg)
        sceneDirty = true
      }
      // 视角过渡期间跳过 controls.update()，避免 damping 干扰相机位置
      if (!viewTransition) {
        controls?.update()
      }
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

  /** 对线类图层的 geometry 启动逐点生长动画（drawRange 0→N，各段各自生长）. */
  function startGrowAnimation(group: THREE.Group): void {
    group.traverse((child: THREE.Object3D) => {
      if (!(child instanceof THREE.Line || child instanceof THREE.LineSegments)) return
      const geo = child.geometry as THREE.BufferGeometry
      const target = geo.index ? geo.index.count : (geo.attributes.position?.count ?? 0)
      if (target <= 0) return
      geo.setDrawRange(0, 0)
      growingGeometries.set(geo, target)
    })
  }

  /** 把刀具系 T 图层 group 施加安装变换 T→W（中心距 a 沿 X + 绕 X 轴交角 Σ）. */
  function applyInstallTransform(group: THREE.Group): void {
    if (!envelopeInstall) return
    group.position.set(envelopeInstall.a, 0, 0)
    group.rotation.x = envelopeInstall.sigma
  }

  /** 用 Canvas 生成文字 Sprite（始终面向相机、屏幕大小恒定）；无 2D 上下文时退回空占位（测试环境）. */
  function makeTextSprite(text: string, color: string): THREE.Sprite {
    const fontPx = 64
    const pad = 12
    const font = `600 ${fontPx}px "Segoe UI", "Microsoft YaHei", sans-serif`
    const material = new THREE.SpriteMaterial({ transparent: true })
    const sprite = new THREE.Sprite(material)
    const canvas = document.createElement('canvas')

    let ctx: CanvasRenderingContext2D | null = null
    try {
      ctx = canvas.getContext('2d')
    } catch {
      ctx = null
    }
    if (!ctx) {
      sprite.scale.set(AXIS_LABEL_HEIGHT, AXIS_LABEL_HEIGHT, 1)
      return sprite // jsdom 等无 2D 上下文：空标注占位（测试仅断言结构）
    }

    ctx.font = font
    const textW = Math.ceil(ctx.measureText(text).width)
    const w = textW + pad * 2
    const h = Math.ceil(fontPx * 1.35)
    canvas.width = w
    canvas.height = h
    ctx = canvas.getContext('2d')! // 重设宽高会重置上下文状态，重取
    ctx.font = font
    ctx.fillStyle = color
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(text, w / 2, h / 2)

    const tex = new THREE.CanvasTexture(canvas)
    tex.minFilter = THREE.LinearFilter
    tex.generateMipmaps = false
    material.map = tex
    sprite.scale.set(AXIS_LABEL_HEIGHT * (w / h), AXIS_LABEL_HEIGHT, 1)
    return sprite
  }

  /** 构造绕 Z 轴旋转的示意指针（圆弧箭头：弧身 + 末端切向箭头锥体），返回 { group, dir }（dir=扫掠方向）. */
  function makeRotationPointer(prefix: 'W' | 'T'): { group: THREE.Group; dir: 1 | -1 } {
    // W 工件逆时针(+Z)、T 刀具方向随旋向 j_t（+1 右旋逆时针 / −1 左旋顺时针）
    const dir: 1 | -1 = prefix === 'W' ? 1 : (envelopeJt === 1 ? 1 : -1)
    const group = new THREE.Group()
    group.name = `rotation-pointer-${prefix}`
    const radius = ROTATION_POINTER_RADIUS
    const endAngle = dir * ROTATION_POINTER_ARC

    // 弧身：圆环管绕 Z 轴扫掠，dir 决定顺/逆时针（正=逆时针、负=顺时针）；管径与轴身圆柱匹配
    const arc = new THREE.Mesh(
      new THREE.TubeGeometry(new CircularArcCurve(radius, endAngle), 48, 2.0, 8, false),
      new THREE.MeshBasicMaterial({ color: ROTATION_POINTER_COLOR }),
    )
    group.add(arc)

    // 箭头锥体：置于弧末端，指向切向（扫掠方向）
    const tipAngle = endAngle
    const tip = new THREE.Vector3(radius * Math.cos(tipAngle), radius * Math.sin(tipAngle), 0)
    const tangent = new THREE.Vector3(-Math.sin(tipAngle), Math.cos(tipAngle), 0).multiplyScalar(dir)
    const cone = new THREE.Mesh(
      new THREE.ConeGeometry(3.2, 8, 12),
      new THREE.MeshBasicMaterial({ color: ROTATION_POINTER_COLOR }),
    )
    cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), tangent)
    cone.position.copy(tip).addScaledVector(tangent, 2)
    group.add(cone)

    return { group, dir }
  }

  /** 单套坐标轴（X 红 / Y 绿 / Z 蓝，长 length [mm]）+ X/Y/Z 文字标注 + Z 轴旋转指针；返回 group. */
  function makeAxisTriad(length: number, prefix: 'W' | 'T'): THREE.Group {
    const g = new THREE.Group()
    const defs = [
      { v: new THREE.Vector3(1, 0, 0), color: 0xff4444, label: 'X' },
      { v: new THREE.Vector3(0, 1, 0), color: 0x44cc44, label: 'Y' },
      { v: new THREE.Vector3(0, 0, 1), color: 0x4488ff, label: 'Z' },
    ]
    for (const d of defs) {
      // 轴身用圆柱而非 Line（LineBasicMaterial.linewidth 在 Windows/ANGLE 上恒为 1px 无法加粗；
      // 圆柱 + 标准材质受光照着色，加粗后更有质感）。透明度为 0：完全不透明。
      const mat = new THREE.MeshStandardMaterial({
        color: d.color,
        roughness: 0.35,
        metalness: 0.1,
        transparent: false,
        opacity: 1.0,
      })
      const shaftLen = length - AXIS_CONE_HEIGHT // 轴身让出箭头长度，圆锥接在末端
      const shaft = new THREE.Mesh(
        new THREE.CylinderGeometry(AXIS_SHAFT_RADIUS, AXIS_SHAFT_RADIUS, shaftLen, 12),
        mat,
      )
      shaft.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.v)
      shaft.position.copy(d.v).multiplyScalar(shaftLen / 2)
      g.add(shaft)

      // 轴端圆锥箭头（指向轴正方向，尖点恰落在 length 处）
      const cone = new THREE.Mesh(new THREE.ConeGeometry(AXIS_CONE_RADIUS, AXIS_CONE_HEIGHT, 12), mat)
      cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.v)
      cone.position.copy(d.v).multiplyScalar(length - AXIS_CONE_HEIGHT / 2)
      g.add(cone)

      // 轴末端文字标注（跟轴同色，略超出轴尖）
      const sprite = makeTextSprite(`${d.label}_${prefix}`, `#${d.color.toString(16).padStart(6, '0')}`)
      sprite.name = `axis-label-${d.label}_${prefix}`
      sprite.position.copy(d.v.clone().multiplyScalar(length + AXIS_LABEL_OFFSET))
      g.add(sprite)
    }

    // Z 轴尖端旋转指针（示意旋转方向，绕 Z 连续转）
    const pointer = makeRotationPointer(prefix)
    pointer.group.position.set(0, 0, length)
    g.add(pointer.group)
    rotationPointers.push(pointer)
    return g
  }

  /** 画 W（原点）与 T（偏移 a、倾斜 Σ）两套坐标轴（长度随工件尺寸自适应）. */
  function drawCoordinateAxes(): void {
    if (axesGroup) {
      worldGroup?.remove(axesGroup)
      disposeGroup(axesGroup)
      axesGroup = null
    }
    clearRotationPointers()
    if (!worldGroup || !envelopeInstall) return
    // 齿轮大小自适应：目标轴长 = 工件包围球半径（夹上下限），三轴组整体缩放（线/标注/旋转指针同比例）
    const k = axisScaleFactor()
    axesGroup = new THREE.Group()
    axesGroup.name = 'coordinate-axes'
    const wTriad = makeAxisTriad(AXIS_LENGTH, 'W') // W 轴（工件，原点）
    wTriad.scale.setScalar(k)
    axesGroup.add(wTriad)
    const tGroup = new THREE.Group()
    tGroup.position.set(envelopeInstall.a, 0, 0)
    tGroup.rotation.x = envelopeInstall.sigma
    const tTriad = makeAxisTriad(AXIS_LENGTH * 0.85, 'T') // T 轴（刀具，稍短）
    tTriad.scale.setScalar(k)
    tGroup.add(tTriad)
    axesGroup.add(tGroup)
    worldGroup.add(axesGroup)
    requestRender()
  }

  /** 坐标轴缩放因子：目标轴长取工件层包围球半径 [mm]（夹上下限），未挂载工件时退回 1. */
  function axisScaleFactor(): number {
    const wp = layerGroups['workpiece']
    if (!wp || !worldGroup) return 1
    // 在 worldGroup 本地系（mm、Z-up）取包围盒：外层 tilt(45°)/spin/scale 会把场景空间
    // 轴对齐包围盒膨胀，且 Box3.setFromObject 不刷新父级矩阵（matrixWorld 可能过期），均需排除
    worldGroup.updateWorldMatrix(true, true)
    const invWorld = worldGroup.matrixWorld.clone().invert()
    const box = new THREE.Box3()
    wp.traverse((child) => {
      const mesh = child as THREE.Mesh
      if (!mesh.isMesh) return
      const geo = mesh.geometry
      if (!geo.attributes.position || geo.attributes.position.count === 0) return
      geo.computeBoundingBox()
      if (!geo.boundingBox) return
      const local = new THREE.Matrix4().multiplyMatrices(invWorld, mesh.matrixWorld)
      box.union(geo.boundingBox.clone().applyMatrix4(local))
    })
    if (box.isEmpty()) return 1
    const radius = box.getBoundingSphere(new THREE.Sphere()).radius
    const len = THREE.MathUtils.clamp(radius * AXIS_SIZE_RATIO, AXIS_MIN_LENGTH, AXIS_MAX_LENGTH)
    return len / AXIS_LENGTH
  }

  /** 设置安装参数并（重）画坐标轴 + 对已挂载的刀具系图层施加变换. */
  function setEnvelopeInstall(a: number, sigmaDeg: number, j_t: number = -1): void {
    envelopeInstall = { a, sigma: (sigmaDeg * Math.PI) / 180 }
    envelopeJt = j_t
    // 注意：本列表仅收刀具系 T 图层；toothFlank（内齿轮齿面）为 W 系，勿加入（免 T→W 变换）
    for (const id of ['rake', 'edge', 'flank', 'singleTooth', 'toolRing', 'toolBody', 'conjugate', 'conjugateGear', 'interference'] as LayerId[]) {
      const g = layerGroups[id]
      if (g) applyInstallTransform(g)
    }
    drawCoordinateAxes()
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
    // 刀具系 T 图层（除 workpiece/toothFlank 外的包络图层）施加安装变换 T→W（中心距 a + 轴交角 Σ）；
    // toothFlank（内齿轮齿面）本身就在 W 系（工件齿面网格），免变换——否则整层平移/翻转错位
    if (id !== 'workpiece' && id !== 'toothFlank') {
      applyInstallTransform(group)
    }
    layerGroups[id] = group
    layerMaterials.set(id, mats)
    requestRender()
    applyRenderModeInternal(renderMode.value)
    if (visual.kind === 'line') {
      startGrowAnimation(group)
    }
    // 等效产形齿轮：默认单色（覆盖 createLayerMaterial 的顶点色自动检测），「干涉」切换时改顶点色
    if (id === 'conjugateGear') {
      applyConjugateGearStyle()
    }
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
    if (id === 'sweptCloud') { clearAnimMesh(); return } // 扫掠点云走动画清理链（内部引用一并释放）
    removeLayerGroup(id)
    requestRender()
  }

  function clearLayers(): void {
    // 扫掠点云（运动仿真动画）一并清理：其 group 登记在 layerGroups，但内部引用由 clearAnimMesh 释放
    if (animGroup || pitchCirclesGroup) clearAnimMesh()
    for (const id of Object.keys(layerGroups) as LayerId[]) {
      if (id === 'workpiece') continue
      removeLayerGroup(id)
    }
    // 清空非工件层时同步清坐标轴 + 安装参数
    if (axesGroup) {
      worldGroup?.remove(axesGroup)
      disposeGroup(axesGroup)
      axesGroup = null
    }
    clearRotationPointers()
    envelopeInstall = null
    requestRender()
  }

  function setLayerVisible(id: LayerId, visible: boolean): void {
    const group = layerGroups[id]
    if (group) group.visible = visible
    requestRender()
  }

  function setLayerOpacity(id: LayerId, opacity: number): void {
    // 扫掠点云：透明度是「因子」语义（与光谱逐帧揭示 opacity 相乘），不直接覆写
    if (id === 'sweptCloud') {
      sweptCloudOpacityFactor = opacity
      if (spectrumMode && spectrumMesh) {
        // 以当前揭示位置重刷一遍 opacity（复用现有揭示逻辑）
        setSpectrumReveal(animPhiDeg)
      } else if (animMesh || fullGearMesh || sectionAnimLine || sectionAnimGear) {
        const apply = (mesh: THREE.Mesh | null): void => {
          if (!mesh) return
          const mat = mesh.material as THREE.MeshStandardMaterial
          mat.opacity = opacity
        }
        apply(animMesh)
        apply(fullGearMesh)
        // 截面动画线同步因子
        for (const line of [sectionAnimLine, sectionAnimGear]) {
          if (line) (line.material as THREE.LineBasicMaterial).opacity = opacity
        }
      }
      requestRender()
      return
    }
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
      } else if (child instanceof THREE.Sprite) {
        const mat = child.material as THREE.SpriteMaterial
        if (mat instanceof THREE.SpriteMaterial) {
          if (mat.map instanceof THREE.Texture) mat.map.dispose()
          mat.dispose()
        }
      }
    })
  }

  function dispose(): void {
    savedMaxPolarAngle = null
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
    growingGeometries.clear()
    axesGroup = null
    clearRotationPointers()
    envelopeInstall = null
    workpieceViewMode = 'solid'
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

  // ── 运动仿真：动画网格管理 ──────────────────────────────────────────

  /** 创建分度圆环（工件 r_pw 在 W 原点，刀具 r_pt 在 T 原点）. */
  function drawPitchCircles(rpw: number, rpt: number): void {
    if (!worldGroup || !envelopeInstall) return
    if (pitchCirclesGroup) {
      worldGroup.remove(pitchCirclesGroup)
      disposeGroup(pitchCirclesGroup)
      pitchCirclesGroup = null
    }
    pitchCirclesGroup = new THREE.Group()
    pitchCirclesGroup.name = 'pitch-circles'
    const hw = rpw * 0.005 // 视觉半宽 ≈ 0.5% r_pw
    const circleMat = new THREE.MeshBasicMaterial({
      color: 0xffaa00,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.6,
      depthWrite: false,
    })
    // 工件节圆（W 系原点）
    const wpGeo = new THREE.RingGeometry(rpw - hw, rpw + hw, 128)
    const wpMesh = new THREE.Mesh(wpGeo, circleMat)
    wpMesh.name = 'pitch-circle-workpiece'
    pitchCirclesGroup.add(wpMesh)
    // 刀具节圆（T 系原点，经安装变换放置）
    const tGeo = new THREE.RingGeometry(rpt - hw, rpt + hw, 128)
    const tMesh = new THREE.Mesh(tGeo, circleMat.clone())
    tMesh.name = 'pitch-circle-tool'
    const tSub = new THREE.Group()
    tSub.position.set(envelopeInstall.a, 0, 0)
    tSub.rotation.x = envelopeInstall.sigma
    tSub.add(tMesh)
    pitchCirclesGroup.add(tSub)
    worldGroup.add(pitchCirclesGroup)
  }

  /** K-0.5 链矩阵 M(φ) = Rot_z(−φ_t)·Rot_x(−Σ)·Tran_x(−a)·Rot_z(φ_t/ω)（与后端 workpiece_to_tool_chain 默认参数一致，W 系点 → T 系）. */
  function animChainMatrix(phiDeg: number): THREE.Matrix4 {
    const c = animChain!
    const phiT = (phiDeg * Math.PI) / 180
    const phiW = phiT / c.omega
    const m = new THREE.Matrix4()
    m.makeRotationZ(-phiT)
    m.multiply(new THREE.Matrix4().makeRotationX(-c.sigma))
    m.multiply(new THREE.Matrix4().makeTranslation(-c.a, 0, 0))
    m.multiply(new THREE.Matrix4().makeRotationZ(phiW))
    return m
  }

  /** 矩阵逐顶点应用 src → out[outBase..]（xyz 交错；column-major elements 手工展开）. */
  function applyMatrixToPositions(m: THREE.Matrix4, src: Float32Array, out: Float32Array, outBase: number = 0): void {
    const e = m.elements
    for (let i = 0; i < src.length; i += 3) {
      const x = src[i], y = src[i + 1], z = src[i + 2]
      out[outBase + i] = e[0] * x + e[4] * y + e[8] * z + e[12]
      out[outBase + i + 1] = e[1] * x + e[5] * y + e[9] * z + e[13]
      out[outBase + i + 2] = e[2] * x + e[6] * y + e[10] * z + e[14]
    }
  }

  /** 帧网格 φ → 连续帧号（回退插值模式映射）. */
  function animPhiToFframe(phiDeg: number): number {
    return animPhiStep !== 0 ? (phiDeg - animPhi0) / animPhiStep : 0
  }

  /** φ 夹取：合成模式限 ±span；回退模式夹到帧网格范围. */
  function clampPhi(phiDeg: number): number {
    if (animSynthOk) return Math.max(-animSpanDeg, Math.min(animSpanDeg, phiDeg))
    const lo = animPhi0
    const hi = animPhiStep * (animMAnim - 1) + animPhi0
    return Math.max(Math.min(lo, hi), Math.min(Math.max(lo, hi), phiDeg))
  }

  /** 取 φ_t [deg] 处单齿顶点位置写入 out（合成 = 链矩阵实时变换；回退 = 帧间插值）. */
  function animPositionsAt(phiDeg: number, out: Float32Array): void {
    if (animSynthOk && animChain) {
      applyMatrixToPositions(animChainMatrix(phiDeg), animBasePos, out)
      return
    }
    const f = animPhiToFframe(phiDeg)
    const idx = Math.max(0, Math.min(Math.floor(f), animMAnim - 1))
    const nxt = Math.min(idx + 1, animMAnim - 1)
    const frac = Math.max(0, f - idx)
    const cur = animFramePositions[idx]
    const next = animFramePositions[nxt]
    if (frac < 1e-6) {
      out.set(cur)
    } else {
      for (let i = 0; i < out.length; i++) out[i] = cur[i] + frac * (next[i] - cur[i])
    }
  }

  /** 加载动画数据：创建齿面网格 + 分度圆. */
  function loadAnimMesh(
    animData: { frames: Array<{ phi_t_deg: number; positions: number[] }>; indices: number[]; mesh_indices: number[]; n_vertices: number; theta_range_deg: number; omega_ratio?: number; n_profile?: number; layer_zs?: number[] },
    pitchRadii: { rpw: number; rpt: number; z_w?: number },
    onFrameUpdate?: (phiDeg: number) => void,
  ): void {
    clearAnimMesh()
    animFrameCallback = onFrameUpdate ?? null
    if (!worldGroup || !envelopeInstall) { console.warn('[loadAnimMesh] 无 worldGroup 或 envelopeInstall'); return }
    animMAnim = animData.frames.length
    if (animMAnim === 0) { console.warn('[loadAnimMesh] 0 帧'); return }
    animZW = pitchRadii.z_w ?? 0

    // 动画位置保持 T 系（后端原始坐标），不额外变换。
    // animGroup 会施加安装变换，使 T 系几何正确放置到场景中。
    animFramePositions = animData.frames.map(f => new Float32Array(f.positions))
    animMeshIndices = new Uint32Array(animData.mesh_indices)
    // 截面切片元数据（旧后端缺省 → n_profile=0，前端不可切截面）
    animVertexOrig = new Uint32Array(animData.indices)
    animNProfile = animData.n_profile ?? 0
    animLayerZs = animData.layer_zs ? [...animData.layer_zs] : []

    // φ 域合成初始化：omega_ratio 提供时由 frames[0] 反解 W 系基准点 P_W = M(φ0)^{-1}·frame0，
    // 再用 frames[1] 自校验（合成 vs 后端帧，链矩阵若与后端不符此处必超差）→ 失败回退帧插值
    animPhi0 = animData.frames[0].phi_t_deg
    animPhiStep = animMAnim > 1
      ? (animData.frames[animMAnim - 1].phi_t_deg - animPhi0) / (animMAnim - 1)
      : 0
    animSynthOk = false
    animChain = null
    if (animData.omega_ratio && animData.omega_ratio > 0 && envelopeInstall && animMAnim >= 2) {
      animChain = { a: envelopeInstall.a, sigma: envelopeInstall.sigma, omega: animData.omega_ratio }
      const f0 = animFramePositions[0]
      const inv = animChainMatrix(animPhi0).invert()
      animBasePos = new Float32Array(f0.length)
      applyMatrixToPositions(inv, f0, animBasePos)
      const check = new Float32Array(f0.length)
      applyMatrixToPositions(animChainMatrix(animData.frames[1].phi_t_deg), animBasePos, check)
      const ref = animFramePositions[1]
      let maxd = 0
      for (let i = 0; i < check.length; i++) {
        const d = Math.abs(check[i] - ref[i])
        if (d > maxd) maxd = d
      }
      animSynthOk = maxd < 1e-3 // mm（后端帧值 1e-6 圆整，正常应 ≈1e-5 内）
      console.log('[loadAnimMesh] φ 合成自校验 maxΔ =', maxd.toFixed(6), 'mm →', animSynthOk ? '启用 ±360°' : '回退帧插值')
    }
    // 半程：合成 ±360°；回退 = 帧实际铺设范围（≠ theta_range_deg 元数据——那是接触求解域）
    animSpanDeg = animSynthOk
      ? ANIM_SPAN_DEG
      : Math.max(1, Math.abs(animPhiStep * (animMAnim - 1)) / 2)
    animScratch = new Float32Array(animFramePositions[0].length)

    // 创建 BufferGeometry
    animGeometry = new THREE.BufferGeometry()
    animGeometry.setAttribute('position', new THREE.BufferAttribute(animFramePositions[0].slice(), 3))
    animGeometry.setIndex(new THREE.BufferAttribute(animMeshIndices, 1))
    // 光谱顶点色（蓝→红，按帧索引）
    const nVerts = animFramePositions[0].length / 3
    const colors = new Float32Array(nVerts * 3)
    setFrameColors(colors, animPhi0) // 初始色（随后 setAnimPhi 刷到起点 φ）
    animGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    animGeometry.computeVertexNormals()

    const mat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      metalness: 0.3,
      roughness: 0.5,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
      depthTest: false,  // 动画网格始终可见，不被产形面深度缓冲遮挡
    })
    animMesh = new THREE.Mesh(animGeometry, mat)
    animMesh.name = 'anim-tooth-surface'
    animMesh.frustumCulled = false // 防止视锥剔除误杀

    animGroup = new THREE.Group()
    animGroup.name = 'anim-group'
    animGroup.position.set(envelopeInstall.a, 0, 0)
    animGroup.rotation.x = envelopeInstall.sigma
    animGroup.add(animMesh)
    worldGroup.add(animGroup)
    // 注册为「扫掠点云」图层（图层面板眼睛/聚焦/透明度对该层生效；不 dispose，clearAnimMesh 统一清理）
    delete layerGroups['sweptCloud']
    layerGroups['sweptCloud'] = animGroup

    // 分度圆
    drawPitchCircles(pitchRadii.rpw, pitchRadii.rpt)

    // 重置播放状态（φ 起点 = −span，与滑条左端一致）
    animFrameFloat = 0
    animPhiDeg = -animSpanDeg
    animDirection = 1
    animPlaying = false
    animLastTime = 0
    // 刷到起点 φ（合成模式覆盖初始 frame0 占位）
    setAnimPhi(animPhiDeg)

    // 诊断日志
    const posAttr = animGeometry.getAttribute('position') as THREE.BufferAttribute
    const bbox = animGeometry.boundingBox ?? (animGeometry.computeBoundingBox(), animGeometry.boundingBox!)
    console.log('[loadAnimMesh]', animMAnim, '帧,', posAttr.count, '顶点,', animMeshIndices.length / 3, '三角形')
    console.log('[loadAnimMesh] bbox:', JSON.stringify(bbox.min), '→', JSON.stringify(bbox.max))
    console.log('[loadAnimMesh] install a=', envelopeInstall.a, 'sigma=', envelopeInstall.sigma)
    console.log('[loadAnimMesh] worldGroup children:', worldGroup.children.length)

    requestRender()
  }

  /** 更新动画到指定 φ_t [deg]（合成模式任意角；回退模式夹到帧网格后插值）. */
  function setAnimPhi(phiDeg: number): void {
    if (!animGeometry || !animFramePositions.length) {
      console.warn('[setAnimPhi] 无 animGeometry 或无帧数据')
      return
    }
    const phi = clampPhi(phiDeg)
    animPhiDeg = phi
    animFrameFloat = animPhiToFframe(phi) // 回退模式同步内部帧计数
    // 截面模式：更新截面线（光谱色 + 合成 positions），面网格保持不动
    if (sectionIz !== null && sectionGroup) {
      updateSectionPositions(phi)
      requestRender()
      return
    }
    const posAttr = animGeometry.getAttribute('position') as THREE.BufferAttribute
    animPositionsAt(phi, posAttr.array as Float32Array)
    posAttr.needsUpdate = true
    // 光谱色更新（φ 归一化跨整个滑条范围）
    const colAttr = animGeometry.getAttribute('color') as THREE.BufferAttribute
    setFrameColors(colAttr.array as Float32Array, phi)
    colAttr.needsUpdate = true
    // 全齿同步更新
    if (fullGearGeometry && fullGearMesh?.visible) {
      const fgAttr = fullGearGeometry.getAttribute('position') as THREE.BufferAttribute
      fillFullGearPositions(fgAttr.array as Float32Array, phi)
      fgAttr.needsUpdate = true
      const fgCol = fullGearGeometry.getAttribute('color') as THREE.BufferAttribute
      if (fgCol) {
        fillFullGearColors(fgCol.array as Float32Array, phi)
        fgCol.needsUpdate = true
      }
    }
    requestRender()
  }

  /**
   * φ_t 光谱色：滑条范围 [−span, +span] → HSL (蓝240°→红0°，s=100%，l=35%，加深版).
   */
  function colorAtPhi(phiDeg: number): [number, number, number] {
    const t = Math.max(0, Math.min(1, (phiDeg + animSpanDeg) / (2 * animSpanDeg)))
    const hue = (1 - t) * 240 // −span=蓝 → +span=红
    const h = hue / 360
    // HSL → RGB（s=1, l=0.35 加深）
    const c = 0.7 // chroma = 2*l*s = 2*0.35*1
    const x = c * (1 - Math.abs((h * 6) % 2 - 1))
    let r = 0, g = 0, b = 0
    const m = 0.35 - c / 2 // lightness offset
    const sector = Math.floor(h * 6) % 6
    if (sector === 0) { r = c + m; g = x + m; b = m }
    else if (sector === 1) { r = x + m; g = c + m; b = m }
    else if (sector === 2) { r = m; g = c + m; b = x + m }
    else if (sector === 3) { r = m; g = x + m; b = c + m }
    else if (sector === 4) { r = x + m; g = m; b = c + m }
    else { r = c + m; g = m; b = x + m }
    return [r, g, b]
  }

  /**
   * 光谱色：φ_t [deg] → 每顶点 RGB 写入 Float32Array colors（nVerts*3）.
   */
  function setFrameColors(colors: Float32Array, phiDeg: number): void {
    const [r, g, b] = colorAtPhi(phiDeg)
    for (let i = 0; i < colors.length; i += 3) {
      colors[i] = r; colors[i + 1] = g; colors[i + 2] = b
    }
  }

  /** 设置播放/暂停. */
  function setAnimPlaying(playing: boolean): void {
    animPlaying = playing
    if (playing) animLastTime = 0
  }

  /** 设置播放速度. */
  function setAnimSpeed(speed: number): void {
    animSpeed = speed
  }

  /** 切换单齿/全齿. */
  function setAnimGearMode(mode: 'single' | 'full'): void {
    if (!animGroup || !animMesh || !animGeometry || !envelopeInstall) return

    const changed = animGearMode !== mode
    animGearMode = mode

    // 清理旧全齿 mesh
    if (fullGearMesh && animGroup) {
      animGroup.remove(fullGearMesh)
      fullGearMesh.geometry.dispose()
      ;(fullGearMesh.material as THREE.Material).dispose()
      fullGearMesh = null
      fullGearGeometry = null
      fullGearIndices = null
    }

    if (mode === 'full' && animZW > 1 && animFramePositions.length > 0) {
      const nVerts = animFramePositions[0].length / 3
      const nTriIdx = animMeshIndices ? animMeshIndices.length : 0

      fullGearIndices = new Uint32Array(nTriIdx * animZW)
      for (let t = 0; t < animZW; t++) {
        const offset = t * nVerts
        for (let j = 0; j < nTriIdx; j++) {
          fullGearIndices[t * nTriIdx + j] = animMeshIndices![j] + offset
        }
      }

      fullGearGeometry = new THREE.BufferGeometry()
      const fullPositions = new Float32Array(nVerts * 3 * animZW)
      fillFullGearPositions(fullPositions, animPhiDeg)
      fullGearGeometry.setAttribute('position', new THREE.BufferAttribute(fullPositions, 3))
      fullGearGeometry.setIndex(new THREE.BufferAttribute(fullGearIndices, 1))
      const fullColors = new Float32Array(nVerts * 3 * animZW)
      fillFullGearColors(fullColors, animPhiDeg)
      fullGearGeometry.setAttribute('color', new THREE.BufferAttribute(fullColors, 3))
      fullGearGeometry.computeVertexNormals()

      const mat = new THREE.MeshStandardMaterial({
        vertexColors: true,
        metalness: 0.3,
        roughness: 0.5,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.85,
        depthTest: false,
      })
      fullGearMesh = new THREE.Mesh(fullGearGeometry, mat)
      fullGearMesh.name = 'anim-full-gear'
      fullGearMesh.frustumCulled = false
      animGroup.add(fullGearMesh)
    }

    // 可见性仲裁（面/截面线 × 单齿/全齿 × 光谱开关，单一事实源）
    applyAnimRenderVisibility()

    // 光谱模式下齿轮模式变化 → 重建光谱组（揭示位置按 φ 恢复）
    if (spectrumMode && changed) {
      const prevReveal = spectrumMesh
        ? (() => {
            const visible = spectrumMesh.children.filter(
              c => c instanceof THREE.Mesh && c.visible,
            ) as THREE.Mesh[]
            return visible.length
              ? Math.max(...visible.map(m => (m.userData.phiDeg as number) ?? -animSpanDeg))
              : -animSpanDeg
          })()
        : -animSpanDeg
      clearSpectrumMesh()
      spectrumMesh = buildSpectrumGroup(mode === 'full')
      if (spectrumMesh) animGroup.add(spectrumMesh)
      setSpectrumReveal(prevReveal)
    }

    requestRender()
  }

  /**
   * 填充全齿环 positions：φ 处单齿位置（合成/插值到 animScratch）绕 Z 轴旋转 z_w 份.
   * 在 T 系中做旋转（近似：内齿轮 Σ 小，视觉等价）.
   */
  function fillFullGearPositions(out: Float32Array, phiDeg: number): void {
    animPositionsAt(phiDeg, animScratch)
    fillGearCopies(out, phiDeg)
  }

  /** 旋转 z_w 份写入 out（全齿 positions 公共复制环）.

    合成模式：实例必须绕**工件轴**阵列——先在 W 系对基准点 animBasePos 绕 z 转
    t·齿距，再经 M(φ) 到 T 系（旧实现直接绕 z 转 T 系坐标 = 绕刀具轴阵列，整环
    错位、仅基齿槽落齿轮上，用户报「只有一对齿面落在齿轮上」）。回退模式无解析
    链，保持 T 系绕 z 近似。 */
  function fillGearCopies(out: Float32Array, phiDeg: number = animPhiDeg): void {
    const nVerts = animScratch.length / 3
    const toothAngle = (2 * Math.PI) / animZW
    const m = animSynthOk && animChain ? animChainMatrix(phiDeg) : null
    for (let t = 0; t < animZW; t++) {
      const angle = t * toothAngle
      const cosA = Math.cos(angle)
      const sinA = Math.sin(angle)
      const base = t * nVerts * 3
      if (m) {
        for (let v = 0; v < nVerts; v++) {
          const vi = v * 3
          const x = animBasePos[vi], y = animBasePos[vi + 1], z = animBasePos[vi + 2]
          animScratch[vi] = cosA * x - sinA * y
          animScratch[vi + 1] = sinA * x + cosA * y
          animScratch[vi + 2] = z
        }
        applyMatrixToPositions(m, animScratch, out, base)
      } else {
        for (let v = 0; v < nVerts; v++) {
          const vi = v * 3
          const x = animScratch[vi], y = animScratch[vi + 1], z = animScratch[vi + 2]
          out[base + vi] = cosA * x - sinA * y
          out[base + vi + 1] = sinA * x + cosA * y
          out[base + vi + 2] = z
        }
      }
    }
  }

  /** 填充全齿环 colors：每齿同色（当前 φ 光谱色，HSL l=0.35 与 setFrameColors 一致）. */
  function fillFullGearColors(out: Float32Array, phiDeg: number): void {
    // 与 setFrameColors 同参（s=1, l=0.35 加深版），直接复用其单色写入
    setFrameColors(out, phiDeg)
  }

  // ── 截面切片：沿齿向选廓线平面（线渲染替代面网格）─────────────────

  /** 计算层 iz 的线段顶点对（层内相邻 iu 顶点，跳过未命中缺口）. */
  function computeSectionSegments(iz: number): void {
    sectionSegPairs = []
    const nProf = animNProfile
    const verts: number[] = []
    for (let v = 0; v < animVertexOrig.length; v++) {
      if (Math.floor(animVertexOrig[v] / nProf) === iz) verts.push(v)
    }
    // mesh_verts 升序 → 层内 iu 升序；原始索引差 1 = 相邻 iu
    for (let i = 0; i + 1 < verts.length; i++) {
      if (animVertexOrig[verts[i + 1]] - animVertexOrig[verts[i]] === 1) {
        sectionSegPairs.push(verts[i], verts[i + 1])
      }
    }
  }

  /**
   * φ 处截面线几何：该层廓线折线段（fullGear=true 时绕 T 轴旋转复制 z_w 份合并）.
   * 行为与面模式全齿复制的近似一致（绕 T 系 z 轴阵列）.
   */
  function buildSectionLineGeometry(phiDeg: number, fullGear: boolean): THREE.BufferGeometry {
    animPositionsAt(phiDeg, animScratch)
    const seg = sectionSegPairs
    const nSeg = seg.length / 2
    const copies = fullGear && animZW > 1 ? animZW : 1
    const toothAngle = copies > 1 ? (2 * Math.PI) / copies : 0
    const positions = new Float32Array(nSeg * copies * 2 * 3)
    let w = 0
    // 实例绕工件轴阵列：W 系阵列后 M(φ)（同 fillGearCopies 修法）
    const mI = animSynthOk && animChain ? animChainMatrix(phiDeg) : null
    const srcI = mI ? animBasePos : animScratch
    const eI = mI ? mI.elements : null
    for (let k = 0; k < copies; k++) {
      const c = Math.cos(k * toothAngle)
      const s = Math.sin(k * toothAngle)
      for (let e = 0; e < nSeg; e++) {
        for (let j = 0; j < 2; j++) {
          const v = seg[e * 2 + j]
          const x = srcI[v * 3], y = srcI[v * 3 + 1], z = srcI[v * 3 + 2]
          const rx = c * x - s * y
          const ry = s * x + c * y
          if (eI) {
            positions[w++] = eI[0] * rx + eI[4] * ry + eI[8] * z + eI[12]
            positions[w++] = eI[1] * rx + eI[5] * ry + eI[9] * z + eI[13]
            positions[w++] = eI[2] * rx + eI[6] * ry + eI[10] * z + eI[14]
          } else {
            positions[w++] = rx
            positions[w++] = ry
            positions[w++] = z
          }
        }
      }
    }
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return geo
  }

  /** 构建截面动画线（动画模式：单齿廓线 + 全齿廓线，按 φ 更新 positions）. */
  function buildSectionRenderables(): void {
    if (!animGroup || sectionSegPairs.length === 0) return
    clearSectionRenderables()
    sectionGroup = new THREE.Group()
    sectionGroup.name = 'section-lines'
    const matLine = new THREE.LineBasicMaterial({
      color: new THREE.Color(...colorAtPhi(animPhiDeg)),
      transparent: true,
      opacity: sweptCloudOpacityFactor,
      depthTest: false, // 廓线始终可见（与动画面网格一致）
    })
    sectionAnimLine = new THREE.LineSegments(buildSectionLineGeometry(animPhiDeg, false), matLine)
    sectionAnimLine.name = 'section-anim-line'
    sectionAnimLine.frustumCulled = false
    sectionGroup.add(sectionAnimLine)
    if (animZW > 1) {
      sectionAnimGear = new THREE.LineSegments(buildSectionLineGeometry(animPhiDeg, true), matLine.clone())
      sectionAnimGear.name = 'section-anim-gear'
      sectionAnimGear.frustumCulled = false
      sectionGroup.add(sectionAnimGear)
    }
    animGroup.add(sectionGroup)
  }

  /** 按 φ 更新截面线 positions（合成/插值）+ φ 光谱色. */
  function updateSectionPositions(phiDeg: number): void {
    animPositionsAt(phiDeg, animScratch)
    const seg = sectionSegPairs
    const nSeg = seg.length / 2
    const [cr, cg, cb] = colorAtPhi(phiDeg)
    for (const line of [sectionAnimLine, sectionAnimGear]) {
      if (!line) continue
      ;(line.material as THREE.LineBasicMaterial).color.setRGB(cr, cg, cb)
      const attr = line.geometry.getAttribute('position') as THREE.BufferAttribute
      const arr = attr.array as Float32Array
      const copies = arr.length / (nSeg * 2 * 3)
      const toothAngle = copies > 1 ? (2 * Math.PI) / copies : 0
      // 实例绕工件轴阵列：W 系阵列后 M(φ)（同 fillGearCopies 修法）
      const mU = animSynthOk && animChain ? animChainMatrix(phiDeg) : null
      const srcU = mU ? animBasePos : animScratch
      const eU = mU ? mU.elements : null
      let w = 0
      for (let k = 0; k < copies; k++) {
        const c = Math.cos(k * toothAngle)
        const s = Math.sin(k * toothAngle)
        for (let e = 0; e < nSeg; e++) {
          for (let j = 0; j < 2; j++) {
            const v = seg[e * 2 + j]
            const x = srcU[v * 3], y = srcU[v * 3 + 1], z = srcU[v * 3 + 2]
            const rx = c * x - s * y
            const ry = s * x + c * y
            if (eU) {
              arr[w++] = eU[0] * rx + eU[4] * ry + eU[8] * z + eU[12]
              arr[w++] = eU[1] * rx + eU[5] * ry + eU[9] * z + eU[13]
              arr[w++] = eU[2] * rx + eU[6] * ry + eU[10] * z + eU[14]
            } else {
              arr[w++] = rx
              arr[w++] = ry
              arr[w++] = z
            }
          }
        }
      }
      attr.needsUpdate = true
    }
  }

  /** 清理截面动画线. */
  function clearSectionRenderables(): void {
    if (!sectionGroup) return
    sectionGroup.traverse((child) => {
      if (child instanceof THREE.LineSegments) {
        child.geometry.dispose()
        ;(child.material as THREE.Material).dispose()
      }
    })
    sectionGroup.parent?.remove(sectionGroup)
    sectionGroup = null
    sectionAnimLine = null
    sectionAnimGear = null
  }

  /** 动画渲染对象可见性仲裁（面/截面线 × 单齿/全齿 × 光谱开关）——单一事实源. */
  function applyAnimRenderVisibility(): void {
    const sec = sectionIz !== null
    if (animMesh) animMesh.visible = !sec && !spectrumMode && animGearMode === 'single'
    if (fullGearMesh) fullGearMesh.visible = !sec && !spectrumMode && animGearMode === 'full'
    if (sectionGroup) {
      sectionGroup.visible = sec && !spectrumMode
      if (sectionAnimLine) sectionAnimLine.visible = animGearMode === 'single'
      if (sectionAnimGear) sectionAnimGear.visible = animGearMode === 'full'
    }
  }

  /** 截面切片：沿齿向选廓线平面（iz = 轴向层号，null = 恢复全齿面渲染）. */
  function setAnimSection(iz: number | null): void {
    if (!animGroup) return
    if (iz !== null && (animNProfile <= 0 || animVertexOrig.length === 0)) return
    sectionIz = iz
    if (iz !== null) {
      computeSectionSegments(iz)
      buildSectionRenderables()
    } else {
      clearSectionRenderables()
      sectionSegPairs = []
    }
    applyAnimRenderVisibility()
    // 光谱模式 → 重建（面 ↔ 线两形态，揭示位置保留）
    if (spectrumMode) {
      clearSpectrumMesh()
      spectrumMesh = buildSpectrumGroup(animGearMode === 'full')
      if (spectrumMesh) animGroup.add(spectrumMesh)
      setSpectrumReveal(animPhiDeg)
    } else if (animFramePositions.length) {
      // 动画模式 → 立即刷到当前 φ
      updateSectionPositions(animPhiDeg)
    }
    requestRender()
  }

  /** 清理动画网格. */
  function clearAnimMesh(): void {
    // 注销「扫掠点云」图层登记（几何/材质由下方统一 dispose，不走 removeLayerGroup）
    delete layerGroups['sweptCloud']
    sweptCloudOpacityFactor = 1
    clearSpectrumMesh()
    // 截面切片状态一并复位
    clearSectionRenderables()
    sectionIz = null
    sectionSegPairs = []
    animVertexOrig = new Uint32Array(0)
    animNProfile = 0
    animLayerZs = []
    if (fullGearMesh && animGroup) {
      animGroup.remove(fullGearMesh)
      fullGearMesh.geometry.dispose()
      ;(fullGearMesh.material as THREE.Material).dispose()
      fullGearMesh = null
      fullGearGeometry = null
      fullGearIndices = null
    }
    if (animGroup && worldGroup) {
      worldGroup.remove(animGroup)
      disposeGroup(animGroup)
      animGroup = null
    }
    if (pitchCirclesGroup && worldGroup) {
      worldGroup.remove(pitchCirclesGroup)
      disposeGroup(pitchCirclesGroup)
      pitchCirclesGroup = null
    }
    animGeometry = null
    animMesh = null
    animFramePositions = []
    animMeshIndices = null
    animMAnim = 0
    animPlaying = false
    animFrameFloat = 0
    // φ 域合成状态复位
    animPhiDeg = 0
    animSpanDeg = 40
    animSynthOk = false
    animBasePos = new Float32Array(0)
    animScratch = new Float32Array(0)
    animChain = null
    animPhi0 = 0
    animPhiStep = 0
    animZW = 0
    spectrumMode = false
    animGearMode = 'single'
    animFrameCallback = null
    requestRender()
  }

  // ── 光谱扫掠面模式 ─────────────────────────────────────────────────

  /** 清理光谱扫掠面 mesh 组. */
  function clearSpectrumMesh(): void {
    if (spectrumMesh && animGroup) {
      animGroup.remove(spectrumMesh)
      spectrumMesh.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.geometry.dispose()
          ;(child.material as THREE.Material).dispose()
        }
      })
      spectrumMesh = null
    }
    requestRender()
  }

  /** jet colormap: t∈[0,1] → (r,g,b)，蓝→青→绿→黄→红（加深版）. */
  function jetColor(t: number): [number, number, number] {
    let r: number, g: number, b: number
    if (t < 0.25) {
      r = 0; g = t * 4; b = 1
    } else if (t < 0.5) {
      r = 0; g = 1; b = 1 - (t - 0.25) * 4
    } else if (t < 0.75) {
      r = (t - 0.5) * 4; g = 1; b = 0
    } else {
      r = 1; g = 1 - (t - 0.75) * 4; b = 0
    }
    // 加深：整体乘 0.7
    return [r * 0.7, g * 0.7, b * 0.7]
  }

  /** 全齿/截面光谱最大采样数（降采样上限，控制构建耗时与显存）. */
  const SPECTRUM_MAX_FRAMES = 16

  /**
   * 构建光谱扫掠面（φ 域均匀采样 [−span, +span]）.
   * 单齿：每采样 φ 一个 mesh（与帧数同密度）。
   * 全齿：每采样 φ 一个全齿 mesh（≤16 个）——flatShading 免法向、材质单色免顶点色、
   *       索引跨采样共享，构建与渲染均比旧「单 geometry 全帧合并」轻一个量级。
   * mesh.userData.phiDeg 记录采样 φ（揭示时映射用）。
   */
  function buildSpectrumGroup(fullGear = false): THREE.Group | null {
    if (!animFramePositions.length || !animMeshIndices || animMAnim < 2) return null

    const F = animMAnim
    const span = animSpanDeg
    const sectionMode = sectionIz !== null && sectionSegPairs.length > 0
    const full = fullGear && animZW > 1
    const group = new THREE.Group()
    group.name = 'spectrum-swept-surface'

    // φ 均匀采样序列（含 ±span 端点）；全齿/截面全齿降采样 ≤ SPECTRUM_MAX_FRAMES
    const step = full ? Math.max(1, Math.ceil(F / SPECTRUM_MAX_FRAMES)) : 1
    const phis: number[] = []
    for (let i = 0; i < F; i += step) phis.push(-span + (2 * span * i) / Math.max(1, F - 1))
    if (phis.length === 0 || phis[phis.length - 1] < span - 1e-9) phis.push(span)

    // ── 截面光谱：每采样 φ 一条廓线折线（全齿时 z_w 份合并进单对象） ──
    if (sectionMode) {
      for (const phi of phis) {
        const t = (phi + span) / (2 * span)
        const [cr, cg, cb] = jetColor(t)
        const mat = new THREE.LineBasicMaterial({
          color: new THREE.Color(cr, cg, cb),
          transparent: true,
          opacity: 0,
        })
        const line = new THREE.LineSegments(buildSectionLineGeometry(phi, full), mat)
        line.name = `spectrum-section-${phi.toFixed(1)}`
        line.userData.phiDeg = phi
        line.frustumCulled = false
        line.visible = false
        group.add(line)
      }
      return group
    }

    if (full) {
      // ── 全齿模式：每采样 φ 一个全齿 mesh（≤ SPECTRUM_MAX_FRAMES） ──
      const nVerts = animFramePositions[0].length / 3
      const nTriIdx = animMeshIndices.length

      // 全齿索引模板（z_w 份单齿偏移）——所有采样共享同一 BufferAttribute
      const gearIndices = new Uint32Array(nTriIdx * animZW)
      for (let t = 0; t < animZW; t++) {
        const offset = t * nVerts
        for (let j = 0; j < nTriIdx; j++) {
          gearIndices[t * nTriIdx + j] = animMeshIndices[j] + offset
        }
      }
      const sharedIndex = new THREE.BufferAttribute(gearIndices, 1)

      for (const phi of phis) {
        // 合成/插值 φ 处单齿 → 旋转 z_w 份全齿 positions
        const positions = new Float32Array(nVerts * 3 * animZW)
        animPositionsAt(phi, animScratch)
        fillGearCopies(positions, phi)

        const geo = new THREE.BufferGeometry()
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
        geo.setIndex(sharedIndex)
        // flatShading：着色器内按面法向着色，免 computeVertexNormals（构建主卡点）

        const t = (phi + span) / (2 * span)
        const [cr, cg, cb] = jetColor(t)
        const mat = new THREE.MeshStandardMaterial({
          color: new THREE.Color(cr, cg, cb),
          metalness: 0.3,
          roughness: 0.5,
          flatShading: true,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0,
          depthWrite: false,
        })
        const mesh = new THREE.Mesh(geo, mat)
        mesh.name = `spectrum-gear-phi-${phi.toFixed(1)}`
        mesh.userData.phiDeg = phi
        mesh.frustumCulled = false
        mesh.visible = false
        group.add(mesh)
      }

    } else {
      // ── 单齿模式：每采样 φ 一个 mesh（轻量） ──
      for (const phi of phis) {
        const t = (phi + span) / (2 * span)
        const [cr, cg, cb] = jetColor(t)

        const geo = new THREE.BufferGeometry()
        const positions = new Float32Array(animScratch.length)
        animPositionsAt(phi, positions)
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
        geo.setIndex(new THREE.BufferAttribute(animMeshIndices, 1))
        geo.computeVertexNormals()

        const mat = new THREE.MeshStandardMaterial({
          color: new THREE.Color(cr, cg, cb),
          metalness: 0.3,
          roughness: 0.5,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0,
          depthWrite: false,
        })
        const mesh = new THREE.Mesh(geo, mat)
        mesh.name = `spectrum-phi-${phi.toFixed(1)}`
        mesh.userData.phiDeg = phi
        mesh.frustumCulled = false
        mesh.visible = false
        group.add(mesh)
      }
    }

    return group
  }

  /**
   * 光谱揭示：显示 −span..phiDeg 的采样.
   * 单齿/全齿统一 per-mesh 揭示：按 userData.phiDeg 与当前 φ 比较——
   * 未来采样隐藏（visible=false，不进渲染队列），当前 0.9，过去 0.3；
   * 降采样时 current 映射到 ≤current 的最近采样。
   * opacity 一律乘扫掠点云图层透明度因子（图层面板滑条）。
   */
  function setSpectrumReveal(phiDeg: number): void {
    if (!spectrumMesh) return
    const current = clampPhi(phiDeg)
    // 同步内部 φ 计数器（播放/重置后从正确位置继续）
    animPhiDeg = current
    animFrameFloat = animPhiToFframe(current)
    const factor = sweptCloudOpacityFactor

    // 当前 φ 对应的高亮采样：phiDeg ≤ current 的最大者
    let activeIdx = -1
    const meshes = spectrumMesh.children as THREE.Mesh[]
    for (let i = 0; i < meshes.length; i++) {
      const pd = meshes[i].userData.phiDeg as number
      if (pd <= current + 1e-9) activeIdx = i
    }

    for (let i = 0; i < meshes.length; i++) {
      const mesh = meshes[i]
      const mat = mesh.material as THREE.MeshStandardMaterial
      if (i > activeIdx) {
        // 未来采样：隐藏（免 overdraw）
        mesh.visible = false
      } else {
        mesh.visible = true
        mat.opacity = (i === activeIdx ? 0.9 : 0.3) * factor
      }
    }
    requestRender()
  }

  /** 切换光谱扫掠面模式. */
  function setSpectrumMode(on: boolean): void {
    spectrumMode = on
    if (!animGroup || !animFramePositions.length) return

    if (on) {
      // 暂停动画播放
      animPlaying = false
      // 隐藏逐帧动画渲染对象（面网格/截面线，经仲裁器统一处理）
      // 构建光谱扫掠面（按当前齿轮模式；截面模式下为线形态）
      if (!spectrumMesh) {
        spectrumMesh = buildSpectrumGroup(animGearMode === 'full')
        if (spectrumMesh) animGroup.add(spectrumMesh)
      }
      applyAnimRenderVisibility()
      // 初始揭示：从起点 φ 开始
      setSpectrumReveal(-animSpanDeg)
    } else {
      // 清理光谱 mesh
      clearSpectrumMesh()
      // 恢复逐帧动画渲染对象（面/截面线按当前模式）
      applyAnimRenderVisibility()
    }
    requestRender()
  }

  // ── ViewCube 视角切换 ──────────────────────────────────────────────

  /** 获取模型包围盒中心与相机距离（ViewCube 定位用）. */
  function getViewInfo(): { center: THREE.Vector3; distance: number } {
    if (!camera || !controls) return { center: new THREE.Vector3(), distance: 10 }
    const center = controls.target.clone()
    const distance = camera.position.distanceTo(controls.target)
    return { center, distance }
  }

  /** 标准视图方向表（模型 Z-up 坐标系）.
   *  up = cross(dir, right) 在屏幕上的方向，确保面平行屏幕。
   *  front/back 的 right 都是 +X，但 dir 相反，故 up 也相反。
   */
  const STANDARD_VIEWS: Record<StandardView, { dir: THREE.Vector3; up: THREE.Vector3 }> = {
    top:    { dir: new THREE.Vector3(0, 0, 1),  up: new THREE.Vector3(0, 1, 0) },
    bottom: { dir: new THREE.Vector3(0, 0, -1), up: new THREE.Vector3(0, -1, 0) },
    front:  { dir: new THREE.Vector3(0, -1, 0), up: new THREE.Vector3(0, 0, 1) },
    back:   { dir: new THREE.Vector3(0, 1, 0),  up: new THREE.Vector3(0, 0, -1) },
    right:  { dir: new THREE.Vector3(1, 0, 0),  up: new THREE.Vector3(0, 0, 1) },
    left:   { dir: new THREE.Vector3(-1, 0, 0), up: new THREE.Vector3(0, 0, 1) },
  }

  /**
   * 切换到标准视图（300ms easeOutCubic 过渡）.
   * 只做 Z-up → Y-up 轴转换（-90°X），不补偿 presentation 倾斜/自旋，
   * 确保正交平面视图：前脸平行屏幕、边线水平/垂直。
   */
  function setStandardView(view: StandardView): void {
    if (!camera || !controls) return
    restoreMaxPolarAngle() // 从底视图切换时恢复原始限制
    const { center, distance } = getViewInfo()
    const { dir, up } = STANDARD_VIEWS[view]

    // 模型空间 → 场景空间（仅 Z-up→Y-up 轴转换：worldGroup.rotation.x = -PI/2）
    // model X→scene X, model Y→scene Z, model Z→scene -Y
    const sceneDir = new THREE.Vector3(dir.x, dir.z, -dir.y)
    const sceneUp = new THREE.Vector3(up.x, up.z, -up.y)

    const targetPos = center.clone().add(sceneDir.multiplyScalar(distance))

    // 停止自旋 + 立即归零 tilt/spin（确保相机目标位置对应摆正的模型）
    if (!userInteracted) {
      userInteracted = true
    }
    if (spinGroup) spinGroup.quaternion.identity()
    if (tiltGroup) tiltGroup.quaternion.identity()
    // 强制刷新世界矩阵，确保归零立即生效（否则相机目标位置对应的是旧姿态）
    if (scene) scene.updateMatrixWorld(true)
    controls.enabled = false

    // 底视图 θ=π 超出 maxPolarAngle(126°) → 转场期间临时放行到 π，防止 controls.update() 钳制弹回
    if (savedMaxPolarAngle === null) {
      savedMaxPolarAngle = controls.maxPolarAngle
    }
    controls.maxPolarAngle = Math.PI

    viewTransition = {
      from: camera.position.clone(),
      to: targetPos,
      upFrom: camera.up.clone(),
      upTo: sceneUp,
      start: performance.now(),
      duration: 300,
    }
    requestRender()
  }

  /** 恢复初始视角（Home 按钮用，300ms 过渡）. */
  function resetView(): void {
    if (!camera || !controls || !initialCameraPos || !initialCameraUp) return
    restoreMaxPolarAngle() // 从底视图恢复时还原原始限制
    const { center } = getViewInfo()
    const dist = camera.position.distanceTo(center)
    const dir = initialCameraPos.clone().sub(new THREE.Vector3(0, 0.5, 0)).normalize()
    const targetPos = center.clone().add(dir.multiplyScalar(dist))

    if (!userInteracted) {
      userInteracted = true
    }
    if (spinGroup) spinGroup.quaternion.identity()
    if (tiltGroup) tiltGroup.quaternion.identity()
    if (scene) scene.updateMatrixWorld(true)
    controls.enabled = false

    viewTransition = {
      from: camera.position.clone(),
      to: targetPos,
      upFrom: camera.up.clone(),
      upTo: initialCameraUp.clone(),
      start: performance.now(),
      duration: 300,
    }
    requestRender()
  }

  /** 获取 ViewCube CSS 旋转矩阵（16 值，每帧由 animate 调用更新）. */
  function getViewCubeRotation(): number[] {
    if (!camera || !worldGroup) return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

    // 模型→场景的完整旋转链（worldGroup × tiltGroup × spinGroup）
    const modelQuat = new THREE.Quaternion()
    worldGroup.getWorldQuaternion(modelQuat)

    // CSS 立方体朝向 = inverse(cameraRot) × modelRot
    // 即：从相机视角看，模型的朝向
    const cubeQuat = new THREE.Quaternion()
      .copy(camera.quaternion)
      .invert()
      .multiply(modelQuat)

    const m = new THREE.Matrix4().makeRotationFromQuaternion(cubeQuat)
    return m.elements as unknown as number[]
  }

  return {
    loadGear,
    addLayer,
    setEnvelopeInstall,
    removeLayer,
    clearLayers,
    setLayerVisible,
    setLayerOpacity,
    focusLayer,
    setRenderMode: applyRenderModeInternal,
    setWorkpieceView: (mode: WorkpieceViewMode) => {
      workpieceViewMode = mode
      applyWorkpieceView()
    },
    setConjugateGearInterference: (on: boolean) => {
      conjugateGearInterference = on
      applyConjugateGearStyle()
    },
    setLoggedIn: (v: boolean) => {
      loggedIn = v
    },
    setModelLayout: (layout: { scale?: number; offsetX?: number }) => {
      if (layout.scale !== undefined) targetModelScale = layout.scale
      if (layout.offsetX !== undefined) targetOffsetX = layout.offsetX
    },
    resize,
    dispose,
    loadAnimMesh,
    setAnimPhi,
    setAnimPlaying,
    setAnimSpeed,
    setAnimGearMode,
    setAnimSection,
    setSpectrumMode,
    setSpectrumReveal,
    clearAnimMesh,
    getViewInfo,
    setStandardView,
    resetView,
    getViewCubeRotation,
  }
}
