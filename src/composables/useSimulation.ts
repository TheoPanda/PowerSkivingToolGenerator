/**
 * 反向包络运动仿真状态管理.
 *
 * 模块级单例（同 useWorkpieceState 模式）：φ_t 角度域为主状态（滑条 ±spanDeg、
 * 1° 步进；合成模式 span=360°），管理播放/暂停、乒乓方向、速度、单齿/全齿切换。
 * SimulationPanel 和 gearViewport 共享此状态；viewport 是播放主时钟（回调 setPhi 同步）。
 */

import { reactive, computed } from 'vue'
import type { AnimData } from '../api'

// ── 状态 ──────────────────────────────────────────────────────────────

export interface SimulationState {
  /** SimulationPanel 是否打开. */
  open: boolean
  /** 自动播放中. */
  playing: boolean
  /** 播放速度倍率. */
  speed: number
  /** 当前 φ_t [deg]（连续值；滑条/播放/viewport 回调共同驱动）. */
  phiDeg: number
  /** 滑条/播放半程 [deg]：后端带 omega_ratio（链合成可用）= 360；回退 = 帧实际范围. */
  spanDeg: number
  /** 乒乓方向：+1 正向，-1 反向. */
  direction: 1 | -1
  /** 单齿/全齿模式. */
  gearMode: 'single' | 'full'
  /** 光谱扫掠面模式（true=采样叠加 + jet 光谱色，false=逐帧动画播放）. */
  spectrumMode: boolean
  /** 截面切片模式（true=只渲染指定轴向层的廓线扫掠，false=全齿面）. */
  sectionMode: boolean
  /** 截面层号（0..n_z−1；animData.layer_zs 下标）. */
  sectionIz: number
  /** 动画数据（从后端获取）. */
  animData: AnimData | null
}

const state = reactive<SimulationState>({
  open: false,
  playing: false,
  speed: 1,
  phiDeg: -360,
  spanDeg: 360,
  direction: 1,
  gearMode: 'single',
  spectrumMode: false,
  sectionMode: false,
  sectionIz: 0,
  animData: null,
})

export const simState: SimulationState = state

// ── 计算属性 ──────────────────────────────────────────────────────────

/** 当前 φ_t [deg]（滑条绑定/数值显示）. */
export const currentPhiTDeg = computed(() => state.phiDeg)

/** 滑条范围 [deg]（±spanDeg，step=1 → 1° 分辨率）. */
export const angleRange = computed(() => ({
  min: -state.spanDeg,
  max: state.spanDeg,
}))

// ── 操作 ──────────────────────────────────────────────────────────────

/** 打开仿真面板并加载动画数据（span 由 omega_ratio 推定：合成 ±360° / 回退帧范围）. */
export function openSimulation(animData: AnimData): void {
  state.animData = animData
  const fr = animData.frames
  const frameSpan = fr.length >= 2
    ? Math.abs(fr[fr.length - 1].phi_t_deg - fr[0].phi_t_deg) / 2
    : animData.theta_range_deg
  state.spanDeg = animData.omega_ratio != null ? 360 : Math.max(1, frameSpan)
  state.phiDeg = -state.spanDeg
  state.direction = 1
  state.playing = false
  state.sectionMode = false
  state.sectionIz = 0
  state.open = true
}

/** 关闭仿真面板. */
export function closeSimulation(): void {
  state.open = false
  state.playing = false
  state.spectrumMode = false
  state.sectionMode = false
  state.sectionIz = 0
  state.animData = null
  state.phiDeg = -360
  state.spanDeg = 360
}

/** 切换播放/暂停. */
export function togglePlay(): void {
  state.playing = !state.playing
}

/** 重置到起点 φ（−span，滑条左端）. */
export function resetPhi(): void {
  state.phiDeg = -state.spanDeg
  state.direction = 1
  state.playing = false
}

/** 设定当前 φ_t [deg]（滑条/viewport 回调；夹到 ±span）. */
export function setPhi(phiDeg: number): void {
  state.phiDeg = Math.max(-state.spanDeg, Math.min(state.spanDeg, phiDeg))
}

/** 设置播放速度. */
export function setSpeed(speed: number): void {
  state.speed = speed
}

/** 切换单齿/全齿. */
export function toggleGearMode(): void {
  state.gearMode = state.gearMode === 'single' ? 'full' : 'single'
}

/** 切换光谱扫掠面模式. */
export function toggleSpectrumMode(): void {
  state.spectrumMode = !state.spectrumMode
  if (state.spectrumMode) {
    state.playing = false // 切到光谱时暂停动画
  }
}

/** 切换截面切片模式（沿齿向选廓线平面）. */
export function toggleSectionMode(): void {
  state.sectionMode = !state.sectionMode
}

/** 设置截面层号. */
export function setSectionIz(iz: number): void {
  state.sectionIz = iz
}

/** 截面可用性：后端 anim 元数据带 n_profile/layer_zs 才能切层. */
export const sectionAvailable = computed(() => {
  const d = state.animData
  return !!(d?.n_profile && d.n_profile > 0 && d.layer_zs && d.layer_zs.length > 1)
})

/** 当前截面层的 W 系 z 坐标 [mm]（无层信息时 null）. */
export const sectionZmm = computed(() => {
  const d = state.animData
  if (!d?.layer_zs || d.layer_zs.length === 0) return null
  return d.layer_zs[Math.min(Math.max(state.sectionIz, 0), d.layer_zs.length - 1)]
})

/**
 * 由 gearViewport.animate() 每帧调用，推进 φ（乒乓）.
 * 单程（−span → +span）耗时 1s / speed.
 *
 * @param dt 距上一帧的时间 [s]
 * @returns 当前 φ_t [deg]，未播放时 null
 */
export function tickAnimation(dt: number): number | null {
  if (!state.playing || state.spanDeg <= 0) return null
  state.phiDeg += state.direction * state.speed * (2 * state.spanDeg) * dt
  if (state.phiDeg >= state.spanDeg) {
    state.phiDeg = state.spanDeg
    state.direction = -1
  } else if (state.phiDeg <= -state.spanDeg) {
    state.phiDeg = -state.spanDeg
    state.direction = 1
  }
  return state.phiDeg
}
