<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getArticleList } from '@/api/article'
import { formatDate } from '@/utils/format'
import type { Article } from '@/types/article'

const router = useRouter()
const loading = ref(false)
const articles = ref<Article[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

async function fetchArticles(): Promise<void> {
  loading.value = true
  try {
    const res = await getArticleList({
      current: currentPage.value,
      size: pageSize.value,
    })
    articles.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handlePageChange(page: number): void {
  currentPage.value = page
  fetchArticles()
}

onMounted(fetchArticles)
</script>

<template>
  <div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
    <h1 class="mb-8 text-3xl font-bold text-gray-900">文章列表</h1>

    <div v-if="loading" class="space-y-6">
      <el-skeleton v-for="i in 5" :key="i" :rows="2" animated />
    </div>

    <div v-else class="space-y-6">
      <article
        v-for="article in articles"
        :key="article.id"
        class="flex gap-6 rounded-xl border bg-white p-6 transition-shadow hover:shadow-lg"
      >
        <div class="h-32 w-48 flex-shrink-0 overflow-hidden rounded-lg bg-gray-100">
          <img
            v-if="article.cover"
            :src="article.cover"
            :alt="article.title"
            class="h-full w-full object-cover"
          />
          <div v-else class="flex h-full items-center justify-center text-gray-400">
            <el-icon :size="48"><Picture /></el-icon>
          </div>
        </div>

        <div class="flex flex-1 flex-col">
          <div class="mb-2 flex items-center gap-2">
            <span
              v-if="article.isTop"
              class="rounded bg-primary-100 px-2 py-1 text-xs font-medium text-primary-700"
            >
              置顶
            </span>
            <span class="text-sm text-primary-600">{{ article.categoryName }}</span>
          </div>

          <h2
            class="mb-2 text-xl font-semibold text-gray-900 hover:text-primary-600"
            @click="router.push(`/article/${article.slug}`)"
          >
            {{ article.title }}
          </h2>

          <p class="mb-4 line-clamp-2 text-gray-600">{{ article.summary }}</p>

          <div class="mt-auto flex items-center gap-4 text-sm text-gray-500">
            <span>{{ formatDate(article.publishTime) }}</span>
            <span>阅读 {{ article.viewCount }}</span>
            <span>{{ article.wordCount }} 字</span>
            <span>约 {{ article.readingTime }} 分钟</span>
          </div>
        </div>
      </article>

      <div class="flex justify-center pt-6">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </div>
</template>
