# Nanmuli Blog - 页面实现示例

本文档提供各页面的具体实现代码示例，基于 [UI设计系统](./ui-design-system.md)。

---

## 1. 首页实现 (views/home/Index.vue)

```vue
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getArticleList, getTopArticles } from '@/api/article'
import { getCategoryList } from '@/api/category'
import { getTagList } from '@/api/tag'
import { formatDateCN, fromNowCN } from '@/utils/format'
import type { Article } from '@/types/article'
import type { Category } from '@/types/category'
import type { Tag } from '@/types/tag'

const router = useRouter()
const loading = ref(false)
const articles = ref<Article[]>([])
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])

// 统计数据
const stats = computed(() => ({
  articles: 128,
  projects: 32,
  logs: 50,
  days: 365
}))

async function fetchArticles(): Promise<void> {
  loading.value = true
  try {
    const res = await getArticleList({ current: 1, size: 6 })
    articles.value = res.records
  } finally {
    loading.value = false
  }
}

async function fetchCategories(): Promise<void> {
  const res = await getCategoryList()
  categories.value = res.slice(0, 6)
}

async function fetchTags(): Promise<void> {
  const res = await getTagList()
  tags.value = res.slice(0, 8)
}

function navigateToArticle(slug: string): void {
  router.push(`/article/${slug}`)
}

function navigateToCategory(slug: string): void {
  router.push(`/category/${slug}`)
}

onMounted(() => {
  fetchArticles()
  fetchCategories()
  fetchTags()
})
</script>

<template>
  <div class="home-page">
    <!-- Hero Section -->
    <section class="relative overflow-hidden bg-gradient-to-b from-primary-50 to-white py-20 md:py-28">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <h1 class="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl md:text-6xl">
          记录技术成长
        </h1>
        <p class="mx-auto mt-6 max-w-2xl text-lg text-gray-600 md:text-xl">
          分享学习心得，探索技术边界，在代码的世界里不断前行
        </p>
        
        <div class="mt-10 flex flex-col sm:flex-row justify-center gap-4">
          <router-link
            to="/article"
            class="inline-flex items-center justify-center h-12 px-8 rounded-lg bg-primary-600 text-white font-medium transition-all duration-150 hover:bg-primary-700 active:scale-[0.98]"
          >
            <el-icon class="mr-2"><Document /></el-icon>
            浏览文章
          </router-link>
          
          <router-link
            to="/daily-log"
            class="inline-flex items-center justify-center h-12 px-8 rounded-lg border border-gray-300 bg-white text-gray-700 font-medium transition-all duration-150 hover:bg-gray-50 active:scale-[0.98]"
          >
            <el-icon class="mr-2"><Timer /></el-icon>
            技术日志
          </router-link>
        </div>
      </div>
    </section>

    <!-- Stats Section -->
    <section class="border-y border-gray-100 bg-white py-8">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-2 gap-8 md:grid-cols-4">
          <div class="text-center">
            <div class="text-3xl font-bold text-primary-600">{{ stats.articles }}</div>
            <div class="mt-1 text-sm text-gray-500">文章</div>
          </div>
          <div class="text-center">
            <div class="text-3xl font-bold text-primary-600">{{ stats.projects }}</div>
            <div class="mt-1 text-sm text-gray-500">项目</div>
          </div>
          <div class="text-center">
            <div class="text-3xl font-bold text-primary-600">{{ stats.logs }}</div>
            <div class="mt-1 text-sm text-gray-500">日志</div>
          </div>
          <div class="text-center">
            <div class="text-3xl font-bold text-primary-600">{{ stats.days }}</div>
            <div class="mt-1 text-sm text-gray-500">天</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Latest Articles Section -->
    <section class="py-16 md:py-20">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <!-- Section Header -->
        <div class="mb-10 flex items-center justify-between">
          <div>
            <h2 class="text-2xl font-bold text-gray-900 md:text-3xl">最新文章</h2>
            <p class="mt-2 text-gray-500">探索技术的无限可能</p>
          </div>
          <router-link 
            to="/article" 
            class="inline-flex items-center text-primary-600 font-medium hover:text-primary-700 transition-colors"
          >
            查看全部
            <el-icon class="ml-1"><ArrowRight /></el-icon>
          </router-link>
        </div>

        <!-- Loading State -->
        <div v-if="loading" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <div v-for="i in 6" :key="i" class="bg-white rounded-xl p-6 border border-gray-100">
            <el-skeleton :rows="3" animated />
          </div>
        </div>

        <!-- Article Grid -->
        <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <article
            v-for="article in articles"
            :key="article.id"
            class="group cursor-pointer bg-white rounded-xl border border-gray-100 p-6 shadow-sm transition-all duration-150 hover:shadow-lg hover:-translate-y-0.5"
            @click="navigateToArticle(article.slug)"
          >
            <!-- Meta -->
            <div class="mb-4 flex items-center gap-3">
              <span class="rounded-full bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-600">
                {{ article.categoryName }}
              </span>
              <span class="text-sm text-gray-400">{{ formatDateCN(article.publishTime) }}</span>
              <span v-if="article.isTop" class="text-amber-500 text-xs font-medium">置顶</span>
            </div>

            <!-- Title -->
            <h3 class="mb-3 text-lg font-semibold text-gray-900 line-clamp-2 group-hover:text-primary-600 transition-colors">
              {{ article.title }}
            </h3>

            <!-- Summary -->
            <p class="mb-4 text-sm text-gray-600 line-clamp-2 leading-relaxed">
              {{ article.summary }}
            </p>

            <!-- Footer -->
            <div class="flex items-center justify-between text-sm text-gray-400">
              <div class="flex items-center gap-4">
                <span class="flex items-center gap-1">
                  <el-icon><View /></el-icon>
                  {{ article.viewCount }}
                </span>
                <span class="flex items-center gap-1">
                  <el-icon><Clock /></el-icon>
                  {{ article.readingTime }}分钟
                </span>
              </div>
            </div>
          </article>
        </div>
      </div>
    </section>

    <!-- Categories Section -->
    <section class="border-t border-gray-100 bg-gray-50/50 py-16">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div class="mb-10 text-center">
          <h2 class="text-2xl font-bold text-gray-900">热门分类</h2>
          <p class="mt-2 text-gray-500">按主题探索文章</p>
        </div>

        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="category in categories"
            :key="category.id"
            class="group cursor-pointer bg-white rounded-xl p-6 border border-gray-100 shadow-sm transition-all duration-150 hover:shadow-md"
            @click="navigateToCategory(category.slug)"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div 
                  class="w-10 h-10 rounded-lg flex items-center justify-center text-white"
                  :style="{ backgroundColor: category.color || '#0284c7' }"
                >
                  <el-icon><Folder /></el-icon>
                </div>
                <div>
                  <h3 class="font-semibold text-gray-900">{{ category.name }}</h3>
                  <p class="text-sm text-gray-500">{{ category.articleCount }} 篇文章</p>
                </div>
              </div>
              <el-icon class="text-gray-300 group-hover:text-primary-600 transition-colors">
                <ArrowRight />
              </el-icon>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Tags Cloud Section -->
    <section class="py-16">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div class="mb-10 text-center">
          <h2 class="text-2xl font-bold text-gray-900">热门标签</h2>
          <p class="mt-2 text-gray-500">发现感兴趣的技术话题</p>
        </div>

        <div class="flex flex-wrap justify-center gap-3">
          <router-link
            v-for="tag in tags"
            :key="tag.id"
            :to="`/tag/${tag.slug}`"
            class="inline-flex items-center px-4 py-2 rounded-full bg-white border border-gray-200 text-sm text-gray-700 transition-all duration-150 hover:border-primary-300 hover:text-primary-600"
            :style="{ fontSize: `${Math.max(0.875, Math.min(1.25, tag.articleCount / 10 + 0.8))}rem` }"
          >
            {{ tag.name }}
            <span class="ml-1.5 text-gray-400">{{ tag.articleCount }}</span>
          </router-link>
        </div>
      </div>
    </section>
  </div>
</template>
```

