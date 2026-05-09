import type { PageQuery } from './api'

// ============== Task ==============

export interface CollectTaskAiSearchMetadata {
  originalKeyword?: string
  optimizedKeyword?: string
  searchVariants?: string[]
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
  created_at: string
}

export interface DigestSchedulerStatus {
  running: boolean
  cron: string | null
  enabled: boolean
  next_run: string | null
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

export const CrawlerHealthStatus = {
  AVAILABLE: 'available',
  UNAVAILABLE: 'unavailable',
} as const

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
  createdAt: string
  updatedAt: string
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
