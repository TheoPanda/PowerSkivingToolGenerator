/**
 * Electron 主进程
 * 管理窗口创建、Python 后端生命周期、IPC 通信
 */

import { app, BrowserWindow, ipcMain, dialog } from 'electron'
import { join } from 'path'
import type { SpecPayload } from '../src/api/spec-types'
import { PythonManager } from './python-manager'

// 开发模式判断
const isDev: boolean = process.env.NODE_ENV !== 'production'
// 禁用 nodeIntegration，仅通过 preload 暴露受控 API
const preloadPath: string = join(__dirname, 'preload.js')

let mainWindow: BrowserWindow | null = null
let pythonManager: PythonManager | null = null

// 齿轮规格独立窗口（单独 BrowserWindow，非 DOM 覆盖层）
let specWindow: BrowserWindow | null = null
let pendingSpec: SpecPayload | null = null

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 650,
    title: '车齿刀参数化设计工具',
    frame: false,                    // 隐藏原生窗口边框，自绘标题栏
    webPreferences: {
      preload: preloadPath,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  if (isDev) {
    // 开发模式：加载 Vite 开发服务器
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    // 生产模式：加载打包后的文件
    mainWindow.loadFile(join(__dirname, '../dist/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
    specWindow?.close()
  })

  // 最大化/还原状态变化 → 通知渲染进程更新按钮图标
  mainWindow.on('maximize', () => mainWindow?.webContents.send('window:maximizeChange', true))
  mainWindow.on('unmaximize', () => mainWindow?.webContents.send('window:maximizeChange', false))
}

/**
 * 打开/聚焦齿轮规格独立窗口，并把 spec 数据推给它.
 * 窗口加载完成后经 did-finish-load 发送 spec:data；已打开则聚焦并直接重发.
 *
 * 关闭后重开的健壮性：
 *  - 窗口处于「关闭中」但 isDestroyed() 尚未为 true 时，仍按存活处理会占用引用 → 用本地
 *    win 引用 + closed 时仅当仍是当前窗口才清空，避免残留濒死引用导致后续无法重建。
 *  - 已销毁的窗口引用显式置 null 后重建。
 */
function openSpecWindow(spec: SpecPayload): void {
  pendingSpec = spec
  if (specWindow) {
    if (!specWindow.isDestroyed() && !specWindow.webContents.isDestroyed()) {
      if (specWindow.isMinimized()) specWindow.restore()
      specWindow.focus()
      try {
        specWindow.webContents.send('spec:data', spec)
      } catch {
        /* 窗口正在关闭，忽略发送失败 */
      }
      return
    }
    specWindow = null
  }
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 900,
    minHeight: 620,
    title: '齿轮规格',
    parent: mainWindow ?? undefined,
    autoHideMenuBar: true, // 默认不显示 File 等菜单栏
    frame: false,          // 自绘标题栏（软件 logo，而非 Electron 默认图标），与主窗口一致
    webPreferences: {
      preload: preloadPath,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })
  // 彻底移除本窗口的菜单栏
  win.removeMenu()
  specWindow = win
  // close（关闭开始）即清引用，避免「关闭中」点击按钮时仍命中聚焦分支而不重建窗口
  win.on('close', () => {
    if (specWindow === win) specWindow = null
  })
  win.on('closed', () => {
    if (specWindow === win) specWindow = null
  })
  win.on('show', () => win.focus())
  if (isDev) {
    win.loadURL('http://localhost:5173/spec.html')
  } else {
    win.loadFile(join(__dirname, '../dist/spec.html'))
  }
  win.webContents.once('did-finish-load', () => {
    if (!win.isDestroyed()) win.webContents.send('spec:data', pendingSpec)
  })
}

// IPC: 文件对话框
ipcMain.handle('dialog:openFile', async (_event, options) => {
  if (!mainWindow) return null
  const result = await dialog.showOpenDialog(mainWindow, options)
  return result.canceled ? null : result.filePaths
})

ipcMain.handle('dialog:saveFile', async (_event, options) => {
  if (!mainWindow) return null
  const result = await dialog.showSaveDialog(mainWindow, options)
  return result.canceled ? null : result.filePath
})

// IPC: 齿轮规格独立窗口
ipcMain.handle('spec:open', (_event, spec: SpecPayload) => {
  openSpecWindow(spec)
})
ipcMain.handle('spec:getData', () => pendingSpec)
ipcMain.handle('spec:close', () => {
  specWindow?.close()
})

// IPC: 窗口动态扩展——主进程逐帧响应
ipcMain.handle('window:expand', async () => {
  if (!mainWindow) return
  const targetW = 1400, targetH = 900
  const [cx, cy] = mainWindow.getPosition()
  const [cw, ch] = mainWindow.getSize()
  const startTime = Date.now()
  const duration = 550

  return new Promise<void>((resolve) => {
    let lastUpdate = 0
    function step(): void {
      const now = Date.now()
      if (now - lastUpdate < 6) {  // 上限 ~160fps，防止过度调用
        setImmediate(step)
        return
      }
      lastUpdate = now
      const elapsed = now - startTime
      const t = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3)
      const w = Math.round(cw + (targetW - cw) * eased)
      const h = Math.round(ch + (targetH - ch) * eased)
      mainWindow?.setBounds({ x: cx, y: cy, width: w, height: h }, false)
      if (t < 1) {
        setImmediate(step)
      } else {
        mainWindow?.center()
        resolve()
      }
    }
    step()
  })
})

// IPC: 窗口控制（自绘标题栏）
ipcMain.handle('window:minimize', () => mainWindow?.minimize())
ipcMain.handle('window:maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize()
  } else {
    mainWindow?.maximize()
  }
})
ipcMain.handle('window:close', () => mainWindow?.close())
ipcMain.handle('window:isMaximized', () => mainWindow?.isMaximized() ?? false)

// IPC: Python 后端状态
ipcMain.handle('python:status', async () => {
  return pythonManager?.getStatus() || { running: false }
})

app.whenReady().then(() => {
  // 启动 Python 后端
  pythonManager = new PythonManager()
  pythonManager.start()

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  // 关闭 Python 后端
  if (pythonManager) {
    pythonManager.stop()
  }
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  if (pythonManager) {
    pythonManager.stop()
  }
})
