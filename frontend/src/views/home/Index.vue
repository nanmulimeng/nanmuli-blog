<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useConfigStore } from '@/stores/modules/config'
import { getArticleList } from '@/api/article'
import { getHomeAggregated } from '@/api/home'
import { formatDateCN } from '@/utils/format'
import type { Article } from '@/types/article'
import type { HomeAggregated } from '@/types/home'

const router = useRouter()
const configStore = useConfigStore()

// 数据状态
const loading = ref(true)
const articles = ref<Article[]>([])
const aggregated = ref<HomeAggregated | null>(null)
const activeCategory = ref<string | null>(null)

// 统计数据动画
const animatedStats = ref({
  articleCount: 0,
  projectCount: 0,
  tagCount: 0,
  dayCount: 0,
})

// 获取首页数据
async function fetchData() {
  loading.value = true
  try {
    const [articlesRes, aggRes] = await Promise.all([
      getArticleList({ current: 1, size: 6 }),
      getHomeAggregated(),
    ])
    articles.value = articlesRes.records
    aggregated.value = aggRes

    // 动画显示统计数据
    animateStats()
  } finally {
    loading.value = false
  }
}

// 数字动画
function animateStats() {
  if (!aggregated.value) return

  const targets = {
    articleCount: aggregated.value.stats.articleCount || 0,
    projectCount: aggregated.value.stats.projectCount || 0,
    tagCount: aggregated.value.stats.tagCount || 0,
    dayCount: aggregated.value.stats.dailyLogCount || 0,
  }

  const duration = 1500
  const steps = 60
  const interval = duration / steps

  let step = 0
  const timer = setInterval(() => {
    step++
    const progress = step / steps
    const easeOut = 1 - Math.pow(1 - progress, 3)

    animatedStats.value = {
      articleCount: Math.floor(targets.articleCount * easeOut),
      projectCount: Math.floor(targets.projectCount * easeOut),
      tagCount: Math.floor(targets.tagCount * easeOut),
      dayCount: Math.floor(targets.dayCount * easeOut),
    }

    if (step >= steps) {
      animatedStats.value = targets
      clearInterval(timer)
    }
  }, interval)
}

// 导航到文章
function navigateToArticle(slug: string) {
  router.push(`/article/${slug}`)
}

// 导航到分类
function navigateToCategory(categoryId: string) {
  router.push(`/article?categoryId=${categoryId}`)
}

// 过滤文章
const filteredArticles = computed(() => {
  if (!activeCategory.value) return articles.value
  return articles.value.filter(a => a.categoryId === activeCategory.value)
})

// 打字机效果文字
const heroTexts = ['记录技术成长', '探索代码世界', '分享学习心得']
const currentText = ref('')
const textIndex = ref(0)
const charIndex = ref(0)
const isDeleting = ref(false)

function typeWriter() {
  const text = heroTexts[textIndex.value] as string

  if (isDeleting.value) {
    currentText.value = text.substring(0, charIndex.value - 1)
    charIndex.value--
  } else {
    currentText.value = text.substring(0, charIndex.value + 1)
    charIndex.value++
  }

  let typeSpeed = isDeleting.value ? 50 : 100

  if (!isDeleting.value && charIndex.value === text.length) {
    typeSpeed = 2000
    isDeleting.value = true
  } else if (isDeleting.value && charIndex.value === 0) {
    isDeleting.value = false
    textIndex.value = (textIndex.value + 1) % heroTexts.length
    typeSpeed = 500
  }

  setTimeout(typeWriter, typeSpeed)
}

onMounted(() => {
  fetchData()
  typeWriter()
})
</script>

