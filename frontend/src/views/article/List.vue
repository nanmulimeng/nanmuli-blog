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
const selectedCategory = ref<string | undefined>(undefined)
const sortBy = ref('newest')

const sortOptions = [
  { value: 'newest', label: '最新发布', icon: 'Calendar' },
  { value: 'oldest', label: '最早发布', icon: 'Clock' },
  { value: 'popular', label: '最多人看', icon: 'View' }
]

// 从URL参数初始化
watch(() => route.query, (query) => {
  if (query.categoryId) {
    selectedCategory.value = String(query.categoryId)
  }
  if (query.keyword) {
    searchKeyword.value = String(query.keyword)
  }
  fetchArticles()
}, { immediate: true })

// 获取父级分类列表（用于筛选）
const parentCategories = computed(() => {
  // 只返回父级分类（有子分类的节点），排除"日志"分类
  return categoryTree.value
        .filter(item => !item.isLeaf && item.children && item.children.length > 0 && item.name !== '日志' && item.name !== '项目展示')
    .sort((a, b) => (a.sort || 0) - (b.sort || 0))
})

// 获取选中的分类名称
const selectedCategoryName = computed(() => {
  if (!selectedCategory.value) return '全部文章'
  const cat = parentCategories.value.find((c: Category) => String(c.id) === String(selectedCategory.value))
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

function handleCategoryChange(categoryId: string | undefined): void {
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
      <div class="absolute inset-0 bg-gradient-to-br from-primary/10 via-surface-tertiary to-primary/5 dark:from-primary/10 dark:via-surface-secondary dark:to-primary/5" />
      <div class="absolute top-0 right-0 h-96 w-96 rounded-full bg-primary/15 blur-3xl dark:bg-primary/10" />
      <div class="absolute bottom-0 left-0 h-64 w-64 rounded-full bg-primary-light/15 blur-3xl dark:bg-primary/10" />

      <div class="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <!-- Breadcrumb -->
        <nav class="mb-6 flex items-center gap-2 text-sm text-content-tertiary">
          <router-link to="/" class="hover:text-primary transition-colors">
            首页
          </router-link>
          <el-icon><ArrowRight class="text-xs" /></el-icon>
          <span class="text-content-primary font-medium">文章</span>
        </nav>

        <!-- Title -->
        <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
          <div>
            <h1 class="text-4xl sm:text-5xl font-bold text-content-primary">
              {{ selectedCategoryName }}
            </h1>
            <p class="mt-2 text-content-secondary">
              共 <span class="text-primary font-semibold">{{ total }}</span> 篇技术文章
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
            <el-icon class="absolute right-3 top-1/2 -translate-y-1/2 text-content-tertiary">
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
                :class="selectedCategory === undefined ? 'pill-primary' : 'pill-secondary'"
                @click="handleCategoryChange(undefined)"
              >
                全部
              </button>
              <button
                v-for="cat in parentCategories"
                :key="cat.id"
                class="pill whitespace-nowrap"
                :class="String(selectedCategory) === String(cat.id) ? 'pill-primary' : 'pill-secondary'"
                @click="handleCategoryChange(String(cat.id))"
              >
                {{ cat.name }}
              </button>
            </div>

            <!-- Sort Options -->
            <div class="flex items-center gap-2">
              <span class="text-sm text-content-tertiary">排序：</span>
              <div class="flex items-center gap-1 rounded-xl bg-surface-tertiary p-1">
                <button
                  v-for="opt in sortOptions"
                  :key="opt.value"
                  class="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm transition-all"
                  :class="sortBy === opt.value
                    ? 'bg-surface-secondary text-primary shadow-sm'
                    : 'text-content-secondary hover:text-content-primary'"
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
          <span class="text-content-secondary">
            搜索 "<span class="text-primary font-medium">{{ searchKeyword }}</span>" 的结果
          </span>
          <button
            class="text-sm text-content-tertiary hover:text-content-secondary"
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
          <div class="flex h-24 w-24 items-center justify-center rounded-full bg-surface-tertiary">
            <el-icon class="text-4xl text-content-tertiary">
              <Document />
            </el-icon>
          </div>
          <h3 class="mt-6 text-xl font-semibold text-content-primary">暂无文章</h3>
          <p class="mt-2 text-content-secondary">该分类下还没有文章，去看看其他内容吧</p>
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
            class="group cursor-pointer overflow-hidden rounded-3xl bg-surface-secondary shadow-card transition-all duration-500 hover:shadow-card-hover hover:-translate-y-2"
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
                class="flex h-full w-full items-center justify-center bg-gradient-to-br from-blue-400/20 to-cyan-300/20 dark:from-cyan-500/20 dark:to-blue-400/20"
              >
                <el-icon class="text-5xl text-primary/50">
                  <Document />
                </el-icon>
              </div>

              <!-- Top Badge -->
              <div v-if="article.isTop" class="absolute left-4 top-4">
                <span class="flex items-center gap-1 rounded-full bg-warning px-3 py-1 text-xs font-medium text-white shadow-lg">
                  <el-icon><StarFilled /></el-icon>
                  置顶
                </span>
              </div>

              <!-- Category Badge -->
              <div class="absolute bottom-4 left-4 max-w-[80%]">
                <!-- 分类路径 -->
                <div v-if="article.categoryPath?.length" class="flex items-center gap-1 flex-wrap">
                  <span
                    v-for="(cat, index) in article.categoryPath"
                    :key="cat.id"
                    class="flex items-center gap-1"
                  >
                    <span
                      class="rounded-full px-2 py-1 text-xs font-medium shadow-sm backdrop-blur-sm"
                      :style="{
                        backgroundColor: cat.color ? cat.color + '90' : 'rgba(255,255,255,0.9)',
                        color: cat.color ? '#fff' : '#374151'
                      }"
                    >
                      {{ cat.name }}
                    </span>
                    <span
                      v-if="index < article.categoryPath.length - 1"
                      class="text-white/80 text-xs"
                    >/</span>
                  </span>
                </div>
                <span
                  v-else-if="article.category"
                  class="rounded-full px-3 py-1 text-xs font-medium shadow-sm backdrop-blur-sm"
                  :style="{
                    backgroundColor: article.category.color ? article.category.color + '90' : 'rgba(255,255,255,0.9)',
                    color: article.category.color ? '#fff' : '#374151'
                  }"
                >
                  {{ article.category.name }}
                </span>
                <span
                  v-else
                  class="rounded-full bg-surface-secondary/90 px-3 py-1 text-xs font-medium text-content-secondary shadow-sm backdrop-blur-sm"
                >
                  {{ article.categoryName }}
                </span>
              </div>
            </div>

            <!-- Content -->
            <div class="p-6">
              <h3 class="mb-3 text-lg font-semibold text-content-primary line-clamp-2 transition-colors group-hover:text-primary">
                {{ article.title }}
              </h3>

              <p class="mb-4 text-sm text-content-secondary line-clamp-2 leading-relaxed">
                {{ article.summary }}
              </p>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3 text-xs text-content-tertiary">
                  <span class="flex items-center gap-1">
                    <el-icon><Calendar /></el-icon>
                    {{ formatDateCN(article.publishTime) }}
                  </span>
                  <span class="flex items-center gap-1">
                    <el-icon><View /></el-icon>
                    {{ article.viewCount }} 人
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
              class="flex h-10 w-10 items-center justify-center rounded-xl border border-border text-content-secondary transition-all hover:border-primary hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed"
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
                  ? 'bg-primary text-white'
                  : 'text-content-secondary hover:bg-surface-tertiary'"
                @click="handlePageChange(page)"
              >
                {{ page }}
              </button>
            </div>

            <button
              :disabled="currentPage >= Math.ceil(total / pageSize)"
              class="flex h-10 w-10 items-center justify-center rounded-xl border border-border text-content-secondary transition-all hover:border-primary hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed"
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
