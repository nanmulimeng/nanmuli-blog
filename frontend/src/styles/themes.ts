/**
 * 简化的主题系统 - 二元模式
 * 亮色模式：沉稳深蓝 (Deep Blue)
 * 暗色模式：赛博朋克 (Cyberpunk)
 *
 * CSS 变量定义在 index.scss 中，JS 只负责切换 dark 类
 */

export type ThemeMode = 'light' | 'dark' | 'system'

let currentMode: ThemeMode = 'light'
let systemThemeListener: MediaQueryList | null = null

// 获取系统主题偏好
function getSystemTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

// 应用主题到 DOM - 只切换 class，CSS 变量由 scss 文件控制
function applyTheme(mode: ThemeMode) {
  const root = document.documentElement
  currentMode = mode

  let effectiveMode: 'light' | 'dark'

  if (mode === 'system') {
    effectiveMode = getSystemTheme()
    setupSystemThemeListener()
  } else {
    effectiveMode = mode
    removeSystemThemeListener()
  }

  // 设置暗黑模式类 - CSS 变量由 index.scss 中的 :root 和 .dark 定义
  if (effectiveMode === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }

  // 保存到 localStorage
  localStorage.setItem('blog-theme-mode', mode)
}

// 设置系统主题监听器
function setupSystemThemeListener() {
  if (typeof window === 'undefined') return

  if (!systemThemeListener) {
    systemThemeListener = window.matchMedia('(prefers-color-scheme: dark)')
  }

  // 监听系统主题变化
  systemThemeListener.addEventListener('change', handleSystemThemeChange)
}

// 移除系统主题监听器
function removeSystemThemeListener() {
  if (systemThemeListener) {
    systemThemeListener.removeEventListener('change', handleSystemThemeChange)
  }
}

// 处理系统主题变化
function handleSystemThemeChange(e: MediaQueryListEvent) {
  const root = document.documentElement
  if (e.matches) {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
}

// 获取保存的主题
function getSavedTheme(): ThemeMode {
  if (typeof window === 'undefined') return 'light'
  return (localStorage.getItem('blog-theme-mode') as ThemeMode) || 'light'
}

// 初始化主题
export function initTheme() {
  const savedMode = getSavedTheme()
  applyTheme(savedMode)
}

// 切换主题（在 light/dark 之间切换，不处理 system）
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
  if (currentMode === 'system') {
    return getSystemTheme() === 'dark'
  }
  return currentMode === 'dark'
}

