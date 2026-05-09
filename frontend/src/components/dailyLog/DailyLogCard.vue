<script setup lang="ts">
import type { DailyLog } from '@/types/dailyLog'
import { formatDate } from '@/utils/format'
import { MOOD_MAP, MOOD_DEFAULT_COLOR, MOOD_DEFAULT_ICON, MOOD_DEFAULT_LABEL } from '@/constants/mood'

const props = defineProps<{
  log: DailyLog
}>()

const emit = defineEmits<{
  click: [id: string]
}>()

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
          :style="{ backgroundColor: (MOOD_MAP[log.mood]?.color || MOOD_DEFAULT_COLOR) + '20' }"
        >
          <el-icon
            :size="20"
            :style="{ color: MOOD_MAP[log.mood]?.color || MOOD_DEFAULT_COLOR }"
          >
            <component :is="MOOD_MAP[log.mood]?.icon || MOOD_DEFAULT_ICON" />
          </el-icon>
        </div>
        <div>
          <div
            class="text-sm font-medium"
            :style="{ color: MOOD_MAP[log.mood]?.color || MOOD_DEFAULT_COLOR }"
          >
            {{ MOOD_MAP[log.mood]?.label || MOOD_DEFAULT_LABEL }}
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

    <div class="flex items-center justify-end">
      <div class="text-xs text-content-tertiary">{{ log.wordCount }} 字</div>
    </div>
  </article>
</template>
