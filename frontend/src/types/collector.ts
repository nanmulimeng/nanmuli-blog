import type { PageQuery } from './api'

// ============== Task ==============

export interface CollectTaskAiSearchMetadata {
  originalKeyword?: string
  optimizedKeyword?: string
  searchVariants?: string[]
  diagnostics?: CollectTaskDiagnostics
}

export interface CollectTaskDiagnostics {
  stage: string
  summary: string
  failure: {
    category: string
    label: string
    severity: 'info' | 'warning' | 'danger' | 'success'
    action_hint: string
  }
  signals: Record<string, boolean>
}

export interface CollectTask {
  id: string
  taskType: string
  taskTypeLabel: string
  sourceUrl: string | null
  keyword: string | null
  searchEngine: string
  triggerType: string
  crawlMode: string
  aiTemplate: string
  maxDepth: number
  maxPages: number
  status: number
  statusLabel: string
  statusDisplay: string
  errorMessage: string | null
  totalPages: number
  completedPages: number
  progressPercent: number
  crawlDuration: number | null
  aiDuration: number | null
  tokensUsed: number | null
  totalWordCount: number | null
  aiTitle: string | null
  aiSummary: string | null
  aiKeyPoints: string[] | null
  aiTags: string[] | null
  aiCategory: string | null
  aiFullContent: string | null
  aiSearchMetadata: CollectTaskAiSearchMetadata | null
  diagnostics?: CollectTaskDiagnostics | null
  articleId: string | null
  dailyLogId: string | null
  createdAt: string
  updatedAt: string
}

export interface CollectTaskListDTO {
  id: string
  taskType: string
  taskTypeLabel: string
  sourceUrl: string | null
  keyword: string | null
  aiTitle: string | null
  aiSummary: string | null
  status: number
  statusLabel: string
  statusDisplay: string
  totalPages: number
  completedPages: number
  progressPercent: number
  totalWordCount: number | null
  tokensUsed: number | null
  articleId: string | null
  dailyLogId: string | null
  createdAt: string
}

// ============== Digest ==============

export interface DigestItem {
  title: string
  one_liner: string
  source_url: string
  source_name: string
}

export interface DigestSection {
  category: string
  category_name: string
  emoji: string
  items: DigestItem[]
}

export interface DigestListItem {
  id: number
  digest_date: string | null
  status: number
  status_label: string
  ai_title: string | null
  ai_summary: string | null
  ai_tags: string[] | null
  highlight: string | null
  error_message: string | null
  created_at: string
}

export interface DigestDetail {
  id: number
  digest_date: string | null
  status: number
  status_label: string
  ai_title: string | null
  ai_summary: string | null
  ai_tags: string[] | null
  highlight: string | null
  ai_full_content: string | null
  ai_duration: number | null
  ai_tokens_used: number | null
  error_message: string | null
  sections: DigestSection[]
  orchestrator_plan: string[] | DigestOrchestratorPlan | null
  diagnostics?: CollectTaskDiagnostics | null
  quality_evaluation?: DigestQualityEvaluation | null
  created_at: string
}

export interface DigestOrchestratorPlan {
  plan_log?: string[]
  search_diagnostics?: DigestSearchDiagnostic[]
}

export interface DigestSearchDiagnostic {
  section: string
  query: string
  engine: string
  intent?: string
  requested?: number
  returned: number
  kept: number
  filtered?: number
  top_domains?: string[]
}

export interface DigestQualityEvaluation {
  overall_score: number | null
  dimensions: Record<string, number | null>
  section_scores: DigestSectionQuality[]
  source_diagnostics?: DigestSourceDiagnostic[]
  next_run_actions?: DigestSourceActions | null
  weaknesses: string[]
  suggestions: string[]
  publishable?: boolean | null
  stage?: string | null
  created_at?: string
}

export interface DigestSourceActionSource {
  source_id?: string | number | null
  source_name: string
  source_url: string
  section: string
  item_count: number
  quality_score?: number | null
  quality_verdict?: string | null
  action: 'skip' | 'deprioritize'
  reason: string
}

export interface DigestSourceActions {
  digest_date?: string | null
  created_at?: string | null
  source_ids: {
    skip: Array<string | number>
    deprioritize: Array<string | number>
  }
  source_urls?: {
    skip: string[]
    deprioritize: string[]
  }
  boost_sections: string[]
  sources: Record<string, DigestSourceActionSource>
  reasons: string[]
  suggestions: string[]
  confidence: 'none' | 'low' | 'medium' | 'high' | string
}

