<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getArticleList } from '@/api/article'
import { formatDate } from '@/utils/format'
import type { Article } from '@/types/article'

const router = useRouter()
const loading = ref(false)
const articles = ref<Article[]>([])

async function fetchArticles(): Promise<void> {
  loading.value = true
  try {
    const res = await getArticleList({ current: 1, size: 1000 })
    articles.value = res.records
  } finally {
    loading.value = false
  }
}

const groupedArticles = computed(() => {
  const groups: Record<string, Article[]> = {}
  articles.value.forEach((article) => {
    const year = new Date(article.publishTime).getFullYear().toString()
    if (!groups[year]) groups[year] = []
    groups[year].push(article)
  })
  return Object.entries(groups).sort((a, b) => Number(b[0]) - Number(a[0]))
})

onMounted(fetchArticles)
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
    <h1 class="mb-8 text-3xl font-bold text-gray-900">文章归档</h1>

    <div v-if="loading" class="space-y-4">
      <el-skeleton v-for="i in 3" :key="i" :rows="3" animated />
    </div>

    <div v-else class="space-y-8">
      <div v-for="[year, items] in groupedArticles" :key="year">
        <h2 class="mb-4 text-2xl font-bold text-gray-800">{{ year }}</h2>
        <div class="space-y-3">
          <div
            v-for="article in items"
            :key="article.id"
            class="flex cursor-pointer items-center justify-between rounded-lg border bg-white p-4 transition-colors hover:bg-gray-50"
            @click="router.push(`/article/${article.slug}`)"
          >
            <span class="font-medium text-gray-900">{{ article.title }}</span>
            <span class="text-sm text-gray-500">{{ formatDate(article.publishTime, 'MM-DD') }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
