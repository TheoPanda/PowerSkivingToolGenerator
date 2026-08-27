/**
 * layerPalette.ts — 图层 id 类型 + 配色/材质预设（纯数据源，可单测）
 *
 * 模块②「分阶段叠加可视化」的图层视觉定义单源。材质颜色为 hex 0xRRGGBB；
 * 与 theme.css 的同名色（--brand-blue #0060A0、冰蓝 #E8F0F8、深色 #1f2937）
 * 注释互指、不做运行时联动（ADR-018）。纯数据，不依赖 Three.js。
 */

/** 10 个语义图层 id（工件 + 内齿轮齿面 + 扫掠点云 + 刃形/前刀面/后刀面/单齿/整环 + 产形面 + 等效产形齿轮）. */
export type LayerId = 'workpiece' | 'toothFlank' | 'rake' | 'edge' | 'flank' | 'singleTooth' | 'toolRing' | 'conjugate' | 'conjugateGear' | 'sweptCloud'

/** 几何种类：mesh=三角网格、line=有序折线、points=点云. */
export type LayerKind = 'mesh' | 'line' | 'points'

/** 材质预设名（steel/carbide 复用现有工件/刀具材质；其余为包络层配色）. */
export type MaterialPreset = 'steel' | 'carbide' | 'rake' | 'flank' | 'edge' | 'conjugate' | 'conjugateGear' | 'toolRing' | 'spectrum' | 'toothFlank'

/** 材质预设的 PBR 参数（color 为 hex 0xRRGGBB）. */
export interface MaterialPresetDef {
  color: number
  roughness: number
  metalness: number
  transparent: boolean
  opacity: number
}

/** 材质预设表（与 gearViewport 现有 steel/carbide 材质一致 + 新增包络层配色）. */
export const MATERIAL_PRESETS: Record<MaterialPreset, MaterialPresetDef> = {
  // 工件（对齐现有 steelMaterial 0x9a9aa0）
  steel: { color: 0x9a9aa0, roughness: 0.32, metalness: 0.98, transparent: false, opacity: 1.0 },
  // 单齿模型（对齐现有 carbideMaterial 0x5a5854，硬质合金）
  carbide: { color: 0x5a5854, roughness: 0.28, metalness: 0.97, transparent: false, opacity: 1.0 },
  // 前刀面 — 琥珀橙 #E8963A（暖色，与后刀面明显区分）
  rake: { color: 0xe8963a, roughness: 0.4, metalness: 0.3, transparent: true, opacity: 0.45 },
  // 后刀面 — 翡翠绿 #3AA06A（冷色半透明面，与前刀面明显区分）
  flank: { color: 0x3aa06a, roughness: 0.4, metalness: 0.3, transparent: true, opacity: 0.5 },
  // 刃形 — 珊瑚红 #E05050（高亮折线，非黑；LineBasicMaterial，roughness/metalness 无效仅占位）
  edge: { color: 0xe05050, roughness: 0.5, metalness: 0.0, transparent: false, opacity: 1.0 },
  // 产形面（共轭面）— 青色 #00A8CC（[12] 图3 蓝色产形面）
  conjugate: { color: 0x00a8cc, roughness: 0.4, metalness: 0.3, transparent: true, opacity: 0.5 },
  // 等效产形齿轮 — 靛蓝 #2A6FBF（完整齿轮，与单齿槽产形面青色区分；GLB 带符号距离顶点色，前端「干涉」切换样式）
  conjugateGear: { color: 0x2a6fbf, roughness: 0.38, metalness: 0.35, transparent: true, opacity: 0.45 },
  // 刀具整环（模块③ B 方案）— 钨钢深灰蓝 #4A5568（成品刀全貌，与单齿硬质合金同族更深一档）
  toolRing: { color: 0x4a5568, roughness: 0.3, metalness: 0.96, transparent: false, opacity: 1.0 },
  // 扫掠点云（运动仿真）— jet 光谱起点蓝 #3050C8（加深版 jet(0)）；实际逐帧 jet 色，仅色块/聚焦显示用
  spectrum: { color: 0x3050c8, roughness: 0.5, metalness: 0.3, transparent: true, opacity: 0.85 },
  // 内齿轮齿面 — 洋红紫 #C05AB0（GLB 逐顶点色为主：参与=洋红紫/被修剪=暗灰；preset 色仅兜底与色块显示）
  toothFlank: { color: 0xc05ab0, roughness: 0.4, metalness: 0.3, transparent: false, opacity: 1.0 },
}

