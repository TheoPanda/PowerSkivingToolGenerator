<script setup lang="ts">
import { ref, computed, inject, watch, type Ref } from 'vue'

// ---- 类型 ----
interface GearParams {
  profile_type: string
  k_io: number
  m_n: number | null
  z_w: number | null
  β_w: number
  j_w: number
  b_w: number | null
  toothMethod: string
  x_w: number
  W_k: number | null
  k_teeth: number | null
  M: number | null
  d_p: number | null
  α_n: number
  h_an: number
  c_n: number
  ρ_f: number
}

const emit = defineEmits<{
  (e: 'valid-change', isValid: boolean): void
}>()

const gearParams = inject<GearParams>('gearParams')
if (!gearParams) {
  throw new Error('GearParamsPanel: 必须在 MainPanel 中使用 (provide gearParams)')
}

// ---- 折叠状态 ----
const expandedSections = ref({
  basic: true,
  tooth: true,
  advanced: false,
})

function toggleSection(section: 'basic' | 'tooth' | 'advanced'): void {
  expandedSections.value[section] = !expandedSections.value[section]
}

// ---- 齿形类型选项 ----
const profileOptions = [
  { value: 'involute', label: '渐开线', disabled: false },
  { value: 'arc', label: '圆弧', disabled: true },
  { value: 'cycloid', label: '摆线', disabled: true },
  { value: 'modified', label: '修形', disabled: true },
  { value: 'pointcloud', label: 'CAD 点云', disabled: true },
]

// ---- 跨齿数 k 自动推荐 ----
const kRecommended = ref<number | null>(null)

function calcK(): void {
  const z = gearParams!.z_w
  const β = gearParams!.β_w
  const α_n = gearParams!.α_n
  if (!z || z < 1) { kRecommended.value = null; return }

  const βRad = (β * Math.PI) / 180
  const α_nRad = (α_n * Math.PI) / 180
  const α_t = Math.atan(Math.tan(α_nRad) / Math.cos(βRad))
  const α_tDeg = (α_t * 180) / Math.PI

  kRecommended.value = Math.round(z * α_tDeg / 180 + 0.5)
}

watch(
  () => [gearParams!.α_n, gearParams!.β_w, gearParams!.z_w],
  () => { if (gearParams!.toothMethod === 'W_k') calcK() },
  { immediate: true },
)

watch(
  () => gearParams!.toothMethod,
  (m) => { if (m === 'W_k') calcK() },
)

// ---- 校验 ----
const isValid = computed<boolean>(() => {
  const p = gearParams!
  if (!p.m_n || p.m_n <= 0) return false
  if (!p.z_w || p.z_w < 1 || !Number.isInteger(p.z_w)) return false
  if (!p.b_w || p.b_w <= 0) return false

  if (p.toothMethod === 'x_w') {
    if (p.x_w < -1 || p.x_w > 1) return false
  } else if (p.toothMethod === 'W_k') {
    if (!p.W_k || p.W_k <= 0) return false
    if (!p.k_teeth || p.k_teeth < 1) return false
  } else if (p.toothMethod === 'M') {
    if (!p.M || p.M <= 0) return false
    if (!p.d_p || p.d_p <= 0) return false
  }

  return true
})

watch(isValid, (v) => emit('valid-change', v), { immediate: true })

// ---- 字段级校验 ----
const errors = ref<Record<string, string>>({})

function validateField(field: string): void {
  const p = gearParams!
  switch (field) {
    case 'm_n':
      if (!p.m_n || p.m_n <= 0) errors.value.m_n = '模数必须大于 0'
      else delete errors.value.m_n
      break
    case 'z_w':
      if (!p.z_w || p.z_w < 1 || !Number.isInteger(p.z_w)) errors.value.z_w = '齿数必须为正整数'
      else delete errors.value.z_w
      break
    case 'b_w':
      if (!p.b_w || p.b_w <= 0) errors.value.b_w = '齿宽必须大于 0'
      else delete errors.value.b_w
      break
    case 'W_k':
      if (gearParams!.toothMethod === 'W_k' && (!p.W_k || p.W_k <= 0))
        errors.value.W_k = '公法线长度必须大于 0'
      else delete errors.value.W_k
      break
    case 'M':
      if (gearParams!.toothMethod === 'M' && (!p.M || p.M <= 0))
        errors.value.M = '跨棒距必须大于 0'
      else delete errors.value.M
      break
    case 'x_w':
      if (p.x_w < -1 || p.x_w > 1)
        errors.value.x_w = '变位系数应在 [-1, 1] 范围'
      else delete errors.value.x_w
      break
  }
}

// 暴露给测试
defineExpose({ expandedSections, kRecommended, isValid, toggleSection })
</script>

