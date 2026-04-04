<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getDailyLogList } from '@/api/dailyLog'
import { formatDate } from '@/utils/format'
import type { DailyLog } from '@/types/dailyLog'

const router = useRouter()
const loading = ref(false)
const logs = ref<DailyLog[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

const moodMap: Record<string, { emoji: string; label: string }> = {
  happy: { emoji: '😊', label: '开心' },
  excited: { emoji: '🤩', label: '兴奋' },
  normal: { emoji: '😐', label: '平静' },
  tired: { emoji: '😴', label: '疲惫' },
}

async function fetchLogs(): Promise<void> {
  loading.value = true
  try {
    const res = await getDailyLogList({
      current: currentPage.value,
      size: pageSize.value,
    })
    logs.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handlePageChange(page: number): void {
  currentPage.value = page
  fetchLogs()
}

onMounted(fetchLogs)
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
    <h1 class="mb-8 text-3xl font-bold text-gray-900">技术日志</h1>

    <el-timeline v-if="!loading">
      <el-timeline-item
        v-for="log in logs"
        :key="log.id"
        :timestamp="formatDate(log.logDate)"
        placement="top"
      >
        <div
          class="cursor-pointer rounded-xl border bg-white p-6 transition-shadow hover:shadow-lg"
          @click="router.push(`/daily-log/${log.id}`)"
        >
          <div class="mb-4 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-2xl">{{ moodMap[log.mood]?.emoji || '😐' }}</span>
              <span class="text-sm text-gray-500">{{ moodMap[log.mood]?.label }}</span>
            </div>
            <span v-if="log.weather" class="text-sm text-gray-500">
              {{ log.weather }}
            </span>
          </div>

          <div class="markdown-body line-clamp-3" v-html="log.contentHtml" />

          <div v-if="log.tags?.length" class="mt-4 flex flex-wrap gap-2">
            <span
              v-for="tag in log.tags"
              :key="tag"
              class="rounded bg-gray-100 px-2 py-1 text-xs text-gray-600"
            >
              #{{ tag }}
            </span>
          </div>
        </div>
      </el-timeline-item>
    </el-timeline>

    <div class="mt-8 flex justify-center">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>
