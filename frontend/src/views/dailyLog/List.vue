<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getDailyLogList } from '@/api/dailyLog'
import { formatDateCN, formatMonthCN } from '@/utils/format'
import type { DailyLog } from '@/types/dailyLog'

const router = useRouter()

const logs = ref<DailyLog[]>([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const moodMap: Record<string, { icon: string; label: string; color: string }> = {
  happy: { icon: 'Sunny', label: '开心', color: '#f59e0b' },
  excited: { icon: 'Star', label: '兴奋', color: '#ef4444' },
  normal: { icon: 'Minus', label: '平静', color: '#6b7280' },
  tired: { icon: 'Moon', label: '疲惫', color: '#6366f1' },
}

// 按月份分组
const groupedLogs = computed(() => {
  const groups: Record<string, DailyLog[]> = {}
  logs.value.forEach((log: DailyLog) => {
    const month = log.logDate?.substring(0, 7) || ''
    if (!month) return
    if (!groups[month]) {
      groups[month] = []
    }
    const arr = groups[month]
    if (arr) {
      arr.push(log)
    }
  })
  return groups
})

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
  <div class="daily-log-page">
    <!-- Page Header -->
    <section class="bg-gray-50 py-12">
      <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center">
        <h1 class="text-3xl font-bold text-gray-900">技术日志</h1>
        <p class="mt-2 text-gray-500">记录每日技术学习与思考</p>
      </div>
    </section>

    <!-- Timeline -->
    <section class="py-12">
      <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <!-- Loading -->
        <div v-if="loading" class="space-y-8">
          <div v-for="i in 3" :key="i" class="bg-white rounded-xl p-6 border border-gray-100">
            <el-skeleton :rows="2" animated />
          </div>
        </div>

        <!-- Empty -->
        <div v-else-if="logs.length === 0" class="text-center py-20">
          <el-icon :size="64" class="text-gray-200 mb-4"><Timer /></el-icon>
          <p class="text-gray-500">暂无日志</p>
        </div>

        <!-- Timeline Content -->
        <div v-else class="relative">
          <div
            v-for="(monthLogs, month) in groupedLogs"
            :key="month"
            class="mb-12"
          >
            <!-- Month Header -->
            <div class="relative flex items-center justify-center mb-8">
              <div class="absolute left-0 right-0 h-px bg-gray-200" />
              <span class="relative px-4 bg-gray-50 text-lg font-semibold text-gray-900">
                {{ formatMonthCN(month) }}
              </span>
            </div>

            <!-- Log Items -->
            <div class="space-y-6">
              <div
                v-for="log in monthLogs"
                :key="log.id"
                class="relative pl-12"
              >
                <!-- Timeline Dot -->
                <div
                  class="absolute left-0 w-8 h-8 rounded-full flex items-center justify-center z-10"
                  :style="{ backgroundColor: moodMap[log.mood]?.color + '20' || '#e5e7eb' }"
                >
                  <el-icon
                    :size="16"
                    :style="{ color: moodMap[log.mood]?.color || '#6b7280' }"
                  >
                    <component :is="moodMap[log.mood]?.icon || 'Minus'" />
                  </el-icon>
                </div>

                <!-- Log Card -->
                <div
                  class="bg-white rounded-xl p-5 border border-gray-100 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
                  @click="router.push(`/daily-log/${log.id}`)"
                >
                  <div class="flex items-center justify-between mb-3">
                    <span class="text-sm font-medium text-primary-600">
                      {{ formatDateCN(log.logDate) }}
                    </span>
                    <div class="flex items-center gap-2">
                      <span
                        v-if="log.mood"
                        class="text-xs px-2 py-1 rounded-full"
                        :style="{
                          backgroundColor: moodMap[log.mood]?.color + '15',
                          color: moodMap[log.mood]?.color
                        }"
                      >
                        {{ moodMap[log.mood]?.label }}
                      </span>
                      <span v-if="log.weather" class="text-sm text-gray-400">{{ log.weather }}</span>
                    </div>
                  </div>

                  <div
                    class="prose prose-sm max-w-none text-gray-700 line-clamp-3"
                    v-html="log.contentHtml"
                  />

                  <div v-if="log.tags?.length" class="mt-4 flex flex-wrap gap-2">
                    <span
                      v-for="tag in log.tags"
                      :key="tag"
                      class="px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600"
                    >
                      #{{ tag }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div v-if="total > pageSize" class="mt-12 flex justify-center">
          <el-pagination
            :current-page="currentPage"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next"
            background
            @current-change="handlePageChange"
          />
        </div>
      </div>
    </section>
  </div>
</template>
