<script setup lang="ts">
/**
 * SpecTable.vue — 齿轮规格表（只读）
 *
 * 分「输入参数 / 解算结果」两组；行选中 + 复制按钮 → Tab 分隔文本（参数名\t值 每行）。
 * 表头 el-tooltip 解释参数定义/计算依据（内置静态词条，来源设计书第3章参数字典）。
 * 数值格式：单位 mm 保留 3 位、角度保留 1 位、无单位整型原样。
 */
import { ref } from 'vue'
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
  tooth_method: '齿厚方式（x_w 变位 / W_k 公法线 / M 跨棒距）',
  d_pw: '分度圆直径 dpw = 2·pitch_radius()',
  d_a: '齿顶圆直径 da = tip_diameter()',
  d_f: '齿根圆直径 df = root_diameter()',
  d_b: '基圆直径 db = 2·base_radius()',
  m_t: '端面模数 mt = mn / cosβw，由 to_transverse()',
  alpha_t_deg: '端面压力角 αt（°），由 to_transverse()',
  s_t: '端面分度圆弧齿厚 st = compute_tooth_thickness()',
  s_n: '法向齿厚 sn = st·cosβw',
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
}

/** 行/选中 Key（组合输入与输出）. */
type RowKey = string
const selectedKey = ref<RowKey | null>(null)

/** 当前选中行的参数名（用于复制）. */
function selectRow(row: RowLike): void {
  selectedKey.value = rowKey(row)
}
function fmt(value: number, unit: string): string {
  if (unit === '°') return `${value.toFixed(1)}°`
  if (unit === '' || unit === '—') return `${value}`
  return `${value.toFixed(3)}${unit}`
}

interface RowLike {
  key: string
  label: string
  symbol: string
  value: number
  unit: string
  group: 'input' | 'output'
}
const allRows = (): RowLike[] => [
  ...props.params.inputs.map((r) => ({ ...r, group: 'input' as const })),
  ...props.params.outputs.map((r) => ({ ...r, group: 'output' as const })),
]

function rowKey(r: RowLike): RowKey {
  return `${r.group}:${r.key}`
}

/** 复制选中行（Tab 分隔：参数名\t值 每行）. */
async function copySelected(): Promise<void> {
  const rows = allRows()
  const target = rows.find((r) => rowKey(r) === selectedKey.value)
  if (!target) {
    ElMessage.warning('请先选中一行')
    return
  }
  const text = `${target.symbol || target.label}\t${target.value}`
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(`已复制 ${target.symbol || target.label}`)
  } catch {
    ElMessage.error('复制失败')
  }
}

/** 全表复制（参数名\t值 每行一次输出）— 规格书验收：复制按钮输出 Tab 分隔文本. */
async function copyAll(): Promise<void> {
  const lines = allRows().map((r) => `${r.symbol || r.label}\t${r.value}`)
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

    <!-- 输入参数 -->
    <div v-if="props.params.inputs.length" class="spec-group">
      <div class="spec-group-title">输入参数</div>
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
          <tr
            v-for="r in props.params.inputs"
            :key="rowKey({ ...r, group: 'input' })"
            :class="{ 'row-selected': selectedKey === rowKey({ ...r, group: 'input' }) }"
            class="spec-row"
            @click="selectRow({ ...r, group: 'input' })"
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
        </tbody>
      </table>
    </div>

    <!-- 解算结果 -->
    <div v-if="props.params.outputs.length" class="spec-group">
      <div class="spec-group-title">解算结果</div>
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
          <tr
            v-for="r in props.params.outputs"
            :key="rowKey({ ...r, group: 'output' })"
            :class="{ 'row-selected': selectedKey === rowKey({ ...r, group: 'output' }) }"
            class="spec-row"
            @click="selectRow({ ...r, group: 'output' })"
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
        </tbody>
      </table>
    </div>
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
.spec-group-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--brand-blue, #0060a0);
  padding-bottom: 4px;
  border-bottom: 1px solid var(--brand-border-light, #e4e9ef);
  margin-bottom: 4px;
}
.spec-rows {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.spec-rows thead {
  color: var(--brand-text-secondary, #5c6b7a);
}
.spec-rows th {
  text-align: left;
  font-weight: 500;
  padding: 3px 6px;
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
