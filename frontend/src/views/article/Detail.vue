<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getArticleBySlug } from '@/api/article'
import { formatDate, fromNow } from '@/utils/format'
import type { Article } from '@/types/article'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const article = ref<Article | null>(null)

async function fetchArticle(): Promise<void> {
  const slug = route.params.slug as string
  if (!slug) {
    router.push('/404')
    return
  }

  loading.value = true
  try {
    article.value = await getArticleBySlug(slug)
  } catch {
    router.push('/404')
  } finally {
    loading.value = false
  }
}

onMounted(fetchArticle)
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
    <div v-if="loading" class="space-y-4">
      <el-skeleton :rows="5" animated />
    </div>

    <article v-else-if="article" class="rounded-xl border bg-white p-8">
      <header class="mb-8 border-b pb-8">
        <div class="mb-4 flex items-center gap-2">
          <span
            v-if="article.isTop"
            class="rounded bg-primary-100 px-2 py-1 text-xs font-medium text-primary-700"
          >
            置顶
          </span>
          <span class="text-sm text-primary-600">{{ article.categoryName }}</span>
        </div>

        <h1 class="mb-4 text-3xl font-bold text-gray-900">{{ article.title }}</h1>

        <div class="flex flex-wrap items-center gap-4 text-sm text-gray-500">
          <span>{{ formatDate(article.publishTime) }}</span>
          <span>阅读 {{ article.viewCount }}</span>
          <span>{{ article.wordCount }} 字</span>
          <span>约 {{ article.readingTime }} 分钟</span>
        </div>

        <div v-if="article.tags?.length" class="mt-4 flex flex-wrap gap-2">
          <span
            v-for="tag in article.tags"
            :key="tag.id"
            class="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600"
          >
            {{ tag.name }}
          </span>
        </div>
      </header>

      <div class="markdown-body" v-html="article.contentHtml" />

      <footer class="mt-8 border-t pt-8">
        <div class="flex items-center justify-between">
          <div class="text-sm text-gray-500">
            最后更新于 {{ fromNow(article.updateTime) }}
          </div>
          <div class="flex gap-4">
            <button class="flex items-center gap-1 text-gray-600 hover:text-primary-600">
              <el-icon><Share /></el-icon>
              <span>分享</span>
            </button>
          </div>
        </div>
      </footer>
    </article>
  </div>
</template>
