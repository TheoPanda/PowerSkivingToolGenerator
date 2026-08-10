/**
 * SpecWindowRoot — 齿轮规格独立窗口根组件测试
 * 断言：等待态 → 收到 IPC spec:data 后渲染左图右表（单齿廓/整体轮廓/规格表）.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import SpecWindowRoot from './SpecWindowRoot.vue'
import type { SpecPayload } from '../api/spec-types'
import { mockSpec } from './__spec-mock'

let onSpecDataCb: ((spec: SpecPayload) => void) | null = null

describe('SpecWindowRoot — 独立规格窗口', () => {
  beforeEach(() => {
    onSpecDataCb = null
    vi.restoreAllMocks()
    const api = window.electronAPI!
    vi.mocked(api.getSpecData).mockResolvedValue(null)
    vi.mocked(api.onSpecData).mockImplementation((cb) => {
      onSpecDataCb = cb
    })
  })

  it('数据到达前显示等待态', async () => {
    const wrapper = mount(SpecWindowRoot)
    await nextTick()
    expect(wrapper.text()).toContain('等待齿轮规格数据')
    wrapper.unmount()
  })

  it('收到 spec 数据后渲染左图右表（单齿廓/整体轮廓/规格表）', async () => {
    const wrapper = mount(SpecWindowRoot)
    await nextTick()
    expect(onSpecDataCb).not.toBeNull()
    onSpecDataCb?.(mockSpec())
    await nextTick()
    await nextTick()
    expect(wrapper.text()).toContain('单齿廓')
    expect(wrapper.text()).toContain('整体轮廓')
    expect(wrapper.text()).toContain('法向模数')
    wrapper.unmount()
  })
})
