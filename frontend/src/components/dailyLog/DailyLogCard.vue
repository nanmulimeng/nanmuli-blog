<script setup lang="ts">
import type { DailyLog } from '@/types/dailyLog'
import { formatDate } from '@/utils/format'

const props = defineProps<{
  log: DailyLog
}>()

const emit = defineEmits<{
  click: [id: number]
}>()

const moodMap: Record<string, { emoji: string; label: string; color: string }> = {
  happy: { emoji: '😊', label: '开心', color: '#f59e0b' },
  excited: { emoji: '🤩', label: '兴奋', color: '#ef4444' },
  normal: { emoji: '😐', label: '平静', color: '#6b7280' },
  tired: { emoji: '😴', label: '疲惫', color: '#8b5cf6' },
}

function handleClick(): void {
  emit('click', props.log.id)
}
</script>

<template>
  <article
    class="group cursor-pointer rounded-xl border bg-white p-6 transition-shadow hover:shadow-lg"
    @click="handleClick"
  >
    <div class="mb-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <span class="text-2xl">{{ moodMap[log.mood]?.emoji || '😐' }}</span>
        <div>
          <div
            class="text-sm font-medium"
            :style="{ color: moodMap[log.mood]?.color || '#6b7280' }"
          >
            {{ moodMap[log.mood]?.label || '平静' }}
          </div>
          <div class="text-xs text-gray-400">{{ formatDate(log.logDate) }}</div>
        </div>
      </div>
      <div v-if="log.weather" class="text-sm text-gray-500">
        {{ log.weather }}
      </div>
    </div>

    <p class="mb-4 line-clamp-4 text-gray-700">
      {{ log.content.replace(/[#*`_\[\]]/g, '').slice(0, 200) }}
    </p>

    <div class="flex items-center justify-between">
      <div v-if="log.tags?.length" class="flex flex-wrap gap-1">
        <span
          v-for="tag in log.tags.slice(0, 3)"
          :key="tag"
          class="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
        >
          #{{ tag }}
        </span>
      </div>
      <div class="text-xs text-gray-400">{{ log.wordCount }} 字</div>
    </div>
  </article>
</template>
