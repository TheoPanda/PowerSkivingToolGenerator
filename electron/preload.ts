/**
 * Electron Preload 脚本
 * 通过 contextBridge 暴露受控 API 给渲染进程
 * 禁止直接暴露 Node.js API（如 fs）
 */

import { contextBridge, ipcRenderer } from 'electron'
import type { SpecPayload } from '../src/api/spec-types'

export interface ElectronAPI {
  openFileDialog: (options?: Record<string, unknown>) => Promise<string[] | null>
  saveFileDialog: (options?: Record<string, unknown>) => Promise<string | null>
  getPythonStatus: () => Promise<{ running: boolean }>
  minimizeWindow: () => Promise<void>
  maximizeWindow: () => Promise<void>
  closeWindow: () => Promise<void>
  expandWindow: () => Promise<void>
  isMaximized: () => Promise<boolean>
  onMaximizeChange: (callback: (maximized: boolean) => void) => void
  // 齿轮规格独立窗口（spec 跨 IPC 缝类型化，架构审查 C5）
  openSpecWindow: (spec: SpecPayload) => Promise<void>
  getSpecData: () => Promise<SpecPayload | null>
  onSpecData: (callback: (spec: SpecPayload) => void) => void
}

const electronAPI: ElectronAPI = {
  openFileDialog: (options?: Record<string, unknown>): Promise<string[] | null> => {
    return ipcRenderer.invoke('dialog:openFile', options)
  },

  saveFileDialog: (options?: Record<string, unknown>): Promise<string | null> => {
    return ipcRenderer.invoke('dialog:saveFile', options)
  },

  getPythonStatus: (): Promise<{ running: boolean }> => {
    return ipcRenderer.invoke('python:status')
  },

  minimizeWindow: (): Promise<void> => {
    return ipcRenderer.invoke('window:minimize')
  },

  maximizeWindow: (): Promise<void> => {
    return ipcRenderer.invoke('window:maximize')
  },

  closeWindow: (): Promise<void> => {
    return ipcRenderer.invoke('window:close')
  },

  expandWindow: (): Promise<void> => {
    return ipcRenderer.invoke('window:expand')
  },

  isMaximized: (): Promise<boolean> => {
    return ipcRenderer.invoke('window:isMaximized')
  },

  onMaximizeChange: (callback: (maximized: boolean) => void): void => {
    ipcRenderer.on('window:maximizeChange', (_event, maximized: boolean) => callback(maximized))
  },

  // 齿轮规格独立窗口
  openSpecWindow: (spec: SpecPayload): Promise<void> => {
    return ipcRenderer.invoke('spec:open', spec)
  },
  getSpecData: (): Promise<SpecPayload | null> => {
    return ipcRenderer.invoke('spec:getData')
  },
  onSpecData: (callback: (spec: SpecPayload) => void): void => {
    ipcRenderer.on('spec:data', (_event, spec: SpecPayload) => callback(spec))
  },
}

contextBridge.exposeInMainWorld('electronAPI', electronAPI)
