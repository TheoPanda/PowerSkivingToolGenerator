/// <reference types="vite/client" />
/**
 * env.d.ts — 渲染进程全局类型声明
 *
 * 覆盖三块：*.vue 模块声明、Vite import.meta.env 变量类型、window.electronAPI
 * （preload 暴露的受控 API，含齿轮规格跨 IPC 缝的类型化接口）。
 */
import type { SpecPayload } from './api/spec-types'

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

declare global {
  interface ImportMetaEnv {
    readonly VITE_BACKEND_URL: string
    readonly VITE_APP_TITLE: string
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv
  }

  interface Window {
    electronAPI?: {
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
  }
}

export {}
