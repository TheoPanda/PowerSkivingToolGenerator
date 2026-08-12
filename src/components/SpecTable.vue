<script setup lang="ts">
/**
 * SpecTable.vue — 齿轮规格表（只读）
 *
 * 按参数语义分组（基本参数/齿形系数/分度圆几何/直径/齿厚/齿高与圆角），而非输入/输出；
 * 行选中 + 复制按钮 → Tab 分隔文本（参数名\t值 每行）。
 * 表头 el-tooltip 解释参数定义/计算依据（内置静态词条，来源设计书第3章参数字典）。
 * 数值格式：单位 mm 保留 3 位、角度保留 1 位、无单位整型原样。
 */
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { ParamRow, ParamTableSpec } from '../api'

const props = defineProps<{
  params: ParamTableSpec
}>()

/** 静态词条表：key → 参数定义/计算依据（来源设计书第3章参数字典）. */
const TERMS: Record<string, string> = {
  m_n: '法向模数 mn（mm），标准模数系列值',
  z_w: '工件齿数 zw，齿数 ≥ 规定下限',
  alpha_n_deg: '法向压力角 αn（°），常用 20°',
  beta_w_deg: '螺旋角 βw（°），β=0 为直齿',
  x_w: '变位系数 xw（径向定位系数）',
  j_w: '旋向（+1 右旋 / -1 左旋，仅螺旋齿）',
  b_w: '齿宽 bw（mm）',
  k_io: '内外齿（1 外齿 / -1 内齿）',
  h_an: '顶高系数 ha*，齿顶高 = ha*·mn',
  c_n: '顶隙系数 c*，齿底高含顶隙',
  rho_f: '齿根圆角系数 ρ*f，齿根圆角半径 = ρ*f·mn',
  rho_tip: '齿顶倒圆系数 ρ*tip（缺项目，默认 0 锐角齿顶）',
  root_fillet: '齿根圆角开关（开 = 齿根圆角生效；关 = 锐齿根）',
  tooth_method: '齿厚方式（x_w 变位 / W_k 公法线 / M 跨棒距）',
  d_pw: '分度圆直径 dpw = 2·pitch_radius()',
  d_a: '齿顶圆直径 da = tip_diameter()',
  d_f: '齿根圆直径 df = root_diameter()',
  d_b: '基圆直径 db = 2·base_radius()',
  m_t: '端面模数 mt = mn / cosβw，由 to_transverse()',
  alpha_t_deg: '端面压力角 αt（°），由 to_transverse()',
  s_t: '端面分度圆弧齿厚 st = compute_tooth_thickness()（弧长）',
  s_n: '法向弧齿厚 sn = st·cosβw',
  s_t_chord: '分度圆弦齿厚 sc = 2·rpw·sin(st/(2·rpw))（两齿面直线距离）',
  s_n_chord: '法向弦齿厚 scn = sc·cosβw',
  p_t: '端面齿距 pt = π·mt',
  h_a: '齿顶高 ha = ha*·mn',
  h_f: '齿底高 hf = (ha*+c*)·mn',
  h: '齿全高 h = ha + hf',
  rho_f_actual: '齿根圆角半径 = ρ*f·mn',
  rho_tip_actual: '齿顶倒圆半径 = ρ*tip·mn',
  W_k: '公法线长度 Wk（mm）',
  k_teeth: '公法线跨齿数 k',
  M: '跨棒距 M（mm）',
  d_p: '量棒直径 dp（mm）',
  tip_mode: '齿顶处理（round 圆角 / chamfer 倒角 / none 锐角）',
  chamfer_tip: '齿顶倒角系数 c*_tip（tip_mode=chamfer 时生效）',
  chamfer_actual: '齿顶倒角实际尺寸 c*_tip·mn（C×45°）',
  d_rim: '齿圈外径（内齿轮环形实体外边界，有效值）',
}

/**
 * 规格表语义分组（按参数含义，而非输入/输出）。
 * 键集覆盖 backend/core/workpiece/spec.py 全量 inputs/outputs；未命中键落入「其他参数」兜底组。
 */
const GROUP_DEFS: ReadonlyArray<{ name: string; keys: ReadonlyArray<string> }> = [
  { name: '基本参数', keys: ['m_n', 'z_w', 'alpha_n_deg', 'beta_w_deg', 'j_w', 'k_io', 'b_w', 'x_w', 'tooth_method'] },
  { name: '齿形系数', keys: ['h_an', 'c_n', 'rho_f', 'rho_tip', 'root_fillet', 'tip_mode', 'chamfer_tip'] },
  { name: '分度圆几何', keys: ['d_pw', 'm_t', 'alpha_t_deg', 'p_t'] },
  { name: '直径', keys: ['d_a', 'd_f', 'd_b', 'd_rim'] },
  { name: '齿厚', keys: ['s_t', 's_n', 's_t_chord', 's_n_chord'] },
  { name: '齿高与圆角', keys: ['h_a', 'h_f', 'h', 'rho_f_actual', 'rho_tip_actual', 'chamfer_actual'] },
]
const FALLBACK_GROUP = '其他参数'

/** 行/选中 Key（参数 key 在 inputs/outputs 间唯一，可直接作选中标识）. */
type RowKey = string
const selectedKey = ref<RowKey | null>(null)

