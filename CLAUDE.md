# CLAUDE.md

车齿刀参数化设计与 3D 可视化桌面应用。用户输入齿轮参数 → Python/OCCT 计算刀具几何体 → glTF 通过 Three.js 渲染。

## 技术栈

| 层级 | 技术 |
|-------|-----------|
| 桌面框架 | Electron |
| 前端 | Vue 3 (Composition API + `<script setup>`)，TypeScript 严格模式，Vite |
| 3D 渲染 | Three.js，OrbitControls |
| UI 组件库 | Element Plus |
| 后端 | Python 3.14+，FastAPI，conda env `power-skiving` |
| 几何内核 | OpenCASCADE (OCCT)，通过 OCP 调用 |

## 架构

```
渲染进程 (Vue/Three.js)
    ↕ HTTP（主要方式，禁止 fs）
Python 后端 (FastAPI + OCCT)
    ↕ child_process
Electron 主进程
    ↕ IPC (preload.js)
渲染进程 (文件对话框、系统 API)
```

- `nodeIntegration: false`，preload.js 暴露受控 API
- 上下文细节见 `src/CLAUDE.md`（前端）和 `backend/CLAUDE.md`（后端）

## 关键约束

- 环境变量通过 Vite `import.meta.env.VITE_...` 管理，严禁硬编码 IP/端口
- TypeScript 函数必须显式类型标注
- 后端 CORS + JSON 错误格式：`{ "error": "描述", "code": 400 }`
- 模型传输仅用 glTF/GLB
- 所有异步 `async/await` + `try/catch`

## 上游权威源：车齿刀设计书

只读引用，禁止本地修改。与项目冲突时以设计书为准。

根路径：`E:/OneDrive/Claude_Word/PowerSkivingDoc/reports/车齿刀设计书/`

| 章节 | 用途 |
|------|------|
| 第1章 设计链与数据流 | 六模块架构、输入/输出向量 |
| 第2章 坐标系与符号约定 | U1-U13 统一约定、K-0.x 变换库 |
| 第3章 参数字典 | 全部参数交互方式、范围、来源 |
| 第4章 算法模块 | K-1.x~K-6.x 公式组、伪代码、失效模式 |
| 第6章 两个算例 | 算例1（解析）、算例2（离散）完整数值 |
| 第7章 验收基准表 | 模块×判据×文献值×容差 |
| 第8章 缺口清单 | T1-T13/W1-W15 — 未销项禁止当已验证公式用 |
| testdata/ | JSON 回归基准，输出偏离 > 容差即失败 |

## 命令

```bash
npm install && cd backend && pip install -r requirements.txt
npm run dev       # 开发模式
npm run build     # 生产构建
npm test          # 运行测试 (Vitest)
npm run typecheck # 类型检查
```

## Agent skills

GitHub Issues（`gh` CLI），triage 标签见 `docs/agents/triage-labels.md`。

所有对话采用中文。
