<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useConfigStore } from '@/stores/modules/config'
import { useTheme } from '@/composables/useTheme'

const router = useRouter()
const route = useRoute()
const configStore = useConfigStore()
const { isDark, toggleTheme } = useTheme()

// 滚动状态
const isScrolled = ref(false)
const scrollProgress = ref(0)

// 移动端菜单
const isMobileMenuOpen = ref(false)

// 搜索框
const isSearchOpen = ref(false)
const searchQuery = ref('')

// 导航项
const navItems = [
  { path: '/', label: '首页', icon: 'HomeFilled' },
  { path: '/article', label: '文章', icon: 'Document' },
  { path: '/daily-log', label: '日志', icon: 'Timer' },
  { path: '/tag', label: '标签', icon: 'CollectionTag' },
  { path: '/project', label: '项目', icon: 'OfficeBuilding' },
  { path: '/about', label: '关于', icon: 'UserFilled' },
]

// 计算滚动进度和状态
const handleScroll = () => {
  const scrollY = window.scrollY
  isScrolled.value = scrollY > 20
  const docHeight = document.documentElement.scrollHeight - window.innerHeight
  scrollProgress.value = docHeight > 0 ? (scrollY / docHeight) * 100 : 0
}

// 判断是否激活
const isActive = (path: string): boolean => {
  if (path === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(path)
}

// 切换移动菜单
const toggleMobileMenu = () => {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
  // 防止背景滚动
  document.body.style.overflow = isMobileMenuOpen.value ? 'hidden' : ''
}

// 关闭移动菜单
const closeMobileMenu = () => {
  isMobileMenuOpen.value = false
  document.body.style.overflow = ''
}

// 处理搜索
const handleSearch = () => {
  if (searchQuery.value.trim()) {
    router.push(`/article?keyword=${encodeURIComponent(searchQuery.value.trim())}`)
    isSearchOpen.value = false
    searchQuery.value = ''
  }
}

// 滚动到顶部
const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll, { passive: true })
  configStore.loadConfig()
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<template>
  <div>
    <header
      class="fixed left-0 right-0 top-0 z-50 transition-all duration-500 ease-smooth"
    :class="{
      'py-3': !isScrolled,
      'py-2': isScrolled,
    }"
  >
    <!-- 滚动进度条 -->
    <div
      class="absolute bottom-0 left-0 h-[2px] bg-gradient-to-r from-aurora-purple via-aurora-pink to-aurora-cyan transition-all duration-300"
      :style="{ width: `${scrollProgress}%` }"
    />

    <!-- 主导航容器 -->
    <div
      class="mx-auto max-w-7xl px-4 transition-all duration-500 ease-smooth sm:px-6 lg:px-8"
      :class="{
        'mt-4': !isScrolled,
        'mt-0': isScrolled,
      }"
    >
      <nav
        class="relative flex h-16 items-center justify-between rounded-2xl px-6 transition-all duration-500 ease-smooth"
        :class="{
          'glass shadow-lg': isScrolled,
          'bg-transparent': !isScrolled,
        }"
      >
        <!-- Logo -->
        <router-link
          to="/"
          class="group flex items-center gap-3 transition-transform duration-300 hover:scale-105"
          @click="scrollToTop"
        >
          <div
            class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-aurora-purple to-aurora-pink text-white shadow-lg shadow-aurora-purple/30 transition-all duration-300 group-hover:shadow-aurora-purple/50"
          >
            <el-icon class="text-xl"><Document /></el-icon>
          </div>
          <span
            class="bg-gradient-to-r from-gray-900 via-gray-700 to-gray-900 bg-clip-text text-xl font-bold text-transparent dark:from-white dark:via-gray-300 dark:to-white"
          >
            {{ configStore.siteName || 'Nanmuli' }}
          </span>
        </router-link>

        <!-- Desktop Navigation -->
        <div class="hidden items-center gap-1 md:flex">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="group relative px-4 py-2 text-sm font-medium transition-all duration-300"
            :class="isActive(item.path)
              ? 'text-aurora-purple dark:text-aurora-pink'
              : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
            "
          >
            <span class="relative z-10">{{ item.label }}</span>
            <!-- 激活指示器 -->
            <span
              class="absolute inset-0 rounded-xl transition-all duration-300"
              :class="isActive(item.path)
                ? 'bg-aurora-purple/10 dark:bg-aurora-pink/10 scale-100'
                : 'bg-gray-100 dark:bg-white/5 scale-0 group-hover:scale-100'
              "
            />
            <!-- 下划线动画 -->
            <span
              class="absolute bottom-0 left-1/2 h-0.5 w-0 -translate-x-1/2 rounded-full bg-gradient-to-r from-aurora-purple to-aurora-pink transition-all duration-300 group-hover:w-1/2"
              :class="{ 'w-1/2': isActive(item.path) }"
            />
          </router-link>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-2">
          <!-- 搜索按钮 -->
          <button
            class="flex h-10 w-10 items-center justify-center rounded-xl text-gray-500 transition-all duration-300 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-white/10 dark:hover:text-white"
            aria-label="搜索"
            @click="isSearchOpen = true"
          >
            <el-icon class="text-lg"><Search /></el-icon>
          </button>

          <!-- 主题切换 -->
          <button
            class="flex h-10 w-10 items-center justify-center rounded-xl text-gray-500 transition-all duration-300 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-white/10 dark:hover:text-white"
            :class="{ 'animate-spin-slow': false }"
            aria-label="切换主题"
            @click="toggleTheme"
          >
            <el-icon v-if="isDark" class="text-lg text-aurora-cyan"><Sunny /></el-icon>
            <el-icon v-else class="text-lg text-aurora-purple"><Moon /></el-icon>
          </button>

          <!-- 管理后台入口 -->
          <router-link
            to="/admin"
            class="hidden items-center gap-2 rounded-xl bg-gradient-to-r from-aurora-purple to-aurora-pink px-4 py-2 text-sm font-medium text-white shadow-lg shadow-aurora-purple/30 transition-all duration-300 hover:shadow-aurora-purple/50 hover:-translate-y-0.5 sm:flex"
          >
            <el-icon><Setting /></el-icon>
            <span>管理</span>
          </router-link>

          <!-- Mobile Menu Button -->
          <button
            class="flex h-10 w-10 items-center justify-center rounded-xl text-gray-500 transition-all duration-300 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/10 md:hidden"
            :class="{ 'bg-gray-100 dark:bg-white/10': isMobileMenuOpen }"
            @click="toggleMobileMenu"
            aria-label="菜单"
          >
            <el-icon class="text-xl">
              <Menu v-if="!isMobileMenuOpen" />
              <Close v-else />
            </el-icon>
          </button>
        </div>
      </nav>
    </div>

    <!-- Search Modal -->
    <Transition
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isSearchOpen"
        class="fixed inset-0 z-50 flex items-start justify-center bg-black/50 backdrop-blur-sm pt-32"
        @click="isSearchOpen = false"
      >
        <div
          class="w-full max-w-2xl transform rounded-3xl glass p-6 shadow-2xl transition-all"
          @click.stop
        >
          <div class="relative">
            <el-icon class="absolute left-5 top-1/2 -translate-y-1/2 text-xl text-gray-400">
              <Search />
            </el-icon>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索文章..."
              class="input-glass w-full py-4 pl-14 pr-12 text-lg"
              @keyup.enter="handleSearch"
            />
            <button
              v-if="searchQuery"
              class="absolute right-5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              @click="searchQuery = ''"
            >
              <el-icon><Close /></el-icon>
            </button>
          </div>
          <p class="mt-4 text-center text-sm text-gray-500">
            按 Enter 搜索，按 ESC 关闭
          </p>
        </div>
      </div>
    </Transition>

    <!-- Mobile Menu Overlay -->
    <Transition
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isMobileMenuOpen"
        class="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
        @click="closeMobileMenu"
      />
    </Transition>

    <!-- Mobile Menu Panel -->
    <Transition
      enter-active-class="transition duration-300 ease-smooth"
      enter-from-class="translate-x-full opacity-0"
      enter-to-class="translate-x-0 opacity-100"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="translate-x-0 opacity-100"
      leave-to-class="translate-x-full opacity-0"
    >
      <div
        v-if="isMobileMenuOpen"
        class="fixed right-0 top-0 z-50 h-full w-80 overflow-y-auto bg-white/95 p-6 shadow-2xl backdrop-blur-2xl dark:bg-dark-800/95 md:hidden"
      >
        <!-- Close Button -->
        <div class="mb-8 flex justify-end">
          <button
            class="flex h-10 w-10 items-center justify-center rounded-xl text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/10"
            @click="closeMobileMenu"
          >
            <el-icon class="text-xl"><Close /></el-icon>
          </button>
        </div>

        <!-- Mobile Nav Links -->
        <nav class="space-y-2">
          <router-link
            v-for="(item, index) in navItems"
            :key="item.path"
            :to="item.path"
            class="group flex items-center gap-4 rounded-2xl p-4 transition-all duration-300"
            :class="isActive(item.path)
              ? 'bg-gradient-to-r from-aurora-purple/10 to-aurora-pink/10 text-aurora-purple dark:text-aurora-pink'
              : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/5'
            "
            :style="{ animationDelay: `${index * 50}ms` }"
            @click="closeMobileMenu"
          >
            <div
              class="flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-300"
              :class="isActive(item.path)
                ? 'bg-gradient-to-br from-aurora-purple to-aurora-pink text-white'
                : 'bg-gray-100 dark:bg-white/10'
              "
            >
              <el-icon class="text-lg"><component :is="item.icon" /></el-icon>
            </div>
            <span class="text-lg font-medium">{{ item.label }}</span>
            <el-icon
              v-if="isActive(item.path)"
              class="ml-auto text-aurora-purple dark:text-aurora-pink"
            >
              <ArrowRight />
            </el-icon>
          </router-link>
        </nav>

        <!-- Mobile Admin Link -->
        <div class="mt-8 border-t border-gray-200 pt-6 dark:border-white/10">
          <router-link
            to="/admin"
            class="flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-aurora-purple to-aurora-pink p-4 font-medium text-white shadow-lg shadow-aurora-purple/30"
            @click="closeMobileMenu"
          >
            <el-icon><Setting /></el-icon>
            <span>进入管理后台</span>
          </router-link>
        </div>

        <!-- Mobile Theme Toggle -->
        <div class="mt-6 flex items-center justify-between rounded-2xl bg-gray-100 p-4 dark:bg-white/5">
          <span class="text-gray-600 dark:text-gray-400">主题模式</span>
          <button
            class="flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm transition-all dark:bg-dark-700"
            @click="toggleTheme"
          >
            <el-icon v-if="isDark" class="text-aurora-cyan"><Sunny /></el-icon>
            <el-icon v-else class="text-aurora-purple"><Moon /></el-icon>
          </button>
        </div>
      </div>
    </Transition>
  </header>

  <!-- 占位符，防止内容被固定导航遮挡 -->
  <div class="h-24" />
</div>
</template>

<style scoped>
/* 慢速旋转动画 */
@keyframes spin-slow {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.animate-spin-slow {
  animation: spin-slow 3s linear infinite;
}
</style>
