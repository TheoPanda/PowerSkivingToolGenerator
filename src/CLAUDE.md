# src/ — 前端源码

Vue 3 + TypeScript + Three.js 渲染进程，Vite 构建。

## 技术约定

- Vue 3 Composition API + `<script setup>`，TypeScript 严格模式
- UI 组件库：Element Plus
- 所有函数参数/返回值必须显式定义类型
- 异步操作统一 `async/await` + `try/catch`
- 禁止直接使用 `fs`（通过 `src/api/` HTTP 通信或 IPC）

## 组件架构

```
App.vue
└── HelloWorld.vue          # 3D 场景 + 登录 + 主功能入口
    └── MainPanel.vue        # 左下角面板：文件栏 + 5 步导航 + 参数表单
        └── GearParamsPanel.vue  # 步骤1：工件参数（三组折叠板块）
```

## 品牌与主题

- `src/assets/theme.css`：全局 CSS 变量 + 表单基类（`.glass-input`、`.glass-segmented`、`.glass-collapse` 等）
- 主色 `#0060A0`，暗色 `#004080`，亮色 `#4080C0`
- 玻璃面板统一蓝色质感：`background: rgba(0, 96, 160, 0.09)`
- 过渡动画统一 `cubic-bezier(0.22, 0.61, 0.36, 1)`

## HTTP 通信

- 封装在 `src/api/index.ts`，通过 Vite 代理 `/api` → `http://127.0.0.1:5199`
- 后端 URL 通过 `import.meta.env.VITE_BACKEND_URL` 配置

## 3D 渲染

- Three.js：PBR 材质 + 三点布光 + ACES 色调映射
- OrbitControls：登录后启用，首次操作停止自动旋转
- 模型格式：STL（过渡）→ GLB（正式）
- 性能：禁止在渲染循环中创建几何体，注意 `dispose()`

## 测试

- Vitest + @vue/test-utils + jsdom
- 测试边界：组件 provide/inject 接口，不测 DOM 细节
- 运行：`npm test`
