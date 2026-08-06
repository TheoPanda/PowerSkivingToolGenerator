/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

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
  }
}
