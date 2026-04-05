<script setup lang="ts">
import { computed } from 'vue'
import { formatDateCN } from '@/utils/format'
import type { Article } from '@/types/article'

const props = defineProps<{
  article: Article
}>()

const emit = defineEmits<{
  click: [id: string]
}>()

const summary = computed(() => {
  return props.article.summary || props.article.content.slice(0, 200) + '...'
})

function handleClick(): void {
  emit('click', props.article.id)
}
</script>

<template>
  <article
    class="group cursor-pointer rounded-xl border border-border bg-surface-secondary p-6 transition-shadow hover:shadow-lg"
    @click="handleClick"
  >
    <div class="mb-4 flex items-center gap-3 text-sm text-content-tertiary">
      <!-- 分类路径 -->
      <span v-if="article.categoryPath?.length" class="flex items-center gap-1">
        <span
          v-for="(cat, index) in article.categoryPath"
          :key="cat.id"
          class="flex items-center gap-1"
        >
          <span
            class="rounded-full px-2 py-1 text-xs"
            :style="{
              backgroundColor: cat.color ? cat.color + '20' : 'var(--theme-bg-tertiary)',
              color: cat.color || 'var(--theme-primary)'
            }"
          >
            {{ cat.name }}
          </span>
          <span v-if="index < article.categoryPath.length - 1" class="text-content-tertiary/50">/</span>
        </span>
      </span>
      <span
        v-else-if="article.category"
        class="rounded-full px-2 py-1 text-xs"
        :style="{
          backgroundColor: article.category.color ? article.category.color + '20' : 'var(--theme-bg-tertiary)',
          color: article.category.color || 'var(--theme-primary)'
        }"
      >
        {{ article.category.name }}
      </span>
      <span v-else class="rounded-full bg-surface-tertiary px-2 py-1 text-primary">
        {{ article.categoryName }}
      </span>
      <span>{{ formatDateCN(article.publishTime) }}</span>
      <span v-if="article.isTop" class="text-warning">置顶</span>
    </div>

    <h3 class="mb-3 text-xl font-bold text-content-primary group-hover:text-primary">
      {{ article.title }}
    </h3>

    <p class="mb-4 line-clamp-3 text-content-secondary">
      {{ summary }}
    </p>

    <div class="flex items-center justify-between text-sm text-content-tertiary">
      <div class="flex gap-4">
        <span>阅读 {{ article.viewCount }}</span>
        <span>点赞 {{ article.likeCount }}</span>
      </div>
      <div v-if="article.tags?.length" class="flex gap-2">
        <span
          v-for="(tag, index) in article.tags.slice(0, 3)"
          :key="index"
          class="rounded bg-surface-tertiary px-2 py-1 text-xs"
        >
          {{ tag }}
        </span>
      </div>
    </div>
  </article>
</template>