<template>
  <div class="gear-params-panel">
    <!-- ① 基本参数 -->
    <div class="glass-collapse" :class="{ expanded: expandedSections.basic }">
      <button class="glass-collapse-header" @click="toggleSection('basic')">
        基本参数
        <span class="glass-collapse-arrow">▶</span>
      </button>
      <div class="glass-collapse-content">
        <div class="collapse-inner">

          <!-- 齿形类型 -->
          <div class="glass-field">
            <label class="glass-field-label">齿形类型</label>
            <select v-model="gearParams.profile_type" class="glass-select">
              <option
                v-for="opt in profileOptions"
                :key="opt.value"
                :value="opt.value"
                :disabled="opt.disabled"
              >
                {{ opt.label }}{{ opt.disabled ? ' (即将支持)' : '' }}
              </option>
            </select>
          </div>

          <!-- 内/外齿 -->
          <div class="glass-field">
            <label class="glass-field-label">内/外齿</label>
            <div class="glass-segmented">
              <button
                class="glass-segmented-btn"
                :class="{ active: gearParams.k_io === 1 }"
                @click="gearParams.k_io = 1"
              >
                外齿
              </button>
              <button
                class="glass-segmented-btn"
                :class="{ active: gearParams.k_io === -1 }"
                @click="gearParams.k_io = -1"
              >
                内齿
              </button>
            </div>
          </div>

          <!-- 法向模数 -->
          <div class="glass-field">
            <label class="glass-field-label">法向模数 mₙ <span style="color:var(--brand-danger)">*</span></label>
            <input
              v-model.number="gearParams.m_n"
              type="number"
              step="0.1"
              min="0.01"
              class="glass-input"
              :class="{ error: errors.m_n }"
              placeholder="例：2"
              @blur="validateField('m_n')"
            />
            <p v-if="errors.m_n" class="glass-field-hint">{{ errors.m_n }}</p>
          </div>

          <!-- 工件齿数 -->
          <div class="glass-field">
            <label class="glass-field-label">工件齿数 z_w <span style="color:var(--brand-danger)">*</span></label>
            <input
              v-model.number="gearParams.z_w"
              type="number"
              step="1"
              min="1"
              class="glass-input"
              :class="{ error: errors.z_w }"
              placeholder="例：82"
              @blur="validateField('z_w')"
            />
            <p v-if="errors.z_w" class="glass-field-hint">{{ errors.z_w }}</p>
          </div>

          <!-- 螺旋角 -->
          <div class="glass-field">
            <label class="glass-field-label">螺旋角 β_w</label>
            <div style="display:flex;align-items:center;gap:8px;">
              <input
                type="range"
                class="glass-slider"
                :value="gearParams.β_w"
                min="0"
                max="45"
                step="0.5"
                style="flex:1;"
                @input="gearParams.β_w = parseFloat(($event.target as HTMLInputElement).value)"
              />
              <input
                v-model.number="gearParams.β_w"
                type="number"
                step="0.5"
                min="0"
                max="45"
                class="glass-input"
                style="width:58px;text-align:center;"
              />
              <span style="font-size:11px;color:var(--brand-text-secondary);">°</span>
            </div>
          </div>

          <!-- 旋向（条件显示） -->
          <div v-if="gearParams.β_w > 0" class="glass-field">
            <label class="glass-field-label">旋向 j_w</label>
            <div class="glass-segmented">
              <button
                class="glass-segmented-btn"
                :class="{ active: gearParams.j_w === 1 }"
                @click="gearParams.j_w = 1"
              >
                右旋
              </button>
              <button
                class="glass-segmented-btn"
                :class="{ active: gearParams.j_w === -1 }"
                @click="gearParams.j_w = -1"
              >
                左旋
              </button>
            </div>
          </div>

          <!-- 齿宽 -->
          <div class="glass-field">
            <label class="glass-field-label">齿宽 b_w <span style="color:var(--brand-danger)">*</span></label>
            <input
              v-model.number="gearParams.b_w"
              type="number"
              step="0.1"
              min="0.01"
              class="glass-input"
              :class="{ error: errors.b_w }"
              placeholder="例：20"
              @blur="validateField('b_w')"
            />
            <p v-if="errors.b_w" class="glass-field-hint">{{ errors.b_w }}</p>
          </div>

        </div>
      </div>
    </div>

    <!-- ② 齿厚指定 -->
    <div class="glass-collapse" :class="{ expanded: expandedSections.tooth }">
      <button class="glass-collapse-header" @click="toggleSection('tooth')">
        齿厚指定
        <span class="glass-collapse-arrow">▶</span>
      </button>
      <div class="glass-collapse-content">
        <div class="collapse-inner">

          <div class="glass-radio-group">
            <label class="glass-radio">
              <input type="radio" value="x_w" v-model="gearParams.toothMethod" />
              变位系数 x_w
            </label>

            <template v-if="gearParams.toothMethod === 'x_w'">
              <div class="glass-field" style="margin-left:22px;">
                <input
                  v-model.number="gearParams.x_w"
                  type="number"
                  step="0.01"
                  min="-1"
                  max="1"
                  class="glass-input"
                  :class="{ error: errors.x_w }"
                  @blur="validateField('x_w')"
                />
                <p v-if="errors.x_w" class="glass-field-hint">{{ errors.x_w }}</p>
              </div>
            </template>

            <label class="glass-radio">
              <input type="radio" value="W_k" v-model="gearParams.toothMethod" />
              公法线长度 W_k
            </label>

            <template v-if="gearParams.toothMethod === 'W_k'">
              <div class="glass-field" style="margin-left:22px;">
                <input
                  v-model.number="gearParams.W_k"
                  type="number"
                  step="0.001"
                  min="0.001"
                  class="glass-input"
                  :class="{ error: errors.W_k }"
                  placeholder="W_k (mm)"
                  @blur="validateField('W_k')"
                />
                <p v-if="errors.W_k" class="glass-field-hint">{{ errors.W_k }}</p>

                <div style="display:flex;align-items:center;gap:6px;margin-top:6px;">
                  <label class="glass-field-label" style="margin-bottom:0;">跨齿数 k</label>
                  <input
                    v-model.number="gearParams.k_teeth"
                    type="number"
                    step="1"
                    min="1"
                    class="glass-input"
                    style="width:60px;text-align:center;"
                    :placeholder="kRecommended ? String(kRecommended) : '—'"
                  />
                  <span
                    v-if="kRecommended"
                    style="font-size:10px;color:var(--brand-text-secondary);cursor:pointer;white-space:nowrap;"
                    @click="gearParams.k_teeth = kRecommended"
                  >
                    推荐 {{ kRecommended }}
                  </span>
                </div>
              </div>
            </template>

            <label class="glass-radio">
              <input type="radio" value="M" v-model="gearParams.toothMethod" />
              跨棒距 M
            </label>

            <template v-if="gearParams.toothMethod === 'M'">
              <div class="glass-field" style="margin-left:22px;">
                <input
                  v-model.number="gearParams.M"
                  type="number"
                  step="0.001"
                  min="0.001"
                  class="glass-input"
                  :class="{ error: errors.M }"
                  placeholder="M (mm)"
                  @blur="validateField('M')"
                />
                <p v-if="errors.M" class="glass-field-hint">{{ errors.M }}</p>

                <div style="margin-top:6px;">
                  <label class="glass-field-label">量棒径 d_p</label>
                  <input
                    v-model.number="gearParams.d_p"
                    type="number"
                    step="0.01"
                    min="0.01"
                    class="glass-input"
                    placeholder="例：1.68·m_t"
                  />
                </div>
              </div>
            </template>
          </div>

        </div>
      </div>
    </div>

    <!-- ③ 高级默认值 -->
    <div class="glass-collapse" :class="{ expanded: expandedSections.advanced }">
      <button class="glass-collapse-header" @click="toggleSection('advanced')">
        高级默认值
        <span class="glass-collapse-arrow">▶</span>
      </button>
      <div class="glass-collapse-content">
        <div class="collapse-inner">

          <div class="glass-field">
            <label class="glass-field-label">法向压力角 α_n</label>
            <input
              v-model.number="gearParams.α_n"
              type="number"
              step="0.5"
              class="glass-input"
            />
          </div>

          <div class="glass-field">
            <label class="glass-field-label">齿顶高系数 h*_an</label>
            <input
              v-model.number="gearParams.h_an"
              type="number"
              step="0.05"
              class="glass-input"
            />
          </div>

          <div class="glass-field">
            <label class="glass-field-label">顶隙系数 c*_n</label>
            <input
              v-model.number="gearParams.c_n"
              type="number"
              step="0.05"
              class="glass-input"
            />
          </div>

          <div class="glass-field">
            <label class="glass-field-label">齿根圆角半径系数 ρ*_f</label>
            <input
              v-model.number="gearParams.ρ_f"
              type="number"
              step="0.01"
              class="glass-input"
            />
          </div>

        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gear-params-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.collapse-inner {
  padding: 8px 4px 8px 10px;
}

.glass-collapse-content {
  overflow: hidden;
  max-height: 0;
  opacity: 0;
  transition:
    max-height 0.3s cubic-bezier(0.22, 0.61, 0.36, 1),
    opacity 0.25s ease;
}

.glass-collapse.expanded .glass-collapse-content {
  max-height: 800px;
  opacity: 1;
}
</style>