export interface DigestSourceDiagnostic {
  section: string
  source_id?: string | number | null
  source_name: string
  source_url: string
  item_count: number
  quality_score?: number | null
  quality_verdict?: string | null
}

export interface DigestSectionQuality {
  name: string
  result_count?: number
  status?: string
  fill_score?: number
  score?: number
  issues?: string[]
  suggestions?: string[]
}

export interface DigestSchedulerStatus {
  running: boolean
  cron: string | null
  enabled: boolean
  next_run: string | null
  source_jobs: number
  digest_job_registered?: boolean
  ai_enabled?: boolean
  ai_configured?: boolean
  jobs?: DigestSchedulerJob[]
  latest_digest?: DigestSchedulerLatestDigest | null
  diagnostics?: DigestSchedulerDiagnostics | null
}

export interface DigestSchedulerDiagnostics {
  state: 'disabled' | 'running' | 'misconfigured' | 'idle' | 'latest_failed' | 'healthy' | string
  summary: string
  action_hint: string
  checks: DigestSchedulerDiagnosticsCheck[]
}

export interface DigestSchedulerDiagnosticsCheck {
  key: string
  label: string
  status: 'success' | 'warning' | 'danger' | 'info' | string
  message: string
}

export interface DigestSchedulerJob {
  id?: string | null
  name?: string | null
  next_run?: string | null
}

export interface DigestSchedulerLatestDigest {
  id?: number
  digest_date?: string | null
  status?: number
  status_label?: string
  error_message?: string | null
  created_at?: string | null
  diagnostics?: CollectTaskDiagnostics | null
}

export interface DigestListResult {
  total: number
  page: number
  size: number
  records: DigestListItem[]
}

export interface DigestSectionConfig {
  name: string
  keyword: string
  max_items: number
  time_range?: string
}

export interface DigestOptimizationTrend {
  trend: DigestQualityTrendItem[]
  count: number
  summary?: DigestQualitySummary
  latest?: DigestQualityTrendItem | null
  weak_dimensions?: Record<string, number>
  suggestions?: string[]
  next_run_actions?: DigestSourceActions | null
}

export interface DigestQualitySummary {
  average_score: number | null
  latest_score: number | null
  score_delta: number | null
  status: 'success' | 'warning' | 'danger' | 'unknown'
}

export interface DigestQualityTrendItem {
  digest_date: string | null
  overall_score: number | null
  angle_coverage?: number | null
  source_diversity?: number | null
  depth_coverage?: number | null
  temporal_coverage?: number | null
  perspective_balance?: number | null
  language_coverage?: number | null
  strategy_detail?: Array<Record<string, any>>
  weaknesses?: string[]
  suggestions?: string[]
  created_at?: string
}

export interface DigestSearchFeedbackResult {
  total: number
  limit: number
  records: DigestSearchFeedbackSnapshot[]
}

export interface DigestSearchFeedbackSnapshot {
  task_id: number
  digest_date: string | null
  status: number
  created_at: string | null
  diagnostics: DigestSearchDiagnostic[]
  summary: DigestSearchFeedbackSummary
}

export interface DigestSearchFeedbackSummary {
  total_queries: number
  total_returned: number
  total_kept: number
  total_filtered: number
  keep_rate: number
  zero_result_queries: DigestZeroResultQuery[]
  section_summaries: DigestSearchSectionSummary[]
  engine_summaries: DigestSearchEngineSummary[]
}

export interface DigestZeroResultQuery {
  section: string
  engine: string
  query: string
  returned: number
  kept: number
}

export interface DigestSearchSectionSummary {
  section: string
  queries: number
  returned: number
  kept: number
  filtered: number
  zero_result_queries: number
  keep_rate: number
  top_domains: string[]
}

export interface DigestSearchEngineSummary {
  engine: string
  queries: number
  returned: number
  kept: number
  filtered: number
  zero_result_queries: number
  keep_rate: number
  top_domains: string[]
}

export interface CollectPage {
  id: string
  taskId: string
  url: string
  pageTitle: string | null
  rawMarkdown: string | null
  pageMetadata: Record<string, any> | null
  crawlStatus: number
  crawlStatusLabel: string
  errorMessage: string | null
  crawlDuration: number | null
  wordCount: number | null
  sortOrder: number
  depth: number
  createdAt: string
}

