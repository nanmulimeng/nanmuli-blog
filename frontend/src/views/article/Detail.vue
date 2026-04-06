<script setup lang="ts">
import { ref, onMounted, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getArticleBySlug, recordArticleViewByVisitor, getArticleList, getArticleStats, type ArticleStats } from '@/api/article'
import { generateVisitorId } from '@/utils/visitor'
import { formatDateCN, formatDateTimeCN } from '@/utils/format'
import type { Article } from '@/types/article'
import hljs from 'highlight.js'

const route = useRoute()
const router = useRouter()

const article = ref<Article | null>(null)
const relatedArticles = ref<Article[]>([])
const loading = ref(false)
const toc = ref<Array<{ id: string; text: string; level: number }>>([])
const activeHeading = ref('')
const copySuccess = ref(false)
const contentRef = ref<HTMLElement | null>(null)
const tocNavRef = ref<HTMLElement | null>(null)

// 访问统计
const articleStats = ref<ArticleStats | null>(null)
const statsLoading = ref(false)

// 生成安全的ID
function generateHeadingId(text: string, index: number): string {
  // 使用索引确保唯一性，同时处理中文
  const safeText = text
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^\w\u4e00-\u9fa5-]/g, '')
    .slice(0, 50)
  return `heading-${index}-${safeText || 'section'}`
}

// 从HTML内容中提取标题并生成目录
function generateTocFromHtml(htmlContent: string): void {
  const parser = new DOMParser()
  const doc = parser.parseFromString(htmlContent, 'text/html')
  const headings = doc.querySelectorAll('h1, h2, h3')

  toc.value = Array.from(headings).map((heading, index) => {
    const text = heading.textContent?.trim() || ''
    return {
      id: generateHeadingId(text, index),
      text: text,
      level: parseInt(heading.tagName[1]),
    }
  })
}

// 处理文章内容：高亮代码、处理图片、处理链接
function processContent(): void {
  if (!contentRef.value) return

  // 1. 代码高亮
  contentRef.value.querySelectorAll('pre code').forEach((block) => {
    hljs.highlightElement(block as HTMLElement)
  })

  // 2. 图片懒加载
  contentRef.value.querySelectorAll('img').forEach((img) => {
    if (!img.hasAttribute('loading')) {
      img.setAttribute('loading', 'lazy')
    }
    // 添加点击放大功能
    img.style.cursor = 'zoom-in'
    img.addEventListener('click', () => {
      // 简单的图片预览
      const modal = document.createElement('div')
      modal.style.cssText = `
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.9);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        cursor: zoom-out;
      `
      const imgClone = document.createElement('img')
      imgClone.src = img.src
      imgClone.style.cssText = 'max-width: 90%; max-height: 90%; object-fit: contain;'
      modal.appendChild(imgClone)
      modal.addEventListener('click', () => modal.remove())
      document.body.appendChild(modal)
    })
  })

  // 3. 外部链接在新标签页打开
  contentRef.value.querySelectorAll('a').forEach((link) => {
    const href = link.getAttribute('href')
    if (href && (href.startsWith('http://') || href.startsWith('https://'))) {
      link.setAttribute('target', '_blank')
      link.setAttribute('rel', 'noopener noreferrer')
    }
  })

  // 4. 为标题添加锚点ID - 严格按索引匹配
  const headings = contentRef.value.querySelectorAll('h1, h2, h3')

  headings.forEach((heading, index) => {
    const tocItem = toc.value[index]
    if (tocItem) {
      heading.id = tocItem.id
    }
  })

  // 5. 重新设置滚动监听（因为刚设置了ID）
  setupScrollSpy()
}

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

    // 从HTML内容生成目录
    generateTocFromHtml(res.contentHtml)

    fetchRelatedArticles(res.categoryId, res.id)

    // 获取文章访问统计
    fetchArticleStats(res.id)

    // processContent 将由 watch(article) 触发
  } catch {
    router.push('/404')
  } finally {
    loading.value = false
  }
}

async function fetchRelatedArticles(categoryId: string, excludeId: string): Promise<void> {
  try {
    const res = await getArticleList({
      current: 1,
      size: 4,
      categoryId
    })
    relatedArticles.value = res.records.filter((a: Article) => a.id !== excludeId).slice(0, 3)
  } catch {
    // ignore
  }
}

// 获取文章访问统计
async function fetchArticleStats(articleId: string): Promise<void> {
  statsLoading.value = true
  try {
    articleStats.value = await getArticleStats(articleId)
  } catch {
    // ignore
  } finally {
    statsLoading.value = false
  }
}


