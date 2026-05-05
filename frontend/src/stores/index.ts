import { createPinia } from 'pinia'

// Pinia 实例
export const pinia = createPinia()

// 导出 Store 模块
export { useUserStore } from './modules/user'
export { useAppStore } from './modules/app'
export { useConfigStore } from './modules/config'
export { useArticleStore } from './modules/article'
export { useDailyLogStore } from './modules/dailyLog'