---

## 2. 文章列表页实现 (views/article/List.vue)

```vue
<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getArticleList } from '@/api/article'
import { getCategoryList } from '@/api/category'
import { formatDateCN } from '@/utils/format'
import type { Article } from '@/types/article'
import type { Category } from '@/types/category'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const articles = ref<Article[]>([])
const categories = ref<Category[]>([])
const total = ref(0)

const currentPage = ref(1)
const pageSize = ref(12)
const selectedCategory = ref('')
const sortBy = ref('newest')

const sortOptions = [
  { value: 'newest', label: '最新发布' },
  { value: 'oldest', label: '最早发布' },
  { value: 'popular', label: '最多阅读' }
]

async function fetchArticles(): Promise<void> {
  loading.value = true
  try {
    const res = await getArticleList({
      current: currentPage.value,
      size: pageSize.value,
      categoryId: selectedCategory.value || undefined,
      sortBy: sortBy.value
    })
    articles.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function fetchCategories(): Promise<void> {
  const res = await getCategoryList()
  categories.value = [{ id: '', name: '全部' }, ...res]
}

function handleCategoryChange(categoryId: string): void {
  selectedCategory.value = categoryId
  currentPage.value = 1
  fetchArticles()
}

function handleSortChange(value: string): void {
  sortBy.value = value
  fetchArticles()
}

function handlePageChange(page: number): void {
  currentPage.value = page
  fetchArticles()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  fetchCategories()
  fetchArticles()
})
</script>

<template>
  <div class="article-list-page">
    <!-- Page Header -->
    <section class="bg-gray-50 py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <h1 class="text-3xl font-bold text-gray-900">文章</h1>
        <p class="mt-2 text-gray-500">共 {{ total }} 篇技术文章</p>
      </div>
    </section>

    <!-- Filter Bar -->
    <section class="sticky top-16 z-40 border-b border-gray-200 bg-white/95 backdrop-blur-md">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-4">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <!-- Category Filter -->
          <div class="flex items-center gap-2 overflow-x-auto pb-2 sm:pb-0 scrollbar-hide">
            <button
              v-for="cat in categories"
              :key="cat.id"
              class="px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all duration-150"
              :class="selectedCategory === cat.id 
                ? 'bg-primary-50 text-primary-600' 
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'"
              @click="handleCategoryChange(cat.id)"
            >
              {{ cat.name }}
            </button>
          </div>

          <!-- Sort Options -->
          <div class="flex items-center gap-2">
            <span class="text-sm text-gray-500">排序：</span>
            <select
              v-model="sortBy"
              class="h-9 px-3 rounded-lg border border-gray-300 bg-white text-sm text-gray-700 focus:border-primary-500 focus:outline-none"
              @change="handleSortChange(sortBy)"
            >
              <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
        </div>
      </div>
    </section>

    <!-- Article Grid -->
    <section class="py-8">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <!-- Loading -->
        <div v-if="loading" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <div v-for="i in 6" :key="i" class="bg-white rounded-xl p-6 border border-gray-100">
            <el-skeleton :rows="3" animated />
          </div>
        </div>

        <!-- Empty State -->
        <div v-else-if="articles.length === 0" class="flex flex-col items-center justify-center py-20">
          <el-icon :size="64" class="text-gray-200 mb-4">
            <Document />
          </el-icon>
          <p class="text-gray-500">暂无文章</p>
        </div>

        <!-- Articles -->
        <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <article
            v-for="article in articles"
            :key="article.id"
            class="group cursor-pointer bg-white rounded-xl border border-gray-100 p-6 shadow-sm transition-all duration-150 hover:shadow-lg"
            @click="$router.push(`/article/${article.slug}`)"
          >
            <div class="mb-4 flex items-center gap-3">
              <span class="rounded-full bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-600">
                {{ article.categoryName }}
              </span>
              <span class="text-sm text-gray-400">{{ formatDateCN(article.publishTime) }}</span>
            </div>

            <h3 class="mb-3 text-lg font-semibold text-gray-900 line-clamp-2 group-hover:text-primary-600 transition-colors">
              {{ article.title }}
            </h3>

            <p class="mb-4 text-sm text-gray-600 line-clamp-2">
              {{ article.summary }}
            </p>

            <div class="flex items-center justify-between text-sm text-gray-400">
              <div class="flex items-center gap-4">
                <span class="flex items-center gap-1">
                  <el-icon><View /></el-icon> {{ article.viewCount }}
                </span>
              </div>
              <div v-if="article.tags?.length" class="flex gap-2">
                <span
                  v-for="tag in article.tags.slice(0, 2)"
                  :key="tag.id"
                  class="px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600"
                >
                  {{ tag.name }}
                </span>
              </div>
            </div>
          </article>
        </div>

        <!-- Pagination -->
        <div v-if="total > pageSize" class="mt-12 flex justify-center">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="total"
            layout="prev, pager, next"
            background
            @change="handlePageChange"
          />
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
```

