<script setup lang="ts">
import { computed } from 'vue'
import type { Article } from '@/types/article'

const props = defineProps<{
  article: Article
}>()

const emit = defineEmits<{
  click: [id: number]
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
    class="group cursor-pointer rounded-xl border bg-white p-6 transition-shadow hover:shadow-lg"
    @click="handleClick"
  >
    <div class="mb-4 flex items-center gap-3 text-sm text-gray-500">
      <span class="rounded-full bg-blue-50 px-2 py-1 text-blue-600">
        {{ article.categoryName }}
      </span>
      <span>{{ article.publishTime?.split('T')[0] }}</span>
      <span v-if="article.isTop" class="text-amber-500">置顶</span>
    </div>

    <h3 class="mb-3 text-xl font-bold text-gray-900 group-hover:text-blue-600">
      {{ article.title }}
    </h3>

    <p class="mb-4 line-clamp-3 text-gray-600">
      {{ summary }}
    </p>

    <div class="flex items-center justify-between text-sm text-gray-500">
      <div class="flex gap-4">
        <span>阅读 {{ article.viewCount }}</span>
        <span>点赞 {{ article.likeCount }}</span>
      </div>
      <div v-if="article.tags?.length" class="flex gap-2">
        <span
          v-for="tag in article.tags.slice(0, 3)"
          :key="tag.id"
          class="rounded bg-gray-100 px-2 py-1 text-xs"
        >
          {{ tag.name }}
        </span>
      </div>
    </div>
  </article>
</template>
