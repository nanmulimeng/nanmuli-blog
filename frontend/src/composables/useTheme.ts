import { ref, computed, watchEffect } from 'vue'

type Theme = 'light' | 'dark' | 'auto'

const STORAGE_KEY = 'blog-theme'

/**
 * 主题管理组合式函数
 */
export function useTheme() {
  const theme = ref<Theme>((localStorage.getItem(STORAGE_KEY) as Theme) || 'auto')

  const isDark = computed(() => {
    if (theme.value === 'auto') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches
    }
    return theme.value === 'dark'
  })

  const currentTheme = computed(() => (isDark.value ? 'dark' : 'light'))

  function setTheme(newTheme: Theme): void {
    theme.value = newTheme
    localStorage.setItem(STORAGE_KEY, newTheme)
  }

  function toggleTheme(): void {
    setTheme(isDark.value ? 'light' : 'dark')
  }

  // 监听主题变化并应用到 DOM
  watchEffect(() => {
    const html = document.documentElement
    if (isDark.value) {
      html.classList.add('dark')
      html.setAttribute('data-theme', 'dark')
    } else {
      html.classList.remove('dark')
      html.setAttribute('data-theme', 'light')
    }
  })

  return {
    theme,
    isDark,
    currentTheme,
    setTheme,
    toggleTheme,
  }
}
