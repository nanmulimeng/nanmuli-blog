<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getTopArticles, getArticleList } from '@/api/article'
import { formatDate, fromNow } from '@/utils/format'
import type { Article } from '@/types/article'

const router = useRouter()
const loading = ref(false)
const articles = ref<Article[]>([])

async function fetchArticles(): Promise<void> {
  loading.value = true
  try {
    const res = await getArticleList({ current: 1, size: 6 })
    articles.value = res.records
  } finally {
    loading.value = false
  }
}

function navigateToArticle(slug: string): void {
  router.push(`/article/${slug}`)
}

onMounted(fetchArticles)
</script>

<template>
  <div class="bg-gradient-to-b from-primary-50 to-white py-20">
    <div class="mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8">
      <h1 class="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
        记录技术成长
      </h1>
      <p class="mx-auto mt-6 max-w-2xl text-lg text-gray-600">
        分享学习心得，探索技术边界，在代码的世界里不断前行
      </p>
      <div class="mt-10 flex justify-center gap-4">
        <router-link
          to="/article"
          class="rounded-lg bg-primary-600 px-6 py-3 font-medium text-white transition-colors hover:bg-primary-700"
        >
          浏览文章
        </router-link>
        <router-link
          to="/daily-log"
          class="rounded-lg border border-gray-300 bg-white px-6 py-3 font-medium text-gray-700 transition-colors hover:bg-gray-50"
        >
          技术日志
        </router-link>
      </div>
    </div>
  </div>

  <div class="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
    <div class="mb-8 flex items-center justify-between">
      <h2 class="text-2xl font-bold text-gray-900">最新文章</h2>
      <router-link to="/article" class="text-primary-600 hover:underline">
        查看全部 →
      </router-link>
    </div>

    <div v-if="loading" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <el-skeleton v-for="i in 6" :key="i" :rows="3" animated />
    </div>

    <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <article
        v-for="article in articles"
        :key="article.id"
        class="cursor-pointer rounded-xl border bg-white p-6 transition-shadow hover:shadow-lg"
        @click="navigateToArticle(article.slug)"
      >
        <div class="mb-4 flex items-center gap-2">
          <span
            v-if="article.isTop"
            class="rounded bg-primary-100 px-2 py-1 text-xs font-medium text-primary-700"
          >
            置顶
          </span>
          <span class="text-sm text-gray-500">{{ article.categoryName }}</span>
        </div>
        <h3 class="mb-2 text-xl font-semibold text-gray-900 line-clamp-2">
          {{ article.title }}
        </h3>
        <p class="mb-4 text-sm text-gray-600 line-clamp-2">
          {{ article.summary }}
        </p>
        <div class="flex items-center gap-4 text-xs text-gray-500">
          <span>{{ formatDate(article.publishTime) }}</span>
          <span>阅读 {{ article.viewCount }}</span>
          <span>{{ article.wordCount }} 字</span>
        </div>
      </article>
    </div>
  </div>
</template>
