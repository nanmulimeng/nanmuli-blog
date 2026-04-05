/**
 * 简化的主题系统 - 二元模式
 * 亮色模式：沉稳深蓝 (Deep Blue)
 * 暗色模式：赛博朋克 (Cyberpunk)
 *
 * CSS 变量定义在 index.scss 中，JS 只负责切换 dark 类
 */

export type ThemeMode = 'light' | 'dark'

let currentMode: ThemeMode = 'light'

// 应用主题到 DOM - 只切换 class，CSS 变量由 scss 文件控制
export function applyTheme(mode: ThemeMode) {
  const root = document.documentElement
  currentMode = mode

  // 设置暗黑模式类 - CSS 变量由 index.scss 中的 :root 和 .dark 定义
  if (mode === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }

  // 保存到 localStorage
  localStorage.setItem('blog-theme-mode', mode)
}

// 获取保存的主题
export function getSavedTheme(): ThemeMode {
  if (typeof window === 'undefined') return 'light'
  return (localStorage.getItem('blog-theme-mode') as ThemeMode) || 'light'
}

// 初始化主题
export function initTheme() {
  const mode = getSavedTheme()
  console.log('[Theme] Initializing theme, saved mode:', mode)
  applyTheme(mode)
}

// 切换主题
export function toggleTheme() {
  const newMode = currentMode === 'light' ? 'dark' : 'light'
  applyTheme(newMode)
}

// 设置主题
export function setTheme(mode: ThemeMode) {
  applyTheme(mode)
}

// 获取当前主题
export function getCurrentTheme(): ThemeMode {
  return currentMode
}

// 判断是否为暗色模式
export function isDarkMode(): boolean {
  return currentMode === 'dark'
}
