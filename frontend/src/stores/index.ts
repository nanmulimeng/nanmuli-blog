import { createPinia } from 'pinia'

// Pinia 实例
export const pinia = createPinia()

// 导出 Store 模块
export { useUserStore } from './modules/user'
export { useConfigStore } from './modules/config'
