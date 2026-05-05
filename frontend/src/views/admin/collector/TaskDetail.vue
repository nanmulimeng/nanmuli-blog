<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCollectTaskDetail, getCollectTaskPages, deleteCollectTask, retryCollectTask } from '@/api/collector'
import type { CollectTask, CollectPage } from '@/types/collector'
import { CollectTaskStatusMap, CollectTaskTypeMap } from '@/types/collector'
import { formatDateCN } from '@/utils/format'
import { renderMarkdown } from '@/utils/markdown'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Delete, Refresh, Document, Notebook } from '@element-plus/icons-vue'
import ConvertArticleDialog from '@/components/collector/ConvertArticleDialog.vue'
import ConvertDailyLogDialog from '@/components/collector/ConvertDailyLogDialog.vue'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id as string

const loading = ref(false)
const task = ref<CollectTask | null>(null)
const pages = ref<CollectPage[]>([])
const activePage = ref(0)
const markdownExpanded = ref<Record<number, boolean>>({})

const showConvertArticle = ref(false)
const showConvertDailyLog = ref(false)

let pollTimer: ReturnType<typeof setInterval> | null = null
let lastStatus: number | null = null

const isTerminal = computed(() => {
  if (!task.value) return false
  // PENDING(0)/COMPLETED(3)/FAILED(4) 均可删除；CRAWLING(1)/PROCESSING(2) 禁止删除
  return task.value.status === 0 || task.value.status === 3 || task.value.status === 4
})

const isActive = computed(() => {
  if (!task.value) return false
  return task.value.status === 0 || task.value.status === 1 || task.value.status === 2
})

const canConvert = computed(() => {
  if (!task.value) return false
  return task.value.status === 3
})

const progressColor = computed(() => {
  if (!task.value) return undefined
  return task.value.status === 4 ? '#EF4444' : undefined
})

async function fetchTask(): Promise<void> {
  loading.value = true
  try {
    task.value = await getCollectTaskDetail(taskId)
    const prev = lastStatus
    lastStatus = task.value?.status ?? null
    // 状态变为终态时拉一次 pages
    if (task.value?.status === 3 || task.value?.status === 4) {
      stopPolling()
      if (prev !== null && prev !== task.value.status) {
        await fetchPages()
      }
    }
  } finally {
    loading.value = false
  }
}

async function fetchPages(): Promise<void> {
  try {
    pages.value = await getCollectTaskPages(taskId)
  } catch { /* non-critical */ }
}

async function handleRetry(): Promise<void> {
  try {
    await ElMessageBox.confirm('确定要重试此任务吗？', '提示', { type: 'warning' })
    await retryCollectTask(taskId)
    ElMessage.success('任务已重新提交')
    fetchTask()
    startPolling()
  } catch (error: any) {
    if (error === 'cancel' || error?.message === 'cancel') return
  }
}

async function handleDelete(): Promise<void> {
  try {
    await ElMessageBox.confirm('确定要删除此任务吗？', '提示', { type: 'warning' })
    await deleteCollectTask(taskId)
    ElMessage.success('删除成功')
    router.push('/admin/collector')
  } catch (error: any) {
    if (error === 'cancel' || error?.message === 'cancel') return
  }
}

function formatDuration(ms: number | null): string {
  if (!ms) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function toggleMarkdown(idx: number): void {
  markdownExpanded.value[idx] = !markdownExpanded.value[idx]
}

function startPolling(): void {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    if (isActive.value && !loading.value) {
      fetchTask()
    } else if (!isActive.value) {
      stopPolling()
    }
  }, 5000)
}

