import { ref, computed, watchEffect, onMounted } from 'vue'

export type Theme = 'light' | 'dark' | 'auto' | 'system'

const STORAGE_KEY = 'blog-theme'

/**
 * 主题管理组合式函数 - Aurora Glass Design
 * 支持 Light / Dark / System 三种模式
 */
export function useTheme() {
  const theme = ref<Theme>('system')
  const systemPrefersDark = ref(false)

  // 计算当前是否为暗色模式
  const isDark = computed(() => {
    if (theme.value === 'auto' || theme.value === 'system') {
      return systemPrefersDark.value
    }
    return theme.value === 'dark'
  })

  // 当前实际主题名称
  const currentTheme = computed(() => (isDark.value ? 'dark' : 'light'))

  // 检测系统主题偏好
  const checkSystemTheme = () => {
    if (typeof window === 'undefined') return false
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  }

  // 监听系统主题变化
  const listenToSystemTheme = () => {
    if (typeof window === 'undefined') return

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQuery.addEventListener('change', (e) => {
      systemPrefersDark.value = e.matches
    })
  }

  // 设置主题
  const setTheme = (newTheme: Theme): void => {
    theme.value = newTheme
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, newTheme)
    }
  }

  // 切换主题（light <-> dark）
  const toggleTheme = (): void => {
    setTheme(isDark.value ? 'light' : 'dark')
  }

  // 初始化主题
  const initTheme = () => {
    if (typeof window === 'undefined') return

    // 读取保存的主题
    const savedTheme = localStorage.getItem(STORAGE_KEY) as Theme | null
    theme.value = savedTheme || 'system'

    // 检测系统主题
    systemPrefersDark.value = checkSystemTheme()
    listenToSystemTheme()
  }

  // 监听主题变化并应用到 DOM
  watchEffect(() => {
    if (typeof document === 'undefined') return

    const html = document.documentElement
    if (isDark.value) {
      html.classList.add('dark')
      html.setAttribute('data-theme', 'dark')
    } else {
      html.classList.remove('dark')
      html.setAttribute('data-theme', 'light')
    }
  })

  // 组件挂载时初始化
  onMounted(() => {
    initTheme()
  })

  return {
    theme,
    isDark,
    currentTheme,
    setTheme,
    toggleTheme,
    initTheme,
  }
}
