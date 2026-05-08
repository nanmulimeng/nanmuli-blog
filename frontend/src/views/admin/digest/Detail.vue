<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getDigestByDate, getLatestDigest, getDigestByTaskId } from '@/api/collector'
import type { DigestDetail } from '@/types/collector'
import { CollectTaskStatusMap } from '@/types/collector'
import { ArrowLeft, Refresh, Calendar } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/markdown'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const digest = ref<DigestDetail | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null

// 路由参数解析：/admin/digest/latest | /admin/digest/:date | /admin/digest/task/:id
const routeMode = computed(() => {
  if (route.name === 'AdminDigestLatest' || !route.params.date) return 'latest'
  if (route.name === 'AdminDigestTaskDetail') return 'task'
  return 'date'
})

const routeValue = computed(() => {
  if (routeMode.value === 'task') return route.params.id as string
  return route.params.date as string
})

const isActive = computed(() => {
  if (!digest.value) return false
  return digest.value.status === 0 || digest.value.status === 1 || digest.value.status === 2
})

const categoryColors: Record<string, string> = {
  hot_trend: '#ef4444',
  open_source: '#f59e0b',
  tech_article: '#3b82f6',
  dev_tool: '#10b981',
  creative: '#8b5cf6',
  paper: '#6366f1',
}

async function fetchDigest(): Promise<void> {
  loading.value = true
  try {
    if (routeMode.value === 'latest') {
      digest.value = await getLatestDigest()
    } else if (routeMode.value === 'task') {
      const taskId = parseInt(routeValue.value, 10)
      if (isNaN(taskId)) {
        digest.value = null
        return
      }
      digest.value = await getDigestByTaskId(taskId)
    } else {
      digest.value = await getDigestByDate(routeValue.value)
    }
  } catch {
    digest.value = null
  } finally {
    loading.value = false
  }
}

function sectionBorderColor(category: string): string {
  return categoryColors[category] || '#6b7280'
}

function goBack(): void {
  router.push('/admin/digest')
}

function startPolling(): void {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    if (isActive.value && !loading.value) fetchDigest()
    else if (!isActive.value) stopPolling()
  }, 5000)
}

function stopPolling(): void {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  fetchDigest()
  startPolling()
})

watch(() => route.params, () => {
  if (route.name === 'AdminDigestLatest' || route.name === 'AdminDigestDate' || route.name === 'AdminDigestTaskDetail') {
    stopPolling()
    fetchDigest()
    startPolling()
  }
})

onUnmounted(stopPolling)
</script>

