<script setup lang="ts">
import { ref, onMounted, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getArticleBySlug, recordArticleView, getArticleList } from '@/api/article'
import { formatDateCN, formatDateTimeCN } from '@/utils/format'
import type { Article } from '@/types/article'

const route = useRoute()
const router = useRouter()

const article = ref<Article | null>(null)
const relatedArticles = ref<Article[]>([])
const loading = ref(false)
const toc = ref<Array<{ id: string; text: string; level: number }>>([])
const activeHeading = ref('')
const copySuccess = ref(false)

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
    fetchRelatedArticles(res.categoryId, res.id)

    // 等待DOM更新后设置滚动监听
    nextTick(() => {
      setupScrollSpy()
    })
  } catch {
    router.push('/404')
  } finally {
    loading.value = false
  }
}

async function fetchRelatedArticles(categoryId: number, excludeId: number): Promise<void> {
  try {
    const res = await getArticleList({
      current: 1,
      size: 4,
      categoryId
    })
    relatedArticles.value = res.records.filter(a => a.id !== excludeId).slice(0, 3)
  } catch {
    // ignore
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
    const offset = 100
    const elementPosition = element.getBoundingClientRect().top
    const offsetPosition = elementPosition + window.pageYOffset - offset
    window.scrollTo({ top: offsetPosition, behavior: 'smooth' })
  }
}

// 设置滚动监听
function setupScrollSpy(): void {
  const headings = document.querySelectorAll('[id^="heading-"]')
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          activeHeading.value = entry.target.id
        }
      })
    },
    { rootMargin: '-100px 0px -60% 0px' }
  )
  headings.forEach((heading) => observer.observe(heading))
}

// 复制文章链接
function copyLink(): void {
  navigator.clipboard.writeText(window.location.href)
  copySuccess.value = true
  setTimeout(() => {
    copySuccess.value = false
  }, 2000)
}

// 分享
function shareArticle(platform: string): void {
  const url = encodeURIComponent(window.location.href)
  const title = encodeURIComponent(article.value?.title || '')

  const shareUrls: Record<string, string> = {
    twitter: `https://twitter.com/intent/tweet?url=${url}&text=${title}`,
    weibo: `https://service.weibo.com/share/share.php?url=${url}&title=${title}`,
  }

  if (shareUrls[platform]) {
    window.open(shareUrls[platform], '_blank', 'width=600,height=400')
  }
}

const readingProgress = computed(() => {
  if (typeof window === 'undefined') return 0
  const scrollTop = window.pageYOffset
  const docHeight = document.documentElement.scrollHeight - window.innerHeight
  return docHeight > 0 ? (scrollTop / docHeight) * 100 : 0
})

onMounted(() => {
  fetchArticle()
  setTimeout(() => {
    const slug = route.params.slug as string
    if (slug) {
      recordArticleView(slug)
    }
  }, 5000)
})
</script>