---

## 3. 文章详情页实现 (views/article/Detail.vue)

```vue
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getArticleBySlug, getRelatedArticles } from '@/api/article'
import { formatDateCN } from '@/utils/format'
import { renderMarkdown } from '@/utils/markdown'
import type { Article } from '@/types/article'

const route = useRoute()
const router = useRouter()

const article = ref<Article | null>(null)
const relatedArticles = ref<Article[]>([])
const loading = ref(false)
const toc = ref<Array<{ id: string; text: string; level: number }>>([])

const articleHtml = computed(() => {
  if (!article.value?.content) return ''
  return renderMarkdown(article.value.content)
})

async function fetchArticle(): Promise<void> {
  loading.value = true
  try {
    const slug = route.params.slug as string
    const res = await getArticleBySlug(slug)
    article.value = res
    generateToc(res.content)
    fetchRelatedArticles(res.id)
  } finally {
    loading.value = false
  }
}

async function fetchRelatedArticles(articleId: number): Promise<void> {
  const res = await getRelatedArticles(articleId)
  relatedArticles.value = res.slice(0, 3)
}

function generateToc(content: string): void {
  // 从markdown内容提取标题生成目录
  const headings = content.match(/^#{1,3}\s+(.+)$/gm) || []
  toc.value = headings.map((heading, index) => {
    const level = heading.match(/^#+/)?.[0].length || 1
    const text = heading.replace(/^#+\s+/, '')
    return { id: `heading-${index}`, text, level }
  })
}

function scrollToHeading(index: number): void {
  const element = document.getElementById(`heading-${index}`)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth' })
  }
}

onMounted(fetchArticle)
</script>

<template>
  <div class="article-detail-page">
    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center min-h-[60vh]">
      <el-skeleton :rows="10" animated style="width: 100%; max-width: 680px;" />
    </div>

    <template v-else-if="article">
      <!-- Article Header -->
      <section class="pt-24 pb-12 bg-gradient-to-b from-primary-50/50 to-white">
        <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <!-- Category -->
          <div class="mb-6">
            <router-link
              :to="`/category/${article.categorySlug}`"
              class="inline-flex items-center px-3 py-1 rounded-full bg-primary-50 text-primary-600 text-sm font-medium hover:bg-primary-100 transition-colors"
            >
              {{ article.categoryName }}
            </router-link>
          </div>

          <!-- Title -->
          <h1 class="text-3xl md:text-4xl font-bold text-gray-900 leading-tight">
            {{ article.title }}
          </h1>

          <!-- Meta -->
          <div class="mt-6 flex flex-wrap items-center gap-4 text-sm text-gray-500">
            <span class="flex items-center gap-1">
              <el-icon><Calendar /></el-icon>
              {{ formatDateCN(article.publishTime) }}
            </span>
            <span class="flex items-center gap-1">
              <el-icon><View /></el-icon>
              阅读 {{ article.viewCount }}
            </span>
            <span class="flex items-center gap-1">
              <el-icon><Clock /></el-icon>
              {{ article.readingTime }}分钟
            </span>
            <span class="flex items-center gap-1">
              <el-icon><Document /></el-icon>
              {{ article.wordCount }}字
            </span>
          </div>

          <!-- Tags -->
          <div v-if="article.tags?.length" class="mt-6 flex flex-wrap gap-2">
            <router-link
              v-for="tag in article.tags"
              :key="tag.id"
              :to="`/tag/${tag.slug}`"
              class="px-3 py-1 rounded-full bg-gray-100 text-gray-600 text-sm hover:bg-primary-50 hover:text-primary-600 transition-colors"
            >
              {{ tag.name }}
            </router-link>
          </div>
        </div>
      </section>

      <!-- Article Content -->
      <section class="py-12">
        <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-12">
            <!-- Main Content -->
            <div class="lg:col-span-8">
              <article 
                class="markdown-body bg-white rounded-xl p-8 md:p-10 shadow-sm border border-gray-100"
                v-html="articleHtml"
              />
            </div>

            <!-- Sidebar TOC -->
            <div class="hidden lg:block lg:col-span-4">
              <div class="sticky top-24">
                <div class="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
                  <h3 class="text-sm font-semibold text-gray-900 mb-4">目录</h3>
                  <nav class="space-y-2">
                    <a
                      v-for="(item, index) in toc"
                      :key="index"
                      :href="`#heading-${index}`"
                      class="block text-sm transition-colors hover:text-primary-600"
                      :class="[
                        item.level === 1 ? 'text-gray-700 font-medium' : 'text-gray-500',
                        item.level === 2 ? 'pl-3' : '',
                        item.level === 3 ? 'pl-6' : ''
                      ]"
                      @click.prevent="scrollToHeading(index)"
                    >
                      {{ item.text }}
                    </a>
                  </nav>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Related Articles -->
      <section v-if="relatedArticles.length" class="py-12 bg-gray-50 border-t border-gray-100">
        <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <h2 class="text-xl font-bold text-gray-900 mb-8">相关文章</h2>
          
          <div class="grid gap-6 md:grid-cols-3">
            <article
              v-for="related in relatedArticles"
              :key="related.id"
              class="group cursor-pointer bg-white rounded-xl p-5 border border-gray-100 shadow-sm transition-all duration-150 hover:shadow-md"
              @click="$router.push(`/article/${related.slug}`)"
            >
              <span class="text-xs text-primary-600 font-medium">{{ related.categoryName }}</span>
              <h3 class="mt-2 text-base font-semibold text-gray-900 line-clamp-2 group-hover:text-primary-600 transition-colors">
                {{ related.title }}
              </h3>
              <p class="mt-2 text-sm text-gray-500 line-clamp-2">{{ related.summary }}</p>
            </article>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
