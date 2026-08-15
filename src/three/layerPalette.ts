/**
 * layerPalette.ts — 图层 id 类型 + 配色/材质预设（纯数据源，可单测）
 *
 * 模块②「分阶段叠加可视化」的图层视觉定义单源。材质颜色为 hex 0xRRGGBB；
 * 与 theme.css 的同名色（--brand-blue #0060A0、冰蓝 #E8F0F8、深色 #1f2937）
 * 注释互指、不做运行时联动（ADR-018）。纯数据，不依赖 Three.js。
 */

/** 8 个语义图层 id（工件 + 刃形/前刀面/后刀面/单齿 + 产形面 + 等效产形齿轮 + 干涉热力图）. */
export type LayerId = 'workpiece' | 'rake' | 'edge' | 'flank' | 'singleTooth' | 'conjugate' | 'conjugateGear' | 'interference'

/** 几何种类：mesh=三角网格、line=有序折线、points=点云. */
export type LayerKind = 'mesh' | 'line' | 'points'

/** 材质预设名（steel/carbide 复用现有工件/刀具材质；其余为包络层配色）. */
export type MaterialPreset = 'steel' | 'carbide' | 'rake' | 'flank' | 'edge' | 'conjugate' | 'conjugateGear' | 'interference'

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
  // 等效产形齿轮 — 靛蓝 #2A6FBF（完整齿轮，与单齿槽产形面青色区分）
  conjugateGear: { color: 0x2a6fbf, roughness: 0.38, metalness: 0.35, transparent: true, opacity: 0.45 },
  // 干涉热力图 — 顶点色（红白蓝发散），color 占位 0xffffff（gearViewport 顶点色优先）
  interference: { color: 0xffffff, roughness: 0.4, metalness: 0.3, transparent: true, opacity: 0.9 },
}

/** 每个图层的视觉默认值. */
export interface LayerVisual {
  id: LayerId
  label: string
  kind: LayerKind
  materialPreset: MaterialPreset
  defaultOpacity: number
  doubleSide: boolean
}

/**
 * 图层视觉定义表（6 语义图层）.
 * workpiece 默认不透明（1.0）以保持模块① 工件零回归；「参考半透明」可由用户经
 * 图层面板调透明度达成，不在默认值里改变既有视觉。
 */
export const LAYER_VISUALS: Record<LayerId, LayerVisual> = {
  workpiece: { id: 'workpiece', label: '工件齿轮', kind: 'mesh', materialPreset: 'steel', defaultOpacity: 1.0, doubleSide: false },
  rake: { id: 'rake', label: '前刀面', kind: 'mesh', materialPreset: 'rake', defaultOpacity: 0.45, doubleSide: true },
  edge: { id: 'edge', label: '刃形', kind: 'line', materialPreset: 'edge', defaultOpacity: 1.0, doubleSide: false },
  flank: { id: 'flank', label: '后刀面', kind: 'mesh', materialPreset: 'flank', defaultOpacity: 0.5, doubleSide: true },
  singleTooth: { id: 'singleTooth', label: '单齿模型', kind: 'mesh', materialPreset: 'carbide', defaultOpacity: 1.0, doubleSide: false },
  conjugate: { id: 'conjugate', label: '产形面', kind: 'mesh', materialPreset: 'conjugate', defaultOpacity: 0.5, doubleSide: true },
  conjugateGear: { id: 'conjugateGear', label: '等效产形齿轮', kind: 'mesh', materialPreset: 'conjugateGear', defaultOpacity: 0.45, doubleSide: true },
  interference: { id: 'interference', label: '干涉热力图', kind: 'mesh', materialPreset: 'interference', defaultOpacity: 0.9, doubleSide: true },
}

/** 全部图层 id（图层面板显示顺序；产形面/等效产形齿轮/干涉热力图紧随工件、置于前刀面之前）. */
export const LAYER_IDS: LayerId[] = ['workpiece', 'conjugate', 'conjugateGear', 'interference', 'rake', 'edge', 'flank', 'singleTooth']

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
