# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 项目概述

**车齿刀**参数化设计与 3D 可视化桌面应用。用户输入齿轮参数 → Python/OCCT 计算刀具几何体 → glTF 模型通过 Three.js 渲染。

## 技术栈

| 层级 | 技术 |
|-------|-----------|
| 桌面框架 | Electron (最新版) |
| 前端 | Vue 3 (Composition API + `<script setup>`)，TypeScript 严格模式，Vite |
| 3D 渲染 | Three.js |
| UI 组件库 | Element Plus |
| 后端 | Python 3.13+，Flask 或 FastAPI |
| 几何内核 | OpenCASCADE (OCCT)，通过 `pythonocc-core` 调用 |
| 模型格式 | glTF/GLB |

## 架构与通信

```
渲染进程 (Vue/Three.js)
    ↕ HTTP（主要方式）
Python 后端 (Flask/FastAPI + OCCT)
    ↕ child_process
Electron 主进程
    ↕ IPC (preload.js)
渲染进程 (文件对话框、系统 API)
```

- **HTTP 优先**——前后端通信统一使用 HTTP，渲染进程中禁止使用 `fs`，以便未来迁移至 Web 端。
- **IPC 仅用于**原生 OS 功能（文件对话框、通过主进程读写文件）。
- 渲染进程设置 **`nodeIntegration: false`**；通过 `preload.js` 暴露受控 API。
- Python 进程生命周期由 Electron 主进程管理（`python-manager.js`）。

## 目录结构（目标）

```
my-skiving-tool/
├── .env.development          # Vite 开发环境变量
├── .env.production           # Vite 生产环境变量
├── electron/
│   ├── main.js
│   ├── preload.js
│   └── python-manager.js
├── src/
│   ├── api/                  # 后端 HTTP 请求封装
│   ├── assets/
│   ├── components/
│   │   ├── ToolParams.vue    # 参数输入表单
│   │   └── ModelViewer.vue   # Three.js 3D 视图
│   ├── App.vue
│   └── main.ts
├── backend/
│   ├── app.py                # Flask/FastAPI 入口
│   ├── requirements.txt
│   └── core/                 # OCCT 几何计算
├── package.json
└── vite.config.ts
```

## 关键约束

- **严禁硬编码 IP 或端口**——通过 Vite 环境变量 `import.meta.env.VITE_...` 管理。
- 所有 TypeScript 函数必须显式定义参数和返回值类型。
- 后端必须开启 CORS（`flask-cors` 或 FastAPI 等价配置）。
- 后端返回标准 JSON 错误格式：`{ "error": "描述", "code": 400 }`。
- 前后端之间仅使用 glTF/GLB 作为模型传输格式。
- 避免在 Three.js 渲染循环中创建几何体；注意资源显式释放。
- 所有异步操作统一使用 `async/await` + `try/catch`。

## 上游权威源：车齿刀设计书（只读引用，禁止本地修改）

所有数学公式、符号约定、模块 I/O 契约以设计书为**唯一依据**。本项目和设计书如有冲突，以设计书为准，并在设计书项目侧修正（不要在本项目内私改公式）。

设计书根路径：`E:/OneDrive/Claude_Word/PowerSkivingDoc`

