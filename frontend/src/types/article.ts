import type { PageQuery } from './api'

export interface Article {
  id: number
  title: string
  slug: string
  content: string
  contentHtml: string
  summary: string
  cover: string
  categoryId: number
  categoryName: string
  userId: number
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
  tags: Tag[]
  tagIds?: number[]
}

export interface ArticleQuery extends PageQuery {
  categoryId?: number
  tagId?: number
  keyword?: string
  sort?: string
}

export interface ArticleListResult {
  list: Article[]
  total: number
}

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