function stopPolling(): void {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function goBack(): void {
  router.push('/admin/collector')
}

onMounted(async () => {
  await fetchTask()
  await fetchPages()
  if (isActive.value) startPolling()
})

onUnmounted(stopPolling)
</script>

<template>
  <div v-loading="loading">
    <template v-if="task">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <el-button :icon="ArrowLeft" @click="goBack">返回列表</el-button>
        <h2 class="text-xl font-bold text-content-primary">
          任务 #{{ task.id }}
          <el-tag :type="CollectTaskTypeMap[task.taskType]?.type || 'info'" size="small" class="ml-2">
            {{ CollectTaskTypeMap[task.taskType]?.label || task.taskType }}
          </el-tag>
        </h2>
      </div>

      <div class="flex items-center gap-2">
        <el-button
          v-if="canConvert && !task.articleId"
          type="primary"
          :icon="Document"
          @click="showConvertArticle = true"
        >
          转为文章
        </el-button>
        <el-button
          v-if="canConvert && !task.dailyLogId"
          type="primary"
          :icon="Notebook"
          plain
          @click="showConvertDailyLog = true"
        >
          转为日志
        </el-button>
        <el-button
          v-if="task.status === 4"
          type="warning"
          :icon="Refresh"
          @click="handleRetry"
        >
          重试
        </el-button>
        <el-button
          v-if="isTerminal"
          type="danger"
          :icon="Delete"
          plain
          @click="handleDelete"
        >
          删除
        </el-button>
      </div>
    </div>

    <!-- Basic Info Card -->
    <div class="mb-6 rounded-xl border border-border bg-surface-secondary p-6 shadow-sm">
      <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div v-if="task.sourceUrl">
          <div class="text-xs text-content-tertiary mb-1">目标 URL</div>
          <a :href="task.sourceUrl" target="_blank" rel="noopener" class="text-sm text-primary hover:underline break-all">
            {{ task.sourceUrl }}
          </a>
        </div>
        <div v-if="task.keyword">
          <div class="text-xs text-content-tertiary mb-1">搜索关键词</div>
          <div class="text-sm font-medium text-content-primary">{{ task.keyword }}</div>
        </div>
        <div>
          <div class="text-xs text-content-tertiary mb-1">状态</div>
          <el-tag :type="CollectTaskStatusMap[task.status]?.type || 'info'" size="small">
            <div class="flex items-center gap-1">
              <el-icon v-if="task.status === 1 || task.status === 2" :size="12" class="animate-spin">
                <Refresh />
              </el-icon>
              {{ CollectTaskStatusMap[task.status]?.label || '未知' }}
            </div>
          </el-tag>
        </div>
        <div>
          <div class="text-xs text-content-tertiary mb-1">进度</div>
          <div class="flex items-center gap-2">
            <el-progress
              :percentage="task.progressPercent"
              :stroke-width="10"
              :color="progressColor"
              class="flex-1"
            />
            <span class="text-sm font-medium text-content-primary">
              {{ task.completedPages }}/{{ task.totalPages }}
            </span>
          </div>
        </div>
      </div>

      <div class="mt-4 grid gap-4 md:grid-cols-3 lg:grid-cols-6">
        <div>
          <div class="text-xs text-content-tertiary">创建时间</div>
          <div class="text-sm text-content-primary">{{ formatDateCN(task.createdAt) }}</div>
        </div>
        <div>
          <div class="text-xs text-content-tertiary">爬取耗时</div>
          <div class="text-sm text-content-primary">{{ formatDuration(task.crawlDuration) }}</div>
        </div>
        <div>
          <div class="text-xs text-content-tertiary">总字数</div>
          <div class="text-sm text-content-primary">{{ task.totalWordCount?.toLocaleString() || '-' }}</div>
        </div>
        <div>
          <div class="text-xs text-content-tertiary">AI 耗时</div>
          <div class="text-sm text-content-primary">{{ formatDuration(task.aiDuration) }}</div>
        </div>
        <div>
          <div class="text-xs text-content-tertiary">Token 用量</div>
          <div class="text-sm text-content-primary">{{ task.tokensUsed?.toLocaleString() || '-' }}</div>
        </div>
        <div v-if="task.articleId">
          <div class="text-xs text-content-tertiary">已转文章</div>
          <router-link :to="`/admin/article/edit/${task.articleId}`" class="text-sm text-primary hover:underline">
            查看 &rarr;
          </router-link>
        </div>
        <div v-else-if="task.dailyLogId">
          <div class="text-xs text-content-tertiary">已转日志</div>
          <router-link :to="`/admin/daily-log`" class="text-sm text-primary hover:underline">
            查看 &rarr;
          </router-link>
        </div>
      </div>

      <div v-if="task.errorMessage" class="mt-4 rounded-lg bg-error/10 p-3">
        <div class="text-xs font-medium text-error mb-1">错误信息</div>
        <div class="text-sm text-error/80">{{ task.errorMessage }}</div>
      </div>
    </div>

    <!-- AI Results Card -->
    <div v-if="task.aiTitle || task.aiSummary" class="mb-6 glass-card rounded-2xl p-6">
      <h3 class="mb-4 text-lg font-semibold text-content-primary">AI 整理结果</h3>

      <div v-if="task.aiTitle" class="mb-4">
        <div class="text-xs text-content-tertiary mb-1">标题</div>
        <div class="text-lg font-semibold text-content-primary">{{ task.aiTitle }}</div>
      </div>

      <div v-if="task.aiSummary" class="mb-4">
        <div class="text-xs text-content-tertiary mb-1">摘要</div>
        <div class="text-sm text-content-secondary leading-relaxed">{{ task.aiSummary }}</div>
      </div>

      <div v-if="task.aiKeyPoints?.length" class="mb-4">
        <div class="text-xs text-content-tertiary mb-1">关键点</div>
        <ul class="list-disc pl-5 space-y-1">
          <li v-for="(point, i) in task.aiKeyPoints" :key="i" class="text-sm text-content-secondary">
            {{ point }}
          </li>
        </ul>
      </div>

      <div v-if="task.aiTags?.length" class="mb-4">
        <div class="text-xs text-content-tertiary mb-1">标签</div>
        <div class="flex flex-wrap gap-2">
          <el-tag v-for="tag in task.aiTags" :key="tag" size="small" effect="plain">
            {{ tag }}
          </el-tag>
        </div>
      </div>

      <div v-if="task.aiCategory" class="mb-4">
        <div class="text-xs text-content-tertiary mb-1">分类</div>
        <div class="text-sm text-content-primary">{{ task.aiCategory }}</div>
      </div>

      <div v-if="task.aiFullContent" class="mt-4">
        <el-collapse>
          <el-collapse-item title="查看 AI 完整内容">
            <div
              class="prose prose-sm max-w-none dark:prose-invert text-sm text-content-secondary"
              v-html="renderMarkdown(task.aiFullContent)"
            />
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>

    <!-- Pages Card -->
    <div v-if="pages.length > 0" class="glass-card rounded-2xl p-6">
      <h3 class="mb-4 text-lg font-semibold text-content-primary">
        爬取页面 ({{ pages.length }})
      </h3>

      <el-tabs v-model="activePage" type="border-card">
        <el-tab-pane
          v-for="(page, idx) in pages"
          :key="page.id"
          :label="`页面 ${idx + 1}`"
          :name="idx"
        >
          <div class="space-y-3">
            <!-- Page Meta -->
            <div class="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
              <div>
                <div class="text-xs text-content-tertiary">URL</div>
                <a :href="page.url" target="_blank" rel="noopener" class="text-sm text-primary hover:underline break-all">
                  {{ page.url }}
                </a>
              </div>
              <div v-if="page.pageTitle">
                <div class="text-xs text-content-tertiary">标题</div>
                <div class="text-sm text-content-primary">{{ page.pageTitle }}</div>
              </div>
              <div>
                <div class="text-xs text-content-tertiary">状态</div>
                <el-tag
                  :type="page.crawlStatus === 2 ? 'success' : page.crawlStatus === 3 ? 'danger' : 'info'"
                  size="small"
                >
                  {{ page.crawlStatusLabel }}
                </el-tag>
              </div>
              <div>
                <div class="text-xs text-content-tertiary">字数 / 耗时</div>
                <div class="text-sm text-content-primary">
                  {{ page.wordCount?.toLocaleString() || '-' }} 字 /
                  {{ formatDuration(page.crawlDuration) }}
                </div>
              </div>
            </div>

            <div v-if="page.errorMessage" class="rounded-lg bg-error/10 p-3">
              <div class="text-sm text-error/80">{{ page.errorMessage }}</div>
            </div>

            <!-- Markdown Content -->
            <div v-if="page.rawMarkdown" class="rounded-lg border border-border bg-surface-tertiary/50 p-4">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-medium text-content-tertiary">Markdown 内容</span>
                <el-button size="small" text @click="toggleMarkdown(idx)">
                  {{ markdownExpanded[idx] ? '收起' : '展开' }}
                </el-button>
              </div>
              <div
                v-if="markdownExpanded[idx]"
                class="prose prose-sm max-w-none dark:prose-invert text-sm text-content-secondary"
                v-html="renderMarkdown(page.rawMarkdown)"
              />
              <div
                v-else
                class="text-sm text-content-secondary whitespace-pre-wrap font-mono leading-relaxed line-clamp-6"
              >
                {{ page.rawMarkdown }}
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    </template>

    <!-- Empty State -->
    <div v-if="!loading && !task" class="py-20 text-center">
      <el-empty description="任务不存在" />
      <el-button type="primary" class="mt-4" @click="goBack">返回列表</el-button>
    </div>

    <!-- Convert Dialogs -->
    <ConvertArticleDialog
      v-model:visible="showConvertArticle"
      :task-id="taskId"
      :ai-title="task?.aiTitle"
      @success="(articleId) => { if (task) task.articleId = String(articleId) }"
    />
    <ConvertDailyLogDialog
      v-model:visible="showConvertDailyLog"
      :task-id="taskId"
      @success="(logId) => { if (task) task.dailyLogId = String(logId) }"
    />
  </div>
</template>
