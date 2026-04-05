<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getArticleList } from '@/api/article'
import { getCategoryList, getLeafCategoryList } from '@/api/category'
import { formatDateCN } from '@/utils/format'
import type { Article } from '@/types/article'
import type { Category } from '@/types/category'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const articles = ref<Article[]>([])
const categoryTree = ref<Category[]>([])
const leafCategories = ref<Category[]>([])
const total = ref(0)
const searchKeyword = ref('')

const currentPage = ref(1)
const pageSize = ref(12)
const selectedCategory = ref<number | undefined>(undefined)
const sortBy = ref('newest')

const sortOptions = [
  { value: 'newest', label: '最新发布', icon: 'Calendar' },
  { value: 'oldest', label: '最早发布', icon: 'Clock' },
  { value: 'popular', label: '最多阅读', icon: 'View' }
]

// 从URL参数初始化
watch(() => route.query, (query) => {
  if (query.categoryId) {
    selectedCategory.value = Number(query.categoryId)
  }
  if (query.keyword) {
    searchKeyword.value = String(query.keyword)
  }
  fetchArticles()
}, { immediate: true })

// 扁平化叶子分类列表
const flatLeafCategories = computed(() => {
  const result: Category[] = []
  function traverse(list: Category[]) {
    list.forEach(item => {
      if (item.isLeaf) {
        result.push(item)
      }
      if (item.children?.length) {
        traverse(item.children)
      }
    })
  }
  traverse(categoryTree.value)
  return result.sort((a, b) => (a.sort || 0) - (b.sort || 0))
})

// 获取选中的分类名称
const selectedCategoryName = computed(() => {
  if (!selectedCategory.value) return '全部文章'
  const cat = flatLeafCategories.value.find(c => c.id === selectedCategory.value)
  return cat?.name || '全部文章'
})

