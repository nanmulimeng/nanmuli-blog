<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getArticleList } from '@/api/article'
import { formatDateCN } from '@/utils/format'
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
  <div class="home-page">
    <!-- Hero Section -->
    <section class="bg-gradient-to-b from-primary-50 to-white py-20">
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

    <!-- Latest Articles Section -->
    <section class="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
      <div class="mb-8 flex items-center justify-between">
        <div>
          <h2 class="text-2xl font-bold text-gray-900">最新文章</h2>
          <p class="mt-1 text-sm text-gray-500">探索技术的无限可能</p>
        </div>
        <router-link
          to="/article"
          class="inline-flex items-center text-primary-600 font-medium hover:text-primary-700 transition-colors"
        >
          查看全部
          <el-icon class="ml-1"><ArrowRight /></el-icon>
        </router-link>
      </div>

      <div v-if="loading" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div v-for="i in 6" :key="i" class="bg-white rounded-xl p-6 border border-gray-100">
          <el-skeleton :rows="3" animated />
        </div>
      </div>

      <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <article
          v-for="article in articles"
          :key="article.id"
          class="group cursor-pointer bg-white rounded-xl border border-gray-100 p-6 shadow-sm transition-all duration-150 hover:shadow-lg hover:-translate-y-0.5"
          @click="navigateToArticle(article.slug)"
        >
          <div class="mb-4 flex items-center gap-3">
            <span class="rounded-full bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-600">
              {{ article.categoryName }}
            </span>
            <span v-if="article.isTop" class="text-amber-500 text-xs font-medium">置顶</span>
          </div>
          <h3 class="mb-3 text-lg font-semibold text-gray-900 line-clamp-2 group-hover:text-primary-600 transition-colors">
            {{ article.title }}
          </h3>
          <p class="mb-4 text-sm text-gray-600 line-clamp-2 leading-relaxed">
            {{ article.summary }}
          </p>
          <div class="flex items-center gap-4 text-sm text-gray-400">
            <span class="flex items-center gap-1">
              <el-icon><Calendar /></el-icon>
              {{ formatDateCN(article.publishTime) }}
            </span>
            <span class="flex items-center gap-1">
              <el-icon><View /></el-icon>
              {{ article.viewCount }}
            </span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>
