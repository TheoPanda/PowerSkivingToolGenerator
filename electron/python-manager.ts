/**
 * Python 进程管理器
 * 管理 FastAPI 后端的启动和关闭
 */

import { ChildProcess, spawn } from 'child_process'
import { join } from 'path'

export interface PythonStatus {
  running: boolean
  pid?: number
  port?: number
}

export class PythonManager {
  private process: ChildProcess | null = null
  private readonly port: number = 5199
  private readonly backendDir: string

  constructor() {
    // 开发模式：backend/ 在项目根目录
    // 生产模式：backend/ 在 extraResources 中
    const isDev: boolean = process.env.NODE_ENV !== 'production'
    this.backendDir = isDev
      ? join(__dirname, '..', 'backend')
      : join(process.resourcesPath, 'backend')
  }

  start(): void {
    if (this.process) {
      console.log('[PythonManager] 后端已在运行')
      return
    }

    const pythonCmd: string = process.platform === 'win32' ? 'conda' : 'python3'
    const pythonArgs: string[] =
      process.platform === 'win32'
        ? ['run', '-n', 'power-skiving', 'python', 'app.py']
        : ['app.py']

    console.log(`[PythonManager] 启动 Python 后端: ${pythonCmd} ${pythonArgs.join(' ')}`)

    this.process = spawn(pythonCmd, pythonArgs, {
      cwd: this.backendDir,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
      },
    })

    this.process.stdout?.on('data', (data: Buffer) => {
      console.log(`[Python] ${data.toString().trim()}`)
    })

    this.process.stderr?.on('data', (data: Buffer) => {
      console.error(`[Python Error] ${data.toString().trim()}`)
    })

    this.process.on('error', (err: Error) => {
      console.error(`[PythonManager] 启动失败: ${err.message}`)
    })

    this.process.on('exit', (code: number | null) => {
      console.log(`[PythonManager] 进程退出, code=${code}`)
      this.process = null
    })
  }

  stop(): void {
    if (!this.process) return

    console.log('[PythonManager] 关闭 Python 后端')
    if (process.platform === 'win32') {
      // Windows 上通过 taskkill 结束进程树
      spawn('taskkill', ['/pid', String(this.process.pid), '/f', '/t'])
    } else {
      this.process.kill('SIGTERM')
    }
    this.process = null
  }

  getStatus(): PythonStatus {
    return {
      running: this.process !== null,
      pid: this.process?.pid,
      port: this.port,
    }
  }
}
