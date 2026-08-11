<script setup lang="ts">
/**
 * ToothProfileSvg.vue — 单齿廓图（端面，目标齿 + 左右邻齿连成一体）+ ISO 尺寸标注
 *
 * - 主路径 = spec.single_tooth.neighborhood（后端产出的**连续三齿开放链**，三齿连成一体、
 *   齿根过渡圆角按 ISO 53 ρ*_f 已含在内）；无 neighborhood 时回退为目标齿 + 旋转邻齿
 * - 分度线为**连贯点画线**（跨三齿一整条，随齿轮曲率）；齿顶圆为浅灰虚线（同一跨幅）
 * - 标注布局：
 *   · 齿厚/齿距 = 分度线上下**平行弧线**（同心偏移），弧端**实心点**截止，文字贴弧
 *   · 齿顶高/齿底高 = 与左齿中分线**平行且重合**的尺寸线，分度处与两端实心点隔断
 *   · 齿全高 = 左齿中分线外侧平行尺寸线
 *   · 齿顶/齿根圆角 = 靠近**中间齿**（目标齿顶/齿根）的短尺寸线
 * - 固定像素画布 + vector-effect="non-scaling-stroke"（线宽/文字缩放不变量）
 * - 支持滚轮缩放 + 拖拽平移 + 按钮复位
 * 几何全部来自 spec（前端不重算齿形，±0.0001mm 由后端保证）。
 */
import { computed } from 'vue'
import type { Arc, Point2, Segment, SingleToothSpec } from '../api'
import { dimensionDefs, arrowMarkerId, formatDim } from './dimension'
import { useSvgViewport } from '../composables/useSvgViewport'

const CANVAS_W = 760
const CANVAS_H = 360
const TOOTH_LEFT = 150
const TOOTH_RIGHT = 690
const TOOTH_TOP = 60
const TOOTH_BOTTOM = 340

// 布局常量（px，画布固定坐标下）
const PITCH_DASH = '14 4 2 4' // 分度线：点画线
const TIP_CIRCLE_COLOR = '#C6CDD4' // 齿顶圆：浅灰
const TIP_DASH = '8 5' // 齿顶圆：虚线
const PAR_OFFSET_PX = 9 // 齿厚/齿距 平行弧距分度线的偏距
const ARC_TEXT_GAP_PX = 5 // 弧标注文字贴弧间隙
const HEIGHT_O1 = 118 // 齿全高线（左齿中分线外侧）偏距
const HEIGHT_O2 = 94 // 齿顶/齿底高重合线偏距
const HEIGHT_TEXT_GAP_PX = 10 // 高度标注文字距尺寸线间隙
const DOT_R = 2.6 // 实心点（弧端截止 / 重合线隔断）

const props = defineProps<{
  singleTooth: SingleToothSpec
}>()

const rot = computed<number>(() => (props.singleTooth.center_line.from_angle_deg * Math.PI) / 180)
const pitchR = computed<number>(() => props.singleTooth.pitch_line.r)
const s_t = computed<number>(() => props.singleTooth.annotations.tooth_thickness.value)
/** 单齿相位角（rad）= 弧齿距 / 分度圆半径 = 2π/z_w. */
const phase = computed<number>(() => props.singleTooth.annotations.circular_pitch.value / pitchR.value)
/** 齿厚半角 = s_t/(2·r_pw). */
const pitchHalf = computed<number>(() => s_t.value / (2 * pitchR.value))
/** 齿顶/分度/齿根圆半径（mm，由分度线 + 标注高度推导，与后端同源）. */
const rTip = computed<number>(() => pitchR.value + props.singleTooth.annotations.addendum.value)
const rPitch = computed<number>(() => pitchR.value)
const rRoot = computed<number>(() => pitchR.value - props.singleTooth.annotations.dedendum.value)