```

---

## 4. 技术日志页实现 (views/dailyLog/List.vue)

```vue
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { getDailyLogList } from '@/api/dailyLog'
import { formatDateCN, formatMonthCN } from '@/utils/format'
import type { DailyLog } from '@/types/dailyLog'

const logs = ref<DailyLog[]>([])
const loading = ref(false)

// 按月份分组
const groupedLogs = computed(() => {
  const groups: Record<string, DailyLog[]> = {}
  logs.value.forEach(log => {
    const month = log.logDate.substring(0, 7) // YYYY-MM
    if (!groups[month]) {
      groups[month] = []
    }
    groups[month].push(log)
  })
  return groups
})

async function fetchLogs(): Promise<void> {
  loading.value = true
  try {
    const res = await getDailyLogList({ current: 1, size: 50 })
    logs.value = res.records
  } finally {
    loading.value = false
  }
}

const moodIcons: Record<string, string> = {
  happy: '😊',
  excited: '🤩',
  normal: '😐',
  tired: '😫'
}

onMounted(fetchLogs)
</script>

<template>
  <div class="daily-log-page">
    <!-- Page Header -->
    <section class="bg-gray-50 py-12">
      <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center">
        <h1 class="text-3xl font-bold text-gray-900">技术日志</h1>
        <p class="mt-2 text-gray-500">记录每日技术学习与思考</p>
      </div>
    </section>

    <!-- Timeline -->
    <section class="py-12">
      <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <!-- Loading -->
        <div v-if="loading" class="space-y-8">
          <div v-for="i in 3" :key="i" class="bg-white rounded-xl p-6 border border-gray-100">
            <el-skeleton :rows="2" animated />
          </div>
        </div>

        <!-- Empty -->
        <div v-else-if="logs.length === 0" class="text-center py-20">
          <el-icon :size="64" class="text-gray-200 mb-4"><Timer /></el-icon>
          <p class="text-gray-500">暂无日志</p>
        </div>

        <!-- Timeline Content -->
        <div v-else class="relative">
          <!-- Timeline Line -->
          <div class="absolute left-4 md:left-0 md:right-0 md:mx-auto md:w-0.5 h-full bg-gray-200"></div>

          <div v-for="(monthLogs, month) in groupedLogs" :key="month" class="mb-12">
            <!-- Month Header -->
            <div class="relative flex items-center justify-center mb-8">
              <div class="absolute left-0 right-0 h-px bg-gray-200"></div>
              <span class="relative px-4 bg-white text-lg font-semibold text-gray-900">
                {{ formatMonthCN(month) }}
              </span>
            </div>

            <!-- Log Items -->
            <div class="space-y-6">
              <div
                v-for="log in monthLogs"
                :key="log.id"
                class="relative pl-12 md:pl-0"
              >
                <!-- Timeline Dot -->
                <div class="absolute left-0 md:left-1/2 md:-translate-x-1/2 w-8 h-8 rounded-full bg-primary-100 border-2 border-primary-500 flex items-center justify-center z-10"
