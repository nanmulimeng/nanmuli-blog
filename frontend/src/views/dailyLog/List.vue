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

const moodMap: Record<string, { icon: string; label: string; color: string; bgColor: string }> = {
  happy: { icon: 'Sunny', label: '开心', color: '#f59e0b', bgColor: '#fef3c7' },
  excited: { icon: 'Star', label: '兴奋', color: '#ef4444', bgColor: '#fee2e2' },
  normal: { icon: 'Minus', label: '平静', color: '#64748B', bgColor: '#f1f5f9' },
  tired: { icon: 'Moon', label: '疲惫', color: '#3B82F6', bgColor: '#dbeafe' },
}

// 统计数据
const stats = computed(() => {
  const totalWords = logs.value.reduce((sum, log) => sum + (log.wordCount || 0), 0)
  const totalDays = new Set(logs.value.map(log => log.logDate)).size
  return {
    totalLogs: logs.value.length,
    totalWords,
    totalDays,
    avgWords: logs.value.length > 0 ? Math.round(totalWords / logs.value.length) : 0
  }
})

// 提取纯文本摘要
function extractSummary(html: string, maxLength: number = 150): string {
  if (!html) return ''
  const text = html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim()
  return text.length > maxLength ? text.slice(0, maxLength) + '...' : text
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
    <section class="py-12">
      <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center">
        <h1 class="text-3xl font-bold text-content-primary">技术日志</h1>
        <p class="mt-2 text-content-secondary">记录每日技术学习与思考</p>
      </div>
    </section>

    <!-- Stats Overview -->
    <section v-if="!loading && logs.length > 0" class="pb-8">
      <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="bg-surface-primary rounded-xl p-4 border border-border text-center">
            <div class="text-2xl font-bold text-primary">{{ stats.totalLogs }}</div>
            <div class="text-xs text-content-tertiary mt-1">篇日志</div>
          </div>
          <div class="bg-surface-primary rounded-xl p-4 border border-border text-center">
            <div class="text-2xl font-bold text-success">{{ stats.totalWords }}</div>
            <div class="text-xs text-content-tertiary mt-1">总字数</div>
          </div>
          <div class="bg-surface-primary rounded-xl p-4 border border-border text-center">
            <div class="text-2xl font-bold text-warning">{{ stats.avgWords }}</div>
            <div class="text-xs text-content-tertiary mt-1">篇均字数</div>
          </div>
          <div class="bg-surface-primary rounded-xl p-4 border border-border text-center">
            <div class="text-2xl font-bold text-info">{{ stats.totalDays }}</div>
            <div class="text-xs text-content-tertiary mt-1">记录天数</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Timeline -->
    <section class="py-8">
      <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <!-- Loading -->
        <div v-if="loading" class="space-y-8">
          <div v-for="i in 3" :key="i" class="bg-surface-primary rounded-xl p-6 border border-border">
            <el-skeleton :rows="3" animated />
          </div>
        </div>

        <!-- Empty -->
        <div v-else-if="logs.length === 0" class="text-center py-20">
          <el-icon :size="64" class="text-content-tertiary/30 mb-4"><Timer /></el-icon>
          <p class="text-content-tertiary">暂无日志</p>
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
              <div class="absolute left-0 right-0 h-px bg-border" />
              <span class="relative px-4 bg-surface-primary text-lg font-semibold text-content-primary">
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
                  :style="{ backgroundColor: moodMap[log.mood]?.color + '20' || 'var(--theme-surface-tertiary)' }"
                >
                  <el-icon
                    :size="16"
                    :style="{ color: moodMap[log.mood]?.color || '#64748B' }"
                  >
                    <component :is="moodMap[log.mood]?.icon || 'Minus'" />
                  </el-icon>
                </div>

                <!-- Log Card -->
                <div
                  class="bg-surface-primary rounded-xl p-5 border border-border shadow-sm hover:shadow-md transition-all cursor-pointer group"
                  @click="router.push(`/daily-log/${log.id}`)"
                >
                  <!-- Header -->
                  <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                      <span class="text-sm font-medium text-primary">
                        {{ formatDateCN(log.logDate) }}
                      </span>
                      <span v-if="log.wordCount" class="text-xs text-content-tertiary">
                        {{ log.wordCount }} 字
                      </span>
                    </div>
                    <div class="flex items-center gap-2">
                      <span
                        v-if="log.mood"
                        class="flex items-center gap-1 text-xs px-2 py-1 rounded-full"
                        :style="{
                          backgroundColor: moodMap[log.mood]?.color + '15',
                          color: moodMap[log.mood]?.color
                        }"
                      >
                        <el-icon :size="12"><component :is="moodMap[log.mood]?.icon" /></el-icon>
                        {{ moodMap[log.mood]?.label }}
                      </span>
                      <span v-if="log.weather" class="text-sm text-content-tertiary flex items-center gap-1">
                        <el-icon :size="14"><PartlyCloudy /></el-icon>
                        {{ log.weather }}
                      </span>
                    </div>
                  </div>

                  <!-- Content Summary -->
                  <p class="text-content-secondary line-clamp-3 mb-3">
                    {{ extractSummary(log.contentHtml) }}
                  </p>

                  <!-- Footer -->
                  <div class="flex items-center justify-between pt-3 border-t border-border">
                    <!-- Category -->
                    <div v-if="log.category" class="flex items-center gap-1">
                      <span
                        class="text-xs px-2 py-0.5 rounded"
                        :style="{
                          backgroundColor: log.category.color ? log.category.color + '20' : 'var(--theme-bg-tertiary)',
                          color: log.category.color || 'var(--theme-primary)'
                        }"
                      >
                        {{ log.category.name }}
                      </span>
                    </div>
                    <!-- Read More -->
                    <div class="flex items-center gap-1 text-sm text-primary group-hover:underline">
                      <span>阅读全文</span>
                      <el-icon :size="14"><ArrowRight /></el-icon>
                    </div>
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
