import { createApp } from 'vue'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
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
import { imgFallback } from './directives/imgFallback'

// 初始化主题（在 DOM 创建后，应用挂载前）
initTheme()

// 使用持久化插件
pinia.use(piniaPluginPersistedstate)

const app = createApp(App)

app.use(pinia)
app.use(router)

// 注册全局自定义指令
app.directive('img-fallback', imgFallback)

// 注册所有 Element Plus 图标（图标不支持自动按需导入，需手动注册）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.mount('#app')
