<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useConfigStore } from '@/stores/modules/config'
import { useTheme } from '@/composables/useTheme'
import { getArticleList } from '@/api/article'
import type { Article } from '@/types/article'
import ThemeSwitcher from './ThemeSwitcher.vue'

const router = useRouter()
const route = useRoute()
const configStore = useConfigStore()
useTheme() // 初始化主题

// 滚动状态
const isScrolled = ref(false)
const scrollProgress = ref(0)

// 移动端菜单
const isMobileMenuOpen = ref(false)

// 搜索框
const isSearchOpen = ref(false)
const searchQuery = ref('')
const searchResults = ref<Article[]>([])
const isSearching = ref(false)
const selectedIndex = ref(-1)
const searchInputRef = ref<HTMLInputElement | null>(null)

// 导航项
const navItems = [
  { path: '/', label: '首页', icon: 'HomeFilled' },
  { path: '/article', label: '文章', icon: 'Document' },
  { path: '/project', label: '项目', icon: 'OfficeBuilding' },
  { path: '/daily-log', label: '日志', icon: 'Timer' },
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
  document.body.style.overflow = isMobileMenuOpen.value ? 'hidden' : ''
}

// 关闭移动菜单
const closeMobileMenu = () => {
  isMobileMenuOpen.value = false
  document.body.style.overflow = ''
}

// 搜索文章
const performSearch = async () => {
  const query = searchQuery.value.trim()
  if (!query) {
    searchResults.value = []
    return
  }

  isSearching.value = true
  try {
    const res = await getArticleList({
      current: 1,
      size: 8,
      keyword: query
    })
    searchResults.value = res.records
    selectedIndex.value = -1
  } finally {
    isSearching.value = false
  }
}

// 防抖搜索
let searchTimeout: ReturnType<typeof setTimeout> | null = null
const debouncedSearch = () => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(performSearch, 300)
}

// 处理搜索输入
watch(searchQuery, () => {
  debouncedSearch()
})

// 处理键盘导航
const handleKeydown = (e: KeyboardEvent) => {
  if (!isSearchOpen.value) return

  switch (e.key) {
    case 'Escape':
      isSearchOpen.value = false
      break
    case 'ArrowDown':
      e.preventDefault()
      selectedIndex.value = Math.min(selectedIndex.value + 1, searchResults.value.length - 1)
      break
    case 'ArrowUp':
      e.preventDefault()
      selectedIndex.value = Math.max(selectedIndex.value - 1, -1)
      break
    case 'Enter':
      e.preventDefault()
      if (selectedIndex.value >= 0 && searchResults.value[selectedIndex.value]) {
        goToArticle(searchResults.value[selectedIndex.value])
      } else if (searchQuery.value.trim()) {
        router.push(`/article?keyword=${encodeURIComponent(searchQuery.value.trim())}`)
        closeSearch()
      }
      break
  }
}

// 跳转到文章
const goToArticle = (article: Article) => {
  router.push(`/article/${article.slug}`)
  closeSearch()
}

// 关闭搜索
const closeSearch = () => {
  isSearchOpen.value = false
  searchQuery.value = ''
  searchResults.value = []
  selectedIndex.value = -1
}

// 打开搜索时聚焦输入框
watch(isSearchOpen, (open) => {
  if (open) {
    nextTick(() => {
      searchInputRef.value?.focus()
    })
  }
})

// 滚动到顶部
const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll, { passive: true })
  window.addEventListener('keydown', handleKeydown)
  configStore.loadConfig()
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
  window.removeEventListener('keydown', handleKeydown)
  if (searchTimeout) clearTimeout(searchTimeout)
})
</script>

