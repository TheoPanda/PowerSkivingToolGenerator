/**
 * main.ts — 渲染进程主入口
 *
 * 挂载 App.vue（Electron 主窗口根组件）。
 * 兄弟入口 spec-window.ts 挂载齿轮规格独立窗口（spec.html）。
 */
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './assets/theme.css'
import App from './App.vue'

const app = createApp(App)
app.use(ElementPlus)
app.mount('#app')
