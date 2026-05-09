<script setup lang="ts">
import type { Article } from '@/types/article'
import type { ArticleStats } from '@/api/article'
import { formatDateCN } from '@/utils/format'

defineProps<{
  article: Article
  articleStats: ArticleStats | null
}>()
</script>

<template>
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
        <span class="text-content-primary font-medium truncate max-w-[150px] sm:max-w-[200px]" :title="article.title">
          {{ article.title.length > 20 ? article.title.slice(0, 20) + '...' : article.title }}
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
            <div class="flex h-8 w-8 items-center justify-center rounded-full bg-info/10">
              <el-icon class="text-info"><User /></el-icon>
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
</template>
