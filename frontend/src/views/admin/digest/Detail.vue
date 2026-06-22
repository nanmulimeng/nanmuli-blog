<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getDigestByDate, getLatestDigest, getDigestByTaskId } from '@/api/collector'
import type { DigestDetail } from '@/types/collector'
import { CollectTaskStatusMap } from '@/types/collector'
import { ArrowLeft, Refresh, Calendar } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/markdown'
import { sanitize } from '@/utils/sanitize'
import { usePolling } from '@/composables/usePolling'
import { getDigestCategoryColor } from '@/constants/digest'
import { POLLING_INTERVAL } from '@/constants/api'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const digest = ref<DigestDetail | null>(null)

// 路由参数解析：/admin/digest/latest | /admin/digest/:date | /admin/digest/task/:id
const routeMode = computed(() => {
  if (route.name === 'AdminDigestTaskDetail') return 'task'
  if (route.name === 'AdminDigestLatest' || !route.params.date) return 'latest'
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

const qualityEvaluation = computed(() => digest.value?.quality_evaluation ?? null)
const sectionQualityScores = computed(() => {
  return (qualityEvaluation.value?.section_scores ?? []).filter(score => score.name !== '__digest_output__')
})
const outputQuality = computed(() => {
  return (qualityEvaluation.value?.section_scores ?? []).find(score => score.name === '__digest_output__') ?? null
})
const sourceDiagnostics = computed(() => (qualityEvaluation.value?.source_diagnostics ?? []).slice(0, 6))
const nextRunActions = computed(() => qualityEvaluation.value?.next_run_actions ?? null)
const nextRunActionSources = computed(() => Object.values(nextRunActions.value?.sources ?? {}).slice(0, 6))
const taskDiagnostics = computed(() => digest.value?.diagnostics ?? null)
const orchestratorPlanLogs = computed(() => {
  const plan = digest.value?.orchestrator_plan
  if (Array.isArray(plan)) return plan
  return plan?.plan_log ?? []
})
const searchDiagnostics = computed(() => {
  const plan = digest.value?.orchestrator_plan
  if (!plan || Array.isArray(plan)) return []
  return plan.search_diagnostics ?? []
})
const eventDiagnostics = computed(() => {
  const plan = digest.value?.orchestrator_plan
  if (!plan || Array.isArray(plan)) return null
  return plan.event_diagnostics ?? null
})
const eventSamples = computed(() => eventDiagnostics.value?.sample_events ?? [])
const optimizationActionOutcome = computed(() => {
  const plan = digest.value?.orchestrator_plan
  if (!plan || Array.isArray(plan)) return null
  return plan.optimization_action_outcome ?? null
})
const optimizationActionSnapshot = computed(() => optimizationActionOutcome.value?.action_snapshot ?? null)
const optimizationActionResult = computed(() => optimizationActionOutcome.value?.result ?? null)
const optimizationSectionCounts = computed(() => {
  return Object.entries(optimizationActionResult.value?.section_result_counts ?? {})
})

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
  return getDigestCategoryColor(category)
}

function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return '-'
  const normalized = score > 1 ? score : score * 100
  return `${Math.round(normalized)}`
}