function rotateP(p: Point2, ang: number): Point2 {
  const c = Math.cos(ang)
  const s = Math.sin(ang)
  return [p[0] * c - p[1] * s, p[0] * s + p[1] * c]
}
function toLocal(p: Point2): Point2 {
  return rotateP(p, rot.value)
}
function arcPointLocal(seg: Arc, ang: number): Point2 {
  const [cx, cy] = toLocal(seg.center)
  const a = ang + rot.value
  return [cx + seg.radius * Math.cos(a), cy + seg.radius * Math.sin(a)]
}
/** 短弧终点角度（后端弧可能以 >180° 跨度表达，如根弧 a0=4°→a1=356° 实为 8° 短弧）. */
function shortArcEnd(seg: Arc): number {
  let d = seg.a1 - seg.a0
  d = ((d % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)
  if (d > Math.PI) d -= 2 * Math.PI
  return seg.a0 + d
}
/** 圆弧短弧采样点（局部系）. */
function arcSamplePoints(seg: Arc, steps: number): Point2[] {
  const end = shortArcEnd(seg)
  const pts: Point2[] = []
  for (let i = 0; i <= steps; i++) {
    pts.push(arcPointLocal(seg, seg.a0 + ((end - seg.a0) * i) / steps))
  }
  return pts
}
/** 段列 → 局部点列（bbox 用；圆弧取短弧）. */
function segsToLocalPoints(segs: Segment[]): Point2[] {
  const pts: Point2[] = []
  for (const seg of segs) {
    if (seg.type === 'arc') pts.push(...arcSamplePoints(seg, 20))
    else for (const p of seg.points) pts.push(toLocal(p))
  }
  return pts
}

/** 连接齿廓段（后端 neighborhood；无则回退为空 → 用回退渲染）. */
const connectedSegs = computed<Segment[]>(() => props.singleTooth.neighborhood ?? [])
const hasNeighborhood = computed<boolean>(() => connectedSegs.value.length > 0)

/** 目标齿局部点列 + 邻齿派生（回退路径用）. */
function targetLocalPoints(): Point2[] {
  return segsToLocalPoints(props.singleTooth.segments)
}
function neighborPoints(dPhi: number): Point2[] {
  return targetLocalPoints().map((p) => rotateP(p, dPhi))
}

/** 三齿簇包围盒（neighborhood 或 目标+邻齿）. */
const clusterPoints = computed<Point2[]>(() => {
  if (hasNeighborhood.value) return segsToLocalPoints(connectedSegs.value)
  return [...targetLocalPoints(), ...neighborPoints(phase.value), ...neighborPoints(-phase.value)]
})
const bbox = computed<{ minX: number; maxX: number; minY: number; maxY: number }>(() => {
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const [x, y] of clusterPoints.value) {
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }
  if (!isFinite(minX)) return { minX: -5, maxX: 5, minY: -5, maxY: 5 }
  return { minX, maxX, minY, maxY }
})

const map = computed<{ k: number; ox: number; oy: number }>(() => {
  const { minX, minY, maxX, maxY } = bbox.value
  const w = maxX - minX || 1
  const h = maxY - minY || 1
  const k = Math.min((TOOTH_RIGHT - TOOTH_LEFT) / w, (TOOTH_BOTTOM - TOOTH_TOP) / h)
  const ox = TOOTH_LEFT + ((TOOTH_RIGHT - TOOTH_LEFT) - w * k) / 2 - minX * k
  const oy = TOOTH_TOP + ((TOOTH_BOTTOM - TOOTH_TOP) - h * k) / 2 - minY * k
  return { k, ox, oy }
})
function mapX(x: number): number {
  return map.value.ox + x * map.value.k
}
function mapY(y: number): number {
  return map.value.oy + y * map.value.k
}