async function fetchArticles(): Promise<void> {
  loading.value = true
  try {
    const res = await getArticleList({
      current: currentPage.value,
      size: pageSize.value,
      categoryId: selectedCategory.value,
      sort: sortBy.value,
      keyword: searchKeyword.value || undefined
    })
    articles.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function fetchCategories(): Promise<void> {
  categoryTree.value = await getCategoryList()
  leafCategories.value = await getLeafCategoryList()
}

function handleCategoryChange(categoryId: number | undefined): void {
  selectedCategory.value = categoryId
  currentPage.value = 1
  fetchArticles()
}

function handleSortChange(sort: string): void {
  sortBy.value = sort
  fetchArticles()
}

function handlePageChange(page: number): void {
  currentPage.value = page
  fetchArticles()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function clearSearch(): void {
  searchKeyword.value = ''
  fetchArticles()
}

onMounted(() => {
  fetchCategories()
})
</script>

<template>
  <div class="article-list-page">
    <!-- Page Header with Gradient -->
    <section class="relative overflow-hidden pt-20 pb-12">
      <!-- Background Decoration -->
      <div class="absolute inset-0 bg-gradient-to-br from-aurora-purple/10 via-aurora-pink/5 to-aurora-cyan/10" />
      <div class="absolute top-0 right-0 h-96 w-96 rounded-full bg-aurora-purple/20 blur-3xl" />
      <div class="absolute bottom-0 left-0 h-64 w-64 rounded-full bg-aurora-cyan/20 blur-3xl" />

      <div class="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <!-- Breadcrumb -->
        <nav class="mb-6 flex items-center gap-2 text-sm text-gray-500">
          <router-link to="/" class="hover:text-aurora-purple transition-colors">
            首页
          </router-link>
          <el-icon><ArrowRight class="text-xs" /></el-icon>
          <span class="text-gray-900 dark:text-white font-medium">文章</span>
        </nav>

        <!-- Title -->
        <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
          <div>
            <h1 class="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white">
              {{ selectedCategoryName }}
            </h1>
            <p class="mt-2 text-gray-600 dark:text-gray-400">
              共 <span class="text-aurora-purple font-semibold">{{ total }}</span> 篇技术文章
            </p>
          </div>

          <!-- Search Box -->
          <div class="relative w-full sm:w-auto">
            <input
              v-model="searchKeyword"
              type="text"
              placeholder="搜索文章..."
              class="input-glass w-full sm:w-72 pr-10"
              @keyup.enter="fetchArticles"
            />
            <el-icon class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
              <Search />
            </el-icon>
          </div>
        </div>
      </div>
    </section>

    <!-- Filter Bar -->
    <section class="sticky top-20 z-30">
      <div class="glass border-b-0 rounded-none py-4">
        <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <!-- Category Filter -->
            <div class="flex items-center gap-2 overflow-x-auto pb-2 lg:pb-0 scrollbar-hide">
              <button
                class="pill whitespace-nowrap"
                :class="selectedCategory === undefined ? 'pill-gradient' : 'pill-glass'"
                @click="handleCategoryChange(undefined)"
              >
                全部
              </button>
              <button
                v-for="cat in flatLeafCategories"
                :key="cat.id"
                class="pill whitespace-nowrap"
                :class="selectedCategory === cat.id ? 'pill-gradient' : 'pill-glass'"
                @click="handleCategoryChange(cat.id)"
              >
                {{ cat.name }}
              </button>
            </div>

            <!-- Sort Options -->
            <div class="flex items-center gap-2">
              <span class="text-sm text-gray-500 dark:text-gray-400">排序：</span>
              <div class="flex items-center gap-1 rounded-xl bg-gray-100 p-1 dark:bg-dark-700">
                <button
                  v-for="opt in sortOptions"
                  :key="opt.value"
                  class="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm transition-all"
                  :class="sortBy === opt.value
                    ? 'bg-white text-aurora-purple shadow-sm dark:bg-dark-600 dark:text-aurora-pink'
                    : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'"
                  @click="handleSortChange(opt.value)"
                >
                  <el-icon class="text-xs"><component :is="opt.icon" /></el-icon>
                  {{ opt.label }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Article Grid -->
    <section class="py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <!-- Search Result Info -->
        <div v-if="searchKeyword" class="mb-6 flex items-center gap-2">
          <span class="text-gray-600 dark:text-gray-400">
            搜索 "<span class="text-aurora-purple font-medium">{{ searchKeyword }}</span>" 的结果
          </span>
          <button
            class="text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            @click="clearSearch"
          >
            清除搜索
          </button>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <div v-for="i in 6" :key="i" class="glass-card h-80">
            <el-skeleton :rows="5" animated />
          </div>
        </div>

        <!-- Empty State -->
        <div v-else-if="articles.length === 0" class="flex flex-col items-center justify-center py-24">
          <div class="flex h-24 w-24 items-center justify-center rounded-full bg-gray-100 dark:bg-dark-700">
            <el-icon class="text-4xl text-gray-400">
              <Document />
            </el-icon>
          </div>
          <h3 class="mt-6 text-xl font-semibold text-gray-900 dark:text-white">暂无文章</h3>
          <p class="mt-2 text-gray-500 dark:text-gray-400">该分类下还没有文章，去看看其他内容吧</p>
          <button
            class="mt-6 btn-gradient"
            @click="handleCategoryChange(undefined)"
          >
            查看全部文章
          </button>
        </div>

        <!-- Articles -->
        <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <article
            v-for="(article, index) in articles"
            :key="article.id"
            class="group cursor-pointer overflow-hidden rounded-3xl bg-white shadow-card transition-all duration-500 hover:shadow-card-hover hover:-translate-y-2 dark:bg-dark-800"
            :style="{ animationDelay: `${index * 50}ms` }"
            @click="router.push(`/article/${article.slug}`)"
          >
            <!-- Cover Image -->
            <div class="relative aspect-[16/10] overflow-hidden">
              <img
                v-if="article.cover"
                :src="article.cover"
                :alt="article.title"
                class="h-full w-full object-cover transition-transform duration-700 group-hover:scale-110"
              />
              <div
                v-else
                class="flex h-full w-full items-center justify-center bg-gradient-to-br from-aurora-purple/20 to-aurora-pink/20"
              >
                <el-icon class="text-5xl text-aurora-purple/50">
                  <Document />
                </el-icon>
              </div>

              <!-- Top Badge -->
              <div v-if="article.isTop" class="absolute left-4 top-4">
                <span class="flex items-center gap-1 rounded-full bg-amber-500 px-3 py-1 text-xs font-medium text-white shadow-lg">
                  <el-icon><StarFilled /></el-icon>
                  置顶
                </span>
              </div>

              <!-- Category Badge -->
              <div class="absolute bottom-4 left-4">
                <span class="rounded-full bg-white/90 px-3 py-1 text-xs font-medium text-gray-700 shadow-sm backdrop-blur-sm dark:bg-dark-900/90 dark:text-gray-300">
                  {{ article.category?.name || article.categoryName }}
                </span>
              </div>
            </div>

            <!-- Content -->
            <div class="p-6">
              <h3 class="mb-3 text-lg font-semibold text-gray-900 line-clamp-2 transition-colors group-hover:text-aurora-purple dark:text-white dark:group-hover:text-aurora-pink">
                {{ article.title }}
              </h3>

              <p class="mb-4 text-sm text-gray-600 line-clamp-2 leading-relaxed dark:text-gray-400">
                {{ article.summary }}
              </p>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3 text-xs text-gray-400">
                  <span class="flex items-center gap-1">
                    <el-icon><Calendar /></el-icon>
                    {{ formatDateCN(article.publishTime) }}
                  </span>
                  <span class="flex items-center gap-1">
                    <el-icon><View /></el-icon>
                    {{ article.viewCount }}
                  </span>
                </div>

                <!-- Tags -->
                <div v-if="article.tags?.length" class="flex gap-1">
                  <span
                    v-for="tag in article.tags.slice(0, 2)"
                    :key="tag"
                    class="rounded-full bg-aurora-purple/10 px-2 py-0.5 text-xs text-aurora-purple dark:bg-aurora-pink/10 dark:text-aurora-pink"
                  >
                    {{ tag }}
                  </span>
                </div>
              </div>
            </div>
          </article>
        </div>

        <!-- Pagination -->
        <div v-if="total > pageSize" class="mt-16 flex justify-center">
          <div class="flex items-center gap-2">
            <button
              :disabled="currentPage === 1"
              class="flex h-10 w-10 items-center justify-center rounded-xl border border-gray-200 text-gray-600 transition-all hover:border-aurora-purple hover:text-aurora-purple disabled:opacity-50 disabled:cursor-not-allowed dark:border-dark-600 dark:text-gray-400"
              @click="handlePageChange(currentPage - 1)"
            >
              <el-icon><ArrowLeft /></el-icon>
            </button>

            <div class="flex items-center gap-1">
              <button
                v-for="page in Math.ceil(total / pageSize)"
                :key="page"
                class="flex h-10 w-10 items-center justify-center rounded-xl text-sm font-medium transition-all"
                :class="currentPage === page
                  ? 'bg-gradient-to-r from-aurora-purple to-aurora-pink text-white'
                  : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-dark-700'"
                @click="handlePageChange(page)"
              >
                {{ page }}
              </button>
            </div>

            <button
              :disabled="currentPage >= Math.ceil(total / pageSize)"
              class="flex h-10 w-10 items-center justify-center rounded-xl border border-gray-200 text-gray-600 transition-all hover:border-aurora-purple hover:text-aurora-purple disabled:opacity-50 disabled:cursor-not-allowed dark:border-dark-600 dark:text-gray-400"
              @click="handlePageChange(currentPage + 1)"
            >
              <el-icon><ArrowRight /></el-icon>
            </button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
</style>
