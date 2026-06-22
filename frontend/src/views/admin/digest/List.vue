<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getDigestList, getDigestOptimizationTrend, getDigestRuntimeHealth, getDigestSchedulerStatus, getDigestSearchFeedback, triggerDigest } from '@/api/collector'
import type { DigestListItem, DigestOptimizationTrend, DigestRuntimeHealth, DigestSchedulerStatus, DigestSearchFeedbackResult } from '@/types/collector'
import { CollectTaskStatusMap } from '@/types/collector'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Calendar, View, Promotion, Timer, DataAnalysis } from '@element-plus/icons-vue'
import { usePolling } from '@/composables/usePolling'
import { PAGE_SIZE, POLLING_INTERVAL, DELAY } from '@/constants/api'

const router = useRouter()
const loading = ref(false)
const digests = ref<DigestListItem[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(PAGE_SIZE.DIGEST)
const triggerLoading = ref(false)
const schedulerStatus = ref<DigestSchedulerStatus | null>(null)
const qualityOverview = ref<DigestOptimizationTrend | null>(null)
const searchFeedback = ref<DigestSearchFeedbackResult | null>(null)
const runtimeHealth = ref<DigestRuntimeHealth | null>(null)
const loadError = ref<string | null>(null)

const qualitySummary = computed(() => qualityOverview.value?.summary ?? null)
const latestQuality = computed(() => qualityOverview.value?.latest ?? null)
const weakDimensions = computed(() => Object.entries(qualityOverview.value?.weak_dimensions ?? {}).slice(0, 4))
const qualitySuggestions = computed(() => (qualityOverview.value?.suggestions ?? []).slice(0, 3))
const latestSchedulerDigest = computed(() => schedulerStatus.value?.latest_digest ?? null)
const schedulerDiagnostics = computed(() => schedulerStatus.value?.diagnostics ?? null)
const latestSearchFeedback = computed(() => searchFeedback.value?.records?.[0] ?? null)
const latestSearchSummary = computed(() => latestSearchFeedback.value?.summary ?? null)
const searchSectionSummaries = computed(() => (latestSearchSummary.value?.section_summaries ?? []).slice(0, 5))
const searchEngineSummaries = computed(() => (latestSearchSummary.value?.engine_summaries ?? []).slice(0, 4))
const zeroResultQueries = computed(() => (latestSearchSummary.value?.zero_result_queries ?? []).slice(0, 3))
const runtimeChecks = computed(() => runtimeHealth.value?.checks ?? [])
const runtimeBlockingChecks = computed(() => runtimeChecks.value.filter(check => check.blocking).slice(0, 4))
const runtimeRecommendations = computed(() => (runtimeHealth.value?.recommendations ?? []).slice(0, 3))

async function fetchData(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const res = await getDigestList(currentPage.value, pageSize.value)
    digests.value = res.records
    total.value = res.total
  } catch (error: unknown) {
    loadError.value = error instanceof Error ? error.message : '日报列表加载失败'
  } finally {
    loading.value = false
  }
}

async function fetchSchedulerStatus(): Promise<void> {
  try {
    schedulerStatus.value = await getDigestSchedulerStatus()
  } catch (error: unknown) {
    schedulerStatus.value = null
    loadError.value = error instanceof Error ? error.message : '调度状态加载失败'
  }
}

async function fetchQualityOverview(): Promise<void> {
  try {
    qualityOverview.value = await getDigestOptimizationTrend(10)
  } catch (error: unknown) {
    qualityOverview.value = null
    loadError.value = error instanceof Error ? error.message : '质量趋势加载失败'
  }
}

async function fetchSearchFeedback(): Promise<void> {
  try {
    searchFeedback.value = await getDigestSearchFeedback(10)
  } catch (error: unknown) {
    searchFeedback.value = null
    loadError.value = error instanceof Error ? error.message : '搜索反馈加载失败'
  }
}

async function fetchRuntimeHealth(): Promise<void> {
  try {
    runtimeHealth.value = await getDigestRuntimeHealth()
  } catch (error: unknown) {
    runtimeHealth.value = null
    loadError.value = error instanceof Error ? error.message : '日报上线健康状态加载失败'
  }
}

function handlePageChange(page: number): void {
  currentPage.value = page
  fetchData()
}

function handleView(row: DigestListItem): void {
  if (row.status === 3 && row.ai_title && row.digest_date) {
    router.push(`/admin/digest/${row.digest_date}`)
  } else {
    router.push(`/admin/digest/task/${row.id}`)
  }
}