<template>
  <div class="home-page">
    <!-- Hero Section -->
    <section class="relative min-h-[90vh] overflow-hidden">
      <!-- 动态背景 - 使用主题变量 -->
      <div class="absolute inset-0 bg-gradient-to-br from-primary/10 via-surface-tertiary to-primary/5 dark:from-primary/10 dark:via-surface-secondary dark:to-primary/5">
        <!-- 动画网格 -->
        <div class="absolute inset-0 bg-grid-pattern opacity-30 dark:opacity-20" />

        <!-- 浮动光球 - 使用主题蓝色系 -->
        <div class="absolute left-10 top-20 h-72 w-72 rounded-full bg-primary/20 blur-3xl animate-float dark:bg-primary-light/10" />
        <div class="animation-delay-500 absolute right-20 top-40 h-96 w-96 rounded-full bg-primary/15 blur-3xl animate-float dark:bg-primary/10" />
        <div class="animation-delay-700 absolute bottom-20 left-1/3 h-64 w-64 rounded-full bg-primary/20 blur-3xl animate-float dark:bg-primary-light/10" />
      </div>

      <!-- Hero 内容 -->
      <div class="relative z-10 mx-auto flex min-h-[90vh] max-w-7xl items-center px-4 sm:px-6 lg:px-8">
        <div class="grid w-full gap-12 lg:grid-cols-2 lg:gap-8 items-center">
          <!-- 左侧：文字内容 -->
          <div class="space-y-8">
            <!-- 标签 -->
            <div class="inline-flex items-center gap-2 rounded-full bg-surface-secondary/80 px-4 py-2 shadow-sm backdrop-blur-sm">
              <span class="flex h-2 w-2 rounded-full bg-success animate-pulse" />
              <span class="text-sm font-medium text-content-secondary">持续更新中</span>
            </div>

            <!-- 主标题 -->
            <div class="space-y-4">
              <h1 class="text-5xl font-bold leading-tight text-content-primary sm:text-6xl lg:text-7xl">
                <span class="block">欢迎来到</span>
                <span class="gradient-text">{{ configStore.siteName || '我的博客' }}</span>
              </h1>

              <!-- 打字机效果副标题 -->
              <p class="h-10 text-xl text-content-secondary sm:text-2xl">
                {{ currentText }}<span class="animate-pulse">|</span>
              </p>
            </div>

            <!-- 描述 -->
            <p class="max-w-lg text-lg text-content-secondary">
              {{ configStore.siteDescription || '分享技术学习心得，记录编程成长历程，探索代码世界的无限可能' }}
            </p>

            <!-- CTA 按钮 -->
            <div class="flex flex-wrap gap-4">
              <router-link
                to="/article"
                class="btn-gradient group inline-flex items-center gap-2"
              >
                <el-icon class="text-lg"><Document /></el-icon>
                <span>浏览文章</span>
                <el-icon class="transition-transform group-hover:translate-x-1"><ArrowRight /></el-icon>
              </router-link>

              <router-link
                to="/daily-log"
                class="btn-glass inline-flex items-center gap-2 text-content-secondary"
              >
                <el-icon class="text-lg"><Timer /></el-icon>
                <span>技术日志</span>
              </router-link>
            </div>

            <!-- 社交链接 -->
            <div class="flex items-center gap-4 pt-4">
              <a
                v-if="configStore.siteGithub"
                :href="configStore.siteGithub"
                target="_blank"
                class="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-tertiary text-content-secondary transition-all hover:bg-surface-secondary hover:text-content-primary"
              >
                <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
              </a>
              <a
                v-if="configStore.siteEmail"
                :href="`mailto:${configStore.siteEmail}`"
                class="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-tertiary text-content-secondary transition-all hover:bg-surface-secondary hover:text-content-primary"
              >
                <el-icon class="text-lg"><Message /></el-icon>
              </a>
            </div>
          </div>

          <!-- 右侧：装饰卡片 -->
          <div class="relative hidden lg:block">
            <!-- 浮动代码卡片 -->
            <div class="glass-card relative mx-auto max-w-md p-6 animate-fade-in-up">
              <div class="mb-4 flex items-center justify-between">
                <div class="flex gap-2">
                  <div class="h-3 w-3 rounded-full bg-error" />
                  <div class="h-3 w-3 rounded-full bg-warning" />
                  <div class="h-3 w-3 rounded-full bg-success" />
                </div>
                <span class="text-xs text-content-tertiary">blog.vue</span>
              </div>
              <pre class="overflow-x-auto text-sm leading-relaxed text-content-secondary"><code>&lt;script setup&gt;
const passion = ref('Coding')
const dream = computed(() => {
  return `Build with ${passion.value}`
})

