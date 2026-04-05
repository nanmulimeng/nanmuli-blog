<script setup lang="ts">
import type { DailyLog } from '@/types/dailyLog'
import { formatDate } from '@/utils/format'

const props = defineProps<{
  log: DailyLog
}>()

const emit = defineEmits<{
  click: [id: string]
}>()

const moodMap: Record<string, { icon: string; label: string; color: string }> = {
  happy: { icon: 'Sunny', label: '开心', color: '#f59e0b' },
  excited: { icon: 'Star', label: '兴奋', color: '#ef4444' },
  normal: { icon: 'Minus', label: '平静', color: '#64748B' },
  tired: { icon: 'Moon', label: '疲惫', color: '#3B82F6' },
}

function handleClick(): void {
  emit('click', props.log.id)
}
</script>

<template>
  <article
    class="group cursor-pointer rounded-xl border bg-surface-secondary p-6 transition-shadow hover:shadow-lg"
    @click="handleClick"
  >
    <div class="mb-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div
          class="flex h-10 w-10 items-center justify-center rounded-full"
          :style="{ backgroundColor: (moodMap[log.mood]?.color || '#64748B') + '20' }"
        >
          <el-icon
            :size="20"
            :style="{ color: moodMap[log.mood]?.color || '#64748B' }"
          >
            <component :is="moodMap[log.mood]?.icon || 'Minus'" />
          </el-icon>
        </div>
        <div>
          <div
            class="text-sm font-medium"
            :style="{ color: moodMap[log.mood]?.color || '#64748B' }"
          >
            {{ moodMap[log.mood]?.label || '平静' }}
          </div>
          <div class="text-xs text-content-tertiary">{{ formatDate(log.logDate) }}</div>
        </div>
      </div>
      <div v-if="log.weather" class="text-sm text-content-tertiary">
        {{ log.weather }}
      </div>
    </div>

    <p class="mb-4 line-clamp-4 text-content-secondary">
      {{ log.content.replace(/[#*`_\[\]]/g, '').slice(0, 200) }}
    </p>

    <div class="flex items-center justify-between">
      <div v-if="log.tags?.length" class="flex flex-wrap gap-1">
        <span
          v-for="tag in log.tags.slice(0, 3)"
          :key="tag"
          class="rounded bg-surface-tertiary px-2 py-0.5 text-xs text-content-secondary"
        >
          #{{ tag }}
        </span>
      </div>
      <div class="text-xs text-content-tertiary">{{ log.wordCount }} 字</div>
    </div>
  </article>
</template>
