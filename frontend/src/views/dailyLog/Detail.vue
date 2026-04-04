<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getDailyLogById } from '@/api/dailyLog'
import { formatDate, fromNow } from '@/utils/format'
import type { DailyLog } from '@/types/dailyLog'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const log = ref<DailyLog | null>(null)

const moodMap: Record<string, { emoji: string; label: string; color: string }> = {
  happy: { emoji: '😊', label: '开心', color: '#f59e0b' },
  excited: { emoji: '🤩', label: '兴奋', color: '#ef4444' },
  normal: { emoji: '😐', label: '平静', color: '#6b7280' },
  tired: { emoji: '😴', label: '疲惫', color: '#8b5cf6' },
}

async function fetchLog(): Promise<void> {
  const id = Number(route.params.id)
  if (!id) {
    router.push('/404')
    return
  }

  loading.value = true
  try {
    log.value = await getDailyLogById(id)
  } catch {
    router.push('/404')
  } finally {
    loading.value = false
  }
}

onMounted(fetchLog)
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
    <div v-if="loading" class="space-y-4">
      <el-skeleton :rows="5" animated />
    </div>

    <article v-else-if="log" class="rounded-xl border bg-white p-8">
      <header class="mb-8 border-b pb-8">
        <div class="mb-4 flex items-center gap-4">
          <span class="text-4xl">{{ moodMap[log.mood]?.emoji || '😐' }}</span>
          <div>
            <div class="text-lg font-medium" :style="{ color: moodMap[log.mood]?.color }">
              {{ moodMap[log.mood]?.label || '未知' }}
            </div>
            <div class="text-sm text-gray-500">{{ formatDate(log.logDate) }}</div>
          </div>
        </div>

        <div v-if="log.weather" class="flex items-center gap-2 text-sm text-gray-500">
          <el-icon><Sunny /></el-icon>
          <span>{{ log.weather }}</span>
        </div>
      </header>

      <div class="markdown-body" v-html="log.contentHtml" />

      <div v-if="log.tags?.length" class="mt-8 flex flex-wrap gap-2">
        <span
          v-for="tag in log.tags"
          :key="tag"
          class="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-600"
        >
          #{{ tag }}
        </span>
      </div>

      <footer class="mt-8 border-t pt-8">
        <div class="text-sm text-gray-500">发布于 {{ fromNow(log.createTime) }}</div>
      </footer>
    </article>
  </div>
</template>