| 源 | 路径 | 开发用途 |
|---|------|---------|
| 设计书（9 章） | `E:/OneDrive/Claude_Word/PowerSkivingDoc/reports/车齿刀设计书/` | 公式 K-N.M、模块 I/O 契约（数据结构级）、统一约定 U1-U13、冲突表 C1-Cx、失效模式、验收阈值 |
| 第1章 设计链与数据流 | `…/第1章_总体设计链与数据流.md` | 六模块架构、输入/输出向量、用户输入引导汇总 |
| 第2章 坐标系与符号约定 | `…/第2章_统一坐标系与符号约定.md` | U1-U13 统一约定（内核唯一依据）、K-0.x 基础变换库、文献冲突表 |
| 第3章 参数字典 | `…/第3章_参数字典.md` | 全部参数的交互方式（必填/可默认/导出）、典型范围、文献来源 |
| 第4章 算法模块 | `…/第4章_算法模块.md` | K-1.x（模块①）、K-2.x（模块②a/b/c）、K-3.x~K-6.x，含 I/O 契约、公式组、伪代码、失效模式 |
| 第5章 双方法边界 | `…/第5章_双方法边界.md` | 解析共轭 vs 离散包络的适用矩阵与切换判据 |
| 第6章 两个算例 | `…/第6章_两个算例.md` | 算例1（解析路线）、算例2（离散路线）的完整数值轨迹 |
| 第7章 验收基准表 | `…/第7章_验收基准表.md` | 模块×判据×文献值×容差 |
| 第8章 缺口清单 | `…/第8章_缺口清单.md` | T1-T13 公式断点、W1-W15 核对存疑——⚠️ 未销项项**禁止当已验证公式用** |
| 测试向量 | `…/testdata/` | 算例 JSON 回归基准 |
| 文献摘录 | `E:/OneDrive/Claude_Word/PowerSkivingDoc/knowledge-base/参考文献摘录.md` | 各篇文献的核心内容、公式编号、标签与评级 |
| 原始 PDF | `E:/OneDrive/Claude_Word/PowerSkivingDoc/references/` | 公式核对必须回读原页，勿信 OCR 提取 |
| 00 大纲与决策 | `…/00_大纲与决策.md` | 决策记录、算例规格、撰写纪律 |

## 核心业务逻辑（车齿刀）

六模块流水线（详见设计书第1/4章）：

```
模块① 工件与工艺方案   → 工件曲面 + 工艺方案(Σ/a/i/同步律)
模块②a 前刀面定义      → RakeSurface
模块②b 刃形求解        → EdgeCurve（刃形点集）+ GeneratrixSurface（产形面）
模块②c 后刀面生成      → FlankSurface
模块③ 三维几何与结构   → 单齿→阵列→刀体实体(STEP)
模块④ 正向仿真验证     → 虚拟切削，ffα/过切欠切/PASS-FAIL
⑤ 磨削  ⑥ 工艺文件
```

### 开发纪律

1. **实现任何公式前，先读设计书对应章节**——不要凭记忆写。K 公式的编号即查找路径。
2. **符号体系**：内部计算一律 rad，接口层 °；变量名与设计书符号一致（w/t/F_w/F_t，**严禁用 1/2 表示工件/刀具**）。见第2章 U1-U13。
3. **冲突表 C1-Cx**：引用文献公式时，先确认冲突表是否已记录，已记录的按转换式处理。
4. **接口不变量**（第1章 §1.4）：任何点集/曲面对象携带坐标系标签（W/T/F_w/F_t/R），无标签→非法。
5. **缺口清单中的 ⚠️/🔴 项**：未销项的用骨架+assert 占位，**不得直接当已验证公式写入**。

### 开发分批（按公式可信度）

**第一批（公式干净，可立即开发）**：K-0.x 变换库 → 模块①主体 → ②b 离散路线（[21][25] 锚点齐）→ ②a 平面前刀面
**第二批（销项后开发）**：E1/T13 计量齿厚 → T8 变位链 → ②b 解析路线的 ε_NR 标定（T1）
**缓行（⚠️ 回读 PDF 前不动）**：K-2.4 锥面前刀面（W5）→ 工作角度分布 K-2.22（W6）→ 机床补偿 K-2.27（W7）→ 模块⑤（W8）

### 测试基准

testdata/ 中的 JSON 向量为回归基准：`ex1_analytic.json`（算例1 [23]）、`ex2_discrete.json`（算例2 [21]）、`ex3_jia2019_cases.json`（算例3 [25] 参数级）。输出偏离 > 容差即算失败。

## 命令（脚手架搭建后可用）

```bash
# 安装依赖
npm install
cd backend && pip install -r requirements.txt

# 开发模式（Vite 开发服务器 + Electron）
npm run dev

# 生产构建
npm run build

# 代码检查
npm run lint

# 类型检查
npm run typecheck

# 运行测试
npm test
```

## Agent skills

### Issue tracker

GitHub Issues，通过 `gh` CLI 操作。详见 `docs/agents/issue-tracker.md`。

### Triage labels

默认词汇：`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`。详见 `docs/agents/triage-labels.md`。

### Domain docs

单上下文布局：根目录 `CONTEXT.md` + `docs/adr/`。详见 `docs/agents/domain.md`。

## 其他

所有对话采用中文。
