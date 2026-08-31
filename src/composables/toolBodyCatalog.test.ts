/**
 * toolBodyCatalog 纯数据单测 — 手册标准表 / 对档规则 / 键槽查表 / 可行性预过滤
 * （与 backend tool_body 纯数学测试同源对照；ADR-021 表驱动的前端闸门）.
 */
import { describe, it, expect } from 'vitest'
import {
  TOOL_BODY_SEGMENTS,
  filterBoresByRoot,
  selectToolBodySegment,
  toolBodyDefaultThickness,
  toolBodyKeywayB,
  toolBodyKeywayDepth,
} from './toolBodyCatalog'

describe('toolBodyCatalog — 对档与查表', () => {
  it('向下取档：84.9→φ75、74.9→φ63、30→钳制 φ40（安全侧，ADR-021 ⑤）', () => {
    expect(selectToolBodySegment(84.9).dia).toBe(75)
    expect(selectToolBodySegment(74.9).dia).toBe(63)
    expect(selectToolBodySegment(30).dia).toBe(40)
    expect(selectToolBodySegment(100).dia).toBe(100)
    expect(selectToolBodySegment(500).dia).toBe(200)
  })

  it('档位表与规格文档数值一致（孔径系列 / 厚度系列）', () => {
    expect(TOOL_BODY_SEGMENTS.map((s) => s.dia)).toEqual([40, 63, 75, 100, 125, 160, 200])
    expect(TOOL_BODY_SEGMENTS.find((s) => s.dia === 100)?.bores).toEqual([31.743, 44.443])
    expect(TOOL_BODY_SEGMENTS.find((s) => s.dia === 75)?.thickness).toEqual([15, 17, 20])
  })

  it('键槽宽随档×模数段（φ100：m≤1.6→10 / 更大→12）；图纸锚定 31.743→14 优先', () => {
    const seg100 = selectToolBodySegment(100)
    expect(toolBodyKeywayB(seg100, 1.2)).toBe(10)
    expect(toolBodyKeywayB(seg100, 2)).toBe(12)
    expect(toolBodyKeywayB(selectToolBodySegment(75), 3)).toBe(10)
    expect(toolBodyKeywayB(selectToolBodySegment(75), 3, 31.743)).toBe(14) // 图纸 4035100343
  })

  it('键槽深：图纸锚定 31.743→6.0 优先，其余 GB/T 6132 最近档；非系列孔径 null', () => {
    expect(toolBodyKeywayDepth(31.743)).toBe(6.0)
    expect(toolBodyKeywayDepth(44.443)).toBe(3.5)
    expect(toolBodyKeywayDepth(99)).toBeNull()
  })

  it('默认厚度 = 档内 ≥L 最小值；全 <L null', () => {
    const seg75 = selectToolBodySegment(75)
    expect(toolBodyDefaultThickness(seg75, 4)).toBe(15)
    expect(toolBodyDefaultThickness(seg75, 16)).toBe(17)
    expect(toolBodyDefaultThickness(seg75, 21)).toBeNull()
  })
})

describe('toolBodyCatalog — 内孔可行性预过滤（Q10）', () => {
  const seg100 = selectToolBodySegment(100)

  it('孔缘含键槽底 ≥ r_root 的孔径被滤除', () => {
    // 44.443：r_bore+t1 = 22.2215+3.5 = 25.72 ≥ 25 → 滤除；31.743 侧 15.87+2.8 < 25 留
    expect(filterBoresByRoot(seg100, 25, 3.5)).toEqual([31.743])
  })

  it('无键槽时只看孔缘；rRoot=null（估算不可用）不过滤', () => {
    // 44.443 孔缘 22.2215：< 22.5 留、≥ 22.0 滤
    expect(filterBoresByRoot(seg100, 22.5, null)).toEqual([31.743, 44.443])
    expect(filterBoresByRoot(seg100, 22.0, null)).toEqual([31.743])
    expect(filterBoresByRoot(seg100, null, null)).toEqual(seg100.bores)
  })
})
