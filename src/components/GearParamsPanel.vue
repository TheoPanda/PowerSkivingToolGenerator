<script setup lang="ts">
import { ref, computed, inject, watch, type Ref } from 'vue'
import { gearParamsKey, type GearParams } from '../composables/useGearParams'

const emit = defineEmits<{
  (e: 'valid-change', isValid: boolean): void
}>()

const gearParams = inject(gearParamsKey)
if (!gearParams) {
  throw new Error('GearParamsPanel: 必须在 MainPanel 中使用 (provide gearParams)')
}

// ---- 折叠状态 ----
const expandedSections = ref({
  basic: true,
  tooth: true,
  advanced: false,
  decoration: false,
})

function toggleSection(section: 'basic' | 'tooth' | 'advanced' | 'decoration'): void {
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
    <!-- ① 基本 -->
    <div class="glass-collapse" :class="{ expanded: expandedSections.basic }">
      <button class="glass-collapse-header" @click="toggleSection('basic')">
        基本
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
            <input
              v-model.number="gearParams.β_w"
              type="number"
              step="0.5"
              min="0"
              max="45"
              class="glass-input"
              style="flex:1;"
            />
            <span style="font-size:10px;color:var(--brand-text-secondary);">°</span>
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

    <!-- ② 齿厚 -->
    <div class="glass-collapse" :class="{ expanded: expandedSections.tooth }">
      <button class="glass-collapse-header" @click="toggleSection('tooth')">
        齿厚
        <span class="glass-collapse-arrow">▶</span>
      </button>
      <div class="glass-collapse-content">
        <div class="collapse-inner">

          <!-- 齿厚方式选择（segmented） -->
          <div class="glass-field">
            <label class="glass-field-label">齿厚方式</label>
            <div class="glass-segmented">
              <button
                class="glass-segmented-btn"
                :class="{ active: gearParams.toothMethod === 'x_w' }"
                @click="gearParams.toothMethod = 'x_w'"
              >变位</button>
              <button
                class="glass-segmented-btn"
                :class="{ active: gearParams.toothMethod === 'W_k' }"
                @click="gearParams.toothMethod = 'W_k'"
              >公法线</button>
              <button
                class="glass-segmented-btn"
                :class="{ active: gearParams.toothMethod === 'M' }"
                @click="gearParams.toothMethod = 'M'"
              >跨棒距</button>
            </div>
          </div>

          <!-- 变位系数 -->
          <template v-if="gearParams.toothMethod === 'x_w'">
            <div class="glass-field">
              <label class="glass-field-label">变位系数 x_w</label>
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
            </div>
            <p v-if="errors.x_w" class="glass-field-hint" style="padding-left:98px;">{{ errors.x_w }}</p>
          </template>

          <!-- 公法线 -->
          <template v-if="gearParams.toothMethod === 'W_k'">
            <div class="glass-field">
              <label class="glass-field-label">公法线长度 W_k</label>
              <input
                v-model.number="gearParams.W_k"
                type="number"
                step="0.001"
                min="0.001"
                class="glass-input"
                :class="{ error: errors.W_k }"
                @blur="validateField('W_k')"
              />
            </div>
            <p v-if="errors.W_k" class="glass-field-hint" style="padding-left:98px;">{{ errors.W_k }}</p>
            <div class="glass-field">
              <label class="glass-field-label">跨齿数 k</label>
              <input
                v-model.number="gearParams.k_teeth"
                type="number"
                step="1"
                min="1"
                class="glass-input"
                :placeholder="kRecommended ? String(kRecommended) : '—'"
              />
              <span
                v-if="kRecommended"
                class="k-hint"
                @click="gearParams.k_teeth = kRecommended"
              >推荐 {{ kRecommended }}</span>
            </div>
          </template>

          <!-- 跨棒距 -->
          <template v-if="gearParams.toothMethod === 'M'">
            <div class="glass-field">
              <label class="glass-field-label">跨棒距 M</label>
              <input
                v-model.number="gearParams.M"
                type="number"
                step="0.001"
                min="0.001"
                class="glass-input"
                :class="{ error: errors.M }"
                @blur="validateField('M')"
              />
            </div>
            <p v-if="errors.M" class="glass-field-hint" style="padding-left:98px;">{{ errors.M }}</p>
            <div class="glass-field">
              <label class="glass-field-label">量棒径 d_p</label>
              <input
                v-model.number="gearParams.d_p"
                type="number"
                step="0.01"
                min="0.01"
                class="glass-input"
              />
            </div>
          </template>

        </div>
      </div>
    </div>

    <!-- ③ 高级 -->
    <div class="glass-collapse" :class="{ expanded: expandedSections.advanced }">
      <button class="glass-collapse-header" @click="toggleSection('advanced')">
        高级
        <span class="glass-collapse-arrow">▶</span>
      </button>
      <div class="glass-collapse-content">
        <div class="collapse-inner">

          <div class="glass-field">
            <label class="glass-field-label">压力角 α_n</label>
            <input v-model.number="gearParams.α_n" type="number" step="0.5" class="glass-input" />
            <span style="font-size:10px;color:var(--brand-text-secondary);">°</span>
          </div>

          <div class="glass-field">
            <label class="glass-field-label">齿顶高系数 h*_an</label>
            <input v-model.number="gearParams.h_an" type="number" step="0.05" class="glass-input" />
          </div>

          <div class="glass-field">
            <label class="glass-field-label">顶隙系数 c*_n</label>
            <input v-model.number="gearParams.c_n" type="number" step="0.05" class="glass-input" />
          </div>

        </div>
      </div>
    </div>

    <!-- ④ 齿顶/齿根修饰 -->
    <div class="glass-collapse" :class="{ expanded: expandedSections.decoration }">
      <button class="glass-collapse-header" @click="toggleSection('decoration')">
        齿顶/齿根修饰
        <span class="glass-collapse-arrow">▶</span>
      </button>
      <div class="glass-collapse-content">
        <div class="collapse-inner">

          <!-- 齿根圆角开关 -->
          <div class="glass-field">
            <label class="glass-field-label">齿根圆角</label>
            <input
              v-model="gearParams.root_fillet"
              type="checkbox"
              class="glass-checkbox"
            />
          </div>

          <!-- 齿根圆角系数（勾选时显示） -->
          <div v-if="gearParams.root_fillet" class="glass-field">
            <label class="glass-field-label">齿根圆角系数 ρ*_f</label>
            <input v-model.number="gearParams.ρ_f" type="number" step="0.01" class="glass-input" />
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
  gap: 8px;
}

.collapse-inner {
  padding: 4px 4px 4px 12px;
}

.k-hint {
  font-size: 10px;
  color: var(--brand-text-secondary);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}

.k-hint:hover {
  color: var(--brand-blue);
}

.glass-checkbox {
  accent-color: var(--brand-blue);
  width: 15px;
  height: 15px;
  cursor: pointer;
  flex-shrink: 0;
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