// ============== Request Models ==============

export interface CreateCollectTaskCommand {
  taskType: 'single' | 'deep' | 'keyword' | 'digest'
  sourceUrl?: string
  keyword?: string
  searchEngine?: 'sogou' | 'bing' | 'baidu' | 'google'
  timeRange?: 'day' | 'week' | 'month' | 'year' | 'all'
  crawlMode?: 'single' | 'deep'
  maxDepth?: number
  maxPages?: number
  aiTemplate?: string
}

export interface ConvertToArticleCommand {
  title?: string
  categoryId?: string
}

export interface ConvertToDailyLogCommand {
  mood?: string
  weather?: string
  logDate?: string
  isPublic?: boolean
  categoryId?: string
}

export interface CollectTaskQuery extends PageQuery {
  status?: number
  taskType?: string
  keyword?: string
}

// ============== Enums ==============

export const CollectTaskStatusMap: Record<number, { label: string; type: 'info' | 'warning' | 'primary' | 'success' | 'danger'; display: string }> = {
  0: { label: '待处理', type: 'info', display: '排队中...' },
  1: { label: '爬取中', type: 'warning', display: '正在爬取网页...' },
  2: { label: '整理中', type: 'primary', display: 'AI 正在整理内容...' },
  3: { label: '已完成', type: 'success', display: '查看结果' },
  4: { label: '失败', type: 'danger', display: '失败' },
}

export const CollectTaskTypeMap: Record<string, { label: string; type: 'primary' | 'success' | 'warning' | 'danger' }> = {
  single: { label: '单页爬取', type: 'primary' },
  deep: { label: '深度爬取', type: 'success' },
  keyword: { label: '关键词搜索', type: 'warning' },
  digest: { label: '技术日报', type: 'danger' },
}

export const AiTemplateMap: Record<string, string> = {
  tech_summary: '技术文档摘要',
  tutorial: '教程提炼',
  comparison: '对比分析',
  knowledge_report: '知识报告',
  daily_digest: '每日技术日报',
}

// ============== Source ==============

export interface Source {
  id: string
  name: string
  type: string
  value: string
  contentCategory: string | null
  crawlMode: string | null
  maxDepth: number | null
  maxPages: number | null
  cssSelector: string | null
  aiTemplate: string | null
  scheduleCron: string | null
  freshnessHours: number | null
  isActive: boolean
  lastRunAt: string | null
  lastRunStatus: string | null
  runCount: number | null
  successCount: number | null
  failCount: number | null
  avgQualityScore: number | null
  lastResultCount: number | null
  lastError: string | null
  createdAt: string
  updatedAt: string
}

export interface SourceTestItem {
  success: boolean
  url: string
  title: string
  word_count: number
  markdown_len: number
  source_id?: string | null
  source_name?: string | null
  error?: string | null
}

export interface SourceTestResult {
  source_type: string
  source_value: string
  content_category: string
  total: number
  success_count: number
  failed_count: number
  crawlable: boolean
  items: SourceTestItem[]
}

export interface CreateSourceCommand {
  name: string
  type: string
  value: string
  contentCategory?: string
  crawlMode?: string
  maxDepth?: number
  maxPages?: number
  cssSelector?: string
  aiTemplate?: string
  scheduleCron?: string
  freshnessHours?: number
}

export interface UpdateSourceCommand extends CreateSourceCommand {
  isActive?: boolean
}

export const SourceTypeMap: Record<string, { label: string; type: 'info' | 'warning' | 'primary' | 'success' | 'danger' }> = {
  keyword: { label: '关键词', type: 'warning' },
  url: { label: 'URL', type: 'primary' },
  rss: { label: 'RSS', type: 'success' },
}

export const ContentCategoryMap: Record<string, { label: string; color: string }> = {
  hot_trend: { label: '热点趋势', color: '#ef4444' },
  open_source: { label: '开源项目', color: '#f59e0b' },
  tech_article: { label: '技术文章', color: '#3b82f6' },
  dev_tool: { label: '开发工具', color: '#10b981' },
  creative: { label: '创意发现', color: '#8b5cf6' },
  paper: { label: '论文研究', color: '#6366f1' },
}
