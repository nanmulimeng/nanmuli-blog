import { get, post, put, del } from '@/utils/request'
import type { Article, ArticleQuery, ArticleArchive } from '@/types/article'
import type { PageResult } from '@/types/api'

// 公开接口：获取已发布文章列表
export function getArticleList(params: ArticleQuery): Promise<PageResult<Article>> {
  return get<PageResult<Article>>('/article/list', { params })
}

// 管理后台接口：获取所有文章（包括草稿）
export function getAdminArticleList(params: ArticleQuery): Promise<PageResult<Article>> {
  return get<PageResult<Article>>('/admin/article/list', { params })
}

export function getArticleBySlug(slug: string): Promise<Article> {
  return get<Article>(`/article/${slug}`)
}

export function getArticleById(id: string): Promise<Article> {
  return get<Article>(`/admin/article/${id}`)
}

export function getTopArticles(limit = 5): Promise<Article[]> {
  return get<Article[]>('/article/top', { params: { limit } })
}

export function createArticle(data: Partial<Article>): Promise<string> {
  return post<string>('/admin/article', data)
}

export function updateArticle(id: string, data: Partial<Article>): Promise<void> {
  return put<void>(`/admin/article/${id}`, data)
}

export function deleteArticle(id: string): Promise<void> {
  return del<void>(`/admin/article/${id}`)
}

export function getArticleArchive(): Promise<ArticleArchive[]> {
  return get<ArticleArchive[]>('/article/archive')
}

export function recordArticleView(slug: string): Promise<void> {
  return post<void>(`/article/${slug}/view`)
}
