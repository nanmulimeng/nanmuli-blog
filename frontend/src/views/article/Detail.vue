<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getArticleBySlug } from '@/api/article'
import { formatDateCN, formatDateTimeCN } from '@/utils/format'
import type { Article } from '@/types/article'

const route = useRoute()
const router = useRouter()

const article = ref<Article | null>(null)
const loading = ref(false)
const toc = ref<Array<{ id: string; text: string; level: number }>>([])

async function fetchArticle(): Promise<void> {
  const slug = route.params.slug as string
  if (!slug) {
    router.push('/404')
    return
  }

  loading.value = true
  try {
    const res = await getArticleBySlug(slug)
    article.value = res
    generateToc(res.content)
  } catch {
    router.push('/404')
  } finally {
    loading.value = false
  }
}

function generateToc(content: string): void {
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
      <div class="w-full max-w-2xl px-4">
        <el-skeleton :rows="10" animated />
      </div>
    </div>

    <template v-else-if="article">
      <!-- Article Header -->
      <section class="pt-24 pb-12 bg-gradient-to-b from-primary-50/50 to-white">
        <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <!-- Category -->
          <div class="mb-6">
            <router-link
              :to="`/article?category=${article.categoryId}`"
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
                class="markdown-body bg-white rounded-xl p-8 md:p-10 shadow-sm border border-gray-100 prose prose-gray max-w-none"
                v-html="article.contentHtml"
              />

              <!-- Article Footer -->
              <div class="mt-8 bg-white rounded-xl p-6 border border-gray-100">
                <div class="flex items-center justify-between">
                  <div class="text-sm text-gray-500">
                    最后更新于 {{ formatDateTimeCN(article.updateTime) }}
                  </div>
                  <div class="flex gap-4">
                    <button class="flex items-center gap-1 text-gray-600 hover:text-primary-600 transition-colors">
                      <el-icon><Share /></el-icon>
                      <span>分享</span>
                    </button>
                  </div>
                </div>
              </div>
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
    </template>
  </div>
</template>