// 每一天都在进步
watch(experience, (newVal) => {
  if (newVal > yesterday) {
    console.log('成长了！')
  }
})
&lt;/script&gt;</code></pre>
            </div>

            <!-- 装饰元素 - 使用主题蓝色系 -->
            <div class="absolute -right-4 top-1/2 -translate-y-1/2 transform rounded-2xl bg-gradient-to-br from-primary to-primary-light p-4 shadow-xl animate-float">
              <el-icon class="text-3xl text-white"><Code /></el-icon>
            </div>

            <div class="absolute -left-8 bottom-10 transform rounded-2xl bg-gradient-to-br from-primary-light to-primary p-4 shadow-xl animation-delay-500 animate-float">
              <el-icon class="text-3xl text-white"><Coffee /></el-icon>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部渐变过渡 -->
      <div class="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[var(--theme-bg-primary)] to-transparent" />
    </section>

    <!-- Stats Bar -->
    <section class="relative z-20 -mt-16 mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
      <div class="glass-card grid grid-cols-2 gap-8 rounded-3xl p-8 md:grid-cols-4">
        <div class="text-center">
          <div class="text-3xl font-bold text-content-primary sm:text-4xl">
            {{ animatedStats.articleCount }}
          </div>
          <div class="mt-1 text-sm text-content-tertiary">篇文章</div>
        </div>
        <div class="text-center">
          <div class="text-3xl font-bold text-content-primary sm:text-4xl">
            {{ animatedStats.projectCount }}
          </div>
          <div class="mt-1 text-sm text-content-tertiary">个项目</div>
        </div>
        <div class="text-center">
          <div class="text-3xl font-bold text-content-primary sm:text-4xl">
            {{ animatedStats.tagCount }}
          </div>
          <div class="mt-1 text-sm text-content-tertiary">个标签</div>
        </div>
        <div class="text-center">
          <div class="text-3xl font-bold text-content-primary sm:text-4xl">
            {{ animatedStats.dayCount }}
          </div>
          <div class="mt-1 text-sm text-content-tertiary">篇日志</div>
        </div>
      </div>
    </section>

    <!-- Featured Articles Section -->
    <section class="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
      <!-- Section Header -->
      <div class="mb-12 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 class="text-3xl font-bold text-content-primary sm:text-4xl">
            最新文章
          </h2>
          <p class="mt-2 text-content-secondary">
            探索技术的无限可能，分享学习的点滴收获
          </p>
        </div>

        <!-- 分类筛选 -->
        <div class="flex flex-wrap gap-2">
          <button
            class="pill"
            :class="!activeCategory ? 'pill-primary' : 'pill-secondary'"
            @click="activeCategory = null"
          >
            全部
          </button>
          <button
            v-for="cat in aggregated?.categories?.slice(0, 5)"
            :key="cat.id"
            class="pill"
            :class="activeCategory === cat.id ? 'pill-primary' : 'pill-secondary'"
            @click="activeCategory = cat.id"
          >
            {{ cat.name }}
          </button>
        </div>
      </div>

      <!-- Articles Grid -->
      <div v-if="loading" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div v-for="i in 6" :key="i" class="glass-card h-80 p-6">
          <el-skeleton :rows="5" animated />
        </div>
      </div>

      <div v-else-if="filteredArticles.length" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <article
          v-for="(article, index) in filteredArticles"
          :key="article.id"
          class="group cursor-pointer overflow-hidden rounded-3xl bg-surface-secondary shadow-card transition-all duration-500 hover:shadow-card-hover hover:-translate-y-2"
          :style="{ animationDelay: `${index * 100}ms` }"
          @click="navigateToArticle(article.slug)"
        >
          <!-- 封面图 -->
          <div class="relative aspect-video overflow-hidden">
            <img
              v-if="article.cover"
              :src="article.cover"
              :alt="article.title"
              class="h-full w-full object-cover transition-transform duration-700 group-hover:scale-110"
            />
            <div v-else class="flex h-full w-full items-center justify-center bg-gradient-to-br from-blue-400/20 to-cyan-300/20 dark:from-cyan-500/20 dark:to-blue-400/20">
              <el-icon class="text-4xl text-primary/50"><Document /></el-icon>
            </div>

            <!-- 置顶标签 -->
            <div v-if="article.isTop" class="absolute left-4 top-4">
              <span class="flex items-center gap-1 rounded-full bg-warning px-3 py-1 text-xs font-medium text-white shadow-lg">
                <el-icon><StarFilled /></el-icon>
                置顶
              </span>
            </div>

            <!-- 分类标签 -->
            <div class="absolute bottom-4 left-4">
              <span class="pill pill-secondary text-xs shadow-sm backdrop-blur-sm">
                {{ article.categoryName }}
              </span>
            </div>
          </div>

          <!-- 内容 -->
          <div class="p-6">
            <h3 class="mb-3 text-lg font-semibold text-content-primary line-clamp-2 transition-colors group-hover:text-primary">
              {{ article.title }}
            </h3>
            <p class="mb-4 text-sm text-content-secondary line-clamp-2 leading-relaxed">
              {{ article.summary }}
            </p>
            <div class="flex items-center gap-4 text-xs text-content-tertiary">
              <span class="flex items-center gap-1">
                <el-icon><Calendar /></el-icon>
                {{ formatDateCN(article.publishTime) }}
              </span>
              <span class="flex items-center gap-1">
                <el-icon><View /></el-icon>
                {{ article.viewCount }}
              </span>
            </div>
          </div>
        </article>
      </div>

      <!-- Empty State -->
      <div v-else class="flex flex-col items-center justify-center py-20 text-center">
        <el-icon class="mb-4 text-6xl text-content-tertiary/50"><Document /></el-icon>
        <p class="text-content-secondary">暂无文章</p>
      </div>

      <!-- View All Button -->
      <div class="mt-12 text-center">
        <router-link
          to="/article"
          class="inline-flex items-center gap-2 rounded-full border border-border bg-surface-secondary px-6 py-3 text-sm font-medium text-content-secondary transition-all hover:border-primary hover:text-primary"
        >
          查看全部文章
          <el-icon><ArrowRight /></el-icon>
        </router-link>
      </div>
    </section>

    <!-- Categories Section -->
    <section class="relative overflow-hidden py-24">
      <!-- 背景装饰 -->
      <div class="absolute inset-0 bg-gradient-to-b from-transparent via-primary/5 to-transparent" />

      <div class="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div class="mb-12 text-center">
          <h2 class="text-3xl font-bold text-content-primary sm:text-4xl">
            探索分类
          </h2>
          <p class="mt-2 text-content-secondary">
            按主题浏览感兴趣的内容
          </p>
        </div>

        <div class="flex flex-wrap justify-center gap-4">
          <button
            v-for="cat in aggregated?.categories"
            :key="cat.id"
            class="group relative overflow-hidden rounded-2xl bg-surface-secondary p-6 text-left shadow-card transition-all duration-300 hover:shadow-card-hover hover:-translate-y-1"
            @click="navigateToCategory(cat.id)"
          >
            <!-- 装饰背景 -->
            <div class="absolute -right-4 -top-4 h-20 w-20 rounded-full bg-gradient-to-br from-primary/20 to-primary-light/20 opacity-0 transition-opacity group-hover:opacity-100" />

            <div class="relative">
              <h3 class="text-lg font-semibold text-content-primary">
                {{ cat.name }}
              </h3>
              <p class="mt-1 text-sm text-content-tertiary">
                {{ cat.articleCount || 0 }} 篇文章
              </p>
            </div>
          </button>
        </div>
      </div>
    </section>

    <!--     <!-- Archive Preview Section --> -->
    <!--     <section v-if="aggregated?.archive?.length" class="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8"> -->
    <!--       <div class="mb-12 flex items-end justify-between"> -->
    <!--         <div> -->
    <!--           <h2 class="text-3xl font-bold text-gray-900 dark:text-white sm:text-4xl"> -->
    <!--             文章归档 -->
    <!--           </h2> -->
    <!--           <p class="mt-2 text-gray-600 dark:text-gray-400"> -->
    <!--             按时间线回顾过往文章 -->
    <!--           </p> -->
    <!--         </div> -->
    <!--         <router-link -->
    <!--           to="/article/archive" -->
    <!--           class="flex items-center gap-1 text-sm font-medium text-aurora-purple transition-colors hover:text-aurora-pink dark:text-aurora-pink dark:hover:text-aurora-cyan" -->
    <!--         > -->
    <!--           查看全部 -->
    <!--           <el-icon><ArrowRight /></el-icon> -->
    <!--         </router-link> -->
    <!--       </div> -->
    <!--  -->
    <!--       <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"> -->
    <!--         <div -->
    <!--           v-for="item in aggregated.archive.slice(0, 8)" -->
    <!--           :key="`${item.year}-${item.month}`" -->
    <!--           class="glass-card group cursor-pointer p-6" -->
    <!--           @click="router.push(`/article?year=${item.year}&month=${item.month}`)" -->
    <!--         > -->
    <!--           <div class="flex items-center justify-between"> -->
    <!--             <div> -->
    <!--               <div class="text-2xl font-bold text-gray-900 dark:text-white"> -->
    <!--                 {{ item.year }}年{{ item.month }}月 -->
    <!--               </div> -->
    <!--               <div class="mt-1 text-sm text-gray-500 dark:text-gray-400"> -->
    <!--                 {{ item.count }} 篇文章 -->
    <!--               </div> -->
    <!--             </div> -->
    <!--             <div class="flex h-10 w-10 items-center justify-center rounded-full bg-aurora-purple/10 text-aurora-purple transition-all group-hover:bg-aurora-purple group-hover:text-white dark:bg-aurora-pink/10 dark:text-aurora-pink dark:group-hover:bg-aurora-pink"> -->
    <!--               <el-icon><ArrowRight /></el-icon> -->
    <!--             </div> -->
    <!--           </div> -->
    <!--         </div> -->
    <!--       </div> -->
    <!--     </section> -->
  </div>
</template>

<style scoped>
/* 额外的动画样式 */
@keyframes float {
  0%, 100% {
    transform: translateY(0) rotate(0deg);
  }
  50% {
    transform: translateY(-20px) rotate(5deg);
  }
}

.animate-float {
  animation: float 6s ease-in-out infinite;
}
</style>