<template>
  <div>
    <header
      class="fixed left-0 right-0 top-0 z-50 transition-all duration-300"
      :class="{
        'py-3': !isScrolled,
        'py-2': isScrolled,
      }"
    >
      <!-- 滚动进度条 -->
      <div
        class="absolute bottom-0 left-0 h-[2px] bg-gradient-to-r from-primary to-primary-light transition-all duration-300"
        :style="{ width: `${scrollProgress}%` }"
      />

      <!-- 主导航容器 -->
      <div
        class="mx-auto max-w-7xl px-4 transition-all duration-300 sm:px-6 lg:px-8"
        :class="{
          'mt-4': !isScrolled,
          'mt-0': isScrolled,
        }"
      >
        <nav
          class="relative flex h-16 items-center justify-between rounded-2xl px-6 transition-all duration-300"
          :class="{
            'glass-card': isScrolled,
            'bg-transparent': !isScrolled,
          }"
        >
          <!-- Logo -->
          <router-link
            to="/"
            class="group flex items-center gap-3 transition-transform duration-200 hover:scale-105"
            @click="scrollToTop"
          >
            <div
              class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary-light text-white shadow-lg transition-all duration-200"
            >
              <el-icon class="text-xl"><Document /></el-icon>
            </div>
            <span class="text-xl font-bold text-content-primary">
              {{ configStore.siteName || 'Nanmuli' }}
            </span>
          </router-link>

          <!-- Desktop Navigation -->
          <div class="hidden items-center gap-1 md:flex">
            <router-link
              v-for="item in navItems"
              :key="item.path"
              :to="item.path"
              class="group relative px-4 py-2 text-sm font-medium transition-all duration-200"
              :class="isActive(item.path)
                ? 'text-primary'
                : 'text-content-secondary hover:text-content-primary'
              "
            >
              <span class="relative z-10">{{ item.label }}</span>
              <!-- 激活指示器 -->
              <span
                class="absolute inset-0 rounded-xl transition-all duration-200"
                :class="isActive(item.path)
                  ? 'bg-primary/10 scale-100'
                  : 'bg-surface-tertiary scale-0 group-hover:scale-100'
                "
              />
              <!-- 下划线动画 -->
              <span
                class="absolute bottom-0 left-1/2 h-0.5 w-0 -translate-x-1/2 rounded-full bg-primary transition-all duration-200 group-hover:w-1/2"
                :class="{ 'w-1/2': isActive(item.path) }"
              />
            </router-link>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-2">
            <!-- 搜索按钮 -->
            <button
              class="flex h-10 w-10 items-center justify-center rounded-xl text-content-tertiary transition-all duration-200 hover:bg-surface-tertiary hover:text-content-primary"
              aria-label="搜索"
              @click="isSearchOpen = true"
            >
              <el-icon class="text-lg"><Search /></el-icon>
            </button>

            <!-- 主题切换 -->
            <ThemeSwitcher />

            <!-- 管理后台入口 -->
            <router-link
              to="/admin"
              class="hidden items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-primary-light px-4 py-2 text-sm font-medium text-white shadow-lg transition-all duration-200 hover:shadow-xl hover:-translate-y-0.5 sm:flex"
            >
              <el-icon><Setting /></el-icon>
              <span>管理</span>
            </router-link>

            <!-- Mobile Menu Button -->
            <button
              class="flex h-10 w-10 items-center justify-center rounded-xl text-content-tertiary transition-all duration-200 hover:bg-surface-tertiary md:hidden"
              :class="{ 'bg-surface-tertiary': isMobileMenuOpen }"
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
          class="fixed inset-0 z-50 flex items-start justify-center bg-black/60 backdrop-blur-md pt-[15vh]"
          @click="closeSearch"
        >
          <div
            class="w-full max-w-2xl mx-4 transform rounded-2xl bg-surface-primary border border-border shadow-2xl overflow-hidden transition-all"
            @click.stop
          >
            <!-- Search Input -->
            <div class="relative border-b border-border">
              <el-icon class="absolute left-5 top-1/2 -translate-y-1/2 text-2xl text-content-tertiary">
                <Search />
              </el-icon>
              <input
                ref="searchInputRef"
                v-model="searchQuery"
                type="text"
                placeholder="搜索文章标题、内容..."
                class="w-full py-5 pl-14 pr-24 text-lg bg-transparent text-content-primary placeholder:text-content-tertiary/50 focus:outline-none"
              />
              <div class="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
                <!-- Clear Button -->
                <button
                  v-if="searchQuery"
                  class="p-1.5 rounded-lg text-content-tertiary hover:bg-surface-tertiary hover:text-content-secondary transition-colors"
                  @click="searchQuery = ''"
                >
                  <el-icon><Close /></el-icon>
                </button>
                <!-- Shortcut Hint -->
                <span class="hidden sm:flex items-center gap-1 px-2 py-1 rounded-md bg-surface-tertiary text-xs text-content-tertiary">
                  ESC
                </span>
              </div>
            </div>

            <!-- Search Results -->
            <div class="max-h-[60vh] overflow-y-auto">
              <!-- Loading State -->
              <div v-if="isSearching" class="py-12 flex flex-col items-center justify-center">
                <el-icon class="text-3xl text-primary animate-spin">
                  <Loading />
                </el-icon>
                <span class="mt-3 text-sm text-content-tertiary">搜索中...</span>
              </div>

              <!-- Results List -->
              <div v-else-if="searchResults.length > 0" class="py-2">
                <div class="px-4 py-2 text-xs text-content-tertiary uppercase tracking-wider">
                  找到 {{ searchResults.length }} 篇文章
                </div>
                <div
                  v-for="(article, index) in searchResults"
                  :key="article.id"
                  class="mx-2 px-4 py-3 rounded-xl cursor-pointer transition-all"
                  :class="selectedIndex === index ? 'bg-primary/10 border border-primary/20' : 'hover:bg-surface-tertiary border border-transparent'"
                  @click="goToArticle(article)"
                  @mouseenter="selectedIndex = index"
                >
                  <div class="flex items-start gap-3">
                    <!-- Article Cover or Icon -->
                    <div class="w-12 h-12 rounded-lg bg-surface-tertiary flex-shrink-0 overflow-hidden">
                      <img
                        v-if="article.cover"
                        :src="article.cover"
                        class="w-full h-full object-cover"
                        alt=""
                      />
                      <div v-else class="w-full h-full flex items-center justify-center">
                        <el-icon class="text-content-tertiary"><Document /></el-icon>
                      </div>
                    </div>
                    <!-- Article Info -->
                    <div class="flex-1 min-w-0">
                      <h4 class="font-medium text-content-primary truncate">
                        {{ article.title }}
                      </h4>
                      <p class="mt-1 text-sm text-content-secondary line-clamp-1">
                        {{ article.summary || '暂无摘要' }}
                      </p>
                      <div class="mt-1.5 flex items-center gap-3 text-xs text-content-tertiary">
                        <span class="flex items-center gap-1">
                          <el-icon class="text-xs"><Calendar /></el-icon>
                          {{ new Date(article.publishTime).toLocaleDateString('zh-CN') }}
                        </span>
                        <span class="flex items-center gap-1">
                          <el-icon class="text-xs"><View /></el-icon>
                          {{ article.viewCount }} 阅读
                        </span>
                      </div>
                    </div>
                    <!-- Arrow Icon for selected -->
                    <el-icon
                      v-if="selectedIndex === index"
                      class="text-primary self-center"
                    >
                      <ArrowRight />
                    </el-icon>
                  </div>
                </div>
              </div>

              <!-- No Results -->
              <div v-else-if="searchQuery && !isSearching" class="py-12 flex flex-col items-center justify-center">
                <div class="w-16 h-16 rounded-full bg-surface-tertiary flex items-center justify-center mb-4">
                  <el-icon class="text-2xl text-content-tertiary"><DocumentDelete /></el-icon>
                </div>
                <p class="text-content-secondary">未找到相关文章</p>
                <p class="mt-1 text-sm text-content-tertiary">换个关键词试试吧</p>
              </div>

              <!-- Empty State (Initial) -->
              <div v-else class="py-10 px-6">
                <div class="text-center">
                  <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/10 mb-4">
                    <el-icon class="text-2xl text-primary"><Search /></el-icon>
                  </div>
                  <h4 class="text-content-primary font-medium">搜索文章</h4>
                  <p class="mt-1 text-sm text-content-secondary">输入关键词查找感兴趣的内容</p>
                </div>
                <!-- Quick Tips -->
                <div class="mt-6 flex flex-wrap justify-center gap-2">
                  <button
                    v-for="tag in ['Vue', 'Spring Boot', '数据库', '前端']"
                    :key="tag"
                    class="px-3 py-1.5 rounded-full text-sm bg-surface-tertiary text-content-secondary hover:bg-primary/10 hover:text-primary transition-colors"
                    @click="searchQuery = tag; performSearch()"
                  >
                    {{ tag }}
                  </button>
                </div>
              </div>

              <!-- Footer -->
              <div v-if="searchResults.length > 0" class="px-4 py-3 border-t border-border bg-surface-secondary/50">
                <div class="flex items-center justify-between text-xs text-content-tertiary">
                  <div class="flex items-center gap-3">
                    <span class="flex items-center gap-1">
                      <span class="px-1.5 py-0.5 rounded bg-surface-tertiary">↑↓</span>
                      选择
                    </span>
                    <span class="flex items-center gap-1">
                      <span class="px-1.5 py-0.5 rounded bg-surface-tertiary">↵</span>
                      打开
                    </span>
                  </div>
                  <button
                    class="text-primary hover:underline"
                    @click="router.push(`/article?keyword=${encodeURIComponent(searchQuery)}`); closeSearch()"
                  >
                    查看全部结果
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Mobile Menu Overlay -->
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-150 ease-in"
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
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="translate-x-full opacity-0"
        enter-to-class="translate-x-0 opacity-100"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="translate-x-0 opacity-100"
        leave-to-class="translate-x-full opacity-0"
      >
        <div
          v-if="isMobileMenuOpen"
          class="fixed right-0 top-0 z-50 h-full w-80 overflow-y-auto bg-surface-secondary/95 p-6 shadow-2xl backdrop-blur-2xl md:hidden"
        >
          <!-- Close Button -->
          <div class="mb-8 flex justify-end">
            <button
              class="flex h-10 w-10 items-center justify-center rounded-xl text-content-tertiary transition-colors hover:bg-surface-tertiary"
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
              class="group flex items-center gap-4 rounded-xl p-4 transition-all duration-200"
              :class="isActive(item.path)
                ? 'bg-primary/10 text-primary'
                : 'text-content-secondary hover:bg-surface-tertiary'
              "
              :style="{ animationDelay: `${index * 50}ms` }"
              @click="closeMobileMenu"
            >
              <div
                class="flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200"
                :class="isActive(item.path)
                  ? 'bg-gradient-to-br from-primary to-primary-light text-white'
                  : 'bg-surface-tertiary'
                "
              >
                <el-icon class="text-lg"><component :is="item.icon" /></el-icon>
              </div>
              <span class="text-lg font-medium">{{ item.label }}</span>
              <el-icon
                v-if="isActive(item.path)"
                class="ml-auto text-primary"
              >
                <ArrowRight />
              </el-icon>
            </router-link>
          </nav>

          <!-- Mobile Admin Link -->
          <div class="mt-8 border-t border-border pt-6">
            <router-link
              to="/admin"
              class="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-primary to-primary-light p-4 font-medium text-white shadow-lg"
              @click="closeMobileMenu"
            >
              <el-icon><Setting /></el-icon>
              <span>进入管理后台</span>
            </router-link>
          </div>
        </div>
      </Transition>
    </header>

    <!-- 占位符，防止内容被固定导航遮挡 -->
    <div class="h-24" />
  </div>
</template>