/** 段列 → 画布 path（arc → M+A 短弧，polyline → L）. */
function segmentsToPathD(segs: Segment[]): string {
  let d = ''
  for (const seg of segs) {
    if (seg.type === 'arc') {
      const p0 = arcPointLocal(seg, seg.a0)
      const p1 = arcPointLocal(seg, seg.a1)
      const q0 = [mapX(p0[0]), mapY(p0[1])]
      const q1 = [mapX(p1[0]), mapY(p1[1])]
      const r = seg.radius * map.value.k
      const sweep = seg.clockwise ? 0 : 1
      d += `M ${q0[0].toFixed(2)} ${q0[1].toFixed(2)} A ${r.toFixed(2)} ${r.toFixed(2)} 0 0 ${sweep} ${q1[0].toFixed(2)} ${q1[1].toFixed(2)} `
    } else {
      for (const raw of seg.points) {
        const p = toLocal(raw)
        const q = [mapX(p[0]), mapY(p[1])]
        d += d ? `L ${q[0].toFixed(2)} ${q[1].toFixed(2)} ` : `M ${q[0].toFixed(2)} ${q[1].toFixed(2)} `
      }
    }
  }
  return d
}
/** 邻齿回退 path（采样 polyline）. */
function neighborPathD(dPhi: number): string {
  const pts = neighborPoints(dPhi)
  let d = ''
  for (const p of pts) {
    const q = [mapX(p[0]), mapY(p[1])]
    d += d ? ` L ${q[0].toFixed(2)} ${q[1].toFixed(2)}` : `M ${q[0].toFixed(2)} ${q[1].toFixed(2)}`
  }
  return d + ' Z'
}
/** 主齿廓 path：neighborhood（连接三齿）优先；否则目标齿 + 邻齿. */
const targetD = computed<string>(() => segmentsToPathD(props.singleTooth.segments))
const mainPathD = computed<string>(() => {
  if (hasNeighborhood.value) return segmentsToPathD(connectedSegs.value)
  return [targetD.value, neighborPathD(phase.value), neighborPathD(-phase.value)].join(' ')
})
const leftNeighborD = computed<string>(() => neighborPathD(phase.value))
const rightNeighborD = computed<string>(() => neighborPathD(-phase.value))

/** 圆心在原点的半径 r 圆弧采样（齿轮角 a0→a1，局部系经 rot 旋转）. */
function arcOnRadius(r: number, a0: number, a1: number, steps = 16): Point2[] {
  const pts: Point2[] = []
  for (let i = 0; i <= steps; i++) {
    const ang = a0 + ((a1 - a0) * i) / steps + rot.value
    pts.push([r * Math.cos(ang), r * Math.sin(ang)])
  }
  return pts
}
/** 半径 r 圆上、齿轮角 ang 处的一点（画布坐标）. */
function arcPointOn(r: number, ang: number): Point2 {
  const a = ang + rot.value
  return [mapX(r * Math.cos(a)), mapY(r * Math.sin(a))]
}
function arcPathD(pts: Point2[]): string {
  let d = ''
  for (const p of pts) {
    const q = [mapX(p[0]), mapY(p[1])]
    d += d ? ` L ${q[0].toFixed(2)} ${q[1].toFixed(2)}` : `M ${q[0].toFixed(2)} ${q[1].toFixed(2)}`
  }
  return d
}

/** 分度线 & 齿顶圆：连贯跨三齿（左齿左齿面 → 右齿右齿面）的整条曲线. */
const spanA0 = computed<number>(() => -phase.value - pitchHalf.value)
const spanA1 = computed<number>(() => phase.value + pitchHalf.value)
const pitchLineD = computed<string>(() => arcPathD(arcOnRadius(pitchR.value, spanA0.value, spanA1.value, 40)))
const tipCircleD = computed<string>(() => arcPathD(arcOnRadius(rTip.value, spanA0.value, spanA1.value, 40)))

/** 分度线 y 与齿形边界. */
const pitchLocalY = computed<number>(() => {
  const s = Math.sin(rot.value)
  return Math.abs(s) < 1e-9 ? pitchR.value : pitchR.value / s
})
const pitchY = computed<number>(() => mapY(pitchLocalY.value))
const centerX = computed<number>(() => mapX(0))
// 齿形经 toLocal(-90°) 后：齿顶在局部 -y（画布上方 = 较小 y），齿根在局部 -y 更大（画布下方）。
// bbox.minY = 齿顶局部 y，bbox.maxY = 齿根局部 y。
const tipY = computed<number>(() => mapY(bbox.value.minY))
const rootY = computed<number>(() => mapY(bbox.value.maxY))

