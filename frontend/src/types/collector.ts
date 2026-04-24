import type { PageQuery } from './api'

// ============== Task ==============

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
  taskType: 'single' | 'deep' | 'keyword'
  sourceUrl?: string
  keyword?: string
  searchEngine?: 'bing' | 'duckduckgo'
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

export const CollectTaskTypeMap: Record<string, { label: string; type: 'primary' | 'success' | 'warning' }> = {
  single: { label: '单页爬取', type: 'primary' },
  deep: { label: '深度爬取', type: 'success' },
  keyword: { label: '关键词搜索', type: 'warning' },
}

export const AiTemplateMap: Record<string, string> = {
  tech_summary: '技术文档摘要',
  tutorial: '教程提炼',
  comparison: '对比分析',
  knowledge_report: '知识报告',
  daily_digest: '每日技术日报',
  custom: '自定义',
}

export const CrawlerHealthStatus = {
  AVAILABLE: 'available',
  UNAVAILABLE: 'unavailable',
} as const