async function handleTrigger(): Promise<void> {
  try {
    // 检测今天是否已有日报
    const now = new Date()
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    const todayDigest = digests.value.find(d => d.digest_date?.startsWith(today) && d.status === 3)

    let res: { status: string; message: string; task_id?: number }
    if (todayDigest) {
      await ElMessageBox.confirm(
        '今日已有日报，确定要强制重新生成吗？',
        '重新生成',
        { type: 'warning', confirmButtonText: '强制重新生成', cancelButtonText: '取消' }
      )
      triggerLoading.value = true
      res = await triggerDigest(true)
    } else {
      await ElMessageBox.confirm('确定要手动触发生成今日技术日报吗？', '提示', { type: 'info' })
      triggerLoading.value = true
      res = await triggerDigest()
    }

    if (res.status === 'created') {
      ElMessage.success(res.message || '日报生成已触发')
      if (res.task_id) {
        router.push(`/admin/digest/task/${res.task_id}`)
        return
      }
      setTimeout(() => { fetchData(); fetchRuntimeHealth(); startPolling() }, DELAY.DIGEST_REFRESH)
    } else {
      ElMessage.warning(res.message || '日报生成已跳过')
    }
  } catch (error: unknown) {
    if (error === 'cancel' || (error instanceof Error && error.message === 'cancel')) return
    ElMessage.error(error instanceof Error ? error.message : '日报生成失败，请检查爬虫服务状态')
  } finally {
    triggerLoading.value = false
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return dateStr.slice(0, 10)
}

function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return '-'
  return `${Math.round(score * 100)}`
}

function formatDelta(delta: number | null | undefined): string {
  if (delta === null || delta === undefined) return '-'
  const sign = delta > 0 ? '+' : ''
  return `${sign}${Math.round(delta * 100)}`
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  return `${Math.round(value * 100)}%`
}

function sectionLabel(key: string): string {
  const labels: Record<string, string> = {
    hot_trend: '热点趋势',
    open_source: '开源项目',
    dev_tool: '开发工具',
    tech_article: '技术文章',
    paper: '论文研究',
  }
  return labels[key] || key
}

function dimensionLabel(key: string): string {
  const labels: Record<string, string> = {
    angle: '选题角度',
    source_diversity: '来源多样性',
    depth: '分析深度',
    temporal: '时效性',
    perspective: '观点平衡',
    language: '语言覆盖',
  }
  return labels[key] || key
}

function qualityTagType(status: string | undefined): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'success' || status === 'warning' || status === 'danger') return status
  return 'info'
}

function taskStatusTagType(status: number | undefined): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 3) return 'success'
  if (status === 4) return 'danger'
  if (status === 1 || status === 2) return 'warning'
  return 'info'
}

function schedulerStateLabel(state: string | undefined): string {
  const labels: Record<string, string> = {
    disabled: '未启用',
    running: '执行中',
    misconfigured: '配置异常',
    idle: '等待执行',
    latest_failed: '最近失败',
    healthy: '运行正常',
  }
  return state ? (labels[state] || state) : '未知'
}

function schedulerStateTagType(state: string | undefined): 'success' | 'warning' | 'danger' | 'info' {
  if (state === 'healthy') return 'success'
  if (state === 'latest_failed' || state === 'misconfigured') return 'danger'
  if (state === 'disabled' || state === 'idle' || state === 'running') return 'warning'
  return 'info'
}

function diagnosticCheckTagType(status: string | undefined): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'success' || status === 'warning' || status === 'danger') return status
  return 'info'
}

function runtimeHealthTagType(status: string | undefined): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'healthy' || status === 'success') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'danger') return 'danger'
  return 'info'
}

function hasActiveTasks(): boolean {
  return digests.value.some(d => d.status === 0 || d.status === 1 || d.status === 2)
}

// 使用 usePolling 替代手动 setInterval 轮询
const { start: startPolling } = usePolling(fetchData, POLLING_INTERVAL.DIGEST_STATUS, {
  immediate: false,
  condition: () => hasActiveTasks() && !loading.value,
})