function normalizedScore(score: number | null | undefined): number | null {
  if (score === null || score === undefined) return null
  return score > 1 ? score / 100 : score
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

function scoreTagType(score: number | null | undefined): 'success' | 'warning' | 'danger' | 'info' {
  const normalized = normalizedScore(score)
  if (normalized === null) return 'info'
  if (normalized >= 0.75) return 'success'
  if (normalized >= 0.6) return 'warning'
  return 'danger'
}

function sectionStatusLabel(status: string | undefined): string {
  const labels: Record<string, string> = {
    completed: '完成',
    skipped: '跳过',
    failed: '失败',
    partial: '部分完成',
  }
  return status ? (labels[status] || status) : '-'
}

function publishStageLabel(stage: string | null | undefined): string {
  const labels: Record<string, string> = {
    pre_generated: '预生成',
    fallback: 'AI 回退整理',
  }
  return stage ? (labels[stage] || stage) : '-'
}

function verdictLabel(verdict: string | null | undefined): string {
  const labels: Record<string, string> = {
    keep: '保留',
    review: '需复核',
    filter: '过滤',
  }
  return verdict ? (labels[verdict] || verdict) : '-'
}

function actionLabel(action: string | null | undefined): string {
  const labels: Record<string, string> = {
    skip: '下次跳过',
    deprioritize: '下次降权',
  }
  return action ? (labels[action] || action) : '-'
}

function actionTagType(action: string | null | undefined): 'success' | 'warning' | 'danger' | 'info' {
  if (action === 'skip') return 'danger'
  if (action === 'deprioritize') return 'warning'
  return 'info'
}

function diagnosticTagType(severity: string | undefined): 'success' | 'warning' | 'danger' | 'info' {
  if (severity === 'success' || severity === 'warning' || severity === 'danger') return severity
  return 'info'
}

function optimizationVerdictTagType(verdict: string | undefined): 'success' | 'warning' | 'danger' | 'info' {
  if (verdict === 'positive') return 'success'
  if (verdict === 'needs_review') return 'warning'
  if (verdict === 'negative') return 'danger'
  return 'info'
}

function formatDomains(domains: string[] | undefined): string {
  return (domains ?? []).join(', ')
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  return `${Math.round(value * 100)}%`
}

function goBack(): void {
  router.push('/admin/digest')
}

// 使用 usePolling 替代手动 setInterval 轮询
const { start: startPolling, stop: stopPolling } = usePolling(
  fetchDigest,
  POLLING_INTERVAL.DIGEST_STATUS,
  {
    immediate: false,
    condition: () => isActive.value && !loading.value,
  },
)

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

      <div v-if="taskDiagnostics" class="mb-6 rounded-xl border border-border bg-surface-secondary p-4">
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <div class="text-sm font-medium text-content-primary">失败诊断</div>
          <el-tag :type="diagnosticTagType(taskDiagnostics.failure?.severity)" size="small">
            {{ taskDiagnostics.failure?.label || '暂无异常' }}
          </el-tag>
          <el-tag size="small" effect="plain">
            阶段 {{ taskDiagnostics.stage }}
          </el-tag>
        </div>
        <div class="text-sm text-content-secondary">
          {{ taskDiagnostics.summary }}
        </div>
        <div v-if="taskDiagnostics.failure?.action_hint" class="mt-2 text-sm text-content-secondary">
          建议：{{ taskDiagnostics.failure.action_hint }}
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <el-tag
            v-for="(enabled, key) in taskDiagnostics.signals"
            v-show="enabled"
            :key="key"
            type="info"
            size="small"
            effect="plain"
          >
            {{ key }}
          </el-tag>
        </div>
      </div>

      <!-- Highlight Banner -->
      <div v-if="digest.highlight" class="mb-6 rounded-xl bg-primary/5 border border-primary/20 p-4">
        <div class="text-sm font-medium text-primary">今日亮点</div>
        <div class="mt-1 text-sm text-content-primary">{{ digest.highlight }}</div>
      </div>

      <!-- Quality Evaluation -->
      <div v-if="qualityEvaluation" class="mb-6 rounded-xl border border-border bg-surface-secondary p-4">
        <div class="mb-3 flex flex-wrap items-center gap-3">
          <div class="text-sm font-medium text-content-primary">质量评估</div>
          <el-tag :type="scoreTagType(qualityEvaluation.overall_score)" size="small">
            总分 {{ formatScore(qualityEvaluation.overall_score) }}
          </el-tag>
          <el-tag
            v-if="qualityEvaluation.publishable === false"
            type="danger"
            size="small"
          >
            质量门拒绝
          </el-tag>
          <el-tag
            v-else-if="qualityEvaluation.publishable === true"
            type="success"
            size="small"
          >
            可发布
          </el-tag>
          <el-tag
            v-if="qualityEvaluation.stage"
            type="info"
            size="small"
            effect="plain"
          >
            {{ publishStageLabel(qualityEvaluation.stage) }}
          </el-tag>
          <el-tag
            v-for="weakness in qualityEvaluation.weaknesses"
            :key="weakness"
            type="warning"
            size="small"
            effect="plain"
          >
            {{ dimensionLabel(weakness) }}
          </el-tag>
        </div>

        <div class="mb-3 flex flex-wrap gap-2">
          <el-tag
            v-for="(score, key) in qualityEvaluation.dimensions"
            :key="key"
            :type="scoreTagType(score)"
            size="small"
            effect="plain"
          >
            {{ dimensionLabel(String(key)) }} {{ formatScore(score) }}
          </el-tag>
        </div>

        <div v-if="sectionQualityScores.length" class="grid gap-2 md:grid-cols-2">
          <div
            v-for="score in sectionQualityScores"
            :key="score.name"
            class="rounded-lg border border-border bg-surface-primary px-3 py-2"
          >
            <div class="flex items-center justify-between gap-3">
              <span class="truncate text-sm font-medium text-content-primary">{{ dimensionLabel(score.name) }}</span>
              <el-tag :type="scoreTagType(score.fill_score)" size="small">
                {{ formatScore(score.fill_score) }}
              </el-tag>
            </div>
            <div class="mt-1 flex flex-wrap gap-3 text-xs text-content-secondary">
              <span>结果 {{ score.result_count ?? 0 }}</span>
              <span>状态 {{ sectionStatusLabel(score.status) }}</span>
            </div>
          </div>
        </div>

        <div v-if="sourceDiagnostics.length" class="mt-3 grid gap-2 md:grid-cols-2">
          <div
            v-for="source in sourceDiagnostics"
            :key="`${source.section}-${source.source_id || source.source_url || source.source_name}`"
            class="rounded-lg border border-border bg-surface-primary px-3 py-2"
          >
            <div class="flex items-center justify-between gap-3">
              <a
                v-if="source.source_url"
                :href="source.source_url"
                target="_blank"
                rel="noopener"
                class="truncate text-sm font-medium text-content-primary hover:text-primary"
              >
                {{ source.source_name || source.source_url }}
              </a>
              <span v-else class="truncate text-sm font-medium text-content-primary">
                {{ source.source_name || '未知来源' }}
              </span>
              <el-tag :type="scoreTagType(source.quality_score)" size="small">
                {{ formatScore(source.quality_score) }}
              </el-tag>
            </div>
            <div class="mt-1 flex flex-wrap gap-3 text-xs text-content-secondary">
              <span>{{ dimensionLabel(source.section) }}</span>
              <span>条目 {{ source.item_count }}</span>
              <span>判定 {{ verdictLabel(source.quality_verdict) }}</span>
            </div>
          </div>
        </div>

        <div
          v-if="nextRunActions && (nextRunActions.source_ids.skip.length || nextRunActions.source_ids.deprioritize.length || nextRunActions.source_urls?.skip.length || nextRunActions.source_urls?.deprioritize.length || nextRunActions.boost_sections.length)"
          class="mt-3 rounded-lg border border-border bg-surface-primary px-3 py-2"
        >
          <div class="mb-2 flex flex-wrap items-center gap-2 text-sm text-content-primary">
            <span>下次优化动作</span>
            <el-tag v-if="nextRunActions.source_ids.skip.length" type="danger" size="small">
              跳过 {{ nextRunActions.source_ids.skip.length }}
            </el-tag>
            <el-tag v-if="nextRunActions.source_ids.deprioritize.length" type="warning" size="small">
              降权 {{ nextRunActions.source_ids.deprioritize.length }}
            </el-tag>
            <el-tag
              v-for="section in nextRunActions.boost_sections.slice(0, 4)"
              :key="section"
              type="primary"
              size="small"
              effect="plain"
            >
              增强 {{ dimensionLabel(section) }}
            </el-tag>
          </div>
          <div v-if="nextRunActionSources.length" class="grid gap-2 md:grid-cols-2">
            <div
              v-for="source in nextRunActionSources"
              :key="`${source.action}-${source.source_id || source.source_url || source.source_name}`"
              class="rounded border border-border bg-surface-secondary px-3 py-2"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="truncate text-sm font-medium text-content-primary">
                  {{ source.source_name || source.source_url || source.source_id }}
                </span>
                <el-tag :type="actionTagType(source.action)" size="small">
                  {{ actionLabel(source.action) }}
                </el-tag>
              </div>
              <div class="mt-1 flex flex-wrap gap-3 text-xs text-content-secondary">
                <span>{{ dimensionLabel(source.section) }}</span>
                <span v-if="source.quality_score != null">质量 {{ formatScore(source.quality_score) }}</span>
                <span>{{ source.reason }}</span>
              </div>
            </div>
          </div>
          <div v-else-if="nextRunActions.reasons.length" class="space-y-1 text-xs text-content-secondary">
            <div v-for="reason in nextRunActions.reasons.slice(0, 4)" :key="reason">{{ reason }}</div>
          </div>
        </div>

        <div v-if="outputQuality" class="mt-3 rounded-lg border border-border bg-surface-primary px-3 py-2">
          <div class="flex items-center gap-2 text-sm text-content-primary">
            <span>成品质量</span>
            <el-tag :type="scoreTagType(outputQuality.score)" size="small">
              {{ formatScore(outputQuality.score) }}
            </el-tag>
          </div>
          <div v-if="outputQuality.issues?.length" class="mt-1 flex flex-wrap gap-2">
            <el-tag v-for="issue in outputQuality.issues" :key="issue" type="warning" size="small" effect="plain">
              {{ issue }}
            </el-tag>
          </div>
        </div>

        <div v-if="qualityEvaluation.suggestions?.length" class="mt-3 space-y-1 text-sm text-content-secondary">
          <div v-for="suggestion in qualityEvaluation.suggestions" :key="suggestion">
            {{ suggestion }}
          </div>
        </div>
      </div>

      <!-- Orchestrator Plan Log -->
      <el-collapse v-if="orchestratorPlanLogs.length" class="mb-6">
        <el-collapse-item title="总管 Agent 规划日志" name="plan">
          <div class="space-y-1 text-xs font-mono text-content-secondary">
            <div v-for="(log, idx) in orchestratorPlanLogs" :key="idx" class="py-0.5">
              {{ log }}
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>

      <div v-if="eventDiagnostics" class="mb-6 rounded-2xl p-5 glass-card">
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <div class="text-sm font-medium text-content-primary">Event Merge Diagnostics</div>
          <el-tag size="small" type="info" effect="plain">Events {{ eventDiagnostics.event_count }}</el-tag>
          <el-tag size="small" type="success" effect="plain">Merged {{ eventDiagnostics.merged_event_count }}</el-tag>
          <el-tag size="small" type="warning" effect="plain">Duplicate Inputs {{ eventDiagnostics.duplicate_input_count }}</el-tag>
          <el-tag size="small" type="info" effect="plain">Multi-source {{ eventDiagnostics.multi_source_event_count }}</el-tag>
          <el-tag size="small" type="info" effect="plain">Max Sources {{ eventDiagnostics.max_sources_per_event }}</el-tag>
          <el-tag size="small" type="info" effect="plain">Diversity {{ formatPercent(eventDiagnostics.source_diversity) }}</el-tag>
        </div>
        <el-table v-if="eventSamples.length" :data="eventSamples" border size="small">
          <el-table-column prop="category" label="Section" width="120" />
          <el-table-column prop="event_group_key" label="Event Key" min-width="180" show-overflow-tooltip />
          <el-table-column label="Primary URL" min-width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <a
                v-if="row.primary_url"
                :href="row.primary_url"
                target="_blank"
                rel="noopener noreferrer"
                class="text-primary hover:underline"
              >
                {{ row.primary_url }}
              </a>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="item_count" label="Sources" width="90" />
          <el-table-column label="Related Domains" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              {{ formatDomains(row.source_domains) }}
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="optimizationActionOutcome" class="mb-6 rounded-2xl p-5 glass-card">
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <div class="text-sm font-medium text-content-primary">Optimization Action Outcome</div>
          <el-tag
            :type="optimizationVerdictTagType(optimizationActionOutcome.verdict)"
            size="small"
          >
            {{ optimizationActionOutcome.verdict || 'unknown' }}
          </el-tag>
          <el-tag v-if="optimizationActionSnapshot?.confidence" type="info" size="small" effect="plain">
            confidence {{ optimizationActionSnapshot.confidence }}
          </el-tag>
          <el-tag v-if="optimizationActionResult?.saved_to_kb" type="success" size="small" effect="plain">
            saved to KB
          </el-tag>
          <el-tag v-else type="warning" size="small" effect="plain">
            KB not saved
          </el-tag>
        </div>

        <div class="grid gap-2 md:grid-cols-4">
          <div class="rounded-lg border border-border bg-surface-primary px-3 py-2">
            <div class="text-xs text-content-tertiary">Source ID skip</div>
            <div class="text-lg font-semibold text-content-primary">
              {{ optimizationActionSnapshot?.source_id_skip_count ?? 0 }}
            </div>
          </div>
          <div class="rounded-lg border border-border bg-surface-primary px-3 py-2">
            <div class="text-xs text-content-tertiary">Source ID deprioritize</div>
            <div class="text-lg font-semibold text-content-primary">
              {{ optimizationActionSnapshot?.source_id_deprioritize_count ?? 0 }}
            </div>
          </div>
          <div class="rounded-lg border border-border bg-surface-primary px-3 py-2">
            <div class="text-xs text-content-tertiary">Score</div>
            <div class="text-lg font-semibold text-content-primary">
              {{ formatScore(optimizationActionResult?.overall_score) }}
            </div>
          </div>
          <div class="rounded-lg border border-border bg-surface-primary px-3 py-2">
            <div class="text-xs text-content-tertiary">Section fill</div>
            <div class="text-lg font-semibold text-content-primary">
              {{ formatPercent(optimizationActionResult?.section_fill_ratio) }}
            </div>
          </div>
        </div>

        <div v-if="optimizationActionSnapshot?.boost_sections?.length" class="mt-3 flex flex-wrap gap-2">
          <el-tag
            v-for="section in optimizationActionSnapshot.boost_sections"
            :key="section"
            type="primary"
            size="small"
            effect="plain"
          >
            boost {{ dimensionLabel(section) }}
          </el-tag>
        </div>

        <div v-if="optimizationSectionCounts.length" class="mt-3 flex flex-wrap gap-2 text-xs text-content-secondary">
          <span
            v-for="[section, count] in optimizationSectionCounts"
            :key="section"
            class="rounded border border-border bg-surface-primary px-2 py-1"
          >
            {{ dimensionLabel(section) }}: {{ count }}
          </span>
        </div>

        <div v-if="optimizationActionOutcome.suggestions?.length" class="mt-3 space-y-1 text-sm text-content-secondary">
          <div v-for="suggestion in optimizationActionOutcome.suggestions" :key="suggestion">
            {{ suggestion }}
          </div>
        </div>
      </div>

      <div v-if="searchDiagnostics.length" class="mb-6 rounded-2xl p-5 glass-card">
        <div class="mb-3 text-sm font-medium text-content-primary">Search Diagnostics</div>
        <el-table :data="searchDiagnostics" border size="small">
          <el-table-column prop="section" label="Section" width="120" />
          <el-table-column prop="engine" label="Engine" width="90" />
          <el-table-column prop="intent" label="Intent" width="100" />
          <el-table-column prop="query" label="Query" min-width="220" show-overflow-tooltip />
          <el-table-column prop="requested" label="Req" width="70" />
          <el-table-column prop="returned" label="Ret" width="70" />
          <el-table-column prop="kept" label="Kept" width="80" />
          <el-table-column prop="filtered" label="Drop" width="80" />
          <el-table-column label="Top Domains" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              {{ formatDomains(row.top_domains) }}
            </template>
          </el-table-column>
        </el-table>
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
          v-html="sanitize(renderMarkdown(digest.ai_full_content))"
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
