import type { PageQuery } from './api'
import type { Category } from './category'

// 注意：ID 使用 string 类型，因为 JavaScript number 无法精确表示 64 位整数（Long）
// 后端使用雪花算法生成 ID，超过 2^53-1，前端必须用 string 保持精度
export interface Article {
  id: string
  title: string
  slug: string
  content: string
  contentHtml: string
  summary: string
  cover: string
  categoryId: string
  categoryName?: string  // 从category中提取
  category?: Category    // 完整分类信息
  categoryPath?: Category[]  // 分类层级路径（如：后端开发 > Java）
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
  categoryId?: string  // 按叶子分类筛选
  keyword?: string
  sort?: string
}

export interface ArticleListResult {
  list: Article[]
  total: number
}


export interface ArticleArchive {
  year: string
  month: string
  count: number
  articles?: ArticleSimple[]
}

export interface ArticleSimple {
  id: string
  title: string
  slug: string
  publishTime: string
}