function scrollToHeading(index: number): void {
  const tocItem = toc.value[index]
  if (!tocItem) return

  const element = document.getElementById(tocItem.id)
  if (element) {
    const offset = 100
    const elementPosition = element.getBoundingClientRect().top
    const offsetPosition = elementPosition + window.pageYOffset - offset
    window.scrollTo({ top: offsetPosition, behavior: 'smooth' })
  } else {
    // 尝试通过索引查找
    const headings = document.querySelectorAll('h1, h2, h3')
    if (headings[index]) {
      headings[index].scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }
}

// ScrollSpy 状态
let scrollSpyObserver: IntersectionObserver | null = null

// 设置滚动监听
function setupScrollSpy(): void {
  if (!contentRef.value) return

  // 清除旧的观察者
  if (scrollSpyObserver) {
    scrollSpyObserver.disconnect()
    scrollSpyObserver = null
  }

  // 等待ID设置完成后查找标题
  const headings = contentRef.value.querySelectorAll('h1, h2, h3')

  // 筛选出有ID的标题
  const validHeadings = Array.from(headings).filter(h => h.id)
  if (validHeadings.length === 0) return

  scrollSpyObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          activeHeading.value = entry.target.id
        }
      })
    },
    {
      rootMargin: '-80px 0px -70% 0px',
      threshold: 0
    }
  )

  validHeadings.forEach((heading) => {
    scrollSpyObserver?.observe(heading)
  })
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
  // 5秒后记录阅读用户（UV统计）
  setTimeout(() => {
    const articleId = article.value?.id
    if (articleId) {
      const visitorId = generateVisitorId()
      recordArticleViewByVisitor(articleId, visitorId)
    }
  }, 5000)
})

// 监听路由参数变化，当文章slug变化时重新加载
watch(() => route.params.slug, (newSlug, oldSlug) => {
  if (newSlug && newSlug !== oldSlug) {
    // 重置状态
    toc.value = []
    activeHeading.value = ''
    window.scrollTo({ top: 0, behavior: 'smooth' })
    fetchArticle()
  }
})

// 监听 article 变化，确保内容渲染后处理
watch(article, (newArticle) => {
  if (newArticle?.contentHtml) {
    // 使用更长的延迟确保 v-html 完全渲染
    setTimeout(() => {
      processContent()
    }, 500)
  }
}, { immediate: false })

// 监听 activeHeading 变化，自动滚动目录到可视区域
watch(activeHeading, (newId) => {
  if (!newId || !tocNavRef.value) return

  // 找到当前激活的目录项
  const activeLink = tocNavRef.value.querySelector(`a[href="#${newId}"]`)
  if (!activeLink) return

  // 滚动到可视区域
  const nav = tocNavRef.value
  const linkElement = activeLink as HTMLElement
  const linkTop = linkElement.offsetTop
  const navHeight = nav.clientHeight
  const linkHeight = linkElement.clientHeight

  // 计算目标滚动位置，让当前项居中显示
  const targetScrollTop = linkTop - navHeight / 2 + linkHeight / 2

  nav.scrollTo({
    top: Math.max(0, targetScrollTop),
    behavior: 'smooth'
  })
})
</script>