<template>
  <div v-loading="loading">
    <template v-if="digest">
      <div class="mb-6 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <el-button :icon="ArrowLeft" @click="goBack">返回列表</el-button>
          <el-icon :size="20" class="text-primary"><Calendar /></el-icon>
          <h2 class="text-xl font-bold text-content-primary">
            {{ digest.digest_date || '日报' }}
            <el-tag
              :type="CollectTaskStatusMap[digest.status]?.type || 'info'"
              size="small"
              class="ml-2"
            >
              <div class="flex items-center gap-1">
                <el-icon v-if="digest.status === 1 || digest.status === 2" :size="12" class="animate-spin">
                  <Refresh />
                </el-icon>
                {{ digest.status_label || CollectTaskStatusMap[digest.status]?.label || '未知' }}
              </div>
            </el-tag>
          </h2>
        </div>
      </div>

      <!-- Error Banner -->
      <div v-if="digest.error_message" class="mb-6 rounded-xl bg-error/10 border border-error/20 p-4">
        <div class="text-sm font-medium text-error">错误信息</div>
        <div class="mt-1 text-sm text-error/80">{{ digest.error_message }}</div>
      </div>

      <!-- Highlight Banner -->
      <div v-if="digest.highlight" class="mb-6 rounded-xl bg-primary/5 border border-primary/20 p-4">
        <div class="text-sm font-medium text-primary">今日亮点</div>
        <div class="mt-1 text-sm text-content-primary">{{ digest.highlight }}</div>
      </div>

      <!-- AI Summary -->
      <div v-if="digest.ai_summary" class="mb-6 rounded-2xl p-6 glass-card">
        <div class="mb-2 text-xs text-content-tertiary">AI 摘要</div>
        <div class="text-sm leading-relaxed text-content-secondary">{{ digest.ai_summary }}</div>

        <div v-if="digest.ai_tags?.length" class="mt-4 flex flex-wrap gap-2">
          <el-tag v-for="tag in digest.ai_tags" :key="tag" size="small" effect="plain">
            {{ tag }}
          </el-tag>
        </div>

        <div class="mt-3 flex gap-4 text-xs text-content-tertiary">
          <span v-if="digest.ai_duration">AI 耗时: {{ (digest.ai_duration / 1000).toFixed(1) }}s</span>
          <span v-if="digest.ai_tokens_used">Token: {{ digest.ai_tokens_used?.toLocaleString() }}</span>
        </div>
      </div>

      <!-- Structured Sections -->
      <div v-if="digest.sections?.length" class="space-y-6">
        <div
          v-for="section in digest.sections"
          :key="section.category"
          class="rounded-2xl border-l-4 bg-surface-secondary p-5 shadow-sm"
          :style="{ borderLeftColor: sectionBorderColor(section.category) }"
        >
          <h3 class="mb-4 flex items-center gap-2 text-lg font-semibold text-content-primary">
            <span v-if="section.emoji">{{ section.emoji }}</span>
            {{ section.category_name }}
            <span class="text-sm font-normal text-content-tertiary">({{ section.items.length }})</span>
          </h3>

          <div v-if="section.items.length" class="space-y-3">
            <div
              v-for="(item, idx) in section.items"
              :key="idx"
              class="group flex items-start gap-3 rounded-lg p-3 transition-colors hover:bg-surface-tertiary/50"
            >
              <span class="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-surface-tertiary text-xs font-medium text-content-secondary">
                {{ idx + 1 }}
              </span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <a
                    v-if="item.source_url"
                    :href="item.source_url"
                    target="_blank"
                    rel="noopener"
                    class="text-sm font-medium text-content-primary hover:text-primary transition-colors"
                  >
                    {{ item.title }}
                  </a>
                  <span v-else class="text-sm font-medium text-content-primary">{{ item.title }}</span>
                  <span class="text-xs text-content-tertiary">{{ item.source_name }}</span>
                </div>
                <div v-if="item.one_liner" class="mt-1 text-sm text-content-secondary">
                  {{ item.one_liner }}
                </div>
              </div>
            </div>
          </div>

          <div v-else class="text-sm text-content-tertiary py-2">暂无内容</div>
        </div>
      </div>

      <!-- Full Content (fallback) -->
      <div v-else-if="digest.ai_full_content" class="rounded-2xl p-6 glass-card">
        <h3 class="mb-4 text-lg font-semibold text-content-primary">完整内容</h3>
        <div
          class="prose prose-sm max-w-none text-sm text-content-secondary dark:prose-invert"
          v-html="renderMarkdown(digest.ai_full_content)"
        />
      </div>

      <!-- Processing placeholder -->
      <div v-if="isActive && !digest.sections?.length && !digest.ai_full_content" class="py-20 text-center">
        <el-icon :size="48" class="animate-spin text-primary"><Refresh /></el-icon>
        <div class="mt-4 text-content-secondary">
          {{ digest.status === 1 ? '正在爬取内容...' : 'AI 正在整理日报...' }}
        </div>
      </div>
    </template>

    <div v-if="!loading && !digest" class="py-20 text-center">
      <el-empty description="日报不存在" />
      <el-button type="primary" class="mt-4" @click="goBack">返回列表</el-button>
    </div>
  </div>
</template>