onMounted(() => {
  fetchData()
  fetchSchedulerStatus()
  fetchQualityOverview()
  fetchSearchFeedback()
  fetchRuntimeHealth()
  startPolling()
})
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <el-icon :size="24" class="text-primary"><Calendar /></el-icon>
        <h2 class="text-xl font-bold text-content-primary">技术日报</h2>
      </div>
      <el-button type="primary" :icon="Promotion" :loading="triggerLoading" @click="handleTrigger">
        生成日报
      </el-button>
    </div>

    <div v-if="schedulerStatus" class="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface-secondary px-4 py-3 text-sm text-content-secondary">
      <div class="flex items-center gap-2 text-content-primary">
        <el-icon><Timer /></el-icon>
        <span>{{ schedulerStatus.enabled ? '自动日报已启用' : '自动日报未启用' }}</span>
      </div>
      <span>调度器: {{ schedulerStatus.running ? '运行中' : '未运行' }}</span>
      <span v-if="schedulerStatus.cron">Cron: {{ schedulerStatus.cron }}</span>
      <span v-if="schedulerStatus.next_run">下次: {{ schedulerStatus.next_run }}</span>
      <span>信息源任务: {{ schedulerStatus.source_jobs || 0 }}</span>
    </div>

    <el-alert
      v-if="loadError"
      class="mb-4"
      type="error"
      show-icon
      :closable="false"
      title="日报系统接口异常"
      :description="loadError"
    />

    <div
      v-if="runtimeHealth"
      class="mb-4 rounded-lg border border-border bg-surface-secondary px-4 py-3 text-sm text-content-secondary"
    >
      <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <span class="font-medium text-content-primary">上线健康</span>
          <el-tag :type="runtimeHealthTagType(runtimeHealth.status)" size="small">
            {{ runtimeHealth.status === 'healthy' ? '可验证' : runtimeHealth.status }}
          </el-tag>
          <span>{{ runtimeHealth.summary.message }}</span>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <span>核心板块 {{ runtimeHealth.config.configured_core_sections.length }}/{{ runtimeHealth.config.min_core_sections }}</span>
          <span>优化置信度 {{ runtimeHealth.optimization_safety.confidence }}</span>
          <span v-if="runtimeHealth.search_feedback.latest_keep_rate != null">
            搜索保留率 {{ formatPercent(runtimeHealth.search_feedback.latest_keep_rate) }}
          </span>
        </div>
      </div>

      <div class="mb-2 flex flex-wrap gap-2">
        <el-tag
          v-for="check in runtimeChecks"
          :key="check.key"
          :type="diagnosticCheckTagType(check.status)"
          size="small"
          effect="plain"
          :title="check.message"
        >
          {{ check.label }}: {{ check.message }}
        </el-tag>
      </div>

      <div v-if="runtimeBlockingChecks.length || runtimeRecommendations.length" class="flex flex-wrap gap-2">
        <el-tag
          v-for="check in runtimeBlockingChecks"
          :key="`blocking-${check.key}`"
          type="danger"
          size="small"
          effect="plain"
        >
          阻塞: {{ check.label }}
        </el-tag>
        <span
          v-for="item in runtimeRecommendations"
          :key="item"
          class="max-w-[360px] truncate"
          :title="item"
        >
          {{ item }}
        </span>
      </div>
    </div>

    <div
      v-if="schedulerDiagnostics"
      class="mb-4 rounded-lg border border-border bg-surface-secondary px-4 py-3 text-sm text-content-secondary"
    >
      <div class="mb-2 flex flex-wrap items-center gap-2">
        <span class="text-content-primary">调度诊断</span>
        <el-tag :type="schedulerStateTagType(schedulerDiagnostics.state)" size="small">
          {{ schedulerStateLabel(schedulerDiagnostics.state) }}
        </el-tag>
        <span class="text-content-primary">{{ schedulerDiagnostics.summary }}</span>
      </div>
      <div class="mb-2 flex flex-wrap gap-2">
        <el-tag
          v-for="check in schedulerDiagnostics.checks"
          :key="check.key"
          :type="diagnosticCheckTagType(check.status)"
          size="small"
          effect="plain"
          :title="check.message"
        >
          {{ check.label }}：{{ check.message }}
        </el-tag>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span v-if="schedulerDiagnostics.action_hint">
          建议：{{ schedulerDiagnostics.action_hint }}
        </span>
        <template v-if="latestSchedulerDigest">
          <span>最近执行</span>
          <el-tag :type="taskStatusTagType(latestSchedulerDigest.status)" size="small">
            {{ latestSchedulerDigest.status_label || CollectTaskStatusMap[latestSchedulerDigest.status ?? -1]?.display || '未知' }}
          </el-tag>
          <span v-if="latestSchedulerDigest.digest_date">{{ formatDate(latestSchedulerDigest.digest_date) }}</span>
          <span v-if="latestSchedulerDigest.diagnostics?.failure?.category">
            {{ latestSchedulerDigest.diagnostics.failure.category }}
          </span>
          <span v-if="latestSchedulerDigest.error_message" class="text-error">
            {{ latestSchedulerDigest.error_message }}
          </span>
        </template>
      </div>
    </div>

    <div v-if="schedulerStatus && !schedulerDiagnostics" class="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-secondary px-4 py-3 text-sm text-content-secondary">
      <span class="text-content-primary">调度诊断</span>
      <el-tag :type="schedulerStatus.digest_job_registered ? 'success' : 'warning'" size="small" effect="plain">
        日报任务 {{ schedulerStatus.digest_job_registered ? '已注册' : '未注册' }}
      </el-tag>
      <el-tag :type="schedulerStatus.ai_configured ? 'success' : 'warning'" size="small" effect="plain">
        AI {{ schedulerStatus.ai_enabled ? (schedulerStatus.ai_configured ? '可用' : '缺少 Key') : '未启用' }}
      </el-tag>
      <template v-if="latestSchedulerDigest">
        <span>最近执行:</span>
        <el-tag :type="taskStatusTagType(latestSchedulerDigest.status)" size="small">
          {{ latestSchedulerDigest.status_label || CollectTaskStatusMap[latestSchedulerDigest.status ?? -1]?.display || '未知' }}
        </el-tag>
        <span v-if="latestSchedulerDigest.digest_date">{{ formatDate(latestSchedulerDigest.digest_date) }}</span>
        <span v-if="latestSchedulerDigest.diagnostics?.failure?.category">
          {{ latestSchedulerDigest.diagnostics.failure.category }}
        </span>
        <span v-if="latestSchedulerDigest.error_message" style="color: var(--el-color-danger)">
          {{ latestSchedulerDigest.error_message }}
        </span>
      </template>
    </div>

    <div
      v-if="qualitySummary"
      class="mb-4 grid gap-3 rounded-lg border border-border bg-surface-secondary px-4 py-3 text-sm md:grid-cols-[auto_1fr]"
    >
      <div class="flex flex-wrap items-center gap-3">
        <div class="text-content-primary">
          <span class="text-content-secondary">最近质量</span>
          <span class="ml-2 text-lg font-semibold">{{ formatScore(qualitySummary.latest_score) }}</span>
        </div>
        <el-tag :type="qualityTagType(qualitySummary.status)" size="small">
          {{ qualitySummary.status === 'success' ? '稳定' : qualitySummary.status === 'danger' ? '需处理' : qualitySummary.status === 'warning' ? '观察' : '暂无数据' }}
        </el-tag>
        <span class="text-content-secondary">均分 {{ formatScore(qualitySummary.average_score) }}</span>
        <span class="text-content-secondary">变化 {{ formatDelta(qualitySummary.score_delta) }}</span>
        <span v-if="latestQuality?.digest_date" class="text-content-secondary">
          {{ formatDate(latestQuality.digest_date) }}
        </span>
      </div>
      <div class="flex flex-wrap items-center gap-2 md:justify-end">
        <el-tag
          v-for="[key, count] in weakDimensions"
          :key="key"
          type="warning"
          size="small"
          effect="plain"
        >
          {{ dimensionLabel(key) }} x{{ count }}
        </el-tag>
        <span
          v-for="suggestion in qualitySuggestions"
          :key="suggestion"
          class="max-w-[260px] truncate text-content-secondary"
          :title="suggestion"
        >
          {{ suggestion }}
        </span>
      </div>
    </div>

    <div
      v-if="latestSearchSummary"
      class="mb-4 rounded-lg border border-border bg-surface-secondary px-4 py-3 text-sm text-content-secondary"
    >
      <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2 text-content-primary">
          <el-icon><DataAnalysis /></el-icon>
          <span class="font-medium">搜索反馈</span>
          <span v-if="latestSearchFeedback?.digest_date" class="text-content-secondary">
            {{ formatDate(latestSearchFeedback.digest_date) }}
          </span>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <span>Query {{ latestSearchSummary.total_queries }}</span>
          <span>返回 {{ latestSearchSummary.total_returned }}</span>
          <span>保留 {{ latestSearchSummary.total_kept }}</span>
          <el-tag
            :type="latestSearchSummary.keep_rate >= 0.5 ? 'success' : latestSearchSummary.keep_rate >= 0.25 ? 'warning' : 'danger'"
            size="small"
            effect="plain"
          >
            保留率 {{ formatPercent(latestSearchSummary.keep_rate) }}
          </el-tag>
        </div>
      </div>

      <div class="grid gap-3 lg:grid-cols-2">
        <div class="space-y-2">
          <div class="text-xs font-medium text-content-secondary">板块表现</div>
          <div class="flex flex-wrap gap-2">
            <el-tag
              v-for="section in searchSectionSummaries"
              :key="section.section"
              size="small"
              effect="plain"
              :type="section.keep_rate >= 0.5 ? 'success' : section.keep_rate >= 0.25 ? 'warning' : 'danger'"
              :title="section.top_domains.join(', ')"
            >
              {{ sectionLabel(section.section) }} {{ section.kept }}/{{ section.returned }} · {{ formatPercent(section.keep_rate) }}
            </el-tag>
          </div>
        </div>

        <div class="space-y-2">
          <div class="text-xs font-medium text-content-secondary">搜索引擎</div>
          <div class="flex flex-wrap gap-2">
            <el-tag
              v-for="engine in searchEngineSummaries"
              :key="engine.engine"
              size="small"
              effect="plain"
              :type="engine.zero_result_queries > 0 ? 'warning' : 'success'"
              :title="engine.top_domains.join(', ')"
            >
              {{ engine.engine }} {{ engine.kept }}/{{ engine.returned }} · 零结果 {{ engine.zero_result_queries }}
            </el-tag>
          </div>
        </div>
      </div>

      <div v-if="zeroResultQueries.length" class="mt-3 flex flex-wrap gap-2">
        <span class="text-xs font-medium text-content-secondary">需要关注</span>
        <el-tag
          v-for="item in zeroResultQueries"
          :key="`${item.section}-${item.engine}-${item.query}`"
          size="small"
          type="warning"
          effect="plain"
          :title="item.query"
        >
          {{ sectionLabel(item.section) }} / {{ item.engine }}：{{ item.query }}
        </el-tag>
      </div>
    </div>

    <el-table v-loading="loading" :data="digests" border>
      <el-table-column label="日期" width="130">
        <template #default="{ row }">
          <span class="font-medium text-content-primary">{{ formatDate(row.digest_date) }}</span>
        </template>
      </el-table-column>

      <el-table-column label="标题" min-width="260">
        <template #default="{ row }">
          <div v-if="row.ai_title" class="text-sm font-medium text-content-primary">
            {{ row.ai_title }}
          </div>
          <div v-else-if="row.status === 0 || row.status === 1 || row.status === 2" class="text-content-tertiary">生成中...</div>
          <div v-else-if="row.error_message" class="text-sm text-error/80 truncate" :title="row.error_message">
            {{ row.error_message }}
          </div>
          <div v-else class="text-content-tertiary">-</div>
          <div v-if="row.highlight" class="mt-1 truncate text-xs text-content-secondary" :title="row.highlight">
            {{ row.highlight }}
          </div>
        </template>
      </el-table-column>

      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="CollectTaskStatusMap[row.status]?.type || 'info'" size="small">
            <div class="flex items-center gap-1">
              <el-icon v-if="row.status === 1 || row.status === 2" :size="12" class="animate-spin">
                <Refresh />
              </el-icon>
              {{ row.status_label || CollectTaskStatusMap[row.status]?.label || '未知' }}
            </div>
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="标签" width="200">
        <template #default="{ row }">
          <div v-if="row.ai_tags?.length" class="flex flex-wrap gap-1">
            <el-tag v-for="tag in row.ai_tags.slice(0, 4)" :key="tag" size="small" effect="plain">
              {{ tag }}
            </el-tag>
            <el-tag v-if="row.ai_tags.length > 4" size="small" effect="plain" type="info">
              +{{ row.ai_tags.length - 4 }}
            </el-tag>
          </div>
          <span v-else class="text-content-tertiary">-</span>
        </template>
      </el-table-column>

      <el-table-column label="创建时间" width="110">
        <template #default="{ row }">
          <div class="text-xs text-content-secondary">
            {{ row.created_at?.slice(0, 10) || '-' }}
          </div>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="80" fixed="right" align="center">
        <template #default="{ row }">
          <el-button
            type="primary"
            size="small"
            :icon="View"
            :disabled="row.status === 0 || row.status === 1 || row.status === 2"
            @click="handleView(row)"
            title="查看详情"
          />
        </template>
      </el-table-column>
    </el-table>

    <div class="mt-4 flex justify-end">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :pager-count="7"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <div v-if="!loading && digests.length === 0" class="mt-10 text-center">
      <el-empty description="暂无日报数据">
        <el-button type="primary" @click="handleTrigger">生成第一份日报</el-button>
      </el-empty>
    </div>
  </div>
</template>
