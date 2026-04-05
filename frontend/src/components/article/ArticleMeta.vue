<script setup lang="ts">
import type { Article } from '@/types/article'

defineProps<{
  article: Article
}>()
</script>

<template>
  <div class="flex flex-wrap items-center gap-4 text-sm text-content-tertiary">
    <span class="flex items-center gap-1">
      <el-icon><Calendar /></el-icon>
      {{ article.publishTime?.split('T')[0] }}
    </span>
    <span class="flex items-center gap-1">
      <el-icon><View /></el-icon>
      阅读 {{ article.viewCount }}
    </span>
    <span class="flex items-center gap-1">
      <el-icon><Star /></el-icon>
      点赞 {{ article.likeCount }}
    </span>
    <span v-if="article.wordCount" class="flex items-center gap-1">
      <el-icon><Document /></el-icon>
      字数 {{ article.wordCount }}
    </span>
    <span v-if="article.readingTime" class="flex items-center gap-1">
      <el-icon><Timer /></el-icon>
      约 {{ article.readingTime }} 分钟
    </span>
  </div>
</template>
