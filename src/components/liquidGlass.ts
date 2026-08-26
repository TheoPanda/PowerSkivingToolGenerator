/**
 * liquidGlass.ts — 液态玻璃真折光层（SVG feDisplacementMap + backdrop-filter）
 *
 * 原理（kube.io 2025 复刻路线，Apple Liquid Glass 分层模型）：
 *  - 凸面 squircle 边缘剖面：边缘位移大、中心平坦 → 背景在玻璃边缘被弯折（折射感）
 *  - 位移场编码为位图：R=X 位移、G=Y 位移、128=中性（feDisplacementMap 语义）
 *  - backdrop-filter: url(#filter) 引用 SVG 滤镜仅 Chromium 支持 → Electron 全兼容；
 *    未安装/不支持时 CSS 变量回退 blur(0px)，面板退化为纯模糊玻璃（保底不破相）
 *  - 边缘镜面高光（rim light）由 .liquid-glass::after 的 conic 渐变环承担（theme.css）
 *
 * 用法：面板根元素加 .liquid-glass class + onMounted 调 installGlassRefraction(el, key)。
 * 尺寸变化（步骤展开/收起、面板折叠）经 ResizeObserver 自动重装（同尺寸跳过）。
 * jsdom（测试）无布局/无 canvas → 静默退化，不影响单测。
 */

export interface GlassRefractionOptions {
  bezel?: number   // 折射边带宽度 [px]（默认 min(边长)*0.22，上限 34）
  strength?: number // feDisplacementMap scale [px]；实际最大位移 ≈ strength/2（默认 22 → 11px）
}

/** 全局滤镜宿主（懒创建，挂在 body 下，0×0 不占布局）. */
function ensureHost(): SVGSVGElement {
  let host = document.getElementById('liquid-glass-filters') as SVGSVGElement | null
  if (!host) {
    host = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    host.id = 'liquid-glass-filters'
    host.setAttribute('width', '0')
    host.setAttribute('height', '0')
    host.style.position = 'absolute'
    document.body.appendChild(host)
  }
  return host
}

/** 已安装面板的尺寸（同尺寸重入直接跳过，ResizeObserver 防循环）. */
const installed = new Map<string, { w: number; h: number }>()

/** 观察器引用（WeakMap 键销毁即回收，不需显式 disconnect）. */
const observers = new WeakMap<HTMLElement, ResizeObserver>()

/**
 * 凸面位移剖面：t=0（玻璃外缘）→ 1（最大位移），t=1（bezel 内界）→ 0（接平面）。
 * 平滑衔接（squircle 精神）：外缘陡、内侧缓，避免折光带内侧出现硬边界。
 */
function profile(t: number): number {
  const c = Math.min(Math.max(t, 0), 1)
  return (1 - c) * (1 - c * c)
}

/** 为面板安装边缘折射：生成位移图 → 注册全局 SVG filter → inline 写单层 backdrop-filter. */
export function installGlassRefraction(el: HTMLElement, key: string, opts: GlassRefractionOptions = {}): void {
  const w = el.offsetWidth
  const h = el.offsetHeight
  if (w < 8 || h < 8) return // jsdom 无布局 / 未渲染（隐藏面板由 ResizeObserver 显示后补装）
  const prev = installed.get(key)
  if (prev && prev.w === w && prev.h === h) return
  installed.set(key, { w, h })

  const bezel = opts.bezel ?? Math.min(34, Math.round(Math.min(w, h) * 0.22))
  const strength = opts.strength ?? 22

  // 位移图：凸面 → 取样指向面内（左边缘 vx>0 向右、上边缘 vy>0 向下），
  // 角落两分量自然合成对角向（kube.io「旋转对称、单边计算复用」同思路）
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) return // 无 canvas 环境（测试）→ 静默退化
  const img = ctx.createImageData(w, h)
  for (let y = 0; y < h; y++) {
    const dT = y
    const dB = h - 1 - y
    const vy = (dT < bezel ? profile(dT / bezel) : 0) - (dB < bezel ? profile(dB / bezel) : 0)
    for (let x = 0; x < w; x++) {
      const dL = x
      const dR = w - 1 - x
      const vx = (dL < bezel ? profile(dL / bezel) : 0) - (dR < bezel ? profile(dR / bezel) : 0)
      const i = (y * w + x) * 4
      img.data[i] = 128 + Math.round(vx * 127)
      img.data[i + 1] = 128 + Math.round(vy * 127)
      img.data[i + 2] = 128 // B 通道被忽略
      img.data[i + 3] = 255
    }
  }
  ctx.putImageData(img, 0, 0)

  // 注册/更新全局 filter（userSpaceOnUse：坐标 = 元素盒局部系，须与元素尺寸一致）
  const id = `lg-${key}`
  const host = ensureHost()
  let filter = document.getElementById(id) as SVGFilterElement | null
  if (!filter) {
    filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter')
    filter.id = id
    filter.setAttribute('color-interpolation-filters', 'sRGB')
    filter.setAttribute('filterUnits', 'userSpaceOnUse')
    const feImage = document.createElementNS('http://www.w3.org/2000/svg', 'feImage')
    feImage.setAttribute('result', 'map')
    feImage.setAttribute('preserveAspectRatio', 'none')
    const feDisp = document.createElementNS('http://www.w3.org/2000/svg', 'feDisplacementMap')
    feDisp.setAttribute('in', 'SourceGraphic')
    feDisp.setAttribute('in2', 'map')
    feDisp.setAttribute('xChannelSelector', 'R')
    feDisp.setAttribute('yChannelSelector', 'G')
    filter.appendChild(feImage)
    filter.appendChild(feDisp)
    host.appendChild(filter)
  }
  filter.setAttribute('x', '0')
  filter.setAttribute('y', '0')
  filter.setAttribute('width', String(w))
  filter.setAttribute('height', String(h))
  const feImage = filter.querySelector('feImage') as SVGFEImageElement
  feImage.setAttribute('x', '0')
  feImage.setAttribute('y', '0')
  feImage.setAttribute('width', String(w))
  feImage.setAttribute('height', String(h))
  feImage.setAttribute('href', canvas.toDataURL())
  const feDisp = filter.querySelector('feDisplacementMap') as SVGFEDisplacementMapElement
  feDisp.setAttribute('scale', String(strength))

  // 单层合并（v6）：折射 url + 饱和/亮度写进**同一** backdrop-filter 链，
  // 直接以 inline style 下发（优先级高于组件 scoped 声明）。用户要求取消模糊
  // （2026-08-26）：blur 分量移除——纯折射形态（kube.io slider 的 Blur 0.0 同款），
  // 背景渐变经边缘弯折清晰透出。伪元素双层 backdrop-filter 在 Chromium 有
  // 白化渲染异常，禁止再叠层。
  el.style.backdropFilter = `url(#${id}) saturate(175%) brightness(1.04)`
  el.style.setProperty('-webkit-backdrop-filter', `url(#${id}) saturate(175%) brightness(1.04)`)

  // 尺寸自适应（步骤展开/面板折叠）：同尺寸早退防观察循环；jsdom 无 ResizeObserver 跳过
  if (typeof ResizeObserver !== 'undefined' && !observers.has(el)) {
    const ro = new ResizeObserver(() => {
      requestAnimationFrame(() => installGlassRefraction(el, key, opts))
    })
    ro.observe(el)
    observers.set(el, ro)
  }
}
