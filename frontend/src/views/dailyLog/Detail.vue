<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getDailyLogById } from '@/api/dailyLog'
import { formatDateCN, formatDateTimeCN } from '@/utils/format'
import type { DailyLog } from '@/types/dailyLog'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const log = ref<DailyLog | null>(null)

const moodMap: Record<string, { icon: string; label: string; color: string }> = {
  happy: { icon: 'Sunny', label: '开心', color: '#f59e0b' },
  excited: { icon: 'Star', label: '兴奋', color: '#ef4444' },
  normal: { icon: 'Minus', label: '平静', color: '#6b7280' },
  tired: { icon: 'Moon', label: '疲惫', color: '#6366f1' },
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
  <div class="daily-log-detail-page">
    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center min-h-[60vh]">
      <div class="w-full max-w-2xl px-4">
        <el-skeleton :rows="8" animated />
      </div>
    </div>

    <template v-else-if="log">
      <!-- Header -->
      <section class="pt-24 pb-8 bg-gradient-to-b from-primary-50/50 to-white">
        <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <div class="flex items-center gap-4 mb-6">
            <div
              class="w-14 h-14 rounded-2xl flex items-center justify-center"
              :style="{ backgroundColor: moodMap[log.mood]?.color + '15' || '#e5e7eb' }"
            >
              <el-icon
                :size="28"
                :style="{ color: moodMap[log.mood]?.color || '#6b7280' }"
              >
                <component :is="moodMap[log.mood]?.icon || 'Minus'" />
              </el-icon>
            </div>
            <div>
              <div class="text-sm text-gray-500">{{ formatDateCN(log.logDate) }}</div>
              <div
                class="text-lg font-semibold"
                :style="{ color: moodMap[log.mood]?.color || '#6b7280' }"
              >
                {{ moodMap[log.mood]?.label || '平静' }}
              </div>
            </div>
          </div>

          <div v-if="log.weather" class="flex items-center gap-2 text-sm text-gray-500">
            <el-icon><PartlyCloudy /></el-icon>
            <span>{{ log.weather }}</span>
          </div>
        </div>
      </section>

      <!-- Content -->
      <section class="py-8">
        <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <article class="bg-white rounded-xl p-8 shadow-sm border border-gray-100">
            <div class="prose prose-gray max-w-none" v-html="log.contentHtml" />

            <!-- Tags -->
            <div v-if="log.tags?.length" class="mt-8 pt-6 border-t border-gray-100">
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="tag in log.tags"
                  :key="tag"
                  class="px-3 py-1 rounded-full bg-gray-100 text-sm text-gray-600"
                >
                  #{{ tag }}
                </span>
              </div>
            </div>
          </article>

          <!-- Footer -->
          <div class="mt-8 text-center text-sm text-gray-400">
            发布于 {{ formatDateTimeCN(log.createTime) }}
          </div>

          <!-- Back Button -->
          <div class="mt-8 flex justify-center">
            <button
              class="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
              @click="router.push('/daily-log')"
            >
              <el-icon><ArrowLeft /></el-icon>
              返回日志列表
            </button>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
