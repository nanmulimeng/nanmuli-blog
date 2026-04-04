/**
 * 全局常量定义
 */

// 应用信息
export const APP_NAME = '楠木里博客'
export const APP_VERSION = '1.0.0'

// 分页配置
export const DEFAULT_PAGE_SIZE = 10
export const MAX_PAGE_SIZE = 100
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]

// 文章状态 (与后端一致)
export enum ArticleStatus {
  PUBLISHED = 1,
  DRAFT = 2,
  RECYCLED = 3,
}

export const ArticleStatusText: Record<number, string> = {
  [ArticleStatus.PUBLISHED]: '已发布',
  [ArticleStatus.DRAFT]: '草稿',
  [ArticleStatus.RECYCLED]: '回收站',
}

export const ArticleStatusMap: Record<number, { label: string; type: 'success' | 'warning' | 'danger' | 'info' }> = {
  [ArticleStatus.PUBLISHED]: { label: '已发布', type: 'success' },
  [ArticleStatus.DRAFT]: { label: '草稿', type: 'warning' },
  [ArticleStatus.RECYCLED]: { label: '回收站', type: 'danger' },
}

// 技能分类
export enum SkillCategory {
  LANGUAGE = 'language',
  FRAMEWORK = 'framework',
  TOOL = 'tool',
  OTHER = 'other',
}

export const SkillCategoryText: Record<string, string> = {
  [SkillCategory.LANGUAGE]: '编程语言',
  [SkillCategory.FRAMEWORK]: '框架',
  [SkillCategory.TOOL]: '工具',
  [SkillCategory.OTHER]: '其他',
}

// 心情类型
export enum DailyLogMood {
  HAPPY = 'happy',
  EXCITED = 'excited',
  NORMAL = 'normal',
  TIRED = 'tired',
}

export const DailyLogMoodText: Record<string, string> = {
  [DailyLogMood.HAPPY]: '开心',
  [DailyLogMood.EXCITED]: '兴奋',
  [DailyLogMood.NORMAL]: '平静',
  [DailyLogMood.TIRED]: '疲惫',
}

// 存储键名
export const STORAGE_KEYS = {
  TOKEN: 'blog_token',
  USER: 'blog_user',
  SETTINGS: 'blog_settings',
  THEME: 'blog_theme',
} as const

// 路由名称
export const ROUTE_NAMES = {
  HOME: 'Home',
  ARTICLE_LIST: 'ArticleList',
  ARTICLE_DETAIL: 'ArticleDetail',
  DAILY_LOG: 'DailyLogList',
  ADMIN_DASHBOARD: 'AdminDashboard',
} as const
