import { get, post, put, del } from '@/utils/request'
import type { Article, ArticleListResult, ArticleQuery } from '@/types/article'
import type { PageResult } from '@/types/api'

export function getArticleList(params: ArticleQuery): Promise<PageResult<Article>> {
  return get<PageResult<Article>>('/article/list', { params })
}

export function getArticleBySlug(slug: string): Promise<Article> {
  return get<Article>(`/article/${slug}`)
}

export function getTopArticles(limit = 5): Promise<Article[]> {
  return get<Article[]>('/article/top', { params: { limit } })
}

export function createArticle(data: Partial<Article>): Promise<number> {
  return post<number>('/admin/article', data)
}

export function updateArticle(id: number, data: Partial<Article>): Promise<void> {
  return put<void>(`/admin/article/${id}`, data)
}

export function deleteArticle(id: number): Promise<void> {
  return del<void>(`/admin/article/${id}`)
}
