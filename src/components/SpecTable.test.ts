/**
 * SpecTable — 单元测试
 * 断言：行数（输入 + 输出）、行点击选中、「复制全部」输出 Tab 分隔文本（参数名\t值 每行）.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import SpecTable from './SpecTable.vue'
import { mockSpec } from './__spec-mock'

function mountTable(): VueWrapper {
  return mount(SpecTable, {
    props: { params: mockSpec().params },
  })
}

describe('SpecTable', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    ;(navigator as unknown as { clipboard?: { writeText: (t: string) => Promise<void> } }).clipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    }
  })

  it('渲染输入 + 输出两组，行数等于 spec 行数', () => {
    const spec = mockSpec()
    const wrapper = mountTable()
    const inputRows = spec.params.inputs.length
    const outputRows = spec.params.outputs.length
    const total = wrapper.findAll('.spec-rows tbody tr.spec-row').length
    expect(total).toBe(inputRows + outputRows)
    // 两组标题
    expect(wrapper.text()).toContain('输入参数')
    expect(wrapper.text()).toContain('解算结果')
  })

  it('点击行 → 选中态高亮', async () => {
    const wrapper = mountTable()
    const firstRow = wrapper.find('.spec-row')
    await firstRow.trigger('click')
    await nextTick()
    expect(wrapper.find('.row-selected').exists()).toBe(true)
  })

  it('「复制选中」输出 Tab 分隔文本', async () => {
    const wrapper = mountTable()
    const firstRow = wrapper.find('.spec-row')
    await firstRow.trigger('click')
    await nextTick()
    const copySelected = wrapper.findAll('.spec-copy-btn').find((b) => b.text().includes('复制选中'))
    await copySelected!.trigger('click')
    const writeText = (navigator.clipboard?.writeText as unknown as ReturnType<typeof vi.fn>)!
    const lastArg: string = writeText.mock.calls[writeText.mock.calls.length - 1][0]
    // 参数名\t值
    expect(lastArg).toContain('\t')
    const [name, value] = lastArg.split('\t')
    expect(name.length).toBeGreaterThan(0)
    expect(value).toMatch(/^-?\d/)
  })

  it('「复制全部」输出每行「参数名\t值」Tab 分隔', async () => {
    const spec = mockSpec()
    const wrapper = mountTable()
    const copyAll = wrapper.findAll('.spec-copy-btn').find((b) => b.text().includes('复制全部'))
    await copyAll!.trigger('click')
    const writeText = (navigator.clipboard?.writeText as unknown as ReturnType<typeof vi.fn>)!
    const text: string = writeText.mock.calls[writeText.mock.calls.length - 1][0]
    const lines = text.split('\n')
    const totalRows = spec.params.inputs.length + spec.params.outputs.length
    expect(lines.length).toBe(totalRows)
    for (const line of lines) {
      expect(line).toContain('\t')
      expect(line.split('\t').length).toBe(2)
    }
  })
})
