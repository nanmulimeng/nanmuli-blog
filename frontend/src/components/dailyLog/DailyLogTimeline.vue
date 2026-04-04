<script setup lang="ts">
import DailyLogCard from './DailyLogCard.vue'
import type { DailyLog } from '@/types/dailyLog'

defineProps<{
  logs: DailyLog[]
  loading?: boolean
}>()

const emit = defineEmits<{
  click: [id: number]
}>()

function handleLogClick(id: number): void {
  emit('click', id)
}
</script>

<template>
  <div class="space-y-6">
    <div v-if="loading" class="space-y-6">
      <el-skeleton v-for="i in 3" :key="i" :rows="3" animated />
    </div>

    <div v-else-if="logs.length === 0" class="py-12 text-center text-gray-500">
      暂无日志
    </div>

    <div v-else class="relative space-y-6">
      <!-- 时间线轴线 -->
      <div class="absolute left-4 top-0 bottom-0 w-px bg-gray-200" />

      <div
        v-for="log in logs"
        :key="log.id"
        class="relative pl-12"
      >
        <!-- 时间线节点 -->
        <div class="absolute left-2 top-6 h-4 w-4 rounded-full border-2 border-white bg-blue-500 shadow" />
        <DailyLogCard :log="log" @click="handleLogClick" />
      </div>
    </div>
  </div>
</template>
