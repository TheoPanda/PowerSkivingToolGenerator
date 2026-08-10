/**
 * spec-window.ts — 齿轮规格独立窗口入口
 *
 * Electron 主进程新建 BrowserWindow 加载 spec.html → 本入口挂载 SpecWindowRoot。
 * 规格数据经 IPC（spec:open → spec:data / spec:getData）从主窗口传入。
 */
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './assets/theme.css'
import SpecWindowRoot from './components/SpecWindowRoot.vue'

const app = createApp(SpecWindowRoot)
app.use(ElementPlus)
app.mount('#app')
