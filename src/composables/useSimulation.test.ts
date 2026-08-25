/**
 * useSimulation 测试 — φ_t 角度域状态（±spanDeg 滑条、omega_ratio → ±360°、乒乓播放）.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import type { AnimData } from '../api'
import {
  simState, openSimulation, closeSimulation,
  setPhi, resetPhi, tickAnimation, angleRange, currentPhiTDeg,
} from './useSimulation'

/** 均匀采样动画数据（后端 linspace(−θ,+θ,m) 语义）：帧铺 ±frameTheta，元数据 metaTheta（可与帧不同），可选 omega_ratio. */
function fakeAnim(m: number, frameTheta: number, metaTheta?: number, omegaRatio?: number): AnimData {
  const frames = Array.from({ length: m }, (_, i) => ({
    phi_t_deg: -frameTheta + ((2 * frameTheta * i) / (m - 1)),
    positions: [] as number[],
  }))
  return {
    frames, indices: [], mesh_indices: [], n_vertices: 0,
    theta_range_deg: metaTheta ?? frameTheta, ...(omegaRatio != null ? { omega_ratio: omegaRatio } : {}),
  }
}

describe('useSimulation φ 角度域', () => {
  beforeEach(() => {
    openSimulation(fakeAnim(72, 120, undefined, 2))
  })

  it('omega_ratio 存在 → span=360（合成模式）；缺省 → 帧实际范围半程', () => {
    expect(simState.spanDeg).toBe(360)
    expect(angleRange.value).toEqual({ min: -360, max: 360 })
    expect(simState.phiDeg).toBe(-360) // 起点在滑条左端
    // 回退：帧铺 ±40°、元数据标 120°（接触求解域）→ span 按帧端点=40，不采信元数据
    openSimulation(fakeAnim(72, 40, 120))
    expect(simState.spanDeg).toBe(40)
    openSimulation(fakeAnim(72, 120, undefined, 2)) // 恢复
  })

  it('setPhi 夹到 ±span（1° 步进滑条越界防护）', () => {
    setPhi(13)
    expect(simState.phiDeg).toBe(13)
    setPhi(999)
    expect(simState.phiDeg).toBe(360)
    setPhi(-999)
    expect(simState.phiDeg).toBe(-360)
  })

  it('tickAnimation 乒乓推进（720°/s × speed，端点反弹）', () => {
    simState.playing = true
    simState.phiDeg = 359
    const phi = tickAnimation(1 / 720) // 1ms 推进 1°
    expect(phi).toBe(360)
    expect(simState.direction).toBe(-1) // 端点反弹
    tickAnimation(1 / 720)
    expect(simState.phiDeg).toBeCloseTo(359, 6)
    simState.playing = false
    expect(tickAnimation(1)).toBeNull()
  })

  it('resetPhi 回到 −span 并停播；currentPhiTDeg 跟随', () => {
    setPhi(123.4)
    simState.playing = true
    resetPhi()
    expect(simState.phiDeg).toBe(-360)
    expect(simState.playing).toBe(false)
    expect(currentPhiTDeg.value).toBe(-360)
  })

  it('closeSimulation 复位默认（无数据时安全）', () => {
    closeSimulation()
    expect(simState.open).toBe(false)
    expect(simState.animData).toBeNull()
    expect(() => setPhi(5)).not.toThrow()
    expect(simState.phiDeg).toBe(5) // span 复位 360，5 在界内原值保留
    expect(simState.spanDeg).toBe(360)
  })
})