<template>
  <div class="article-detail-page">
    <!-- Reading Progress Bar -->
    <div
      class="fixed top-0 left-0 right-0 h-[3px] z-50 bg-gradient-to-r from-aurora-purple via-aurora-pink to-aurora-cyan transition-all duration-150"
      :style="{ width: `${readingProgress}%` }"
    />

    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center min-h-[60vh]">
      <div class="glass-card w-full max-w-2xl p-8">
        <el-skeleton :rows="10" animated />
      </div>
    </div>

    <template v-else-if="article">
      <!-- Article Hero Section -->
      <section class="relative pt-32 pb-16 overflow-hidden">
        <!-- Background Decoration -->
        <div class="absolute inset-0 bg-gradient-to-b from-aurora-purple/10 via-transparent to-transparent" />

        <div class="relative mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <!-- Breadcrumb -->
          <nav class="mb-8 flex items-center gap-2 text-sm text-gray-500">
            <router-link to="/" class="hover:text-aurora-purple transition-colors">
              首页
            </router-link>
            <el-icon><ArrowRight class="text-xs" /></el-icon>
            <router-link to="/article" class="hover:text-aurora-purple transition-colors">
              文章
            </router-link>
            <el-icon><ArrowRight class="text-xs" /></el-icon>
            <span class="text-gray-900 dark:text-white font-medium truncate max-w-[200px]">
              {{ article.title }}
            </span>
          </nav>

          <!-- Category Badge -->
          <div class="mb-6">
            <div v-if="article.categoryPath?.length" class="flex items-center gap-2 flex-wrap">
              <span
                v-for="(cat, index) in article.categoryPath"
                :key="cat.id"
                class="flex items-center gap-2"
              >
                <router-link
                  :to="`/article?categoryId=${cat.id}`"
                  class="text-sm transition-colors"
                  :class="index === article.categoryPath.length - 1
                    ? 'inline-flex items-center px-4 py-1.5 rounded-full bg-gradient-to-r from-aurora-purple to-aurora-pink text-white font-medium shadow-lg shadow-aurora-purple/30'
                    : 'text-gray-500 hover:text-aurora-purple'"
                >
                  {{ cat.name }}
                </router-link>
                <span v-if="index < article.categoryPath.length - 1" class="text-gray-300">/</span>
              </span>
            </div>
            <router-link
              v-else
              :to="`/article?categoryId=${article.categoryId}`"
              class="inline-flex items-center px-4 py-1.5 rounded-full bg-gradient-to-r from-aurora-purple to-aurora-pink text-white font-medium shadow-lg shadow-aurora-purple/30"
            >
              {{ article.category?.name || article.categoryName }}
            </router-link>
          </div>

          <!-- Title -->
          <h1 class="text-3xl md:text-4xl lg:text-5xl font-bold text-gray-900 dark:text-white leading-tight">
            {{ article.title }}
          </h1>

          <!-- Meta Info -->
          <div class="mt-8 flex flex-wrap items-center gap-6 text-sm">
            <span class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
              <div class="flex h-8 w-8 items-center justify-center rounded-full bg-aurora-purple/10">
                <el-icon class="text-aurora-purple"><Calendar /></el-icon>
              </div>
              {{ formatDateCN(article.publishTime) }}
            </span>
            <span class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
              <div class="flex h-8 w-8 items-center justify-center rounded-full bg-aurora-cyan/10">
                <el-icon class="text-aurora-cyan"><View /></el-icon>
              </div>
              {{ article.viewCount }} 阅读
            </span>
            <span class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
              <div class="flex h-8 w-8 items-center justify-center rounded-full bg-aurora-pink/10">
                <el-icon class="text-aurora-pink"><Clock /></el-icon>
              </div>
              {{ article.readingTime }}分钟
            </span>
            <span class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
              <div class="flex h-8 w-8 items-center justify-center rounded-full bg-green-500/10">
                <el-icon class="text-green-500"><Document /></el-icon>
              </div>
              {{ article.wordCount }}字
            </span>
          </div>

          <!-- Tags -->
          <div v-if="article.tags?.length" class="mt-6 flex flex-wrap gap-2">
            <span
              v-for="(tag, index) in article.tags"
              :key="index"
              class="pill pill-glass"
            >
              {{ tag }}
            </span>
          </div>
        </div>
      </section>

      <!-- Article Content -->
      <section class="pb-20">
        <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <!-- Main Content -->
            <div class="lg:col-span-8">
              <article class="glass-card rounded-3xl p-8 md:p-12">
                <div
                  class="markdown-body prose prose-lg max-w-none dark:prose-invert"
                  v-html="article.contentHtml"
                />
              </article>

              <!-- Article Footer Actions -->
              <div class="mt-8 glass-card rounded-2xl p-6">
                <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div class="text-sm text-gray-500 dark:text-gray-400">
                    最后更新于 {{ formatDateTimeCN(article.updateTime) }}
                  </div>

                  <div class="flex items-center gap-3">
                    <span class="text-sm text-gray-500 dark:text-gray-400">分享到：</span>
                    <button
                      class="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100 text-gray-600 transition-all hover:bg-[#1da1f2] hover:text-white dark:bg-dark-700 dark:text-gray-400"
                      @click="shareArticle('twitter')"
                    >
                      <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/>
                      </svg>
                    </button>
                    <button
                      class="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100 text-gray-600 transition-all hover:bg-[#e6162d] hover:text-white dark:bg-dark-700 dark:text-gray-400"
                      @click="shareArticle('weibo')"
                    >
                      <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M10.098 20.323c-3.977.391-7.414-1.406-7.672-4.02-.259-2.609 2.759-5.047 6.74-5.441 3.979-.394 7.413 1.404 7.671 4.018.259 2.6-2.759 5.049-6.737 5.439l-.002.004zM9.05 17.219c-.384.616-1.208.884-1.829.602-.612-.279-.793-.991-.406-1.593.379-.595 1.176-.861 1.793-.601.622.263.82.972.442 1.592zm1.27-1.627c-.141.237-.449.353-.689.253-.236-.09-.313-.361-.177-.586.138-.227.436-.346.672-.24.239.09.315.36.18.573h.014zm.176-2.719c-1.893-.493-4.033.45-4.857 2.118-.836 1.704-.026 3.591 1.886 4.21 1.983.64 4.318-.341 5.132-2.179.8-1.793-.201-3.642-2.161-4.149zm7.563-1.224c-.346-.105-.579-.18-.405-.649.384-.1.405-.649.384-.1.386-1.433-.045-2.758-1.091-3.493.136-.633-.045-2.758-1.091-3.493-1.592-1.024-3.711-.615-4.965.26-.855-.099-1.73-.064-2.589.165-2.235.6-3.74 2.46-3.535 4.42.205 1.96 2.076 3.438 4.466 3.579.855.099 1.73.064 2.589-.165.442-.118.871-.28 1.282-.484 1.592 1.024 3.711.615 4.965-.26.346.105.579.18.405.649l-.406-.029zm1.854-5.162c-.605-1.706-2.127-2.926-3.946-3.233-.314-.051-.631-.069-.946-.058-.252.009-.445-.192-.436-.445.009-.253.192-.446.445-.436.384-.014.77.008 1.152.065 2.18.354 4.014 1.822 4.736 3.858.088.251-.044.526-.295.614-.251.088-.526-.044-.614-.295l-.096-.07z"/>
                      </svg>
                    </button>
                    <button
                      class="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100 text-gray-600 transition-all hover:bg-aurora-purple hover:text-white dark:bg-dark-700 dark:text-gray-400"
                      :class="{ 'bg-green-500 text-white': copySuccess }"
                      @click="copyLink"
                    >
                      <el-icon v-if="!copySuccess"><Link /></el-icon>
                      <el-icon v-else><Check /></el-icon>
                    </button>
                  </div>
                </div>
              </div>

              <!-- Related Articles -->
              <div v-if="relatedArticles.length" class="mt-12">
                <h3 class="mb-6 text-xl font-bold text-gray-900 dark:text-white">
                  相关文章
                </h3>
                <div class="grid gap-4 sm:grid-cols-2">
                  <article
                    v-for="rel in relatedArticles"
                    :key="rel.id"
                    class="group cursor-pointer glass-card p-5"
                    @click="router.push(`/article/${rel.slug}`)"
                  >
                    <h4 class="font-medium text-gray-900 line-clamp-2 transition-colors group-hover:text-aurora-purple dark:text-white dark:group-hover:text-aurora-pink">
                      {{ rel.title }}
                    </h4>
                    <p class="mt-2 text-sm text-gray-500 line-clamp-1">
                      {{ rel.summary }}
                    </p>
                  </article>
                </div>
              </div>
            </div>

            <!-- Sidebar TOC -->
            <div class="hidden lg:block lg:col-span-4">
              <div class="sticky top-28 space-y-6">
                <!-- TOC Card -->
                <div class="glass-card rounded-2xl p-6">
                  <h3 class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white mb-4">
                    <el-icon><List /></el-icon>
                    目录
                  </h3>
                  <nav class="space-y-1 max-h-[calc(100vh-300px)] overflow-y-auto scrollbar-hide">
                    <a
                      v-for="(item, index) in toc"
                      :key="index"
                      :href="`#heading-${index}`"
                      class="block py-2 text-sm transition-all rounded-lg px-3"
                      :class="[
                        item.level === 1 ? 'text-gray-700 font-medium dark:text-gray-300' : 'text-gray-500 dark:text-gray-400',
                        item.level === 2 ? 'pl-6' : '',
                        item.level === 3 ? 'pl-9' : '',
                        activeHeading === `heading-${index}`
                          ? 'bg-aurora-purple/10 text-aurora-purple dark:bg-aurora-pink/10 dark:text-aurora-pink'
                          : 'hover:bg-gray-100 dark:hover:bg-dark-700'
                      ]"
                      @click.prevent="scrollToHeading(index)"
                    >
                      {{ item.text }}
                    </a>
                  </nav>
                </div>

                <!-- Quick Actions -->
                <div class="glass-card rounded-2xl p-6">
                  <h3 class="text-sm font-semibold text-gray-900 dark:text-white mb-4">
                    快速操作
                  </h3>
                  <div class="space-y-2">
                    <router-link
                      to="/article"
                      class="flex items-center gap-3 p-3 rounded-xl text-sm text-gray-600 transition-all hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-dark-700"
                    >
                      <el-icon><ArrowLeft /></el-icon>
                      返回文章列表
                    </router-link>
                    <router-link
                      to="/"
                      class="flex items-center gap-3 p-3 rounded-xl text-sm text-gray-600 transition-all hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-dark-700"
                    >
                      <el-icon><HomeFilled /></el-icon>
                      回到首页
                    </router-link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </template>
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
