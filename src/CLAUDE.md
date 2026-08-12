# src/ — 前端源码

Vue 3 + TypeScript + Three.js 渲染进程，Vite 构建。

## 技术约定

- Vue 3 Composition API + `<script setup>`，TypeScript 严格模式
- UI 组件库：Element Plus
- 所有函数参数/返回值必须显式定义类型
- 异步操作统一 `async/await` + `try/catch`
- 禁止直接使用 `fs`（通过 `src/api/` HTTP 通信或 IPC）
- 注释一律中文；每个源文件以 `/** */` 头部说明其职责
- 命名：组件文件 PascalCase（`*.vue`）、composable `useXxx.ts`、其余模块 camelCase

## 目录布局

| 路径 | 职责 |
|------|------|
| `main.ts` / `spec-window.ts` | 两个渲染进程入口：主窗口 / 齿轮规格独立窗口 |
| `App.vue` | 应用根组件：自绘标题栏 + 窗口控件 + 挂载主视图 |
| `components/` | 9 个 Vue 组件（见下方组件树） |
| `composables/` | 跨组件状态/逻辑：参数 schema / 结果单例 / SVG 视口 |
| `three/gearViewport.ts` | Three.js 场景深模块（渲染循环藏于小接口后） |
| `api/` | HTTP 封装（`index.ts`）+ spec 纯类型（`spec-types.ts`） |
| `assets/theme.css` | 全局主题 |

## 组件架构

```
App.vue                          # 窗口外壳：自绘标题栏 + 窗口控件（登录后滑入）
└── MainView.vue                 # 主视图：全屏 3D 视口 + 登录门 + 主功能入口
    ├── MainPanel.vue            #   左下角面板：文件栏 + 5 步导航（provide gearParams）
    │   ├── GearParamsPanel.vue  #     步骤1：工件参数（注入 gearParams 直接改值）
    │   └── WorkpieceViewer.vue  #     步骤2：生成齿轮 GLB（fetchWorkpiece → 全局单例）
    └── ResultPanel.vue          #   独立可拖拽「计算结果」面板（消费 useWorkpieceState）
SpecWindowRoot.vue               # 齿轮规格独立窗口（spec.html，经 IPC 传 spec）
    ├── ToothProfileSvg.vue      #   单齿廓 + ISO 尺寸标注
    ├── GearOutlineSvg.vue       #   整体轮廓
    └── SpecTable.vue            #   参数规格表（只读）
```

### composables（跨组件状态/逻辑）

- `useGearParams.ts` — GearParams 单一 schema：类型 + 默认值 + `toPayload`（camelCase→snake_case，唯一 wire 映射源）
- `useWorkpieceState.ts` — 生成结果全局单例（WorkpieceViewer 写入 / ResultPanel 消费；面板位置持久化 localStorage）
- `useSvgViewport.ts` — SVG 视口缩放/平移/复位（ToothProfileSvg / GearOutlineSvg 共享）

### three/gearViewport.ts（3D 深模块）

- 小接口 `loadGear / setRenderMode / setLoggedIn / setModelLayout / resize / dispose`
- 场景/相机/渲染器/布光/动画循环全部藏于模块内；消费者注入可观察 ref（`modelLoaded` 等）供模板绑定

## 品牌与主题

- `src/assets/theme.css`：全局 CSS 变量 + 表单基类（`.glass-input`、`.glass-segmented`、`.glass-collapse` 等）
- 主色 `#0060A0`，暗色 `#004080`，亮色 `#4080C0`
- 玻璃面板统一蓝色质感：`background: rgba(0, 96, 160, 0.09)`
- 过渡动画统一 `cubic-bezier(0.22, 0.61, 0.36, 1)`

## HTTP 通信

- 封装在 `src/api/index.ts`，通过 Vite 代理 `/api` → `http://127.0.0.1:5199`
- 后端 URL 通过 `import.meta.env.VITE_BACKEND_URL` 配置
- 业务调用 `fetchWorkpiece`；camelCase→snake_case 映射由 `useGearParams.toPayload` 统一负责

## 3D 渲染

- Three.js：PBR 材质 + 三点布光 + ACES 色调映射
- OrbitControls：登录后启用，首次操作停止自动旋转
- 模型格式：STL（过渡）→ GLB（正式）
- 性能：禁止在渲染循环中创建几何体，注意 `dispose()`

## 测试

- Vitest + @vue/test-utils + jsdom
- 测试边界：组件 provide/inject 接口，不测 DOM 细节
- 运行：`npm test`
