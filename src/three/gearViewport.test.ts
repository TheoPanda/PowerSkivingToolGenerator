/**
 * gearViewport 多图层测试 — 注入 fake renderer，测图层增删/显隐/透明度/清空/dispose。
 *
 * 接缝（spec Testing Decisions）：rendererFactory 注入 fake；GLTFLoader 用真实 GLB
 * （由后端 gltf_export 生成，硬编码 base64）；STLLoader mock 走 error 短路。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import * as THREE from 'three'
import { createGearViewport, type GearViewport } from './gearViewport'
import type { LayerId } from './layerPalette'

vi.mock('three/examples/jsm/loaders/STLLoader.js', () => ({
  STLLoader: class {
    load(_url: string, _onLoad: unknown, _onProgress: unknown, onError: (e: Error) => void): void {
      onError(new Error('no stl in test'))
    }
  },
}))

// GLB 解析是 Three.js 职责（后端已有 GLB 往返测试）；前端聚焦图层逻辑，mock 为同步返回一个含 mesh 的 scene。
// 注意用顶层 import 的 THREE（ESM 构建），与 gearViewport 的 instanceof 检查一致。
vi.mock('three/examples/jsm/loaders/GLTFLoader.js', () => ({
  GLTFLoader: class {
    parse(_buffer: ArrayBuffer, _path: string, onLoad: (gltf: { scene: THREE.Group }) => void, _onError: unknown): void {
      const group = new THREE.Group()
      group.add(new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial()))
      onLoad({ scene: group })
    }
  },
}))

// 后端 export_geometry_glb 生成的真实 GLB（一个三角形 mesh + 一条折线）
const MESH_B64 = 'Z2xURgIAAABYAwAA7AIAAEpTT057ImFjY2Vzc29ycyI6W3siYnVmZmVyVmlldyI6MCwiYnl0ZU9mZnNldCI6MCwiY29tcG9uZW50VHlwZSI6NTEyNiwibm9ybWFsaXplZCI6ZmFsc2UsImNvdW50IjozLCJ0eXBlIjoiVkVDMyIsIm1heCI6WzEuMCwxLjAsMC4wXSwibWluIjpbMC4wLDAuMCwwLjBdfSx7ImJ1ZmZlclZpZXciOjEsImJ5dGVPZmZzZXQiOjAsImNvbXBvbmVudFR5cGUiOjUxMjYsIm5vcm1hbGl6ZWQiOmZhbHNlLCJjb3VudCI6MywidHlwZSI6IlZFQzMifSx7ImJ1ZmZlclZpZXciOjIsImJ5dGVPZmZzZXQiOjAsImNvbXBvbmVudFR5cGUiOjUxMjMsIm5vcm1hbGl6ZWQiOmZhbHNlLCJjb3VudCI6MywidHlwZSI6IlNDQUxBUiJ9XSwiYXNzZXQiOnsiZ2VuZXJhdG9yIjoicHlnbHRmbGliQHYxLjE2LjUiLCJ2ZXJzaW9uIjoiMi4wIn0sImJ1ZmZlclZpZXdzIjpbeyJidWZmZXIiOjAsImJ5dGVPZmZzZXQiOjAsImJ5dGVMZW5ndGgiOjM2fSx7ImJ1ZmZlciI6MCwiYnl0ZU9mZnNldCI6MzYsImJ5dGVMZW5ndGgiOjM2fSx7ImJ1ZmZlciI6MCwiYnl0ZU9mZnNldCI6NzIsImJ5dGVMZW5ndGgiOjh9XSwiYnVmZmVycyI6W3siYnl0ZUxlbmd0aCI6ODB9XSwibWVzaGVzIjpbeyJwcmltaXRpdmVzIjpbeyJhdHRyaWJ1dGVzIjp7IlBPU0lUSU9OIjowLCJOT1JNQUwiOjF9LCJpbmRpY2VzIjoyLCJtb2RlIjo0fV19XSwibm9kZXMiOlt7Im1lc2giOjAsIm5hbWUiOiJnZW5lcmF0cml4In1dLCJzY2VuZSI6MCwic2NlbmVzIjpbeyJub2RlcyI6WzBdfV19UAAAAEJJTgAAAAAAAAAAAAAAAAAAAIA/AAAAAAAAAAAAAAAAAACAPwAAAAAAAAAAAAAAAAAAgD8AAAAAAAAAAAAAgD8AAAAAAAAAAAAAgD8AAAEAAgAAAA=='
const LINE_B64 = 'Z2xURgIAAAD0AQAAtAEAAEpTT057ImFjY2Vzc29ycyI6W3siYnVmZmVyVmlldyI6MCwiYnl0ZU9mZnNldCI6MCwiY29tcG9uZW50VHlwZSI6NTEyNiwibm9ybWFsaXplZCI6ZmFsc2UsImNvdW50IjozLCJ0eXBlIjoiVkVDMyIsIm1heCI6WzEuMCwxLjAsMC4wXSwibWluIjpbMC4wLDAuMCwwLjBdfV0sImFzc2V0Ijp7ImdlbmVyYXRvciI6InB5Z2x0ZmxpYkB2MS4xNi41IiwidmVyc2lvbiI6IjIuMCJ9LCJidWZmZXJWaWV3cyI6W3siYnVmZmVyIjowLCJieXRlT2Zmc2V0IjowLCJieXRlTGVuZ3RoIjozNn1dLCJidWZmZXJzIjpbeyJieXRlTGVuZ3RoIjozNn1dLCJtZXNoZXMiOlt7InByaW1pdGl2ZXMiOlt7ImF0dHJpYnV0ZXMiOnsiUE9TSVRJT04iOjB9LCJtb2RlIjozfV19XSwibm9kZXMiOlt7Im1lc2giOjAsIm5hbWUiOiJlZGdlIn1dLCJzY2VuZSI6MCwic2NlbmVzIjpbeyJub2RlcyI6WzBdfV19JAAAAEJJTgAAAAAAAAAAAAAAAAAAAIA/AAAAAAAAAAAAAIA/AACAPwAAAAA='

let lastScene: THREE.Scene | null = null

function createFakeRenderer() {
  const render = vi.fn((scene: THREE.Scene) => {
    lastScene = scene
  })
  const renderer = {
    domElement: document.createElement('canvas'),
    setSize: vi.fn(),
    setPixelRatio: vi.fn(),
    shadowMap: { enabled: false, type: 0 },
    toneMapping: 0,
    toneMappingExposure: 1,
    dispose: vi.fn(),
    render,
  }
  return { renderer: renderer as unknown as THREE.WebGLRenderer, render, dispose: renderer.dispose }
}

function createViewport() {
  lastScene = null
  const container = document.createElement('div')
  Object.defineProperty(container, 'clientWidth', { value: 800 })
  Object.defineProperty(container, 'clientHeight', { value: 600 })
  const fake = createFakeRenderer()
  const vp: GearViewport = createGearViewport({
    container,
    modelLoaded: ref(false),
    modelLoadProgress: ref(0),
    renderMode: ref('solid'),
    onGearDisplayed: () => {},
    rendererFactory: () => fake.renderer,
  })
  return { vp, container, fake }
}

function findLayerGroup(id: LayerId): THREE.Group | null {
  if (!lastScene) return null
  let found: THREE.Group | null = null
  lastScene.traverse((c) => {
    if (c.name === id && (c as THREE.Group).isGroup) found = c as THREE.Group
  })
  return found
}

function firstMesh(group: THREE.Group): THREE.Mesh {
  let mesh: THREE.Mesh | null = null
  group.traverse((c) => { if (!mesh && (c as THREE.Mesh).isMesh) mesh = c as THREE.Mesh })
  return mesh as unknown as THREE.Mesh
}

/** 按 name 在 lastScene 全树查找首个匹配对象（Sprite / Group / Mesh 通用）. */
function findByName(name: string): THREE.Object3D | null {
  if (!lastScene) return null
  let found: THREE.Object3D | null = null
  lastScene.traverse((c) => { if (!found && c.name === name) found = c })
  return found
}

