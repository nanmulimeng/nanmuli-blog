import { createApp } from 'vue'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'highlight.js/styles/github-dark.css'

import App from './App.vue'
import router from './router'
import { pinia } from './stores'

import './styles/index.scss'
import { initTheme } from './styles/themes'

// 初始化主题（在 DOM 创建后，应用挂载前）
initTheme()

// 使用持久化插件
pinia.use(piniaPluginPersistedstate)

const app = createApp(App)

app.use(pinia)
app.use(router)
app.use(ElementPlus)

app.mount('#app')