003e
                  <span class="text-sm">{{ moodIcons[log.mood] || '😐' }}</span>
                </div>

                <!-- Log Card -->
                <div class="md:w-[calc(50%-2rem)] md:ml-auto bg-white rounded-xl p-6 border border-gray-100 shadow-sm hover:shadow-md transition-shadow"
                :class="{'md:mr-auto md:ml-0': index % 2 === 1}"
              >
                <div class="flex items-center justify-between mb-3">
                  <span class="text-sm font-medium text-primary-600">{{ formatDateCN(log.logDate) }}</span>
                  <span v-if="log.weather" class="text-sm text-gray-400">{{ log.weather }}</span>
                </div>

                <div class="prose prose-sm max-w-none text-gray-700" v-html="log.contentHtml || log.content" />

                <div v-if="log.tags?.length" class="mt-4 flex flex-wrap gap-2">
                  <span
                    v-for="tag in log.tags"
                    :key="tag"
                    class="px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600"
                  >
                    {{ tag }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
```

---

## 5. 分类页实现 (views/category/Index.vue)

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getCategoryList } from '@/api/category'
import type { Category } from '@/types/category'

const router = useRouter()
const categories = ref<Category[]>([])
const loading = ref(false)

const categoryIcons: Record<string, string> = {
  backend: 'Cpu',
  frontend: 'Monitor',
  database: 'Coin',
  devops: 'SetUp',
  'daily-log': 'Timer',
  projects: 'OfficeBuilding'
}

async function fetchCategories(): Promise<void> {
  loading.value = true
  try {
    const res = await getCategoryList()
    categories.value = res
  } finally {
    loading.value = false
  }
}

onMounted(fetchCategories)
</script>

<template>
  <div class="category-page">
    <!-- Page Header -->
    <section class="bg-gray-50 py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <h1 class="text-3xl font-bold text-gray-900">文章分类</h1>
        <p class="mt-2 text-gray-500">按主题浏览文章</p>
      </div>
    </section>

    <!-- Categories Grid -->
    <section class="py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <!-- Loading -->
        <div v-if="loading" class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <div v-for="i in 6" :key="i" class="bg-white rounded-xl p-6 border border-gray-100">
            <el-skeleton :rows="2" animated />
          </div>
        </div>

        <!-- Categories -->
        <div v-else class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="category in categories"
            :key="category.id"
            class="group cursor-pointer bg-white rounded-xl p-6 border border-gray-100 shadow-sm transition-all duration-150 hover:shadow-lg hover:-translate-y-0.5"
            @click="router.push(`/category/${category.slug}`)"
          >
            <div class="flex items-start justify-between">
              <div class="flex items-center gap-4">
                <div
                  class="w-12 h-12 rounded-xl flex items-center justify-center text-white text-xl transition-transform duration-150 group-hover:scale-110"
                  :style="{ backgroundColor: category.color || '#0284c7' }"
                >
                  <el-icon>
                    <component :is="categoryIcons[category.slug] || 'Folder'" />
                  </el-icon>
                </div>
                <div>
                  <h3 class="text-lg font-semibold text-gray-900 group-hover:text-primary-600 transition-colors">
                    {{ category.name }}
                  </h3>
                  <p class="text-sm text-gray-500">{{ category.articleCount }} 篇文章</p>
                </div>
              </div>
              <el-icon class="text-gray-300 group-hover:text-primary-600 transition-colors">
                <ArrowRight />
              </el-icon>
            </div>

            <p v-if="category.description" class="mt-4 text-sm text-gray-600">
              {{ category.description }}
            </p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
```

---

## 6. 标签云页实现 (views/tag/Index.vue)

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getTagList } from '@/api/tag'
import type { Tag } from '@/types/tag'

