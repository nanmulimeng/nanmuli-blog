<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
const selectedCategory = ref<number | undefined>(undefined)
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
      categoryId: selectedCategory.value,
      sort: sortBy.value
    })
    articles.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function fetchCategories(): Promise<void> {
  const res = await getCategoryList()
  categories.value = res
}

function handleCategoryChange(categoryId: number | undefined): void {
  selectedCategory.value = categoryId
  currentPage.value = 1
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
              class="px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all duration-150"
              :class="selectedCategory === undefined
                ? 'bg-primary-50 text-primary-600'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'"
              @click="handleCategoryChange(undefined)"
            >
              全部
            </button>
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
            @click="router.push(`/article/${article.slug}`)"
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
            :current-page="currentPage"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next"
            background
            @current-change="handlePageChange"
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
