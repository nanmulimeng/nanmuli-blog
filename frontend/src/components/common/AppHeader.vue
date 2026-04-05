<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConfigStore } from '@/stores/modules/config'

const router = useRouter()
const configStore = useConfigStore()
const isScrolled = ref(false)
const isMobileMenuOpen = ref(false)

onMounted(() => {
  window.addEventListener('scroll', () => {
    isScrolled.value = window.scrollY > 20
  })
  configStore.loadConfig()
})

const navItems = [
  { path: '/', label: '首页', icon: 'HomeFilled' },
  { path: '/article', label: '文章', icon: 'Document' },
  { path: '/daily-log', label: '技术日志', icon: 'Timer' },
  { path: '/tag', label: '标签', icon: 'CollectionTag' },
  { path: '/project', label: '项目', icon: 'OfficeBuilding' },
  { path: '/about', label: '关于', icon: 'UserFilled' },
]

function isActive(path: string): boolean {
  if (path === '/') {
    return router.currentRoute.value.path === '/'
  }
  return router.currentRoute.value.path.startsWith(path)
}

function toggleMobileMenu(): void {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}

function closeMobileMenu(): void {
  isMobileMenuOpen.value = false
}
</script>

<template>
  <header
    class="fixed left-0 right-0 top-0 z-50 transition-all duration-300"
    :class="{
      'bg-white/95 shadow-sm backdrop-blur-md': isScrolled,
      'bg-transparent': !isScrolled
    }"
  >
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <div class="flex h-16 items-center justify-between">
        <!-- Logo -->
        <router-link to="/" class="flex items-center gap-2">
          <div
            v-if="!configStore.siteLogo"
            class="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center text-white"
          >
            <el-icon><Document /></el-icon>
          </div>
          <img v-else :src="configStore.siteLogo" alt="logo" class="h-8 w-8" />
          <span class="text-xl font-bold text-gray-900">{{ configStore.siteName || '我的博客' }}</span>
        </router-link>

        <!-- Desktop Navigation -->
        <nav class="hidden md:flex items-center gap-1">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="isActive(item.path)
              ? 'text-primary-600 bg-primary-50'
              : 'text-gray-600 hover:text-primary-600 hover:bg-gray-50'"
          >
            {{ item.label }}
          </router-link>
        </nav>

        <!-- Actions -->
        <div class="flex items-center gap-2">
          <button
            class="p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
            aria-label="搜索"
          >
            <el-icon :size="20"><Search /></el-icon>
          </button>

          <!-- Mobile Menu Button -->
          <button
            class="md:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
            @click="toggleMobileMenu"
            aria-label="菜单"
          >
            <el-icon :size="20">
              <Menu v-if="!isMobileMenuOpen" />
              <Close v-else />
            </el-icon>
          </button>
        </div>
      </div>
    </div>

    <!-- Mobile Menu -->
    <transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div
        v-if="isMobileMenuOpen"
        class="md:hidden bg-white border-t border-gray-100 shadow-lg"
      >
        <nav class="mx-auto max-w-7xl px-4 py-4 space-y-1">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors"
            :class="isActive(item.path)
              ? 'text-primary-600 bg-primary-50'
              : 'text-gray-600 hover:text-primary-600 hover:bg-gray-50'"
            @click="closeMobileMenu"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            {{ item.label }}
          </router-link>
        </nav>
      </div>
    </transition>
  </header>
</template>