const router = useRouter()
const tags = ref<Tag[]>([])
const loading = ref(false)

async function fetchTags(): Promise<void> {
  loading.value = true
  try {
    const res = await getTagList()
    tags.value = res
  } finally {
    loading.value = false
  }
}

// 计算标签大小 (0.875rem ~ 1.5rem)
function getTagSize(count: number): string {
  const maxCount = Math.max(...tags.value.map(t => t.articleCount), 1)
  const min = 0.875
  const max = 1.5
  const size = min + (count / maxCount) * (max - min)
  return `${size.toFixed(2)}rem`
}

onMounted(fetchTags)
</script>

<template>
  <div class="tag-page">
    <!-- Page Header -->
    <section class="bg-gray-50 py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <h1 class="text-3xl font-bold text-gray-900">标签云</h1>
        <p class="mt-2 text-gray-500">共 {{ tags.length }} 个标签，涵盖各种技术主题</p>
      </div>
    </section>

    <!-- Tag Cloud -->
    <section class="py-16">
      <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <!-- Loading -->
        <div v-if="loading" class="flex flex-wrap justify-center gap-3">
          <div v-for="i in 20" :key="i" class="h-10 w-24 bg-gray-100 rounded-full animate-pulse" />
        </div>

        <!-- Empty -->
        <div v-else-if="tags.length === 0" class="text-center py-20">
          <el-icon :size="64" class="text-gray-200 mb-4"><CollectionTag /></el-icon>
          <p class="text-gray-500">暂无标签</p>
        </div>

        <!-- Tags -->
        <div v-else class="flex flex-wrap justify-center gap-3">
          <button
            v-for="tag in tags"
            :key="tag.id"
            class="inline-flex items-center px-4 py-2 rounded-full bg-white border border-gray-200 font-medium transition-all duration-150 hover:border-primary-300 hover:text-primary-600 hover:shadow-sm"
            :style="{ fontSize: getTagSize(tag.articleCount) }"
            @click="router.push(`/tag/${tag.slug}`)"
          >
            {{ tag.name }}
            <span class="ml-1.5 text-gray-400 text-sm">{{ tag.articleCount }}</span>
          </button>
        </div>
      </div>
    </section>
  </div>
