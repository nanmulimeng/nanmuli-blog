import type { PageQuery } from './api'
import type { Category } from './category'

export interface Article {
  id: number
  title: string
  slug: string
  content: string
  contentHtml: string
  summary: string
  cover: string
  categoryId: number
  categoryName?: string  // 从category中提取
  category?: Category    // 完整分类信息
  categoryPath?: Category[]  // 分类层级路径（如：后端开发 > Java）
  tags?: string[]        // SEO关键词列表（从分类继承）
  viewCount: number
  likeCount: number
  wordCount: number
  readingTime: number
  status: number
  isTop: boolean
  isOriginal: boolean
  originalUrl: string
  publishTime: string
  createTime: string
  updateTime: string
}

export interface ArticleQuery extends PageQuery {
  categoryId?: number  // 按叶子分类筛选
  keyword?: string
  sort?: string
}

export interface ArticleListResult {
  list: Article[]
  total: number
}

// Tag已废弃，使用多级分类替代
export interface Tag {
  id: number
  name: string
  slug: string
  color: string
}

export interface ArticleArchive {
  year: string
  month: string
  count: number
  articles?: ArticleSimple[]
}

export interface ArticleSimple {
  id: number
  title: string
  slug: string
  publishTime: string
}
