<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getDailyLogById, getDailyLogList } from '@/api/dailyLog'
import { formatDateCN, formatDateTimeCN, formatTimeAgoCN } from '@/utils/format'
import { sanitize } from '@/utils/sanitize'
import { ArrowRight, Calendar, PartlyCloudy, Document, Clock, ArrowLeft } from '@element-plus/icons-vue'
import type { DailyLog } from '@/types/dailyLog'
import { MOOD_MAP, MOOD_DEFAULT_COLOR, MOOD_DEFAULT_ICON, MOOD_DEFAULT_LABEL } from '@/constants/mood'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const log = ref<DailyLog | null>(null)
const relatedLogs = ref<DailyLog[]>([])

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
    const fetched = await getDailyLogById(id)
    log.value = fetched
    fetchRelatedLogs(fetched.id)
  } catch {
    router.push('/404')
  } finally {
    loading.value = false
  }
}

// 获取相关日志（相近日期或相同心情）
async function fetchRelatedLogs(currentId?: string): Promise<void> {
  const excludeId = currentId || log.value?.id
  if (!excludeId) return
  try {
    const res = await getDailyLogList({ current: 1, size: 5 })
    relatedLogs.value = res.records
      .filter((l: DailyLog) => l.id !== excludeId)
      .slice(0, 3)
  } catch {
    // ignore
  }
}

// 路由参数变化时重新获取数据（同组件复用场景）
watch(() => route.params.id, (newId) => {
  if (newId) fetchLog()
})

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
              :style="{ backgroundColor: (MOOD_MAP[log.mood]?.color || 'var(--theme-surface-tertiary)') + '20' }"
            >
              <el-icon
                :size="32"
                :style="{ color: MOOD_MAP[log.mood]?.color || MOOD_DEFAULT_COLOR }"
              >
                <component :is="MOOD_MAP[log.mood]?.icon || MOOD_DEFAULT_ICON" />
              </el-icon>
            </div>
            <div>
              <div
                class="text-xl font-semibold"
                :style="{ color: MOOD_MAP[log.mood]?.color || '#6b7280' }"
              >
                {{ MOOD_MAP[log.mood]?.label || MOOD_DEFAULT_LABEL }}
              </div>
              <div class="text-sm text-content-tertiary mt-1">
                {{ MOOD_MAP[log.mood]?.description }}
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
            <div class="prose prose-lg max-w-none dark:prose-invert" v-html="sanitize(log.contentHtml)" />
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
                :style="{ backgroundColor: (MOOD_MAP[related.mood]?.color || 'var(--theme-surface-tertiary)') + '20' }"
              >
                <el-icon
                  :size="18"
                  :style="{ color: MOOD_MAP[related.mood]?.color || MOOD_DEFAULT_COLOR }"
                >
                  <component :is="MOOD_MAP[related.mood]?.icon || MOOD_DEFAULT_ICON" />
                </el-icon>
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm text-content-primary font-medium truncate">
                  {{ formatDateCN(related.logDate) }} 的日志
                </div>
                <div class="text-xs text-content-tertiary mt-0.5">
                  {{ related.wordCount || 0 }} 字 · {{ related.mood ? MOOD_MAP[related.mood]?.label : MOOD_DEFAULT_LABEL }}
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
