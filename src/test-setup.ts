/**
 * vitest setup — 为所有测试提供全局 mock
 */
import { vi } from 'vitest'

// jsdom 无 Electron API —— 全局 mock，避免组件因 window.electronAPI 缺失报错
if (!window.electronAPI) {
  ;(window as unknown as { electronAPI: Record<string, unknown> }).electronAPI = {
    openFileDialog: vi.fn(),
    saveFileDialog: vi.fn(),
    getPythonStatus: vi.fn(),
    minimizeWindow: vi.fn(),
    maximizeWindow: vi.fn(),
    closeWindow: vi.fn(),
    expandWindow: vi.fn(),
    isMaximized: vi.fn(),
    onMaximizeChange: vi.fn(),
    // 齿轮规格独立窗口
    openSpecWindow: vi.fn(),
    closeSpecWindow: vi.fn(),
    getSpecData: vi.fn(),
    onSpecData: vi.fn(),
  }
}
