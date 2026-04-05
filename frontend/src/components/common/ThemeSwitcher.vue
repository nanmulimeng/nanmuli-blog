<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getCurrentTheme, toggleTheme, isDarkMode, type ThemeMode } from '@/styles/themes'

const currentMode = ref<ThemeMode>('light')

function handleToggle() {
  toggleTheme()
  currentMode.value = getCurrentTheme()
}

onMounted(() => {
  currentMode.value = getCurrentTheme()
})
</script>

<template>
  <button
    class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200"
    :class="isDarkMode()
      ? 'bg-primary/10 text-primary-light hover:bg-primary/20'
      : 'bg-primary/5 text-primary hover:bg-primary/10'"
    @click="handleToggle"
    aria-label="切换明暗主题"
    :title="isDarkMode() ? '切换到亮色模式' : '切换到暗色模式'"
  >
    <!-- 亮色模式图标 -->
    <svg v-if="isDarkMode()" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
        d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728
        0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
    </svg>
    <!-- 暗色模式图标 -->
    <svg v-else class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
        d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
    </svg>
    <span class="hidden sm:inline">{{ isDarkMode() ? '暗夜模式' : '日间模式' }}</span>
  </button>
</template>
