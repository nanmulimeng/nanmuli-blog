import { ref, computed, onMounted } from 'vue'
import { getCurrentTheme, toggleTheme, setTheme, type ThemeMode, initTheme } from '@/styles/themes'

/**
 * 简化的主题管理 - 二元模式
 * 亮色：沉稳深蓝 | 暗色：赛博朋克
 */
export function useTheme() {
  const theme = ref<ThemeMode>('light')

  // 计算当前是否为暗色模式
  const isDark = computed(() => theme.value === 'dark')

  // 切换主题
  const toggle = () => {
    toggleTheme()
    theme.value = getCurrentTheme()
  }

  // 设置主题
  const set = (mode: ThemeMode) => {
    setTheme(mode)
    theme.value = mode
  }

  // 初始化
  onMounted(() => {
    initTheme()
    theme.value = getCurrentTheme()
  })

  return {
    theme,
    isDark,
    toggle,
    set,
  }
}