</template>
```

---

## 7. 项目展示页实现 (views/project/Index.vue)

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getProjectList } from '@/api/project'
import type { Project } from '@/types/project'

const projects = ref<Project[]>([])
const loading = ref(false)

async function fetchProjects(): Promise<void> {
  loading.value = true
  try {
    const res = await getProjectList()
    projects.value = res
  } finally {
    loading.value = false
  }
}

onMounted(fetchProjects)
</script>

<template>
  <div class="project-page">
    <!-- Page Header -->
    <section class="bg-gray-50 py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <h1 class="text-3xl font-bold text-gray-900">项目展示</h1>
        <p class="mt-2 text-gray-500">个人开源项目与作品</p>
      </div>
    </section>

    <!-- Projects Grid -->
    <section class="py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <!-- Loading -->
        <div v-if="loading" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <div v-for="i in 6" :key="i" class="bg-white rounded-xl overflow-hidden border border-gray-100">
            <div class="aspect-video bg-gray-100" />
            <div class="p-5">
              <el-skeleton :rows="2" animated />
            </div>
          </div>
        </div>

        <!-- Empty -->
        <div v-else-if="projects.length === 0" class="text-center py-20">
          <el-icon :size="64" class="text-gray-200 mb-4"><OfficeBuilding /></el-icon>
          <p class="text-gray-500">暂无项目</p>
        </div>

        <!-- Projects -->
        <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="project in projects"
            :key="project.id"
            class="group bg-white rounded-xl overflow-hidden border border-gray-100 shadow-sm transition-all duration-150 hover:shadow-lg"
          >
            <!-- Cover -->
            <div class="aspect-video bg-gray-100 relative overflow-hidden">
              <img
                v-if="project.cover"
                :src="project.cover"
                :alt="project.name"
                class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
              >
              <div v-else class="w-full h-full flex items-center justify-center text-gray-300">
                <el-icon :size="48"><OfficeBuilding /></el-icon>
              </div>
            </div>

            <!-- Content -->
            <div class="p-5">
              <h3 class="text-lg font-semibold text-gray-900 mb-2">{{ project.name }}</h3>
              
              <p class="text-sm text-gray-600 line-clamp-2 mb-4">
                {{ project.description }}
              </p>

              <!-- Tech Stack -->
              <div class="flex flex-wrap gap-2 mb-4">
                <span
                  v-for="tech in project.techStack?.slice(0, 4)"
                  :key="tech"
                  class="px-2 py-1 bg-gray-100 rounded text-xs text-gray-600"
                >
                  {{ tech }}
                </span>
              </div>

              <!-- Links -->
              <div class="flex gap-4">
                <a
                  v-if="project.demoUrl"
                  :href="project.demoUrl"
                  target="_blank"
                  class="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
                  @click.stop
                >
                  <el-icon><Link /></el-icon> 演示
                </a>
                <a
                  v-if="project.githubUrl"
                  :href="project.githubUrl"
                  target="_blank"
                  class="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1"
                  @click.stop
                >
                  <el-icon><Promotion /></el-icon> GitHub
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
```

---

## 8. 关于页实现 (views/about/Index.vue)

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConfigStore } from '@/stores/modules/config'
import { getSkillList } from '@/api/skill'
import type { Skill } from '@/types/skill'

const configStore = useConfigStore()
const skills = ref<Skill[]>([])

const experiences = [
  {
    period: '2024年 - 至今',
    title: '高级开发工程师',
    company: 'XXX科技有限公司',
    description: '负责核心业务系统架构设计与开发'
  },
  {
    period: '2022年 - 2024年',
    title: '中级开发工程师',
    company: 'YYY互联网公司',
    description: '参与电商平台后端开发'
  },
  {
    period: '2020年 - 2022年',
    title: '计算机科学硕士',
    company: 'ZZZ大学',
    description: '研究方向：分布式系统'
  }
]

async function fetchSkills(): Promise<void> {
  const res = await getSkillList()
  skills.value = res
}

// 技能分类
const skillCategories = [
  { key: 'language', name: '编程语言' },
  { key: 'framework', name: '框架' },
  { key: 'tool', name: '工具' },
  { key: 'other', name: '其他' }
]

onMounted(() => {
  fetchSkills()
  configStore.loadConfig()
})
</script>

