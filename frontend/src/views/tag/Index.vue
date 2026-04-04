<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getTagCloud } from '@/api/tag'
import type { Tag } from '@/types/tag'

const router = useRouter()
const loading = ref(false)
const tags = ref<Tag[]>([])

async function fetchTags(): Promise<void> {
  loading.value = true
  try {
    tags.value = await getTagCloud()
  } finally {
    loading.value = false
  }
}

function getTagSize(count: number): string {
  if (count >= 50) return 'text-2xl'
  if (count >= 30) return 'text-xl'
  if (count >= 10) return 'text-lg'
  return 'text-base'
}

onMounted(fetchTags)
</script>

<template>
  <div class="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
    <h1 class="mb-8 text-3xl font-bold text-gray-900">标签云</h1>

    <div v-if="loading" class="flex justify-center py-20">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else class="flex flex-wrap gap-4">
      <span
        v-for="tag in tags"
        :key="tag.id"
        class="cursor-pointer rounded-full px-4 py-2 font-medium transition-all hover:shadow-md"
        :class="getTagSize(tag.articleCount)"
        :style="{
          backgroundColor: tag.color ? `${tag.color}20` : '#e5e7eb',
          color: tag.color || '#374151',
        }"
        @click="router.push(`/article?tag=${tag.id}`)"
      >
        {{ tag.name }}
        <span class="ml-1 text-sm opacity-70">({{ tag.articleCount }})</span>
      </span>
    </div>
  </div>
</template>