/** 左齿（画布左侧，-phase 邻齿）中分线方向与垂直偏移方向（局部系单位向量）. */
const leftDir = computed<[number, number]>(() => [-Math.sin(phase.value), -Math.cos(phase.value)])
const leftPerp = computed<[number, number]>(() => [-Math.cos(phase.value), Math.sin(phase.value)])
/** 距原点半径 r、沿左齿中分线偏距 oPx（px）的点（画布坐标）. */
function leftPoint(r: number, oPx: number): Point2 {
  const [dx, dy] = leftDir.value
  const [px, py] = leftPerp.value
  return [mapX(r * dx) + oPx * px, mapY(r * dy) + oPx * py]
}
/** 高度标注文字：在尺寸线（偏距 oPx）基础上沿垂直方向再外推 HEIGHT_TEXT_GAP_PX. */
function leftText(r: number, oPx: number): Point2 {
  const p = leftPoint(r, oPx)
  const [px, py] = leftPerp.value
  return [p[0] + HEIGHT_TEXT_GAP_PX * px, p[1] + HEIGHT_TEXT_GAP_PX * py]
}
/** 左齿中分线（根→顶，略外延）. */
const leftCenterLine = computed<Point2[]>(() => [
  leftPoint(rRoot.value - 0.4, 0),
  leftPoint(rTip.value + 0.4, 0),
])

/** 7 项标注（画布 px）. 齿厚/齿距 = 分度线上下平行弧 + 端部实心点；高度尺寸 = 平行左齿中分线. */
interface Anno {
  role: string
  kind: 'line' | 'arc'
  line?: { x1: number; y1: number; x2: number; y2: number }
  pathD?: string
  textX: number
  textY: number
  text: string
  textAnchor?: string
  /** 实心点（弧端截止 / 重合线隔断点），画布坐标. */
  dots?: Point2[]
  /** 线端用实心点代替箭头（重合线隔断）. */
  noArrows?: boolean
}
const annotations = computed<Anno[]>(() => {
  const a = props.singleTooth.annotations
  const list: Anno[] = []
  const k = map.value.k
  const half = pitchHalf.value
  const parMm = PAR_OFFSET_PX / k

  // 1) 齿厚：分度线上方平行弧（同心偏移 +parMm），端部实心点，文字贴弧上方
  const thR = pitchR.value + parMm
  list.push({
    role: 'tooth_thickness',
    kind: 'arc',
    pathD: arcPathD(arcOnRadius(thR, -half, half)),
    textX: arcPointOn(thR, 0)[0],
    textY: arcPointOn(thR, 0)[1] - ARC_TEXT_GAP_PX,
    text: `齿厚 ${formatDim(a.tooth_thickness.value, 2)}`,
    dots: [arcPointOn(thR, -half), arcPointOn(thR, half)],
  })

  // 2) 齿距：分度线下方平行弧（同心偏移 -parMm），端部实心点，文字贴弧下方
  const ptR = pitchR.value - parMm
  const ptMid = arcPointOn(ptR, phase.value / 2 - half)
  list.push({
    role: 'circular_pitch',
    kind: 'arc',
    pathD: arcPathD(arcOnRadius(ptR, -half, phase.value - half)),
    textX: ptMid[0],
    textY: ptMid[1] + ARC_TEXT_GAP_PX + 12,
    text: `齿距 ${formatDim(a.circular_pitch.value, 2)}`,
    dots: [arcPointOn(ptR, -half), arcPointOn(ptR, phase.value - half)],
  })

  // 3) 齿全高：左齿中分线外侧平行尺寸线（偏距 HEIGHT_O1），两端实心点标明起止
  const wd0 = leftPoint(rRoot.value, HEIGHT_O1)
  const wd1 = leftPoint(rTip.value, HEIGHT_O1)
  const wdText = leftText((rRoot.value + rTip.value) / 2, HEIGHT_O1)
  list.push({
    role: 'whole_depth',
    kind: 'line',
    line: { x1: wd0[0], y1: wd0[1], x2: wd1[0], y2: wd1[1] },
    textX: wdText[0],
    textY: wdText[1],
    text: `齿全高 ${formatDim(a.whole_depth.value, 2)}`,
    textAnchor: 'end',
    dots: [wd0, wd1],
    noArrows: true,
  })

  // 4) 齿顶高 / 齿底高：重合线（同一偏距 HEIGHT_O2），分度处与两端实心点隔断
  const ad0 = leftPoint(rPitch.value, HEIGHT_O2)
  const ad1 = leftPoint(rTip.value, HEIGHT_O2)
  const adText = leftText((rPitch.value + rTip.value) / 2, HEIGHT_O2)
  list.push({
    role: 'addendum',
    kind: 'line',
    line: { x1: ad0[0], y1: ad0[1], x2: ad1[0], y2: ad1[1] },
    textX: adText[0],
    textY: adText[1],
    text: `齿顶高 ${formatDim(a.addendum.value, 2)}`,
    textAnchor: 'end',
    dots: [ad0, ad1],
    noArrows: true,
  })
  const dd0 = leftPoint(rRoot.value, HEIGHT_O2)
  const dd1 = leftPoint(rPitch.value, HEIGHT_O2)
  const ddText = leftText((rRoot.value + rPitch.value) / 2, HEIGHT_O2)
  list.push({
    role: 'dedendum',
    kind: 'line',
    line: { x1: dd0[0], y1: dd0[1], x2: dd1[0], y2: dd1[1] },
    textX: ddText[0],
    textY: ddText[1],
    text: `齿底高 ${formatDim(a.dedendum.value, 2)}`,
    textAnchor: 'end',
    dots: [dd0, dd1],
    noArrows: true,
  })

  // 6) 齿顶圆角/倒角：value>0 才标注 (tip_mode=none 或 ρ=0 时锐角齿顶, 不显示)
  if (a.tip_fillet.value > 0) {
    const tipHalf = a.tooth_thickness.value / (2 * rTip.value)
    const tipRightX = mapX(rTip.value * Math.sin(tipHalf))
    const isChamfer = a.tip_fillet.label === '齿顶倒角'
    list.push({
      role: 'tip_fillet',
      kind: 'line',
      line: { x1: tipRightX + 8, y1: tipY.value, x2: tipRightX + 40, y2: tipY.value },
      textX: tipRightX + 24,
      textY: tipY.value - 9,
      text: isChamfer
        ? `齿顶倒角 C${a.tip_fillet.value.toFixed(2)}×45°`
        : `齿顶R${a.tip_fillet.value.toFixed(2)}`,
    })
  }
  // 7) 齿根圆角：靠近中间齿齿根右侧
  const rootHalf = Math.atan(Math.sin(phase.value / 2) * (pitchR.value / rRoot.value))
  const rootRightX = mapX(rRoot.value * Math.sin(rootHalf))
  list.push({
    role: 'root_fillet',
    kind: 'line',
    line: { x1: rootRightX + 8, y1: rootY.value, x2: rootRightX + 40, y2: rootY.value },
    textX: rootRightX + 24,
    textY: rootY.value + 14,
    text: `齿根R${a.root_fillet.value.toFixed(2)}`,
  })

  return list
})

