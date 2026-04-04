<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConfigStore } from '@/stores/modules/config'

const router = useRouter()
const configStore = useConfigStore()
const isScrolled = ref(false)

onMounted(() => {
  window.addEventListener('scroll', () => {
    isScrolled.value = window.scrollY > 20
  })
  configStore.loadConfig()
})

const navItems = [
  { path: '/', label: '首页' },
  { path: '/article', label: '文章' },
  { path: '/daily-log', label: '技术日志' },
  { path: '/category', label: '分类' },
  { path: '/tag', label: '标签' },
  { path: '/project', label: '项目' },
  { path: '/about', label: '关于' },
]

function isActive(path: string): boolean {
  return router.currentRoute.value.path === path
}
</script>

<template>
  <header
    class="fixed left-0 right-0 top-0 z-50 transition-all duration-300"
    :class="{ 'bg-white/90 shadow-sm backdrop-blur-md': isScrolled, 'bg-transparent': !isScrolled }"
  >
    <div class="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
      <router-link to="/" class="flex items-center gap-2">
        <img v-if="configStore.siteLogo" :src="configStore.siteLogo" alt="logo" class="h-8 w-8" />
        <span class="text-xl font-bold text-gray-900">{{ configStore.siteName }}</span>
      </router-link>

      <nav class="hidden md:flex items-center gap-8">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="text-sm font-medium transition-colors"
          :class="isActive(item.path) ? 'text-primary-600' : 'text-gray-600 hover:text-primary-600'"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <div class="flex items-center gap-4">
        <button class="rounded-full p-2 text-gray-600 hover:bg-gray-100">
          <el-icon :size="20"><Search /></el-icon>
        </button>
      </div>
    </div>
  </header>
</template>