beforeEach(() => {
  lastScene = null
  let rafCalled = false
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback): number => {
    if (!rafCalled) {
      rafCalled = true
      cb(0)
    }
    return 1
  })
  vi.stubGlobal('cancelAnimationFrame', (): void => {})
  // 静音 jsdom 的 getContext "Not implemented" 噪声；返回 null 走 makeTextSprite 空标注占位分支（本测试只断言结构）
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('gearViewport 多图层', () => {
  it('addLayer 创建独立图层 group（各层独立）', () => {
    const { vp } = createViewport()
    vp.addLayer('rake', MESH_B64)
    vp.addLayer('edge', LINE_B64)
    const rake = findLayerGroup('rake')
    const edge = findLayerGroup('edge')
    expect(rake).toBeTruthy()
    expect(edge).toBeTruthy()
    expect(rake).not.toBe(edge)
  })

  it('setLayerVisible 正确显隐', () => {
    const { vp } = createViewport()
    vp.addLayer('rake', MESH_B64)
    const rake = findLayerGroup('rake') as THREE.Group
    vp.setLayerVisible('rake', false)
    expect(rake.visible).toBe(false)
    vp.setLayerVisible('rake', true)
    expect(rake.visible).toBe(true)
  })

  it('setLayerOpacity 只调本层（材质独立不串改）', () => {
    const { vp } = createViewport()
    vp.addLayer('conjugate', MESH_B64)
    vp.addLayer('rake', MESH_B64)
    const conj = findLayerGroup('conjugate') as THREE.Group
    const rake = findLayerGroup('rake') as THREE.Group
    vp.setLayerOpacity('conjugate', 0.5)
    const conjMat = firstMesh(conj).material as THREE.MeshStandardMaterial
    const rakeMat = firstMesh(rake).material as THREE.MeshStandardMaterial
    expect(conjMat.opacity).toBe(0.5)
    expect(rakeMat.opacity).toBe(0.45) // rake 默认透明度不被串改
  })

  it('clearLayers 清空非工件层（保留 workpiece）', () => {
    const { vp } = createViewport()
    vp.loadGear(MESH_B64)
    vp.addLayer('rake', MESH_B64)
    vp.clearLayers()
    expect(findLayerGroup('rake')).toBeNull()
    expect(findLayerGroup('workpiece')).toBeTruthy()
  })

  it('removeLayer 不删除工件基准层', () => {
    const { vp } = createViewport()
    vp.loadGear(MESH_B64)
    vp.removeLayer('workpiece')
    expect(findLayerGroup('workpiece')).toBeTruthy()
  })

  it('setWorkpieceView 工件透明线框：透明面 + 边线 + 切回实体', () => {
    const { vp } = createViewport()
    vp.loadGear(MESH_B64)
    const wp = findLayerGroup('workpiece') as THREE.Group
    const mesh = firstMesh(wp)
    // 空 mock 几何补一个三角形，便于验证边线生成
    mesh.geometry = new THREE.BufferGeometry()
    mesh.geometry.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0, 1, 0, 0, 0, 1, 0], 3))
    const solidMat = mesh.material

    // 切到透明线框：材质变透明 + 挂载一条边线 LineSegments
    vp.setWorkpieceView('wireframe')
    const wireMat = mesh.material as THREE.MeshStandardMaterial
    expect(wireMat.transparent).toBe(true)
    expect(wireMat.opacity).toBeCloseTo(0.15)
    let lines = 0
    mesh.traverse((c) => { if ((c as THREE.LineSegments).isLineSegments) lines++ })
    expect(lines).toBe(1)

    // 切回实体：材质还原为原实体材质 + 边线移除
    vp.setWorkpieceView('solid')
    expect(mesh.material).toBe(solidMat)
    let lines2 = 0
    mesh.traverse((c) => { if ((c as THREE.LineSegments).isLineSegments) lines2++ })
    expect(lines2).toBe(0)
  })

  it('setWorkpieceView 无工件层时安全 no-op', () => {
    const { vp } = createViewport()
    expect(() => vp.setWorkpieceView('wireframe')).not.toThrow()
    expect(() => vp.setWorkpieceView('solid')).not.toThrow()
  })

  it('dispose 移除画布 DOM + 释放 renderer', () => {
    const { vp, container, fake } = createViewport()
    vp.dispose()
    expect(fake.dispose).toHaveBeenCalled()
    expect(container.querySelector('canvas')).toBeNull()
  })

  it('dispose 释放图层 geometry/material（无残留）', () => {
    const { vp } = createViewport()
    vp.addLayer('rake', MESH_B64)
    const rake = findLayerGroup('rake') as THREE.Group
    const mesh = firstMesh(rake)
    const geometryDispose = vi.spyOn(mesh.geometry, 'dispose')
    const materialDispose = vi.spyOn(mesh.material as THREE.Material, 'dispose')
    vp.dispose()
    expect(geometryDispose).toHaveBeenCalled()
    expect(materialDispose).toHaveBeenCalled()
  })

  it('setEnvelopeInstall 画坐标轴 + 施加 T→W 变换不抛错', () => {
    const { vp } = createViewport()
    expect(() => vp.setEnvelopeInstall(39.55, 15.0)).not.toThrow()
    // 无图层时也能画坐标轴（W 原点 + T 偏移）
    expect(lastScene).toBeTruthy()
  })

  it('rake/flank/singleTooth 图层也施加 T→W 安装变换', () => {
    const { vp } = createViewport()
    vp.setEnvelopeInstall(39.55, 15.0)
    vp.addLayer('rake', MESH_B64)
    vp.addLayer('flank', MESH_B64)
    vp.addLayer('singleTooth', MESH_B64)
    const rake = findLayerGroup('rake') as THREE.Group
    const flank = findLayerGroup('flank') as THREE.Group
    const tooth = findLayerGroup('singleTooth') as THREE.Group
    expect(rake.position.x).toBeCloseTo(39.55)
    expect(rake.rotation.x).toBeCloseTo((15 * Math.PI) / 180)
    expect(flank.position.x).toBeCloseTo(39.55)
    expect(tooth.rotation.x).toBeCloseTo((15 * Math.PI) / 180)
  })

  it('setEnvelopeInstall 画 6 个 X/Y/Z 标注（W/T 前缀）+ 2 个旋转指针', () => {
    const { vp } = createViewport()
    vp.setEnvelopeInstall(39.55, 15.0)
    for (const axis of ['X', 'Y', 'Z']) {
      for (const frame of ['W', 'T']) {
        expect(findByName(`axis-label-${axis}_${frame}`)).toBeTruthy()
      }
    }
    expect(findByName('rotation-pointer-W')).toBeTruthy()
    expect(findByName('rotation-pointer-T')).toBeTruthy()
    // W/T 指针是各自独立对象
    expect(findByName('rotation-pointer-W')).not.toBe(findByName('rotation-pointer-T'))
  })

  it('旋转指针含弧身 + 箭头锥体（2 个 Mesh）', () => {
    const { vp } = createViewport()
    vp.setEnvelopeInstall(39.55, 15.0)
    const wPtr = findByName('rotation-pointer-W') as THREE.Group
    let meshCount = 0
    wPtr.traverse((c) => { if ((c as THREE.Mesh).isMesh) meshCount++ })
    expect(meshCount).toBe(2) // 弧身（圆环管 TubeGeometry）+ 箭头（圆锥 ConeGeometry）
  })

  it('dispose 清空坐标轴标注与旋转指针', () => {
    const { vp } = createViewport()
    vp.setEnvelopeInstall(39.55, 15.0)
    expect(findByName('axis-label-X_W')).toBeTruthy()
    vp.dispose()
    expect(findByName('axis-label-X_W')).toBeNull()
    expect(findByName('rotation-pointer-W')).toBeNull()
  })
})
