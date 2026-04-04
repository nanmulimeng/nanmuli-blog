<script setup lang="ts">
import ArticleCard from './ArticleCard.vue'
import type { Article } from '@/types/article'

defineProps<{
  articles: Article[]
  loading?: boolean
}>()

const emit = defineEmits<{
  click: [id: number]
}>()

function handleArticleClick(id: number): void {
  emit('click', id)
}
</script>

<template>
  <div class="space-y-6">
    <div v-if="loading" class="space-y-6">
      <el-skeleton v-for="i in 3" :key="i" :rows="3" animated />
    </div>

    <div v-else-if="articles.length === 0" class="py-12 text-center text-gray-500">
      暂无文章
    </div>

    <div v-else class="space-y-6">
      <ArticleCard
        v-for="article in articles"
        :key="article.id"
        :article="article"
        @click="handleArticleClick"
      />
    </div>
  </div>
</template>