const markerId = computed<string>(() => arrowMarkerId('tooth-profile'))
const markerUrl = computed<string>(() => `url(#${markerId.value})`)

/** 视口缩放/平移/复位：来自 useSvgViewport 深模块（与 GearOutlineSvg 共享）. */
const { viewBox, onWheel, startPan, zoomAt, reset } = useSvgViewport([0, 0, CANVAS_W, CANVAS_H])
</script>

<template>
  <div class="tooth-profile">
    <div class="tooth-controls">
      <button class="ctl-btn" title="放大" @click="zoomAt(0.9)">＋</button>
      <button class="ctl-btn" title="缩小" @click="zoomAt(1 / 0.9)">－</button>
      <button class="ctl-btn" title="复位" @click="reset">⤾</button>
    </div>
    <svg
      class="tooth-svg"
      :viewBox="viewBox.join(' ')"
      width="100%"
      height="100%"
      xmlns="http://www.w3.org/2000/svg"
      @wheel="onWheel"
      @mousedown="startPan"
    >
      <g v-html="dimensionDefs(markerId)"></g>
      <rect :x="-10" :y="-10" :width="CANVAS_W + 20" :height="CANVAS_H + 20" fill="#ffffff"></rect>
      <!-- 中心线：目标齿（长点划线，限于齿形区内）+ 左齿中分线 -->
      <line
        :x1="centerX"
        :y1="TOOTH_TOP + 6"
        :x2="centerX"
        :y2="TOOTH_BOTTOM - 6"
        class="center-line"
        stroke="#4080C0"
        stroke-width="1"
        vector-effect="non-scaling-stroke"
        stroke-dasharray="16 4 2 4"
      ></line>
      <line
        :x1="leftCenterLine[0][0]"
        :y1="leftCenterLine[0][1]"
        :x2="leftCenterLine[1][0]"
        :y2="leftCenterLine[1][1]"
        class="left-center-line"
        stroke="#4080C0"
        stroke-width="1"
        vector-effect="non-scaling-stroke"
        stroke-dasharray="16 4 2 4"
      ></line>
      <!-- 齿顶圆：浅灰虚线（跨三齿） -->
      <path
        :d="tipCircleD"
        class="tip-circle"
        fill="none"
        :stroke="TIP_CIRCLE_COLOR"
        stroke-width="1"
        vector-effect="non-scaling-stroke"
        :stroke-dasharray="TIP_DASH"
      ></path>
      <!-- 分度线：连贯点画线（跨三齿一整条） -->
      <path
        :d="pitchLineD"
        class="pitch-line"
        fill="none"
        stroke="#7A8B99"
        stroke-width="1"
        vector-effect="non-scaling-stroke"
        :stroke-dasharray="PITCH_DASH"
      ></path>
      <!-- 主齿廓：neighborhood（连接三齿）或 目标+邻齿 -->
      <template v-if="hasNeighborhood">
        <path
          :d="mainPathD"
          class="profile-outline"
          fill="none"
          stroke="#1A2332"
          stroke-width="2"
          vector-effect="non-scaling-stroke"
        ></path>
      </template>
      <template v-else>
        <path
          :d="leftNeighborD"
          class="neighbor-outline"
          fill="none"
          stroke="#C4CCD4"
          stroke-width="1.2"
          vector-effect="non-scaling-stroke"
        ></path>
        <path
          :d="rightNeighborD"
          class="neighbor-outline"
          fill="none"
          stroke="#C4CCD4"
          stroke-width="1.2"
          vector-effect="non-scaling-stroke"
        ></path>
        <path
          :d="targetD"
          class="profile-outline"
          fill="none"
          stroke="#1A2332"
          stroke-width="2"
          vector-effect="non-scaling-stroke"
        ></path>
      </template>
      <!-- 标注 -->
      <g
        class="annotations"
        stroke="#0060A0"
        fill="#0060A0"
        font-size="10"
        font-family="sans-serif"
        stroke-width="1"
        vector-effect="non-scaling-stroke"
      >
        <g v-for="an in annotations" :key="an.role" class="annotation-g" :data-role="an.role">
          <line
            v-if="an.kind === 'line'"
            :x1="an.line!.x1"
            :y1="an.line!.y1"
            :x2="an.line!.x2"
            :y2="an.line!.y2"
            :marker-start="an.noArrows ? undefined : markerUrl"
            :marker-end="an.noArrows ? undefined : markerUrl"
          ></line>
          <path
            v-else
            :d="an.pathD"
            class="dim-arc"
            fill="none"
          ></path>
          <circle
            v-for="(d, i) in an.dots ?? []"
            :key="i"
            class="dim-dot"
            :cx="d[0]"
            :cy="d[1]"
            :r="DOT_R"
            fill="currentColor"
            stroke="none"
          ></circle>
          <text :x="an.textX" :y="an.textY" :text-anchor="an.textAnchor || 'middle'">{{ an.text }}</text>
        </g>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.tooth-profile {
  position: relative;
  width: 100%;
  height: 100%;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
}
.tooth-svg {
  display: block;
  cursor: grab;
}
.tooth-svg:active {
  cursor: grabbing;
}
.tooth-controls {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 3;
  display: flex;
  gap: 3px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--brand-border-light, #e4e9ef);
  border-radius: 6px;
  padding: 2px 4px;
}
.ctl-btn {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--brand-text, #1a2332);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
}
.ctl-btn:hover {
  background: rgba(0, 96, 160, 0.1);
  color: var(--brand-blue, #0060a0);
}
</style>
