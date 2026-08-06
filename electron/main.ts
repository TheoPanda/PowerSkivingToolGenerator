/**
 * Electron 主进程
 * 管理窗口创建、Python 后端生命周期、IPC 通信
 */

import { app, BrowserWindow, ipcMain, dialog } from 'electron'
import { join } from 'path'
import { PythonManager } from './python-manager'

// 开发模式判断
const isDev: boolean = process.env.NODE_ENV !== 'production'
// 禁用 nodeIntegration，仅通过 preload 暴露受控 API
const preloadPath: string = join(__dirname, 'preload.js')

let mainWindow: BrowserWindow | null = null
let pythonManager: PythonManager | null = null

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
  })

  // 最大化/还原状态变化 → 通知渲染进程更新按钮图标
  mainWindow.on('maximize', () => mainWindow?.webContents.send('window:maximizeChange', true))
  mainWindow.on('unmaximize', () => mainWindow?.webContents.send('window:maximizeChange', false))
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
