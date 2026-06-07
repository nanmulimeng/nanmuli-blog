import { createApp } from 'vue'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import 'highlight.js/styles/github-dark.css'

// unplugin-vue-components 仅自动导入模板中组件的样式
// JS API（ElMessageBox/ElMessage/ElNotification）的样式需手动导入
import 'element-plus/theme-chalk/el-overlay.css'
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-notification.css'

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

app.mount('#app')
