<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getTagList } from '@/api/tag'
import type { Tag } from '@/types/tag'

const router = useRouter()
const tags = ref<Tag[]>([])
const loading = ref(false)

async function fetchTags(): Promise<void> {
  loading.value = true
  try {
    const res = await getTagList()
    tags.value = res
  } finally {
    loading.value = false
  }
}

// 计算标签大小 (0.875rem ~ 1.5rem)
function getTagSize(count: number): string {
  const maxCount = Math.max(...tags.value.map(t => t.articleCount), 1)
  const min = 0.875
  const max = 1.5
  const size = min + (count / maxCount) * (max - min)
  return `${size.toFixed(2)}rem`
}

onMounted(fetchTags)
</script>

<template>
  <div class="tag-page">
    <!-- Page Header -->
    <section class="bg-surface-tertiary py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <h1 class="text-3xl font-bold text-content-primary">标签云</h1>
        <p class="mt-2 text-content-secondary">共 {{ tags.length }} 个标签，涵盖各种技术主题</p>
      </div>
    </section>

    <!-- Tag Cloud -->
    <section class="py-16">
      <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <!-- Loading -->
        <div v-if="loading" class="flex flex-wrap justify-center gap-3">
          <div v-for="i in 20" :key="i" class="h-10 w-24 bg-surface-tertiary rounded-full animate-pulse" />
        </div>

        <!-- Empty -->
        <div v-else-if="tags.length === 0" class="text-center py-20">
          <el-icon :size="64" class="text-content-tertiary/30 mb-4"><CollectionTag /></el-icon>
          <p class="text-content-tertiary">暂无标签</p>
        </div>

        <!-- Tags -->
        <div v-else class="flex flex-wrap justify-center gap-3">
          <button
            v-for="tag in tags"
            :key="tag.id"
            class="inline-flex items-center px-4 py-2 rounded-full bg-surface-secondary border border-border font-medium transition-all duration-150 hover:border-primary hover:text-primary hover:shadow-sm"
            :style="{ fontSize: getTagSize(tag.articleCount) }"
            @click="router.push(`/article?tag=${tag.id}`)"
          >
            {{ tag.name }}
            <span class="ml-1.5 text-content-tertiary text-sm">{{ tag.articleCount }}</span>
          </button>
        </div>
      </div>
    </section>
  </div>
</template>