/** 每个图层的视觉默认值. */
export interface LayerVisual {
  id: LayerId
  label: string
  kind: LayerKind
  materialPreset: MaterialPreset
  defaultOpacity: number
  doubleSide: boolean
  /** 深度推后防共面 z-fighting（rake 面片/后刀面 ribbon 与实体帽盖/侧面严格共面） */
  polygonOffset?: boolean
  /** 点云图层的点尺寸（默认 0.5 世界单位；sizeAttenuation=false 时为像素） */
  pointSize?: number
  /** 点尺寸是否随距离衰减（默认 true）。toothFlank=false：屏幕空间固定像素点——
   * 世界单位点（0.8mm）远大于采样间距（n=200 廓形 ~0.06mm），重叠方块会连成条带 */
  pointSizeAttenuation?: boolean
}

/**
 * 图层视觉定义表（6 语义图层）.
 * workpiece 默认不透明（1.0）以保持模块① 工件零回归；「参考半透明」可由用户经
 * 图层面板调透明度达成，不在默认值里改变既有视觉。
 */
export const LAYER_VISUALS: Record<LayerId, LayerVisual> = {
  workpiece: { id: 'workpiece', label: '工件齿轮', kind: 'mesh', materialPreset: 'steel', defaultOpacity: 1.0, doubleSide: false },
  // 内齿轮齿面：参与产形面求解的工件齿面网格（W 系，免 T→W 安装变换），离散点 + 法向箭头。
  // 点用屏幕空间 4px 固定尺寸（世界单位点与采样间距不匹配会重叠成条带）
  toothFlank: { id: 'toothFlank', label: '内齿轮齿面', kind: 'points', materialPreset: 'toothFlank', defaultOpacity: 1.0, doubleSide: false, pointSize: 4, pointSizeAttenuation: false },
  rake: { id: 'rake', label: '前刀面', kind: 'mesh', materialPreset: 'rake', defaultOpacity: 0.45, doubleSide: true, polygonOffset: true },
  edge: { id: 'edge', label: '刃形', kind: 'line', materialPreset: 'edge', defaultOpacity: 1.0, doubleSide: false },
  flank: { id: 'flank', label: '后刀面', kind: 'mesh', materialPreset: 'flank', defaultOpacity: 0.5, doubleSide: true, polygonOffset: true },
  singleTooth: { id: 'singleTooth', label: '单齿模型', kind: 'mesh', materialPreset: 'carbide', defaultOpacity: 1.0, doubleSide: false },
  toolRing: { id: 'toolRing', label: '刀具整环', kind: 'mesh', materialPreset: 'toolRing', defaultOpacity: 1.0, doubleSide: false },
  conjugate: { id: 'conjugate', label: '产形面', kind: 'mesh', materialPreset: 'conjugate', defaultOpacity: 0.5, doubleSide: true },
  conjugateGear: { id: 'conjugateGear', label: '等效产形齿轮', kind: 'mesh', materialPreset: 'conjugateGear', defaultOpacity: 0.45, doubleSide: true },
  // 扫掠点云：运动仿真（固定刀具系看工件运动）的离散包络扫掠轨迹，非产形面（2026-08-20 术语厘清）
  sweptCloud: { id: 'sweptCloud', label: '扫掠点云', kind: 'mesh', materialPreset: 'spectrum', defaultOpacity: 0.85, doubleSide: true },
}

/** 全部图层 id（图层面板显示顺序；内齿轮齿面/产形面/等效产形齿轮紧随工件；整环紧随单齿；扫掠点云置于最后）. */
export const LAYER_IDS: LayerId[] = ['workpiece', 'toothFlank', 'conjugate', 'conjugateGear', 'rake', 'edge', 'flank', 'singleTooth', 'toolRing', 'sweptCloud']

/**
 * 刀具整环图层 id 的具名常量：步骤3 预设保留层 / 过期标记对象共用
 * （评审 S3 收口——避免 'toolRing' 字面量散布，单源从类型层下沉到值层）.
 */
export const TOOL_RING_ID: LayerId = 'toolRing'

/** 安装参数（中心距 a + 轴交角 Σ），供前端把刀具系 T 的几何变换到工件系 W + 画坐标轴. */
export interface EnvelopeInstall {
  a: number        // 中心距 [mm]
  sigma_deg: number  // 轴交角 [°]
}

/** window 事件 gear:layer-ready 的 detail 契约（派发方与监听方共享）. */
export interface LayerReadyDetail {
  id: LayerId
  glbBase64: string
}