/** 当前选中行的参数名（用于复制）. */
function selectRow(row: RowLike): void {
  selectedKey.value = row.key
}
/** 布尔开关显示为「开/关」，数值原样字符串化. */
function valStr(value: number | boolean): string {
  if (typeof value === 'boolean') return value ? '开' : '关'
  return `${value}`
}
function fmt(value: number | boolean, unit: string): string {
  if (typeof value === 'boolean') return valStr(value)
  if (unit === '°') return `${value.toFixed(1)}°`
  if (unit === '' || unit === '—') return valStr(value)
  return `${value.toFixed(3)}${unit}`
}

interface RowLike {
  key: string
  label: string
  symbol: string
  value: number | boolean
  unit: string
}
const allRows = (): RowLike[] => [...props.params.inputs, ...props.params.outputs]

/** 按语义分组（GROUP_DEFS 顺序）；空组跳过；未命中键进「其他参数」兜底组，保证不丢参数. */
const groupedRows = computed<Array<{ name: string; rows: RowLike[] }>>(() => {
  const groups = GROUP_DEFS.map((g) => ({ name: g.name, rows: [] as RowLike[] }))
  const keyToGroup = new Map<string, number>()
  GROUP_DEFS.forEach((g, i) => g.keys.forEach((k) => keyToGroup.set(k, i)))
  const fallback: RowLike[] = []
  for (const r of allRows()) {
    const gi = keyToGroup.get(r.key)
    if (gi === undefined) fallback.push(r)
    else groups[gi].rows.push(r)
  }
  const out = groups.filter((g) => g.rows.length > 0)
  if (fallback.length > 0) out.push({ name: FALLBACK_GROUP, rows: fallback })
  return out
})

/** 复制选中行（Tab 分隔：参数名\t值 每行）. */
async function copySelected(): Promise<void> {
  const rows = allRows()
  const target = rows.find((r) => r.key === selectedKey.value)
  if (!target) {
    ElMessage.warning('请先选中一行')
    return
  }
  const text = `${target.symbol || target.label}\t${valStr(target.value)}`
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(`已复制 ${target.symbol || target.label}`)
  } catch {
    ElMessage.error('复制失败')
  }
}

/** 全表复制（参数名\t值 每行一次输出）— 规格书验收：复制按钮输出 Tab 分隔文本. */
async function copyAll(): Promise<void> {
  const lines = allRows().map((r) => `${r.symbol || r.label}\t${valStr(r.value)}`)
  const text = lines.join('\n')
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制全部参数')
  } catch {
    ElMessage.error('复制失败')
  }
}

function term(key: string): string {
  return TERMS[key] || key
}
</script>

<template>
  <div class="spec-table">
    <div class="spec-table-toolbar">
      <span class="spec-table-title">齿轮规格</span>
      <div class="spec-table-actions">
        <button class="glass-btn spec-copy-btn" @click="copyAll">复制全部</button>
        <button class="glass-btn spec-copy-btn" @click="copySelected">复制选中</button>
      </div>
    </div>

    <!-- 参数按语义分组展示（非输入/输出）；单表 + 组标题行 → 跨组列纵向对齐 -->
    <table class="spec-rows">
      <thead>
        <tr>
          <th class="th-sec"></th>
          <th class="th-sym">符号</th>
          <th class="th-name">名称</th>
          <th class="th-val">数值</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="group in groupedRows" :key="group.name">
          <tr class="spec-group-row">
            <td colspan="4" class="spec-group-title">{{ group.name }}</td>
          </tr>
          <tr
            v-for="r in group.rows"
            :key="r.key"
            :class="{ 'row-selected': selectedKey === r.key }"
            class="spec-row"
            @click="selectRow(r)"
          >
            <td class="td-sec"></td>
            <td class="td-sym">
              <el-tooltip :content="term(r.key)" placement="top">
                <span class="sym">{{ r.symbol || r.key }}</span>
              </el-tooltip>
            </td>
            <td class="td-name">{{ r.label }}</td>
            <td class="td-val">{{ fmt(r.value, r.unit) }}</td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.spec-table {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding: 4px;
  box-sizing: border-box;
}
.spec-table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.spec-table-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--brand-text, #1a2332);
}
.spec-table-actions {
  display: flex;
  gap: 6px;
}
.spec-copy-btn {
  padding: 5px 12px;
  font-size: 12px;
}
/* 组标题行（单表内 colspan 全宽；收敛为浅灰小节标签，醒目度让给列头） */
.spec-group-row td.spec-group-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--brand-text-secondary, #5c6b7a);
  padding: 8px 6px 4px;
  border-bottom: 1px solid var(--brand-border-light, #e4e9ef);
}
.spec-group-row:first-of-type td.spec-group-title {
  padding-top: 4px;
}
.spec-rows {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.spec-rows thead {
  color: var(--brand-blue, #0060a0);
}
.spec-rows th {
  text-align: left;
  font-weight: 600;
  padding: 3px 6px;
}
.spec-rows th.th-val {
  text-align: right; /* 「数值」表头与下方数值右对齐 */
}
/* 左侧留白列：组标题坐左栏，列头/数据靠右 → 组标题与列头错开 */
.spec-rows th.th-sec,
.spec-row td.td-sec {
  width: 80px;
}
.spec-row {
  cursor: pointer;
  color: var(--brand-text, #1a2332);
}
.spec-row:hover {
  background: rgba(0, 96, 160, 0.05);
}
.spec-row.row-selected {
  background: rgba(0, 96, 160, 0.12);
}
.spec-row td {
  padding: 3px 6px;
}
.td-sym .sym {
  font-family: 'Cambria Math', serif;
  color: var(--brand-blue, #0060a0);
}
.td-val {
  font-variant-numeric: tabular-nums;
  text-align: right;
  font-weight: 600;
}
</style>