<template>
  <div class="article-detail-page">
    <!-- Reading Progress Bar -->
    <div
      class="fixed top-0 left-0 right-0 h-[3px] z-50 bg-gradient-to-r from-primary via-primary-light to-primary transition-all duration-150"
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
        <div class="absolute inset-0 bg-gradient-to-b from-primary/10 via-transparent to-transparent" />

        <div class="relative mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <!-- Breadcrumb -->
          <nav class="mb-8 flex items-center gap-2 text-sm text-content-tertiary">
            <router-link to="/" class="hover:text-primary transition-colors">
              首页
            </router-link>
            <el-icon><ArrowRight class="text-xs" /></el-icon>
            <router-link to="/article" class="hover:text-primary transition-colors">
              文章
            </router-link>
            <el-icon><ArrowRight class="text-xs" /></el-icon>
            <span class="text-content-primary font-medium truncate max-w-[200px]">
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
                    ? 'inline-flex items-center px-4 py-1.5 rounded-full bg-gradient-to-r from-primary to-primary-light text-white font-medium shadow-lg shadow-primary/30'
                    : 'text-content-tertiary hover:text-primary'"
                >
                  {{ cat.name }}
                </router-link>
                <span v-if="index < article.categoryPath.length - 1" class="text-content-tertiary/50">/</span>
              </span>
            </div>
            <router-link
              v-else
              :to="`/article?categoryId=${article.categoryId}`"
              class="inline-flex items-center px-4 py-1.5 rounded-full bg-gradient-to-r from-primary to-primary-light text-white font-medium shadow-lg shadow-primary/30"
            >
              {{ article.category?.name || article.categoryName }}
            </router-link>
          </div>

          <!-- Title -->
          <h1 class="text-3xl md:text-4xl lg:text-5xl font-bold text-content-primary leading-tight">
            {{ article.title }}
          </h1>

          <!-- Meta Info -->
          <div class="mt-8 flex flex-wrap items-center gap-4 text-sm">
            <!-- 原创/转载标识 -->
            <span
              class="flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium"
              :class="article.isOriginal
                ? 'bg-success/10 text-success'
                : 'bg-warning/10 text-warning'"
            >
              <el-icon v-if="article.isOriginal"><DocumentChecked /></el-icon>
              <el-icon v-else><Link /></el-icon>
              {{ article.isOriginal ? '原创内容' : '转载内容' }}
            </span>
            <span class="flex items-center gap-2 text-content-tertiary">
              <div class="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                <el-icon class="text-primary"><Calendar /></el-icon>
              </div>
              {{ formatDateCN(article.publishTime) }}
            </span>
            <!-- 访问统计 -->
            <template v-if="articleStats">
              <span class="flex items-center gap-2 text-content-tertiary" title="总访问量">
                <div class="flex h-8 w-8 items-center justify-center rounded-full bg-info/10">
                  <el-icon class="text-info"><View /></el-icon>
                </div>
                {{ articleStats.visitCount || 0 }}
              </span>
              <span class="flex items-center gap-2 text-content-tertiary" title="访客数">
                <div class="flex h-8 w-8 items-center justify-center rounded-full bg-purple/10">
                  <el-icon class="text-purple"><User /></el-icon>
                </div>
                {{ articleStats.visitorCount || 0 }}
              </span>
              <span class="flex items-center gap-2 text-content-tertiary" title="今日访问">
                <div class="flex h-8 w-8 items-center justify-center rounded-full bg-success/10">
                  <el-icon class="text-success"><TrendCharts /></el-icon>
                </div>
                今日 {{ articleStats.todayCount || 0 }}
              </span>
            </template>
            <span v-else class="flex items-center gap-2 text-content-tertiary">
              <div class="flex h-8 w-8 items-center justify-center rounded-full bg-info/10">
                <el-icon class="text-info"><View /></el-icon>
              </div>
              {{ article.viewCount }} 人阅读
            </span>
            <span class="flex items-center gap-2 text-content-tertiary">
              <div class="flex h-8 w-8 items-center justify-center rounded-full bg-warning/10">
                <el-icon class="text-warning"><Clock /></el-icon>
              </div>
              {{ article.readingTime }}分钟
            </span>
            <span class="flex items-center gap-2 text-content-tertiary">
              <div class="flex h-8 w-8 items-center justify-center rounded-full bg-success/10">
                <el-icon class="text-success"><Document /></el-icon>
              </div>
              {{ article.wordCount }}字
            </span>
            <!-- 非原创文章来源 -->
            <span v-if="!article.isOriginal && article.originalUrl" class="flex items-center gap-2 text-sm">
              <span class="text-content-tertiary">来源：</span>
              <a
                :href="article.originalUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="text-primary hover:text-primary-light hover:underline truncate max-w-[200px]"
              >
                {{ article.originalUrl.replace(/^https?:\/\//, '').split('/')[0] }}
              </a>
              <el-icon class="text-content-tertiary text-xs"><Link /></el-icon>
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
              <article ref="contentRef" class="glass-card rounded-3xl p-8 md:p-12">
                <div
                  class="markdown-body prose prose-lg max-w-none dark:prose-invert"
                  v-html="article.contentHtml"
                />
              </article>

              <!-- Article Footer Actions -->
              <div class="mt-8 glass-card rounded-2xl p-6">
                <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div class="text-sm text-content-tertiary">
                    最后更新于 {{ formatDateTimeCN(article.updateTime) }}
                  </div>

                  <div class="flex items-center gap-3">
                    <span class="text-sm text-content-tertiary">分享到：</span>
                    <button
                      class="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-tertiary text-content-secondary transition-all hover:bg-[#1da1f2] hover:text-white"
                      @click="shareArticle('twitter')"
                    >
                      <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/>
                      </svg>
                    </button>
                    <button
                      class="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-tertiary text-content-secondary transition-all hover:bg-[#e6162d] hover:text-white"
                      @click="shareArticle('weibo')"
                    >
                      <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M10.098 20.323c-3.977.391-7.414-1.406-7.672-4.02-.259-2.609 2.759-5.047 6.74-5.441 3.979-.394 7.413 1.404 7.671 4.018.259 2.6-2.759 5.049-6.737 5.439l-.002.004zM9.05 17.219c-.384.616-1.208.884-1.829.602-.612-.279-.793-.991-.406-1.593.379-.595 1.176-.861 1.793-.601.622.263.82.972.442 1.592zm1.27-1.627c-.141.237-.449.353-.689.253-.236-.09-.313-.361-.177-.586.138-.227.436-.346.672-.24.239.09.315.36.18.573h.014zm.176-2.719c-1.893-.493-4.033.45-4.857 2.118-.836 1.704-.026 3.591 1.886 4.21 1.983.64 4.318-.341 5.132-2.179.8-1.793-.201-3.642-2.161-4.149zm7.563-1.224c-.346-.105-.579-.18-.405-.649.384-.1.405-.649.384-.1.386-1.433-.045-2.758-1.091-3.493.136-.633-.045-2.758-1.091-3.493-1.592-1.024-3.711-.615-4.965.26-.855-.099-1.73-.064-2.589.165-2.235.6-3.74 2.46-3.535 4.42.205 1.96 2.076 3.438 4.466 3.579.855.099 1.73.064 2.589-.165.442-.118.871-.28 1.282-.484 1.592 1.024 3.711.615 4.965-.26.346.105.579.18.405.649l-.406-.029zm1.854-5.162c-.605-1.706-2.127-2.926-3.946-3.233-.314-.051-.631-.069-.946-.058-.252.009-.445-.192-.436-.445.009-.253.192-.446.445-.436.384-.014.77.008 1.152.065 2.18.354 4.014 1.822 4.736 3.858.088.251-.044.526-.295.614-.251.088-.526-.044-.614-.295l-.096-.07z"/>
                      </svg>
                    </button>
                    <button
                      class="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-tertiary text-content-secondary transition-all hover:bg-primary hover:text-white"
                      :class="{ 'bg-success text-white': copySuccess }"
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
                <h3 class="mb-6 text-xl font-bold text-content-primary">
                  相关文章
                </h3>
                <div class="grid gap-4 sm:grid-cols-2">
                  <article
                    v-for="rel in relatedArticles"
                    :key="rel.id"
                    class="group cursor-pointer glass-card p-5"
                    @click="router.push(`/article/${rel.slug}`)"
                  >
                    <h4 class="font-medium text-content-primary line-clamp-2 transition-colors group-hover:text-primary">
                      {{ rel.title }}
                    </h4>
                    <p class="mt-2 text-sm text-content-tertiary line-clamp-1">
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
                  <h3 class="flex items-center gap-2 text-sm font-semibold text-content-primary mb-4">
                    <el-icon><List /></el-icon>
                    目录
                  </h3>
                  <nav ref="tocNavRef" class="space-y-1 max-h-[calc(100vh-300px)] overflow-y-auto scrollbar-hide">
                    <a
                      v-for="(item, index) in toc"
                      :key="item.id"
                      :href="`#${item.id}`"
                      class="block py-2 text-sm transition-all rounded-lg px-3"
                      :class="[
                        item.level === 1 ? 'text-content-secondary font-medium' : 'text-content-tertiary',
                        item.level === 2 ? 'pl-6' : '',
                        item.level === 3 ? 'pl-9' : '',
                        activeHeading === item.id
                          ? 'bg-primary/10 text-primary'
                          : 'hover:bg-surface-tertiary'
                      ]"
                      @click.prevent="scrollToHeading(index)"
                    >
                      {{ item.text }}
                    </a>
                  </nav>
                </div>

                <!-- Quick Actions -->
                <div class="glass-card rounded-2xl p-6">
                  <h3 class="text-sm font-semibold text-content-primary mb-4">
                    快速操作
                  </h3>
                  <div class="space-y-2">
                    <router-link
                      to="/article"
                      class="flex items-center gap-3 p-3 rounded-xl text-sm text-content-secondary transition-all hover:bg-surface-tertiary"
                    >
                      <el-icon><ArrowLeft /></el-icon>
                      返回文章列表
                    </router-link>
                    <router-link
                      to="/"
                      class="flex items-center gap-3 p-3 rounded-xl text-sm text-content-secondary transition-all hover:bg-surface-tertiary"
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
