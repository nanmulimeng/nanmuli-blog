<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getDailyLogById, getDailyLogList } from '@/api/dailyLog'
import { formatDateCN, formatDateTimeCN, formatTimeAgoCN } from '@/utils/format'
import { ArrowRight, Calendar, PartlyCloudy, Document, Clock, ArrowLeft } from '@element-plus/icons-vue'
import type { DailyLog } from '@/types/dailyLog'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const log = ref<DailyLog | null>(null)
const relatedLogs = ref<DailyLog[]>([])

const moodMap: Record<string, { icon: string; label: string; color: string; description: string }> = {
  happy: { icon: 'Sunny', label: '开心', color: '#f59e0b', description: '充满能量，效率很高' },
  excited: { icon: 'Star', label: '兴奋', color: '#ef4444', description: '充满激情，学习热情高涨' },
  normal: { icon: 'Minus', label: '平静', color: '#64748B', description: '稳步推进，保持节奏' },
  tired: { icon: 'Moon', label: '疲惫', color: '#3B82F6', description: '需要休息，适当放松' },
}

// 阅读时间估算（分钟）
const readingTime = computed(() => {
  if (!log.value?.wordCount) return 1
  return Math.max(1, Math.ceil(log.value.wordCount / 300))
})

async function fetchLog(): Promise<void> {
  const id = route.params.id as string
  if (!id) {
    router.push('/404')
    return
  }

  loading.value = true
  try {
    log.value = await getDailyLogById(id)
    fetchRelatedLogs()
  } catch {
    router.push('/404')
  } finally {
    loading.value = false
  }
}

// 获取相关日志（相近日期或相同心情）
async function fetchRelatedLogs(): Promise<void> {
  if (!log.value) return
  try {
    const res = await getDailyLogList({ current: 1, size: 5 })
    relatedLogs.value = res.records
      .filter((l: DailyLog) => l.id !== log.value?.id)
      .slice(0, 3)
  } catch {
    // ignore
  }
}

onMounted(fetchLog)
</script>

<template>
  <div class="daily-log-detail-page">
    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center min-h-[60vh]">
      <div class="w-full max-w-2xl px-4">
        <el-skeleton :rows="8" animated />
      </div>
    </div>

    <template v-else-if="log">
      <!-- Header -->
      <section class="pt-24 pb-8 bg-gradient-to-b from-primary-50/50 to-transparent">
        <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <!-- Breadcrumb -->
          <nav class="mb-6 flex items-center gap-2 text-sm text-content-tertiary">
            <router-link to="/" class="hover:text-primary transition-colors">首页</router-link>
            <el-icon><ArrowRight class="text-xs" /></el-icon>
            <router-link to="/daily-log" class="hover:text-primary transition-colors">日志</router-link>
            <el-icon><ArrowRight class="text-xs" /></el-icon>
            <span class="text-content-primary">{{ formatDateCN(log.logDate) }}</span>
          </nav>

          <!-- Mood & Date -->
          <div class="flex items-center gap-4 mb-6">
            <div
              class="w-16 h-16 rounded-2xl flex items-center justify-center shadow-lg"
              :style="{ backgroundColor: moodMap[log.mood]?.color + '20' || 'var(--theme-surface-tertiary)' }"
            >
              <el-icon
                :size="32"
                :style="{ color: moodMap[log.mood]?.color || '#64748B' }"
              >
                <component :is="moodMap[log.mood]?.icon || 'Minus'" />
              </el-icon>
            </div>
            <div>
              <div
                class="text-xl font-semibold"
                :style="{ color: moodMap[log.mood]?.color || '#6b7280' }"
              >
                {{ moodMap[log.mood]?.label || '平静' }}
              </div>
              <div class="text-sm text-content-tertiary mt-1">
                {{ moodMap[log.mood]?.description }}
              </div>
            </div>
          </div>

          <!-- Meta Info -->
          <div class="flex flex-wrap items-center gap-4 text-sm">
            <span class="flex items-center gap-2 text-content-secondary">
              <el-icon><Calendar /></el-icon>
              {{ formatDateCN(log.logDate) }}
            </span>
            <span v-if="log.weather" class="flex items-center gap-2 text-content-secondary">
              <el-icon><PartlyCloudy /></el-icon>
              {{ log.weather }}
            </span>
            <span class="flex items-center gap-2 text-content-secondary">
              <el-icon><Document /></el-icon>
              {{ log.wordCount || 0 }} 字
            </span>
            <span class="flex items-center gap-2 text-content-secondary">
              <el-icon><Clock /></el-icon>
              {{ readingTime }} 分钟阅读
            </span>
            <span v-if="log.category" class="px-2 py-0.5 rounded text-xs"
              :style="{
                backgroundColor: log.category.color ? log.category.color + '20' : 'var(--theme-bg-tertiary)',
                color: log.category.color || 'var(--theme-primary)'
              }"
            >
              {{ log.category.name }}
            </span>
          </div>
        </div>
      </section>

      <!-- Content -->
      <section class="py-8">
        <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <article class="bg-surface-secondary rounded-2xl p-8 shadow-sm border border-border">
            <div class="prose prose-lg max-w-none dark:prose-invert" v-html="log.contentHtml" />
          </article>

          <!-- Content Footer -->
          <div class="mt-6 flex items-center justify-between text-sm text-content-tertiary">
            <span>发布于 {{ formatDateTimeCN(log.createTime) }}</span>
            <span v-if="log.updateTime && log.updateTime !== log.createTime">
              更新于 {{ formatTimeAgoCN(log.updateTime) }}
            </span>
          </div>

          <!-- Navigation -->
          <div class="mt-8">
            <button
              class="flex items-center gap-2 px-4 py-3 rounded-xl bg-surface-secondary border border-border text-content-secondary hover:border-primary hover:text-primary transition-colors"
              @click="router.push('/daily-log')"
            >
              <el-icon><ArrowLeft /></el-icon>
              <span>返回日志列表</span>
            </button>
          </div>
        </div>
      </section>

      <!-- Related Logs -->
      <section v-if="relatedLogs.length > 0" class="py-12 border-t border-border">
        <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <h3 class="text-lg font-semibold text-content-primary mb-6">相关日志</h3>
          <div class="space-y-4">
            <div
              v-for="related in relatedLogs"
              :key="related.id"
              class="flex items-center gap-4 p-4 rounded-xl bg-surface-secondary border border-border hover:border-primary cursor-pointer transition-colors"
              @click="router.push(`/daily-log/${related.id}`)"
            >
              <div
                class="w-10 h-10 rounded-xl flex items-center justify-center"
                :style="{ backgroundColor: moodMap[related.mood]?.color + '20' || 'var(--theme-surface-tertiary)' }"
              >
                <el-icon
                  :size="18"
                  :style="{ color: moodMap[related.mood]?.color || '#64748B' }"
                >
                  <component :is="moodMap[related.mood]?.icon || 'Minus'" />
                </el-icon>
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm text-content-primary font-medium truncate">
                  {{ formatDateCN(related.logDate) }} 的日志
                </div>
                <div class="text-xs text-content-tertiary mt-0.5">
                  {{ related.wordCount || 0 }} 字 · {{ related.mood ? moodMap[related.mood]?.label : '平静' }}
                </div>
              </div>
              <el-icon class="text-content-tertiary"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