<template>
  <div class="about-page">
    <!-- Profile Section -->
    <section class="pt-24 pb-12">
      <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center">
        <!-- Avatar -->
        <div class="relative inline-block">
          <div class="w-28 h-28 md:w-32 md:h-32 rounded-full overflow-hidden border-4 border-white shadow-lg">
            <img
              v-if="configStore.siteAvatar"
              :src="configStore.siteAvatar"
              alt="Avatar"
              class="w-full h-full object-cover"
            >
            <div v-else class="w-full h-full bg-primary-100 flex items-center justify-center">
              <el-icon :size="48" class="text-primary-600"><UserFilled /></el-icon>
            </div>
          </div>
        </div>

        <!-- Name & Title -->
        <h1 class="mt-6 text-2xl md:text-3xl font-bold text-gray-900">
          {{ configStore.siteAuthor || '博主' }}
        </h1>
        <p class="mt-2 text-gray-500">全栈开发工程师 | 技术博主</p>

        <!-- Social Links -->
        <div class="mt-6 flex justify-center gap-4">
          <a
            v-if="configStore.siteGithub"
            :href="configStore.siteGithub"
            target="_blank"
            class="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center text-gray-600 hover:bg-gray-200 transition-colors"
          >
            <el-icon><Promotion /></el-icon>
          </a>
          <a
            v-if="configStore.siteEmail"
            :href="`mailto:${configStore.siteEmail}`"
            class="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center text-gray-600 hover:bg-gray-200 transition-colors"
          >
            <el-icon><Message /></el-icon>
          </a>
        </div>
      </div>
    </section>

    <!-- Bio Section -->
    <section v-if="configStore.siteAbout" class="py-12">
      <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-xl font-bold text-gray-900 mb-6">关于我</h2>
        <div class="prose prose-gray max-w-none text-gray-600 leading-relaxed" v-html="configStore.siteAbout" />
      </div>
    </section>

    <!-- Skills Section -->
    <section class="py-12 bg-gray-50">
      <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-xl font-bold text-gray-900 mb-8">技能栈</h2>

        <div class="space-y-8">
          <div v-for="cat in skillCategories" :key="cat.key">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4">{{ cat.name }}</h3>
            
            <div class="grid gap-3 sm:grid-cols-2">
              <div
                v-for="skill in skills.filter(s => s.category === cat.key)"
                :key="skill.id"
                class="flex items-center gap-3 bg-white rounded-lg p-3"
              >
                <img v-if="skill.icon" :src="skill.icon" class="w-6 h-6" :alt="skill.name">
                <span class="flex-1 font-medium text-gray-900">{{ skill.name }}</span>
                
                <div class="flex gap-1">
                  <div
                    v-for="i in 5"
                    :key="i"
                    class="w-2 h-2 rounded-full"
                    :class="i <= skill.proficiency ? 'bg-primary-500' : 'bg-gray-200'"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Experience Timeline -->
    <section class="py-12">
      <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-xl font-bold text-gray-900 mb-8">经历</h2>

        <div class="relative border-l-2 border-gray-200 ml-3 space-y-8">
          <div v-for="(exp, index) in experiences" :key="index" class="relative pl-8">
            <div class="absolute -left-2 top-1 w-4 h-4 rounded-full bg-primary-500 border-2 border-white" />
            
            <div class="text-sm text-primary-600 font-medium">{{ exp.period }}</div>
            <h3 class="mt-1 text-lg font-semibold text-gray-900">{{ exp.title }}</h3>
            <div class="text-gray-500">{{ exp.company }}</div>
            <p class="mt-2 text-gray-600">{{ exp.description }}</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
```

---

## 9. 工具函数更新 (utils/format.ts)

```typescript
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

dayjs.locale('zh-cn')

/**
 * 格式化日期为中文格式：YYYY年M月D日
 */
export function formatDateCN(date: string | Date | undefined): string {
  if (!date) return '-'
  return dayjs(date).format('YYYY年M月D日')
}

/**
 * 格式化为短日期：M月D日
 */
export function formatShortDateCN(date: string | Date | undefined): string {
  if (!date) return '-'
  return dayjs(date).format('M月D日')
}

/**
 * 格式化月份：YYYY年M月
 */
export function formatMonthCN(date: string | undefined): string {
  if (!date) return '-'
  return dayjs(date).format('YYYY年M月')
}

/**
 * 格式化完整时间：YYYY年M月D日 HH:mm:ss
 */
export function formatDateTimeCN(date: string | Date | undefined): string {
  if (!date) return '-'
  return dayjs(date).format('YYYY年M月D日 HH:mm:ss')
}

/**
 * 相对时间：刚刚、5分钟前、2小时前、昨天、3天前...
 */
export function fromNowCN(date: string | Date | undefined): string {
  if (!date) return '-'
  
  const now = dayjs()
  const target = dayjs(date)
  const diffMinutes = now.diff(target, 'minute')
  const diffHours = now.diff(target, 'hour')
  const diffDays = now.diff(target, 'day')

  if (diffMinutes < 1) return '刚刚'
  if (diffMinutes < 60) return `${diffMinutes}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`
  
  return formatDateCN(date)
}

/**
 * 数字千分位分隔
 */
export function formatNumber(num: number | undefined): string {
  if (num === undefined || num === null) return '0'
  return num.toLocaleString('zh-CN')
}
```

---

> 文档版本: v1.0
> 最后更新: 2026年4月4日
> 维护者: nanmuli
